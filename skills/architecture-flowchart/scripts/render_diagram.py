#!/usr/bin/env python3
"""Dispatch architecture or flowchart rendering and normalize output names."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    source = Path(args.input)
    output = Path(args.output_dir)
    if not source.is_file():
        print(json.dumps({"success": False, "error": f"input file not found: {source}"}, ensure_ascii=False), file=sys.stderr)
        return 1
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    diagram_type = raw.get("diagram_type")
    scripts = Path(__file__).resolve().parent
    if diagram_type == "architecture":
        script, prefix = scripts / "render_architecture.py", "architecture"
    elif diagram_type == "flowchart":
        script, prefix = scripts / "render_flowchart.py", "flowchart"
    else:
        print(json.dumps({"success": False, "error": "diagram_type must be architecture or flowchart"}, ensure_ascii=False), file=sys.stderr)
        return 1
    command = [sys.executable, str(script), "--input", str(source), "--output-dir", str(output)]
    completed = subprocess.run(command, timeout=55, check=False)
    if completed.returncode not in {0, 2}:
        return completed.returncode
    for suffix in ("html", "png"):
        old = output / f"{prefix}.{suffix}"
        new = output / f"diagram.{suffix}"
        if old.exists():
            old.replace(new)
    manifest_path = output / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["diagram_type"] = diagram_type
        manifest["files"] = {key: str(output / f"diagram.{key}") for key in ("html", "png") if (output / f"diagram.{key}").is_file()}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False))
    return completed.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired:
        print(json.dumps({"success": False, "error": "renderer timed out"}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(3)

