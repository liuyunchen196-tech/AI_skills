#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
arrow_assets.py —— 箭头 / 连接件资产库（命名图形资产，一行取用）。

定位
    `slide_emit.py` 解决「整页选哪个版式」，`composition_lib.py` 解决「整页换哪种构图」，
    本库解决**元素级的连接表达**：把流程箭头、分支回流、循环闭环、汇聚分叉等
    **连接件**沉淀成命名资产 —— 需要时 `arrow("loop_back")` 一行取用，
    而不是每次手画线段、或用 `↓ → ➤` 之类的字符硬凑（字符箭头的字号/粗细/颜色随字体漂移，
    在中文正文字体下尤其不可控）。

资产清单（15 种）
    基础指向   straight 直线 / thin 细线 / dashed 虚线 / dotted 点线
    双向       bidi 双向
    转弯       elbow 直角折线 / zpath Z 型换行 / curve 弧形绕行
    关系       loop_back 回流 / fork 分叉 / merge 汇聚 / cycle 闭环
    带形       chevron 箭头带 / block 粗块箭头 / stair 阶梯递进

引擎事实（与 composition_lib 同源，实测）
    · `<svg>` 在 pptx 中落为 `ppt/slides/media/imageN.svg`（活的矢量，非位图）
    · SVG 内**中文可用**，但必须显式挂 `font-family`（`_svg()` 已注入 FONT_STACK）
    · 只用 `line / polygon / circle / rect / text` 五类元素：`<path>` 的二次曲线、
      `<marker>` 箭头定义、`<polyline>`、嵌套 `<svg>` 均**未验证**，一律避开 ——
      弧线用「多段 line 拼接」等效，箭头头一律用显式 `polygon` 画。
    · `<text>` 不支持换行 —— 带内标签必须短（≤6 字）

设计纪律
    · 颜色只用主蓝 / 深蓝 / 灰，粗细 2~3；**禁用旋转大箭头、渐变、阴影**
    · 箭头是「连接件」不是「装饰件」：面积小、语义强，不参与装饰占比统计
    · 主干指向用主蓝，回流 / 循环等次级路径用灰（视觉层级靠颜色而非粗细区分）
