# -*- coding: utf-8 -*-
"""ocr_scan.py — 扫描件 / 乱码文本层 OCR 提取（BUILD_lhl）

适用：`probe.py` 判定「文本层不可用」的素材。
要点：
  - 渲染 300dpi；坐标换算 pt = px * 72 / dpi
  - RapidOCR 参数 text_score=0.3, box_thresh=0.2（默认阈值会吞掉单字行）
  - 名称列单独裁切、400dpi 重识别（名称最易丢末字）
  - **列/行网格用 PDF 矢量框线定，不要用 OCR 坐标定列**

依赖：rapidocr_onnxruntime（建议放在 D:\\AI技能库\\runtime\\ocr-venv）
用法：
  python ocr_scan.py --pdf x.pdf --pages 1-20 --dpi 300 --out _tmp/ocr.json
  python ocr_scan.py --pdf x.pdf --name-col 120,400 --pages 3 --out names.json
"""
import argparse
import json
import os

import pymupdf as fitz


def get_engine():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        raise SystemExit('缺少 rapidocr_onnxruntime。\n'
                         '请用 D:\\AI技能库\\runtime\\ocr-venv\\Scripts\\python.exe 运行，\n'
                         '或 pip install rapidocr_onnxruntime')
    return RapidOCR()


def ocr_page(engine, page, dpi, clip=None, score=0.3, box=0.2):
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    tmp = '_ocr_tmp.png'
    pix.save(tmp)
    res, _ = engine(tmp, text_score=score, box_thresh=box)
    os.remove(tmp)
    k = 72.0 / dpi
    out = []
    for item in (res or []):
        pts, txt, sc = item[0], item[1], item[2]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0, y0 = min(xs) * k, min(ys) * k
        x1, y1 = max(xs) * k, max(ys) * k
        if clip:
            x0 += clip.x0
            x1 += clip.x0
            y0 += clip.y0
            y1 += clip.y0
        out.append({'t': txt, 'x0': round(x0, 1), 'y0': round(y0, 1),
                    'x1': round(x1, 1), 'y1': round(y1, 1), 'score': round(float(sc), 3)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--pages', default='', help='如 3-10；默认全部')
    ap.add_argument('--dpi', type=int, default=300)
    ap.add_argument('--name-col', default='', help='名称列 x0,x1（单独 400dpi 重识别）')
    ap.add_argument('--name-y', default='', help='名称列 y0,y1')
    ap.add_argument('--out', default='ocr.json')
    a = ap.parse_args()

    engine = get_engine()
    doc = fitz.open(a.pdf)
    lo, hi = 1, doc.page_count
    if a.pages:
        x = a.pages.split('-')
        lo, hi = int(x[0]), int(x[-1])

    result = {}
    for pi in range(lo - 1, min(hi, doc.page_count)):
        page = doc[pi]
        if a.name_col:
            x0, x1 = [float(v) for v in a.name_col.split(',')]
            y0, y1 = ([float(v) for v in a.name_y.split(',')] if a.name_y
                      else [0, page.rect.height])
            items = ocr_page(engine, page, 400, fitz.Rect(x0, y0, x1, y1))
        else:
            items = ocr_page(engine, page, a.dpi)
        result[str(pi + 1)] = items
        print('p%-3d 识别 %d 段' % (pi + 1, len(items)))

    json.dump(result, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('-> %s' % a.out)
    print('下一步：按框线落格（extract_tables.py 的 grid 逻辑），不要按 OCR 坐标定列')


if __name__ == '__main__':
    main()
