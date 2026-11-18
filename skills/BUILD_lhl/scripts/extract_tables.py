# -*- coding: utf-8 -*-
"""extract_tables.py — 矢量框线表格提取（BUILD_lhl）

原则：**列由竖线定，行由横线聚类定，文本按 bbox 中心落格**。
不要用 page.find_tables()：合并单元格 + 跨页续表的场景会全线崩。

用法:
  python extract_tables.py --pdf x.pdf --columns auto --header-row 0 \
      --column-map "2=优化措施名称;3=优化内容;4=优化效果" --out recs.json
  python extract_tables.py --pdf x.pdf --columns 81,128,184,296,358,514 ...

输出 recs.json（列名来自 --column-map），并打印行列自检。
"""
import argparse
import json
import re

import pymupdf as fitz


def cluster(vals, tol=3.0):
    vals = sorted(vals)
    out, group = [], [vals[0]] if vals else []
    for v in vals[1:]:
        if v - group[-1] <= tol:
            group.append(v)
        else:
            out.append(sum(group) / len(group))
            group = [v]
    if group:
        out.append(sum(group) / len(group))
    return out


def lines_of(page):
    vx, hy = [], []
    for d in page.get_drawings():
        for it in d['items']:
            if it[0] == 'l':
                p1, p2 = it[1], it[2]
                if abs(p1.x - p2.x) < 1.5:
                    vx.append((p1.x, min(p1.y, p2.y), max(p1.y, p2.y)))
                elif abs(p1.y - p2.y) < 1.5:
                    hy.append((p1.y, min(p1.x, p2.x), max(p1.x, p2.x)))
            elif it[0] == 're':
                r = it[1]
                w, h = r.width, r.height
                if w < 1.5 and h > 2:            # 细竖矩形 = 竖线
                    vx.append((r.x0, r.y0, r.y1))
                elif h < 1.5 and w > 2:          # 细横矩形 = 横线
                    hy.append((r.y0, r.x0, r.x1))
                else:                             # 单元格矩形，取四边
                    vx += [(r.x0, r.y0, r.y1), (r.x1, r.y0, r.y1)]
                    hy += [(r.y0, r.x0, r.x1), (r.y1, r.x0, r.x1)]
    return vx, hy


def auto_columns(vx, page_h, ratio=0.35):
    tall = [x for x, y0, y1 in vx if (y1 - y0) > page_h * ratio]
    return cluster(tall) if tall else []


def row_bounds(hy, page_w, ratio=0.35):
    wide = [y for y, x0, x1 in hy if (x1 - x0) > page_w * ratio]
    ys = cluster(wide) if wide else []
    if len(ys) < 3:                      # 单元格级横线的表格：退化为全部横线
        ys = cluster([y for y, _, _ in hy])
    return ys


def cells_of(page):
    """收集单元格级矩形（很多手册的表格是"一格一个填充矩形"，没有整表线）。"""
    out = []
    W, H = page.rect.width, page.rect.height
    for d in page.get_drawings():
        for it in d['items']:
            if it[0] == 're':
                r = it[1]
                w, h = r.x1 - r.x0, r.y1 - r.y0
                if 2 < w < W * 0.85 and 2 < h < H * 0.5:
                    out.append((r.x0, r.y0, r.x1, r.y1))
    return out


