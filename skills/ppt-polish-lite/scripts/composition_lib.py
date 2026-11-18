#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
composition_lib.py —— 构图构件库（构图原型 / 图形化表达 · 可复用资产）。

定位
    与 `slide_emit.py`（整页版式路由，16 种）互补：
    `slide_emit` 产出「整页骨架」，本库产出**构图构件（片段）**——
    造 deck 时按需拼装，用来把「内容组织方式」从单一模板变成多种原型交替，
    避免整篇视觉疲劳（人类作者的 deck 天然会换构图）。

原型清单（21 种，含本库新增 13 种）
    [原有可组合项] card_row / card_grid / two_column / layered_stack / flow_* 由 slide_emit 提供
    [本库新增]
      1)  four_row(items)            4 要点·横排等宽
      2)  four_grid(items)           4 要点·2×2 网格
      3)  four_stagger(items)        4 要点·阶梯错位（注入节奏）
      4)  four_radial(center, items) 4 要点·中心辐射（1 中心 + 4 环绕）
      5)  four_top1_bottom3(...)     4 要点·上一下三（主次分级）
      6)  four_split_2x2(...)        4 要点·左右分栏各 2
      7)  arrangement_gallery()      4 要点排布的「线框图谱」（一页看全 6 种）
      8)  pentagon_overall(...)      五边形整体（5 段围成一个整体 + 顶点编号）
      9)  polygon_honeycomb(...)     六边形蜂巢（非矩形多边形卡）
     10)  diamond_steps(steps)       菱形步骤带（非矩形流程）
     11)  arch_diagram(tiers)        架构图（SVG 分层 + 层间连线 + 模块格）
     12)  flow_branch(steps)         流程图（SVG 节点 + 菱形判定 + 是/否分支）
     13)  code_block(code, lang)     代码块（CodeBlock，macOS 三色点 + 语法高亮）
     14)  score_table(...)           打分对比表（Table + ✓✗★ + 推荐列高亮）
     15)  compare_matrix(...)        多维对比表（Table 斑马纹 + 表头深底）
     16)  decor_corner()             留白区装饰·角部几何纹样（低语义 SVG）
     17)  decor_ring(pct)            留白区装饰·进度环（低语义 SVG）
     18)  decor_dotgrid()            留白区装饰·点阵（低语义 SVG）
     19)  side_image_band(img)       侧栏装饰图片带（受占比约束）
     20)  kv_metric_row(...)         关键指标行（数字锚点）
     21)  pull_quote(...)            引文块（留白区利用）

引擎事实（实测，见 references/known-pitfalls.md）
    · `<svg>` 是**首选**矢量渲染路径（架构图/流程图禁走 `<Diagram>`：它依赖远程 Kroki，易 502）
    · SVG 在 pptx 中落为 `ppt/slides/media/imageN.svg`（**活的矢量，不是位图**），
      python-pptx 取不到内嵌 blob —— 可据此与内容位图区分
    · **SVG 内中文可用，但必须显式挂 `font-family`**：文字由查看器字体引擎在渲染时解析，
      不指定就会走查看器默认字体、跨机器观感不可控。`_svg()` 已统一注入 FONT_STACK。
      （此条取代早期「SVG 只放数字/拉丁字符」的保守做法——那是把「没指定字体」误判成「不支持中文」。）
    · **正 4 边形的 `rot` 决定「菱形 vs 正方形」**：`rot=-45` 顶点落在四个对角线上 → 渲染成
      **轴对齐正方形**；`rot=-90` 才把首个顶点放正上方 → 上/右/下/左四点 = 菱形。踩过。
    · `<Table>` 落为真 **TABLE** 形状；`<CodeBlock>` 落为**深色底 AUTO_SHAPE + 文本框**
    · Box 仅支持 `display:flex`，**不支持 grid / calc()**
    · SVG `h` 不要写死大值：写死会在图形与下方说明之间留出空洞（flow_branch 踩过 300→动态）

设计纪律（见 references/layout-whitespace-graphics.md）
    · 零阴影、零卡片顶弧、零标题竖条、零卡片边框
    · 主蓝只做「点」与图标 fill，卡底只用 tint / 白
    · 装饰必须结构化、低语义，且落在留白区；装饰总面积 ≤ 内容区 25%
    · 常规内容页留白 ≤ 35%
