#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
layout_audit.py — PPT 布局体检 + 模板路由

逐页计算：文字占比 / 留白率 / 图形占比，判断 拥挤 / 纯文字 / 留白不足 / 健康，
并按结构启发式把问题页映射到 layout-whitespace-graphics.md 的模板（§编号）。

用法：
  python layout_audit.py <pptx> [--json 布局体检.json] [--top N]

输出：
  - 终端：每页一行判定 + 末尾「要动手的页」清单
  - --json：recommendations 数组，每条含
      {page, text_ratio, whitespace_ratio, graphic_ratio,
       verdict, template, ref_section, action, hints}
    action = "lightweight"(本 skill 按模板整改) | "route"(交 ppt-graphic-design)

依赖：python-pptx
"""
import argparse
import json
import sys

try:
    from pptx import Presentation
    from pptx.util import Emu
except ImportError:
    sys.stderr.write("缺少 python-pptx，先装：pip install python-pptx\n")
    sys.exit(2)


# ---- 阈值（经验值，16:9 校准）----
TEXT_RATIO_OVERLOAD = 0.60      # 文字占比 > 此值 = 文字过载
TEXT_RATIO_GRAPHICIZE = 0.35    # 文字占比在此区间且图形很少 = 建议图形化
GRAPHIC_RATIO_MIN = 0.08        # 非文字图形占比 < 此值 = 纯文字页
WHITESPACE_MIN = 0.15           # 留白 < 此值 = 留白不足
COLUMN_GAP = 0.18               # 文本 x 中心间距 > 此比例 = 不同列


def _frac(shape, slide_w, slide_h):
    """返回 shape 在版面的占比面积（0..1），无尺寸则 0。"""
    try:
        w = shape.width
        h = shape.height
    except Exception:
        return 0.0
    if not w or not h:
        return 0.0
    return float(w * h) / float(slide_w * slide_h)


def _walk(shapes):
    """递归展开（含 group 子形状），不重复计 group 自身。"""
    out = []
    for sh in shapes:
        if sh.shape_type == 6:  # GROUP
            out.extend(_walk(sh.shapes))
        else:
            out.append(sh)
    return out


def _has_text(sh):
    try:
        return bool(sh.has_text_frame and sh.text_frame.text.strip())
    except Exception:
        return False


def analyze_slide(slide, idx, prs=None):
    if prs is not None:
        sw = prs.slide_width
        sh = prs.slide_height
    else:
        sw = slide.part.package.presentation.slide_width
        sh = slide.part.package.presentation.slide_height
    slide_area = float(sw * sh)

    flat = _walk(slide.shapes)
    text_shapes = [s for s in flat if _has_text(s)]
    non_text = [s for s in flat if not _has_text(s)]

    sum_area = sum(_frac(s, sw, sh) for s in flat)
    text_area = sum(_frac(s, sw, sh) for s in text_shapes)
    non_text_area = sum(_frac(s, sw, sh) for s in non_text)

    text_ratio = min(text_area, 1.0)
    graphic_ratio = min(non_text_area, 1.0)
    whitespace = max(0.0, 1.0 - min(sum_area, 1.0))

    char_count = sum(len(s.text_frame.text) for s in text_shapes)
    bullet_lines = sum(len(s.text_frame.text.splitlines()) for s in text_shapes)

    # 列聚类：文本 x 中心
    centers = []
    for s in text_shapes:
        try:
            if s.width:
                centers.append(float(s.left + s.width / 2) / float(sw))
        except Exception:
            pass
    centers.sort()
    n_cols = 0
    last = None
    for c in centers:
        if last is None or (c - last) > COLUMN_GAP:
            n_cols += 1
            last = c

    verdict, template, ref_section, action, hints = _judge(
        text_ratio, graphic_ratio, whitespace, len(text_shapes), n_cols, bullet_lines
    )

    return {
        "page": idx + 1,
        "text_ratio": round(text_ratio, 3),
        "whitespace_ratio": round(whitespace, 3),
        "graphic_ratio": round(graphic_ratio, 3),
        "text_shapes": len(text_shapes),
        "columns": n_cols,
        "chars": char_count,
        "verdict": verdict,
        "template": template,
        "ref_section": ref_section,
        "action": action,
        "hints": hints,
    }


def _judge(text_ratio, graphic_ratio, whitespace, n_text, n_cols, bullet_lines):
    # 1) 文字过载
    if text_ratio > TEXT_RATIO_OVERLOAD:
        if n_cols >= 2:
            return ("文字过载", "双栏对照", "5.1", "lightweight",
                    "左右栏拆分，选中列用 primary_light 浅底")
        if bullet_lines >= 4:
            return ("文字过载", "横向流程图", "5.2", "lightweight",
                    "步骤式要点转横向 Box+箭头")
        return ("文字过载", "矩形并列/矩阵", "5.4", "lightweight",
                "并列要点转等宽卡片网格")
    # 2) 纯文字页，建议图形化
    if (TEXT_RATIO_GRAPHICIZE <= text_ratio <= TEXT_RATIO_OVERLOAD
            and graphic_ratio < GRAPHIC_RATIO_MIN and n_text >= 3):
        if n_cols >= 2:
            return ("纯文字页", "双栏对照", "5.1", "lightweight",
                    "已是双列结构，强化对照表 + 中缝细线")
        if n_text >= 5:
            return ("纯文字页", "矩形并列/矩阵", "5.4", "lightweight",
                    "多类要点转卡片网格")
        return ("纯文字页", "横向流程图", "5.2", "lightweight",
                "顺序要点转流程图")
    # 3) 留白不足但非文字过载
    if whitespace < WHITESPACE_MIN:
        return ("留白不足", "矩形并列/矩阵", "5.4", "lightweight",
                "用网格把内容铺开，腾出模块间距")
    # 4) 健康
    if graphic_ratio >= 0.25 and text_ratio <= 0.45:
        return ("布局健康", None, None, "ok", "图文均衡，保持")
    return ("布局健康", None, None, "ok", "无需改动")


def main():
    ap = argparse.ArgumentParser(description="PPT 布局体检 + 模板路由")
    ap.add_argument("pptx", help="目标 .pptx 路径")
    ap.add_argument("--json", help="输出 recommendations.json 路径", default=None)
    ap.add_argument("--top", type=int, default=0, help="只显示前 N 页（0=全部）")
    args = ap.parse_args()

    prs = Presentation(args.pptx)
    recs = [analyze_slide(s, i, prs) for i, s in enumerate(prs.slides)]

    if args.top:
        recs_view = recs[: args.top]
    else:
        recs_view = recs

    print("=" * 64)
    print("PPT 布局体检  %s  （共 %d 页）" % (args.pptx, len(recs)))
    print("=" * 64)
    for r in recs_view:
        line = ("第%02d页 | 文字%.0f%% 留白%.0f%% 图形%.0f%% | %s"
                % (r["page"], r["text_ratio"] * 100,
                   r["whitespace_ratio"] * 100, r["graphic_ratio"] * 100,
                   r["verdict"]))
        if r["template"]:
            line += " → 模板[%s] %s" % (r["ref_section"], r["template"])
        print(line)

    todo = [r for r in recs if r["action"] == "lightweight"]
    route = [r for r in recs if r["action"] == "route"]
    print("-" * 64)
    print("要动手（本 skill 按模板整改）：%s"
          % (", ".join("P%d[%s]" % (r["page"], r["ref_section"]) for r in todo) or "无"))
    print("交 ppt-graphic-design：%s"
          % (", ".join("P%d" % r["page"] for r in route) or "无"))
    print("=" * 64)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(recs, f, ensure_ascii=False, indent=2)
        print("已写 %s" % args.json)


if __name__ == "__main__":
    main()
