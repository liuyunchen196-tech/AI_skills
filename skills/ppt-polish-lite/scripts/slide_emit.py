#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
slide_emit.py —— 内容 → slidep JSX DSL (.slide) 路由引擎。

输入: 内容 dict { title, subtitle, items, layout } + 可选 layout 覆盖
输出: .slide 文件路径（合法 JSX，可直接给 slidep lint / upsert-dsl）

设计规则（v3 方案 §4）:
- 零 AI 味元素: 不写色条/竖条/下划线/单边框/滥用阴影
- 用背景 tint + 圆形色底图标 + 字号尺度对比建立层次
- 配色: 默认科技蓝调色板（可被 palette 覆盖）
- 字号: 大标题 36 / 副标 16 / 卡标题 18 / 副标 13 / 页脚 12

版式目录:
- comparison 双栏对比（左灰色 + 右蓝色 tint）
- icon-grid-2x3 6 点 2×3 网格（每卡：圆底图标 + 标题 + 副标）
- icon-grid-3x2 6-9 点 3 列横排
- kpi-grid-6 6 个 KPI 大数字卡
- flow-timeline 横向流程卡 + 箭头
- list-icon 图标 + 文字行列表（4-7 项）
- diagram 节点-连线图示（吃 graph/nodes+edges，自动判 tree/flow/grid）
"""

import re
from pathlib import Path
from typing import Optional


# ============================================================
# 调色板：默认科技蓝（参考 deck 与 蓝族）
# ============================================================
DEFAULT_PALETTE = {
    "primary": "#1677FF",
    "primary_deep": "#0B3A8C",
    "primary_dark": "#1F2937",
    "accent_tint": "#F0F5FF",
    "icon_bg": "#E6F0FF",
    "icon_fill": "#1677FF",
    "text_main": "#1F2937",
    "text_sub": "#4B5563",
    "text_muted": "#9CA3AF",
    "divider": "#E5E7EB",
    "surface": "#FFFFFF",
    "surface_alt": "#F8FAFF",
    "compare_left_bg": "#F3F4F6",
    "compare_right_bg": "#E6F0FF",
    "compare_right_border": "#1677FF",
    "font_family": '"微软雅黑", "PingFang SC", "Microsoft YaHei", sans-serif',
}


def _make_palette(primary, primary_deep, tint, icon_bg, font_family=None):
    """从 4 个核心色生成完整色板（中性色保持统一）。"""
    return {
        "primary": primary,
        "primary_deep": primary_deep,
        "primary_dark": primary_deep,
        "accent_tint": tint,
        "icon_bg": icon_bg,
        "icon_fill": primary,
        "text_main": "#1F2937",
        "text_sub": "#4B5563",
        "text_muted": "#9CA3AF",
        "divider": "#E5E7EB",
        "surface": "#FFFFFF",
        "surface_alt": "#F8FAFF",
        "compare_left_bg": "#F3F4F6",
        "compare_right_bg": tint,
        "compare_right_border": primary,
        "font_family": font_family or '"微软雅黑", "PingFang SC", "Microsoft YaHei", sans-serif',
    }


# v3.2: 10 组命名色板 + 科技蓝 = 11 组
PALETTES = {
    # 默认科技蓝（v3.0 原有）
    "tech-blue": DEFAULT_PALETTE,

    # 10 组
    "midnight-executive": _make_palette("#1E2761", "#0A1428", "#E8EAF0", "#D1D5E8"),
    "forest-moss": _make_palette("#2C5F2D", "#1A3A1B", "#EDF5ED", "#D5E8D5"),
    "coral-energy": _make_palette("#F96167", "#8B2D33", "#FFF0F0", "#FFDADA"),
    "warm-terracotta": _make_palette("#B85042", "#6B2D24", "#F9F0EE", "#E8D5D0"),
    "ocean-gradient": _make_palette("#065A82", "#022E48", "#E8F4FA", "#CFE8F5"),
    "charcoal-minimal": _make_palette("#36454F", "#1A2026", "#F0F0F2", "#E2E2E5"),
    "teal-trust": _make_palette("#028090", "#014550", "#E0F7F7", "#C5EDED"),
    "berry-cream": _make_palette("#6D2E46", "#3D1A28", "#F5EBF0", "#E8D5DD"),
    "sage-calm": _make_palette("#84B59F", "#4A6648", "#EFF5F0", "#DCE8DE"),
    "cherry-bold": _make_palette("#990011", "#4D0009", "#FFF0F2", "#FFD5DA"),
}


def resolve_palette(palette) -> dict:
    """palette 参数支持：色板名字符串 / dict / None。"""
    if palette is None:
        return DEFAULT_PALETTE
    if isinstance(palette, str):
        return PALETTES.get(palette, DEFAULT_PALETTE)
    # dict：合并到 DEFAULT_PALETTE（允许部分覆盖）
    result = dict(DEFAULT_PALETTE)
    result.update(palette)
    return result


# ============================================================
# 图标映射（Font Awesome 5 名）
# 顺序敏感: 更长 / 更精确的关键词放前面, 避免短词被误命中
# ============================================================
ICON_KEYWORDS = {
    # 文档类（精确词在前）
    "ppt|演示|幻灯片": "file-powerpoint",
    "pdf|word|excel|表格": "file-alt",
    "文档|解析|抽取": "file-text",
    "图片|图像|ocr|拍照|识别": "file-image",
    # 协作 / 多智能体（去掉 "编排"，让 "编排" 专属流程类）
    "多智能体|agent|团队|群|角色|成员|权限": "users",
    "协作|协同|合作": "handshake",
    # 检索 / 知识 / 选型（"选型|验证"归这里，与搜索同语义）
    "知识库|检索|搜索|问答|选型|验证|poc|评估|测试": "search",
    "数据库|存储": "database",
    # 流程 / 自动化（"编排" "工作流" "自动化" "流程" 全部归这里）
    "工作流|自动化|流程|定时|齿轮|流水线|编排": "cog",
    "同步|联动|对接": "sync",
    # 盘点 / 清单 / 梳理（在"步骤"前匹配，否则"需求盘点"会 fallback 到 check-circle）
    "盘点|清单|梳理|整理|需求": "clipboard",
    # 数据 / 图表（"复盘|推广"归 chart-line，与"趋势"同语义）
    "看板|报表|图表|统计|可视化|数据|指标": "chart-bar",
    "趋势|折线|走势|复盘|推广|规模化|扩张": "chart-line",
    # 接口 / 连接
    "连接器|api|集成|开放接口": "plug",
    "对接企业|外部系统|第三方": "external-link-alt",
    "分享|共享|分发": "share",
    # 其他常见
    "步骤|阶段|节点|里程碑": "check-circle",
    "建议|提示|想法|灵感": "lightbulb",
    "安全|加密|防护|风控": "shield",
    "速度|高效|加速|毫秒": "bolt",
    # 上线 / 部署 / 发布（"上线|灰度"归 rocket，与"创新|首发"同语义）
    "创新|首发|首发版本|上线|灰度|部署|发布|launch": "rocket",
    "目标|精准|定位|瞄准": "bullseye",
    "配置|设置|参数": "sliders-h",
    "监控|实时|观察": "eye",
    "时间|历史|日期": "clock",
    "模型|训练|学习": "brain",
    "语音|音频|声音": "volume-up",
    "视频|影像|动画": "video",
    "代码|编程|开发|脚本": "code",
}


def icon_for(text: str) -> str:
    if not text:
        return "check-circle"
    for pattern, icon in ICON_KEYWORDS.items():
        if re.search(pattern, text, re.IGNORECASE):
            return icon
    return "check-circle"


# ============================================================
# JSX 工具函数（关键：避免 f-string 吃花括号）
# ============================================================
def bs(**kwargs) -> str:
    """生成 box style 对象字符串（无 fontSize/color 默认值）。

    返回 'style={{ width: 1280, ... }}'，其中 {{ 和 }} 是字面量，
    在 f-string 中通过 {bs(...)} 插入，f-string 只插值调用结果，不会再转义。
    """
    parts = []
    for k, v in kwargs.items():
        if isinstance(v, str):
            parts.append(f"{k}: '{v}'")
        elif isinstance(v, bool):
            parts.append(f"{k}: {'true' if v else 'false'}")
        else:
            parts.append(f"{k}: {v}")
    return "style={{ " + ", ".join(parts) + " }}"


def ts(fontSize=None, color=None, **kwargs) -> str:
    """生成 text style 对象字符串。fontSize/color 不传则不输出。"""
    parts = []
    if fontSize is not None:
        parts.append(f"fontSize: {fontSize}")
    if color is not None:
        parts.append(f"color: '{color}'")
    for k, v in kwargs.items():
        if isinstance(v, str):
            parts.append(f"{k}: '{v}'")
        elif isinstance(v, bool):
            parts.append(f"{k}: {'true' if v else 'false'}")
        else:
            parts.append(f"{k}: {v}")
    return "style={{ " + ", ".join(parts) + " }}"


def esc(text: str) -> str:
    if text is None:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ============================================================
# 公共片段：标题区 / 页脚 / 卡片单元
# ============================================================
def header(title: str, subtitle: str = "", p: dict = None) -> str:
    """顶部标题块（A 区）。"""
    p = p or DEFAULT_PALETTE
    sub_block = ""
    if subtitle:
        sub_block = f"""
