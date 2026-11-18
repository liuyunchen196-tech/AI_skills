#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
diagram_emit.py —— 节点-连线图示生成器（Deck B 范式：矩形块 + 文字 + 对齐排版）。

输入: 内容 dict，含 `graph` 字段（节点 + 连线），而非固定填空模板。
    {
      "title": "数智园区总体架构",
      "subtitle": "集团 → 中台 → 应用",
      "graph": {
        "type": "tree",                 # 可选: tree / flow / grid / auto（缺省自动判）
        "nodes": [
          {"id": "root", "label": "集团总部", "sub": "战略与治理", "style": "highlight"},
          {"id": "t",    "label": "技术中台", "sub": "AI / 物联"},
          {"id": "b",    "label": "业务中台", "sub": "招商 / 运营"},
          {"id": "d",    "label": "数据平台", "sub": "湖仓一体"}
        ],
        "edges": [
          {"from": "root", "to": "t"},
          {"from": "root", "to": "b"},
          {"from": "root", "to": "d"}
        ]
      }
    }

输出: .slide 文件（合法 slidep JSX，可被 slidep lint / upsert-dsl）。

设计要点（还原 Deck B 的"人类按内容逻辑构图"纪律）:
- 统一块样式: 矩形块 + 居中文字 + 统一 tint 背景 + 圆角 8px（consulting_block）。
- 强调块: style="highlight" 用主色实底 + 白字（对应人类"关键节点加深"的手法）。
- 连线: 用 2px 细 Box 模拟（与 build_issue_tree 同源技术），不用图片/箭头素材。
- 不依赖绝对定位: 全部 flex + 细 Box 连线，slidep 安全。
- 复用 slide_emit 的 bs/ts/esc/header/footer/resole_palette。

