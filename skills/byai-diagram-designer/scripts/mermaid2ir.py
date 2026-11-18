#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
byai-diagram-designer · Mermaid → IR 转换

只读取 Mermaid 的「拓扑与语义」，不保留 Mermaid 的样式。
支持：flowchart / graph、sequenceDiagram、stateDiagram(-v2)。
纯标准库实现。
"""

import re

# 一行上的节点定义：id + (shape-spec)
#   A[Label]  A[Label]  A(Label)  A((Label))  A{Label}  A[[Label]]
# 用平衡括号扫描，避免嵌套括号导致的截断
_OPEN_CHARS = "[({"
_CLOSE_CHARS = "])}"
_PAIR = {"[": "]", "(": ")", "{": "}"}


def _scan_shape(line, start):
    """从 start 位置起，扫描一个完整的 "形状描述"，返回 (shape_text, end_pos)。

    形状描述 = 开括号 + 内容 + 对应闭括号（允许嵌套）。
    若 start 不是开括号，则返回 (None, start)。
    """
    if start >= len(line):
        return None, start
    ch = line[start]
    if ch not in _OPEN_CHARS:
        return None, start
    stack = [_PAIR[ch]]
    i = start + 1
    while i < len(line):
        c = line[i]
        if c in _OPEN_CHARS:
            stack.append(_PAIR[c])
        elif c == '"':
            # 跨过带引号的字符串
            i += 1
            while i < len(line) and line[i] != '"':
                if line[i] == '\\':
                    i += 2
                else:
                    i += 1
        elif c in _CLOSE_CHARS:
            want = stack[-1]
            if c == want:
                stack.pop()
                if not stack:
                    return line[start:i + 1], i + 1
            else:
                # 错位闭括号：放弃，交给后续匹配
                return None, start
        i += 1
    return None, start


def _strip_pipes(line):
    """把 mermaid 箭头之间的 |label| 段去掉，留下 bare 箭头链。

    转换前先把 `A -->|label| B` 转成 `A --> B`，避免 label 内的字符
    被误当成节点 id 扫进 nodes。
    """
    return re.sub(r"\|[^|\n]*\|", "", line)


def _find_all_nodes(line):
    """找出行里所有 (id, shape_spec, end) 三元组，按出现顺序。

    id 必须符合 [A-Za-z0-9_.-]+，且 id 之后紧跟 shape_spec。
    """
    out = []
    i = 0
    n = len(line)
    while i < n:
        # 跳过空白
        while i < n and line[i] in " \t":
            i += 1
        if i >= n:
            break
        c = line[i]
        # 引号
        if c == '"':
            i += 1
            while i < n and line[i] != '"':
                if line[i] == '\\':
                    i += 2
                else:
                    i += 1
            i += 1
            continue
        # 行注释
        if c == '%' and i + 1 < n and line[i + 1] == '%':
            break
        # 试匹配 id
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", line[i:])
        if not m:
            i += 1
            continue
        nid = m.group(1)
        after = i + len(nid)
        # 跳过空白
        j = after
        while j < n and line[j] in " \t":
            j += 1
        if j >= n:
            # 行尾裸 id
            out.append((nid, None, i, j))
            i = j
            continue
        if line[j] in _OPEN_CHARS:
            shape, end = _scan_shape(line, j)
            if shape and end <= n:
                out.append((nid, shape, i, end))
                i = end
                continue
        # 不是节点定义；要不要把它当裸 id 处理？看后续是不是箭头
        out.append((nid, None, i, after))
        i = after
    return out


def _stripped_id(line):
    """返回把节点 spec 剥成裸 id 后的行（保留所有其它结构与空白）。

    用于边匹配前：把 `A[请求]` 还原为 `A`，让连线正则能拍上。
    """
    spans = _find_all_nodes(line)
    if not spans:
        return line
    parts = []
    last = 0
    for nid, shape, s, e in spans:
        # 只对"带 shape 的节点定义"做剥离，避免把普通 id 也变没了
        if shape is None:
            continue
        parts.append(line[last:s])
        parts.append(nid)
        last = e
    parts.append(line[last:])
    return "".join(parts)


_EDGE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(-->|---|-.->|===>|==>|-x|--x|--)\s*"
    r"(?:\|([^|]*)\|)?\s*"
    r"([A-Za-z_][A-Za-z0-9_]*)(?:\s*:\s*(.*))?\s*$"
)
_NODE_ONLY = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*$")
_NODE_LABELED = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+?)\s*$")

_SEQ_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(->>|-->>|->|-->|-x|--x|--\)|->\))\s*"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+?)\s*$"
)
_STATE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(-->|---)\s*"
    r"([A-Za-z_][A-Za-z0-9_]*)(?:\s*:\s*(.+?))?\s*$"
)


def _shape_kind(shape):
    """把 mermaid shape 转成 IR 的 type 提示（决定形状 vs 是否判定）。"""
    if shape is None:
        return None
    if shape.startswith("((") or shape.startswith("(["):
        return "terminal"
    if shape.startswith("[("):
        return "storage"
    if shape.startswith("{") or shape.endswith("}"):
        return "decision"
    if shape.startswith("[["):
        return "process"
    return "process"


def _clean_label(shape):
    if shape is None:
        return None
    # 去掉两端成对括号的 shape-spec，保留内容
    while shape and shape[0] in _OPEN_CHARS and shape[-1] in _CLOSE_CHARS:
        # 必须是成对匹配
        if _PAIR.get(shape[0]) == shape[-1]:
            shape = shape[1:-1]
        else:
            break
    return shape.replace('"', "").strip()


def _guess_type(node_id, label):
    text = (str(node_id) + " " + str(label or "")).lower()
    HINT = {
        "db": "database", "database": "database", "redis": "database", "cache": "database",
        "queue": "messagebus", "kafka": "messagebus", "mq": "messagebus",
        "llm": "llm", "gpt": "llm", "model": "llm", "agent": "agent",
        "vector": "vector", "embedding": "vector", "user": "user", "client": "frontend",
        "web": "frontend", "ui": "frontend", "front": "frontend", "browser": "frontend",
        "api": "backend", "server": "backend", "service": "backend", "backend": "backend",
        "gw": "backend", "gateway": "backend", "cloud": "cloud", "s3": "storage",
        "storage": "storage", "auth": "security", "security": "security",
    }
    for k, v in HINT.items():
        if k in text:
            return v
    return "process"


_ARROW_RE = re.compile(r"(-->|---|-.->|===>|==>|--x|-x)")


def _strip_inline_label(line):
    """把 `A -- 内联文字 --> B` 这类内联标签去掉，只留裸箭头。

    内联文字会丢失，但拓扑与箭头类型保留。标签文本可含任意字符
    （中文、连字符、空格等）。
    """
    return re.sub(r"--\s+.+?\s+(-->|---|-x|--x)", r"\1", line)


def _expand_amp_edges(line):
    """把一行里的复杂连线拆成多条「源 箭头 目标」边语句。

    支持：
      • 链式  `A --> B --> C`  →  A-->B, B-->C
      • 多目标 `A --> B & C`  /  `A & B --> C`  /  `A & B --> C & D`（笛卡尔积）
      • 内联标签 `A -- 文字 --> B`（先剥离文字）
    非边语句原样返回。
    """
    line = _strip_inline_label(line)
    s = _strip_pipes(line)
    s = _stripped_id(s)
    arrows = list(_ARROW_RE.finditer(s))
    if not arrows:
        return [line]
    segs = []
    last = 0
    for a in arrows:
        segs.append(s[last:a.start()].strip())
        segs.append(a.group(1))
        last = a.end()
    segs.append(s[last:].strip())
    edges = []
    i = 0
    while i + 2 < len(segs):
        src = segs[i]
        arrow = segs[i + 1]
        tgt = segs[i + 2]
        srcs = [x.strip() for x in src.split("&") if x.strip()]
        tgts = [x.strip() for x in tgt.split("&") if x.strip()]
        for ss in srcs:
            for tt in tgts:
                edges.append("%s %s %s" % (ss, arrow, tt))
        i += 2
    return edges if edges else [line]


def convert(text):
    """Mermaid 文本 → (ir, warnings)。"""
    warnings = []
    raw_text = str(text or "")
    # 渲染引擎不认多行标签，提前把 <br/> 折叠成空格
    raw_text = raw_text.replace("<br/>", " ").replace("<br>", " ")
    raw_lines = [l.rstrip() for l in raw_text.splitlines()]
    lines = [l for l in raw_lines
             if l.strip() and not l.strip().startswith("%%")]

    if not lines:
        return None, ["输入为空"]

    head = lines[0].strip().lower()
    if head.startswith("sequencediagram"):
        return _convert_sequence(lines[1:], warnings)
    if head.startswith("statediagram"):
        return _convert_state(lines[1:], warnings)
    if head.startswith(("flowchart", "graph")):
        return _convert_flowchart(lines[1:], warnings)
    if any(_SEQ_RE.match(l) for l in lines):
        return _convert_sequence(lines, warnings)
    if any(_EDGE_RE.match(_stripped_id(l)) for l in lines):
        return _convert_flowchart(lines, warnings)
    warnings.append("未识别 Mermaid 头部，已按 flowchart 处理")
    return _convert_flowchart(lines, warnings)


def _convert_flowchart(lines, warnings):
    nodes, edges = [], []
    seen = {}
    groups = []
    current_group = None

    def ensure(nid, label=None, type_hint=None):
        if nid in seen:
            if label and not seen[nid].get("label"):
                seen[nid]["label"] = label
            if type_hint and seen[nid]["type"] == "default":
                seen[nid]["type"] = type_hint
            return seen[nid]
        # 支持 `id[标题 // 副标题]` 语法：把 `//` 后的内容拆到 desc 副标题
        desc = None
        if label and " // " in label:
            _t, _d = label.split(" // ", 1)
            label, desc = _t.strip(), _d.strip()
        node = {"id": nid,
                "label": label or nid,
                "type": type_hint or _guess_type(nid, label)}
        if desc:
            node["desc"] = desc
        seen[nid] = node
        nodes.append(node)
        if current_group:
            for g in groups:
                if g["id"] == current_group and nid not in g["members"]:
                    g["members"].append(nid)
        return node

    for raw in lines:
        line = raw.strip()
        low = line.lower()
        if not line:
            continue

        if low.startswith("subgraph"):
            tail = re.sub(r"^subgraph\s+", "", line, flags=re.I).strip()
            tail_id = re.sub(r"\s+.*$", "", tail) or ("sub%d" % len(groups))
            tail_id = tail_id.replace('"', "") or ("sub%d" % len(groups))
            current_group = tail_id
            label = tail.split(None, 1)[1].strip('" ') if len(tail.split(None, 1)) == 2 else tail_id
            if label.startswith("[") and label.endswith("]"):
                label = label[1:-1].strip()
            groups.append({"id": current_group, "label": label,
                           "members": []})
            continue
        if low == "end":
            current_group = None
            continue
        if low.startswith(("classdef", "class ", "style ", "linkstyle",
                           "direction", "click")):
            continue

        # 1) 把行里所有「节点定义」注册到 nodes
        #    先剥掉 |label| 段，避免标签里的字符被当成节点 id
        #    多目标边 A --> B & C 先展开成多条边
        for ln in _expand_amp_edges(line):
            clean = _strip_pipes(ln)
            for nid, shape, _, _ in _find_all_nodes(clean):
                ensure(nid, _clean_label(shape),
                       _shape_kind(shape) if shape else None)

            # 2) 用"剥了 shape 的版本"去匹配连线（label 由正则 group3/group5 回收）
            em = _EDGE_RE.match(_stripped_id(ln))
            if em:
                s, arrow, pipe, t, tail = em.groups()
                label = (pipe or "").strip() or (tail or "").strip() or None
                ensure(s)
                ensure(t)
                kind = "sync"
                if "-." in arrow:
                    kind = "async"
                elif "==" in arrow:
                    kind = "flow"
                elif "-x" in arrow or arrow == "x":
                    kind = "event"
                edges.append({"source": s, "target": t,
                              "label": label, "kind": kind})
                continue

            # 3) 裸节点定义：A: Label 或 A
            nm = _NODE_LABELED.match(ln)
            if nm:
                ensure(nm.group(1), nm.group(2))
                continue
            nm = _NODE_ONLY.match(ln)
            if nm:
                ensure(nm.group(1))
                continue

    if not nodes:
        return None, warnings + ["没有解析出任何节点"]

    for g in groups:
        if not g["members"]:
            warnings.append("subgraph %s 没有成员，已忽略" % g["id"])
    groups = [g for g in groups if g["members"]]

    return {"diagram_type": "workflow",
            "nodes": nodes,
            "edges": edges,
            "groups": groups,
            "meta": {"title": "转换自 Mermaid"}}, warnings


def _convert_sequence(lines, warnings):
    participants, edges = [], []
    seen = {}

    def ensure(pid, label=None, type_hint=None):
        if pid in seen:
            if label and not seen[pid].get("label"):
                seen[pid]["label"] = label
            return seen[pid]
        seen[pid] = {"id": pid,
                     "label": label or pid,
                     "type": type_hint or _guess_type(pid, label)}
        participants.append(seen[pid])
        return seen[pid]

    for raw in lines:
        line = raw.strip()
        low = line.lower()
        if not line:
            continue
        first = low.split()[0] if low.split() else ""
        if first in ("note", "activate", "deactivate", "loop", "alt",
                     "else", "end", "opt", "par", "rect", "critical",
                     "autonumber", "title"):
            continue
        pm = re.match(r"^(?:participant|actor)\s+"
                      r"([A-Za-z_][A-Za-z0-9_]*)"
                      r"(?:\s+as\s+(.+?))?\s*$",
                      line, re.I)
        if pm:
            ensure(pm.group(1), (pm.group(2) or pm.group(1)).strip())
            continue
        m = _SEQ_RE.match(line)
        if m:
            s, arrow, t, msg = m.groups()
            ensure(s)
            ensure(t)
            kind = "return" if "x" in arrow else (
                "async" if "--" in arrow else "sync")
            edges.append({"source": s, "target": t,
                          "label": (msg or "").strip() or None,
                          "kind": kind})

    if not participants:
        return None, warnings + ["没有解析出任何参与者"]
    return {"diagram_type": "sequence",
            "nodes": participants,
            "edges": edges,
            "meta": {"title": "转换自 Mermaid 时序图"}}, warnings


def _convert_state(lines, warnings):
    nodes, edges = [], []
    seen = {}

    def ensure(nid, label=None):
        if nid in seen:
            if label and not seen[nid].get("label"):
                seen[nid]["label"] = label
            return seen[nid]
        seen[nid] = {"id": nid,
                     "label": label or nid,
                     "type": _guess_type(nid, label)}
        nodes.append(seen[nid])
        return seen[nid]

    for raw in lines:
        line = raw.strip()
        low = line.lower()
        if not line:
            continue
        if low.startswith(("note", "direction", "classdef",
                           "class ", "style ")):
            continue
        if low == "end":
            continue
        m = _STATE_RE.match(line)
        if m:
            s, arrow, t, evt = m.groups()
            if s.startswith("[") or t.startswith("["):
                continue
            ensure(s)
            ensure(t)
            edges.append({"source": s, "target": t,
                          "label": (evt or "").strip() or None,
                          "kind": "event"})
            continue
        nm = _NODE_LABELED.match(line)
        if nm:
            ensure(nm.group(1), nm.group(2))
            continue
        nm = _NODE_ONLY.match(line)
        if nm:
            ensure(nm.group(1))

    if not nodes:
        return None, warnings + ["没有解析出任何状态"]
    return {"diagram_type": "lifecycle",
            "nodes": nodes,
            "edges": edges,
            "meta": {"title": "转换自 Mermaid 状态图"}}, warnings