<Text {ts(fontSize=16, color=p['text_muted'], lineHeight=1.4)}>
{esc(subtitle)}
</Text>"""
    return f"""
<Box {bs(flexDirection='column', gap=8)}>
<Text {ts(fontSize=36, fontWeight='bold', color=p['primary_deep'], lineHeight=1.2)}>
{esc(title)}
</Text>{sub_block}
</Box>"""


def footer(p: dict = None, left: str = "WorkBuddy · 办公实战平台", page: str = "01 / 01") -> str:
    p = p or DEFAULT_PALETTE
    return f"""
<Box {bs(flexDirection='row', justifyContent='space-between', alignItems='center', marginTop=28)}>
<Text {ts(fontSize=12, color=p['text_muted'])}>{esc(left)}</Text>
<Text {ts(fontSize=12, color=p['text_muted'])}>{esc(page)}</Text>
</Box>"""


def icon_circle(icon_name: str, p: dict, size: int = 48, icon_size: int = 24) -> str:
    """圆形色底图标。"""
    return f"""
<Box {bs(width=size, height=size, borderRadius=size // 2, background=p['icon_bg'], justifyContent='center', alignItems='center')}>
<FAIcon name='{icon_name}' {bs(fill=p['icon_fill'], width=icon_size, height=icon_size)} />
</Box>"""


def card_block(title: str, desc: str, icon_name: str, p: dict,
               bg: str = None, padding: str = "28px 24px", gap: int = 12) -> str:
    """单个卡片：圆底图标 + 标题 + 副标。"""
    bg = bg or p["accent_tint"]
    return f"""
<Box {bs(flex=1, background=bg, borderRadius=12, padding=padding, flexDirection='column', gap=gap)}>{icon_circle(icon_name, p)}
<Text {ts(fontSize=18, fontWeight='bold', color=p['text_main'], lineHeight=1.3)}>
{esc(title)}
</Text>
<Text {ts(fontSize=13, color=p['text_sub'], lineHeight=1.5)}>
{esc(desc)}
</Text>
</Box>"""


# ============================================================
# 版式 builder
# ============================================================
def _row(cards: list, gap: int = 24, height: int = 220) -> str:
    """横向一行卡片（flex: 1 等分）。"""
    inner = ",".join(cards)
    return f"""
<Box {bs(flexDirection='row', gap=gap, height=height)}>
{inner}
</Box>"""


def build_grid_2x3(items: list, title: str, subtitle: str, p: dict = None,
                    row_height: int = 220, gap: int = 24, page_label: str = "01 / 01") -> str:
    """6 点 2×3 网格。"""
    p = p or DEFAULT_PALETTE
    if len(items) < 6:
        items = items + [{"title": "", "desc": ""}] * (6 - len(items))
    items = items[:6]
    cards = [
        card_block(
            it.get("title", ""), it.get("desc", ""),
            it.get("icon") or icon_for(it.get("title", "")),
            p,
        )
        for it in items
    ]
    row1 = _row(cards[:3], gap=gap, height=row_height)
    row2 = _row(cards[3:], gap=gap, height=row_height)
    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='column', gap=gap, marginTop=36)}>{row1}{row2}
</Box>
{footer(p, page=page_label)}
</Slide>"""


def build_comparison(left_title: str, right_title: str, left_items: list, right_items: list,
                      page_title: str, page_subtitle: str = "", p: dict = None,
                      page_label: str = "01 / 01") -> str:
    """双栏对比（左灰色 tint vs 右蓝色 tint）。"""
    p = p or DEFAULT_PALETTE

    def render_col(items, bg, col_title):
        lines = []
        for it in items:
            title = it.get("title", "") if isinstance(it, dict) else str(it)
            desc = it.get("desc", "") if isinstance(it, dict) else ""
            desc_block = f'<Text {ts(fontSize=12, color=p["text_sub"], lineHeight=1.5)}>{esc(desc)}</Text>' if desc else ""
            lines.append(f"""
<Box {bs(flexDirection='row', gap=10, alignItems='flex-start')}>
<Box {bs(width=6, height=6, borderRadius=3, background=p['primary'], marginTop=8, flexShrink=0)} />
<Box {bs(flex=1, flexDirection='column', gap=4)}>
<Text {ts(fontSize=15, fontWeight='bold', color=p['text_main'], lineHeight=1.4)}>{esc(title)}</Text>
{desc_block}
</Box>
</Box>""")
        items_block = ",".join(lines)
        return f"""
<Box {bs(flex=1, background=bg, borderRadius=12, padding='32px 28px', flexDirection='column', gap=20)}>
<Text {ts(fontSize=20, fontWeight='bold', color=p['text_main'], lineHeight=1.3)}>{esc(col_title)}</Text>
<Box {bs(flexDirection='column', gap=16)}>
{items_block}
</Box>
</Box>"""

    left_col = render_col(left_items, p["compare_left_bg"], left_title)
    right_col = render_col(right_items, p["compare_right_bg"], right_title)
    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(page_title, page_subtitle, p)}

<Box {bs(flexDirection='row', gap=32, marginTop=32, flex=1, alignItems='stretch')}>
{left_col}
{right_col}
</Box>
{footer(p, page=page_label)}
</Slide>"""


def build_flow_timeline(items: list, title: str, subtitle: str, p: dict = None,
                         page_label: str = "01 / 01") -> str:
    """横向流程卡（4-5 步）。"""
    p = p or DEFAULT_PALETTE
    n = min(len(items), 5)

    def step_card(it, idx):
        icon = it.get("icon") or icon_for(it.get("title", ""))
        return f"""
<Box {bs(flex=1, background=p['accent_tint'], borderRadius=12, padding='28px 20px', flexDirection='column', gap=14, justifyContent='flex-start')}>
<Text {ts(fontSize=13, fontWeight='bold', color=p['primary'])}>STEP {idx + 1:02d}</Text>
{icon_circle(icon, p, size=40, icon_size=20)}
<Text {ts(fontSize=17, fontWeight='bold', color=p['text_main'], lineHeight=1.3)}>
{esc(it.get('title', ''))}
</Text>
<Text {ts(fontSize=12, color=p['text_sub'], lineHeight=1.5)}>
{esc(it.get('desc', ''))}
</Text>
</Box>"""

    cards = [step_card(it, i) for i, it in enumerate(items[:n])]
    flow_inner = []
    for i, c in enumerate(cards):
        flow_inner.append(c)
        if i < len(cards) - 1:
            arrow_text = "<Text " + ts(fontSize=24, color='#1677FF', fontWeight='bold') + ">{'>'}</Text>"
            flow_inner.append(
                "<Box " + bs(width=24, justifyContent='center', alignItems='center') + ">"
                + arrow_text + "</Box>"
            )
    flow_row = ",".join(flow_inner)
    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='row', gap=12, marginTop=56, alignItems='stretch', height=380)}>
{flow_row}
</Box>
{footer(p, page=page_label)}
</Slide>"""


def build_list_icon(items: list, title: str, subtitle: str, p: dict = None,
                     page_label: str = "01 / 01") -> str:
    """图标 + 文字行列表（4-7 项）。"""
    p = p or DEFAULT_PALETTE

    def row_block(it):
        icon = it.get("icon") or icon_for(it.get("title", ""))
        return f"""
<Box {bs(flexDirection='row', gap=20, alignItems='flex-start', padding='20px 24px', background=p['accent_tint'], borderRadius=12)}>
{icon_circle(icon, p, size=48, icon_size=24)}
<Box {bs(flex=1, flexDirection='column', gap=6)}>
<Text {ts(fontSize=18, fontWeight='bold', color=p['text_main'], lineHeight=1.3)}>
{esc(it.get('title', ''))}
</Text>
<Text {ts(fontSize=14, color=p['text_sub'], lineHeight=1.5)}>
{esc(it.get('desc', ''))}
</Text>
</Box>
</Box>"""

    rows = [row_block(it) for it in items]
    rows_block = ",".join(rows)
    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='column', gap=14, marginTop=36)}>
{rows_block}
</Box>
{footer(p, page=page_label)}
</Slide>"""


def build_kpi_grid(items: list, title: str, subtitle: str, p: dict = None,
                    page_label: str = "01 / 01") -> str:
    """6 个 KPI 大数字卡。"""
    p = p or DEFAULT_PALETTE
    if len(items) < 6:
        items = items + [{"label": "", "value": "", "delta": ""}] * (6 - len(items))
    items = items[:6]

    def kpi_card(it):
        return f"""
