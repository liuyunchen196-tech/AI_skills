# -*- coding: utf-8 -*-
"""dedupe.py — 新素材入库前的查重候选清单（BUILD_lhl）

只出清单，绝不改库。确认后手工写 merge_map.json: {"新标题": 目标id}

分工：本脚本比「新记录 vs 已有库」，判据是标题为主；
      库内「同分部分项 + 同部位 + 同做法」的自查用 dedupe_content.py（按内容比，含合并执行）。

用法:
  python dedupe.py --new recs.json --lib data/lean_measures.json --out cand.csv
  python dedupe.py --lib data/lean_measures.json --self          # 全库自检

判定三件套（任一满足即为候选）:
  1) 标题 bigram Jaccard >= 0.55
  2) 标题最长公共子串 >= 4 字
  3) 优化效果 Jaccard >= 0.45
"""
import argparse
import csv
import json
import re
import sys

GEN = r'(施工工艺|施工工法|高效工艺|施工技术|工法|工艺|技术|应用|施工)$'


def clean(s):
    return re.sub(r'[^\u4e00-\u9fa5A-Za-z0-9]', '', s or '')


def core(s):
    s = re.sub(r'\s+', '', s or '')
    for _ in range(2):
        s2 = re.sub(GEN, '', s)
        if s2 == s:
            break
        s = s2
    return s


def grams(s, n=2):
    s = clean(s)
    return {s[i:i + n] for i in range(len(s) - n + 1)} or ({s} if s else set())


def jac(a, b):
    A, B = grams(a), grams(b)
    return len(A & B) / len(A | B) if A and B else 0.0


def lcs(a, b):
    a, b = core(a), core(b)
    if not a or not b:
        return 0, ''
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    mx = pos = 0
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                if dp[i][j] > mx:
                    mx, pos = dp[i][j], i
    return mx, a[pos - mx:pos]


SEP = re.compile(r'(同|随|与|跟|一次|免|永临|一体|精准|模块化|预制|定型化|暗埋|隐藏|同步|快拆|高效)')


def obj(s):
    """抽取标题的「对象词」：分隔词之前的主体，如
    「设备基础同主体结构一次浇筑」-> 设备基础；「止水节一次精准预埋」-> 止水节。
    对象不同的两条，即使句式相同也不是重复（如 门垛 / 上反坎 / 设备基础）。"""
    s = core(s)
    head = SEP.split(s)[0] if SEP.search(s) else s
    return head or s


def score(new, old):
    s_title = jac(new['title'], old.get('优化措施名称', ''))
    s_eff = jac(new.get('优化效果', ''), old.get('优化效果', ''))
    L, w = lcs(new['title'], old.get('优化措施名称', ''))
    oa, ob = obj(new['title']), obj(old.get('优化措施名称', ''))
    lo = lcs(oa, ob)[0] / max(min(len(oa), len(ob)), 1) if oa and ob else 0
    same_obj = (len(oa) >= 3 and len(ob) >= 3 and
                (oa == ob or oa in ob or ob in oa or lo >= 0.6))
    hit = same_obj or s_eff >= 0.45 or s_title >= 0.75
    why = '对象同(%s≈%s)' % (oa, ob) if same_obj else ('效果相似' if s_eff >= 0.45 else ('字面极高' if hit else ''))
    return hit, s_title, s_eff, L, w, why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--new', help='新提取记录 recs.json')
    ap.add_argument('--lib', required=True)
    ap.add_argument('--out', default='dedupe_candidates.csv')
    ap.add_argument('--self', action='store_true', help='全库两两自检')
    ap.add_argument('--top', type=int, default=3)
    a = ap.parse_args()

    lib = json.load(open(a.lib, encoding='utf-8'))
    print('库内 %d 条' % len(lib))

    pool = []
    if a.self:
        pool = [{'title': r['优化措施名称'], '优化效果': r.get('优化效果', '')} for r in lib]
        print('自检模式：%d 条两两比对' % len(pool))
    else:
        recs = json.load(open(a.new, encoding='utf-8'))
        for r in recs:
            pool.append({'title': re.sub(r'\s+', '', r.get('title') or r.get('优化措施名称') or ''),
                         '优化效果': r.get('优化效果') or r.get('effect') or ''})
        print('待检 %d 条' % len(pool))

    out = []
    for i, n in enumerate(pool):
        cand = []
        for j, o in enumerate(lib):
            if a.self and i == j:
                continue
            hit, st, se, L, w, why = score(n, o)
            if hit:
                cand.append((round(0.6 * st + 0.4 * se, 3), st, se, L, w, why, o))
        cand.sort(key=lambda x: (x[0], x[3]), reverse=True)
        for c in cand[:a.top]:
            out.append([n['title'], c[6]['优化措施名称'], c[0], round(c[1], 2), round(c[2], 2),
                        c[3], c[4], c[6].get('id', ''), c[5] or '字面相似', '待确认'])

    with open(a.out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['待检措施', '库中候选', '综合分', '标题相似', '效果相似', '公共子串长', '公共子串',
                    '库中id', '命中原因', '处理'])
        w.writerows(out)

    print('候选 %d 对 -> %s' % (len(out), a.out))
    print('\n前 20 对:')
    for x in out[:20]:
        print('  %.2f | %-26s <- #%s %s [%s]' % (x[2], x[0][:26], x[7], x[1][:24], x[6]))
    print('\n下一步：逐条判定「合并 / 新增」，把合并项写成 merge_map.json 再交给 ingest.py')


if __name__ == '__main__':
    main()
