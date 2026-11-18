#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
byai-diagram-designer · 架构对比（Before / Delta / After）

对比两份已校验的 IR，输出机器可读的差异回执：
  added / removed / changed / moved / rerouted
只报告图中真实存在的差异，不做任何推断。
纯标准库实现。
"""

import json

from ir_schema import normalize


def _node_sig(n):
    return {
        "label": n.get("label"),
        "type": n.get("type"),
        "desc": n.get("desc"),
        "tech": n.get("tech"),
        "row": n.get("row"),
        "col": n.get("col"),
        "lane": n.get("lane"),
        "group": n.get("group"),
    }


def _edge_sig(e):
    return {"source": e.get("source"), "target": e.get("target"),
            "label": e.get("label"), "kind": e.get("kind")}


def diff(base_raw, head_raw):
    """对比两份 IR（dict 或已 normalize 的 ir）。返回差异回执 dict。"""
    base, e1 = normalize(base_raw)
    head, e2 = normalize(head_raw)
    if base is None or head is None:
        return {"error": "IR 无法解析", "baseErrors": [x.to_dict() for x in e1],
                "headErrors": [x.to_dict() for x in e2]}

    b_nodes = {n["id"]: n for n in base["nodes"]}
    h_nodes = {n["id"]: n for n in head["nodes"]}

    added = [{"id": i, "label": h_nodes[i]["label"], "type": h_nodes[i]["type"]}
             for i in h_nodes if i not in b_nodes]
    removed = [{"id": i, "label": b_nodes[i]["label"], "type": b_nodes[i]["type"]}
               for i in b_nodes if i not in h_nodes]

    changed, moved = [], []
    for i in h_nodes:
        if i not in b_nodes:
            continue
        bs, hs = _node_sig(b_nodes[i]), _node_sig(h_nodes[i])
        if bs["label"] != hs["label"] or bs["type"] != hs["type"] \
                or bs["desc"] != hs["desc"] or bs["tech"] != hs["tech"]:
            changed.append({"id": i, "label": hs["label"],
                            "before": {k: bs[k] for k in ("label", "type", "desc", "tech")},
                            "after": {k: hs[k] for k in ("label", "type", "desc", "tech")}})
        if bs["row"] != hs["row"] or bs["col"] != hs["col"] \
                or bs["lane"] != hs["lane"] or bs["group"] != hs["group"]:
            moved.append({"id": i, "label": hs["label"],
                          "before": {"row": bs["row"], "col": bs["col"],
                                     "lane": bs["lane"], "group": bs["group"]},
                          "after": {"row": hs["row"], "col": hs["col"],
                                    "lane": hs["lane"], "group": hs["group"]}})

    def esig(ir):
        out = {}
        for e in ir["edges"]:
            out[(e["source"], e["target"])] = e
        return out

    be, he = esig(base), esig(head)
    added_e = [{"key": "%s→%s" % (s, t), "source": s, "target": t,
                "label": he[(s, t)].get("label")}
               for (s, t) in he if (s, t) not in be]
    removed_e = [{"key": "%s→%s" % (s, t), "source": s, "target": t,
                  "label": be[(s, t)].get("label")}
                 for (s, t) in be if (s, t) not in he]
    rerouted = []
    for k in he:
        if k not in be:
            continue
        if _edge_sig(be[k])["label"] != _edge_sig(he[k])["label"] \
                or _edge_sig(be[k])["kind"] != _edge_sig(he[k])["kind"]:
            rerouted.append({"key": "%s→%s" % k,
                             "before": {"label": be[k].get("label"), "kind": be[k]["kind"]},
                             "after": {"label": he[k].get("label"), "kind": he[k]["kind"]}})

    return {
        "summary": {
            "nodesAdded": len(added), "nodesRemoved": len(removed),
            "nodesChanged": len(changed), "nodesMoved": len(moved),
            "edgesAdded": len(added_e), "edgesRemoved": len(removed_e),
            "edgesRerouted": len(rerouted),
            "identical": not (added or removed or changed or moved or
                              added_e or removed_e or rerouted),
        },
        "nodes": {"added": added, "removed": removed, "changed": changed, "moved": moved},
        "edges": {"added": added_e, "removed": removed_e, "rerouted": rerouted},
    }


def render_report(result, base_title="Before", head_title="After"):
    if "error" in result:
        return "<html><body><pre>%s</pre></body></html>" % json.dumps(
            result, ensure_ascii=False, indent=2)
    s = result["summary"]
    rows = []
    for n in result["nodes"]["added"]:
        rows.append(("新增节点", n["label"], "＋ %s" % n["type"]))
    for n in result["nodes"]["removed"]:
        rows.append(("删除节点", n["label"], "－ %s" % n["type"]))
    for n in result["nodes"]["changed"]:
        rows.append(("修改节点", n["label"],
                     "%s → %s" % (n["before"]["label"], n["after"]["label"])))
    for n in result["nodes"]["moved"]:
        rows.append(("移动节点", n["label"],
                     "第 %s 层 → 第 %s 层" % (n["before"]["row"], n["after"]["row"])))
    for e in result["edges"]["added"]:
        rows.append(("新增连线", e["key"], e.get("label") or ""))
    for e in result["edges"]["removed"]:
        rows.append(("删除连线", e["key"], e.get("label") or ""))
    for e in result["edges"]["rerouted"]:
        rows.append(("连线变更", e["key"],
                     "%s → %s" % (e["before"]["label"] or "（无标签）",
                                  e["after"]["label"] or "（无标签）")))

    body = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            r[0], r[1], (r[2] or "")) for r in rows) or \
        '<tr><td colspan="3" style="text-align:center;padding:24px;color:#6b7684">两份图纸完全一致</td></tr>'

    return """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>架构对比 · Delta</title><style>
body{margin:0;background:#f4f6f9;color:#1b2330;font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:36px 20px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:13px;color:#6b7684;font-weight:400;margin:0 0 20px}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px}
.stat{background:#fff;border:1px solid #e3e8ef;border-radius:10px;padding:10px 16px;min-width:96px}
.stat b{display:block;font-size:20px}.stat span{font-size:12px;color:#6b7684}
table{width:100%%;border-collapse:collapse;background:#fff;border:1px solid #e3e8ef;border-radius:10px;overflow:hidden}
th{background:#f7f9fc;text-align:left;font-size:12px;color:#6b7684;padding:10px 14px;font-weight:600}
td{padding:10px 14px;border-top:1px solid #eef1f6;font-size:13px}
</style></head><body><div class="wrap">
<h1>架构对比 · Delta</h1><h2>%s → %s</h2>
<div class="stats">
<div class="stat"><b>%d</b><span>新增节点</span></div>
<div class="stat"><b>%d</b><span>删除节点</span></div>
<div class="stat"><b>%d</b><span>修改节点</span></div>
<div class="stat"><b>%d</b><span>移动节点</span></div>
<div class="stat"><b>%d</b><span>新增连线</span></div>
<div class="stat"><b>%d</b><span>删除连线</span></div>
<div class="stat"><b>%d</b><span>连线变更</span></div>
</div>
<table><thead><tr><th style="width:110px">类型</th><th>对象</th><th>变化</th></tr></thead>
<tbody>%s</tbody></table></div></body></html>""" % (
        base_title, head_title, s["nodesAdded"], s["nodesRemoved"], s["nodesChanged"],
        s["nodesMoved"], s["edgesAdded"], s["edgesRemoved"], s["edgesRerouted"], body)