def grid_by_cells(page):
    """矩形法：用所有单元格的 x0/x1、y0/y1 聚类出列线与行线。"""
    cs = cells_of(page)
    if len(cs) < 4:
        return [], []
    xs, ys = [], []
    for x0, y0, x1, y1 in cs:
        xs += [x0, x1]
        ys += [y0, y1]
    cols, rows = cluster(xs, 2.5), cluster(ys, 2.5)
    # 去掉过密/过疏的伪边界（至少 2 列 2 行）
    return (cols if len(cols) >= 3 else []), (rows if len(rows) >= 3 else [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--columns', default='auto', help='auto 或逗号分隔的 x 坐标')
    ap.add_argument('--header-row', type=int, default=0)
    ap.add_argument('--column-map', default='', help='索引=字段名;索引=字段名')
    ap.add_argument('--out', default='recs.json')
    ap.add_argument('--pages', default='', help='如 3-10，默认全部')
    ap.add_argument('--table-gap', type=float, default=110, help='换表判定：行间距阈值')
    ap.add_argument('--tables-config', help='表驱动配置 JSON: [{name,start,end,columns,column_map,typ}]')
    ap.add_argument('--probe-cols', help='只探测：打印该页竖线 x / 横线 y 的频次分布，用于人工定列坐标')
    a = ap.parse_args()

    cmap = {}
    for part in a.column_map.split(';'):
        if '=' in part:
            k, v = part.split('=', 1)
            cmap[int(k.strip())] = v.strip()

    doc = fitz.open(a.pdf)

    if a.probe_cols:
        from collections import Counter
        pi = int(a.probe_cols) - 1
        page = doc[pi]
        vx, hy = lines_of(page)
        xs = Counter(round(x) for x, _, _ in vx)
        ys = Counter(round(y) for y, _, _ in hy)
        print('页 %d 尺寸 %.0fx%.0f | 竖线 %d 条 / 横线 %d 条'
              % (pi + 1, page.rect.width, page.rect.height, len(vx), len(hy)))
        print('竖线 x（频次降序，取出现多的作为列边界）:')
        for x, n in xs.most_common(24):
            print('   x=%-6d 出现 %d 次' % (x, n))
        print('横线 y（用于确认行范围）:')
        for y, n in ys.most_common(24):
            print('   y=%-6d 出现 %d 次' % (y, n))
        print('提示：列边界写成 --columns 逗号序列，如 %s'
              % ','.join(str(x) for x, _ in sorted(xs.most_common(8))[:8]))
        return
    lo, hi = 1, doc.page_count
    if a.pages:
        x = a.pages.split('-')
        lo, hi = int(x[0]), int(x[-1])

    # 表驱动模式：每张表有自己的页范围与列坐标（跨页表更可靠）
    tables = None
    if a.tables_config:
        tables = json.load(open(a.tables_config, encoding='utf-8'))
        print('表驱动模式：%d 张表' % len(tables))

    recs = []
    jobs = []
    if tables:
        for t in tables:
            jobs.append((t['start'], t['end'], t.get('columns') or a.columns,
                         t.get('column_map') or a.column_map, t.get('name', ''), t.get('typ', '')))
    else:
        jobs.append((lo, hi, a.columns, a.column_map, '', ''))

    for (p0, p1, colsarg, maparg, tname, ttyp) in jobs:
        cm = {}
        for part in maparg.split(';'):
            if '=' in part:
                k, v = part.split('=', 1)
                cm[int(k.strip())] = v.strip()
        for pi in range(p0 - 1, min(p1, doc.page_count)):
            page = doc[pi]
            vx, hy = lines_of(page)
            cols = ([float(x) for x in colsarg.split(',')] if colsarg != 'auto'
                    else auto_columns(vx, page.rect.height))
            rows = row_bounds(hy, page.rect.width)
            if len(cols) < 2:
                c2, r2 = grid_by_cells(page)
                cols = cols or c2
                rows = rows or r2
            if len(cols) < 2 or len(rows) < 2:
                continue
            blocks, cur = [], [rows[0]]
            for i in range(1, len(rows)):
                if rows[i] - rows[i - 1] > a.table_gap:
                    blocks.append(cur)
                    cur = [rows[i]]
                else:
                    cur.append(rows[i])
            blocks.append(cur)
            spans = [s for b in page.get_text('dict')['blocks'] if b['type'] == 0
                     for l in b['lines'] for s in l['spans'] if s['text'].strip()]
            for block in blocks:
                grid = {}
                for s in spans:
                    cx = (s['bbox'][0] + s['bbox'][2]) / 2
                    cy = (s['bbox'][1] + s['bbox'][3]) / 2
                    if cy < block[0] - 2 or cy > block[-1] + 40:
                        continue
                    ci = next((i for i in range(len(cols) - 1) if cols[i] <= cx < cols[i + 1]), None)
                    if ci is None:
                        continue
                    ri = next((i for i in range(len(block) - 1) if block[i] <= cy < block[i + 1]), None)
                    if ri is None:
                        continue
                    grid.setdefault((ri, ci), []).append((round(s['bbox'][1], 1), s['bbox'][0], s['text']))
                if not grid:
                    continue
                for ri in sorted({r for r, _ in grid}):
                    if ri == a.header_row:
                        continue
                    cell = {}
                    for ci in range(len(cols) - 1):
                        items = sorted(grid.get((ri, ci), []))
                        txt = re.sub(r'\s+', '', ''.join(t for _, _, t in items))
                        if txt:
                            cell[cm.get(ci, '列%d' % ci)] = txt
                    if len([v for v in cell.values() if len(v) > 2]) >= 2:
                        cell['page'] = pi + 1
                        if tname:
                            cell['来源表'] = tname
                        if ttyp:
                            cell['优化类型'] = ttyp
                        recs.append(cell)

    json.dump(recs, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('提取 %d 行 -> %s' % (len(recs), a.out))
    if recs:
        print('列名:', list(recs[0].keys()))
        for r in recs[:3]:
            print('  ', {k: str(v)[:18] for k, v in list(r.items())[:5]})
    else:
        print('!! 0 行：检查 --columns（列边界 x 坐标）与 --pages；')
        print('   或改用 --tables-config 按表配置页范围；纯图/乱码页请走 ocr_scan.py')


if __name__ == '__main__':
    main()
