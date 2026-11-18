#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
byai-diagram-designer · IR 规范化（diagram IR schema v1）

负责：图型识别 → 字段补全 → 自动分层布局 → 节点尺寸估算。
输出一个"渲染就绪"的 ir 对象，渲染引擎不再做任何推断。
纯标准库实现。
"""

import re

SCHEMA_VERSION = "1"

# ---------------------------------------------------------------------------
# 图型 → 布局引擎
# ---------------------------------------------------------------------------
LAYOUT_LAYERED = "layered"    # 自上而下分层
LAYOUT_SEQUENCE = "sequence"  # 生命线 + 消息
LAYOUT_MATRIX = "matrix"      # 对比矩阵
LAYOUT_RADIAL = "radial"      # 思维导图

DIAGRAM_TYPES = {
    # 基础
    "architecture": LAYOUT_LAYERED,
    "dataflow": LAYOUT_LAYERED,
    "workflow": LAYOUT_LAYERED,
    "lifecycle": LAYOUT_LAYERED,
    "sequence": LAYOUT_SEQUENCE,
    "comparison": LAYOUT_MATRIX,
    "mindmap": LAYOUT_RADIAL,
    # AI / Agent 领域模式
    "ai.rag": LAYOUT_LAYERED,
    "ai.agentic-rag": LAYOUT_LAYERED,
    "ai.agentic-search": LAYOUT_LAYERED,
    "ai.memory": LAYOUT_LAYERED,
    "ai.memory-types": LAYOUT_LAYERED,
    "ai.multi-agent": LAYOUT_LAYERED,
    "ai.tool-call": LAYOUT_LAYERED,
    # UML
    "uml.class": LAYOUT_LAYERED,
    "uml.component": LAYOUT_LAYERED,
    "uml.deployment": LAYOUT_LAYERED,
    "uml.package": LAYOUT_LAYERED,
    "uml.usecase": LAYOUT_LAYERED,
    "uml.activity": LAYOUT_LAYERED,
    "uml.state": LAYOUT_LAYERED,
    "uml.sequence": LAYOUT_SEQUENCE,
    "uml.er": LAYOUT_LAYERED,
}

TYPE_ALIASES = {
    "arch": "architecture", "system": "architecture", "microservice": "architecture",
    "架构": "architecture", "架构图": "architecture", "系统架构": "architecture",
    "data-flow": "dataflow", "data_flow": "dataflow", "pipeline": "dataflow",
    "数据流": "dataflow", "数据管道": "dataflow", "血缘": "dataflow",
    "flow": "workflow", "flowchart": "workflow", "process": "workflow", "runbook": "workflow",
    "流程": "workflow", "流程图": "workflow", "审批": "workflow",
    "state": "lifecycle", "state-machine": "lifecycle", "fsm": "lifecycle",
    "状态": "lifecycle", "状态机": "lifecycle", "生命周期": "lifecycle",
    "seq": "sequence", "时序": "sequence", "时序图": "sequence", "调用链": "sequence",
    "compare": "comparison", "matrix": "comparison", "对比": "comparison", "矩阵": "comparison",
    "mind-map": "mindmap", "mind_map": "mindmap", "思维导图": "mindmap", "概念图": "mindmap",
    "rag": "ai.rag", "agentic-rag": "ai.agentic-rag", "agentic-search": "ai.agentic-search",
    "mem0": "ai.memory", "memory": "ai.memory", "记忆": "ai.memory",
    "multi-agent": "ai.multi-agent", "多智能体": "ai.multi-agent",
    "tool-call": "ai.tool-call", "工具调用": "ai.tool-call",
}

# ---------------------------------------------------------------------------
# 节点语义类型 → 形状
# ---------------------------------------------------------------------------
TYPE_SHAPES = {
    "frontend": "rect",
    "backend": "rect",
    "database": "cylinder",
    "storage": "cylinder",
    "cloud": "cloud",
    "security": "shield",
    "messagebus": "rail",
    "external": "dashed-rect",
    "llm": "double-rect",
    "agent": "hexagon",
    "vector": "ring-cylinder",
    "user": "person",
    "process": "rect",
    "decision": "diamond",
    "terminal": "stadium",
    "note": "note",
    "default": "rect",
}

VALID_TYPES = set(TYPE_SHAPES) - {"default"}
VALID_VARIANTS = {"default", "emphasis", "security", "dashed"}
VALID_KINDS = {"sync", "async", "write", "read", "loop", "flow", "event", "return"}
VALID_ROUTES = {"auto", "orthogonal", "straight", "curve"}

# 布局常量（像素）
NODE_W = 168
NODE_H = 64
NODE_H_DESC = 78
NODE_H_LINES = 18
GAP_X = 56
GAP_Y = 92
LANE_PAD_Y = 26
LANE_LABEL_W = 96
MARGIN_X = 48
MARGIN_Y = 96
GROUP_PAD = 20


def text_width(text, size):
    """估算文本宽度：CJK 按 1.0 em，ASCII 按 0.56 em。"""
    if not text:
        return 0.0
    w = 0.0
    for ch in str(text):
        w += size * (1.0 if ord(ch) > 0x2E80 else 0.56)
    return w


def _slug(text, used):
    base = re.sub(r"[^0-9a-zA-Z]+", "-", str(text or "n").strip().lower()).strip("-")
    if not base:
        base = "n"
    if not base[0].isalpha():
        base = "n" + base
    cid, i = base, 2
    while cid in used:
        cid = "%s-%d" % (base, i)
        i += 1
    used.add(cid)
    return cid


class IRError(object):
    def __init__(self, code, subject, message, evidence=None, fixes=None):
        self.code = code
        self.subject = subject
        self.message = message
        self.evidence = evidence or {}
        self.fixes = fixes or []

    def to_dict(self):
        # level 必须与契约 finding 对齐：_print_human / JSON 消费方都按 f["level"] 分支，
        # 缺这个键会让合并后的 findings 列表在打印时 KeyError。
        return {"code": self.code, "subject": self.subject, "message": self.message,
                "level": "error", "evidence": self.evidence,
                "supportedFixes": self.fixes}


def normalize_diagram_type(value):
    if not value:
        return "architecture", False
    key = str(value).strip().lower()
    if key in DIAGRAM_TYPES:
        return key, True
    if key in TYPE_ALIASES:
        return TYPE_ALIASES[key], True
    return "architecture", False


def normalize(raw):
    """把用户/上游给的 IR 规范成渲染就绪结构。

    返回 (ir, errors)。errors 中的 IRError 是可机读的修复回执。
    """
    errors = []
    if not isinstance(raw, dict):
        return None, [IRError("IR_NOT_OBJECT", "$", "IR 顶层必须是 JSON 对象",
                              {"got": type(raw).__name__}, ["把 IR 改成 JSON 对象"])]

    ir = {}
    ir["schema_version"] = str(raw.get("schema_version") or SCHEMA_VERSION)

    dtype, ok = normalize_diagram_type(raw.get("diagram_type") or raw.get("type"))
    if raw.get("diagram_type") and not ok:
        errors.append(IRError(
            "UNKNOWN_DIAGRAM_TYPE", "$.diagram_type",
            "未识别的图型，已回退为 architecture",
            {"given": raw.get("diagram_type")},
            ["改用受支持的图型标识", "查阅 references/diagram-types.md"]))
    ir["diagram_type"] = dtype
    ir["layout"] = DIAGRAM_TYPES[dtype]

    # ---- meta ----
    m = raw.get("meta") or {}
    meta = {
        "title": m.get("title") or "",
        "subtitle": m.get("subtitle") or None,
        "style": m.get("style") or "flat-icon",
        "theme": (m.get("theme") or "auto").lower(),
        "locale": m.get("locale") or "zh-CN",
        "animation": m.get("animation"),
        "quality_profile": m.get("quality_profile") or "showcase",
        "legend": m.get("legend") or "auto",
        "viewBox": m.get("viewBox"),
        "brand": m.get("brand"),
    }
    if meta["quality_profile"] not in ("showcase", "standard"):
        errors.append(IRError(
            "BAD_QUALITY_PROFILE", "$.meta.quality_profile",
            "quality_profile 只能是 showcase 或 standard",
            {"given": meta["quality_profile"]}, ["设为 showcase", "设为 standard"]))
        meta["quality_profile"] = "showcase"
    ir["meta"] = meta

    # ---- nodes ----
    used = set()
    nodes = []
    by_id = {}
    for i, n in enumerate(raw.get("nodes") or []):
        if not isinstance(n, dict):
            errors.append(IRError("NODE_NOT_OBJECT", "$.nodes[%d]" % i,
                                  "节点必须是对象", {}, ["改为 JSON 对象"]))
            continue
        nid = n.get("id") or _slug(n.get("label"), used)
        if nid in by_id:
            errors.append(IRError(
                "DUPLICATE_NODE_ID", "$.nodes[%d].id" % i, "节点 id 重复",
                {"id": nid}, ["改成唯一 id"]))
            nid = _slug(nid, used)
        used.add(nid)
        # 缺 type 是合法的（IR 规范：节点至少 id + label），静默回退 default；
        # 只有显式写了不受支持的 type 才报 ERROR——否则报错的修复建议
        # 「省略 type 字段」会反过来触发同一个 ERROR，自相矛盾。
        if n.get("type"):
            ntype = str(n["type"]).lower()
            if ntype not in VALID_TYPES:
                errors.append(IRError(
                    "UNKNOWN_NODE_TYPE", "$.nodes[%d].type" % i,
                    "未识别的节点类型，已回退为 default",
                    {"id": nid, "given": ntype},
                    ["使用受支持的语义类型", "省略 type 字段"]))
                ntype = "default"
        else:
            ntype = "default"
        variant = (n.get("variant") or "default").lower()
        if variant not in VALID_VARIANTS:
            errors.append(IRError(
                "UNKNOWN_VARIANT", "$.nodes[%d].variant" % i,
                "variant 只能是 default/emphasis/security/dashed",
                {"id": nid, "given": variant}, ["改为受支持的 variant"]))
            variant = "default"
        node = {
            "id": nid,
            "label": str(n.get("label") or nid),
            "type": ntype,
            "shape": n.get("shape") or TYPE_SHAPES.get(ntype, "rect"),
            "variant": variant,
            "icon": n.get("icon"),
            "desc": n.get("desc") or n.get("description"),
            "tech": n.get("tech") or n.get("technology"),
            "protocol": n.get("protocol"),
            "responsibility": n.get("responsibility"),
            "meta_lines": n.get("meta_lines") or [],
            "lane": n.get("lane"),
            "group": n.get("group"),
            "row": n.get("row"),
            "col": n.get("col"),
            "badge": n.get("badge"),
            "brand": n.get("brand"),
            "w": n.get("w"),
            "h": n.get("h"),
            "emphasis": bool(n.get("emphasis")),
        }
        if node["emphasis"] and variant == "default":
            node["variant"] = "emphasis"
        nodes.append(node)
        by_id[nid] = node

    if not nodes and ir["layout"] != LAYOUT_MATRIX:
        errors.append(IRError(
            "NO_NODES", "$.nodes", "IR 没有任何节点",
            {}, ["至少添加 2 个节点"]))
        return None, errors

    # ---- edges ----
    eids = set()
    edges = []
    for i, e in enumerate(raw.get("edges") or []):
        if not isinstance(e, dict):
            errors.append(IRError("EDGE_NOT_OBJECT", "$.edges[%d]" % i,
                                  "连线必须是对象", {}, ["改为 JSON 对象"]))
            continue
        src, dst = e.get("source"), e.get("target")
        if src not in by_id:
            errors.append(IRError(
                "DANGLING_SOURCE", "$.edges[%d].source" % i, "连线起点不存在",
                {"source": src}, ["指向已有节点 id", "补上该节点"]))
            continue
        if dst not in by_id:
            errors.append(IRError(
                "DANGLING_TARGET", "$.edges[%d].target" % i, "连线终点不存在",
                {"target": dst}, ["指向已有节点 id", "补上该节点"]))
            continue
        kind = (e.get("kind") or "sync").lower()
        if kind not in VALID_KINDS:
            errors.append(IRError(
                "UNKNOWN_EDGE_KIND", "$.edges[%d].kind" % i,
                "未识别的关系语义，已回退为 sync",
                {"given": kind},
                ["使用 sync/async/write/read/loop/flow/event/return"]))
            kind = "sync"
        route = (e.get("route") or "auto").lower()
        if route not in VALID_ROUTES:
            errors.append(IRError(
                "UNKNOWN_ROUTE", "$.edges[%d].route" % i,
                "route 只能是 auto/orthogonal/straight/curve",
                {"given": route}, ["改为 auto"]))
            route = "auto"
        eid = e.get("id") or _slug("%s-%s" % (src, dst), eids)
        if eid in eids:
            eid = _slug(eid, eids)
        eids.add(eid)
        via = e.get("via")
        if via is not None:
            if not isinstance(via, list) or len(via) % 2 != 0:
                errors.append(IRError(
                    "BAD_VIA", "$.edges[%d].via" % i,
                    "via 必须是 [x1,y1,x2,y2,...] 的偶数长度数组",
                    {"given": via}, ["改为坐标对数组", "删除 via 交给自动路由"]))
                via = None
            else:
                via = [(float(via[k]), float(via[k + 1])) for k in range(0, len(via), 2)]
        edges.append({
            "id": eid,
            "source": src,
            "target": dst,
            "label": e.get("label"),
            "kind": kind,
            "route": route,
            "via": via,
            "source_side": e.get("source_side"),
            "target_side": e.get("target_side"),
            "dashed": e.get("dashed"),
            "color": e.get("color"),
            "critical": bool(e.get("critical")),
            "order": e.get("order"),
        })
    ir["edges"] = edges
    ir["by_id"] = by_id

    # ---- lanes / groups / views ----
    lanes = []
    for i, l in enumerate(raw.get("lanes") or []):
        if isinstance(l, str):
            lanes.append({"id": l, "label": l, "order": i})
        elif isinstance(l, dict):
            lid = l.get("id") or l.get("label") or ("lane-%d" % i)
            lanes.append({"id": lid, "label": l.get("label") or str(lid),
                          "order": l.get("order", i), "kind": l.get("kind")})
    ir["lanes"] = lanes

    groups = []
    for i, g in enumerate(raw.get("groups") or []):
        if not isinstance(g, dict):
            continue
        gid = g.get("id") or ("group-%d" % i)
        members = [x for x in (g.get("members") or []) if x in by_id]
        for x in (g.get("members") or []):
            if x not in by_id:
                errors.append(IRError(
                    "DANGLING_GROUP_MEMBER", "$.groups[%d].members" % i,
                    "分组引用了不存在的节点", {"group": gid, "node": x},
                    ["移除该成员", "补上该节点"]))
                continue
            by_id[x]["group"] = gid
        if not members:
            errors.append(IRError(
                "EMPTY_GROUP", "$.groups[%d]" % i, "分组没有有效成员",
                {"group": gid}, ["补上成员", "删除该分组"]))
            continue
        groups.append({"id": gid, "label": g.get("label") or str(gid),
                       "kind": g.get("kind") or "boundary",
                       "members": members, "dash": g.get("dash")})
    ir["groups"] = groups

    views = []
    for i, v in enumerate(raw.get("views") or []):
        if not isinstance(v, dict):
            continue
        vn = [x for x in (v.get("nodes") or []) if x in by_id]
        if not vn:
            continue
        views.append({"id": v.get("id") or ("view-%d" % i),
                      "label": v.get("label") or (v.get("id") or ("视图 %d" % (i + 1))),
                      "nodes": vn})
    ir["views"] = views[:5]

    ir["notes"] = [n for n in (raw.get("notes") or []) if isinstance(n, dict)]

    # ---- 矩阵型补充 ----
    if ir["layout"] == LAYOUT_MATRIX:
        ir["matrix"] = {
            "columns": raw.get("columns") or [],
            "rows": raw.get("rows") or [],
            "cells": raw.get("cells") or [],
        }
        if not ir["matrix"]["columns"]:
            errors.append(IRError(
                "MATRIX_NO_COLUMNS", "$.columns", "对比矩阵缺少 columns",
                {}, ["补充 columns：每个被对比的系统一列"]))

    # ---- 自动分层 ----
    ir["nodes"] = nodes
    _auto_layer(ir, errors)
    return ir, errors


def _auto_layer(ir, errors):
    """为未显式指定 row/col 的节点计算层级与列序。"""
    nodes = ir["nodes"]
    by_id = ir["by_id"]
    layout = ir["layout"]

    if layout == LAYOUT_RADIAL:
        for i, n in enumerate(nodes):
            n["row"] = 1 if i else 0
            n["col"] = i
        return
    if layout == LAYOUT_MATRIX:
        for i, n in enumerate(nodes):
            n["row"] = 0
            n["col"] = i
        return

    preds = {n["id"]: [] for n in nodes}
    succs = {n["id"]: [] for n in nodes}
    for e in ir["edges"]:
        if e["target"] in succs.get(e["source"], {}):
            pass
        preds.setdefault(e["target"], []).append(e["source"])
        succs.setdefault(e["source"], []).append(e["target"])

    # 最长路径分层（带环保护）
    row = {}
    explicit = {n["id"]: int(n["row"]) for n in nodes if n["row"] is not None}
    indeg = {n["id"]: len(preds.get(n["id"], [])) for n in nodes}
    frontier = [n["id"] for n in nodes if indeg[n["id"]] == 0]
    # 显式 row 优先
    for nid, r in explicit.items():
        row[nid] = r
    unresolved = [n["id"] for n in nodes if n["id"] not in row]

    if frontier:
        queue = list(frontier)
        seen = 0
        while queue and seen < len(nodes) * 4:
            seen += 1
            nid = queue.pop(0)
            base = row.get(nid)
            if base is None:
                base = max([row.get(p, -1) for p in preds.get(nid, [])] + [-1]) + 1
                row[nid] = base
            for s in succs.get(nid, []):
                cand = base + 1
                if row.get(s) is None or (s not in explicit and cand > row[s]):
                    row[s] = cand
                    queue.append(s)
    for nid in unresolved:
        if nid not in row:
            row[nid] = max([row.get(p, -1) for p in preds.get(nid, [])] + [-1]) + 1
    for n in nodes:
        n["row"] = int(n["row"]) if n["row"] is not None else row.get(n["id"], 0)

    # 层内列序：显式 col 优先，否则按前驱重心排序
    rows = {}
    for n in nodes:
        rows.setdefault(n["row"], []).append(n)

    def bary(n):
        """前驱重心。优先用本趟已算出的 prev，col 可能尚未赋值。"""

        def col_of(pid):
            if pid in prev:
                return prev[pid]
            p = by_id.get(pid)
            if p is not None and p.get("col") is not None:
                return float(p["col"])
            return 0.0

        ps = [p for p in preds.get(n["id"], []) if p in by_id]
        if not ps:
            return float(n["col"]) if n.get("col") is not None else 0.0
        return sum(col_of(p) for p in ps) / float(len(ps))

    ordered_rows = sorted(rows)
    prev = {}
    for r in ordered_rows:
        items = rows[r]
        fixed = [n for n in items if n.get("col") is not None]
        free = [n for n in items if n.get("col") is None]
        for n in fixed:
            prev[n["id"]] = float(n["col"])
        free.sort(key=lambda n: (bary(n), n["label"]))
        taken = set(int(n["col"]) for n in fixed)
        cursor = 0
        for n in free:
            cursor = max(cursor, int(round(bary(n))))
            while cursor in taken:
                cursor += 1
            taken.add(cursor)
            prev[n["id"]] = float(cursor)
            cursor += 1
        # 归一化：把固定与自由列合并成 0..k 的连续列
    for r in ordered_rows:
        items = sorted(rows[r], key=lambda n: (float(n["col"]) if n["col"] is not None
                                               else prev.get(n["id"], 0.0)))
        for idx, n in enumerate(items):
            n["_order"] = idx
        rows[r] = items
    # 统一层内最大列宽，保证整齐
    max_cols = max(len(v) for v in rows.values()) if rows else 1
    for r, items in rows.items():
        span = max_cols
        for idx, n in enumerate(items):
            pos = (idx + 1) * (span + 1) / float(len(items) + 1) - 0.5
            n["col"] = pos
    ir["_rows"] = {str(k): [n["id"] for n in v] for k, v in rows.items()}


def estimate_node_size(node, style):
    """按标签/描述/技术栈估算节点尺寸。"""
    title_size = style["node"]["title_size"]
    desc_size = style["node"]["desc_size"]
    pad_x = style["node"]["pad_x"]
    pad_y = style["node"]["pad_y"]
    icon_w = 26 if node.get("icon") else 0

    w = text_width(node["label"], title_size) + icon_w + pad_x * 2
    lines = 1
    if node.get("tech"):
        w = max(w, text_width(node["tech"], desc_size) + icon_w + pad_x * 2)
        lines += 1
    if node.get("desc"):
        w = max(w, text_width(node["desc"], desc_size) + icon_w + pad_x * 2)
        lines += 1
    lines += len(node.get("meta_lines") or [])
    for ml in (node.get("meta_lines") or []):
        w = max(w, text_width(str(ml), desc_size) + pad_x * 2)

    w = max(NODE_W, min(300, w))
    h = pad_y * 2 + title_size * 1.35 + (lines - 1) * (desc_size + 5)
    if node["shape"] in ("cylinder", "ring-cylinder"):
        h += 6
    if node["shape"] == "diamond":
        w = max(w, 150)
        h = max(h, 74)
    h = max(NODE_H, h)
    if node.get("w"):
        w = float(node["w"])
    if node.get("h"):
        h = float(node["h"])
    return round(w, 1), round(h, 1)