<Box {bs(flex=1, background=p['accent_tint'], borderRadius=12, padding='24px 22px', flexDirection='column', gap=8, justifyContent='space-between')}>
<Text {ts(fontSize=13, color=p['text_muted'])}>{esc(it.get('label', ''))}</Text>
<Text {ts(fontSize=44, fontWeight='bold', color=p['primary_deep'], lineHeight=1.1)}>
{esc(it.get('value', ''))}
</Text>
<Text {ts(fontSize=12, color=p['text_sub'])}>{esc(it.get('delta', ''))}</Text>
</Box>"""

    cards = [kpi_card(it) for it in items]
    row1 = _row(cards[:3], gap=20, height=210)
    row2 = _row(cards[3:], gap=20, height=210)
    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='column', gap=20, marginTop=36)}>{row1}{row2}
</Box>
{footer(p, page=page_label)}
</Slide>"""


# ============================================================
# v3.1 新增版式（5 个）
# ============================================================
def _jsx_array(data) -> str:
    """把 Python 嵌套数组/标量转成 JSX 字面量（用于 Chart 的 data 属性）。"""
    if isinstance(data, list):
        return "[" + ", ".join(_jsx_array(item) for item in data) + "]"
    if isinstance(data, str):
        return f"'{data}'"
    if isinstance(data, bool):
        return "true" if data else "false"
    return str(data)


