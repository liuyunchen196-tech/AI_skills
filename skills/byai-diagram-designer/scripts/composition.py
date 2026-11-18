#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
byai-diagram-designer · 构图质量契约

九项交付检查（artifact checks）：
  1 schema        结构完整性
  2 layout        画布边界与节点重叠
  3 spacing       间距与微段
  4 route         折弯数与正交性
  5 crossing      连线交叉
  6 label         标签净空
  7 typography    文字溢出与截断
  8 semantics     语义完整性（孤立节点 / 空标签 / 缺职责）
  9 delivery      产物结构

失败返回可机读回执：rule code + subject + evidence + supportedFixes。
纯标准库实现。
"""

from ir_schema import text_width, LAYOUT_MATRIX

MIN_NODE_GAP = 28.0      # 节点之间的最小净距
MIN_SEGMENT = 8.0        # 正交段最小长度（短于此为微段）
MAX_BENDS = 2            # 单边最大折弯
MAX_PRIMARY_NODES = 12   # 主路径节点上限
ARTIFACT_CHECKS = ["schema", "layout", "spacing", "route", "crossing",
                   "label", "typography", "semantics", "delivery"]


class Finding(object):
    def __init__(self, level, code, subject, message, evidence=None, fixes=None):
        self.level = level          # error | warning
        self.code = code
        self.subject = subject
        self.message = message
        self.evidence = evidence or {}
        self.fixes = fixes or []

    def to_dict(self):
        return {"level": self.level, "code": self.code, "subject": self.subject,
                "message": self.message, "evidence": self.evidence,
                "supportedFixes": self.fixes}


def rect_overlap(a, b, pad=0.0):
    return not (a[0] + a[2] + pad <= b[0] or b[0] + b[2] + pad <= a[0] or
                a[1] + a[3] + pad <= b[1] or b[1] + b[3] + pad <= a[1])


def rects_intersect(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def segment_rect_hit(p1, p2, rect, pad=0.0):
    """线段（仅水平/垂直）是否与矩形相交。"""
    x1, y1 = p1
    x2, y2 = p2
    rx, ry, rw, rh = rect
    rx -= pad
    ry -= pad
    rw += pad * 2
    rh += pad * 2
    lo_x, hi_x = sorted((x1, x2))
    lo_y, hi_y = sorted((y1, y2))
    return not (hi_x <= rx or rx + rw <= lo_x or hi_y <= ry or ry + rh <= lo_y)


def label_rect(edge, style):
    """连线标签的占位矩形。"""
    if not edge.get("label"):
        return None
    lx, ly, _ = edge["label_at"]
    size = style["edge"]["label_size"]
    tw = text_width(edge["label"], size)
    h = size + 8
    return (lx - tw / 2.0 - 4, ly - h / 2.0, tw + 8, h)


def _label_hits_node(lr, node_rects, skip):
    """找出与 label rect 重叠的所有节点（不是"只报告第一个"）。"""
    out = []
    if not lr:
        return out
    for nid, rr in node_rects.items():
        if nid in skip:
            continue
        if rects_intersect(lr, rr):
            out.append(nid)
    return out


def check(ir, geom, style, html=None):
    """执行全部构图检查，返回 (findings, report)。"""
    findings = []
    profile = (ir.get("meta") or {}).get("quality_profile", "showcase")
    canvas = geom["canvas"]
    nodes = ir["nodes"]
    by_id = ir["by_id"]

    # ---------- 1. schema（结构完整性由 ir_schema 负责，此处核对派生约束） ----------
    if not nodes and ir["layout"] != LAYOUT_MATRIX:
        findings.append(Finding("error", "NO_NODES", "$.nodes",
                                "图中没有节点", {}, ["至少添加 2 个节点"]))
    if len(nodes) == 1 and not ir["edges"]:
        findings.append(Finding("warning", "SINGLE_NODE", "$.nodes",
                                "只有一个节点且没有连线", {},
                                ["补充相关节点", "确认是否真的需要画图"]))

    # ---------- 2. layout：画布边界与节点重叠 ----------
    cw, ch = float(canvas["w"]), float(canvas["h"])
    for n in nodes:
        if n["x"] < -0.5 or n["y"] < -0.5 or n["x"] + n["w"] > cw + 0.5 \
                or n["y"] + n["h"] > ch + 0.5:
            findings.append(Finding(
                "error", "NODE_OUT_OF_CANVAS", "$.nodes[%s]" % n["id"],
                "节点超出画布边界",
                {"id": n["id"], "x": n["x"], "y": n["y"],
                 "w": n["w"], "h": n["h"], "canvas": [cw, ch]},
                ["增大 meta.viewBox", "减少节点", "缩短标签文字"]))

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            ra = (a["x"], a["y"], a["w"], a["h"])
            rb = (b["x"], b["y"], b["w"], b["h"])
            if rects_intersect(ra, rb):
                findings.append(Finding(
                    "error", "NODE_OVERLAP", "$.nodes[%s]" % a["id"],
                    "节点与 %s 重叠" % b["id"],
                    {"a": a["id"], "b": b["id"], "rectA": ra, "rectB": rb},
                    ["调整 row/col 分层", "缩短标签", "缩小节点尺寸"]))

    # ---------- 3. spacing：间距与微段 ----------
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            dx = max(a["x"] - (b["x"] + b["w"]), b["x"] - (a["x"] + a["w"]))
            dy = max(a["y"] - (b["y"] + b["h"]), b["y"] - (a["y"] + a["h"]))
            if dx >= 0 and dy < MIN_NODE_GAP and dy >= 0:
                findings.append(Finding(
                    "warning", "NODE_GAP_TOO_SMALL", "$.nodes[%s]" % a["id"],
                    "与 %s 的垂直净距 %.0fpx 小于 %dpx" % (b["id"], dy, MIN_NODE_GAP),
                    {"a": a["id"], "b": b["id"], "gap": round(dy, 1)},
                    ["增大分层间距", "减少该层节点"]))
            if dy >= 0 and 0 <= dx < MIN_NODE_GAP:
                findings.append(Finding(
                    "warning", "NODE_GAP_TOO_SMALL", "$.nodes[%s]" % a["id"],
                    "与 %s 的水平净距 %.0fpx 小于 %dpx" % (b["id"], dx, MIN_NODE_GAP),
                    {"a": a["id"], "b": b["id"], "gap": round(dx, 1)},
                    ["增大同一层的列间距", "换行缩短标签"]))

    for e in ir["edges"]:
        pts = e.get("points") or []
        for k in range(len(pts) - 1):
            x1, y1 = pts[k]
            x2, y2 = pts[k + 1]
            ln = abs(x2 - x1) + abs(y2 - y1)
            if 0 < ln < MIN_SEGMENT:
                findings.append(Finding(
                    "warning", "MICRO_SEGMENT", "$.edges[%s]" % e["id"],
                    "存在 %.1fpx 的微段，视觉上会像毛刺" % ln,
                    {"id": e["id"], "length": round(ln, 1)},
                    ["调整端口分散", "移动节点对齐端口", "改用 via 显式路由"]))

    # ---------- 4. route：折弯数 ----------
    for e in ir["edges"]:
        bends = e.get("bends", 0)
        # 跨越多层的连线必须走垂直通道绕开节点，允许 4 折；回边同理
        span = e.get("span", 1)
        if e.get("loop") or span > 1:
            limit = MAX_BENDS + 2
        else:
            limit = MAX_BENDS
        if bends > limit:
            hint = ("消除回边" if e.get("loop") else
                    "让相关节点落在相邻层" if span > 1 else "移动节点使端口接近对齐")
            findings.append(Finding(
                "warning", "TOO_MANY_BENDS", "$.edges[%s]" % e["id"],
                "折弯 %d 处，超过建议的 %d 处" % (bends, limit),
                {"id": e["id"], "bends": bends, "limit": limit, "span": span,
                 "source": e["source"], "target": e["target"]},
                ["调整节点层级" + hint, "用 via 指定更短路径",
                 "把细节移入节点描述而非新增连线"]))

    # ---------- 5. crossing：连线交叉 ----------
    crossings = ir.get("_crossings") or []
    if profile == "showcase" and crossings:
        seen = set()
        for c in crossings:
            key = tuple(sorted((c["edge"], c["other"])))
            if key in seen:
                continue
            seen.add(key)
            findings.append(Finding(
                "warning", "EDGE_CROSSING", "$.edges[%s]" % c["edge"],
                "与 %s 在 (%.0f, %.0f) 交叉" % (c["other"], c["x"], c["y"]),
                {"edge": c["edge"], "other": c["other"], "at": [c["x"], c["y"]]},
                ["调整同层节点顺序", "拆分过密的连线",
                 "把细节移入节点描述而非新增连线"]))
    for e in ir["edges"]:
        if e.get("bridges"):
            e["_has_bridge"] = True

    # ---------- 6. label：标签净空 ----------
    node_rects = {n["id"]: (n["x"], n["y"], n["w"], n["h"]) for n in nodes}
    for e in ir["edges"]:
        lr = label_rect(e, style)
        if not lr:
            continue
        if lr[0] < 2 or lr[0] + lr[2] > cw - 2:
            findings.append(Finding(
                "warning", "LABEL_OUT_OF_CANVAS", "$.edges[%s]" % e["id"],
                "标签超出画布左右边界",
                {"id": e["id"], "label": e["label"], "rect": [round(v, 1) for v in lr]},
                ["缩短标签文字", "增大画布宽度", "调整该边路由"]))
        for nid in _label_hits_node(lr, node_rects, (e["source"], e["target"])):
            findings.append(Finding(
                "warning", "LABEL_OVER_NODE", "$.edges[%s]" % e["id"],
                "标签与节点 %s 重叠" % nid,
                {"id": e["id"], "label": e["label"], "node": nid},
                ["错开标签垂直高度", "缩短标签文字", "调整该边路由",
                 "必要时把标签放到边线另一段"]))
        for other in ir["edges"]:
            if other["id"] == e["id"]:
                continue
            pts = other.get("points") or []
            for k in range(len(pts) - 1):
                if segment_rect_hit(pts[k], pts[k + 1], lr):
                    findings.append(Finding(
                        "warning", "LABEL_OVER_EDGE", "$.edges[%s]" % e["id"],
                        "标签与 %s 的连线重叠" % other["id"],
                        {"id": e["id"], "label": e["label"], "other": other["id"]},
                        ["错开两条边的路由高度", "缩短标签文字", "删除冗余标签"]))
                    break

    # ---------- 7. typography：文字溢出 ----------
    for n in nodes:
        size = style["node"]["title_size"]
        avail = n["w"] - style["node"]["pad_x"] * 2 - (26 if n.get("icon") else 0)
        tw = text_width(n["label"], size)
        if tw > avail + 1:
            findings.append(Finding(
                "error", "TITLE_OVERFLOW", "$.nodes[%s]" % n["id"],
                "标题宽度 %.0fpx 超出可用 %.0fpx" % (tw, avail),
                {"id": n["id"], "text": n["label"], "textWidth": round(tw, 1),
                 "available": round(avail, 1)},
                ["缩短标题", "显式设置更大的 w", "拆分节点"]))
        if n.get("desc"):
            dsize = style["node"]["desc_size"]
            davail = n["w"] - style["node"]["pad_x"] * 2
            dw = text_width(n["desc"], dsize)
            if dw > davail + 1:
                findings.append(Finding(
                    "warning", "DESC_OVERFLOW", "$.nodes[%s].desc" % n["id"],
                    "描述文字溢出节点宽度",
                    {"id": n["id"], "text": n["desc"], "textWidth": round(dw, 1)},
                    ["缩短描述", "显式设置更大的 w"]))

    # ---------- 8. semantics ----------
    degree = {n["id"]: 0 for n in nodes}
    for e in ir["edges"]:
        degree[e["source"]] = degree.get(e["source"], 0) + 1
        degree[e["target"]] = degree.get(e["target"], 0) + 1
    for n in nodes:
        if degree.get(n["id"], 0) == 0 and len(nodes) > 1:
            findings.append(Finding(
                "warning", "ISOLATED_NODE", "$.nodes[%s]" % n["id"],
                "孤立节点：没有任何连线",
                {"id": n["id"]},
                ["补上连线", "移入备注区", "删除该节点"]))

    if len(nodes) > MAX_PRIMARY_NODES:
        findings.append(Finding(
            "warning", "TOO_MANY_NODES", "$.nodes",
            "节点数 %d 超过主路径建议上限 %d，图会显得拥挤"
            % (len(nodes), MAX_PRIMARY_NODES),
            {"count": len(nodes), "limit": MAX_PRIMARY_NODES},
            ["把细节写进节点 desc 而非新增节点", "拆成多张图",
             "把次要节点折叠为一个分组"]))

    # C4 / 云部署 / 事件轨 / 运维脉搏 的工程契约：事实缺失则 fail closed
    eng = {"c4-review": ("responsibility", "tech"),
           "cloud-fabric": ("tech",),
           "event-transit": ("protocol",),
           "ops-pulse": ("tech",)}
    sid = style.get("id")
    if sid in eng:
        for n in nodes:
            missing = [f for f in eng[sid] if not n.get(f)]
            if missing:
                findings.append(Finding(
                    "error", "ENGINEERING_FACT_MISSING", "$.nodes[%s]" % n["id"],
                    "%s 风格要求节点显式声明 %s，不要臆造"
                    % (style.get("name_zh", sid), "/".join(missing)),
                    {"id": n["id"], "missing": missing, "style": sid},
                    ["补齐事实字段", "改用 flat-icon 等通用风格",
                     "向用户确认后回填"]))

    # ---------- 9. delivery ----------
    if html is not None:
        if not html.lstrip().startswith("<"):
            findings.append(Finding("error", "BAD_HTML", "$artifact",
                                    "产物不是合法 HTML", {}, ["重新渲染"]))
        if "<svg" not in html:
            findings.append(Finding("error", "NO_SVG", "$artifact",
                                    "产物中缺少 SVG 图层", {}, ["重新渲染"]))
        if "bd-svg" not in html:
            findings.append(Finding("warning", "NO_VIEWER_HOOK", "$artifact",
                                    "产物缺少查看器挂载点", {}, ["用 render 重新生成"]))

    # ---------- 汇总 ----------
    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warning"]

    def status_for(name):
        prefix = {"schema": ("IR_", "NO_NODES", "SINGLE_NODE", "DANGLING",
                             "DUPLICATE", "UNKNOWN", "BAD_", "EMPTY_GROUP"),
                  "layout": ("NODE_OUT_OF_CANVAS", "NODE_OVERLAP"),
                  "spacing": ("NODE_GAP_TOO_SMALL", "MICRO_SEGMENT"),
                  "route": ("TOO_MANY_BENDS",),
                  "crossing": ("EDGE_CROSSING",),
                  "label": ("LABEL_OVER_NODE", "LABEL_OVER_EDGE", "LABEL_OUT_OF_CANVAS"),
                  "typography": ("TITLE_OVERFLOW", "DESC_OVERFLOW"),
                  "semantics": ("ISOLATED_NODE", "TOO_MANY_NODES", "ENGINEERING_FACT_MISSING"),
                  "delivery": ("BAD_HTML", "NO_SVG", "NO_VIEWER_HOOK")}
        codes = prefix[name]
        hits = [f for f in findings if f.code.startswith(codes)]
        if any(f.level == "error" for f in hits):
            return "fail", len(hits)
        if hits:
            return "warn", len(hits)
        return "pass", 0

    checks = []
    for name in ARTIFACT_CHECKS:
        st, cnt = status_for(name)
        checks.append({"check": name, "status": st, "findings": cnt})

    report = {
        "quality_profile": profile,
        "artifactChecks": checks,
        "checksPassed": sum(1 for c in checks if c["status"] != "fail"),
        "checksTotal": len(checks),
        "errors": len(errors),
        "warnings": len(warnings),
        "nodes": len(nodes),
        "edges": len(ir["edges"]),
        "crossings": len(crossings),
        "canvas": {"w": canvas["w"], "h": canvas["h"]},
        "passed": not errors,
    }
    # 交付门槛：ERROR 必须清零；WARNING 是质量提示，须如实报告给用户
    report["passed"] = not errors
    report["showcaseReady"] = (not errors) and (not warnings)
    return findings, report
