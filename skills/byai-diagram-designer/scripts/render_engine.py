#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
byai-diagram-designer · 渲染引擎

IR + geometry → 内联 SVG → 自包含 HTML（含查看器）。
确定性：同样的 IR 永远产出同样的字节。
纯标准库实现。
"""

import json
import os

import icons as iconlib
from ir_schema import text_width, LAYOUT_SEQUENCE, LAYOUT_MATRIX, LAYOUT_RADIAL

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "templates", "viewer.html")


def esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# 形状
# ---------------------------------------------------------------------------
def _shape(node, style, tc):
    x, y, w, h = node["x"], node["y"], node["w"], node["h"]
    rx = style["node"]["rx"]
    sw = style["node"]["stroke_width"]
    fill = tc["fill"]
    stroke = tc["stroke"]
    if node["variant"] == "emphasis":
        sw = sw + 0.7
        stroke = style["accent"]
    elif node["variant"] == "security":
        stroke = "#DC2626" if style["base"] == "light" else "#F87171"
    dash = ' stroke-dasharray="7 4"' if node["variant"] == "dashed" else ""
    shape = node["shape"]
    common = 'fill="%s" stroke="%s" stroke-width="%s"%s' % (fill, stroke, sw, dash)

    if shape == "hexagon":
        c = min(18.0, w * 0.16)
        pts = "%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" % (
            x + c, y, x + w - c, y, x + w, y + h / 2.0,
            x + w - c, y + h, x + c, y + h, x, y + h / 2.0)
        return '<polygon points="%s" %s stroke-linejoin="round"/>' % (pts, common)
    if shape == "diamond":
        pts = "%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" % (
            x + w / 2.0, y, x + w, y + h / 2.0, x + w / 2.0, y + h, x, y + h / 2.0)
        return '<polygon points="%s" %s stroke-linejoin="round"/>' % (pts, common)
    if shape == "stadium":
        return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" %s/>' % (
            x, y, w, h, h / 2.0, common)
    if shape in ("cylinder", "ring-cylinder"):
        ry = min(11.0, h * 0.16)
        cx = x + w / 2.0
        d = ("M%.1f,%.1f V%.1f A%.1f,%.1f 0 0 0 %.1f,%.1f V%.1f Z"
             % (x, y + ry, y + h - ry, w / 2.0, ry, x + w, y + h - ry, y + ry))
        out = '<path d="%s" %s/>' % (d, common)
        out += '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" %s/>' % (
            cx, y + ry, w / 2.0, ry, common)
        if shape == "ring-cylinder":
            out += ('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="none" '
                    'stroke="%s" stroke-width="%.1f" stroke-dasharray="3 3" opacity="0.75"/>'
                    % (cx, y + h - ry, w / 2.0 * 0.72, ry * 0.72, stroke, sw))
        return out
    if shape == "double-rect":
        return ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" %s/>'
                '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" '
                'fill="none" stroke="%s" stroke-width="%.1f" opacity="0.7"/>'
                % (x, y, w, h, rx, common,
                   x + 4.5, y + 4.5, max(2.0, w - 9), max(2.0, h - 9), max(2.0, rx - 3),
                   stroke, sw))
    if shape == "cloud":
        d = ("M%.1f,%.1f A%.1f,%.1f 0 0 1 %.1f,%.1f A%.1f,%.1f 0 0 1 %.1f,%.1f "
             "A%.1f,%.1f 0 0 1 %.1f,%.1f A%.1f,%.1f 0 0 1 %.1f,%.1f Z"
             % (x + w * 0.18, y + h * 0.80, w * 0.17, h * 0.30, x + w * 0.18, y + h * 0.50,
                w * 0.23, h * 0.34, x + w * 0.55, y + h * 0.26,
                w * 0.21, h * 0.32, x + w * 0.86, y + h * 0.52,
                w * 0.17, h * 0.30, x + w * 0.84, y + h * 0.80))
        return '<path d="%s" %s stroke-linejoin="round"/>' % (d, common)
    if shape == "shield":
        d = ("M%.1f,%.1f L%.1f,%.1f V%.1f Q%.1f,%.1f %.1f,%.1f Q%.1f,%.1f %.1f,%.1f "
             "L%.1f,%.1f Z" % (x + w / 2.0, y, x + w, y + 10, y + h * 0.58,
                                     x + w / 2.0, y + h + 6, x + w / 2.0, y + h,
                                     x + w / 2.0, y + h + 6, x, y + h * 0.58,
                                     x, y + 10))
        return '<path d="%s" %s stroke-linejoin="round"/>' % (d, common)
    if shape == "person":
        return ('<circle cx="%.1f" cy="%.1f" r="%.1f" %s/>'
                '<path d="M%.1f,%.1f a%.1f,%.1f 0 0 0 %.1f,0" fill="none" stroke="%s" '
                'stroke-width="%.1f" stroke-linecap="round"/>'
                % (x + w / 2.0, y + 16, min(11.0, w * 0.09), common,
                   x + w * 0.32, y + h - 8, w * 0.18, h * 0.30, w * 0.36,
                   stroke, sw))
    if shape == "note":
        f = min(14.0, w * 0.10)
        pts = ("%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f"
               % (x, y, x + w - f, y, x + w, y + f, x + w, y + h, x, y + h))
        out = '<polygon points="%s" %s stroke-linejoin="round"/>' % (pts, common)
        out += ('<polyline points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" '
                'stroke="%s" stroke-width="%.1f"/>'
                % (x + w - f, y, x + w - f, y + f, x + w, y + f, stroke, sw))
        return out
    if shape == "rail":
        out = '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" %s/>' % (
            x, y, w, h, rx, common)
        cells = 3
        for i in range(1, cells):
            lx = x + w * i / float(cells)
            out += ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                    'stroke-width="%.1f" opacity="0.45"/>'
                    % (lx, y + 6, lx, y + h - 6, stroke, sw))
        return out
    if shape == "dashed-rect":
        return ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" '
                'stroke="%s" stroke-width="%.1f" stroke-dasharray="7 4"/>'
                % (x, y, w, h, rx, fill, stroke, sw))
    return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" %s/>' % (
        x, y, w, h, rx, common)


# ---------------------------------------------------------------------------
# 节点
# ---------------------------------------------------------------------------
def _node_svg(node, style):
    from styles import type_color
    tc = dict(type_color(style, node["type"]))
    x, y, w, h = node["x"], node["y"], node["w"], node["h"]
    pad_x = style["node"]["pad_x"]
    tsize = style["node"]["title_size"]
    dsize = style["node"]["desc_size"]

    lines = [(node["label"], tsize, tc["text"], "500")]
    if node.get("tech"):
        lines.append((node["tech"], dsize, tc["text"], "400"))
    if node.get("desc"):
        lines.append((node["desc"], dsize, style["node"]["desc_color"], "400"))
    for ml in (node.get("meta_lines") or []):
        lines.append((str(ml), dsize, style["node"]["desc_color"], "400"))
    if node.get("protocol"):
        lines.append((node["protocol"], dsize, tc["icon"], "400"))
    if node.get("responsibility"):
        lines.append((node["responsibility"], dsize, style["node"]["desc_color"], "400"))

    icon_name = node.get("icon") or iconlib.TYPE_ICON.get(node["type"])
    ic = iconlib.get_icon(icon_name, node["type"]) if icon_name else None
    icon_w = 22.0
    gap = 9.0 if ic else 0.0
    text_w = max(text_width(t[0], t[1]) for t in lines)
    content_w = icon_w + gap + text_w
    sx = x + max(pad_x, (w - content_w) / 2.0)
    tx = sx + icon_w + gap

    total_h = tsize * 1.35 + (len(lines) - 1) * (dsize + 6)
    sy = y + (h - total_h) / 2.0

    out = ['<g class="bd-node" data-id="%s">' % esc(node["id"])]
    out.append(_shape(node, style, tc))
    if ic:
        color = iconlib.brand_color(node.get("icon"), tc["icon"])
        out.append(
            '<g transform="translate(%.1f,%.1f) scale(%.3f)" fill="none" stroke="%s" '
            'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="%s"/></g>'
            % (sx, sy + total_h / 2.0 - icon_w / 2.0, icon_w / 24.0, color, ic[0]))
    by = sy
    for i, (txt, size, color, weight) in enumerate(lines):
        out.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" '
                   'font-weight="%s" fill="%s">%s</text>'
                   % (tx, by + size, style["font_family"], size, weight, color, esc(txt)))
        by += size * (1.35 if i == 0 else 1.0) + (6 if i else 0)
    if node.get("badge"):
        bw = text_width(str(node["badge"]), dsize - 1) + 12
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="16" rx="8" fill="%s"/>'
                   % (x + w - bw - 8, y - 8, bw, style["accent"]))
        out.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" fill="#FFFFFF" '
                   'text-anchor="middle">%s</text>'
                   % (x + w - bw / 2.0 - 8, y + 3.5, style["font_family"], dsize - 1,
                      esc(node["badge"])))
    out.append("</g>")
    return "".join(out)


# ---------------------------------------------------------------------------
# 连线
# ---------------------------------------------------------------------------
def _edge_path_d(e):
    pts = e.get("points") or []
    if not pts:
        return ""
    if e.get("curve"):
        (x1, y1), (x2, y2) = pts[0], pts[-1]
        mx = (x1 + x2) / 2.0
        return "M%.1f,%.1f Q%.1f,%.1f %.1f,%.1f" % (
            x1, y1, mx + (y2 - y1) * 0.12, (y1 + y2) / 2.0 - (x2 - x1) * 0.12, x2, y2)
    d = ["M%.1f,%.1f" % (pts[0][0], pts[0][1])]
    for i in range(1, len(pts)):
        x1, y1 = pts[i - 1]
        x2, y2 = pts[i]
        if abs(y1 - y2) < 0.5 and e.get("bridges"):
            # 水平段：插入跨接桥
            x_from, x_to = x1, x2
            bridges = sorted([b["x"] for b in e["bridges"]
                              if abs(b["y"] - y1) < 0.5
                              and min(x1, x2) + 3 < b["x"] < max(x1, x2) - 3])
            cur = x_from
            sweep = 1 if x_to > x_from else 0
            for bx in bridges:
                d.append("L%.1f,%.1f" % (bx - 5, y1))
                d.append("A5,5 0 0 %d %.1f,%.1f" % (sweep, bx + 5, y1))
                cur = bx + 5
            d.append("L%.1f,%.1f" % (x_to, y2))
        else:
            d.append("L%.1f,%.1f" % (x2, y2))
    return " ".join(d)


def _edges_svg(ir, style, markers):
    out = []
    for e in ir["edges"]:
        kind = style["kinds"].get(e["kind"], style["kinds"]["sync"])
        color = e.get("color") or kind["color"]
        dash = e.get("dashed")
        if dash is None:
            dash = kind.get("dash")
        width = style["edge"]["width"] * (1.25 if e.get("critical") else 1.0)
        mid = markers.setdefault(color, "bd-a%d" % len(markers))
        da = ' stroke-dasharray="%s"' % dash if dash else ""
        out.append('<g class="bd-edge" data-id="%s" data-source="%s" data-target="%s">'
                   % (esc(e["id"]), esc(e["source"]), esc(e["target"])))
        out.append('<path class="bd-edge-hit" d="%s" fill="none" stroke="transparent" '
                   'stroke-width="14"/>' % _edge_path_d(e))
        out.append('<path class="bd-edge-line" d="%s" fill="none" stroke="%s" '
                   'stroke-width="%.2f" stroke-linejoin="round" stroke-linecap="round"'
                   '%s marker-end="url(#%s)"/>'
                   % (_edge_path_d(e), color, width, da, mid))
        if e.get("label"):
            lx, ly, _ = e["label_at"]
            lsize = style["edge"]["label_size"]
            tw = text_width(e["label"], lsize)
            bg = style["edge"]["label_bg"]
            out.append('<rect class="bd-edge-label-bg" x="%.1f" y="%.1f" width="%.1f" '
                       'height="%.1f" rx="4" fill="%s" opacity="0.94"/>'
                       % (lx - tw / 2.0 - 5, ly - lsize / 2.0 - 4, tw + 10, lsize + 8, bg))
            out.append('<text class="bd-edge-label" x="%.1f" y="%.1f" text-anchor="middle" '
                       'font-family="%s" font-size="%s" fill="%s">%s</text>'
                       % (lx, ly + lsize * 0.36, style["font_family"], lsize,
                          style["edge"]["label_color"], esc(e["label"])))
        out.append("</g>")
    return "".join(out)


# ---------------------------------------------------------------------------
# 图例
# ---------------------------------------------------------------------------
def _legend_svg(ir, geom, style):
    if (ir.get("meta") or {}).get("legend") == "hidden":
        return ""
    used = {}
    for n in ir["nodes"]:
        used[n["type"]] = True
    kinds = {}
    for e in ir["edges"]:
        kinds[e["kind"]] = True
    items = []
    from styles import type_color
    for t in sorted(used):
        if t == "default":
            continue
        tc = type_color(style, t)
        items.append(("node", t, tc))
    for k in sorted(kinds):
        if k == "sync":
            continue
        items.append(("kind", k, style["kinds"].get(k, {})))
    if not items:
        return ""
    cw = geom["canvas"]["w"]
    x0 = 24.0
    y0 = geom["canvas"]["h"] - 26.0
    out = ['<g class="bd-legend">']
    cur = x0
    for typ, key, spec in items:
        label = _kind_label(key) if typ == "kind" else _type_label(key)
        tw = text_width(label, style["legend"]["size"])
        if cur + tw + 40 > cw - 24:
            break
        color = spec.get("color") if typ == "kind" else spec.get("stroke")
        if typ == "kind":
            dash = ' stroke-dasharray="%s"' % spec.get("dash") if spec.get("dash") else ""
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                       'stroke-width="1.6"%s/>' % (cur, y0, cur + 18, y0, color, dash))
        else:
            out.append('<rect x="%.1f" y="%.1f" width="14" height="12" rx="3" fill="%s" '
                       'stroke="%s" stroke-width="1"/>' % (cur, y0 - 6, spec.get("fill"),
                                                           color))
        out.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" fill="%s">%s</text>'
                   % (cur + 23, y0 + 4, style["font_family"], style["legend"]["size"],
                      style["legend"]["text_color"], esc(label)))
        cur += tw + 48
    out.append("</g>")
    return "".join(out)


def _type_label(t):
    return {"frontend": "前端", "backend": "服务", "database": "数据库", "storage": "存储",
            "cloud": "云资源", "security": "安全", "messagebus": "消息", "external": "外部",
            "llm": "大模型", "agent": "智能体", "vector": "向量库", "user": "用户",
            "process": "处理", "decision": "判断", "terminal": "终态",
            "note": "说明"}.get(t, t)


def _kind_label(k):
    return {"sync": "同步", "async": "异步", "write": "写入", "read": "读取",
            "loop": "循环", "flow": "流向", "event": "事件", "return": "返回"}.get(k, k)


# ---------------------------------------------------------------------------
# SVG 主体
# ---------------------------------------------------------------------------
def render_svg(ir, geom, style):
    canvas = geom["canvas"]
    cw, ch = float(canvas["w"]), float(canvas["h"])
    bg = style["canvas"]["bg"]
    parts = []
    parts.append(
        '<svg id="bd-svg" class="bd-svg" xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 %.0f %.0f" width="%.0f" height="%.0f" '
        'font-family="%s" role="img" aria-label="%s">'
        % (cw, ch, cw, ch, style["font_family"], esc(ir["meta"].get("title") or "技术图")))

    # defs：网格 + 箭头
    parts.append("<defs>")
    if style.get("grid"):
        g = style["grid"]
        parts.append('<pattern id="bd-grid" width="%s" height="%s" patternUnits="userSpaceOnUse">'
                     '<path d="M %s 0 L 0 0 0 %s" fill="none" stroke="%s" stroke-width="1"/>'
                     "</pattern>" % (g["step"], g["step"], g["step"], g["step"], g["color"]))
    markers = {}
    parts.append("</defs>")
    if style.get("grid"):
        parts.append('<rect width="%.0f" height="%.0f" fill="url(#bd-grid)"/>' % (cw, ch))

    # 泳道
    for b in (geom.get("bands") or []):
        if not b.get("visible"):
            continue
        parts.append('<rect x="%s" y="%.1f" width="%.1f" height="%.1f" rx="10" fill="%s" '
                     'stroke="%s" stroke-width="1"/>'
                     % (geom.get("lane_offset", 0) - 8, b["top"],
                        cw - (geom.get("lane_offset", 0) or 0) - 16,
                        b["bottom"] - b["top"], style["lane"]["fill"], style["lane"]["stroke"]))
        if b.get("label"):
            lsize = style["lane"]["label_size"]
            parts.append('<text x="14" y="%.1f" font-family="%s" font-size="%s" fill="%s">%s</text>'
                         % ((b["top"] + b["bottom"]) / 2.0 + lsize * 0.35,
                            style["font_family"], lsize,
                            style["lane"]["label_color"], esc(b["label"])))

    # 分组边界
    for g in (geom.get("groups") or []):
        dash = g.get("dash") or style["group"]["dash"]
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="12" fill="%s" '
                     'stroke="%s" stroke-width="1.2" stroke-dasharray="%s"/>'
                     % (g["x"], g["y"], g["w"], g["h"], style["group"]["fill"],
                        style["group"]["stroke"], dash))
        lsize = style["group"]["label_size"]
        parts.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" fill="%s">%s</text>'
                     % (g["x"] + 12, g["y"] + lsize + 2, style["font_family"], lsize,
                        style["group"]["label_color"], esc(g["label"])))

    # 时序图生命线
    if geom["layout"] == LAYOUT_SEQUENCE:
        for n in ir["nodes"]:
            cx = n["x"] + n["w"] / 2.0
            parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                         'stroke-width="1" stroke-dasharray="4 5" opacity="0.65"/>'
                         % (cx, n["y"] + n["h"] + 6, cx, n.get("lifeline_to", ch - 40),
                            style["edge"]["color"]))

    # 连线（先画连线，节点覆盖其上）
    parts.append('<g class="bd-edges">%s</g>' % _edges_svg(ir, style, markers))

    # 节点
    parts.append('<g class="bd-nodes">')
    for n in ir["nodes"]:
        parts.append(_node_svg(n, style))
    parts.append("</g>")

    # 矩阵 / 径向补充层
    if geom["layout"] == LAYOUT_MATRIX:
        parts.append(_matrix_svg(geom, style))
    parts.append(_legend_svg(ir, geom, style))
    parts.append("</svg>")

    svg = "".join(parts)
    # 注入箭头 marker（颜色数量已知后）
    defs = "".join(
        '<marker id="%s" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" '
        'markerHeight="6.5" orient="auto-start-reverse"><path d="M2 1.5 L8.5 5 L2 8.5" '
        'fill="none" stroke="%s" stroke-width="1.6" stroke-linecap="round" '
        'stroke-linejoin="round"/></marker>' % (mid, color)
        for color, mid in markers.items())
    svg = svg.replace("</defs>", defs + "</defs>")
    return svg


def _matrix_svg(geom, style):
    m = geom.get("matrix")
    if not m:
        return ""
    out = ['<g class="bd-matrix">']
    x0 = 48.0
    y0 = 96.0
    head_h = m["head_h"]
    col_w = m["col_w"]
    row_h = m["row_h"]
    rlw = m["row_label_w"]
    tsize = style["node"]["title_size"]
    dsize = style["node"]["desc_size"]

    out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="8" fill="%s" '
               'stroke="%s" stroke-width="1"/>'
               % (x0, y0, col_w * len(m["columns"]), head_h,
                  style["lane"]["fill"], style["lane"]["stroke"]))
    for ci, c in enumerate(m["columns"]):
        cx = x0 + col_w * ci + col_w / 2.0
        out.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-family="%s" '
                   'font-size="%s" font-weight="500" fill="%s">%s</text>'
                   % (cx, y0 + head_h / 2.0 + tsize * 0.35, style["font_family"], tsize,
                      style["node"]["title_color"], esc(c)))
    for cell in m["cells"]:
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" '
                   'stroke="%s" stroke-width="0.8" opacity="0.8"/>'
                   % (cell["x"], cell["y"], cell["w"], cell["h"], style["lane"]["stroke"]))
    for ri, r in enumerate(m["rows"]):
        cy = y0 + head_h + ri * row_h + row_h / 2.0
        out.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" fill="%s">%s</text>'
                   % (x0 - 12, cy + dsize * 0.35, style["font_family"], dsize,
                      style["node"]["title_color"], esc(r["label"])))
    for cell in m["cells"]:
        if not cell["text"]:
            continue
        out.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" fill="%s">%s</text>'
                   % (cell["x"] + 14, cell["y"] + cell["h"] / 2.0 + dsize * 0.35,
                      style["font_family"], dsize, style["node"]["desc_color"],
                      esc(cell["text"])))
    out.append("</g>")
    return "".join(out)


# ---------------------------------------------------------------------------
# 自包含 HTML
# ---------------------------------------------------------------------------
def render_html(ir, geom, style, svg):
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        tpl = f.read()

    meta = ir["meta"]
    data = {
        "nodes": [{"id": n["id"], "label": n["label"], "type": n["type"],
                   "desc": n.get("desc"), "tech": n.get("tech")} for n in ir["nodes"]],
        "edges": [{"id": e["id"], "source": e["source"], "target": e["target"],
                   "label": e.get("label"), "kind": e["kind"]} for e in ir["edges"]],
        "views": ir.get("views") or [],
    }
    cw, chh = float(geom["canvas"]["w"]), float(geom["canvas"]["h"])

    html = (tpl
            .replace("__LANG__", "zh-CN" if meta.get("locale", "").startswith("zh") else "en")
            .replace("__TITLE__", esc(meta.get("title") or "技术图"))
            .replace("__SUBTITLE__", esc(meta.get("subtitle") or ""))
            .replace("__SVG__", svg)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__CANVAS_W__", "%.0f" % cw)
            .replace("__CANVAS_H__", "%.0f" % chh)
            .replace("__STYLE_ID__", esc(style.get("id", "")))
            .replace("__DIAGRAM_TYPE__", esc(ir["diagram_type"]))
            .replace("__BG__", style["canvas"]["bg"])
            .replace("__BASE__", style["base"])
            .replace("__VIEW_OPTS__", _view_options(ir))
            .replace("__NODE_COUNT__", str(len(ir["nodes"])))
            .replace("__EDGE_COUNT__", str(len(ir["edges"]))))
    return html


def _view_options(ir):
    views = ir.get("views") or []
    if not views:
        return ""
    out = ['<option value="">语义视图…</option>']
    for v in views:
        out.append('<option value="%s">%s</option>' % (esc(v["id"]), esc(v["label"])))
    return "".join(out)
