#!/usr/bin/env python3
"""Render a validated flowchart JSON document to HTML and PNG."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from render_architecture import InputError, THEMES, css_font, resolve_cjk_font, resolve_cjk_font_family, svg_text, text, wrap


ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def validate(raw):
    if not isinstance(raw, dict):
        raise InputError("root must be an object")
    title = text(raw.get("title"), "title", 1, 80)
    subtitle = text(raw.get("subtitle", ""), "subtitle", 0, 120)
    direction = raw.get("direction", "top-down")
    if direction not in {"top-down", "left-right"}:
        raise InputError("direction must be top-down or left-right")
    theme = raw.get("theme", "chaoxing-blue")
    if theme not in THEMES:
        raise InputError(f"theme must be one of: {', '.join(THEMES)}")
    nodes = raw.get("nodes")
    edges = raw.get("edges")
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= 60:
        raise InputError("nodes must contain 2-60 objects")
    if not isinstance(edges, list) or not 1 <= len(edges) <= 120:
        raise InputError("edges must contain 1-120 objects")
    clean_nodes, ids = [], set()
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise InputError(f"nodes[{i}] must be an object")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not ID_PATTERN.fullmatch(node_id):
            raise InputError(f"nodes[{i}].id must match [A-Za-z0-9_-] and be 1-40 characters")
        if node_id in ids:
            raise InputError(f"duplicate node id: {node_id}")
        ids.add(node_id)
        shape = node.get("shape", "process")
        if shape not in {"start", "process", "decision", "end"}:
            raise InputError(f"nodes[{i}].shape is invalid")
        status = node.get("status", "current")
        if status not in {"current", "planned"}:
            raise InputError(f"nodes[{i}].status is invalid")
        clean_nodes.append({"id": node_id, "label": text(node.get("label"), f"nodes[{i}].label", 1, 60), "description": text(node.get("description", ""), f"nodes[{i}].description", 0, 120), "shape": shape, "status": status})
    clean_edges = []
    outgoing = defaultdict(int)
    for i, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise InputError(f"edges[{i}] must be an object")
        source, target = edge.get("from"), edge.get("to")
        if source not in ids or target not in ids:
            raise InputError(f"edges[{i}] references a missing node")
        label = text(edge.get("label", ""), f"edges[{i}].label", 0, 30)
        clean_edges.append({"from": source, "to": target, "label": label})
        outgoing[source] += 1
    for node in clean_nodes:
        if node["shape"] == "decision" and outgoing[node["id"]] >= 2:
            unlabeled = [edge for edge in clean_edges if edge["from"] == node["id"] and not edge["label"]]
            if unlabeled:
                raise InputError(f"decision node {node['id']} has unlabeled branches")
    return {"title": title, "subtitle": subtitle, "direction": direction, "theme": theme, "nodes": clean_nodes, "edges": clean_edges}


def layout(data):
    nodes = data["nodes"]
    index = {node["id"]: i for i, node in enumerate(nodes)}
    ranks = {node["id"]: 0 for node in nodes}
    forward = [edge for edge in data["edges"] if index[edge["to"]] > index[edge["from"]]]
    for _ in nodes:
        changed = False
        for edge in forward:
            candidate = ranks[edge["from"]] + 1
            if candidate > ranks[edge["to"]]:
                ranks[edge["to"]] = candidate
                changed = True
        if not changed:
            break
    groups = defaultdict(list)
    for node in nodes:
        groups[ranks[node["id"]]].append(node)
    return index, ranks, groups


def node_markup(node, x, y, width, height, palette):
    stroke = "#E2A83B" if node["status"] == "planned" else palette["line"]
    fill = "#FFF8E8" if node["status"] == "planned" else palette["light"]
    dash = ' stroke-dasharray="8 6"' if node["status"] == "planned" else ""
    if node["shape"] == "decision":
        points = f"{x+width/2},{y} {x+width},{y+height/2} {x+width/2},{y+height} {x},{y+height/2}"
        shape = f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash}/>'
    elif node["shape"] in {"start", "end"}:
        shape = f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{height/2}" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash}/>'
    else:
        shape = f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="16" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash}/>'
    names = wrap(node["label"], 15)
    descriptions = wrap(node["description"], 20) if node["description"] else []
    total_text = len(names) * 27 + len(descriptions) * 20
    start_y = y + height / 2 - total_text / 2 + 20
    result = [shape, svg_text(names, x + width / 2, start_y, "node-name", 27)]
    if descriptions:
        result.append(svg_text(descriptions, x + width / 2, start_y + len(names) * 27 + 7, "node-desc", 20))
    if node["status"] == "planned":
        result.append(f'<rect x="{x+width-58}" y="{y+10}" width="46" height="23" rx="11" fill="#D68A16"/><text x="{x+width-35}" y="{y+27}" class="badge" text-anchor="middle">规划</text>')
    return "".join(result)


def render_svg(data):
    palette = THEMES[data["theme"]]
    font_family = resolve_cjk_font_family()
    index, ranks, groups = layout(data)
    margin, title_h, node_w, node_h, axis_gap, cross_gap = 90, (165 if data["subtitle"] else 125), 270, 130, 115, 54
    max_cross = max(len(group) for group in groups.values())
    if data["direction"] == "top-down":
        width = max(1200, margin * 2 + max_cross * node_w + (max_cross - 1) * cross_gap + 260)
        height = title_h + (max(ranks.values()) + 1) * node_h + max(ranks.values()) * axis_gap + 100
    else:
        width = margin * 2 + (max(ranks.values()) + 1) * node_w + max(ranks.values()) * axis_gap + 260
        height = max(760, title_h + max_cross * node_h + (max_cross - 1) * cross_gap + 100)
    positions = {}
    for rank in sorted(groups):
        group = groups[rank]
        if data["direction"] == "top-down":
            group_width = len(group) * node_w + (len(group) - 1) * cross_gap
            start = (width - group_width) / 2
            for i, node in enumerate(group):
                positions[node["id"]] = (start + i * (node_w + cross_gap), title_h + rank * (node_h + axis_gap))
        else:
            group_height = len(group) * node_h + (len(group) - 1) * cross_gap
            start = title_h + max(0, (height - title_h - group_height) / 2)
            for i, node in enumerate(group):
                positions[node["id"]] = (margin + rank * (node_w + axis_gap), start + i * (node_h + cross_gap))
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{int(width)}" height="{int(height)}" viewBox="0 0 {int(width)} {int(height)}">
<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 Z" fill="{palette['primary']}"/></marker><filter id="shadow" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="3" stdDeviation="5" flood-color="#1D3854" flood-opacity="0.12"/></filter></defs>
<style>.title{{{css_font(font_family, 42, 700)};fill:{palette['dark']}}}.subtitle{{{css_font(font_family, 21, 400)};fill:#5F7185}}.node-name{{{css_font(font_family, 20, 700)};fill:{palette['dark']}}}.node-desc{{{css_font(font_family, 14, 400)};fill:#607286}}.edge-label{{{css_font(font_family, 15, 700)};fill:{palette['dark']}}}.badge{{{css_font(font_family, 13, 700)};fill:white}}</style><rect width="100%" height="100%" fill="#F7FAFD"/>{svg_text([data['title']], width/2, 70, 'title', 48)}''']
    if data["subtitle"]:
        parts.append(svg_text([data["subtitle"]], width / 2, 110, "subtitle", 30))
    loop_count = 0
    for edge in data["edges"]:
        sx, sy = positions[edge["from"]]
        tx, ty = positions[edge["to"]]
        is_back = index[edge["to"]] <= index[edge["from"]]
        if is_back:
            loop_count += 1
            lane = width - 70 - loop_count * 32
            start_x, start_y = sx + node_w, sy + node_h / 2
            end_x, end_y = tx + node_w, ty + node_h / 2
            path = f"M {start_x} {start_y} L {lane} {start_y} L {lane} {end_y} L {end_x+8} {end_y}"
            label_x, label_y = lane - 8, (start_y + end_y) / 2
        elif data["direction"] == "top-down":
            start_x, start_y = sx + node_w / 2, sy + node_h
            end_x, end_y = tx + node_w / 2, ty
            mid_y = (start_y + end_y) / 2
            path = f"M {start_x} {start_y} L {start_x} {mid_y} L {end_x} {mid_y} L {end_x} {end_y-8}"
            label_x, label_y = (start_x + end_x) / 2 + 10, mid_y - 9
        else:
            start_x, start_y = sx + node_w, sy + node_h / 2
            end_x, end_y = tx, ty + node_h / 2
            mid_x = (start_x + end_x) / 2
            path = f"M {start_x} {start_y} L {mid_x} {start_y} L {mid_x} {end_y} L {end_x-8} {end_y}"
            label_x, label_y = mid_x + 8, (start_y + end_y) / 2 - 9
        parts.append(f'<path d="{path}" fill="none" stroke="{palette["primary"]}" stroke-width="3" marker-end="url(#arrow)"/>')
        if edge["label"]:
            parts.append(f'<rect x="{label_x-7}" y="{label_y-18}" width="{max(42, len(edge["label"])*18+14)}" height="25" rx="7" fill="white" opacity="0.94"/>')
            parts.append(f'<text x="{label_x}" y="{label_y}" class="edge-label">{html.escape(edge["label"])}</text>')
    for node in data["nodes"]:
        x, y = positions[node["id"]]
        parts.append(f'<g filter="url(#shadow)">{node_markup(node, x, y, node_w, node_h, palette)}</g>')
    parts.append("</svg>")
    return "".join(parts), int(width), int(height)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    source, output = Path(args.input), Path(args.output_dir)
    if not source.is_file():
        raise InputError(f"input file not found: {source}")
    data = validate(json.loads(source.read_text(encoding="utf-8")))
    output.mkdir(parents=True, exist_ok=True)
    svg, width, height = render_svg(data)
    html_path, png_path = output / "flowchart.html", output / "flowchart.png"
    manifest_path = output / "manifest.json"
    html_path.write_text("<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><title>" + html.escape(data["title"]) + "</title><style>html,body{margin:0;background:#eef3f8}svg{display:block;max-width:100%;height:auto;margin:auto}</style><body>" + svg + "</body></html>", encoding="utf-8")
    renderer = shutil.which("magick") or shutil.which("convert")
    font_family, font_file = resolve_cjk_font()
    manifest = {"success": False, "title": data["title"], "nodes": len(data["nodes"]), "edges": len(data["edges"]), "width": width, "height": height, "files": {"html": str(html_path)}, "renderer": renderer, "font_family": font_family, "font_file": Path(font_file).name if font_file else None}
    if not renderer:
        manifest["error"] = "ImageMagick magick/convert was not found; HTML was generated"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False))
        return 2
    if not font_file:
        manifest["error"] = "No Chinese-capable font was found by fontconfig; HTML was generated and PNG was skipped"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False))
        return 5
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", encoding="utf-8", dir="/tmp", delete=True) as temporary_svg:
            temporary_svg.write(svg)
            temporary_svg.flush()
            completed = subprocess.run([renderer, "-background", "white", "-density", "144", "-font", font_file, temporary_svg.name, str(png_path)], capture_output=True, text=True, timeout=45, check=False)
    except subprocess.TimeoutExpired:
        manifest["error"] = "PNG conversion timed out after 45 seconds"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False))
        return 3
    if completed.returncode != 0 or not png_path.is_file() or png_path.stat().st_size == 0:
        manifest["error"] = (completed.stderr or "PNG conversion failed")[-2000:]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False))
        return 4
    manifest["success"] = True
    manifest["files"]["png"] = str(png_path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InputError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)