def build_stat_callout(content: dict, p: dict = None, page_label: str = "01 / 01") -> str:
    """大数字 callout：单页一个巨型数字 + 标签 + 描述 + 来源。"""
    p = p or DEFAULT_PALETTE
    title = content.get("title", "")
    subtitle = content.get("subtitle", "")
    stat_label = content.get("stat_label", "")
    stat_value = content.get("stat_value", "")
    stat_desc = content.get("stat_desc", "")
    source = content.get("source", "数据来源：内部统计")

    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flex=1, flexDirection='column', justifyContent='center', alignItems='center', marginTop=20)}>
<Text {ts(fontSize=16, color=p['text_muted'], textAlign='center')}>{esc(stat_label)}</Text>
<Text {ts(fontSize=120, fontWeight='bold', color=p['primary'], lineHeight=1.0, textAlign='center')}>
{esc(stat_value)}
</Text>
<Text {ts(fontSize=20, color=p['text_sub'], marginTop=16, textAlign='center', lineHeight=1.5)}>
{esc(stat_desc)}
</Text>
</Box>

<Box {bs(flexDirection='row', justifyContent='space-between', alignItems='center', marginTop=28)}>
<Text {ts(fontSize=12, color=p['text_muted'])}>{esc(source)}</Text>
<Text {ts(fontSize=12, color=p['text_muted'])}>{esc(page_label)}</Text>
</Box>
</Slide>"""


def build_chart_page(content: dict, p: dict = None, page_label: str = "01 / 01") -> str:
    """数据图表页：左 Chart + 右洞察文字。"""
    p = p or DEFAULT_PALETTE
    title = content.get("title", "")
    subtitle = content.get("subtitle", "")
    chart_type = content.get("chart_type", "barChart")
    chart_data = content.get("chart_data", [["类别", "数值"], ["A", 10]])
    chart_colors = content.get("chart_colors", [p["primary"]])
    insight_title = content.get("insight_title", "核心洞察")
    insight_desc = content.get("insight_desc", "")

    data_jsx = _jsx_array(chart_data)
    colors_jsx = _jsx_array(chart_colors)
    bar_dir = ""
    if chart_type == "barChart":
        bar_dir = content.get("bar_direction", "column")
        bar_dir_attr = f" barDirection='{bar_dir}'"
    else:
        bar_dir_attr = ""

    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='row', gap=32, marginTop=36, height=480)}>
<Box {bs(flex=3, background=p['accent_tint'], borderRadius=12, padding=20)}>
<Chart
chartType='{chart_type}'{bar_dir_attr}
data={{ {data_jsx} }}
colors={{ {colors_jsx} }}
title=''
showLegend={{true}}
showDataLabels={{false}}
{bs(height=440, width='100%')}
legendColor='{p['text_muted']}'
axisColor='{p['text_muted']}'
/>
</Box>
<Box {bs(flex=2, flexDirection='column', gap=16, justifyContent='center')}>
<Box {bs(flexDirection='row', gap=12, alignItems='center')}>
<Box {bs(width=6, height=24, borderRadius=3, background=p['primary'])} />
<Text {ts(fontSize=20, fontWeight='bold', color=p['text_main'])}>{esc(insight_title)}</Text>
</Box>
<Text {ts(fontSize=16, color=p['text_sub'], lineHeight=1.6)}>
{esc(insight_desc)}
</Text>
</Box>
</Box>
{footer(p, page=page_label)}
</Slide>"""


def build_timeline_vertical(content: dict, p: dict = None, page_label: str = "01 / 01") -> str:
    """纵向时间轴：左时间线 + 右事件卡（3-6 个事件，行高 flex 均分自适应，防长文案溢出）。"""
    p = p or DEFAULT_PALETTE
    title = content.get("title", "")
    subtitle = content.get("subtitle", "")
    events = content.get("events", [])[:6]
    n = max(len(events), 1)
    # 事件越多字号越收敛（5-6 个事件时 desc 降为单行节奏）
    title_size = 18 if n <= 4 else 16
    desc_size = 14 if n <= 4 else 13

    def event_block(ev, idx, is_last):
        dot_line = "" if is_last else f"<Box {bs(width=2, flex=1, background=p['divider'], marginTop=4)} />"
        return f"""
<Box {bs(flex=1, flexDirection='row', gap=24)}>
<Box {bs(width=80, flexDirection='column', alignItems='center', flexShrink=0)}>
<Box {bs(width=14, height=14, borderRadius=7, background=p['primary'])} />
{dot_line}
</Box>
<Box {bs(flex=1, background=p['accent_tint'], borderRadius=12, padding='10px 20px', flexDirection='column', gap=3, justifyContent='center')}>
<Text {ts(fontSize=13, fontWeight='bold', color=p['primary'])}>{esc(ev.get('date', ''))}</Text>
<Text {ts(fontSize=title_size, fontWeight='bold', color=p['text_main'], lineHeight=1.3)}>{esc(ev.get('title', ''))}</Text>
<Text {ts(fontSize=desc_size, color=p['text_sub'], lineHeight=1.45)}>{esc(ev.get('desc', ''))}</Text>
</Box>
</Box>"""

    blocks = [event_block(ev, i, i == len(events) - 1) for i, ev in enumerate(events)]
    blocks_str = ",".join(blocks)
    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='column', gap=10, marginTop=24, flex=1)}>
{blocks_str}
</Box>
{footer(p, page=page_label)}
</Slide>"""


def build_image_text_split(content: dict, p: dict = None, page_label: str = "01 / 01") -> str:
    """图文左右分栏：左大图标/图区 + 右侧 bullet 列表（3-4 条）。"""
    p = p or DEFAULT_PALETTE
    title = content.get("title", "")
    subtitle = content.get("subtitle", "")
    icon = content.get("icon") or icon_for(title)
    bullets = content.get("bullets", content.get("items", []))[:4]

    def bullet_block(bi):
        b_icon = bi.get("icon") or icon_for(bi.get("title", ""))
        return f"""
