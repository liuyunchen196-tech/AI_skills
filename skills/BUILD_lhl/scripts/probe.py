# -*- coding: utf-8 -*-
"""probe.py — 素材体检与提取路径建议（BUILD_lhl）

用法: python probe.py <pdf> [--pages 1-5]

输出：页数 / 尺寸 / 旋转页 / 文本层是否可用 / 框线数量 / 每页图片数 / 版式判定
"""
import argparse
import sys

import pymupdf as fitz

CARD_LABELS = ('实施效果', '工艺要点', '实体案例', '实例案例', '实际案例', '案例简述')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--pages', help='抽样页范围，如 3-8，默认前 8 页')
    a = ap.parse_args()

    doc = fitz.open(a.pdf)
    print('=' * 68)
    print('素材体检: %s' % a.pdf)
    print('  页数 %d | 首末尺寸 %s' % (doc.page_count, doc[0].rect))
    print('=' * 68)

    rot = [i + 1 for i in range(doc.page_count) if doc[i].rotation % 360]
    if rot:
        print('  !! 旋转页 %d 个: %s（取图需做坐标变换）' % (len(rot), rot[:12]))

    lo, hi = 1, min(doc.page_count, 8)
    if a.pages:
        x = a.pages.split('-')
        lo, hi = int(x[0]), int(x[-1])

    txt_ok = txt_bad = cards = tables = 0
    for i in range(doc.page_count):
        page = doc[i]
        t = page.get_text().strip()
        # 可用判定：汉字/字母占比高，且无大量私用区/替换符
        if len(t) > 30:
            cjk = sum(1 for ch in t if '\u4e00' <= ch <= '\u9fff')
            bad = sum(1 for ch in t if ch == '\ufffd' or '\ue000' <= ch <= '\uf8ff'
                      or ch in '□▯\u25a1')
            if cjk / len(t) > 0.15 and bad / len(t) < 0.05:
                txt_ok += 1
            else:
                txt_bad += 1
        if any(k in t for k in CARD_LABELS):
            cards += 1
        d = page.get_drawings()
        if len(d) > 20:
            tables += 1
        if any(k in t for k in CARD_LABELS):
            cards += 1
        d = page.get_drawings()
        if len(d) > 20:
            tables += 1

    print('\n  全册统计: 文本层可用页 %d | 疑似乱码页 %d | 含卡片标签页 %d | 框线密集页 %d'
          % (txt_ok, txt_bad, cards, tables))

    print('\n  抽样明细 (p%d~p%d):' % (lo, hi))
    print('  %-4s %-14s %-8s %-6s %-6s %s' % ('页', '尺寸', '旋转', '字符', '框线', '图片(>100pt)'))
    for i in range(lo - 1, min(hi, doc.page_count)):
        p = doc[i]
        imgs = [x for x in p.get_image_info(xrefs=True)
                if (x['bbox'][2] - x['bbox'][0]) > 50 and (x['bbox'][3] - x['bbox'][1]) > 60]
        print('  %-4d %-14s %-8s %-6d %-6d %d'
              % (i + 1, '%dx%d' % (p.rect.width, p.rect.height), p.rotation,
                 len(p.get_text().strip()), len(p.get_drawings()), len(imgs)))

    # —— 路由建议 ——
    print('\n  判定与建议:')
    if txt_bad > txt_ok:
        print('    文本层不可靠 → 走 OCR 路径: scripts/ocr_scan.py')
    if cards >= max(2, doc.page_count // 3):
        print('    卡片式版式 → scripts/extract_cards.py（注意先按 x 分栏，再按 y 切段）')
    if tables >= max(2, doc.page_count // 3):
        print('    框线表格 → scripts/extract_tables.py（竖线定列、横线聚类分行）')
    if txt_bad > txt_ok and tables >= 2:
        print('    乱码 + 框线表格 → OCR 识别文字，PDF 框线定格网（不要用 OCR 坐标定列）')
    print('=' * 68)


if __name__ == '__main__':
    main()