"""

import math

from slide_emit import DEFAULT_PALETTE, bs, ts, icon_circle

P = DEFAULT_PALETTE
CW = 1152          # 内容区宽度（1280 − 左右各 64 padding）
CH = 560           # 内容区参考高度（720 − 上 48 − 下 40 − 标题区）

# ---- 内容区垂直居中的「下移补偿」------------------------------------------------
# 用户反馈的原话：「表格没有垂直居中！留白不能只在下方，应该是信息区上下平均」。
# 实测标定（探针脚本 _probe_fit.py + 渲染像素量测）：
#   · body 骨架的可用内容带 = 153..641（高 488），页脚可见文字 = 669..684；
#     页脚组件在布局上比它的可见文字高约 28px（15px 文字 / 43px 布局），
#     这 28px 死区落在内容带下方 → 内容组即使「在容器内居中」，视觉上仍然偏上。
#   · 实测偏差恒定：上方 22px / 下方 32px（差 10px），与内容多少无关（容器高度固定）。
#   · 修正：把内容组整体下移 5px。居中容器里给子元素 `marginTop=2×5` 即产生 5px 位移。
#     → CENTER_BIAS = 10，配合 vcenter_band() 使用，全 deck 一致。
CENTER_BIAS = 10

__all__ = [
    "four_row", "four_grid", "four_stagger", "four_radial",
    "four_top1_bottom3", "four_split_2x2", "arrangement_gallery",
    "pentagon_overall", "polygon_honeycomb", "diamond_steps",
    "arch_diagram", "flow_branch", "code_block",
    "score_table", "compare_matrix",
    "decor_corner", "decor_ring", "decor_dotgrid", "side_image_band",
    "kv_metric_row", "pull_quote",
    "vcenter_band",
]


# ============================================================
# 0. 内部工具
# ============================================================
def _poly_pts(n, cx, cy, r, rot=-90.0):
    """正 n 边形顶点坐标串（SVG points 格式）。rot=-90 表示首个顶点在正上方。"""
    pts = []
    for i in range(n):
        a = math.radians(rot + i * 360.0 / n)
        pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
    return " ".join(pts)


# SVG 文字字体栈：必须与 deck 字体一致。**SVG 在 pptx 里是「活的 .svg」（不是位图）**——
# 实测 media 里落的是 `ppt/slides/media/imageN.svg`，文字由查看器的字体引擎在渲染时解析。
# 不挂 font-family 时中文会走查看器默认字体（跨机器观感不可控）；挂上后与 Box+Text 等价。
FONT_STACK = "Microsoft YaHei, 微软雅黑, PingFang SC, sans-serif"


def _svg(w, h, children):
    """包一个 SVG 容器。

    - width/height 必填，viewBox 保比例。
    - **默认挂 font-family**：SVG 内中文可用，但必须显式指定字体（见 FONT_STACK 注释）。
      这条是实测结论，取代此前「SVG 只放数字/拉丁字符」的保守做法。
    """
    return (f"<svg width={{{w}}} height={{{h}}} viewBox='0 0 {w} {h}' "
            f"fontFamily='{FONT_STACK}'>" + children + "</svg>")


def _boxtag(**kw):
    """生成 `<Box style={{...}}>` 开标签。

    之所以要包一层：f-string 里的 `{ ... }` 表达式**不能跨隐式字符串拼接断开**
    （`f"...{bs(a,"  f"b=1)}"` 会 SyntaxError）。用普通函数调用可自由换行。
    """
    return "<Box " + bs(**kw) + ">"


def _num_badge(n, size=44, bg=None, fg="#FFFFFF"):
    """实心圆编号徽章（主蓝填充，白字）。"""
    bg = bg or P["primary"]
    return (_boxtag(width=size, height=size, borderRadius=size // 2, background=bg,
                    justifyContent="center", alignItems="center", flexShrink=0)
            + f"<Text {ts(fontSize=int(size * 0.42), fontWeight='bold', color=fg)}>{n}</Text></Box>")


# ============================================================
# 0.5 内容区垂直居中（用户明确要求的行为）
# ============================================================
def vcenter_band(children, gap=18, bias=CENTER_BIAS, vcenter=True):
    """把「引导句 + 主体 + 收束句」整组在内容区**垂直居中**，并做下移补偿。

    children：按上下顺序排列的已渲染 DSL 片段（list/tuple 均可）。

    为什么必须用这个、而不是 `justifyContent='space-between'`：
        space-between 会把引导句顶到标题下、收束句顶到页脚上，中间的主体被
        「撑」到剩余空间里 —— 内容少时主体浮在上半页、下半页整片空白
        （用户原话：「留白只在下方，显得下方太空」）。

    bias 的作用（见模块顶部 CENTER_BIAS 的实测标定）：
        页脚组件在布局上比其可见文字高约 28px，这段死区落在内容带下方，
        导致「容器内已居中」但视觉上仍偏上（实测上 22px / 下 32px）。
        用 `paddingTop=bias`：内容可用高度少 bias、起点下移 bias
        → 居中位置净下移 **bias/2**，故 bias=10 → 下移 5px → 视觉上下各 ~27px，对称。

    ⚠️ 必须**单层**实现（同一个 Box 上同时用 `justifyContent:center` + `paddingTop`）。
        踩过的坑：先写成「外层居中 + 内层 marginTop」两层嵌套，结果内层是
        auto 高度，而主体的 `flex=1` 在 auto 高度容器里拿不到确定高度 →
        32 页里 **16 页** 直接 `child-containment` 溢出（最大 301px），
        而「主体没有 flex」的页（表格 / 代码块）却全部正常，症状极具误导性。
        → 结论：**不要在 flex 骨架中间插入无高度约束的包装层**。

    vcenter=False：退回 space-between 撑满式，仅在需要极限填充率时使用。
    """
    if vcenter:
        st = bs(flex=1, flexDirection="column", gap=gap, justifyContent="center",
                paddingTop=bias, minHeight=0)
    else:
        st = bs(flex=1, flexDirection="column", gap=gap,
                justifyContent="space-between", minHeight=0)
    return f"<Box {st}>{''.join(children)}</Box>"


def _tint_card(inner, bg=None, pad="20px 18px", radius=14, gap=10, align="center",
               text_align="center"):
    bg = bg or P["accent_tint"]
    return (_boxtag(flex=1, background=bg, borderRadius=radius, padding=pad,
                    flexDirection="column", gap=gap, justifyContent="center",
                    alignItems=align, textAlign=text_align)
            + inner + "</Box>")


def _card(num, title, desc, bg=None, badge=40):
    return _tint_card(
        _num_badge(num, badge) +
        f"<Text {ts(fontSize=17, fontWeight='bold', color=P['primary_deep'], lineHeight=1.3)}>{title}</Text>" +
        f"<Text {ts(fontSize=13, color=P['text_sub'], lineHeight=1.5)}>{desc}</Text>",
        bg=bg)


def _rlabel(num, title, desc):
    """右侧编号说明行（与左侧示意图的编号对应）。"""
    sep = "1px solid " + P["divider"]
    return (f"<Box {bs(flexDirection='row', gap=12, alignItems='center', padding='9px 0', borderBottom=sep)}>"
            f"{_num_badge(num, 30)}"
            f"<Box {bs(flex=1, flexDirection='column', gap=2)}>"
            f"<Text {ts(fontSize=16, fontWeight='bold', color=P['primary_deep'])}>{title}</Text>"
            f"<Text {ts(fontSize=13, color=P['text_sub'], lineHeight=1.4)}>{desc}</Text>"
            f"</Box></Box>")


# ============================================================
# 1. 四个要点的 6 种排布（用户核心问题：4 个要点能有几种排法）
# ============================================================
def four_row(items):
    """1. 横排等宽：4 张等宽卡一行 —— 最稳、最常规；适合 4 项并列且无主次。"""
    return (f"<Box {bs(height=250, flexDirection='row', gap=16, alignItems='stretch')}>"
            + "".join(_card(*it) for it in items) + "</Box>")


def four_grid(items):
    """2. 2×2 网格：卡更宽更矮 —— 适合每项文字较多、需要更大阅读面。"""
    def row(a, b):
        return (f"<Box {bs(flex=1, flexDirection='row', gap=16)}>"
                + _card(*items[a]) + _card(*items[b]) + "</Box>")
    return (f"<Box {bs(flex=1, flexDirection='column', gap=16, minHeight=0)}>"
            + row(0, 1) + row(2, 3) + "</Box>")


def four_stagger(items):
    """3. 阶梯错位：每卡上下错开，注入动态节奏 —— 适合 4 项有递进感。"""
    offs = [0, 34, 68, 102]
    cells = []
    for (it, off) in zip(items, offs):
        cells.append(f"<Box {bs(flex=1, flexDirection='column', marginTop=off)}>"
                     + _card(*it, badge=38) + "</Box>")
    return f"<Box {bs(height=330, flexDirection='row', gap=14, alignItems='flex-start')}>{''.join(cells)}</Box>"


def four_radial(center_title, items):
    """4. 中心辐射：1 个中心核 + 4 张环绕卡 —— 适合「一个目标 + 四个支撑」。"""
    def side(it):
        return _tint_card(
            f"<Box {bs(flexDirection='row', gap=10, alignItems='center')}>"
            + _num_badge(it[0], 32)
            + f"<Box {bs(flex=1, flexDirection='column', gap=2)}>"
              f"<Text {ts(fontSize=15, fontWeight='bold', color=P['primary_deep'])}>{it[1]}</Text>"
              f"<Text {ts(fontSize=12, color=P['text_sub'], lineHeight=1.4)}>{it[2]}</Text>"
              f"</Box></Box>",
            pad="14px 16px", align="flex-start", text_align="left")
    core = (_boxtag(width=250, height=250, borderRadius=125, background=P["primary_deep"],
                    justifyContent="center", alignItems="center", flexShrink=0, padding="0 30px")
            + f"<Text {ts(fontSize=19, fontWeight='bold', color='#FFFFFF', textAlign='center', lineHeight=1.4)}>{center_title}</Text></Box>")
    left = (f"<Box {bs(flex=1, flexDirection='column', gap=14, justifyContent='center')}>"
            + side(items[0]) + side(items[1]) + "</Box>")
    right = (f"<Box {bs(flex=1, flexDirection='column', gap=14, justifyContent='center')}>"
             + side(items[2]) + side(items[3]) + "</Box>")
    return (f"<Box {bs(flex=1, flexDirection='row', gap=22, alignItems='center', minHeight=0)}>"
            + left + core + right + "</Box>")


def four_top1_bottom3(main, subs):
    """5. 上一下三：顶部一张主卡 + 下方三张子卡 —— 适合「1 个总纲 + 3 个展开」。"""
    top = (_boxtag(background=P["primary_deep"], borderRadius=14, padding="20px 26px",
                   flexDirection="row", alignItems="center", gap=16)
           + _num_badge(main[0], 36, bg="#FFFFFF", fg=P["primary_deep"])
           + f"<Box {bs(flex=1, flexDirection='column', gap=3)}>"
             f"<Text {ts(fontSize=18, fontWeight='bold', color='#FFFFFF')}>{main[1]}</Text>"
             f"<Text {ts(fontSize=13, color='#C9D8FF', lineHeight=1.4)}>{main[2]}</Text>"
             f"</Box></Box>")
    bottom = (f"<Box {bs(flex=1, flexDirection='row', gap=16)}>"
              + "".join(_card(*s, badge=36) for s in subs) + "</Box>")
    return (f"<Box {bs(flex=1, flexDirection='column', gap=16, minHeight=0)}>"
            + top + bottom + "</Box>")


def four_split_2x2(items):
    """6. 左右分栏各 2：左 2 右 2 的对称双区 —— 适合两组对照（现状 2 项 vs 目标 2 项）。"""
    def col(a, b, bg, head):
        return (_boxtag(flex=1, background=bg, borderRadius=14, padding="18px 18px",
                        flexDirection="column", gap=12)
                + f"<Text {ts(fontSize=16, fontWeight='bold', color=P['primary_deep'])}>{head}</Text>"
                + _mini(a) + _mini(b) + "</Box>")
    def _mini(it):
        return (_boxtag(flex=1, flexDirection="row", gap=10, alignItems="center",
                        background="#FFFFFF", borderRadius=10, padding="12px 14px")
                + _num_badge(it[0], 30)
                + f"<Box {bs(flex=1, flexDirection='column', gap=2)}>"
                  f"<Text {ts(fontSize=14, fontWeight='bold', color=P['text_main'])}>{it[1]}</Text>"
                  f"<Text {ts(fontSize=12, color=P['text_sub'], lineHeight=1.35)}>{it[2]}</Text>"
                  f"</Box></Box>")
    return (f"<Box {bs(flex=1, flexDirection='row', gap=18, minHeight=0)}>"
            + col(items[0], items[1], P["surface_alt"], "第一组") +
            col(items[2], items[3], P["accent_tint"], "第二组") + "</Box>")


def arrangement_gallery():
    """4 要点排布的「线框图谱」：一页看全 6 种骨架（纯 SVG 线框，低语义结构化元素）。

    每个线框单元 166×240（宽度受 6 列 × 1152 内容区约束，只能竖着长）。
    高度 190 → 240 是补填充率：190 时整页填充率只有 48%（低于 MIN_FILL 0.55），
    观感是「图谱浮在页面中间、上下都空」。内层示意矩形统一 `DY` 下移保持居中。
    """
    U, GAPX = 166, 30
    H = 240
    DY = 25          # (240-190)/2：内层示意矩形整体下移，保持视觉居中

    def y(v):
        return v + DY
    cells = []
    fill, stroke = "#F0F5FF", "#1677FF"

    def rect(x, yy, w, h, r=8, f=None):
        return f"<rect x='{x:.0f}' y='{yy:.0f}' width='{w:.0f}' height='{h:.0f}' rx='{r}' fill='{f or fill}' />"

    def frame(ox, oy):
        return (f"<rect x='{ox:.0f}' y='{oy:.0f}' width='{U}' height='{H}' rx='10'"
                f" fill='none' stroke='#E5E7EB' strokeWidth='2' />")

    # 1. 横排 4
    ox = 0; cells.append(frame(ox, 0))
    for i in range(4):
        cells.append(rect(ox + 12 + i * 36, y(60), 30, 70))
    # 2. 2×2
    ox = U + GAPX; cells.append(frame(ox, 0))
    for r in range(2):
        for c in range(2):
            cells.append(rect(ox + 20 + c * 70, y(34 + r * 66), 60, 56))
    # 3. 阶梯错位
    ox = 2 * (U + GAPX); cells.append(frame(ox, 0))
    for i in range(4):
        cells.append(rect(ox + 12 + i * 36, y(40 + i * 24), 30, 68))
    # 4. 中心辐射
    ox = 3 * (U + GAPX); cells.append(frame(ox, 0))
    cy = H / 2
    cells.append(f"<circle cx='{ox + U/2:.0f}' cy='{cy:.0f}' r='26' fill='{stroke}' />")
    for (dx, dy) in ((0, -66), (0, 66), (-62, 0), (62, 0)):
        cells.append(rect(ox + U / 2 + dx - 22, cy + dy - 18, 44, 36, 8))
    # 5. 上一下三
    ox = 4 * (U + GAPX); cells.append(frame(ox, 0))
    cells.append(rect(ox + 14, y(30), U - 28, 44, 8, stroke))
    for i in range(3):
        cells.append(rect(ox + 14 + i * 48, y(96), 40, 68))
    # 6. 左右各 2
    ox = 5 * (U + GAPX); cells.append(frame(ox, 0))
    for c in range(2):
        for r in range(2):
            cells.append(rect(ox + 16 + c * 78, y(32 + r * 68), 60, 52))

    w = 6 * U + 5 * GAPX
    return _svg(w, H, "".join(cells))


# ============================================================
# 2. 五边形整体 / 多边形卡
# ============================================================
def pentagon_overall(items, center_title="5 in 1"):
    """五边形整体：左 SVG 五边形（顶点编号 1-5）+ 右 5 条编号说明。

    用「5 段围成一体」表达「五位一体 / 五个环节闭环」这类整体性关系，
    比并列卡片更能传达「合起来才是完整的一件事」。
    center_title 落在 SVG `<text>` 内——中文可以放（`_svg` 已挂字体栈），
    但内五边形只有 ~168px 宽，中文建议 ≤4 字，否则用短拉丁串。
    """
    S = 380
    cx = cy = S / 2
    r = 150
    inner_r = 84
    parts = [
        f"<polygon points='{_poly_pts(5, cx, cy, r)}' fill='#F0F5FF' stroke='{P['primary']}' strokeWidth='3' />",
        f"<polygon points='{_poly_pts(5, cx, cy, inner_r)}' fill='#FFFFFF' stroke='#E5E7EB' strokeWidth='2' />",
    ]
    # 顶点圆点 + 编号（数字安全）
    for i in range(5):
        a = math.radians(-90 + i * 72)
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        parts.append(f"<circle cx='{px:.1f}' cy='{py:.1f}' r='19' fill='{P['primary']}' />")
        parts.append(f"<text x='{px:.1f}' y='{py + 7:.1f}' fontSize='20' fill='#FFFFFF' "
                     f"textAnchor='middle'>{i + 1}</text>")
    # 中心副标（内圈窄，短串更稳；中文 ≤4 字亦可）
    parts.append(f"<text x='{cx:.1f}' y='{cy + 6:.1f}' fontSize='22' fill='{P['primary_deep']}' "
                 f"textAnchor='middle'>5 in 1</text>")
    figure = _svg(S, S, "".join(parts))
    rows = "".join(_rlabel(str(i + 1), t, d) for i, (t, d) in enumerate(items))
    return (f"<Box {bs(flex=1, flexDirection='row', gap=36, alignItems='center', minHeight=0)}>"
            f"<Box {bs(flexShrink=0, justifyContent='center', alignItems='center')}>{figure}</Box>"
            f"<Box {bs(flex=1, flexDirection='column', justifyContent='center')}>{rows}</Box>"
            f"</Box>")


def polygon_honeycomb(cells, cols=3):
    """六边形蜂巢：非矩形多边形卡（SVG 六边形 + 单元格内编号），右侧/下方配编号说明。

    cells: [(标题, 说明), ...] 建议 5-6 个。
    """
    n = len(cells)
    rows = []
    hw = 96          # 六边形外接半径
    step_x = hw * 1.72
    step_y = hw * 1.5
    w = int(step_x * cols + hw)
    h = int(step_y * ((n + cols - 1) // cols) + hw)
    parts = []
    coords = []
    for i in range(n):
        r_i, c_i = divmod(i, cols)
        x = hw + c_i * step_x + (step_x / 2 if r_i % 2 else 0)
        y = hw + r_i * step_y
        coords.append((x, y))
        fill = P["accent_tint"] if i % 2 == 0 else P["icon_bg"]
        parts.append(f"<polygon points='{_poly_pts(6, x, y, hw * 0.92)}' fill='{fill}' "
                     f"stroke='{P['primary']}' strokeWidth='2.5' />")
        parts.append(f"<text x='{x:.1f}' y='{y + 11:.1f}' fontSize='34' "
                     f"fill='{P['primary_deep']}' textAnchor='middle'>{i + 1}</text>")
    ladder = "".join(
        f"<Box {bs(flexDirection='row', gap=12, alignItems='center', padding='10px 0')}>"
        + _num_badge(i + 1, 30)
        + f"<Box {bs(flex=1, flexDirection='column', gap=2)}>"
          f"<Text {ts(fontSize=15, fontWeight='bold', color=P['primary_deep'])}>{t}</Text>"
          f"<Text {ts(fontSize=12, color=P['text_sub'], lineHeight=1.4)}>{d}</Text>"
          f"</Box></Box>"
        for i, (t, d) in enumerate(cells))
    return (f"<Box {bs(flex=1, flexDirection='row', gap=30, alignItems='center', minHeight=0)}>"
            f"<Box {bs(flexShrink=0, justifyContent='center', alignItems='center')}>"
            f"{_svg(w, h, ''.join(parts))}</Box>"
            f"<Box {bs(flex=1, flexDirection='column', justifyContent='center')}>{ladder}</Box>"
            f"</Box>")


def diamond_steps(steps):
    """菱形步骤带：用菱形（旋转 45° 的正方形）串联步骤，替代矩形卡（非矩形流程原型）。

    ⚠️ 菱形必须用 `rot=-90`：正 4 边形在 `rot=-45` 时顶点落在四个对角线上，
    渲染出来是**轴对齐正方形**（实测踩过，标题写「菱形」而画面是方块）。
    `rot=-90` 才把首个顶点放到正上方 → 上/右/下/左四个顶点 = 菱形。
    """
    n = len(steps)
    S = 140                     # 单元步距
    gap = 78
    r = S * 0.48                # 菱形半径 → 视觉尺寸 ≈ 2r ≈ 134
    w = n * S + (n - 1) * gap
    parts = []
    for i in range(n):
        cx = S / 2 + i * (S + gap)
        cy = S / 2
        parts.append(f"<polygon points='{_poly_pts(4, cx, cy, r)}' "
                     f"fill='{P['accent_tint'] if i % 2 == 0 else P['icon_bg']}' />")
        parts.append(f"<text x='{cx:.1f}' y='{cy + 12:.1f}' fontSize='34' "
                     f"fill='{P['primary_deep']}' textAnchor='middle'>{i + 1}</text>")
        if i < n - 1:
            nx = S / 2 + (i + 1) * (S + gap)
            parts.append(f"<line x1='{cx + r + 4:.1f}' y1='{cy:.1f}' "
                         f"x2='{nx - r - 4:.1f}' y2='{cy:.1f}' "
                         f"stroke='{P['primary']}' strokeWidth='3' />")
    figure = _svg(w, S, "".join(parts))
    labels = (f"<Box {bs(flexDirection='row', gap=14, width='100%')}>"
              + "".join(f"<Box {bs(flex=1, flexDirection='column', gap=3, alignItems='center', textAlign='center')}>"
                        f"<Text {ts(fontSize=15, fontWeight='bold', color=P['primary_deep'])}>{t}</Text>"
                        f"<Text {ts(fontSize=12, color=P['text_sub'], lineHeight=1.4)}>{d}</Text>"
                        f"</Box>" for t, d in steps)
              + "</Box>")
    return (_boxtag(flex=1, flexDirection="column", gap=26, alignItems="center",
                    justifyContent="center", minHeight=0)
            + f"{figure}{labels}</Box>")


# ============================================================
# 3. 架构图 / 流程图（SVG 几何 + Box 文字，规避 Kroki）
# ============================================================
def arch_diagram(tiers, width=CW, tier_h=64, gap=18):
    """架构图：SVG 画「分层带 + 层内模块格（模块名在格内） + 层间下行箭头」。

    tiers: [(层名, [模块名, ...]), ...] 自上而下。
    左侧 150px 放层名（Box+Text，中文粗体），右侧 SVG 承载几何 + 模块名。
    ⚠️ 模块名直接写进 SVG（`_svg` 已挂 FONT_STACK）——此前把模块名甩到页脚图例，
    结果是「一堆空白方格 + 一行读不下去的长句」，实测观感失败。中文进 SVG 安全。
    """
    n = len(tiers)
    svg_w = width - 150 - 20      # 左侧层名列 150 + 行内 gap 18 + 2px 余量
    h = n * tier_h + (n - 1) * gap
    box_h = tier_h - 26
    parts = []
    for i, (name, mods) in enumerate(tiers):
        y = i * (tier_h + gap)
        tints = ["#E6F0FF", "#F0F5FF", "#F5F8FF", "#F8FAFF", "#FBFCFF"]
        fill = tints[min(i, len(tints) - 1)]
        parts.append(f"<rect x='0' y='{y}' width='{svg_w}' height='{tier_h}' rx='12' fill='{fill}' />")
        m = max(len(mods), 1)
        inner_pad = 16
        mod_gap = 12
        cw = (svg_w - inner_pad * 2 - (m - 1) * mod_gap) / m
        for j, mod in enumerate(mods or [""]):
            x = inner_pad + j * (cw + mod_gap)
            hero = (i == 0 and j == 0)
            fill2 = P["primary"] if hero else "#FFFFFF"
            fg = "#FFFFFF" if hero else P["primary_dark"]
            parts.append(f"<rect x='{x:.1f}' y='{y + 13}' width='{cw:.1f}' "
                         f"height='{box_h}' rx='8' fill='{fill2}' />")
            parts.append(f"<text x='{x + cw / 2:.1f}' y='{y + 13 + box_h / 2 + 6:.1f}' fontSize='14' "
                         f"fill='{fg}' textAnchor='middle'>{mod}</text>")
        # 层间下行箭头（三角箭头，比 12px 竖线更可读，不会看成杂点）
        if i < n - 1:
            ay = y + tier_h + 1
            mid = svg_w / 2
            parts.append(f"<line x1='{mid:.0f}' y1='{ay:.0f}' x2='{mid:.0f}' "
                         f"y2='{ay + gap - 8:.0f}' stroke='{P['primary']}' strokeWidth='2.5' />")
            parts.append(f"<polygon points='{mid:.0f},{ay + gap:.0f} "
                         f"{mid - 6:.0f},{ay + gap - 8:.0f} {mid + 6:.0f},{ay + gap - 8:.0f}' "
                         f"fill='{P['primary']}' />")
    figure = _svg(svg_w, h, "".join(parts))
    left = (f"<Box {bs(width=150, flexShrink=0, flexDirection='column', gap=gap)}>"
            + "".join(f"<Box {bs(height=tier_h, justifyContent='center')}>"
                      f"<Text {ts(fontSize=15, fontWeight='bold', color=P['primary_deep'], lineHeight=1.3)}>{nm}</Text>"
                      f"</Box>" for nm, _ in tiers)
            + "</Box>")
    return (f"<Box {bs(flex=1, flexDirection='column', justifyContent='center', minHeight=0)}>"
            f"<Box {bs(flexDirection='row', gap=18, alignItems='flex-start')}>{left}{figure}</Box>"
            f"</Box>")


def flow_branch(nodes, width=CW, node_h=96):
    """流程图（带判定分支）：SVG 画「节点 + 菱形判定 + 是/否 分支箭头」。

    nodes: [(标题, 说明, 类型)]，类型 ∈ {'step','decision','end'}。
    主链横向排列；decision 之后引出下方「否」回环支线。
    - 节点标题写进 SVG（`_svg` 已挂 FONT_STACK）；下方一行只放说明，避免上下重复。
    - 判定菱形用 `rot=-90`（`rot=-45` 会渲染成轴对齐正方形，实测踩过）。
    - `h` 按「节点高 + 回环深度」动态算，不再写死 300——写死会让图形与说明之间
      留出 ~140px 空洞（实测观感失败）。
    """
    n = len(nodes)
    w = width - 6
    gap = 30
    drop = 60                     # 「否」回环下折深度
    h = node_h + drop + 6
    cw = (w - (n - 1) * gap) / n
    r = node_h * 0.52             # 菱形半径 → 菱形宽高 ≈ node_h
    parts = []
    edges = []                    # 每个节点的 (左界, 右界)，用于精确连线
    for i, (title, _desc, kind) in enumerate(nodes):
        x = i * (cw + gap)
        cx = x + cw / 2
        cy = node_h / 2
        if kind == "decision":
            parts.append(f"<polygon points='{_poly_pts(4, cx, cy, r)}' fill='{P['primary']}' />")
            edges.append((cx - r, cx + r))
            parts.append(f"<text x='{cx:.1f}' y='{cy + 6:.1f}' fontSize='15' "
                         f"fill='#FFFFFF' textAnchor='middle'>{title}</text>")
        elif kind == "end":
            parts.append(f"<rect x='{x}' y='0' width='{cw:.1f}' height='{node_h}' "
                         f"rx='{node_h / 2:.0f}' fill='{P['primary_deep']}' />")
            edges.append((x, x + cw))
            parts.append(f"<text x='{cx:.1f}' y='{cy + 6:.1f}' fontSize='15' "
                         f"fill='#FFFFFF' textAnchor='middle'>{title}</text>")
        else:
            parts.append(f"<rect x='{x}' y='0' width='{cw:.1f}' height='{node_h}' rx='12' "
                         f"fill='{P['icon_bg']}' />")
            edges.append((x, x + cw))
            parts.append(f"<text x='{cx:.1f}' y='{cy + 6:.1f}' fontSize='15' "
                         f"fill='{P['primary_deep']}' textAnchor='middle'>{title}</text>")
    # 主链连线（按节点真实边界，菱形不会被线穿进去）
    for i in range(n - 1):
        x1 = edges[i][1]
        x2 = edges[i + 1][0]
        if x2 - x1 > 4:
            parts.append(f"<line x1='{x1:.1f}' y1='{node_h / 2:.0f}' x2='{x2:.1f}' "
                         f"y2='{node_h / 2:.0f}' stroke='{P['primary']}' strokeWidth='3' />")
    # 判定后的「否」支线（下折回环）
    dec_idx = next((i for i, nd in enumerate(nodes) if nd[2] == "decision"), None)
    if dec_idx is not None:
        dx = dec_idx * (cw + gap) + cw / 2
        dy = node_h / 2 + r
        y1 = node_h + drop
        parts.append(f"<line x1='{dx:.0f}' y1='{dy:.0f}' x2='{dx:.0f}' y2='{y1:.0f}' "
                     f"stroke='{P['text_muted']}' strokeWidth='2.5' />")
        parts.append(f"<line x1='{dx:.0f}' y1='{y1:.0f}' x2='6' y2='{y1:.0f}' "
                     f"stroke='{P['text_muted']}' strokeWidth='2.5' />")
        parts.append(f"<line x1='6' y1='{y1:.0f}' x2='6' y2='{node_h / 2:.0f}' "
                     f"stroke='{P['text_muted']}' strokeWidth='2.5' />")
        parts.append(f"<text x='{dx - 22:.0f}' y='{y1 - 9:.0f}' fontSize='13' "
                     f"fill='{P['text_muted']}' textAnchor='end'>否</text>")
    figure = _svg(w, h, "".join(parts))
    descs = (f"<Box {bs(flexDirection='row', gap=gap, width='100%', marginTop=4)}>"
             + "".join(f"<Box {bs(flex=1, flexDirection='column', gap=3, alignItems='center', textAlign='center')}>"
                       f"<Text {ts(fontSize=13, color=P['text_sub'], lineHeight=1.45)}>{d}</Text>"
                       f"</Box>" for _t, d, _k in nodes)
             + "</Box>")
    # 不再生成「图例行」：它和页面底部的收束行语义完全重复，两行贴在一起反而显乱
    # （实测：说明行 + 图例行挤成一个噪点带）。形状含义交给页面收束行一句话讲完。
    return (f"<Box {bs(flex=1, flexDirection='column', justifyContent='center', minHeight=0)}>"
            f"{figure}{descs}</Box>")


# ============================================================
# 4. 代码块
# ============================================================
def code_block(code, language="bash", width=1000, font_size=15, theme="github-dark"):
    """代码块：CodeBlock 组件（macOS 三色点 + 语法高亮）。

    注意：code 用 JSX 模板字符串传入，内部反引号与 ${} 需避免。
    """
    safe = code.replace("`", "'").replace("${", "$ {")
    return (f"<CodeBlock\ncode={{`{safe}`}}\nlanguage='{language}'\n"
            f"width={{{width}}}\nfontSize={{{font_size}}}\ntheme='{theme}'\n/>")


# ============================================================
# 5. 多样化表格（真 Table 组件）
# ============================================================
def _cell(text, bold=False, color=None, bg=None, size=16):
    parts = [f"text: '{text}'"]
    tstyle = []
    if bold:
        tstyle.append("bold: true")
    if color:
        tstyle.append(f"color: '{color}'")
    if tstyle:
        parts.append("textStyle: { " + ", ".join(tstyle) + " }")
    if bg:
        parts.append("cellStyle: { background: { color: '" + bg + "' } }")
    return "{ " + ", ".join(parts) + " }"


def score_table(rows, col_titles, recommended=1, title_row=("评估维度",), height=390):
    """能力打分表：✓ / ✗ / ★ 符号化 + 推荐列高亮（Table 组件）。

    rows: [(维度, [各列取值字符串...]), ...]；取值建议用 '✓' '✗' '★★★' '$$' '6个月' 等短符号。
    col_titles: 参与对比的方案名（不含首列维度列）。
    recommended: 推荐列索引（0 基，相对 col_titles），该列整列 tint 高亮。
    """
    head = [ _cell(title_row[0], bold=True, color="#FFFFFF", bg=P["primary_deep"]) ]
    for i, ct in enumerate(col_titles):
        bg = P["primary"] if i == recommended else P["primary_deep"]
        label = ct + ("  ★推荐" if i == recommended else "")
        head.append(_cell(label, bold=True, color="#FFFFFF", bg=bg))
    body = []
    for r_i, (dim, vals) in enumerate(rows):
        zebra = P["surface_alt"] if r_i % 2 else "#FFFFFF"
        line = [ _cell(dim, bold=True, color=P["primary_deep"], bg=zebra) ]
        for c_i, v in enumerate(vals):
            if c_i == recommended:
                line.append(_cell(v, bold=True, color=P["primary"], bg=P["icon_bg"]))
            else:
                color = P["text_muted"] if v.strip() in ("✗", "无", "-") else P["text_sub"]
                line.append(_cell(v, color=color, bg=zebra))
        body.append(line)
    rows_jsx = ",\n  ".join("[" + ", ".join(r) + "]" for r in [head] + body)
    return f"""<Table
