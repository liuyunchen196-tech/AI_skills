# -*- coding: utf-8 -*-
"""
dedupe_content.py — 库内「同部位同做法」内容级重复识别与合并

与 dedupe.py 的分工：
  dedupe.py         新素材入库前，新记录 vs 已有库的候选清单
  dedupe_content.py 库内自查：同分部分项 + 同部位 + 同做法 的重复表述

思路（三步筛）：
1. 按 分部工程 → 子分部 → 分项工程 排序，只在同一分部分项内互比；
2. 再看「适用部位」，有交集或同属一个部位域（楼层/地下/外围/全场）才比；
3. 比较「优化内容」的做法描述（名称/词条只作辅助）：
   名称 45% + 信息词条 25% + 内容包含度 30%。

⚠️ 相似度只用来**筛候选**，是否真重复必须逐组看原文，人工确认后写成
   decisions.json（[{"keep": 12, "drop": [34, 56], "why": "..."}]），再 --decisions 执行。
   纯阈值直接 --apply 只适合"已逐组确认过、组内取舍可交给脚本"的场景。

用法：
    python dedupe_content.py --lib <lean_measures.json> --out cand.csv          # 出候选
    python dedupe_content.py --lib <...> --decisions decisions.json             # 按确认清单合并
    python dedupe_content.py --lib <...> --apply                                # 按自动聚类合并（慎用）

合并动作：保留项吸收 drop 项的 图片（同名去重）、适用部位、信息词条，
         并在「别名」记原名称、「来源合并」记原溯源键；id 重排 1..N；
         首次合并前自动备份 <lib>.prededupe.json。
"""
import argparse
import csv
import difflib
import json
import os
import re
import shutil
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = ''
IMG_DIR = ''
OUT_CSV = ''

DIV_ORDER = ['地基与基础', '主体结构', '建筑装饰装修', '屋面', '建筑给水排水及供暖',
             '通风与空调', '建筑电气', '智能建筑', '建筑节能', '电梯', '措施项目', '室外工程']

POS_GROUP = {
    '标准层': '楼层', '全楼层': '楼层', '室内': '楼层', '首层': '楼层',
    '地下室': '地下', '基础': '地下',
    '外立面': '外围', '外墙': '外围', '屋面': '外围', '室外': '外围',
    '全场': '全场',
}


def norm(s):
    s = re.sub(r'[\s，。、；：,.;:（）()“”"\'·\-—…!？?]', '', str(s or ''))
    return s.lower()


NAME_STOP = re.compile(r'(施工工艺|施工技术|施工方法|施工|工艺|技术|做法|技术措施|优化措施|优化|应用|系统|方案|措施)$')
GENERIC_KW = {'工程', '施工', '工艺', '优化', '措施', '技术', '项目', '现场', '采用', '进行'}


def norm_name(s):
    s = norm(s)
    for _ in range(3):
        s2 = NAME_STOP.sub('', s)
        if s2 == s:
            break
        s = s2
    return s or norm(s)


def bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}


def jacc(a, b):
    A, B = bigrams(a), bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def seq(a, b):
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def coverage(short, long):
    """短文本有多少被长文本覆盖（应对「一句概括 vs 详细描述」的情形）"""
    if not short or not long:
        return 0.0
    sm = difflib.SequenceMatcher(None, short, long, autojunk=False)
    hit = sum(b.size for b in sm.get_matching_blocks())
    return hit / len(short)


def kw_set(rec):
    return {x for x in (rec.get('信息词条') or '').split(';')
            if x and x not in GENERIC_KW and len(x) >= 2}


def sim_detail(a, b):
    """综合相似度：名称 45% + 信息词条 25% + 内容包含度 30%
    返回 (composite, 名称, 词条, 包含度)"""
    na, nb = norm_name(a['优化措施名称']), norm_name(b['优化措施名称'])
    n = 0.5 * jacc(na, nb) + 0.5 * seq(na, nb)
    ka, kb = kw_set(a), kw_set(b)
    k = len(ka & kb) / len(ka | kb) if (ka or kb) else 0.0
    ca, cb = norm(a['优化内容']), norm(b['优化内容'])
    if len(ca) <= len(cb):
        cov = coverage(ca, cb)
    else:
        cov = coverage(cb, ca)
    # 内容二元组作为辅助（防止只靠短句覆盖率误判）
    cj = jacc(ca, cb)
    cov = 0.7 * cov + 0.3 * cj
    return 0.45 * n + 0.25 * k + 0.30 * cov, n, k, cov


def pos_set(rec):
    raw = rec.get('适用部位') or ''
    out = set()
    for p in str(raw).split('、'):
        p = p.strip()
        if p:
            out.add(p)
    return out


