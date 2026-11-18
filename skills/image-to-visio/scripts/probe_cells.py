# -*- coding: utf-8 -*-
"""
probe_cells.py -- 探测本机 Visio 的单元格名 + 标定文本字号。

为什么需要它
------------
1) 不同 Visio 版本的单元格名不一样。本机 16.0 用 `FillForegnd`（不是
   `FillForegroundColor`）、`EndArrow` + `EndArrowSize`（没有 `LineEndArrow`），
   而 `Char.Spacing` **根本不存在**。照抄新文档会报"意外的文件尾"。
2) 本机 Visio 渲染 Times New Roman 比字体本身宽约 11%，没法用负字距压缩，
   所以字号只能**实测标定**：让"渲染墨迹宽度"等于"源图墨迹宽度"。

用法
----
  # 只探测单元格名
  python probe_cells.py

  # 标定若干字符串（JSON 里 target_px = 源图里该串的墨迹宽度，单位源像素）
  python probe_cells.py --cal cal.json

cal.json 示例：
  [
    {"text": "Rocking Podium Structures", "target_px": 192, "size": 24},
    {"text": "Figure 6.",                  "target_px":  71, "size": 24, "bold": true}
  ]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time

import win32com.client
from win32com.client import gencache

TMPDIR = tempfile.gettempdir()

# 候选单元格： (单元格名, 试探公式)
CANDIDATES = [
    ("FillForegnd", "RGB(199,199,200)"),
    ("FillForegroundColor", "RGB(199,199,200)"),
    ("FillBkgnd", "RGB(255,255,255)"),
    ("LineColor", "RGB(85,85,87)"),
    ("LineWeight", "1.5 pt"),
    ("LinePattern", "1"),
    ("LineEndArrow", "4"),
    ("EndArrow", "4"),
    ("EndArrowSize", "2"),
    ("BeginArrow", "4"),
    ("Char.Spacing", "-1 pt"),
    ("Char.Size", "18 pt"),
    ("Char.Font", '"Times New Roman"'),
    ("Char.Style", "1"),
    ("Char.Color", "0"),
    ("Para.HorzAlign", "1"),
    ("VerticalAlign", "1"),
    ("PageWidth", "5 in"),
    ("PageHeight", "5 in"),
    ("FillPattern", "1"),
    ("Rounding", "0.1 in"),
]


def open_visio():
    try:
        app = gencache.EnsureDispatch("Visio.Application")
    except Exception:
        app = win32com.client.Dispatch("Visio.Application")
    for a, v in (("Visible", 0), ("AlertResponse", 7)):
        try:
            setattr(app, a, v)
        except Exception:
            pass
    return app


def probe_cells(page):
    print("=" * 64)
    print("A. 单元格探测（本机 Visio）")
    print("=" * 64)
    shp = page.DrawRectangle(1.0, 1.0, 3.0, 2.0)
    ok, bad = [], []
    for nm, formula in CANDIDATES:
        try:
            shp.CellsU(nm).FormulaU = formula
            ok.append(nm)
            print("   OK    %-24s  <- %s" % (nm, formula))
        except Exception as e:
            bad.append(nm)
            print("   FAIL  %-24s  (%s)" % (nm, str(e)[:52]))
    print()
    print("   可用 %d / %d" % (len(ok), len(CANDIDATES)))
    if bad:
        print("   不可用: %s" % ", ".join(bad))
    print()
    print("   >>> 结论：写 build 脚本时只用上面 OK 的单元格名。")
    print("       - 填色用 %s" % ("FillForegnd" if "FillForegnd" in ok else "FillForegroundColor"))
    arrow = "EndArrow" if "EndArrow" in ok else ("LineEndArrow" if "LineEndArrow" in ok else "无")
    print("       - 箭头用 %s" % arrow)
    print("       - Char.Spacing %s" % ("可用" if "Char.Spacing" in ok else "不可用 -> 字号只能实测标定"))
    print()
    try:
        shp.Delete()
    except Exception:
        pass


def calibrate(items, base_size=24.0):
    print("=" * 64)
    print("B. 文本宽度标定")
    print("=" * 64)
    app = open_visio()
    doc = app.Documents.Add("")
    page = doc.Pages.Item(1)

    tmp = os.path.join(TMPDIR, "cellprobe.vsdx")
    png = os.path.join(TMPDIR, "cellprobe.png")
    for f in (tmp, png):
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass

    order = []
    y = 1.0
    for it in items:
        shp = page.DrawRectangle(0.2, y, 9.0, y + 0.55)
        shp.CellsU("LinePattern").FormulaU = "0"
        shp.CellsU("FillPattern").FormulaU = "0"
        shp.Text = it["text"]
        shp.CellsU("Char.Size").FormulaU = "%.1f pt" % it.get("size", base_size)
        shp.CellsU("Char.Font").FormulaU = '"%s"' % it.get("font", "Times New Roman")
        shp.CellsU("Para.HorzAlign").FormulaU = "0"
        if it.get("bold"):
            shp.CellsU("Char.Style").FormulaU = "1"
        order.append(it)
        y += 0.75

    doc.SaveAs(tmp)
    ok = False
    for _ in range(10):
        try:
            page.Export(png)
            ok = True
            break
        except Exception:
            time.sleep(1.0)
    try:
        doc.Saved = True
        doc.Close()
    except Exception:
        pass
    try:
        app.Quit()
    except Exception:
        pass
    if not ok:
        sys.exit("导出失败，无法标定")

    from PIL import Image
    import numpy as np
    g = np.array(Image.open(png).convert("L"))
    m = g < 200
    rows = m.sum(axis=1)
    bands, inb = [], False
    for r, v in enumerate(rows):
        if v > 0 and not inb:
            s = r
            inb = True
        elif v == 0 and inb:
            bands.append((s, r - 1))
            inb = False
    if inb:
        bands.append((s, len(rows) - 1))

    # 关键：导出栅格的 y 是**上下翻转**的 —— 第 i 个 band（从上往下）对应**最后**画的那个形状
    bands = list(reversed(bands))
    print("   检出 %d 个 band，预期 %d 个" % (len(bands), len(order)))
    if len(bands) != len(order):
        print("   !! 数量不符：检查是否有两行贴在一起，或某行完全空白。")
    print()
    print("   %-34s %6s %10s %10s %8s" %
          ("text", "size", "render_px", "target_px", "needed"))
    for i, (a, b) in enumerate(bands):
        if i >= len(order):
            break
        sub = m[a:b + 1]
        xs = np.nonzero(sub.any(axis=0))[0]
        w_export = xs.max() - xs.min() + 1
        w_src = w_export / 2.0                      # 导出是 2x
        cap = b - a + 1
        it = order[i]
        tgt = it.get("target_px")
        need = (it.get("size", base_size) * tgt / w_src) if tgt else float("nan")
        t = it["text"]
        t = (t[:31] + "..") if len(t) > 33 else t
        print("   %-34s %6.1f %10.2f %10s %8.1f" % (t, it.get("size", base_size), w_src, tgt, need))
    print()
    print("   >>> needed 就是该串应该用的 pt 值（让渲染宽度 = 目标宽度）。")
    print("       导出 band 高度 %s 也一并给你，短词可用 cap-height 交叉验证。" %
          ("已列出" if len(bands) == len(order) else "可能不准"))


def main():
    ap = argparse.ArgumentParser(description="探测 Visio 单元格名 / 标定文本字号")
    ap.add_argument("--cal", default=None, help="标定用的 JSON 文件")
    args = ap.parse_args()

    app = open_visio()
    doc = app.Documents.Add("")
    page = doc.Pages.Item(1)
    try:
        probe_cells(page)
    finally:
        try:
            doc.Saved = True
            doc.Close()
        except Exception:
            pass
        try:
            app.Quit()
        except Exception:
            pass

    if args.cal:
        with open(args.cal, "r", encoding="utf-8") as fh:
            items = json.load(fh)
        calibrate(items)


if __name__ == "__main__":
    main()