style={{{{ width: '100%', height: {height} }}}}
defaultTextStyle={{{{ fontSize: 16, textAlign: 'center', color: '{P['text_main']}' }}}}
defaultCellStyle={{{{ border: {{ bottom: {{ width: 1, color: '{P['divider']}' }} }} }}}}
cells={{[
  {rows_jsx}
]}}
/>"""


def compare_matrix(headers, rows, highlight_col=None, height=390):
    """多维对比表：表头深底 + 斑马纹 + 可选高亮列（Table 组件）。

    headers: ['对比维度', '市面工具', 'ppt-polish']；rows: [[维度, 值1, 值2], ...]。
    """
    head = []
    for i, h in enumerate(headers):
        if i == 0:
            head.append(_cell(h, bold=True, color="#FFFFFF", bg=P["primary_deep"]))
        elif highlight_col is not None and i == highlight_col:
            head.append(_cell(h, bold=True, color="#FFFFFF", bg=P["primary"]))
        else:
            head.append(_cell(h, bold=True, color="#FFFFFF", bg=P["primary_deep"]))
    body = []
    for r_i, row in enumerate(rows):
        zebra = P["surface_alt"] if r_i % 2 else "#FFFFFF"
        line = []
        for c_i, v in enumerate(row):
            if c_i == 0:
                line.append(_cell(v, bold=True, color=P["primary_deep"], bg=zebra))
            elif highlight_col is not None and c_i == highlight_col:
                line.append(_cell(v, bold=True, color=P["primary"], bg=P["icon_bg"]))
            else:
                line.append(_cell(v, color=P["text_sub"], bg=zebra))
        body.append(line)
    rows_jsx = ",\n  ".join("[" + ", ".join(r) + "]" for r in [head] + body)
    return f"""<Table