<Box {bs(flexDirection='row', gap=16, alignItems='flex-start')}>
{icon_circle(b_icon, p, size=40, icon_size=20)}
<Box {bs(flex=1, flexDirection='column', gap=4)}>
<Text {ts(fontSize=18, fontWeight='bold', color=p['text_main'], lineHeight=1.3)}>{esc(bi.get('title', ''))}</Text>
<Text {ts(fontSize=14, color=p['text_sub'], lineHeight=1.5)}>{esc(bi.get('desc', ''))}</Text>
</Box>
</Box>"""

    bullets_str = ",".join(bullet_block(bi) for bi in bullets)
    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='row', gap=40, marginTop=40, height=460)}>
<Box {bs(flex=1, background=p['accent_tint'], borderRadius=16, justifyContent='center', alignItems='center')}>
<FAIcon name='{icon}' {bs(fill=p['primary'], width=128, height=128)} />
</Box>
<Box {bs(flex=1, flexDirection='column', gap=24, justifyContent='center')}>
{bullets_str}
</Box>
</Box>
{footer(p, page=page_label)}
</Slide>"""


def build_architecture_layers(content: dict, p: dict = None, page_label: str = "01 / 01") -> str:
    """架构分层图：多层卡片，每层内含 2-4 个项（适合系统架构/组织架构/技术栈分层）。"""
    p = p or DEFAULT_PALETTE
    title = content.get("title", "")
    subtitle = content.get("subtitle", "")
    layers = content.get("layers", [])[:5]

    def layer_block(layer, idx):
        layer_name = layer.get("name", f"Layer {idx+1}")
        items = layer.get("items", [])[:4]
        # 深浅梯度：第一层最深
        tints = ["#E6F0FF", "#F0F5FF", "#F5F8FF", "#F8FAFF", "#FBFCFF"]
        bg = tints[min(idx, len(tints) - 1)]

        def item_block(it):
            return f"""<Box {bs(flex=1, background=p['surface'], borderRadius=8, padding='10px 14px', flexDirection='column', gap=3)}>
<Text {ts(fontSize=15, fontWeight='bold', color=p['text_main'], lineHeight=1.3)}>{esc(it.get('title', ''))}</Text>
<Text {ts(fontSize=12, color=p['text_sub'], lineHeight=1.4)}>{esc(it.get('desc', ''))}</Text>
</Box>"""

        items_str = ",".join(item_block(it) for it in items)
        return f"""
<Box {bs(background=bg, borderRadius=12, padding='12px 16px', flexDirection='column', gap=8)}>
<Box {bs(flexDirection='row', gap=10, alignItems='center')}>
<Box {bs(width=6, height=20, borderRadius=3, background=p['primary'])} />
<Text {ts(fontSize=16, fontWeight='bold', color=p['primary_deep'])}>{esc(layer_name)}</Text>
</Box>
<Box {bs(flexDirection='row', gap=12)}>
{items_str}
</Box>
</Box>"""

    blocks = [layer_block(layer, i) for i, layer in enumerate(layers)]
    blocks_str = ",".join(blocks)
    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='column', gap=8, marginTop=24)}>
{blocks_str}
</Box>
{footer(p, page=page_label)}
</Slide>"""


# ============================================================
# v3.2 新增版式（5 个高优）
# ============================================================
def build_strategy_house(content: dict, p: dict = None, page_label: str = "01 / 01") -> str:
    """战略房屋：屋顶(使命) + 3-4 根柱(支柱) + 地基(赋能因素)。"""
    p = p or DEFAULT_PALETTE
    title = content.get("title", "")
    subtitle = content.get("subtitle", "")
    roof = content.get("roof", "使命与愿景")
    beam = content.get("beam", "战略目标")
    pillars = content.get("pillars", [])[:4]
    foundation_items = content.get("foundation_items", [])[:6]

    def pillar_block(pi):
        return f"""<Box {bs(flex=1, background=p['accent_tint'], borderRadius=8, padding='16px 18px', flexDirection='column', gap=6, justifyContent='center')}>
<Text {ts(fontSize=15, fontWeight='bold', color=p['text_main'], lineHeight=1.3)}>{esc(pi.get('title', ''))}</Text>
<Text {ts(fontSize=12, color=p['text_sub'], lineHeight=1.4)}>{esc(pi.get('desc', ''))}</Text>
</Box>"""

    pillars_str = ",".join(pillar_block(pi) for pi in pillars)
    foundation_str = " ".join(f"<Text {ts(fontSize=13, color=p['text_sub'])}>{esc(fi)}</Text>" for fi in foundation_items) if foundation_items else ""

    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='column', gap=8, marginTop=28, alignItems='stretch', flex=1)}>
<Box {bs(background=p['primary_deep'], borderRadius=12, padding='16px 24px', justifyContent='center', alignItems='center')}>
<Text {ts(fontSize=18, fontWeight='bold', color='#FFFFFF')}>{esc(roof)}</Text>
</Box>
<Box {bs(background=p['primary'], borderRadius=12, padding='10px 24px', justifyContent='center', alignItems='center')}>
<Text {ts(fontSize=15, fontWeight='bold', color='#FFFFFF')}>{esc(beam)}</Text>
</Box>
<Box {bs(flexDirection='row', gap=10, flex=1)}>
{pillars_str}
</Box>
<Box {bs(background=p['icon_bg'], borderRadius=12, padding='14px 24px', flexDirection='column', gap=8)}>
<Text {ts(fontSize=14, fontWeight='bold', color=p['primary_deep'])}>赋能因素</Text>
<Box {bs(flexDirection='row', gap=20, flexWrap='wrap')}>{foundation_str}</Box>
</Box>
</Box>
{footer(p, page=page_label)}
</Slide>"""


