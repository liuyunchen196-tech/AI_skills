# -*- coding: utf-8 -*-
"""
measure_image.py -- 「图片转 Visio」的像素取证工具。

把一张源图（截图/论文插图）量成数值：填充块、线、带状结构、文本行、精确配色。
输出直接喂给 build_<name>.py 里的 Fig 调用。

用法
----
  # 全量测量
  python measure_image.py src.png

  # 只要某几项
  python measure_image.py src.png --sections fills,text,colors

  # 放大某个区域看细节（会写出 PNG）
  python measure_image.py src.png --crop 258,158,348,272 --zoom 4 --name loop

  # 把文本行也做横向膨胀合并（默认开）
  python measure_image.py src.png --dilate 5

坐标约定：所有输出都是**源图像素**，x 向右、y **向下**，原点在左上角。
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image

try:
    from scipy import ndimage
    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False


# --------------------------------------------------------------------------- #
def load(path):
    im = Image.open(path).convert("RGB")
    a = np.array(im).astype(int)
    g = a.mean(axis=2)
    sat = a.max(axis=2) - a.min(axis=2)
    return im, a, g, sat


def runs_of(idx, gap=1):
    """把有序索引切成连续段。"""
    if len(idx) == 0:
        return []
    out = []
    s = p = idx[0]
    for v in idx[1:]:
        if v > p + gap:
            out.append((int(s), int(p)))
            s = v
        p = v
    out.append((int(s), int(p)))
    return out


def hline(s, ch="="):
    print(ch * len(s))
    print(s)
    print(ch * len(s))


# --------------------------------------------------------------------------- #
def sec_colors(a, g, sat, top=18):
    hline("1. 精确配色（出现最多的颜色，按像素数）")
    flat = a.reshape(-1, 3)
    u, c = np.unique(flat, axis=0, return_counts=True)
    order = np.argsort(-c)[:top]
    for i in order:
        rgb = u[i]
        print("   RGB(%3d,%3d,%3d)  n=%8d   gray=%5.1f" %
              (rgb[0], rgb[1], rgb[2], c[i], rgb.mean()))
    print()
    print("   灰度直方图（每 16 级一档，只列占比 >0.2% 的）")
    hist, edges = np.histogram(g, bins=16, range=(0, 256))
    tot = g.size
    for i, h in enumerate(hist):
        if h / tot > 0.002:
            print("     %3d~%3d : %6.2f%%" % (edges[i], edges[i + 1] - 1, 100.0 * h / tot))
    print()


def sec_fills(a, g, sat, minpix=30, max_show=40):
    hline("2. 填充块（按灰度分层做连通域）")
    if not HAVE_SCIPY:
        print("   scipy 缺失，跳过。pip install scipy")
        return
    # 从直方图峰里挑出候选层
    hist, edges = np.histogram(g, bins=64, range=(0, 256))
    peaks = []
    for i in range(1, len(hist) - 1):
        if hist[i] > 200 and hist[i] >= hist[i - 1] and hist[i] >= hist[i + 1]:
            peaks.append(int(edges[i] + 2))
    peaks = sorted(set(peaks))
    # 合并相邻峰
    merged = []
    for p in peaks:
        if merged and p - merged[-1][-1] <= 8:
            merged[-1].append(p)
        else:
            merged.append([p])
    centers = [int(np.mean(m)) for m in merged]

    for c in centers:
        mask = (np.abs(g - c) <= 8) & (sat < 16)
        lab, n = ndimage.label(mask)
        if n == 0:
            continue
        boxes = []
        for i in range(1, n + 1):
            ys, xs = np.nonzero(lab == i)
            if len(ys) < minpix:
                continue
            boxes.append((xs.min(), ys.min(), xs.max(), ys.max(), len(ys)))
        if not boxes:
            continue
        boxes.sort(key=lambda t: (t[1], t[0]))
        print("   --- 灰度 ~%d  (%d 个连通域 >= %dpx) ---" % (c, len(boxes), minpix))
        for b in boxes[:max_show]:
            print("      x[%4d,%4d] y[%4d,%4d]  w=%4d h=%4d  n=%d" %
                  (b[0], b[2], b[1], b[3], b[2] - b[0] + 1, b[3] - b[1] + 1, b[4]))
        if len(boxes) > max_show:
            print("      ... 另有 %d 个" % (len(boxes) - max_show))
    print()


def sec_bands(g, step=3, thr=205):
    hline("3. 逐行扫描（找水平边界/带状结构）")
    H, W = g.shape
    print("   y      x-range            n     （x-range 突变处 = 元素边界）")
    prev = None
    for y in range(0, H, step):
        xs = np.nonzero(g[y] < thr)[0]
        if not len(xs):
            if prev is not None:
                print("   %3d    (空)" % y)
            prev = None
            continue
        cur = (int(xs.min()), int(xs.max()))
        mark = "  <<<" if prev is not None and (abs(cur[0] - prev[0]) > 2 or abs(cur[1] - prev[1]) > 2) else ""
        print("   %3d    x[%4d,%4d]      %4d%s" % (y, cur[0], cur[1], len(xs), mark))
        prev = cur
    print()


def sec_columns(g, thr=205, step=None):
    hline("4. 逐列扫描（找竖直边界）")
    H, W = g.shape
    if step is None:
        step = max(1, W // 60)
    for x in range(0, W, step):
        ys = np.nonzero(g[:, x] < thr)[0]
        if len(ys):
            print("   x=%4d  runs=%s" % (x, runs_of(ys, gap=2)))
    print()


def sec_text(g, dilate=5, thr=150, max_h=26, min_glyph=4, min_line=3):
    hline("5. 文本行（字形连通域 + 横向膨胀合并）")
    if not HAVE_SCIPY:
        print("   scipy 缺失，跳过。")
        return
    m = g < thr
    lab, n = ndimage.label(m)
    comps = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if len(ys) < min_glyph:
            continue
        h = ys.max() - ys.min() + 1
        w = xs.max() - xs.min() + 1
        if h > max_h or w > 4 * max_h:      # 排除大结构 / 长线
            continue
        comps.append((int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))
    if not comps:
        print("   没找到字形。")
        print()
        return
    # 横向膨胀：把同一行里间距 < dilate 的字形连起来
    comps.sort(key=lambda c: c[0])
    lines = []
    for c in comps:
        for L in lines:
            if not (c[3] < L[0] - 4 or c[1] > L[1] + 4):     # y 有重叠
                if c[0] - L[2] <= dilate:
                    L[0] = min(L[0], c[1]); L[1] = max(L[1], c[3])
                    L[2] = max(L[2], c[2]); L[3] += 1
                    break
        else:
            lines.append([c[1], c[3], c[2], 1])
    lines.sort(key=lambda t: t[0])
    for L in lines:
        if L[3] < min_line:
            continue
        print("   y[%3d,%3d] h=%2d   x1=%4d   glyphs=%d" % (L[0], L[1], L[1] - L[0] + 1, L[2], L[3]))
    print("   （x1 是右边界；左边界需配合 sec_bands / 局部裁剪确认）")
    print()


def sec_crop(im, spec, zoom, name, outdir):
    hline("6. 局部放大裁图")
    x0, y0, x1, y1 = [int(v) for v in spec.split(",")]
    c = im.crop((x0, y0, x1, y1))
    z = max(1, int(zoom))
    c = c.resize((c.width * z, c.height * z), Image.NEAREST)
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, "%s.png" % (name or "crop"))
    c.save(p)
    print("   写出 %s   (%d,%d)-(%d,%d) @%dx  ->  %s" % (p, x0, y0, x1, y1, z, c.size))
    print()


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="图片转 Visio：源图像素取证")
    ap.add_argument("image")
    ap.add_argument("--sections", default="colors,fills,bands,columns,text",
                    help="逗号分隔：colors,fills,bands,columns,text")
    ap.add_argument("--outdir", default=None, help="裁图输出目录（默认图片所在目录）")
    ap.add_argument("--crop", default=None, help="x0,y0,x1,y1 局部放大")
    ap.add_argument("--zoom", type=int, default=4)
    ap.add_argument("--name", default=None, help="裁图文件名（不含扩展名）")
    ap.add_argument("--thr", type=int, default=205, help="线/结构的灰度阈值")
    ap.add_argument("--text-thr", type=int, default=150, help="文本的灰度阈值")
    ap.add_argument("--dilate", type=int, default=5, help="文本行合并的横向间隙（源像素）")
    ap.add_argument("--step", type=int, default=3, help="逐行扫描步长")
    args = ap.parse_args()

    if not os.path.exists(args.image):
        sys.exit("找不到图片：%s" % args.image)
    outdir = args.outdir or os.path.dirname(os.path.abspath(args.image))
    im, a, g, sat = load(args.image)

    hline("图片转 Visio — 像素取证")
    print("文件 : %s" % args.image)
    print("尺寸 : %d x %d  (W x H)" % im.size)
    print("反查 : 布局用 SCALE=48 源像素/英寸 -> 导出 %d x %d（2x）" % (im.width * 2, im.height * 2))
    print()

    want = set(s.strip() for s in args.sections.split(",") if s.strip())
    if "colors" in want:
        sec_colors(a, g, sat)
    if "fills" in want:
        sec_fills(a, g, sat)
    if "bands" in want:
        sec_bands(g, step=args.step, thr=args.thr)
    if "columns" in want:
        sec_columns(g, thr=args.thr)
    if "text" in want:
        sec_text(g, dilate=args.dilate, thr=args.text_thr)
    if args.crop:
        sec_crop(im, args.crop, args.zoom, args.name, outdir)


if __name__ == "__main__":
    main()
