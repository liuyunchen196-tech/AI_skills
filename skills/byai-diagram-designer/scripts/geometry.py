#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
byai-diagram-designer · 布局与几何路由

职责：
  1. 把 IR 中的节点放到画布上（分层 / 时序 / 矩阵 / 径向 四种布局）
  2. 泳道与分组边界框
  3. 正交连线路由：自动端口分散、方向契约、跨接桥
  4. 标签落位

输出 geometry：渲染引擎只负责把它画出来，不再做几何决策。
纯标准库实现。
"""

import math

from ir_schema import (LAYOUT_LAYERED, LAYOUT_SEQUENCE, LAYOUT_MATRIX,
                       LAYOUT_RADIAL, estimate_node_size, text_width,
                       MARGIN_X, MARGIN_Y, GAP_X, GAP_Y, LANE_PAD_Y,
                       LANE_LABEL_W, GROUP_PAD, NODE_H)

# 允许回边（循环）较多的图型
LOOP_FRIENDLY = {"lifecycle", "uml.state", "ai.tool-call", "ai.agentic-rag",
                 "workflow", "uml.activity"}

PORT_SPREAD = 18      # 同一节点上多条连线端口的最小错开距离
BRIDGE_R = 5          # 跨接桥半径
LANE_GAP = 34         # 泳道之间的额外间距


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _seg_intersect(a, b):
    """两条正交线段的交点（只处理水平×垂直）。a、b 为 (x1,y1,x2,y2)。"""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    a_h = abs(ay1 - ay2) < 0.01
    b_h = abs(by1 - by2) < 0.01
    if a_h == b_h:
        return None
    h, v = (a, b) if a_h else (b, a)
    hy = h[1]
    vx = v[0]
    hx1, hx2 = min(h[0], h[2]), max(h[0], h[2])
    vy1, vy2 = min(v[1], v[3]), max(v[1], v[3])
    eps = 0.5
    if hx1 - eps <= vx <= hx2 + eps and vy1 - eps <= hy <= vy2 + eps:
        if abs(vx - hx1) < eps or abs(vx - hx2) < eps:
            return None
        if abs(hy - vy1) < eps or abs(hy - vy2) < eps:
            return None
        return (round(vx, 2), round(hy, 2))
    return None


def count_bends(points):
    if len(points) < 3:
        return 0
    bends = 0
    for i in range(1, len(points) - 1):
        dx1 = points[i][0] - points[i - 1][0]
        dy1 = points[i][1] - points[i - 1][1]
        dx2 = points[i + 1][0] - points[i][0]
        dy2 = points[i + 1][1] - points[i][1]
        if abs(dx1) < 0.01 and abs(dy2) < 0.01:
            bends += 1
        elif abs(dy1) < 0.01 and abs(dx2) < 0.01:
            bends += 1
    return bends


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def build_geometry(ir, style):
    layout = ir["layout"]
    if layout == LAYOUT_SEQUENCE:
        return _layout_sequence(ir, style)
    if layout == LAYOUT_MATRIX:
        return _layout_matrix(ir, style)
    if layout == LAYOUT_RADIAL:
        return _layout_radial(ir, style)
    return _layout_layered(ir, style)


# ---------------------------------------------------------------------------
# 分层布局
# ---------------------------------------------------------------------------
def _layout_layered(ir, style):
    nodes = ir["nodes"]
    for n in nodes:
        n["w"], n["h"] = estimate_node_size(n, style)
        n["x"] = 0.0
        n["y"] = 0.0

    # --- 泳道分组 ---
    lane_order = []
    lane_seen = {}
    for i, l in enumerate(ir.get("lanes") or []):
        lane_order.append(l["id"])
        lane_seen[l["id"]] = i
    for n in nodes:
        lid = n.get("lane")
        if lid and lid not in lane_seen:
            lane_seen[lid] = len(lane_order)
            lane_order.append(lid)
    use_lanes = len(lane_seen) > 1 or any(n.get("lane") for n in nodes)
    if not use_lanes:
        lane_order = ["__all__"]
        lane_seen = {"__all__": 0}
        for n in nodes:
            n["lane"] = "__all__"

    has_lane_label = use_lanes and len(lane_order) > 1
    lane_offset = LANE_LABEL_W if has_lane_label else 0

    # --- 逐泳道、逐层摆放 ---
    bands = []
    cursor_y = MARGIN_Y
    max_row_width = 0
    seq = 0

    for lid in lane_order:
        members = [n for n in nodes if (n.get("lane") or "__all__") == lid]
        if not members:
            continue
        rows = {}
        for n in members:
            rows.setdefault(int(n["row"]), []).append(n)
        band_top = cursor_y
        for r in sorted(rows):
            items = sorted(rows[r], key=lambda n: float(n["col"]))
            total = sum(n["w"] for n in items) + GAP_X * (len(items) - 1)
            max_row_width = max(max_row_width, total)
            start_x = MARGIN_X + lane_offset + 0
            for n in items:
                n["x"] = start_x
                n["y"] = cursor_y
                n["_seq"] = seq
                start_x += n["w"] + GAP_X
            cursor_y += max(n["h"] for n in items) + GAP_Y
            seq += 1
        band_bottom = cursor_y - GAP_Y
        bands.append({"id": lid, "label": _lane_label(ir, lid),
                      "top": band_top - LANE_PAD_Y, "bottom": band_bottom + LANE_PAD_Y,
                      "visible": has_lane_label})
        cursor_y += LANE_GAP if has_lane_label else 0

    canvas_h = cursor_y - (LANE_GAP if has_lane_label else 0) - GAP_Y + MARGIN_Y
    canvas_w = max_row_width + MARGIN_X * 2 + lane_offset

    # 行边界：记录每一全局行（_seq）的上下沿与成员，供长连线找通道
    row_bounds = {}
    row_nodes = {}
    for n in nodes:
        sq = int(n.get("_seq", 0))
        row_nodes.setdefault(sq, []).append(n)
    for n in nodes:
        sq = int(n.get("_seq", 0))
        top = min(x["y"] for x in row_nodes[sq])
        bottom = max(x["y"] + x["h"] for x in row_nodes[sq])
        row_bounds[sq] = (top, bottom)
    ir["_row_bounds"] = row_bounds
    ir["_row_nodes"] = row_nodes

    # --- 行居中 ---
    rows_all = {}
    for n in nodes:
        key = (n.get("lane") or "__all__", int(n["row"]))
        rows_all.setdefault(key, []).append(n)
    for items in rows_all.values():
        total = sum(n["w"] for n in items) + GAP_X * (len(items) - 1)
        start_x = MARGIN_X + lane_offset + (canvas_w - MARGIN_X * 2 - lane_offset - total) / 2.0
        for n in sorted(items, key=lambda n: float(n["col"])):
            n["x"] = round(start_x, 1)
            start_x += n["w"] + GAP_X

    groups = _group_boxes(ir, nodes)
    _route_layered(ir, canvas_w, canvas_h)

    return {
        "canvas": {"w": round(canvas_w, 1), "h": round(canvas_h, 1)},
        "bands": bands,
        "groups": groups,
        "lane_offset": lane_offset,
        "layout": LAYOUT_LAYERED,
    }


def _lane_label(ir, lid):
    for l in ir.get("lanes") or []:
        if l["id"] == lid:
            return l["label"]
    return "" if lid == "__all__" else str(lid)


def _group_boxes(ir, nodes):
    by_id = ir["by_id"]
    out = []
    for g in ir.get("groups") or []:
        members = [by_id[m] for m in g["members"] if m in by_id]
        if not members:
            continue
        x1 = min(n["x"] for n in members)
        y1 = min(n["y"] for n in members)
        x2 = max(n["x"] + n["w"] for n in members)
        y2 = max(n["y"] + n["h"] for n in members)
        out.append({
            "id": g["id"], "label": g["label"], "kind": g.get("kind") or "boundary",
            "dash": g.get("dash"),
            "x": round(x1 - GROUP_PAD, 1), "y": round(y1 - GROUP_PAD - 8, 1),
            "w": round(x2 - x1 + GROUP_PAD * 2, 1),
            "h": round(y2 - y1 + GROUP_PAD * 2 + 8, 1),
        })
    return out


def _node_ports(ir):
    """自动端口分散：按对端位置从左到右分配端口，让走线天然不相交。

    关键：端口顺序必须与对端节点的水平顺序一致，否则同一节点的扇形出线
    会互相缠绕。同一节点上多条出/入连线再按 PORT_SPREAD 错开 x。
    """
    by_id = ir["by_id"]

    def cx_of(nid):
        n = by_id.get(nid)
        return n["x"] + n["w"] / 2.0 if n else 0.0

    out_groups = {}
    in_groups = {}
    for e in ir["edges"]:
        out_groups.setdefault(e["source"], []).append(e)
        in_groups.setdefault(e["target"], []).append(e)

    for src, items in out_groups.items():
        items.sort(key=lambda e: (cx_of(e["target"]), e["id"]))
        total = len(items)
        for i, e in enumerate(items):
            e["_sx"], e["_sy"] = _spread_port(by_id[src], i, total, "bottom")
            e["_out_count"] = total
    for tgt, items in in_groups.items():
        items.sort(key=lambda e: (cx_of(e["source"]), e["id"]))
        total = len(items)
        for i, e in enumerate(items):
            e["_tx"], e["_ty"] = _spread_port(by_id[tgt], i, total, "top")
            e["_in_count"] = total


def _spread_port(node, idx, total, side):
    cx = node["x"] + node["w"] / 2.0
    if total <= 1:
        return cx, (node["y"] + node["h"] if side == "bottom" else node["y"])
    step = min(PORT_SPREAD, max(8, (node["w"] - 24) / float(total)))
    offset = (idx - (total - 1) / 2.0) * step
    return round(cx + offset, 1), round(node["y"] + node["h"] if side == "bottom"
                                        else node["y"], 1)


def _dedupe(pts):
    """去掉重复点与共线中间点，减少虚假弯折。"""
    out = []
    for p in pts:
        if out and abs(p[0] - out[-1][0]) < 0.5 and abs(p[1] - out[-1][1]) < 0.5:
            continue
        out.append(p)
    if len(out) < 3:
        return out
    res = [out[0]]
    for i in range(1, len(out) - 1):
        a, b, c = res[-1], out[i], out[i + 1]
        collinear = (abs(a[0] - b[0]) < 0.5 and abs(b[0] - c[0]) < 0.5) or \
                    (abs(a[1] - b[1]) < 0.5 and abs(b[1] - c[1]) < 0.5)
        if not collinear:
            res.append(b)
    res.append(out[-1])
    return res


def _row_gap_y(ir, s_seq, t_seq, which):
    """返回源行下方 / 目标行上方的走线高度。"""
    rb = ir.get("_row_bounds") or {}
    if s_seq not in rb or t_seq not in rb:
        return None
    s_bottom = rb[s_seq][1]
    t_top = rb[t_seq][0]
    if which == "out":
        nxt = rb.get(s_seq + 1)
        if nxt:
            return s_bottom + (nxt[0] - s_bottom) * 0.42
        return t_top - 24
    prv = rb.get(t_seq - 1)
    if prv:
        return t_top - (t_top - prv[1]) * 0.42
    return s_bottom + 24


def _find_corridor(ir, sx, s_seq, t_seq):
    """在跨越多层的连线中间行里，找一条不被节点占用的垂直通道。"""
    rows = ir.get("_row_nodes") or {}
    between = [q for q in range(int(s_seq) + 1, int(t_seq)) if q in rows]
    if not between:
        return sx

    def free(x):
        for q in between:
            for n in rows[q]:
                if n["x"] - 9 <= x <= n["x"] + n["w"] + 9:
                    return False
        return True

    if free(sx):
        return sx
    cands = []
    for q in between:
        items = sorted(rows[q], key=lambda n: n["x"])
        for i in range(len(items) - 1):
            cands.append((items[i]["x"] + items[i]["w"] + items[i + 1]["x"]) / 2.0)
        cands.append(items[0]["x"] - 26)
        cands.append(items[-1]["x"] + items[-1]["w"] + 26)
    cands.sort(key=lambda c: abs(c - sx))
    for c in cands:
        if free(c):
            return round(c, 1)
    return round(max(cands, key=lambda c: abs(c - sx)), 1)


def _route_layered(ir, canvas_w, canvas_h):
    _node_ports(ir)
    by_id = ir["by_id"]
    allow_loop = ir["diagram_type"] in LOOP_FRIENDLY
    right_channel = 0.0
    left_channel = None
    for n in ir["nodes"]:
        right_channel = max(right_channel, n["x"] + n["w"])
        left_channel = n["x"] if left_channel is None else min(left_channel, n["x"])
    left_channel = (left_channel or 0.0) - 34
    right_channel += 34

    # 回边左右分道：奇数条走左侧、偶数条走右侧，避免全部挤在一侧互相缠绕
    back_seen = 0
    for e in ir["edges"]:
        if e.get("via"):
            continue
        s = by_id.get(e["source"])
        t = by_id.get(e["target"])
        if not s or not t:
            continue
        if int(t.get("_seq", t["row"])) < int(s.get("_seq", s["row"])):
            side = back_seen % 2
            e["_back_ch"] = left_channel if side == 0 else right_channel
            e["_back_off"] = (back_seen // 2) * 18.0
            back_seen += 1

    # 跨多层连线：按 (源行, 目标行) 分组，各组内错开出线高度，减少并行交叉
    long_group = {}
    short_group = {}
    for e in ir["edges"]:
        s = by_id.get(e["source"])
        t = by_id.get(e["target"])
        if not s or not t or e.get("via"):
            continue
        ss = int(s.get("_seq", s["row"]))
        ts = int(t.get("_seq", t["row"]))
        if ts - ss > 1:
            long_group.setdefault((ss, ts), []).append(e)
        elif ts - ss == 1:
            short_group.setdefault((ss, ts), []).append(e)

    long_offset = {}
    for key, items in long_group.items():
        n = len(items)
        for i, e in enumerate(items):
            long_offset[e["id"]] = (i - (n - 1) / 2.0) * 22.0

    # 同一间隙内的水平走线分层（轨道分配）
    # 约束一：区间不重叠的可共用一层
    # 约束二：若 j 的竖向段落在 i 的横向跨度内，j 必须比 i 更靠上，
    #         否则 j 的下行竖线会横穿 i 的横线
    track_of = {}
    for key, items in short_group.items():
        specs = []
        for e in items:
            a, b = e["_sx"], e["_tx"]
            specs.append({"e": e, "lo": min(a, b), "hi": max(a, b),
                          "port": e["_sx"], "track": None})
        for s in specs:
            s["inside"] = [o for o in specs
                           if o is not s and s["lo"] + 1.5 < o["port"] < s["hi"] - 1.5]
        specs.sort(key=lambda z: (len(z["inside"]), -(z["hi"] - z["lo"])))

        def overlaps(x, y):
            return not (x["hi"] + 14 <= y["lo"] or y["hi"] + 14 <= x["lo"])

        for s in specs:
            base = 0
            for o in s["inside"]:
                if o["track"] is not None:
                    base = max(base, o["track"])
            t = base
            while any(o["track"] == t and overlaps(s, o) for o in specs):
                t += 1
            s["track"] = t
        for s in specs:
            track_of[s["e"]["id"]] = s["track"]

    for e in ir["edges"]:
        s = by_id[e["source"]]
        t = by_id[e["target"]]
        sx, sy = e["_sx"], e["_sy"]
        tx, ty = e["_tx"], e["_ty"]
        # 用全局行序（_seq）而非 row 号判定，跨泳道时才不会误判为同层
        s_seq = int(s.get("_seq", s["row"]))
        t_seq = int(t.get("_seq", t["row"]))
        same = s_seq == t_seq
        back = t_seq < s_seq

        if e.get("via"):
            pts = [(sx, sy)] + [tuple(p) for p in e["via"]] + [(tx, ty)]
            e["points"] = _dedupe(pts)
            e["label_at"] = _label_at(e["points"])
            e["bends"] = count_bends(e["points"])
            continue

        if back:
            # 回边：绕左/右外侧通道回到上游
            sy = s["y"] + s["h"]
            ty = t["y"]
            ch = e.get("_back_ch", right_channel)
            off = e.get("_back_off", 0.0)
            y1 = sy + 26 + off
            y2 = ty - 26 - off
            pts = [(sx, sy), (sx, y1), (ch, y1), (ch, y2), (tx, y2), (tx, ty)]
            e["points"] = _dedupe(pts)
            e["label_at"] = _label_at(e["points"])
            e["bends"] = count_bends(e["points"])
            e["loop"] = True
            continue

        if same:
            # 同层相邻：侧面直连，0 折弯且不穿越任何节点
            ordered = sorted(ir.get("_row_nodes", {}).get(s_seq, []),
                             key=lambda n: n["x"])
            ids = [n["id"] for n in ordered]
            if s["id"] in ids and t["id"] in ids and abs(ids.index(s["id"])
                                                          - ids.index(t["id"])) == 1:
                if s["x"] < t["x"]:
                    x1, x2 = s["x"] + s["w"], t["x"]
                else:
                    x1, x2 = s["x"], t["x"] + t["w"]
                cy = round(s["y"] + s["h"] / 2.0, 1)
                pts = [(round(x1, 1), cy), (round(x2, 1), cy)]
            else:
                y_under = max(s["y"] + s["h"], t["y"] + t["h"]) + 30
                pts = [(sx, sy), (sx, y_under), (tx, y_under), (tx, ty)]
            e["points"] = _dedupe(pts)
            e["label_at"] = _label_at(e["points"])
            e["bends"] = count_bends(e["points"])
            continue

        # 常规下行：先在源行下方出线，再落到目标行上方
        y_out = _row_gap_y(ir, s_seq, t_seq, "out")
        y_in = _row_gap_y(ir, s_seq, t_seq, "in")
        span = t_seq - s_seq
        if span == 1:
            rb = ir.get("_row_bounds") or {}
            if s_seq in rb and t_seq in rb:
                gap = rb[t_seq][0] - rb[s_seq][1]
                base = rb[s_seq][1] + gap * (0.30 + 0.22 * track_of.get(e["id"], 0))
                mid = min(base, rb[s_seq][1] + gap * 0.78)
            else:
                mid = (sy + ty) / 2.0
            pts = [(sx, sy), (sx, round(mid, 1)), (tx, round(mid, 1)), (tx, ty)]
            if abs(sx - tx) < 1.0:
                pts = [(sx, sy), (tx, ty)]
        else:
            # 跨多层：先找一条不被节点占用的垂直通道，避免连线穿节点
            corridor = _find_corridor(ir, sx, s_seq, t_seq)
            yo = y_out if y_out is not None else sy + 30
            yi = y_in if y_in is not None else ty - 30
            off = long_offset.get(e["id"], 0.0)
            yo += off
            yi += off
            if abs(corridor - sx) < 1.0:
                pts = [(sx, sy), (sx, yi), (tx, yi), (tx, ty)]
            else:
                pts = [(sx, sy), (sx, yo), (corridor, yo), (corridor, yi),
                       (tx, yi), (tx, ty)]
        e["points"] = _dedupe(pts)
        e["label_at"] = _label_at(e["points"])
        e["bends"] = count_bends(e["points"])
        e["loop"] = False
        e["span"] = span

    _crossings(ir, allow_loop)
    _nudge_labels(ir)


def _nudge_labels(ir):
    """全局标签避让：冲突时整体下移，直到不与任何已放置标签重叠。"""
    from ir_schema import text_width as tw
    items = []
    for e in ir["edges"]:
        if not e.get("label") or not e.get("label_at"):
            continue
        cx, cy, hor = e["label_at"]
        w = tw(e["label"], 11) + 12
        h = 20.0
        items.append([e, cx - w / 2.0, cy - h / 2.0, w, h, hor])
    items.sort(key=lambda z: (z[2], z[1]))
    placed = []
    for e, x, y, w, h, hor in items:
        ny = y
        for _ in range(8):
            if not any(ny < p[1] + p[3] and p[1] < ny + h and
                       x < p[0] + p[2] and p[0] < x + w for p in placed):
                break
            ny += h + 4
        placed.append((x, ny, w, h))
        e["label_at"] = (x + w / 2.0, ny + h / 2.0, hor)


def _label_at(pts):
    """标签落在最长的一段上（优先水平段）。"""
    best = None
    best_len = -1
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        seg_len = abs(x2 - x1) + abs(y2 - y1)
        horizontal = abs(y2 - y1) < 0.5
        score = seg_len * (1.6 if horizontal else 1.0)
        if score > best_len:
            best_len = score
            best = ((x1 + x2) / 2.0, (y1 + y2) / 2.0, horizontal)
    if best is None:
        return (pts[0][0], pts[0][1], True)
    return best


def _crossings(ir, allow_loop):
    """计算正交段交叉点，用于绘制跨接桥。"""
    segs = []
    for e in ir["edges"]:
        pts = e["points"]
        for i in range(len(pts) - 1):
            segs.append((e["id"], pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]))
    crosses = []
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            if segs[i][0] == segs[j][0]:
                continue
            pt = _seg_intersect(segs[i][1:], segs[j][1:])
            if pt:
                horizontal_first = abs(segs[i][2] - segs[i][4]) < 0.01
                crosses.append({"x": pt[0], "y": pt[1],
                                "edge": segs[i][0] if horizontal_first else segs[j][0],
                                "other": segs[j][0] if horizontal_first else segs[i][0]})
    ir["_crossings"] = crosses
    for e in ir["edges"]:
        e["bridges"] = [c for c in crosses if c["edge"] == e["id"]]


# ---------------------------------------------------------------------------
# 时序图
# ---------------------------------------------------------------------------
def _layout_sequence(ir, style):
    nodes = ir["nodes"]
    for n in nodes:
        n["w"], n["h"] = estimate_node_size(n, style)
        n["w"] = max(n["w"], 128)
        n["h"] = max(n["h"], 48)

    step = max(n["w"] for n in nodes) + GAP_X
    total_w = sum(n["w"] for n in nodes) + GAP_X * (len(nodes) - 1)
    start_x = MARGIN_X
    for n in nodes:
        n["x"] = round(start_x, 1)
        n["y"] = round(float(MARGIN_Y), 1)
        start_x += n["w"] + GAP_X

    msgs = sorted(ir["edges"], key=lambda e: (e.get("order") if e.get("order") is not None
                                              else 10**6, e["id"]))
    head_bottom = MARGIN_Y + max(n["h"] for n in nodes)
    y = head_bottom + 46
    for i, e in enumerate(msgs):
        s = ir["by_id"][e["source"]]
        t = ir["by_id"][e["target"]]
        x1 = s["x"] + s["w"] / 2.0
        x2 = t["x"] + t["w"] / 2.0
        e["_seq_y"] = round(y, 1)
        if abs(x1 - x2) < 1.0:
            e["points"] = [(x1, y), (x1 + 46, y), (x1 + 46, y + 26), (x1, y + 26)]
            e["label_at"] = (x1 + 56, y + 6, True)
            e["bends"] = 2
            y += 62
        else:
            e["points"] = [(round(x1, 1), round(y, 1)), (round(x2, 1), round(y, 1))]
            e["label_at"] = ((x1 + x2) / 2.0, y, True)
            e["bends"] = 0
            y += 48
        e["bridges"] = []

    canvas_h = y + 40 + MARGIN_Y
    canvas_w = max(total_w + MARGIN_X * 2, 640)
    for n in nodes:
        n["lifeline_to"] = round(canvas_h - MARGIN_Y, 1)
    ir["_crossings"] = []
    return {"canvas": {"w": round(canvas_w, 1), "h": round(canvas_h, 1)},
            "bands": [], "groups": [], "lane_offset": 0, "layout": LAYOUT_SEQUENCE}


# ---------------------------------------------------------------------------
# 对比矩阵
# ---------------------------------------------------------------------------
def _layout_matrix(ir, style):
    mtx = ir.get("matrix") or {}
    cols = [str(c) for c in (mtx.get("columns") or [])]
    rows = []
    for r in (mtx.get("rows") or []):
        if isinstance(r, dict):
            rows.append({"label": str(r.get("label") or ""),
                         "cells": [str(c) for c in (r.get("cells") or [])]})
        else:
            rows.append({"label": str(r), "cells": []})

    title_size = style["node"]["title_size"]
    desc_size = style["node"]["desc_size"]
    row_label_w = 100.0
    for r in rows:
        row_label_w = max(row_label_w, text_width(r["label"], desc_size) + 24)
    col_w = 168.0
    for c in cols:
        col_w = max(col_w, text_width(c, title_size) + 32)
    for r in rows:
        for c in r["cells"]:
            col_w = max(col_w, min(320, text_width(c, desc_size) + 28))
    row_h = 56.0
    head_h = 62.0

    canvas_w = MARGIN_X * 2 + row_label_w + col_w * max(len(cols), 1)
    canvas_h = MARGIN_Y + head_h + row_h * max(len(rows), 1) + MARGIN_Y

    cells = []
    for ri, r in enumerate(rows):
        y = MARGIN_Y + head_h + ri * row_h
        for ci in range(len(cols)):
            x = MARGIN_X + row_label_w + ci * col_w
            val = r["cells"][ci] if ci < len(r["cells"]) else ""
            cells.append({"x": round(x, 1), "y": round(y, 1), "w": round(col_w, 1),
                          "h": round(row_h, 1), "text": val, "row": ri, "col": ci})

    for n in ir["nodes"]:
        n["x"] = MARGIN_X
        n["y"] = MARGIN_Y
        n["w"] = row_label_w
        n["h"] = head_h
    ir["_crossings"] = []
    return {"canvas": {"w": round(canvas_w, 1), "h": round(canvas_h, 1)},
            "bands": [], "groups": [], "lane_offset": 0, "layout": LAYOUT_MATRIX,
            "matrix": {"columns": cols, "rows": rows, "cells": cells,
                       "row_label_w": round(row_label_w, 1), "col_w": round(col_w, 1),
                       "row_h": round(row_h, 1), "head_h": round(head_h, 1)}}


# ---------------------------------------------------------------------------
# 思维导图（径向）
# ---------------------------------------------------------------------------
def _layout_radial(ir, style):
    nodes = ir["nodes"]
    for n in nodes:
        n["w"], n["h"] = estimate_node_size(n, style)
    if not nodes:
        return {"canvas": {"w": 800, "h": 600}, "bands": [], "groups": [],
                "lane_offset": 0, "layout": LAYOUT_RADIAL}

    by_id = ir["by_id"]
    root = nodes[0]
    children = [n for n in nodes[1:]]
    cx, cy = 420.0, 380.0
    root["x"] = cx - root["w"] / 2.0
    root["y"] = cy - root["h"] / 2.0

    if not children:
        return {"canvas": {"w": 840, "h": 760}, "bands": [], "groups": [],
                "lane_offset": 0, "layout": LAYOUT_RADIAL}

    n = len(children)
    radius = max(200.0, 62.0 * n / math.pi * 0.62 + 120)
    for i, nd in enumerate(children):
        ang = -math.pi / 2.0 + (2 * math.pi * i) / n
        nd["x"] = round(cx + radius * math.cos(ang) - nd["w"] / 2.0, 1)
        nd["y"] = round(cy + radius * math.sin(ang) - nd["h"] / 2.0, 1)
        nd["_angle"] = ang

    min_x = min(n["x"] for n in nodes)
    max_x = max(n["x"] + n["w"] for n in nodes)
    min_y = min(n["y"] for n in nodes)
    max_y = max(n["y"] + n["h"] for n in nodes)
    canvas_w = (max_x - min_x) + MARGIN_X * 2
    canvas_h = (max_y - min_y) + MARGIN_Y * 2

    for e in ir["edges"]:
        s = by_id[e["source"]]
        t = by_id[e["target"]]
        if s is root or t is root:
            other = t if s is root else s
            ang = other.get("_angle", 0)
            if s is root:
                x1 = cx + math.cos(ang) * (root["w"] / 2.0 + 4)
                y1 = cy + math.sin(ang) * (root["h"] / 2.0 + 4)
                x2 = other["x"] + other["w"] / 2.0 - math.cos(ang) * (other["w"] / 2.0)
                y2 = other["y"] + other["h"] / 2.0 - math.sin(ang) * (other["h"] / 2.0)
            else:
                x1 = s["x"] + s["w"] / 2.0
                y1 = s["y"] + s["h"] / 2.0
                x2 = cx + math.cos(ang) * (root["w"] / 2.0 + 4)
                y2 = cy + math.sin(ang) * (root["h"] / 2.0 + 4)
            e["points"] = [(round(x1, 1), round(y1, 1)), (round(x2, 1), round(y2, 1))]
            e["curve"] = True
        else:
            e["points"] = [(s["x"] + s["w"] / 2.0, s["y"] + s["h"] / 2.0),
                           (t["x"] + t["w"] / 2.0, t["y"] + t["h"] / 2.0)]
            e["curve"] = True
        e["bends"] = 0
        e["bridges"] = []
        e["label_at"] = ((e["points"][0][0] + e["points"][1][0]) / 2.0,
                         (e["points"][0][1] + e["points"][1][1]) / 2.0, True)
    ir["_crossings"] = []
    return {"canvas": {"w": round(canvas_w, 1), "h": round(canvas_h, 1)},
            "bands": [], "groups": [], "lane_offset": 0, "layout": LAYOUT_RADIAL,
            "center": (round(cx, 1), round(cy, 1))}