def build_issue_tree(content: dict, p: dict = None, page_label: str = "01 / 01") -> str:
    """Issue Tree：顶部核心问题横条 + 主题色连接线分发 + 3-4 个分支列（列头卡 + 叶子实底卡），铺满全宽。"""
    p = p or DEFAULT_PALETTE
    title = content.get("title", "")
    subtitle = content.get("subtitle", "")
    root = content.get("root", "核心问题")
    metric = content.get("metric", "")
    branches = content.get("branches", [])[:4]
    n = max(len(branches), 1)
    gap = 16
    line_margin = int((1152 - gap * (n - 1)) / n / 2) # 水平分配线两端收窄至首末列中心
    line_w = 1152 - 2 * line_margin

    def leaf_card(s):
        return f"""<Box {bs(flex=1, background=p['compare_left_bg'], borderRadius=8, padding='0 16px', flexDirection='row', alignItems='center', gap=10)}>
<Box {bs(width=7, height=7, borderRadius=2, background=p['primary'], flexShrink=0)} />
<Text {ts(fontSize=13.5, color=p['text_main'], lineHeight=1.35)}>{esc(s)}</Text>
</Box>"""

    def branch_col(br):
        subs = ",".join(leaf_card(s) for s in br.get("items", [])[:3])
        return f"""<Box {bs(flex=1, flexDirection='column', gap=12)}>
<Box {bs(height=54, background=p['accent_tint'], borderRadius=8, justifyContent='center', alignItems='center')}>
<Text {ts(fontSize=15, fontWeight='bold', color=p['primary_deep'])}>{esc(br.get('title', ''))}</Text>
</Box>
{subs}
</Box>"""

    metric_text = f"<Text {ts(fontSize=28, fontWeight='bold', color='#FFFFFF')}>{esc(metric)}</Text>" if metric else ""
    stubs = ",".join(
        f"""<Box {bs(flex=1, flexDirection='column', alignItems='center')}><Box {bs(width=2, height=18, background=p['primary'])} /></Box>"""
        for _ in branches
    )
    cols = ",".join(branch_col(br) for br in branches)
    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='column', marginTop=26, flex=1)}>
<Box {bs(height=80, background=p['primary_deep'], borderRadius=12, padding='0 28px', flexDirection='row', alignItems='center', justifyContent='space-between')}>
<Text {ts(fontSize=17, fontWeight='bold', color='#FFFFFF')}>{esc(root)}</Text>
{metric_text}
</Box>
<Box {bs(flexDirection='column', alignItems='center')}>
<Box {bs(width=2, height=16, background=p['primary'])} />
<Box {bs(width=line_w, height=2, background=p['primary'])} />
</Box>
<Box {bs(flexDirection='row', gap=16)}>{stubs}</Box>
<Box {bs(flexDirection='row', gap=16, flex=1)}>{cols}</Box>
</Box>
{footer(p, page=page_label)}
</Slide>"""


def build_matrix_2x2(content: dict, p: dict = None, page_label: str = "01 / 01") -> str:
    """2×2 矩阵：四象限 + 横纵轴标。"""
    p = p or DEFAULT_PALETTE
    title = content.get("title", "")
    subtitle = content.get("subtitle", "")
    x_axis = content.get("x_axis", "低 → 高")
    y_axis = content.get("y_axis", "低 → 高")
    quadrants = content.get("quadrants", [])
    # quadrants: [{name, items:[...]}] 顺序: 左上/右上/左下/右下
    while len(quadrants) < 4:
        quadrants.append({"name": "", "items": []})

    def quad_block(qd, bg):
        items = qd.get("items", [])[:4]
        items_str = ",".join(
            f"""<Box {bs(flexDirection='row', alignItems='center', gap=8)}>
<Box {bs(width=6, height=6, borderRadius=2, background=p['primary'], flexShrink=0)} />
<Text {ts(fontSize=13, color=p['text_sub'], lineHeight=1.5)}>{esc(it)}</Text>
</Box>"""
            for it in items
        )
        return f"""<Box {bs(flex=1, background=bg, borderRadius=12, padding=20, flexDirection='column', gap=12)}>
<Text {ts(fontSize=18, fontWeight='bold', color=p['primary_deep'])}>{esc(qd.get('name', ''))}</Text>
<Box {bs(flexDirection='column', gap=10)}>{items_str}</Box>
</Box>"""

    tl = quad_block(quadrants[0], p['accent_tint'])
    tr = quad_block(quadrants[1], p['icon_bg'])
    bl = quad_block(quadrants[2], p['icon_bg'])
    br_ = quad_block(quadrants[3], p['accent_tint'])

    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='row', marginTop=32, height=480)}>
<Box {bs(width=30, flexDirection='column', justifyContent='space-around', alignItems='center', flexShrink=0)}>
<Text {ts(fontSize=12, color=p['text_muted'])}>高</Text>
<Text {ts(fontSize=12, color=p['text_muted'])}>低</Text>
</Box>
<Box {bs(flex=1, flexDirection='column', gap=12)}>
<Box {bs(flex=1, flexDirection='row', gap=12)}>{tl}{tr}</Box>
<Box {bs(flex=1, flexDirection='row', gap=12)}>{bl}{br_}</Box>
<Box {bs(flexDirection='row', justifyContent='space-between', padding='0 8px')}>
<Text {ts(fontSize=12, color=p['text_muted'])}>低</Text>
<Text {ts(fontSize=12, color=p['text_muted'])}>{esc(x_axis)}</Text>
<Text {ts(fontSize=12, color=p['text_muted'])}>高</Text>
</Box>
</Box>
</Box>
{footer(p, page=page_label)}
</Slide>"""


def build_funnel(content: dict, p: dict = None, page_label: str = "01 / 01") -> str:
    """漏斗图：4-6 层宽度递减 + 右侧转化率说明。"""
    p = p or DEFAULT_PALETTE
    title = content.get("title", "")
    subtitle = content.get("subtitle", "")
    stages = content.get("stages", [])[:6]
    insight = content.get("insight", "")

    # 深浅梯度：从 primary_deep 到 icon_bg
    colors_list = [p['primary_deep'], p['primary'], p['primary'], p['icon_bg'], p['icon_bg'], p['accent_tint']]
    widths = [700, 610, 520, 430, 340, 260]

    def stage_block(st, idx):
        bg = colors_list[min(idx, len(colors_list) - 1)]
        w = widths[min(idx, len(widths) - 1)]
        text_color = '#FFFFFF' if idx < 2 else p['text_main']
        return f"""<Box {bs(width=w, background=bg, borderRadius=8, padding='15px 24px', flexDirection='row', justifyContent='space-between', alignItems='center')}>
<Text {ts(fontSize=15, fontWeight='bold', color=text_color)}>{esc(st.get('name', ''))}</Text>
<Text {ts(fontSize=16, fontWeight='bold', color=text_color)}>{esc(st.get('value', ''))}</Text>
</Box>"""

    stages_str = ",".join(stage_block(st, i) for i, st in enumerate(stages))
    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='row', gap=32, marginTop=28, flex=1)}>