style={{{{ width: '100%', height: {height} }}}}
defaultTextStyle={{{{ fontSize: 16, textAlign: 'center', color: '{P['text_main']}' }}}}
defaultCellStyle={{{{ border: {{ bottom: {{ width: 1, color: '{P['divider']}' }} }} }}}}
cells={{[
  {rows_jsx}
]}}
/>"""


# ============================================================
# 6. 留白区装饰（低语义 SVG；装饰面积须 ≤ 内容区 25%）
# ============================================================
def decor_corner(size=190, opacity=0.5):
    """角部几何纹样装饰（低语义）：同心弧 + 点阵，放留白角。"""
    c = []
    for i, r in enumerate((size * 0.42, size * 0.30, size * 0.18)):
        c.append(f"<circle cx='{size}' cy='0' r='{r:.0f}' fill='none' "
                 f"stroke='{P['primary']}' strokeWidth='{3 if i == 0 else 2}' opacity='{opacity}' />")
    for i in range(3):
        for j in range(3):
            c.append(f"<circle cx='{28 + j * 20}' cy='{size - 34 + i * 12}' r='3' "
                     f"fill='{P['primary']}' opacity='{opacity}' />")
    return _svg(size, size, "".join(c))


def decor_ring(pct=72, size=180, label=""):
    """进度环装饰（低语义）：承载一个百分比，兼具叙事功能。"""
    r = size * 0.42
    cx = cy = size / 2
    circ = 2 * math.pi * r
    dash = circ * pct / 100.0
    c = [
        f"<circle cx='{cx}' cy='{cy}' r='{r:.1f}' fill='none' stroke='#E6F0FF' strokeWidth='16' />",
        f"<circle cx='{cx}' cy='{cy}' r='{r:.1f}' fill='none' stroke='{P['primary']}' "
        f"strokeWidth='16' strokeDasharray='{dash:.1f} {circ - dash:.1f}' "
        f"strokeLinecap='round' transform='rotate(-90 {cx} {cy})' />",
        f"<text x='{cx}' y='{cy + 10}' fontSize='34' fill='{P['primary_deep']}' "
        f"textAnchor='middle'>{pct}%</text>",
    ]
    return _svg(size, size, "".join(c))


def decor_dotgrid(cols=10, rows=5, cell=16, opacity=0.55):
    """点阵装饰（低语义）：铺在留白区做节奏，禁止压住正文。"""
    c = []
    for r in range(rows):
        for cc in range(cols):
            c.append(f"<circle cx='{8 + cc * cell}' cy='{8 + r * cell}' r='2.5' "
                     f"fill='{P['primary']}' opacity='{opacity}' />")
    return _svg(8 * 2 + (cols - 1) * cell, 8 * 2 + (rows - 1) * cell, "".join(c))


def side_image_band(text_title, text_desc, band_svg, band_w=330):
    """侧栏装饰图带：一侧低语义装饰带（SVG），一侧正文。

    受占比约束：装饰带宽度 ≤ 内容区 30%，且不连续两页都用。
    """
    return (f"<Box {bs(flex=1, flexDirection='row', gap=26, alignItems='stretch', minHeight=0)}>"
            f"<Box {bs(flex=1, flexDirection='column', gap=10, justifyContent='center')}>"
            f"<Text {ts(fontSize=22, fontWeight='bold', color=P['primary_deep'], lineHeight=1.3)}>{text_title}</Text>"
            f"<Text {ts(fontSize=15, color=P['text_sub'], lineHeight=1.7)}>{text_desc}</Text>"
            f"</Box>"
            f"<Box {bs(width=band_w, flexShrink=0, justifyContent='center', alignItems='center')}>"
            f"{band_svg}</Box>"
            f"</Box>")


def kv_metric_row(metrics, metric_size=40):
    """关键指标行：大数字锚点 + 标签 + 说明（数字级视觉锚点）。

    metrics: [(数值, 标签, 说明), ...]
    """
    cells = []
    for v, label, desc in metrics:
        cells.append(f"<Box {bs(flex=1, flexDirection='column', gap=6, alignItems='center', textAlign='center', padding='16px 10px')}>"
                     f"<Text {ts(fontSize=metric_size, fontWeight='bold', color=P['primary'], lineHeight=1.05)}>{v}</Text>"
                     f"<Text {ts(fontSize=15, fontWeight='bold', color=P['primary_deep'])}>{label}</Text>"
                     f"<Text {ts(fontSize=12, color=P['text_muted'], lineHeight=1.4)}>{desc}</Text>"
                     f"</Box>")
    return f"<Box {bs(flexDirection='row', gap=10, alignItems='stretch')}>{''.join(cells)}</Box>"


def pull_quote(quote, author, accent_svg=None):
    """引文块：大号引文 + 出处；用于利用留白、打破页面节奏。"""
    fig = (_boxtag(width=110, flexShrink=0, justifyContent="center", alignItems="center")
           + accent_svg + "</Box>") if accent_svg else ""
    return (_boxtag(flexDirection="row", gap=26, alignItems="center", padding="26px 30px",
                    background=P["surface_alt"], borderRadius=14)
            + fig
            + f"<Box {bs(flex=1, flexDirection='column', gap=12)}>"
            f"<Text {ts(fontSize=23, color=P['primary_deep'], lineHeight=1.6)}>{quote}</Text>"
            f"<Text {ts(fontSize=13, color=P['text_muted'])}>{author}</Text>"
            f"</Box></Box>")