def pos_related(a, b):
    """部位是否可比：有交集，或属于同一部位域（楼层/地下/外围/全场）"""
    sa, sb = pos_set(a), pos_set(b)
    if sa & sb:
        return True
    ga = {POS_GROUP.get(x, x) for x in sa}
    gb = {POS_GROUP.get(x, x) for x in sb}
    return bool(ga & gb)


def norm_div(name):
    """分部名去掉括号备注（「室外工程（附录C）」→「室外工程」）"""
    return str(name or '').split('（')[0].strip()


def load_measures(path=None):
    with open(path or JSON_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def div_key(rec):
    return (norm_div(rec['分部工程']), rec['子分部工程'], rec['分项工程'])


def detail_score(rec):
    """详细程度：内容+效果字数为主，图片数为辅"""
    n = len(rec.get('优化内容') or '') + len(rec.get('优化效果') or '')
    n += 40 * len(rec.get('图片') or [])
    n += len(rec.get('信息词条') or '')
    return n


def build_clusters(threshold=0.62):
    rows = load_measures()
    rows = sorted(rows, key=lambda r: (DIV_ORDER.index(norm_div(r['分部工程']))
                                       if norm_div(r['分部工程']) in DIV_ORDER else 99,
                                       r['子分部工程'], r['分项工程'], r['id']))
    n = len(rows)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = rows[i], rows[j]
            ka, kb = div_key(a), div_key(b)
            # 只比同一分部分项；分项名相同但子分部写法不同也算
            if ka != kb and (ka[0] != kb[0] or ka[2] != kb[2]):
                continue
            if not pos_related(a, b):
                continue
            s, nm, kw, cov = sim_detail(a, b)
            if s >= threshold:
                pairs.append((s, nm, kw, cov, i, j))
                union(i, j)

    groups = OrderedDict()
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    clusters = []
    for root, idxs in groups.items():
        if len(idxs) > 1:
            clusters.append([rows[i] for i in idxs])
    clusters.sort(key=lambda g: (-len(g), -max(detail_score(r) for r in g)))
    return rows, clusters, pairs


def write_report(rows, clusters, pairs, path=None):
    path = path or OUT_CSV
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cmap = {}
    for k, g in enumerate(clusters, 1):
        for r in g:
            cmap[r['id']] = k
    keep = {}
    for k, g in enumerate(clusters, 1):
        keep[k] = max(g, key=detail_score)['id']

    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['组号', '是否保留', '组内条数', '分部工程', '子分部工程', '分项工程',
                    '适用部位', '优化措施名称', '优化内容', '字数', '图片数', '参考相似度'])
        for r in rows:
            gid = cmap.get(r['id'], '')
            sim = ''
            if gid:
                mates = [x for x in clusters[gid - 1] if x['id'] != r['id']]
                sim = '; '.join(f"{m['id']}:{sim_detail(r, m)[0]:.2f}" for m in mates)
            w.writerow([gid, '★保留' if keep.get(gid) == r['id'] else ('合并' if gid else ''),
                        len(clusters[gid - 1]) if gid else 1,
                        r['分部工程'], r['子分部工程'], r['分项工程'],
                        r.get('适用部位', ''), r['优化措施名称'],
                        (r.get('优化内容') or '').replace('\n', ' '),
                        len(r.get('优化内容') or ''), len(r.get('图片') or []), sim])
    return path, keep


def show(clusters, limit=40):
    print(f'\n检出重复组 {len(clusters)} 组，涉及 {sum(len(g) for g in clusters)} 条')
    for k, g in enumerate(clusters[:limit], 1):
        best = max(g, key=detail_score)
        print(f'\n【组 {k}】{g[0]["分部工程"]} / {g[0]["子分部工程"]} / {g[0]["分项工程"]}　部位：'
              + ' | '.join(sorted({r.get("适用部位", "") for r in g})))
        for r in sorted(g, key=detail_score, reverse=True):
            mark = '★' if r is best else ' '
            s = '' if r is best else f'  相似度 {sim_detail(r, best)[0]:.2f}'
            print(f' {mark} #{r["id"]:>3} {r["优化措施名称"][:30]:<32} 字数{len(r.get("优化内容") or ""):>3} '
                  f'图{len(r.get("图片") or []):>2}{s}')
            if r is not best:
                print(f'      内容：{(r.get("优化内容") or "")[:60]}')


