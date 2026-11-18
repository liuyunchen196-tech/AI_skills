#!/usr/bin/env python3
"""analyze_pptx.py - 只读分析一个或多个 PPTX 的结构，为模板套用提供依据。

用法: python analyze_pptx.py <file1.pptx> [file2.pptx ...]
输出: 每个文件的页面尺寸、母版/版式清单、每页元素清单
      (占位符/文本框/图片/表格/组合)，含坐标、字号、文本内容。
"""
import sys
import json
from pptx import Presentation
from pptx.util import Emu

EMU_IN = 914400


def fmt_emu(v):
    if v is None:
        return None
    return round(v / EMU_IN, 2)


def shape_info(sh, depth=0):
    d = {
        "type": str(sh.shape_type),
        "name": sh.name,
        "left": fmt_emu(sh.left), "top": fmt_emu(sh.top),
        "width": fmt_emu(sh.width), "height": fmt_emu(sh.height),
    }
    if sh.is_placeholder:
        d["placeholder"] = str(sh.placeholder_format.type)
    if getattr(sh, "has_text_frame", False) and sh.has_text_frame:
        paras = []
        for p in sh.text_frame.paragraphs:
            sizes = {r.font.size.pt for r in p.runs if r.font.size}
            fonts = {r.font.name for r in p.runs if r.font.name}
            paras.append({"text": p.text, "level": p.level,
                          "sizes": sorted(sizes) if sizes else None,
                          "fonts": sorted(fonts) if fonts else None})
        d["paragraphs"] = paras
    if getattr(sh, "has_table", False) and sh.has_table:
        tbl = sh.table
        d["table"] = {"rows": len(tbl.rows), "cols": len(tbl.columns),
                      "cells": [[c.text for c in row.cells] for row in tbl.rows]}
    if getattr(sh, "has_chart", False) and sh.has_chart:
        d["chart"] = str(sh.chart.chart_type)
    if sh.shape_type == 13:  # PICTURE
        try:
            d["image_ext"] = sh.image.ext
            d["image_bytes"] = len(sh.image.blob)
        except Exception:
            pass
    if sh.shape_type == 6:  # GROUP
        d["children"] = [shape_info(c, depth + 1) for c in sh.shapes]
    return d


def analyze(path):
    prs = Presentation(path)
    out = {
        "file": path,
        "slide_size": {"w_emu": prs.slide_width, "h_emu": prs.slide_height},
        "n_slides": len(prs.slides),
        "layouts": {},
        "slides": [],
    }
    for m in prs.slide_masters:
        for l in m.slide_layouts:
            out["layouts"][l.name] = [
                str(ph.placeholder_format.type) for ph in l.placeholders
            ]
    for i, s in enumerate(prs.slides, 1):
        sl = {"page": i, "layout": s.slide_layout.name,
              "shapes": [shape_info(sh) for sh in s.shapes]}
        out["slides"].append(sl)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for f in sys.argv[1:]:
        print(json.dumps(analyze(f), ensure_ascii=False, indent=1, default=str))