<Box {bs(flex=1, flexDirection='column', gap=8, alignItems='center', justifyContent='center')}>
{stages_str}
</Box>
<Box {bs(width=300, flexShrink=0, flexDirection='column', justifyContent='center')}>
<Box {bs(background=p['accent_tint'], borderRadius=12, padding='24px 26px', flexDirection='column', gap=14)}>
<Box {bs(flexDirection='row', gap=10, alignItems='center')}>
<Box {bs(width=6, height=24, borderRadius=3, background=p['primary'])} />
<Text {ts(fontSize=17, fontWeight='bold', color=p['primary_deep'])}>转化洞察</Text>
</Box>
<Text {ts(fontSize=14, color=p['text_sub'], lineHeight=1.75)}>{esc(insight)}</Text>
</Box>
</Box>
</Box>
{footer(p, page=page_label)}
</Slide>"""


def build_exec_summary_ccr(content: dict, p: dict = None, page_label: str = "01 / 01") -> str:
    """执行摘要三栏：Context / Complication / Resolution。"""
    p = p or DEFAULT_PALETTE
    title = content.get("title", "")
    subtitle = content.get("subtitle", "")

    def col_block(col_title, col_desc, icon_name, bg):
        return f"""<Box {bs(flex=1, background=bg, borderRadius=12, padding='32px 30px', flexDirection='column', gap=18)}>
<Box {bs(flexDirection='row', gap=12, alignItems='center')}>
{icon_circle(icon_name, p, size=44, icon_size=22)}
<Text {ts(fontSize=21, fontWeight='bold', color=p['text_main'])}>{esc(col_title)}</Text>
</Box>
<Text {ts(fontSize=15, color=p['text_sub'], lineHeight=1.85)}>{esc(col_desc)}</Text>
</Box>"""

    ctx = col_block(content.get("context_title", "Context 背景"),
                    content.get("context_desc", ""), "info-circle", p['accent_tint'])
    comp = col_block(content.get("complication_title", "Complication 挑战"),
                     content.get("complication_desc", ""), "exclamation-circle", p['icon_bg'])
    res = col_block(content.get("resolution_title", "Resolution 方案"),
                    content.get("resolution_desc", ""), "check-circle", p['accent_tint'])

    return f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='row', gap=24, marginTop=48, height=420)}>
{ctx}
{comp}
{res}
</Box>
{footer(p, page=page_label)}
</Slide>"""


# ============================================================
# 版式路由
# ============================================================
COLUMN_LABELS = re.compile(r"(左栏|右栏|（左侧）|（右侧）|左侧|右侧|\(左\)|\(右\)|对比|对照|vs\b|VS\b|versus|自研|采购|A vs B)")
FLOW_KEYWORDS = re.compile(r"(步骤|流程|阶段|路径|节点|时序|逐步|四步|三步|五步|落地)")
GRID_KEYWORDS = re.compile(r"(能力|要点|维度|要素|模块|名片|特性|特色|亮点|优势)")
KPI_KEYWORDS = re.compile(r"(指标|kpi|KPI|增长|转化|金额|收入|留存|活跃|订单|用户数)")
STAT_KEYWORDS = re.compile(r"(数字|关键数据|核心指标|突破|达|提升率|降低|命中率|准确率)")
CHART_KEYWORDS = re.compile(r"(图表|柱状|折线|趋势图|饼图|面积图|占比图|走势|对比图)")
TIMELINE_KEYWORDS = re.compile(r"(时间轴|里程碑|历程|大事记|时间线|年表|发展史|演进)")
IMAGE_TEXT_KEYWORDS = re.compile(r"(图文|配图|示意图|图示|场景图|左图右文|图解)")
ARCH_KEYWORDS = re.compile(r"(架构|分层|技术栈|系统组成|层次|组织结构|部门|层级|体系)")
# v3.2 新增关键词
STRATEGY_KEYWORDS = re.compile(r"(战略|房屋|使命|愿景|支柱|顶层设计|战略地图)")
ISSUE_TREE_KEYWORDS = re.compile(r"(问题树|拆解|分解|因果|原因分析|逻辑树|mece)")
MATRIX_KEYWORDS = re.compile(r"(矩阵|象限|二维|定位|bcg|BCG|四象限|2×2)")
FUNNEL_KEYWORDS = re.compile(r"(漏斗|转化漏斗|管线|pipeline|转化率|漏斗图|销售漏斗)")
CCR_KEYWORDS = re.compile(r"(执行摘要|背景挑战方案|context complication|CCR|scr|背景与挑战)")