def apply(clusters, keep):
    """合并：保留 detail_score 最高者，其余条目删除；图片并入保留项（去重）"""
    rows = load_measures()
    drop = {}
    for k, g in enumerate(clusters, 1):
        kp = next(r for r in g if r['id'] == keep[k])
        for r in g:
            if r['id'] != kp['id']:
                drop[r['id']] = kp['id']
                for img in r.get('图片') or []:
                    if img not in kp['图片']:
                        kp['图片'].append(img)
                # 词条合并
                kws = [x for x in (kp.get('信息词条') or '').split(';') if x]
                for x in (r.get('信息词条') or '').split(';'):
                    if x and x not in kws:
                        kws.append(x)
                kp['信息词条'] = ';'.join(kws)
                kp.setdefault('合并自', []).append(r['id'])

    backup = JSON_PATH.replace('.json', '.prededupe.json')
    if not os.path.exists(backup):
        shutil.copy2(JSON_PATH, backup)

    kept = [r for r in rows if r['id'] not in drop]
    for i, r in enumerate(kept, 1):
        r['id'] = i
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(kept, f, ensure_ascii=False, indent=1)
    return len(rows), len(kept), len(drop)


def apply_decisions(path):
    """按人工复核过的合并清单执行：保留 keep，删除 drop，图片/部位/词条/别名并入保留项"""
    with open(path, 'r', encoding='utf-8') as f:
        groups = json.load(f)
    rows = load_measures()
    by_id = {r['id']: r for r in rows}
    drop_ids = set()
    merged = []

    for g in groups:
        kp = by_id.get(g['keep'])
        if not kp:
            print('跳过：保留项不存在', g['keep'])
            continue
        for did in g['drop']:
            r = by_id.get(did)
            if not r:
                print('跳过：待删项不存在', did)
                continue
            # 图片并入（同名去重）
            for img in r.get('图片') or []:
                if img not in kp['图片']:
                    kp['图片'].append(img)
            # 适用部位合并
            parts = [p for p in (kp.get('适用部位') or '').split('、') if p]
            for p in (r.get('适用部位') or '').split('、'):
                if p and p not in parts:
                    parts.append(p)
            kp['适用部位'] = '、'.join(parts)
            # 信息词条合并
            kws = [x for x in (kp.get('信息词条') or '').split(';') if x]
            for x in (r.get('信息词条') or '').split(';'):
                if x and x not in kws:
                    kws.append(x)
            kp['信息词条'] = ';'.join(kws)
            # 别名与来源留痕
            alias = kp.setdefault('别名', [])
            if r['优化措施名称'] not in alias and r['优化措施名称'] != kp['优化措施名称']:
                alias.append(r['优化措施名称'])
            srcs = kp.setdefault('来源合并', [])
            tag = f"{r.get('来源表', '')}·{r.get('来源页', '')}"
            if tag and tag not in srcs:
                srcs.append(tag)
            drop_ids.add(did)
            merged.append((kp['id'], did, r['优化措施名称']))

    backup = JSON_PATH.replace('.json', '.prededupe.json')
    if not os.path.exists(backup):
        shutil.copy2(JSON_PATH, backup)

    kept = [r for r in rows if r['id'] not in drop_ids]
    for i, r in enumerate(kept, 1):
        r['id'] = i
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(kept, f, ensure_ascii=False, indent=1)
    return len(rows), len(kept), drop_ids, merged


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='库内同部位同做法重复识别与合并')
    ap.add_argument('--lib', required=True, help='lean_measures.json 路径')
    ap.add_argument('--img', default='', help='图片库目录（仅用于校验引用，可省）')
    ap.add_argument('--out', default='', help='候选清单 CSV 输出路径')
    ap.add_argument('--decisions', default='', help='人工确认的合并清单 [{"keep":id,"drop":[id...],"why":""}]')
    ap.add_argument('--apply', action='store_true', help='按自动聚类合并（未经逐组确认不要用）')
    ap.add_argument('--threshold', type=float, default=0.62)
    ap.add_argument('--limit', type=int, default=40, help='终端最多展示多少组')
    ap.add_argument('--dry-run', action='store_true', help='只出候选，不写库')
    a = ap.parse_args()

    JSON_PATH = os.path.abspath(a.lib)
    IMG_DIR = os.path.abspath(a.img) if a.img else os.path.join(os.path.dirname(JSON_PATH), '图片库')
    OUT_CSV = os.path.abspath(a.out or os.path.join(os.path.dirname(JSON_PATH), '去重候选.csv'))

    if a.decisions:
        before, after, dropped, merged = apply_decisions(a.decisions)
        print(f'合并完成：{before} → {after} 条，删除 {len(dropped)} 条')
        for keep, did, name in merged:
            print(f'  #{keep} ← 删 #{did} {name}')
        sys.exit(0)

    rows, clusters, pairs = build_clusters(a.threshold)
    path, keep = write_report(rows, clusters, pairs)
    show(clusters, a.limit)
    print('\n报告：', path)
    if a.apply and not a.dry_run:
        before, after, dropped = apply(clusters, keep)
        print(f'合并完成：{before} → {after} 条，删除 {dropped} 条')
