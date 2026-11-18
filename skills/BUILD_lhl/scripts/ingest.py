# -*- coding: utf-8 -*-
"""ingest.py — 落库：归一 + 合并 + 图片重命名 + 幂等（BUILD_lhl）

用法:
  # 1) 只补信息词条（不动其他字段）
  python ingest.py --lib data/lean_measures.json --img data/图片库 --backfill-terms

  # 2) 新素材入库
  python ingest.py --recs recs.json --lib data/lean_measures.json --img data/图片库 \
      --map-file map.json --merge-map merge_map.json --source 优化工艺 --chapter 工艺优化 --type 工艺优化

  # 3) 演练
  python ingest.py ... --dry-run

输入 recs.json 每条:
  { "title": "措施名", "实施效果": "...", "优化效果": "...", "files": ["tmp/a.png"], "page": 3 }
  兼容旧键: effect(->优化效果) / points(->实施效果)

map.json:      { "措施名": ["分部", "子分部", "分项", "适用部位"] }
merge_map.json:{ "措施名": 目标记录id }
"""
import argparse
import json
import os
import re
import shutil
import sys

GEN = r'(施工工艺|施工工法|高效工艺|施工技术|工法|工艺|技术|应用|施工)$'
ACTIONS = ['一次成型', '一次浇筑', '一次预埋', '一次带出', '免抹灰', '免开槽', '免收口', '免砌筑',
           '免吊洞', '免穿孔', '永临结合', '模块化', '预制拼装', '精准定位', '精准预留',
           '快拆', '随主体', '同步安装', '一次预埋成型', '定型化', '隐藏式', '暗埋']
MATERIALS = ['铝模', '木模', '钢模', 'PP-R', 'U-PVC', 'PVC', '止水节', '止水螺杆', '套管', '线盒',
             '穿筋盒', '桥架', '线管', '配电箱', '集分水器', '消火栓', '桥架节', '砌块', '钢筋',
             '螺杆', '拉环', '防护门', '防护棚', '悬挑架', '施工电梯', '塔吊']
THEMES = {'防水': ['防水', '渗漏', '止水'], '免抹灰': ['免抹灰', '免收口'],
          '工期': ['工期', '穿插'], '成本': ['成本', '费用', '节省'],
          '质量': ['质量', '空鼓', '开裂']}
BAD_CHARS = re.compile(r'[\\/:*?"<>|]')


def clean(s):
    s = re.sub(r'[♦◆◊]', '', s or '')
    return re.sub(r'\s+', '', s).strip()


def sents(s):
    return [p.strip() for p in re.split(r'(?<=[；;。])', clean(s)) if p.strip()]


def enhance(old, add):
    old = old or ''
    have = {re.sub(r'[^\u4e00-\u9fa5A-Za-z0-9]', '', x) for x in sents(old)}
    extra = [x for x in sents(add) if re.sub(r'[^\u4e00-\u9fa5A-Za-z0-9]', '', x) not in have]
    if not extra:
        return old, 0
    body = '；'.join(x.rstrip('；;。') for x in extra)
    return (old.rstrip('；;。') + '；' + body + '。') if old else body + '。', len(extra)


def core(s):
    s = clean(s)
    for _ in range(2):
        s2 = re.sub(GEN, '', s)
        if s2 == s:
            break
        s = s2
    return s


def make_terms(r):
    """信息词条：核心对象;动作;材料;部位;分项;主题（去重，3~8 个）"""
    terms = []
    c = core(r.get('优化措施名称', ''))
    if c:
        terms.append(c)
    blob = ' '.join([r.get('优化措施名称', ''), r.get('优化内容', ''), r.get('优化效果', '')])
    for w in ACTIONS:
        if w in blob and w not in terms:
            terms.append(w)
    for m in MATERIALS:
        if m.lower() in blob.lower() and m not in terms:
            terms.append(m)
    for p in re.split(r'[、，,/]', r.get('适用部位', '') or ''):
        p = p.strip()
        if p and p not in terms and p not in ('全楼层', '全场'):
            terms.append(p)
    it = (r.get('分项工程') or '').strip()
    if it and it not in terms:
        terms.append(it)
    # 主题词只补 1 个（按优先级），避免每条都挂满"工期/成本/质量"而失去区分度
    for theme, kws in THEMES.items():
        if any(k in blob for k in kws) and theme not in terms:
            terms.append(theme)
            break
    seen, out = set(), []
    for t in terms:
        t = t.strip(' ;；')
        if not t or t in ('施工', '工程', '优化', '做法', '技术') or re.fullmatch(r'[\d\.\-]+', t):
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return ';'.join(out[:8])