def detect_layout(content: dict) -> str:
    items = content.get("items", [])
    title = content.get("title", "")
    n = len(items)

    # 0) 显式 layout 字段最高优先：调用方指名要哪个版式就直通（v3.2.3 修复，
    # 此前 JSON 里写 "layout": "comparison" 会被无视，标题含"技术栈"误路由
    # 到 architecture-layers，产出空壳页且 lint 零报警）
    explicit = str(content.get("layout", "")).strip().lower()
    if explicit in LAYOUT_REQUIRED:
        return explicit

    # 节点-连线图示（Deck B 范式）：含 graph/nodes 字段即走 diagram 生成器
    if content.get("graph") or content.get("nodes"):
        return "diagram"

    # v3.1 新版式：先检测显式字段（优先级最高）
    if content.get("stat_value"):
        return "stat-callout"
    if content.get("chart_type") or content.get("chart_data"):
        return "chart-page"
    if content.get("events"):
        return "timeline-vertical"
    if content.get("layers"):
        return "architecture-layers"
    if content.get("bullets") and not items:
        return "image-text-split"

    # v3.2 新版式：显式字段
    if content.get("pillars"):
        return "strategy-house"
    if content.get("branches"):
        return "issue-tree"
    if content.get("quadrants"):
        return "matrix-2x2"
    if content.get("stages"):
        return "funnel"
    if content.get("context_desc") or content.get("complication_desc"):
        return "exec-summary-ccr"

    # v3.1 新版式：关键词检测
    is_stat = bool(STAT_KEYWORDS.search(title))
    is_chart = bool(CHART_KEYWORDS.search(title))
    is_timeline = bool(TIMELINE_KEYWORDS.search(title))
    is_image_text = bool(IMAGE_TEXT_KEYWORDS.search(title))
    is_arch = bool(ARCH_KEYWORDS.search(title))

    # v3.2 新版式：关键词检测
    is_strategy = bool(STRATEGY_KEYWORDS.search(title))
    is_issue_tree = bool(ISSUE_TREE_KEYWORDS.search(title))
    is_matrix = bool(MATRIX_KEYWORDS.search(title))
    is_funnel = bool(FUNNEL_KEYWORDS.search(title))
    is_ccr = bool(CCR_KEYWORDS.search(title))

    if is_stat and n <= 1:
        return "stat-callout"
    if is_chart:
        return "chart-page"
    if is_timeline:
        return "timeline-vertical"
    if is_arch:
        return "architecture-layers"
    if is_image_text:
        return "image-text-split"
    if is_strategy:
        return "strategy-house"
    if is_issue_tree:
        return "issue-tree"
    if is_matrix:
        return "matrix-2x2"
    if is_funnel:
        return "funnel"
    if is_ccr:
        return "exec-summary-ccr"

    # v3.0 原有路由
    has_columns = bool(COLUMN_LABELS.search(
        content.get("left_title", "") + content.get("right_title", "") + title))
    is_flow = bool(FLOW_KEYWORDS.search(title))
    is_grid = bool(GRID_KEYWORDS.search(title))
    is_kpi = bool(KPI_KEYWORDS.search(title)) or any(
        KPI_KEYWORDS.search(str(it)) for it in items if isinstance(it, dict))

    if has_columns and content.get("left_items") and content.get("right_items"):
        return "comparison"
    if is_flow:
        return "flow-timeline"
    if is_kpi and 4 <= n <= 8:
        return "kpi-grid-6"
    if is_grid and 4 <= n <= 6:
        return "icon-grid-2x3"
    if 7 <= n <= 9:
        return "list-icon"
    if 4 <= n <= 6:
        return "icon-grid-2x3"
    if 3 <= n <= 5:
        return "flow-timeline"
    return "list-icon"


# ============================================================
# 主入口
# ============================================================
# 每个版式的"必需内容字段"：至少一项非空才允许构建，否则 emit 抛错。
# （v3.2.3 修复：此前路由错版式时会静默产出空壳页，lint 对空内容零报警）
LAYOUT_REQUIRED = {
    "diagram": ["graph", "nodes"],
    "comparison": ["left_items", "right_items"],
    "flow-timeline": ["items"],
    "icon-grid-2x3": ["items"],
    "list-icon": ["items"],
    "kpi-grid-6": ["items"],
    "stat-callout": ["stat_value"],
    "chart-page": ["chart_type", "chart_data"],
    "timeline-vertical": ["events"],
    "image-text-split": ["bullets", "items"],
    "architecture-layers": ["layers"],
    "strategy-house": ["pillars"],
    "issue-tree": ["branches"],
    "matrix-2x2": ["quadrants"],
    "funnel": ["stages"],
    "exec-summary-ccr": ["context_desc", "complication_desc"],
}


def _content_gate(chosen: str, content: dict):
    """内容闸门：版式必需字段全空时抛错，杜绝静默空壳页。"""
    fields = LAYOUT_REQUIRED.get(chosen, [])
    if fields and not any(content.get(f) for f in fields):
        raise ValueError(
            f"layout='{chosen}' 缺少必需内容字段 {fields}；"
            f"现有字段: {list(content.keys())}。请在 content JSON 补齐，"
            f"或显式指定其他 layout。"
        )


def emit(content: dict, output_path: str, layout: Optional[str] = None,
         palette=None) -> str:
    p = resolve_palette(palette)
    chosen = layout or detect_layout(content)
    _content_gate(chosen, content)

    if chosen == "comparison":
        body = build_comparison(
            content.get("left_title", ""),
            content.get("right_title", ""),
            content.get("left_items", []),
            content.get("right_items", []),
            content.get("title", ""),
            content.get("subtitle", ""),
            p,
        )
    elif chosen == "flow-timeline":
        body = build_flow_timeline(content.get("items", []), content.get("title", ""),
                                   content.get("subtitle", ""), p)
    elif chosen == "list-icon":
        body = build_list_icon(content.get("items", []), content.get("title", ""),
                              content.get("subtitle", ""), p)
    elif chosen == "kpi-grid-6":
        body = build_kpi_grid(content.get("items", []), content.get("title", ""),
                             content.get("subtitle", ""), p)
    elif chosen == "icon-grid-2x3":
        body = build_grid_2x3(content.get("items", []), content.get("title", ""),
                             content.get("subtitle", ""), p)
    elif chosen == "stat-callout":
        body = build_stat_callout(content, p)
    elif chosen == "chart-page":
        body = build_chart_page(content, p)
    elif chosen == "timeline-vertical":
        body = build_timeline_vertical(content, p)
    elif chosen == "image-text-split":
        body = build_image_text_split(content, p)
    elif chosen == "architecture-layers":
        body = build_architecture_layers(content, p)
    elif chosen == "strategy-house":
        body = build_strategy_house(content, p)
    elif chosen == "issue-tree":
        body = build_issue_tree(content, p)
    elif chosen == "matrix-2x2":
        body = build_matrix_2x2(content, p)
    elif chosen == "funnel":
        body = build_funnel(content, p)
    elif chosen == "exec-summary-ccr":
        body = build_exec_summary_ccr(content, p)
    elif chosen == "diagram":
        from diagram_emit import emit_node_link
        body = emit_node_link(content, palette=p)
    else:
        raise ValueError(f"未知版式: {chosen}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(body, encoding="utf-8")
    return str(Path(output_path).resolve())


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("用法: python slide_emit.py <content.json> <output.slide> [layout]")
        sys.exit(1)

    import json
    content = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = sys.argv[2]
    forced = sys.argv[3] if len(sys.argv) > 3 else None
    written = emit(content, out, layout=forced)
    print(f"✓ 已写入: {written}")
    print(f" 版式: {forced or detect_layout(content)}")
