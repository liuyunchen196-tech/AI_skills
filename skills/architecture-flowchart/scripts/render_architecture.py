#!/usr/bin/env python3
"""Render validated layered architecture JSON to HTML and PNG."""

from __future__ import annotations

import argparse
import html
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


THEMES = {
    "chaoxing-blue": {"primary": "#1769E0", "dark": "#123B73", "light": "#EAF3FF", "line": "#8CB7EE"},
    "academic-blue": {"primary": "#245A8D", "dark": "#173A5E", "light": "#EDF4FA", "line": "#91AEC9"},
    "neutral": {"primary": "#4B6075", "dark": "#263746", "light": "#F1F4F6", "line": "#A8B4BF"},
}
STATUS_LABELS = {"planned": "规划", "external": "外部"}
DEFAULT_FONT_FAMILY = "sans-serif"


class InputError(ValueError):
    pass


def resolve_cjk_font():
    """Return (family, file) for a fontconfig font declared to support Chinese."""
    fc_list = shutil.which("fc-list")
    if not fc_list:
        return DEFAULT_FONT_FAMILY, None
    try:
        result = subprocess.run([fc_list, ":lang=zh-cn", "-f", "%{file}\t%{family}\n"], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return DEFAULT_FONT_FAMILY, None
    for line in result.stdout.splitlines():
        font_file, separator, family = line.partition("\t")
        path = Path(font_file.strip())
        if separator and path.is_file():
            return family.split(",")[0].strip() or DEFAULT_FONT_FAMILY, str(path)
    return DEFAULT_FONT_FAMILY, None


def resolve_cjk_font_family():
    return resolve_cjk_font()[0]


def css_font(font_family, size, weight):
    """Avoid CSS font shorthand, which ImageMagick SVG may misparse."""
    safe_family = font_family.replace("\\", "").replace("'", "")
    return f"font-family:'{safe_family}',sans-serif;font-size:{size}px;font-weight:{weight}"


def text(value, field, minimum=1, maximum=120):
    if not isinstance(value, str):
        raise InputError(f"{field} must be a string")
    value = value.strip()
    if not minimum <= len(value) <= maximum:
        raise InputError(f"{field} length must be {minimum}-{maximum}")
    return value


def validate(raw):
    if not isinstance(raw, dict):
        raise InputError("root must be an object")
    title = text(raw.get("title"), "title", 1, 80)
    subtitle = text(raw.get("subtitle", ""), "subtitle", 0, 120)
    theme = raw.get("theme", "chaoxing-blue")
    if theme not in THEMES:
        raise InputError(f"theme must be one of: {', '.join(THEMES)}")
    columns = raw.get("columns")
    if columns is not None and (not isinstance(columns, int) or isinstance(columns, bool) or not 1 <= columns <= 6):
        raise InputError("columns must be an integer from 1 to 6")
    layers = raw.get("layers")
    if not isinstance(layers, list) or not 1 <= len(layers) <= 12:
        raise InputError("layers must contain 1-12 objects")
    clean_layers = []
    total = 0
    for li, layer in enumerate(layers):
        if not isinstance(layer, dict):
            raise InputError(f"layers[{li}] must be an object")
        label = text(layer.get("label"), f"layers[{li}].label", 1, 30)
        description = text(layer.get("description", ""), f"layers[{li}].description", 0, 100)
        items = layer.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 30:
            raise InputError(f"layers[{li}].items must contain 1-30 modules")
        clean_items = []
        for ii, item in enumerate(items):
            if isinstance(item, str):
                clean_items.append({"name": text(item, f"layers[{li}].items[{ii}]", 1, 60), "description": "", "status": "current"})
                continue
            if not isinstance(item, dict):
                raise InputError(f"layers[{li}].items[{ii}] must be a string or object")
            status = item.get("status", "current")
            if status not in {"current", "planned", "external"}:
                raise InputError(f"layers[{li}].items[{ii}].status is invalid")
            clean_items.append({
                "name": text(item.get("name"), f"layers[{li}].items[{ii}].name", 1, 60),
                "description": text(item.get("description", ""), f"layers[{li}].items[{ii}].description", 0, 120),
                "status": status,
            })
        total += len(clean_items)
        clean_layers.append({"label": label, "description": description, "items": clean_items})
    if total > 120:
        raise InputError("total module count must not exceed 120")
    return {"title": title, "subtitle": subtitle, "theme": theme, "columns": columns, "layers": clean_layers, "total": total}


def wrap(value, limit):
    lines, current = [], ""
    for ch in value:
        weight = 1 if ord(ch) > 255 else 0.55
        current_weight = sum(1 if ord(c) > 255 else 0.55 for c in current)
        if current and current_weight + weight > limit:
            lines.append(current)
            current = ch
        else:
            current += ch
    if current:
        lines.append(current)
    return lines or [""]


def svg_text(lines, x, y, css_class, line_height, anchor="middle"):
    spans = []
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else str(line_height)
        spans.append(f'<tspan x="{x}" dy="{dy}">{html.escape(line)}</tspan>')
    return f'<text x="{x}" y="{y}" class="{css_class}" text-anchor="{anchor}">' + "".join(spans) + "</text>"


def render_svg(data):
    palette = THEMES[data["theme"]]
    font_family = resolve_cjk_font_family()
    width, margin, label_width, gap = 1600, 70, 220, 24
    content_width = width - margin * 2 - label_width - gap
    title_height = 170 if data["subtitle"] else 135
    layer_gap, card_gap = 34, 18
    layouts, y = [], title_height
    for layer in data["layers"]:
        count = len(layer["items"])
        cols = data["columns"] or min(5, max(1, math.ceil(math.sqrt(count * 1.7))))
        cols = min(cols, count)
        card_width = (content_width - card_gap * (cols - 1)) / cols
        name_limit = max(7, int(card_width / 20))
        desc_limit = max(9, int(card_width / 16))
        card_heights = []
        wrapped = []
        for item in layer["items"]:
            names = wrap(item["name"], name_limit)
            descriptions = wrap(item["description"], desc_limit) if item["description"] else []
            card_height = 44 + len(names) * 28 + len(descriptions) * 22 + (20 if item["status"] != "current" else 0)
            card_heights.append(max(100, card_height))
            wrapped.append((names, descriptions))
        rows = math.ceil(count / cols)
        row_heights = []
        for row in range(rows):
            row_heights.append(max(card_heights[row * cols:min((row + 1) * cols, count)]))
        layer_height = max(132, sum(row_heights) + card_gap * (rows - 1) + 48)
        layouts.append((layer, y, layer_height, cols, card_width, card_heights, row_heights, wrapped))
        y += layer_height + layer_gap
    height = int(y - layer_gap + 70)
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs><filter id="shadow" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="3" stdDeviation="5" flood-color="#1D3854" flood-opacity="0.12"/></filter></defs>
<style>
.title{{{css_font(font_family, 42, 700)};fill:{palette['dark']}}}
.subtitle{{{css_font(font_family, 21, 400)};fill:#5F7185}}
.layer-label{{{css_font(font_family, 24, 700)};fill:white}}
.layer-desc{{{css_font(font_family, 15, 400)};fill:#DDEBFF}}
.module-name{{{css_font(font_family, 21, 700)};fill:{palette['dark']}}}
.module-desc{{{css_font(font_family, 15, 400)};fill:#607286}}
.badge{{{css_font(font_family, 13, 700)};fill:white}}
</style>
<rect width="100%" height="100%" fill="#F7FAFD"/>
{svg_text([data['title']], width/2, 72, 'title', 48)}''']
    if data["subtitle"]:
        parts.append(svg_text([data["subtitle"]], width / 2, 112, "subtitle", 30))
    for index, layout in enumerate(layouts):
        layer, layer_y, layer_h, cols, card_w, card_heights, row_heights, wrapped = layout
        parts.append(f'<rect x="{margin}" y="{layer_y}" width="{width-margin*2}" height="{layer_h}" rx="22" fill="white" stroke="#D8E4F0" filter="url(#shadow)"/>')
        parts.append(f'<rect x="{margin}" y="{layer_y}" width="{label_width}" height="{layer_h}" rx="22" fill="{palette["primary"]}"/>')
        label_lines = wrap(layer["label"], 8)
        label_start = layer_y + layer_h / 2 - (len(label_lines) - 1) * 17
        parts.append(svg_text(label_lines, margin + label_width / 2, label_start, "layer-label", 34))
        if layer["description"]:
            desc_lines = wrap(layer["description"], 12)[:3]
            parts.append(svg_text(desc_lines, margin + label_width / 2, label_start + len(label_lines) * 34 + 7, "layer-desc", 22))
        cards_x = margin + label_width + gap
        row_y = layer_y + 24
        for i, item in enumerate(layer["items"]):
            row, col = divmod(i, cols)
            if col == 0 and row > 0:
                row_y += row_heights[row - 1] + card_gap
            card_x = cards_x + col * (card_w + card_gap)
            card_h = card_heights[i]
            stroke = "#E2A83B" if item["status"] == "planned" else ("#8A98A7" if item["status"] == "external" else palette["line"])
            dash = ' stroke-dasharray="8 6"' if item["status"] == "planned" else ""
            parts.append(f'<rect x="{card_x}" y="{row_y}" width="{card_w}" height="{card_h}" rx="15" fill="{palette["light"]}" stroke="{stroke}" stroke-width="2"{dash}/>')
            names, descriptions = wrapped[i]
            name_y = row_y + 37
            parts.append(svg_text(names, card_x + card_w / 2, name_y, "module-name", 28))
            if descriptions:
                desc_y = name_y + len(names) * 28 + 7
                parts.append(svg_text(descriptions, card_x + card_w / 2, desc_y, "module-desc", 22))
            if item["status"] != "current":
                badge = STATUS_LABELS[item["status"]]
                badge_color = "#D68A16" if item["status"] == "planned" else "#718092"
                parts.append(f'<rect x="{card_x+card_w-58}" y="{row_y+10}" width="46" height="23" rx="11" fill="{badge_color}"/>')
                parts.append(svg_text([badge], card_x + card_w - 35, row_y + 27, "badge", 16))
        if index < len(layouts) - 1:
            center_x = margin + label_width / 2
            start_y = layer_y + layer_h
            parts.append(f'<path d="M {center_x} {start_y} L {center_x} {start_y+layer_gap-8}" stroke="{palette["line"]}" stroke-width="4"/>')
            parts.append(f'<path d="M {center_x-8} {start_y+layer_gap-16} L {center_x} {start_y+layer_gap-7} L {center_x+8} {start_y+layer_gap-16}" fill="none" stroke="{palette["line"]}" stroke-width="4"/>')
    parts.append("</svg>")
    return "".join(parts), width, height


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
    html_path = output / "architecture.html"
    png_path = output / "architecture.png"
    manifest_path = output / "manifest.json"
    html_path.write_text("<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><title>" + html.escape(data["title"]) + "</title><style>html,body{margin:0;background:#eef3f8}svg{display:block;max-width:100%;height:auto;margin:auto}</style><body>" + svg + "</body></html>", encoding="utf-8")
    renderer = shutil.which("magick") or shutil.which("convert")
    font_family, font_file = resolve_cjk_font()
    manifest = {"success": False, "title": data["title"], "layers": len(data["layers"]), "modules": data["total"], "width": width, "height": height, "files": {"html": str(html_path)}, "renderer": renderer, "font_family": font_family, "font_file": Path(font_file).name if font_file else None}
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
            command = [renderer, "-background", "white", "-density", "144", "-font", font_file, temporary_svg.name, str(png_path)]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
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