"""

import math

from composition_lib import P, _svg
from slide_emit import bs, ts

__all__ = ["ARROWS", "arrow", "arrow_band", "arrow_catalog", "loop_hint", "COLOR"]

# kind -> (中文名, 用途)
ARROWS = {
    "straight":  ("直线箭头", "最基础的指向：流程推进、因果方向"),
    "thin":      ("细线箭头", "弱化指向：次级关系、注解引出"),
    "dashed":    ("虚线箭头", "未定关系：推测、待确认、间接影响"),
    "dotted":    ("点线箭头", "弱关联：可选路径、弱依赖"),
    "bidi":      ("双向箭头", "对等关系：互相影响、双向映射"),
    "elbow":     ("折线箭头", "直角转弯：跨行列连接且不穿过中间元素"),
    "zpath":     ("Z 型箭头", "换行折返：上一行右端接到下一行左端"),
    "curve":     ("弧形箭头", "软性绕行：绕过中间内容再指向目标"),
    "loop_back": ("回流箭头", "判定不通过：否 → 退回上一步重来"),
    "fork":      ("分叉箭头", "一进多出：分流、并列展开"),
    "merge":     ("汇聚箭头", "多进一出：汇总、收敛成结论"),
    "cycle":     ("闭环箭头", "迭代回路：PDCA、持续改进、自我复盘"),
    "chevron":   ("箭头带",   "阶段推进带：每段带尖角，读感是依次推进"),
    "block":     ("粗块箭头", "强调指向：大方向、强对比、力量感"),
    "stair":     ("阶梯箭头", "逐级上升：能力跃迁、层级递进"),
}

COLOR = {"primary": P["primary"], "deep": P["primary_deep"],
         "muted": P["text_muted"], "sub": P["text_sub"]}


# ============================================================
# 内部工具
# ============================================================
def _head(x, y, dirn, size, color, hollow=False):
    """三角箭头头，(x, y) 是**尖端**坐标。dirn ∈ {'r','l','u','d'}。"""
    s = size
    if dirn == "r":
        pts = [(x, y), (x - s, y - s * 0.55), (x - s, y + s * 0.55)]
    elif dirn == "l":
        pts = [(x, y), (x + s, y - s * 0.55), (x + s, y + s * 0.55)]
    elif dirn == "u":
        pts = [(x, y), (x - s * 0.55, y + s), (x + s * 0.55, y + s)]
    else:                                   # 'd'
        pts = [(x, y), (x - s * 0.55, y - s), (x + s * 0.55, y - s)]
    ps = " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
    if hollow:
        return (f"<polygon points='{ps}' fill='none' stroke='{color}' "
                f"strokeWidth='2.2' />")
    return f"<polygon points='{ps}' fill='{color}' />"


def _line(x1, y1, x2, y2, color, weight, dash=None, opacity=1.0):
    d = f" strokeDasharray='{dash}'" if dash else ""
    return (f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' "
            f"stroke='{color}' strokeWidth='{weight}' strokeLinecap='round'{d} "
            f"opacity='{opacity}' />")


def _poly(pts, color, opacity=1.0):
    ps = " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
    return f"<polygon points='{ps}' fill='{color}' opacity='{opacity}' />"


def _arc(cx, cy, r, a0, a1, color, weight, opacity=1.0, segs=24):
    """用多段 line 近似圆弧（避开 <path>/<polyline>）。0° = 右，顺时针为正（SVG y 向下）。"""
    out = []
    prev = None
    for i in range(segs + 1):
        a = math.radians(a0 + (a1 - a0) * i / segs)
        pt = (cx + r * math.cos(a), cy + r * math.sin(a))
        if prev is not None:
            out.append(_line(prev[0], prev[1], pt[0], pt[1], color, weight, None, opacity))
        prev = pt
    return "".join(out), prev


# ============================================================
# 单箭头
# ============================================================
def arrow(kind="straight", w=150, h=48, color=None, weight=3,
          opacity=1.0, dirn="r", dash=None, hollow=False):
    """生成一个箭头（SVG），在 w×h 的盒子里绘制。

    kind   见 ARROWS
    dirn   'r' | 'd' —— 控制「直线/细线/虚线/点线/双向」朝向；其余 kind 自带方向语义
    """
    c = color or P["primary"]
    wt = float(weight)
    hs = max(7.0, wt * 2.6)
    cy = h / 2.0
    p = []

    if kind in ("straight", "thin", "dashed", "dotted", "bidi"):
        d = dash
        if kind == "dashed":
            d = "7 5"
        elif kind == "dotted":
            d = "1.5 6"
        hollow = hollow or kind == "thin"
        if dirn == "d":
            x = w / 2.0
            p.append(_line(x, 2, x, h - hs * 0.2, c, wt, d, opacity))
            p.append(_head(x, h - 1, "d", hs, c, hollow))
            if kind == "bidi":
                p.insert(0, _head(x, 1, "u", hs, c, hollow))
        else:
            p.append(_line(2, cy, w - hs * 0.2, cy, c, wt, d, opacity))
            p.append(_head(w - 1, cy, "r", hs, c, hollow))
            if kind == "bidi":
                p.insert(0, _head(1, cy, "l", hs, c, hollow))

    elif kind == "elbow":
        y0, y1 = h * 0.20, h * 0.84
        x1 = w * 0.62
        p.append(_line(2, y0, x1, y0, c, wt, dash, opacity))
        p.append(_line(x1, y0, x1, y1, c, wt, dash, opacity))
        p.append(_line(x1, y1, w - hs * 0.2, y1, c, wt, dash, opacity))
        p.append(_head(w - 1, y1, "r", hs, c, hollow))
        p.append(f"<circle cx='2' cy='{y0:.1f}' r='{wt*0.9:.1f}' fill='{c}' opacity='{opacity}' />")

    elif kind == "zpath":
        y0, y1 = h * 0.22, h * 0.78
        x1 = w * 0.48
        p.append(_line(2, y0, x1, y0, c, wt, dash, opacity))
        p.append(_line(x1, y0, x1, y1, c, wt, dash, opacity))
        p.append(_line(x1, y1, w - hs * 0.2, y1, c, wt, dash, opacity))
        p.append(_head(w - 1, y1, "r", hs, c, hollow))

    elif kind == "curve":
        r = min(h * 0.8, w * 0.4)
        base_y = h - r * 0.75
        seg, tip = _arc(w * 0.46, base_y, r, 185, 355, c, wt, opacity)
        p.append(seg)
        p.append(_head(tip[0] + hs * 0.55, tip[1] - hs * 0.1, "r", hs, c, hollow))

    elif kind == "loop_back":
        y_top, y_bot = h * 0.30, h * 0.84
        xr = w - 6
        p.append(_line(6, y_top, xr, y_top, c, wt, dash, opacity))
        p.append(_head(xr, y_top + hs * 0.2, "d", hs, c))
        p.append(_line(xr, y_top, xr, y_bot, c, wt, dash, opacity))
        p.append(_line(xr, y_bot, 6, y_bot, c, wt, dash, opacity))
        p.append(_head(6, y_top + hs * 0.1, "u", hs, c))

    elif kind == "fork":
        y0 = h * 0.5
        x1 = w * 0.45
        y_u, y_d = h * 0.18, h * 0.82
        p.append(_line(2, y0, x1, y0, c, wt, dash, opacity))
        p.append(_line(x1, y0, x1, y_u, c, wt, dash, opacity))
        p.append(_line(x1, y0, x1, y_d, c, wt, dash, opacity))
        p.append(_line(x1, y_u, w - hs * 0.2, y_u, c, wt, dash, opacity))
        p.append(_line(x1, y_d, w - hs * 0.2, y_d, c, wt, dash, opacity))
        p.append(_head(w - 1, y_u, "r", hs, c, hollow))
        p.append(_head(w - 1, y_d, "r", hs, c, hollow))

    elif kind == "merge":
        y0 = h * 0.5
        x1 = w * 0.55
        y_u, y_d = h * 0.18, h * 0.82
        p.append(_line(2, y_u, x1, y_u, c, wt, dash, opacity))
        p.append(_line(2, y_d, x1, y_d, c, wt, dash, opacity))
        p.append(_line(x1, y_u, x1, y0, c, wt, dash, opacity))
        p.append(_line(x1, y_d, x1, y0, c, wt, dash, opacity))
        p.append(_line(x1, y0, w - hs * 0.2, y0, c, wt, dash, opacity))
        p.append(_head(w - 1, y0, "r", hs, c, hollow))

    elif kind == "cycle":
        r = min(w * 0.36, h * 0.40)
        cx, cyy = w * 0.5, h * 0.5
        seg, tip = _arc(cx, cyy, r, 115, 425, c, wt, opacity, segs=30)
        p.append(seg)
        p.append(_head(tip[0] + hs * 0.62, tip[1] - hs * 0.25, "r", hs, c, hollow))
        for a in (0, 90, 180, 270):
            px = cx + r * math.cos(math.radians(a))
            py = cyy + r * math.sin(math.radians(a))
            p.append(f"<circle cx='{px:.1f}' cy='{py:.1f}' r='2.4' fill='{c}' opacity='0.45' />")

    elif kind == "chevron":
        hw = min(h * 0.55, w * 0.28)
        p.append(_poly([(0, 0), (w - hw, 0), (w, h * 0.5),
                        (w - hw, h), (0, h), (hw, h * 0.5)], c, opacity))

    elif kind == "block":
        wx = w - h * 0.62
        p.append(_poly([(2, h * 0.26), (wx, h * 0.26), (wx, h * 0.02),
                        (w - 2, h * 0.5), (wx, h * 0.98), (wx, h * 0.74),
                        (2, h * 0.74)], c, opacity))

    elif kind == "stair":
        n = 4
        sx = (w - hs * 1.4) / n
        sy = (h - hs * 1.8) / n
        pts = [(2, h - 4)]
        for i in range(1, n + 1):
            pts.append((2 + sx * i, h - 4 - sy * (i - 1)))
            pts.append((2 + sx * i, h - 4 - sy * i))
        for i in range(len(pts) - 1):
            p.append(_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                           c, wt, dash, opacity))
        p.append(_head(pts[-1][0] + hs * 0.7, pts[-1][1], "r", hs, c, hollow))

    else:
        raise ValueError("未知箭头资产: %s（可选：%s）" % (kind, "/".join(ARROWS)))

    return _svg(w, h, "".join(p))


# ============================================================
# 带形箭头
# ============================================================
def arrow_band(labels, kind="chevron", width=1152, height=74,
               color=None, text_color="#FFFFFF", font_size=16, gap=10):
    """横向「阶段推进带」：n 段首尾相扣，标签直接写在段内（SVG 内中文已可用）。

    labels: ["导入草稿", "分析现状", "路由版式", "写回导出"]（每格 ≤6 字）
    kind:   'chevron'（尖角相扣，默认）| 'block'（分离粗箭头）
    """
    c = color or P["primary"]
    n = len(labels)
    if n == 0:
        return _svg(width, height, "")
    out = []
    if kind == "block":
        seg = (width - (n - 1) * gap) / n
        hw = height * 0.34
        for i, lb in enumerate(labels):
            x = i * (seg + gap)
            out.append(_poly([(x, height * 0.22), (x + seg - hw, height * 0.22),
                              (x + seg - hw, height * 0.04), (x + seg, height * 0.5),
                              (x + seg - hw, height * 0.96), (x + seg - hw, height * 0.78),
                              (x, height * 0.78)], c if i % 2 == 0 else P["primary_deep"]))
            out.append(f"<text x='{x + (seg - hw) / 2:.1f}' "
                       f"y='{height * 0.5 + font_size * 0.36:.1f}' fontSize='{font_size}' "
                       f"fontWeight='bold' fill='{text_color}' textAnchor='middle'>{lb}</text>")
        return _svg(width, height, "".join(out))

    hw = min(height * 0.55, width / n * 0.26)
    adv = (width - hw) / n            # 每段实际推进量
    seg = adv + hw                    # 每段多边形宽度
    for i, lb in enumerate(labels):
        x = i * adv
        out.append(_poly([(x, 0), (x + seg - hw, 0), (x + seg, height * 0.5),
                          (x + seg - hw, height), (x, height),
                          (x + hw, height * 0.5)],
                         c if i % 2 == 0 else P["primary_deep"]))
        out.append(f"<text x='{x + seg * 0.5:.1f}' "
                   f"y='{height * 0.5 + font_size * 0.36:.1f}' fontSize='{font_size}' "
                   f"fontWeight='bold' fill='{text_color}' textAnchor='middle'>{lb}</text>")
    return _svg(width, height, "".join(out))


# ============================================================
# 资产总览
# ============================================================
def arrow_catalog(cell_w=368, cell_h=52, cols=3, color=None, kinds=None):
    """箭头资产总览：每种资产一格（箭头样张 + 中文名 + 用途），返回 Box 网格。

    既用于 deck 展示「连接件资产库」，也可作为设计评审时的选型样张。
    """
    ks = kinds or list(ARROWS)
    sw = int(cell_w * 0.60)
    rows = []
    for i in range(0, len(ks), cols):
        cells = []
        for k in ks[i:i + cols]:
            name, use = ARROWS[k]
            fig = arrow(k, w=sw, h=cell_h, color=color)
            st = bs(flex=1, flexDirection="column", gap=5, padding="9px 12px",
                    background=P["surface_alt"], borderRadius=10, justifyContent="center")
            cells.append(
                f"<Box {st}>"
                f"<Box {bs(flexDirection='row', alignItems='center', gap=10)}>"
                f"<Box {bs(width=sw, flexShrink=0)}>{fig}</Box>"
                f"<Text {ts(fontSize=13.5, fontWeight='bold', color=P['primary_deep'])}>{name}</Text>"
                f"</Box>"
                f"<Text {ts(fontSize=11, color=P['text_muted'], lineHeight=1.3)}>{use}</Text>"
                f"</Box>")
        while len(cells) < cols:
            cells.append(f"<Box {bs(flex=1)}></Box>")
        rows.append(f"<Box {bs(flex=1, flexDirection='row', gap=12, minHeight=0)}>"
                    + "".join(cells) + "</Box>")
    return (f"<Box {bs(flex=1, flexDirection='column', gap=12, minHeight=0)}>"
            + "".join(rows) + "</Box>")


def loop_hint(text="不通过 → 回到上一步", width=90):
    """回流提示行（回流箭头 + 小字），配合流程图使用。"""
    return (f"<Box {bs(flexDirection='row', gap=10, alignItems='center', justifyContent='center')}>"
            f"<Box {bs(width=width, flexShrink=0)}>"
            f"{arrow('loop_back', w=width, h=26, weight=2.2, color=P['text_muted'])}</Box>"
            f"<Text {ts(fontSize=12.5, color=P['text_muted'])}>{text}</Text></Box>")
