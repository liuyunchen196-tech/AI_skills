#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
byai-diagram-designer · 视觉风格库（12 套）

纯标准库实现。每套风格定义完整色板、字体、线型、间距与语义编码。
风格是"可执行契约"：渲染引擎只读这里，不写死任何颜色。
"""

# 注意：字体名统一用单引号包裹。这些值会被直接拼进 SVG 的 font-family="%s"
# 属性；若用双引号，序列化后的 SVG 在严格 XML 解析下会因引号提前闭合而非法
# （浏览器打开 SVG 报 "value for attribute sc"，PNG 光栅化因 SVG 无法解析而失败）。
SANS = ("'PingFang SC','Hiragino Sans GB','Microsoft YaHei',"
        "'Source Han Sans SC','Noto Sans CJK SC','Helvetica Neue',Arial,sans-serif")
MONO = ("'SFMono-Regular',Consolas,'Liberation Mono',Menlo,'Courier New',"
        "'Microsoft YaHei',monospace")
SERIF = ("'Songti SC','SimSun','Source Han Serif SC','Noto Serif CJK SC',"
         "Georgia,serif")

# 语义关系默认编码：颜色 + 线型
_DEFAULT_KINDS = {
    "sync": {"dash": None, "label": "同步"},
    "async": {"dash": "7 5", "label": "异步"},
    "write": {"dash": None, "label": "写入"},
    "read": {"dash": "2 4", "label": "读取"},
    "loop": {"dash": "1 4", "label": "循环"},
    "flow": {"dash": None, "label": "流向"},
    "event": {"dash": "7 5", "label": "事件"},
    "return": {"dash": "4 4", "label": "返回"},
}


def _k(kinds, base_color):
    """把风格里的 kind 定义补全为 {color, dash, label}。"""
    out = {}
    for name, meta in _DEFAULT_KINDS.items():
        spec = dict(meta)
        override = kinds.get(name)
        if isinstance(override, str):
            spec["color"] = override
        elif isinstance(override, dict):
            spec["color"] = override.get("color", base_color)
            if "dash" in override:
                spec["dash"] = override["dash"]
        else:
            spec["color"] = base_color
        out[name] = spec
    return out


def _style(sid, name, name_zh, base, font, canvas, node, types, edge,
           lane, group, title, legend, accent, kinds=None, grid=None,
           node_shadow=False, desc="", best_for=""):
    s = {
        "id": sid,
        "name": name,
        "name_zh": name_zh,
        "base": base,
        "desc": desc,
        "best_for": best_for,
        "font_family": font,
        "accent": accent,
        "canvas": canvas,
        "grid": grid,
        "node": node,
        "node_shadow": node_shadow,
        "type_colors": types,
        "kinds": _k(kinds or {}, edge["color"]),
        "edge": edge,
        "lane": lane,
        "group": group,
        "title": title,
        "legend": legend,
    }
    return s


# --------------------------------------------------------------------------
# 通用类型色板：按节点语义类型取色，风格可覆盖
# --------------------------------------------------------------------------
def _types(mapping, default):
    out = {}
    for t in ("frontend", "backend", "database", "cloud", "security",
              "messagebus", "external", "llm", "agent", "vector", "storage",
              "user", "process", "decision", "terminal", "note", "default"):
        out[t] = mapping.get(t, mapping.get("default", default))
    return out


# --------------------------------------------------------------------------
# 01 · Flat Icon —— 默认风格。白底、彩色描边、扁平图标
# --------------------------------------------------------------------------
STYLE_FLAT_ICON = _style(
    sid="flat-icon", name="Flat Icon", name_zh="扁平图标", base="light",
    font=SANS, desc="白底 + 彩色描边 + 扁平图标，最通用的技术图风格",
    best_for="系统架构、AI/Agent 架构、技术分享配图",
    canvas={"bg": "#FFFFFF"},
    node={"fill": "#FFFFFF", "stroke": "#D0D5DD", "stroke_width": 1.2, "rx": 10,
          "title_size": 14, "title_color": "#101828",
          "desc_size": 11, "desc_color": "#667085", "pad_x": 14, "pad_y": 12},
    types=_types({
        "frontend": {"fill": "#EFF6FF", "stroke": "#60A5FA", "text": "#1E3A8A", "icon": "#2563EB"},
        "backend": {"fill": "#ECFDF5", "stroke": "#34D399", "text": "#065F46", "icon": "#059669"},
        "database": {"fill": "#FFFBEB", "stroke": "#FBBF24", "text": "#78350F", "icon": "#D97706"},
        "cloud": {"fill": "#F5F3FF", "stroke": "#A78BFA", "text": "#4C1D95", "icon": "#7C3AED"},
        "security": {"fill": "#FEF2F2", "stroke": "#F87171", "text": "#7F1D1D", "icon": "#DC2626"},
        "messagebus": {"fill": "#FDF2F8", "stroke": "#F472B6", "text": "#831843", "icon": "#DB2777"},
        "external": {"fill": "#F8FAFC", "stroke": "#94A3B8", "text": "#334155", "icon": "#475569"},
        "llm": {"fill": "#EEF2FF", "stroke": "#818CF8", "text": "#312E81", "icon": "#4F46E5"},
        "agent": {"fill": "#ECFEFF", "stroke": "#22D3EE", "text": "#155E75", "icon": "#0891B2"},
        "vector": {"fill": "#F0FDFA", "stroke": "#2DD4BF", "text": "#134E4A", "icon": "#0D9488"},
        "storage": {"fill": "#FFFBEB", "stroke": "#FBBF24", "text": "#78350F", "icon": "#D97706"},
        "user": {"fill": "#F1F5F9", "stroke": "#64748B", "text": "#1E293B", "icon": "#334155"},
        "process": {"fill": "#FFFFFF", "stroke": "#93C5FD", "text": "#1E3A8A", "icon": "#2563EB"},
        "decision": {"fill": "#FFFBEB", "stroke": "#FBBF24", "text": "#78350F", "icon": "#D97706"},
        "terminal": {"fill": "#F1F5F9", "stroke": "#64748B", "text": "#1E293B", "icon": "#334155"},
        "note": {"fill": "#FFFBEB", "stroke": "#FCD34D", "text": "#78350F", "icon": "#D97706"},
        "default": {"fill": "#FFFFFF", "stroke": "#CBD5E1", "text": "#1E293B", "icon": "#475569"},
    }, {"fill": "#FFFFFF", "stroke": "#CBD5E1", "text": "#1E293B", "icon": "#475569"}),
    edge={"color": "#94A3B8", "width": 1.5, "label_bg": "#FFFFFF",
          "label_color": "#475569", "label_size": 11, "arrow": 7},
    lane={"fill": "#F8FAFC", "stroke": "#E2E8F0", "label_color": "#64748B", "label_size": 12,
          "band": True},
    group={"fill": "#F8FAFC", "stroke": "#CBD5E1", "dash": "6 4",
           "label_color": "#475569", "label_size": 12},
    title={"color": "#0F172A", "size": 22, "sub_color": "#64748B", "sub_size": 13},
    legend={"bg": "#FFFFFF", "border": "#E2E8F0", "text_color": "#475569", "size": 11},
    accent="#2563EB",
    kinds={"write": "#059669", "read": "#2563EB", "async": "#7C3AED", "loop": "#D97706",
           "event": "#DB2777", "return": "#64748B"},
)

# --------------------------------------------------------------------------
# 02 · Dark Terminal —— 暗底 + 霓虹 + 等宽字体
# --------------------------------------------------------------------------
STYLE_DARK_TERMINAL = _style(
    sid="dark-terminal", name="Dark Terminal", name_zh="暗色终端", base="dark",
    font=MONO, desc="深色底 + 霓虹描边 + 等宽字体，极客感强",
    best_for="工具调用链、Agent 执行流程、夜间演示",
    canvas={"bg": "#0B1020"},
    grid={"color": "#16203A", "step": 24, "major": 120},
    node={"fill": "#111A2E", "stroke": "#2E4A7D", "stroke_width": 1.2, "rx": 8,
          "title_size": 13, "title_color": "#D7E3FF",
          "desc_size": 11, "desc_color": "#7D93BF", "pad_x": 14, "pad_y": 11},
    types=_types({
        "frontend": {"fill": "#0E2036", "stroke": "#38BDF8", "text": "#BAE6FD", "icon": "#38BDF8"},
        "backend": {"fill": "#0B2419", "stroke": "#34D399", "text": "#A7F3D0", "icon": "#34D399"},
        "database": {"fill": "#251A05", "stroke": "#FBBF24", "text": "#FDE68A", "icon": "#FBBF24"},
        "cloud": {"fill": "#1A1235", "stroke": "#A78BFA", "text": "#DDD6FE", "icon": "#A78BFA"},
        "security": {"fill": "#2A0F14", "stroke": "#F87171", "text": "#FECACA", "icon": "#F87171"},
        "messagebus": {"fill": "#2A0F24", "stroke": "#F472B6", "text": "#FBCFE8", "icon": "#F472B6"},
        "external": {"fill": "#141B2D", "stroke": "#64748B", "text": "#CBD5E1", "icon": "#94A3B8"},
        "llm": {"fill": "#151538", "stroke": "#818CF8", "text": "#C7D2FE", "icon": "#818CF8"},
        "agent": {"fill": "#0B2630", "stroke": "#22D3EE", "text": "#A5F3FC", "icon": "#22D3EE"},
        "vector": {"fill": "#0A2622", "stroke": "#2DD4BF", "text": "#99F6E4", "icon": "#2DD4BF"},
        "storage": {"fill": "#251A05", "stroke": "#FBBF24", "text": "#FDE68A", "icon": "#FBBF24"},
        "user": {"fill": "#141B2D", "stroke": "#94A3B8", "text": "#E2E8F0", "icon": "#CBD5E1"},
        "process": {"fill": "#0E2036", "stroke": "#38BDF8", "text": "#BAE6FD", "icon": "#38BDF8"},
        "decision": {"fill": "#251A05", "stroke": "#FBBF24", "text": "#FDE68A", "icon": "#FBBF24"},
        "terminal": {"fill": "#0E1424", "stroke": "#475569", "text": "#CBD5E1", "icon": "#94A3B8"},
        "note": {"fill": "#251A05", "stroke": "#FCD34D", "text": "#FDE68A", "icon": "#FCD34D"},
        "default": {"fill": "#111A2E", "stroke": "#334867", "text": "#D7E3FF", "icon": "#7D93BF"},
    }, {"fill": "#111A2E", "stroke": "#334867", "text": "#D7E3FF", "icon": "#7D93BF"}),
    edge={"color": "#3E5C8A", "width": 1.5, "label_bg": "#0B1020",
          "label_color": "#8FA8D6", "label_size": 11, "arrow": 7},
    lane={"fill": "#0D1526", "stroke": "#1C2C4A", "label_color": "#6D86B8", "label_size": 12,
          "band": True},
    group={"fill": "#0D1526", "stroke": "#2E4A7D", "dash": "6 4",
           "label_color": "#8FA8D6", "label_size": 12},
    title={"color": "#E6EEFF", "size": 22, "sub_color": "#7D93BF", "sub_size": 13},
    legend={"bg": "#0D1526", "border": "#1C2C4A", "text_color": "#8FA8D6", "size": 11},
    accent="#22D3EE",
    kinds={"write": "#34D399", "read": "#38BDF8", "async": "#A78BFA", "loop": "#FBBF24",
           "event": "#F472B6", "return": "#64748B"},
)

# --------------------------------------------------------------------------
# 03 · Blueprint —— 工程蓝图，网格 + 青线
# --------------------------------------------------------------------------
STYLE_BLUEPRINT = _style(
    sid="blueprint", name="Blueprint", name_zh="工程蓝图", base="dark",
    font=MONO, desc="深蓝网格底 + 青色线条，工程制图感",
    best_for="微服务架构、部署拓扑、数据流管道",
    canvas={"bg": "#0A2540"},
    grid={"color": "#12406B", "step": 20, "major": 100},
    node={"fill": "#0E3763", "stroke": "#5EEAD4", "stroke_width": 1.1, "rx": 4,
          "title_size": 13, "title_color": "#CCFBF1",
          "desc_size": 11, "desc_color": "#7FDBCA", "pad_x": 13, "pad_y": 11},
    types=_types({
        "frontend": {"fill": "#0E3763", "stroke": "#5EEAD4", "text": "#CCFBF1", "icon": "#5EEAD4"},
        "backend": {"fill": "#0D3B4F", "stroke": "#7DD3FC", "text": "#E0F2FE", "icon": "#7DD3FC"},
        "database": {"fill": "#123A5C", "stroke": "#A5B4FC", "text": "#E0E7FF", "icon": "#A5B4FC"},
        "cloud": {"fill": "#123049", "stroke": "#93C5FD", "text": "#DBEAFE", "icon": "#93C5FD"},
        "security": {"fill": "#3A1E2E", "stroke": "#FDA4AF", "text": "#FFE4E6", "icon": "#FDA4AF"},
        "messagebus": {"fill": "#123A5C", "stroke": "#C4B5FD", "text": "#EDE9FE", "icon": "#C4B5FD"},
        "external": {"fill": "#0E2A45", "stroke": "#94A3B8", "text": "#CBD5E1", "icon": "#94A3B8"},
        "llm": {"fill": "#1B2C55", "stroke": "#A5B4FC", "text": "#E0E7FF", "icon": "#A5B4FC"},
        "agent": {"fill": "#0D3B4F", "stroke": "#67E8F9", "text": "#CFFAFE", "icon": "#67E8F9"},
        "vector": {"fill": "#0F3A44", "stroke": "#5EEAD4", "text": "#CCFBF1", "icon": "#5EEAD4"},
        "storage": {"fill": "#123A5C", "stroke": "#A5B4FC", "text": "#E0E7FF", "icon": "#A5B4FC"},
        "user": {"fill": "#0E2A45", "stroke": "#CBD5E1", "text": "#E2E8F0", "icon": "#CBD5E1"},
        "process": {"fill": "#0E3763", "stroke": "#5EEAD4", "text": "#CCFBF1", "icon": "#5EEAD4"},
        "decision": {"fill": "#123A5C", "stroke": "#FCD34D", "text": "#FEF3C7", "icon": "#FCD34D"},
        "terminal": {"fill": "#0E2A45", "stroke": "#64748B", "text": "#CBD5E1", "icon": "#94A3B8"},
        "note": {"fill": "#123A5C", "stroke": "#FCD34D", "text": "#FEF3C7", "icon": "#FCD34D"},
        "default": {"fill": "#0E3763", "stroke": "#5EEAD4", "text": "#CCFBF1", "icon": "#5EEAD4"},
    }, {"fill": "#0E3763", "stroke": "#5EEAD4", "text": "#CCFBF1", "icon": "#5EEAD4"}),
    edge={"color": "#7DD3FC", "width": 1.4, "label_bg": "#0A2540",
          "label_color": "#A5E9F5", "label_size": 11, "arrow": 7},
    lane={"fill": "#0B2C4A", "stroke": "#1B4A78", "label_color": "#7FDBCA", "label_size": 12,
          "band": True},
    group={"fill": "#0B2C4A", "stroke": "#5EEAD4", "dash": "8 4",
           "label_color": "#A5E9F5", "label_size": 12},
    title={"color": "#E0F7FA", "size": 22, "sub_color": "#7FDBCA", "sub_size": 13},
    legend={"bg": "#0B2C4A", "border": "#1B4A78", "text_color": "#A5E9F5", "size": 11},
    accent="#5EEAD4",
    kinds={"write": "#5EEAD4", "read": "#7DD3FC", "async": "#C4B5FD", "loop": "#FCD34D",
           "event": "#FDA4AF", "return": "#94A3B8"},
)

# --------------------------------------------------------------------------
# 04 · Notion Clean —— 极简白、单一箭头色
# --------------------------------------------------------------------------
STYLE_NOTION = _style(
    sid="notion-clean", name="Notion Clean", name_zh="简约笔记", base="light",
    font=SANS, desc="纯白极简、细灰描边、单一箭头色，文档嵌入首选",
    best_for="文档配图、知识库、层级结构图",
    canvas={"bg": "#FFFFFF"},
    node={"fill": "#FFFFFF", "stroke": "#E1E3E6", "stroke_width": 1.0, "rx": 6,
          "title_size": 13, "title_color": "#37352F",
          "desc_size": 11, "desc_color": "#9B9A97", "pad_x": 13, "pad_y": 11},
    types=_types({
        "frontend": {"fill": "#F7F6F3", "stroke": "#C9C8C5", "text": "#37352F", "icon": "#6B6A65"},
        "backend": {"fill": "#F1F5F9", "stroke": "#C9C8C5", "text": "#37352F", "icon": "#6B6A65"},
        "database": {"fill": "#FBFAF7", "stroke": "#C9C8C5", "text": "#37352F", "icon": "#6B6A65"},
        "cloud": {"fill": "#F7F6F3", "stroke": "#C9C8C5", "text": "#37352F", "icon": "#6B6A65"},
        "security": {"fill": "#FDF4F4", "stroke": "#E9B7B7", "text": "#8B3A3A", "icon": "#B45B5B"},
        "messagebus": {"fill": "#FBF3F7", "stroke": "#DCBFCE", "text": "#7A3B58", "icon": "#9B5C7C"},
        "external": {"fill": "#FAFAF9", "stroke": "#DDDBD8", "text": "#5F5E5A", "icon": "#8B8A85"},
        "llm": {"fill": "#F3F4FB", "stroke": "#C3C7E8", "text": "#3B3F6B", "icon": "#5B60A8"},
        "agent": {"fill": "#F1F7FA", "stroke": "#BBD9E6", "text": "#2B5566", "icon": "#4A8299"},
        "vector": {"fill": "#F0F8F6", "stroke": "#B8DDD2", "text": "#286055", "icon": "#45907F"},
        "storage": {"fill": "#FBFAF7", "stroke": "#C9C8C5", "text": "#37352F", "icon": "#6B6A65"},
        "user": {"fill": "#FAFAF9", "stroke": "#DDDBD8", "text": "#37352F", "icon": "#6B6A65"},
        "process": {"fill": "#FFFFFF", "stroke": "#D7D5D0", "text": "#37352F", "icon": "#6B6A65"},
        "decision": {"fill": "#FBFAF7", "stroke": "#DDD3B8", "text": "#6B5A2B", "icon": "#9A8548"},
        "terminal": {"fill": "#F7F6F3", "stroke": "#DDDBD8", "text": "#37352F", "icon": "#6B6A65"},
        "note": {"fill": "#FCF7E8", "stroke": "#EBD9A8", "text": "#6B5A2B", "icon": "#9A8548"},
        "default": {"fill": "#FFFFFF", "stroke": "#E1E3E6", "text": "#37352F", "icon": "#6B6A65"},
    }, {"fill": "#FFFFFF", "stroke": "#E1E3E6", "text": "#37352F", "icon": "#6B6A65"}),
    edge={"color": "#A5A39D", "width": 1.3, "label_bg": "#FFFFFF",
          "label_color": "#78766F", "label_size": 11, "arrow": 6},
    lane={"fill": "#FBFAF8", "stroke": "#EDECE9", "label_color": "#9B9A97", "label_size": 12,
          "band": True},
    group={"fill": "#FCFCFB", "stroke": "#DDDBD8", "dash": "5 4",
           "label_color": "#78766F", "label_size": 12},
    title={"color": "#37352F", "size": 21, "sub_color": "#9B9A97", "sub_size": 13},
    legend={"bg": "#FFFFFF", "border": "#EDECE9", "text_color": "#78766F", "size": 11},
    accent="#37352F",
    kinds={"write": "#45907F", "read": "#4A8299", "async": "#5B60A8", "loop": "#9A8548",
           "event": "#9B5C7C", "return": "#8B8A85"},
)

# --------------------------------------------------------------------------
# 05 · Glassmorphism —— 深色渐变 + 毛玻璃卡片
# --------------------------------------------------------------------------
STYLE_GLASS = _style(
    sid="glassmorphism", name="Glassmorphism", name_zh="毛玻璃", base="dark",
    font=SANS, desc="深色底 + 半透明玻璃卡片 + 柔和描边，适合发布会大屏",
    best_for="Multi-Agent 协作、发布会演示、大屏展示",
    canvas={"bg": "#0F1226", "bg2": "#241B4B"},
    node={"fill": "#FFFFFF14", "stroke": "#FFFFFF33", "stroke_width": 1.1, "rx": 14,
          "title_size": 13, "title_color": "#F5F3FF",
          "desc_size": 11, "desc_color": "#B9B4DE", "pad_x": 15, "pad_y": 12},
    types=_types({
        "frontend": {"fill": "#38BDF820", "stroke": "#38BDF877", "text": "#E0F2FE", "icon": "#7DD3FC"},
        "backend": {"fill": "#34D39920", "stroke": "#34D39977", "text": "#D1FAE5", "icon": "#6EE7B7"},
        "database": {"fill": "#FBBF2420", "stroke": "#FBBF2477", "text": "#FEF3C7", "icon": "#FCD34D"},
        "cloud": {"fill": "#A78BFA20", "stroke": "#A78BFA77", "text": "#EDE9FE", "icon": "#C4B5FD"},
        "security": {"fill": "#F8717120", "stroke": "#F8717177", "text": "#FEE2E2", "icon": "#FCA5A5"},
        "messagebus": {"fill": "#F472B620", "stroke": "#F472B677", "text": "#FCE7F3", "icon": "#F9A8D4"},
        "external": {"fill": "#94A3B820", "stroke": "#94A3B877", "text": "#E2E8F0", "icon": "#CBD5E1"},
        "llm": {"fill": "#818CF820", "stroke": "#818CF877", "text": "#E0E7FF", "icon": "#A5B4FC"},
        "agent": {"fill": "#22D3EE20", "stroke": "#22D3EE77", "text": "#CFFAFE", "icon": "#67E8F9"},
        "vector": {"fill": "#2DD4BF20", "stroke": "#2DD4BF77", "text": "#CCFBF1", "icon": "#5EEAD4"},
        "storage": {"fill": "#FBBF2420", "stroke": "#FBBF2477", "text": "#FEF3C7", "icon": "#FCD34D"},
        "user": {"fill": "#CBD5E11A", "stroke": "#CBD5E166", "text": "#F1F5F9", "icon": "#E2E8F0"},
        "process": {"fill": "#FFFFFF14", "stroke": "#FFFFFF44", "text": "#F5F3FF", "icon": "#DDD6FE"},
        "decision": {"fill": "#FBBF2420", "stroke": "#FBBF2477", "text": "#FEF3C7", "icon": "#FCD34D"},
        "terminal": {"fill": "#FFFFFF10", "stroke": "#FFFFFF33", "text": "#E9E4FF", "icon": "#C4B5FD"},
        "note": {"fill": "#FCD34D1A", "stroke": "#FCD34D66", "text": "#FEF3C7", "icon": "#FCD34D"},
        "default": {"fill": "#FFFFFF14", "stroke": "#FFFFFF33", "text": "#F5F3FF", "icon": "#C4B5FD"},
    }, {"fill": "#FFFFFF14", "stroke": "#FFFFFF33", "text": "#F5F3FF", "icon": "#C4B5FD"}),
    edge={"color": "#A5B4FC99", "width": 1.5, "label_bg": "#1B1740",
          "label_color": "#C7D2FE", "label_size": 11, "arrow": 7},
    lane={"fill": "#FFFFFF08", "stroke": "#FFFFFF1A", "label_color": "#B9B4DE", "label_size": 12,
          "band": True},
    group={"fill": "#FFFFFF0A", "stroke": "#FFFFFF2E", "dash": "7 5",
           "label_color": "#C7D2FE", "label_size": 12},
    title={"color": "#F5F3FF", "size": 22, "sub_color": "#B9B4DE", "sub_size": 13},
    legend={"bg": "#1B1740", "border": "#FFFFFF2E", "text_color": "#C7D2FE", "size": 11},
    accent="#A78BFA", node_shadow=True,
    kinds={"write": "#6EE7B7", "read": "#7DD3FC", "async": "#C4B5FD", "loop": "#FCD34D",
           "event": "#F9A8D4", "return": "#94A3B8"},
)

# --------------------------------------------------------------------------
# 06 · Warm Sand —— 暖砂纸感（Claude 官方风）
# --------------------------------------------------------------------------
STYLE_WARM_SAND = _style(
    sid="warm-sand", name="Warm Sand", name_zh="暖砂纸感", base="light",
    font=SERIF, desc="暖米色底 + 陶土橙点缀 + 衬线标题，人文纸感",
    best_for="系统分层架构、对外汇报、品牌化配图",
    canvas={"bg": "#FAF6F0"},
    node={"fill": "#FFFFFF", "stroke": "#E3D9CC", "stroke_width": 1.1, "rx": 10,
          "title_size": 13, "title_color": "#3D3229",
          "desc_size": 11, "desc_color": "#8A7B6B", "pad_x": 14, "pad_y": 12},
    types=_types({
        "frontend": {"fill": "#FDF6EC", "stroke": "#D9A97A", "text": "#5C3D22", "icon": "#C97B3F"},
        "backend": {"fill": "#F2F5EE", "stroke": "#9CAF86", "text": "#3D4A2F", "icon": "#6E8A52"},
        "database": {"fill": "#FBF1E4", "stroke": "#D9A97A", "text": "#5C3D22", "icon": "#C97B3F"},
        "cloud": {"fill": "#F4F1FA", "stroke": "#A99CC4", "text": "#443A5C", "icon": "#7C6AA8"},
        "security": {"fill": "#FBEDEA", "stroke": "#D99A90", "text": "#6B322A", "icon": "#B5544A"},
        "messagebus": {"fill": "#F9EDF2", "stroke": "#C48FA5", "text": "#5E2D42", "icon": "#A45F7C"},
        "external": {"fill": "#F5F2EC", "stroke": "#C4B8A8", "text": "#4A4038", "icon": "#7A6C5C"},
        "llm": {"fill": "#EFEEF8", "stroke": "#9C96C6", "text": "#3D3A5C", "icon": "#6F68A8"},
        "agent": {"fill": "#EAF1F4", "stroke": "#8FA9B8", "text": "#2F4653", "icon": "#5A7C8F"},
        "vector": {"fill": "#EAF2EE", "stroke": "#8FB39C", "text": "#2F4A39", "icon": "#5A8568"},
        "storage": {"fill": "#FBF1E4", "stroke": "#D9A97A", "text": "#5C3D22", "icon": "#C97B3F"},
        "user": {"fill": "#F5F2EC", "stroke": "#C4B8A8", "text": "#3D3229", "icon": "#7A6C5C"},
        "process": {"fill": "#FFFFFF", "stroke": "#D9CDBB", "text": "#3D3229", "icon": "#8A7B6B"},
        "decision": {"fill": "#FBF1E4", "stroke": "#D9A97A", "text": "#5C3D22", "icon": "#C97B3F"},
        "terminal": {"fill": "#F5F2EC", "stroke": "#C4B8A8", "text": "#3D3229", "icon": "#7A6C5C"},
        "note": {"fill": "#FBF6E6", "stroke": "#E0CB92", "text": "#5C4A22", "icon": "#BC9B3F"},
        "default": {"fill": "#FFFFFF", "stroke": "#E3D9CC", "text": "#3D3229", "icon": "#8A7B6B"},
    }, {"fill": "#FFFFFF", "stroke": "#E3D9CC", "text": "#3D3229", "icon": "#8A7B6B"}),
    edge={"color": "#B5A48E", "width": 1.4, "label_bg": "#FAF6F0",
          "label_color": "#7A6C5C", "label_size": 11, "arrow": 7},
    lane={"fill": "#F5EFE6", "stroke": "#EADFCE", "label_color": "#8A7B6B", "label_size": 12,
          "band": True},
    group={"fill": "#F7F1E8", "stroke": "#D9CDBB", "dash": "6 4",
           "label_color": "#7A6C5C", "label_size": 12},
    title={"color": "#3D3229", "size": 22, "sub_color": "#8A7B6B", "sub_size": 13},
    legend={"bg": "#FFFFFF", "border": "#EADFCE", "text_color": "#7A6C5C", "size": 11},
    accent="#C97B3F",
    kinds={"write": "#6E8A52", "read": "#C97B3F", "async": "#7C6AA8", "loop": "#BC9B3F",
           "event": "#A45F7C", "return": "#8A7B6B"},
)

# --------------------------------------------------------------------------
# 07 · Clean Tech —— 净白科技（OpenAI 官方风）
# --------------------------------------------------------------------------
STYLE_CLEAN_TECH = _style(
    sid="clean-tech", name="Clean Tech", name_zh="净白科技", base="light",
    font=SANS, desc="纯白底 + 墨黑文字 + 单一强调色，API 与集成图首选",
    best_for="API 集成流、SDK 调用链、产品文档",
    canvas={"bg": "#FFFFFF"},
    node={"fill": "#FFFFFF", "stroke": "#DDE1E6", "stroke_width": 1.2, "rx": 8,
          "title_size": 13, "title_color": "#0D0D0D",
          "desc_size": 11, "desc_color": "#6B6B6B", "pad_x": 14, "pad_y": 11},
    types=_types({
        "frontend": {"fill": "#F6F8FA", "stroke": "#C9D1D9", "text": "#0D0D0D", "icon": "#10A37F"},
        "backend": {"fill": "#F1F7F5", "stroke": "#B7DFD3", "text": "#0D0D0D", "icon": "#10A37F"},
        "database": {"fill": "#F7F7F8", "stroke": "#D9D9E3", "text": "#0D0D0D", "icon": "#4B4B4B"},
        "cloud": {"fill": "#F2F6FB", "stroke": "#C6D7EA", "text": "#0D0D0D", "icon": "#2F6FB3"},
        "security": {"fill": "#FDF5F4", "stroke": "#EFCEC9", "text": "#7A2B22", "icon": "#C4463A"},
        "messagebus": {"fill": "#F8F5FB", "stroke": "#DCCDEA", "text": "#4A2D64", "icon": "#8B5CB8"},
        "external": {"fill": "#FAFAFA", "stroke": "#E1E1E1", "text": "#4B4B4B", "icon": "#6B6B6B"},
        "llm": {"fill": "#F1F7F5", "stroke": "#B7DFD3", "text": "#0D0D0D", "icon": "#10A37F"},
        "agent": {"fill": "#F1F7F5", "stroke": "#8FCFB9", "text": "#0D0D0D", "icon": "#0E8C6B"},
        "vector": {"fill": "#F3F8F7", "stroke": "#A9D6C8", "text": "#0D0D0D", "icon": "#10A37F"},
        "storage": {"fill": "#F7F7F8", "stroke": "#D9D9E3", "text": "#0D0D0D", "icon": "#4B4B4B"},
        "user": {"fill": "#FAFAFA", "stroke": "#DDE1E6", "text": "#0D0D0D", "icon": "#4B4B4B"},
        "process": {"fill": "#FFFFFF", "stroke": "#DDE1E6", "text": "#0D0D0D", "icon": "#4B4B4B"},
        "decision": {"fill": "#FBF8F0", "stroke": "#E5D6AE", "text": "#5C4A15", "icon": "#B58B22"},
        "terminal": {"fill": "#F7F7F8", "stroke": "#DDE1E6", "text": "#0D0D0D", "icon": "#4B4B4B"},
        "note": {"fill": "#FBF8F0", "stroke": "#E5D6AE", "text": "#5C4A15", "icon": "#B58B22"},
        "default": {"fill": "#FFFFFF", "stroke": "#DDE1E6", "text": "#0D0D0D", "icon": "#4B4B4B"},
    }, {"fill": "#FFFFFF", "stroke": "#DDE1E6", "text": "#0D0D0D", "icon": "#4B4B4B"}),
    edge={"color": "#8E8E8E", "width": 1.4, "label_bg": "#FFFFFF",
          "label_color": "#4B4B4B", "label_size": 11, "arrow": 6},
    lane={"fill": "#FAFAFA", "stroke": "#EDEDED", "label_color": "#6B6B6B", "label_size": 12,
          "band": True},
    group={"fill": "#FBFBFC", "stroke": "#DDE1E6", "dash": "6 4",
           "label_color": "#4B4B4B", "label_size": 12},
    title={"color": "#0D0D0D", "size": 22, "sub_color": "#6B6B6B", "sub_size": 13},
    legend={"bg": "#FFFFFF", "border": "#EDEDED", "text_color": "#4B4B4B", "size": 11},
    accent="#10A37F",
    kinds={"write": "#0E8C6B", "read": "#10A37F", "async": "#8B5CB8", "loop": "#B58B22",
           "event": "#2F6FB3", "return": "#8E8E8E"},
)

# --------------------------------------------------------------------------
# 08 · Midnight Gold —— 暗夜鎏金
# --------------------------------------------------------------------------
STYLE_MIDNIGHT_GOLD = _style(
    sid="midnight-gold", name="Midnight Gold", name_zh="暗夜鎏金", base="dark",
    font=SANS, desc="近纯黑底 + 香槟金线条，高端质感，适合对外发布",
    best_for="Agent 运行时架构、发布会主视觉、对外白皮书",
    canvas={"bg": "#0A0A0B"},
    node={"fill": "#141416", "stroke": "#4A4230", "stroke_width": 1.1, "rx": 10,
          "title_size": 13, "title_color": "#F5EEDC",
          "desc_size": 11, "desc_color": "#9A8F76", "pad_x": 15, "pad_y": 12},
    types=_types({
        "frontend": {"fill": "#171719", "stroke": "#8A7A50", "text": "#F5EEDC", "icon": "#D4AF6A"},
        "backend": {"fill": "#131618", "stroke": "#5E6E62", "text": "#E4EFE6", "icon": "#87A78F"},
        "database": {"fill": "#191512", "stroke": "#8A6A3A", "text": "#F5E6CC", "icon": "#C89B54"},
        "cloud": {"fill": "#15161C", "stroke": "#5A5F7A", "text": "#E6E8F5", "icon": "#8A92B8"},
        "security": {"fill": "#1B1315", "stroke": "#8A4A4A", "text": "#F5DEDC", "icon": "#C47979"},
        "messagebus": {"fill": "#1A141A", "stroke": "#7A5578", "text": "#F0DCEE", "icon": "#B483B0"},
        "external": {"fill": "#131315", "stroke": "#4A4A50", "text": "#DCDCE0", "icon": "#8A8A92"},
        "llm": {"fill": "#171522", "stroke": "#6E5E9E", "text": "#ECE6FA", "icon": "#A992DD"},
        "agent": {"fill": "#11191C", "stroke": "#4A7A82", "text": "#DCEEF0", "icon": "#6FA8B2"},
        "vector": {"fill": "#111A18", "stroke": "#4A7A6E", "text": "#DCEEE8", "icon": "#6FA897"},
        "storage": {"fill": "#191512", "stroke": "#8A6A3A", "text": "#F5E6CC", "icon": "#C89B54"},
        "user": {"fill": "#131315", "stroke": "#55555C", "text": "#E4E4E8", "icon": "#9A9AA2"},
        "process": {"fill": "#141416", "stroke": "#4A4230", "text": "#F5EEDC", "icon": "#D4AF6A"},
        "decision": {"fill": "#191512", "stroke": "#8A6A3A", "text": "#F5E6CC", "icon": "#C89B54"},
        "terminal": {"fill": "#111112", "stroke": "#3E3E44", "text": "#D4D4D8", "icon": "#7A7A82"},
        "note": {"fill": "#191610", "stroke": "#6E5F33", "text": "#F2EACB", "icon": "#C0A656"},
        "default": {"fill": "#141416", "stroke": "#4A4230", "text": "#F5EEDC", "icon": "#D4AF6A"},
    }, {"fill": "#141416", "stroke": "#4A4230", "text": "#F5EEDC", "icon": "#D4AF6A"}),
    edge={"color": "#6B6142", "width": 1.4, "label_bg": "#0A0A0B",
          "label_color": "#A99B72", "label_size": 11, "arrow": 7},
    lane={"fill": "#101011", "stroke": "#232320", "label_color": "#8A8064", "label_size": 12,
          "band": True},
    group={"fill": "#0F0F11", "stroke": "#4A4230", "dash": "7 5",
           "label_color": "#A99B72", "label_size": 12},
    title={"color": "#F5EEDC", "size": 22, "sub_color": "#9A8F76", "sub_size": 13},
    legend={"bg": "#101011", "border": "#232320", "text_color": "#A99B72", "size": 11},
    accent="#D4AF6A",
    kinds={"write": "#87A78F", "read": "#D4AF6A", "async": "#A992DD", "loop": "#C0A656",
           "event": "#B483B0", "return": "#7A7A82"},
)

# --------------------------------------------------------------------------
# 09 · C4 Review —— 评审画布（工程契约：单一抽象层级）
# --------------------------------------------------------------------------
STYLE_C4_REVIEW = _style(
    sid="c4-review", name="C4 Review", name_zh="架构评审", base="light",
    font=SANS, desc="单一抽象层级 + 职责/技术/协议显式标注，评审专用",
    best_for="C4 容器级评审、技术方案评审会",
    canvas={"bg": "#FFFFFF"},
    grid={"color": "#F1F5F9", "step": 20, "major": 100},
    node={"fill": "#FFFFFF", "stroke": "#334155", "stroke_width": 1.6, "rx": 4,
          "title_size": 13, "title_color": "#0F172A",
          "desc_size": 11, "desc_color": "#475569", "pad_x": 14, "pad_y": 12},
    types=_types({
        "frontend": {"fill": "#FFFFFF", "stroke": "#1E40AF", "text": "#0F172A", "icon": "#1E40AF"},
        "backend": {"fill": "#F8FAFC", "stroke": "#0F766E", "text": "#0F172A", "icon": "#0F766E"},
        "database": {"fill": "#F8FAFC", "stroke": "#B45309", "text": "#0F172A", "icon": "#B45309"},
        "cloud": {"fill": "#F8FAFC", "stroke": "#5B21B6", "text": "#0F172A", "icon": "#5B21B6"},
        "security": {"fill": "#FEF2F2", "stroke": "#B91C1C", "text": "#7F1D1D", "icon": "#B91C1C"},
        "messagebus": {"fill": "#F8FAFC", "stroke": "#9D174D", "text": "#0F172A", "icon": "#9D174D"},
        "external": {"fill": "#F1F5F9", "stroke": "#475569", "text": "#334155", "icon": "#334155"},
        "llm": {"fill": "#EEF2FF", "stroke": "#4338CA", "text": "#312E81", "icon": "#4338CA"},
        "agent": {"fill": "#ECFEFF", "stroke": "#0E7490", "text": "#155E75", "icon": "#0E7490"},
        "vector": {"fill": "#F0FDFA", "stroke": "#0F766E", "text": "#134E4A", "icon": "#0F766E"},
        "storage": {"fill": "#FFFBEB", "stroke": "#B45309", "text": "#78350F", "icon": "#B45309"},
        "user": {"fill": "#F1F5F9", "stroke": "#334155", "text": "#0F172A", "icon": "#334155"},
        "process": {"fill": "#FFFFFF", "stroke": "#1E40AF", "text": "#0F172A", "icon": "#1E40AF"},
        "decision": {"fill": "#FFFBEB", "stroke": "#B45309", "text": "#78350F", "icon": "#B45309"},
        "terminal": {"fill": "#F1F5F9", "stroke": "#475569", "text": "#334155", "icon": "#334155"},
        "note": {"fill": "#FEFCE8", "stroke": "#A16207", "text": "#713F12", "icon": "#A16207"},
        "default": {"fill": "#FFFFFF", "stroke": "#334155", "text": "#0F172A", "icon": "#334155"},
    }, {"fill": "#FFFFFF", "stroke": "#334155", "text": "#0F172A", "icon": "#334155"}),
    edge={"color": "#334155", "width": 1.6, "label_bg": "#FFFFFF",
          "label_color": "#334155", "label_size": 11, "arrow": 7},
    lane={"fill": "#F8FAFC", "stroke": "#CBD5E1", "label_color": "#475569", "label_size": 12,
          "band": True},
    group={"fill": "#F8FAFC", "stroke": "#64748B", "dash": "8 4",
           "label_color": "#334155", "label_size": 12},
    title={"color": "#0F172A", "size": 21, "sub_color": "#475569", "sub_size": 12},
    legend={"bg": "#FFFFFF", "border": "#CBD5E1", "text_color": "#334155", "size": 11},
    accent="#1E40AF",
    kinds={"write": "#0F766E", "read": "#1E40AF", "async": "#5B21B6", "loop": "#B45309",
           "event": "#9D174D", "return": "#475569"},
)

# --------------------------------------------------------------------------
# 10 · Cloud Fabric —— 云部署拓扑（归属 / 区域契约）
# --------------------------------------------------------------------------
STYLE_CLOUD_FABRIC = _style(
    sid="cloud-fabric", name="Cloud Fabric", name_zh="云部署拓扑", base="light",
    font=SANS, desc="中性云字形 + 区域/归属显式边界，部署图专用",
    best_for="多云部署、主备容灾、跨区复制拓扑",
    canvas={"bg": "#FFFFFF"},
    node={"fill": "#FFFFFF", "stroke": "#9AA8BD", "stroke_width": 1.3, "rx": 6,
          "title_size": 13, "title_color": "#1B2735",
          "desc_size": 11, "desc_color": "#5C6B80", "pad_x": 14, "pad_y": 11},
    types=_types({
        "frontend": {"fill": "#EEF4FB", "stroke": "#4F7FB5", "text": "#173049", "icon": "#2F6099"},
        "backend": {"fill": "#EDF6F1", "stroke": "#5C9578", "text": "#173A2A", "icon": "#3B7A5C"},
        "database": {"fill": "#FBF4E9", "stroke": "#B58A46", "text": "#4A3413", "icon": "#8F6A2E"},
        "cloud": {"fill": "#F1F3F8", "stroke": "#7B87A0", "text": "#232F42", "icon": "#4E5C75"},
        "security": {"fill": "#FCEEEE", "stroke": "#B55555", "text": "#4A1A1A", "icon": "#8F3B3B"},
        "messagebus": {"fill": "#F5EFF8", "stroke": "#8E6BA8", "text": "#381A4A", "icon": "#6B4A85"},
        "external": {"fill": "#F4F5F7", "stroke": "#8A93A3", "text": "#3B4453", "icon": "#5C6577"},
        "llm": {"fill": "#EFF1FA", "stroke": "#6B76B8", "text": "#242A52", "icon": "#4B5599"},
        "agent": {"fill": "#EAF4F7", "stroke": "#4F8CA0", "text": "#153641", "icon": "#2F7288"},
        "vector": {"fill": "#EAF5F3", "stroke": "#4F9A8E", "text": "#123B35", "icon": "#2F7A6E"},
        "storage": {"fill": "#FBF4E9", "stroke": "#B58A46", "text": "#4A3413", "icon": "#8F6A2E"},
        "user": {"fill": "#F4F5F7", "stroke": "#8A93A3", "text": "#1B2735", "icon": "#4E5A6B"},
        "process": {"fill": "#FFFFFF", "stroke": "#9AA8BD", "text": "#1B2735", "icon": "#5C6B80"},
        "decision": {"fill": "#FBF4E9", "stroke": "#B58A46", "text": "#4A3413", "icon": "#8F6A2E"},
        "terminal": {"fill": "#F4F5F7", "stroke": "#8A93A3", "text": "#1B2735", "icon": "#5C6577"},
        "note": {"fill": "#FCF7E9", "stroke": "#C4A559", "text": "#4A3A13", "icon": "#9A7F33"},
        "default": {"fill": "#FFFFFF", "stroke": "#9AA8BD", "text": "#1B2735", "icon": "#5C6B80"},
    }, {"fill": "#FFFFFF", "stroke": "#9AA8BD", "text": "#1B2735", "icon": "#5C6B80"}),
    edge={"color": "#6C7B92", "width": 1.5, "label_bg": "#FFFFFF",
          "label_color": "#43506699", "label_size": 11, "arrow": 7},
    lane={"fill": "#F7F9FC", "stroke": "#DCE3ED", "label_color": "#5C6B80", "label_size": 12,
          "band": True},
    group={"fill": "#F7F9FC", "stroke": "#8FA0B8", "dash": "9 5",
           "label_color": "#3B4453", "label_size": 12},
    title={"color": "#1B2735", "size": 21, "sub_color": "#5C6B80", "sub_size": 12},
    legend={"bg": "#FFFFFF", "border": "#DCE3ED", "text_color": "#435066", "size": 11},
    accent="#2F6099",
    kinds={"write": "#3B7A5C", "read": "#2F6099", "async": "#6B4A85", "loop": "#8F6A2E",
           "event": "#4E5C75", "return": "#8A93A3"},
)

# --------------------------------------------------------------------------
# 11 · Event Transit —— 事件轨（Topic / 站点 / 死信）
# --------------------------------------------------------------------------
STYLE_EVENT_TRANSIT = _style(
    sid="event-transit", name="Event Transit", name_zh="事件轨", base="light",
    font=SANS, desc="Topic 作轨道、处理器作站点、显式交汇点与 DLQ",
    best_for="事件驱动架构、消息队列流转、流处理管线",
    canvas={"bg": "#FFFFFF"},
    node={"fill": "#FFFFFF", "stroke": "#7C8AA5", "stroke_width": 1.3, "rx": 6,
          "title_size": 13, "title_color": "#20293A",
          "desc_size": 11, "desc_color": "#5B6880", "pad_x": 14, "pad_y": 11},
    types=_types({
        "frontend": {"fill": "#EEF3FB", "stroke": "#5578B0", "text": "#1B2C48", "icon": "#35589B"},
        "backend": {"fill": "#EDF7F2", "stroke": "#4F9B7C", "text": "#153A2C", "icon": "#2F7B5E"},
        "database": {"fill": "#FBF5E9", "stroke": "#B58F4C", "text": "#463413", "icon": "#8F6A2E"},
        "cloud": {"fill": "#F2F4F9", "stroke": "#7B87A0", "text": "#232F42", "icon": "#4E5C75"},
        "security": {"fill": "#FCEEEE", "stroke": "#B55555", "text": "#4A1A1A", "icon": "#8F3B3B"},
        "messagebus": {"fill": "#EFF0FB", "stroke": "#6A6FC4", "text": "#252A63", "icon": "#4A4FA8"},
        "external": {"fill": "#F4F5F7", "stroke": "#8A93A3", "text": "#3B4453", "icon": "#5C6577"},
        "llm": {"fill": "#F0F1FA", "stroke": "#6E77BC", "text": "#262B54", "icon": "#4C5599"},
        "agent": {"fill": "#EAF4F7", "stroke": "#4F8CA0", "text": "#153641", "icon": "#2F7288"},
        "vector": {"fill": "#EAF5F3", "stroke": "#4F9A8E", "text": "#123B35", "icon": "#2F7A6E"},
        "storage": {"fill": "#FBF5E9", "stroke": "#B58F4C", "text": "#463413", "icon": "#8F6A2E"},
        "user": {"fill": "#F4F5F7", "stroke": "#8A93A3", "text": "#20293A", "icon": "#4E5A6B"},
        "process": {"fill": "#FFFFFF", "stroke": "#7C8AA5", "text": "#20293A", "icon": "#5B6880"},
        "decision": {"fill": "#FBF5E9", "stroke": "#B58F4C", "text": "#463413", "icon": "#8F6A2E"},
        "terminal": {"fill": "#F4F5F7", "stroke": "#8A93A3", "text": "#20293A", "icon": "#5C6577"},
        "note": {"fill": "#FCF7E9", "stroke": "#C4A559", "text": "#4A3A13", "icon": "#9A7F33"},
        "default": {"fill": "#FFFFFF", "stroke": "#7C8AA5", "text": "#20293A", "icon": "#5B6880"},
    }, {"fill": "#FFFFFF", "stroke": "#7C8AA5", "text": "#20293A", "icon": "#5B6880"}),
    edge={"color": "#5B6880", "width": 1.5, "label_bg": "#FFFFFF",
          "label_color": "#46536B", "label_size": 11, "arrow": 7},
    lane={"fill": "#F8FAFD", "stroke": "#DCE4EF", "label_color": "#5B6880", "label_size": 12,
          "band": True},
    group={"fill": "#F8FAFD", "stroke": "#8A9AB5", "dash": "9 5",
           "label_color": "#3B4453", "label_size": 12},
    title={"color": "#20293A", "size": 21, "sub_color": "#5B6880", "sub_size": 12},
    legend={"bg": "#FFFFFF", "border": "#DCE4EF", "text_color": "#46536B", "size": 11},
    accent="#4A4FA8",
    kinds={"write": "#2F7B5E", "read": "#35589B", "async": "#4A4FA8", "loop": "#8F6A2E",
           "event": "#4E5C75", "return": "#8A93A3"},
)

# --------------------------------------------------------------------------
# 12 · Ops Pulse —— 运维脉搏（黄金信号 / 关键路径 / 追踪）
# --------------------------------------------------------------------------
STYLE_OPS_PULSE = _style(
    sid="ops-pulse", name="Ops Pulse", name_zh="运维脉搏", base="dark",
    font=MONO, desc="黄金信号配色 + 关键路径高亮 + 追踪瀑布，可观测性专用",
    best_for="可靠性分析、关键路径梳理、SLO 回顾",
    canvas={"bg": "#0D1117"},
    grid={"color": "#161B22", "step": 24, "major": 120},
    node={"fill": "#161B22", "stroke": "#30363D", "stroke_width": 1.2, "rx": 6,
          "title_size": 13, "title_color": "#E6EDF3",
          "desc_size": 11, "desc_color": "#8B949E", "pad_x": 14, "pad_y": 11},
    types=_types({
        "frontend": {"fill": "#10243A", "stroke": "#58A6FF", "text": "#CAE7FF", "icon": "#58A6FF"},
        "backend": {"fill": "#0E2A1E", "stroke": "#3FB950", "text": "#AFF3BE", "icon": "#3FB950"},
        "database": {"fill": "#2A1E08", "stroke": "#D29922", "text": "#F2E0A8", "icon": "#D29922"},
        "cloud": {"fill": "#1B1B33", "stroke": "#A371F7", "text": "#DCD0FA", "icon": "#A371F7"},
        "security": {"fill": "#2B1216", "stroke": "#F85149", "text": "#FFC9C4", "icon": "#F85149"},
        "messagebus": {"fill": "#2A1526", "stroke": "#DB61A2", "text": "#F9CFE6", "icon": "#DB61A2"},
        "external": {"fill": "#14181F", "stroke": "#484F58", "text": "#C9D1D9", "icon": "#8B949E"},
        "llm": {"fill": "#1A1A38", "stroke": "#8B8BE0", "text": "#D5D5F7", "icon": "#8B8BE0"},
        "agent": {"fill": "#0E2630", "stroke": "#39C5CF", "text": "#B6EEF2", "icon": "#39C5CF"},
        "vector": {"fill": "#0E2A28", "stroke": "#2DD4BF", "text": "#B2F2EA", "icon": "#2DD4BF"},
        "storage": {"fill": "#2A1E08", "stroke": "#D29922", "text": "#F2E0A8", "icon": "#D29922"},
        "user": {"fill": "#14181F", "stroke": "#6E7681", "text": "#E6EDF3", "icon": "#C9D1D9"},
        "process": {"fill": "#161B22", "stroke": "#30363D", "text": "#E6EDF3", "icon": "#8B949E"},
        "decision": {"fill": "#2A1E08", "stroke": "#D29922", "text": "#F2E0A8", "icon": "#D29922"},
        "terminal": {"fill": "#101317", "stroke": "#30363D", "text": "#C9D1D9", "icon": "#8B949E"},
        "note": {"fill": "#24200D", "stroke": "#9E8B33", "text": "#F0E5B8", "icon": "#C4AA42"},
        "default": {"fill": "#161B22", "stroke": "#30363D", "text": "#E6EDF3", "icon": "#8B949E"},
    }, {"fill": "#161B22", "stroke": "#30363D", "text": "#E6EDF3", "icon": "#8B949E"}),
    edge={"color": "#484F58", "width": 1.5, "label_bg": "#0D1117",
          "label_color": "#8B949E", "label_size": 11, "arrow": 7},
    lane={"fill": "#10151C", "stroke": "#21262D", "label_color": "#8B949E", "label_size": 12,
          "band": True},
    group={"fill": "#10151C", "stroke": "#30363D", "dash": "7 4",
           "label_color": "#8B949E", "label_size": 12},
    title={"color": "#E6EDF3", "size": 22, "sub_color": "#8B949E", "sub_size": 13},
    legend={"bg": "#10151C", "border": "#21262D", "text_color": "#8B949E", "size": 11},
    accent="#58A6FF",
    kinds={"write": "#3FB950", "read": "#58A6FF", "async": "#A371F7", "loop": "#D29922",
           "event": "#DB61A2", "return": "#6E7681"},
)


STYLES = {
    s["id"]: s for s in (
        STYLE_FLAT_ICON, STYLE_DARK_TERMINAL, STYLE_BLUEPRINT, STYLE_NOTION,
        STYLE_GLASS, STYLE_WARM_SAND, STYLE_CLEAN_TECH, STYLE_MIDNIGHT_GOLD,
        STYLE_C4_REVIEW, STYLE_CLOUD_FABRIC, STYLE_EVENT_TRANSIT, STYLE_OPS_PULSE,
    )
}

DEFAULT_STYLE = "flat-icon"

# 风格索引（SKILL.md 与 references/styles.md 同步维护）
STYLE_INDEX = [
    ("flat-icon", "扁平图标", "light", "系统架构、AI/Agent 架构、技术分享配图"),
    ("dark-terminal", "暗色终端", "dark", "工具调用链、Agent 执行流程、夜间演示"),
    ("blueprint", "工程蓝图", "dark", "微服务架构、部署拓扑、数据流管道"),
    ("notion-clean", "简约笔记", "light", "文档配图、知识库、层级结构图"),
    ("glassmorphism", "毛玻璃", "dark", "Multi-Agent 协作、发布会演示、大屏"),
    ("warm-sand", "暖砂纸感", "light", "系统分层架构、对外汇报、品牌化配图"),
    ("clean-tech", "净白科技", "light", "API 集成流、SDK 调用链、产品文档"),
    ("midnight-gold", "暗夜鎏金", "dark", "Agent 运行时架构、主视觉、白皮书"),
    ("c4-review", "架构评审", "light", "C4 容器级评审、技术方案评审会"),
    ("cloud-fabric", "云部署拓扑", "light", "多云部署、主备容灾、跨区复制"),
    ("event-transit", "事件轨", "light", "事件驱动架构、消息队列、流处理"),
    ("ops-pulse", "运维脉搏", "dark", "可靠性分析、关键路径、SLO 回顾"),
]

STYLE_ALIASES = {
    "1": "flat-icon", "2": "dark-terminal", "3": "blueprint", "4": "notion-clean",
    "5": "glassmorphism", "6": "warm-sand", "7": "clean-tech", "8": "midnight-gold",
    "9": "c4-review", "10": "cloud-fabric", "11": "event-transit", "12": "ops-pulse",
    "flat": "flat-icon", "terminal": "dark-terminal", "dark": "dark-terminal",
    "notion": "notion-clean", "glass": "glassmorphism", "claude": "warm-sand",
    "openai": "clean-tech", "luxury": "midnight-gold", "c4": "c4-review",
    "cloud": "cloud-fabric", "event": "event-transit", "ops": "ops-pulse",
}


def resolve_style(spec):
    """把用户给的风格名/编号解析成风格对象。"""
    if spec is None:
        return STYLES[DEFAULT_STYLE]
    if isinstance(spec, dict):
        base = STYLES.get(str(spec.get("id", DEFAULT_STYLE)), STYLES[DEFAULT_STYLE])
        merged = dict(base)
        for key in ("canvas", "grid", "node", "type_colors", "edge", "lane",
                    "group", "title", "legend"):
            if key in spec and isinstance(spec[key], dict) and isinstance(base.get(key), dict):
                m = dict(base[key])
                m.update(spec[key])
                merged[key] = m
            elif key in spec:
                merged[key] = spec[key]
        if "accent" in spec:
            merged["accent"] = spec["accent"]
        return merged
    key = str(spec).strip().lower()
    key = STYLE_ALIASES.get(key, key)
    return STYLES.get(key, STYLES[DEFAULT_STYLE])


def type_color(style, ntype):
    return style["type_colors"].get(ntype) or style["type_colors"]["default"]
