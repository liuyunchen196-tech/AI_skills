# -*- coding: utf-8 -*-
"""validate.py — 数据七项校验（BUILD_lhl）

用法:
    python validate.py --lib data/lean_measures.json --img data/图片库
    python validate.py --lib ... --img ... --json      # 机器可读输出
    python validate.py --lib ... --img ... --strict    # 有 FAIL 时退出码 1

校验项:
    1 记录总数 / 类型分布
    2 图片引用一致性（缺失 / 未引用）
    3 无图记录
    4 措施重名
    5 空字段（实施效果 / 优化效果 / 信息词条）
    6 分部分项命中标准树
    7 图片命名规范
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIV = os.path.join(os.path.dirname(HERE), 'assets', 'divisions.json')
VIRTUAL = '措施项目'
BAD_CHARS = re.compile(r'[\\/:*?"<>|]')


def load_tree(path):
    """返回 {分部: {子分部: set(分项)}}，标准树 + 虚拟分部。"""
    data = json.load(open(path, encoding='utf-8'))
    key = '建筑' if '建筑' in data else list(data.keys())[0]
    tree = {}
    for dv in data[key]['divisions']:
        tree[dv['name']] = {s['name']: set(s['items']) for s in dv['subs']}
    tree.setdefault(VIRTUAL, {})
    return tree


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lib', required=True, help='lean_measures.json 路径')
    ap.add_argument('--img', required=True, help='图片库目录')
    ap.add_argument('--divisions', default=DEFAULT_DIV)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--strict', action='store_true')
    a = ap.parse_args()

    rows = json.load(open(a.lib, encoding='utf-8'))
    files = set(os.listdir(a.img)) if os.path.isdir(a.img) else set()
    tree = load_tree(a.divisions)

    used = []
    for r in rows:
        used.extend(r.get('图片') or [])
    used_set = set(used)

    miss = sorted(used_set - files)
    extra = sorted(files - used_set)
    noimg = [r for r in rows if not (r.get('图片') or [])]
    names = Counter(r.get('优化措施名称', '') for r in rows)
    dup = {k: v for k, v in names.items() if v > 1 and k}
    empty = {k: [r.get('id') for r in rows if not str(r.get(k) or '').strip()]
             for k in ('优化内容', '优化效果', '信息词条', '适用部位')}
    bad_div = []
    for r in rows:
        dv, sub, it = r.get('分部工程'), r.get('子分部工程'), r.get('分项工程')
        if dv not in tree:
            bad_div.append((r.get('id'), r.get('优化措施名称'), '%s 不存在' % dv))
            continue
        if dv == VIRTUAL:
            if tree[dv] and sub not in tree[dv]:
                bad_div.append((r.get('id'), r.get('优化措施名称'), '虚拟子分部 %s 未登记' % sub))
            continue
        if sub not in tree[dv]:
            bad_div.append((r.get('id'), r.get('优化措施名称'), '%s/%s 子分部不存在' % (dv, sub)))
        elif it not in tree[dv][sub]:
            bad_div.append((r.get('id'), r.get('优化措施名称'), '%s/%s/%s 分项不存在' % (dv, sub, it)))
    badname = [n for n in files if BAD_CHARS.search(n) or not re.search(r'_\d+\.(jpg|jpeg|png|webp)$', n, re.I)]

    checks = [
        ('1 记录总数', True, '%d 条 | 章节 %s' % (len(rows), dict(Counter(r.get('章节') for r in rows)))),
        ('2 图片引用', not miss and not extra,
         '库内 %d 张 / 引用 %d 处 / 缺失 %d / 未引用 %d' % (len(files), len(used), len(miss), len(extra))),
        ('3 无图记录', not noimg, '%d 条' % len(noimg)),
        ('4 措施重名', not dup, '%d 组 %s' % (len(dup), list(dup)[:3])),
        ('5 空字段', not any(empty.values()),
         ' / '.join('%s %d' % (k, len(v)) for k, v in empty.items())),
        ('6 分部分项', not bad_div, '%d 条异常 %s' % (len(bad_div), bad_div[:3])),
        ('7 图片命名', not badname, '%d 个不规范 %s' % (len(badname), badname[:3])),
    ]

    if a.json:
        print(json.dumps({
            'total': len(rows),
            'chapters': dict(Counter(r.get('章节') for r in rows)),
            'types': dict(Counter(r.get('优化类型') for r in rows)),
            'sources': dict(Counter(r.get('来源表') for r in rows)),
            'images': len(files), 'refs': len(used),
            'missing': miss, 'unused': extra,
            'no_image': [r.get('id') for r in noimg],
            'dup_names': dup, 'empty': empty, 'bad_division': bad_div,
            'bad_filename': badname,
            'pass': all(c[1] for c in checks),
        }, ensure_ascii=False, indent=1))
        sys.exit(0 if (all(c[1] for c in checks) or not a.strict) else 1)

    print('=' * 72)
    print('数据校验 · %s' % a.lib)
    print('=' * 72)
    for name, ok, detail in checks:
        print('  [%s] %-10s %s' % ('PASS' if ok else 'FAIL', name, detail))
    print('-' * 72)
    print('  图片引用明细: 缺失 %s | 未引用 %s' % (miss[:5] or '无', extra[:5] or '无'))
    if bad_div:
        print('  分部分项异常(前10):')
        for x in bad_div[:10]:
            print('    #%s %s -> %s' % x)
    print('=' * 72)
    ok = all(c[1] for c in checks)
    print('  结论: %s' % ('全部通过' if ok else '存在未通过项，禁止交付'))
    sys.exit(0 if (ok or not a.strict) else 1)


if __name__ == '__main__':
    main()