def numeric_suffix(name, used, existing):
    """<name>_序号.jpg，自动避让冲突"""
    base = BAD_CHARS.sub('', name)
    n = len(used) + 1
    while True:
        nm = '%s_%d.jpg' % (base, n)
        if nm not in existing:
            return nm
        n += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--recs')
    ap.add_argument('--lib', required=True)
    ap.add_argument('--img', required=True)
    ap.add_argument('--map-file')
    ap.add_argument('--merge-map')
    ap.add_argument('--source', default='')
    ap.add_argument('--chapter', default='工艺优化')
    ap.add_argument('--type', dest='typ', default='工艺优化')
    ap.add_argument('--subclass', default='')
    ap.add_argument('--backfill-terms', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()

    rows = json.load(open(a.lib, encoding='utf-8'))
    print('现有 %d 条' % len(rows))

    # —— 模式 1：补信息词条 ——
    if a.backfill_terms or not a.recs:
        n = 0
        for r in rows:
            if not (r.get('信息词条') or '').strip():
                r['信息词条'] = make_terms(r)
                n += 1
        print('补信息词条 %d 条' % n)
        for r in rows[:3]:
            print('  例: %s -> %s' % (r['优化措施名称'], r['信息词条']))
        if not a.dry_run:
            json.dump(rows, open(a.lib, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('已写入' if not a.dry_run else '演练模式，未写入')
        return

    recs = json.load(open(a.recs, encoding='utf-8'))
    mp = json.load(open(a.map_file, encoding='utf-8')) if a.map_file else {}
    mm = json.load(open(a.merge_map, encoding='utf-8')) if a.merge_map else {}

    if a.source and not a.force:
        hit = [r for r in rows if r.get('来源表') == a.source]
        if hit:
            print('!! 来源表「%s」已存在 %d 条记录，疑似重复执行。' % (a.source, len(hit)))
            print('   如确认要再并入一次，加 --force；否则请先 restore 备份。')
            sys.exit(2)

    by_id = {r['id']: r for r in rows}
    existing = set(os.listdir(a.img)) if os.path.isdir(a.img) else set()
    next_id = max([r['id'] for r in rows] or [0]) + 1
    log, n_new, n_merge, n_skip = [], 0, 0, 0

    for rec in recs:
        title = re.sub(r'\s+', '', rec.get('title') or rec.get('优化措施名称') or '')
        if not title:
            n_skip += 1
            continue
        eff = clean(rec.get('优化效果') or rec.get('effect') or '')
        pts = clean(rec.get('优化内容') or rec.get('points') or '')
        files = rec.get('files') or []
        tgt = by_id.get(mm.get(title))

        if tgt is not None:
            tgt['优化内容'], a1 = enhance(tgt.get('优化内容'), pts)
            tgt['优化效果'], a2 = enhance(tgt.get('优化效果'), eff)
            used = list(tgt.get('图片') or [])
            for fn in files:
                nm = numeric_suffix(tgt['优化措施名称'], used, existing)
                if not a.dry_run:
                    shutil.copy(os.path.join(os.path.dirname(a.recs), 'img', fn)
                                if not os.path.isabs(fn) else fn, os.path.join(a.img, nm))
                existing.add(nm)
                used.append(nm)
            tgt['图片'] = used
            tgt['信息词条'] = make_terms(tgt)
            n_merge += 1
            log.append(['合并', title, tgt['id'], tgt['优化措施名称'], len(files), a1 + a2])
            continue

        bu, sub, it, part = (mp.get(title) or ['', '', '', ''])[:4]
        row = {
            'id': next_id, '章节': a.chapter, '优化类型': a.typ,
            '手册分类': a.subclass or ('%s·默认' % a.source if a.source else a.typ),
            '分部工程': bu, '子分部工程': sub, '分项工程': it,
            '优化措施名称': title, '优化内容': pts, '优化效果': eff,
            '适用部位': part, '图片': [],
            '来源表': a.source or '未标注', '来源页': str(rec.get('page', '')),
        }
        used = []
        for fn in files:
            nm = numeric_suffix(title, used, existing)
            src = fn if os.path.isabs(fn) else os.path.join(os.path.dirname(a.recs), 'img', fn)
            if not a.dry_run:
                shutil.copy(src, os.path.join(a.img, nm))
            existing.add(nm)
            used.append(nm)
        row['图片'] = used
        row['信息词条'] = make_terms(row)
        rows.append(row)
        by_id[next_id] = row
        n_new += 1
        log.append(['新增', title, next_id, title, len(files), 0])
        next_id += 1

    print('合并 %d / 新增 %d / 跳过 %d -> 总计 %d 条' % (n_merge, n_new, n_skip, len(rows)))
    if a.dry_run:
        print('演练模式，未写入')
        return
    bak = a.lib + '.bak.json'
    shutil.copy(a.lib, bak)
    json.dump(rows, open(a.lib, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump({'log': log}, open(os.path.join(os.path.dirname(a.lib), 'merge_log.json'), 'w',
                                 encoding='utf-8'), ensure_ascii=False, indent=1)
    print('已写入 %s（备份 %s）' % (a.lib, bak))


if __name__ == '__main__':
    main()