拓扑自动判定 classify_topology():
- type 显式且合法 → 直接采用
- 否则: 有向无环且存在唯一根(入度为0) → tree；链状(每个节点出度≤1且线性) → flow；其余 → grid
"""

import json
from pathlib import Path
from typing import Optional

# 复用 slide_emit 的基础工具与调色板
try:
    from slide_emit import (
        bs, ts, esc, header, footer,
        resolve_palette, DEFAULT_PALETTE,
    )
except Exception:  # 独立运行时（脚本在同目录）
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from slide_emit import (
        bs, ts, esc, header, footer,
        resolve_palette, DEFAULT_PALETTE,
    )


# ============================================================
# 统一块样式（Deck B: 矩形块 + 文字 + 对齐 + 统一背景）
# ============================================================
def consulting_block(node: dict, p: dict, flex: str = "1",
                     min_h: int = 64) -> str:
    """单个节点块：矩形 + 居中文字 + 统一 tint（highlight 用主色实底白字）。

    不使用单边框（遵守 skill 禁用清单）；层次靠 tint 深浅 + 字号 + 强调实底。
    """
    label = node.get("label", "")
    sub = node.get("sub", "")
    hl = node.get("style") == "highlight"
    bg = p["primary"] if hl else p["accent_tint"]
    label_color = "#FFFFFF" if hl else p["text_main"]
    sub_color = "#FFFFFF" if hl else p["text_sub"]

    sub_block = ""
    if sub:
        sub_block = f"""
        <Text {ts(fontSize=12, color=sub_color, textAlign='center', lineHeight=1.3)}>
        {esc(sub)}
        </Text>"""
    return f"""
    <Box {bs(flex=flex, minHeight=min_h, background=bg, borderRadius=8,
            padding='14px 18px', flexDirection='column', gap=4,
            justifyContent='center', alignItems='center')}>
        <Text {ts(fontSize=16, fontWeight='bold', color=label_color, textAlign='center', lineHeight=1.25)}>
        {esc(label)}
        </Text>{sub_block}
    </Box>"""


def _vline(p, h=18, color=None):
    return f"<Box {bs(width=2, height=h, background=color or p['primary'])} />"


def _hline(p, w, color=None):
    return f"<Box {bs(width=w, height=2, background=color or p['primary'])} />"


# ============================================================
# 拓扑判定
# ============================================================
def classify_topology(graph: dict) -> str:
    explicit = str(graph.get("type", "")).strip().lower()
    if explicit in ("tree", "flow", "grid", "network"):
        return explicit if explicit != "network" else "grid"
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not nodes:
        return "grid"
    ids = [n.get("id") for n in nodes]
    indeg = {i: 0 for i in ids}
    outdeg = {i: 0 for i in ids}
    for e in edges:
        f, t = e.get("from"), e.get("to")
        if f in outdeg:
            outdeg[f] += 1
        if t in indeg:
            indeg[t] += 1
    roots = [i for i in ids if indeg[i] == 0]
    # 链状: 所有节点出度≤1 且 入度≤1（除可能的首尾）
    chain = all(outdeg[i] <= 1 and indeg[i] <= 1 for i in ids) and len(edges) >= 1
    if len(roots) == 1 and not chain:
        return "tree"
    if chain and len(roots) <= 1:
        return "flow"
    return "grid"


# ============================================================
# 三种布局 builder（均 flex + 细 Box 连线，无绝对定位）
# ============================================================
def _flow_layout(nodes, edges, p):
    """线性流程: 节点横向排列 + 蓝色 '>' 箭头。"""
    # 按 edges 顺序排，缺连接的尾部按 nodes 顺序补
    ordered = []
    seen = set()
    for e in edges:
        if e.get("from") not in seen:
            ordered.append(e.get("from")); seen.add(e.get("from"))
        if e.get("to") not in seen:
            ordered.append(e.get("to")); seen.add(e.get("to"))
    for n in nodes:
        if n.get("id") not in seen:
            ordered.append(n.get("id")); seen.add(n.get("id"))
    by_id = {n.get("id"): n for n in nodes}
    blocks = []
    for i, nid in enumerate(ordered):
        blocks.append(consulting_block(by_id.get(nid, {"label": str(nid)}), p))
        if i < len(ordered) - 1:
            arrow = "<Text " + ts(fontSize=22, color=p['primary'], fontWeight='bold') + ">&gt;</Text>"
            blocks.append(
                "<Box " + bs(width=28, justifyContent='center', alignItems='center') + ">" + arrow + "</Box>"
            )
    inner = ",".join(blocks)
    return f"<Box {bs(flexDirection='row', gap=12, alignItems='stretch', flexWrap='wrap')}>{inner}</Box>"


def _tree_layout(nodes, edges, p):
    """两层树: 根居上，子节点一行展开，细 Box 连线（仿 issue-tree 技术）。"""
    ids = [n.get("id") for n in nodes]
    by_id = {n.get("id"): n for n in nodes}
    # 根 = 入度0 的节点；若无则取第一个
    indeg = {i: 0 for i in ids}
    for e in edges:
        t = e.get("to")
        if t in indeg:
            indeg[t] += 1
    root_id = next((i for i in ids if indeg[i] == 0), ids[0])
    children = [e.get("to") for e in edges if e.get("from") == root_id]
    # 余下的（未在 children 且与 root 无直接边）也作为子节点兜底
    if not children:
        children = [i for i in ids if i != root_id]

    n = max(len(children), 1)
    gap = 16
    # 内容宽 1152 - gap*(n-1)，连线两端收窄到首末列中心
    line_margin = int((1152 - gap * (n - 1)) / n / 2)
    line_w = 1152 - 2 * line_margin

    root_block = consulting_block(by_id.get(root_id, {"label": str(root_id)}), p, flex="1")
    child_blocks = ",".join(
        consulting_block(by_id.get(c, {"label": str(c)}), p, flex="1") for c in children
    )
    stubs = ",".join(
        f"<Box {bs(flex=1, flexDirection='column', alignItems='center')}>{_vline(p, 16)}</Box>"
        for _ in children
    )
    return f"""
    <Box {bs(flexDirection='column', alignItems='stretch', gap=14)}>
        {root_block}
        <Box {bs(flexDirection='column', alignItems='center')}>
            {_vline(p, 14)}
            <Box {bs(width=line_w, height=2, background=p['primary'])} />
        </Box>
        <Box {bs(flexDirection='row', gap=gap)}>{stubs}</Box>
        <Box {bs(flexDirection='row', gap=gap)}>{child_blocks}</Box>
    </Box>"""


def _grid_layout(nodes, edges, p, cols=3):
    """网格: N 个块按 cols 列排布（并列关系）。"""
    rows = [nodes[i:i + cols] for i in range(0, len(nodes), cols)]
    row_strs = []
    for r in rows:
        cells = ",".join(consulting_block(n, p, flex="1") for n in r)
        row_strs.append(f"<Box {bs(flexDirection='row', gap=16)}>{cells}</Box>")
    return f"<Box {bs(flexDirection='column', gap=16)}>{','.join(row_strs)}</Box>"


# ============================================================
# 主入口
# ============================================================
def emit_node_link(content: dict, output_path: str = None,
                   palette=None, layout: Optional[str] = None) -> str:
    p = resolve_palette(palette)
    title = content.get("title", "")
    subtitle = content.get("subtitle", "")
    graph = content.get("graph") or {}
    if not graph:
        # 兼容直接传 nodes/edges 在顶层
        graph = {"nodes": content.get("nodes", []), "edges": content.get("edges", [])}

    kind = layout or graph.get("type") or classify_topology(graph)
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    if kind == "flow":
        body_inner = _flow_layout(nodes, edges, p)
    elif kind == "tree":
        body_inner = _tree_layout(nodes, edges, p)
    else:  # grid / network fallback
        body_inner = _grid_layout(nodes, edges, p, cols=graph.get("cols", 3))

    slide = f"""<Slide {bs(width=1280, height=720, background=p['surface'], padding='48px 64px 40px 64px', flexDirection='column')}>
{header(title, subtitle, p)}

<Box {bs(flexDirection='column', marginTop=36, flex=1, justifyContent='center')}>
{body_inner}
</Box>
{footer(p, page=content.get('page_label', '01 / 01'))}
</Slide>"""

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(slide, encoding="utf-8")
        return str(Path(output_path).resolve())
    return slide


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("用法: python diagram_emit.py <content.json> <output.slide> [layout]")
        sys.exit(1)
    c = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = sys.argv[2]
    forced = sys.argv[3] if len(sys.argv) > 3 else None
    written = emit_node_link(c, out, layout=forced)
    print(f"✓ 已写入: {written}  | 版式: diagram ({forced or 'auto'})")
