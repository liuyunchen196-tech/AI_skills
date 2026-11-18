# -*- coding: utf-8 -*-
"""
compare_render.py -- 源图 vs Visio 复刻：并排 + 红蓝叠加 + 逐区域 ink 比。

用法
----
  python compare_render.py src.png MyFigure_preview.png --outdir . --name MyFigure

  # 自定义关注区域（源图像素 x0,y0,x1,y1）
  # 名字后面加 * = 文本区，改按「中心偏差 + 宽度比」判定（文本的 ink 比天生偏低）
  python compare_render.py src.png prev.png --name MyFigure \
      --regions "title*:100,10,300,40;ground:10,258,355,270;slab:40,130,345,175"

  # 不做区域表，只出图
  python compare_render.py src.png prev.png --name MyFigure --regions none

约定：预览图应是源图的整数倍（本 skill 固定 2x）。非整数倍会被最近邻缩放到 2x。

判定标准（复刻/源 的 ink 像素比，阈值 L<200）：
    0.95~1.05  优秀      0.85~1.15  可接受      <0.80 或 >1.25  不合格，回去精测
  文本区域天生偏低（0.4~0.6）——源图是缩放位图，笔画比矢量渲染胖。
  文本只看**位置**（字串中心偏差 < 2 源像素）和**宽度**（比 0.9~1.1）。
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image


def to_scale(im, src_w, src_h, factor=2):
    """把复刻图缩放到 factor x 源图尺寸。"""
    tw, th = src_w * factor, src_h * factor
    if im.size != (tw, th):
        im = im.resize((tw, th), Image.LANCZOS)
    return im


def bbox_of_ink(g, thr=200):
    m = g < thr
    ys, xs = np.nonzero(m)
    if not len(ys):
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def main():
    ap = argparse.ArgumentParser(description="源图 vs Visio 复刻 比对")
    ap.add_argument("source")
    ap.add_argument("render")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--name", default=None, help="输出文件前缀（默认 render 的文件名）")
    ap.add_argument("--scale", type=int, default=2, help="复刻图相对源图的倍数（默认 2）")
    ap.add_argument("--thr", type=int, default=200, help="ink 阈值")
    ap.add_argument(
        "--regions", default="auto",
        help='"auto"=自动 3x3 网格 + 全图；"none"=不输出区域表；'
             '或 "名字:x0,y0,x1,y1;名字:..." （源图像素）')
    args = ap.parse_args()

    src = Image.open(args.source).convert("RGB")
    SW, SH = src.size
    rep_raw = Image.open(args.render).convert("RGB")
    rep = to_scale(rep_raw, SW, SH, args.scale)

    outdir = args.outdir or os.path.dirname(os.path.abspath(args.render))
    os.makedirs(outdir, exist_ok=True)
    name = args.name or os.path.splitext(os.path.basename(args.render))[0]

    up = src.resize((SW * args.scale, SH * args.scale), Image.LANCZOS)

    # ---- 并排 ---------------------------------------------------------- #
    g = 16
    sb = Image.new("RGB", (up.width * 2 + g, up.height), (255, 255, 255))
    sb.paste(up, (0, 0))
    sb.paste(rep, (up.width + g, 0))
    p_cmp = os.path.join(outdir, name + "_compare.png")
    sb.save(p_cmp)

    # ---- 红蓝叠加 ------------------------------------------------------ #
    a = 255 - np.array(up.convert("L"))
    b = 255 - np.array(rep.convert("L"))
    ov = np.stack([255 - b, 255 - np.maximum(a, b), 255 - a], axis=2).astype(np.uint8)
    p_ov = os.path.join(outdir, name + "_overlay.png")
    Image.fromarray(ov).save(p_ov)

    # ---- 数字 ---------------------------------------------------------- #
    ga = np.array(up.convert("L"))
    gb = np.array(rep.convert("L"))
    sa = ga < args.thr
    sb_ = gb < args.thr
    tot_a, tot_b = int(sa.sum()), int(sb_.sum())
    print("复刻 vs 源")
    print("  源图      : %d x %d" % (SW, SH))
    print("  复刻(原始): %s" % (rep_raw.size,))
    print("  复刻(归一): %s" % (rep.size,))
    print("  全图 ink  : 源 %d   复刻 %d   比 %.2f" %
          (tot_a, tot_b, (tot_b / tot_a) if tot_a else 0))
    ba, bb = bbox_of_ink(ga, args.thr), bbox_of_ink(gb, args.thr)
    print("  ink 包围盒: 源 %s   复刻 %s" % (ba, bb))
    if ba and bb:
        print("             左偏差 %+d  上偏差 %+d  右偏差 %+d  下偏差 %+d  (导出像素)"
              % (bb[0] - ba[0], bb[1] - ba[1], bb[2] - ba[2], bb[3] - ba[3]))
    print()

    # ---- 区域表 -------------------------------------------------------- #
    if args.regions == "none":
        regions = []
    elif args.regions == "auto":
        regions = [("FULL", (0, 0, SW, SH), False)]
        for iy in range(3):
            for ix in range(3):
                x0 = SW * ix // 3
                x1 = SW * (ix + 1) // 3
                y0 = SH * iy // 3
                y1 = SH * (iy + 1) // 3
                regions.append(("R%dC%d" % (iy + 1, ix + 1), (x0, y0, x1, y1), False))
    else:
        regions = []
        for part in args.regions.split(";"):
            if not part.strip():
                continue
            nm, box = part.split(":")
            is_text = nm.strip().endswith("*")
            nm = nm.strip().rstrip("*")
            x0, y0, x1, y1 = [int(v) for v in box.split(",")]
            regions.append((nm, (x0, y0, x1, y1), is_text))

    if regions:
        s = args.scale
        print("  区域比对")
        print("  非文本区按 ink 像素比判；文本区（名字加 *）按 中心偏差 + 宽度比 判")
        print("  （文本的 ink 比天生只有 0.4~0.6——源图是缩放位图，笔画比矢量渲染胖，属正常）")
        print()
        print("  %-10s %8s %8s %7s %8s %8s %8s   %s" %
              ("region", "src", "rep", "ratio", "dx(px)", "dy(px)", "wratio", "判定"))

        def ink_bbox(mask):
            ys, xs = np.nonzero(mask)
            if not len(ys):
                return None
            return xs.min(), ys.min(), xs.max(), ys.max()

        for nm, (x0, y0, x1, y1), is_text in regions:
            MA = sa[y0 * s:y1 * s, x0 * s:x1 * s]
            MB = sb_[y0 * s:y1 * s, x0 * s:x1 * s]
            A, B = int(MA.sum()), int(MB.sum())
            ratio = (B / A) if A else float("nan")
            ba, bb = ink_bbox(MA), ink_bbox(MB)
            if ba and bb:
                # 中心偏差换算回**源像素**
                dx = ((bb[0] + bb[2]) - (ba[0] + ba[2])) / 2.0 / s
                dy = ((bb[1] + bb[3]) - (ba[1] + ba[3])) / 2.0 / s
                wa = ba[2] - ba[0] + 1
                wb = bb[2] - bb[0] + 1
                wratio = wb / wa
            else:
                dx = dy = float("nan")
                wratio = float("nan")

            if A == 0:
                verdict = "源图该区域无墨迹"
            elif is_text:
                if abs(dx) <= 1.0 and abs(dy) <= 1.5 and 0.95 <= wratio <= 1.05:
                    verdict = "优秀"
                elif abs(dx) <= 2.0 and abs(dy) <= 3.0 and 0.90 <= wratio <= 1.10:
                    verdict = "可接受"
                else:
                    verdict = "偏差 -> 调文本框中心/字号"
            elif 0.95 <= ratio <= 1.05:
                verdict = "优秀"
            elif 0.85 <= ratio <= 1.15:
                verdict = "可接受"
            elif ratio < 0.80 or ratio > 1.25:
                verdict = "不合格 -> 精测该区域"
            else:
                verdict = "偏差"

            print("  %-10s %8d %8d %7.2f %8.1f %8.1f %8.2f   %s" %
                  (nm, A, B, ratio, dx, dy, wratio, verdict))
        print()

    print("写出:")
    print("  " + p_cmp)
    print("  " + p_ov)
    print()
    print("读图提示：叠加图里 红=源图、蓝=复刻、黑=重合。")
    print("  出现成对的红蓝双线 = 有平移偏差；只有红或只有蓝 = 该元素多画/漏画。")


if __name__ == "__main__":
    main()
