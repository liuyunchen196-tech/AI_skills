#!/usr/bin/env python3
"""verify_pptx.py - 内容迁移完整性校验：比对源PPT与成品PPT。

用法: python verify_pptx.py <源.pptx> <成品.pptx>
校验项:
  1. 源PPT每个非空文本段落都在成品中出现（目录页除外，目录允许重排）
  2. 源PPT每张图片（按内容哈希）都在成品中存在
  3. 源PPT每张表格的每个单元格文本都在成品中出现
  4. 成品无模板占位残留（目录N标题/填写标题/编制人姓名/时间）
输出: JSON 报告，missing/nonempty 汇总；exit code 0=通过 1=有缺失
"""
import sys
import json
import hashlib
from pptx import Presentation

PLACEHOLDER_RESIDUE = ["目录1标题", "目录2标题", "目录3标题", "目录4标题",
                       "目录5标题", "填写标题", "编制人姓名"]


def iter_pictures(prs):
    def walk(shapes, acc):
        for sh in shapes:
            if sh.shape_type == 13:
                try:
                    acc.add(hashlib.md5(sh.image.blob).hexdigest())
                except Exception:
                    pass
            elif sh.shape_type == 6:
                walk(sh.shapes, acc)
    acc = set()
    for s in prs.slides:
        walk(s.shapes, acc)
    return acc


def iter_text_table(prs):
    texts, tables = [], []
    def walk(shapes):
        for sh in shapes:
            if getattr(sh, "has_table", False) and sh.has_table:
                for row in sh.table.rows:
                    for c in row.cells:
                        if c.text.strip():
                            tables.append(c.text.strip())
            if getattr(sh, "has_text_frame", False) and sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    if p.text.strip():
                        texts.append(p.text.strip())
            if sh.shape_type == 6:
                walk(sh.shapes)
    for s in prs.slides:
        walk(s.shapes)
    return texts, tables


def main(src_path, out_path):
    src, out = Presentation(src_path), Presentation(out_path)
    src_texts, src_tables = iter_text_table(src)
    out_texts, out_tables = iter_text_table(out)
    src_imgs, out_imgs = iter_pictures(src), iter_pictures(out)

    out_blob = "\n".join(out_texts + out_tables)
    missing_text = sorted({t for t in src_texts if t not in out_blob})
    missing_table = sorted({t for t in src_tables if t not in out_blob})
    missing_img = len(src_imgs - out_imgs)

    residue = [t for t in out_texts
               if any(r in t for r in PLACEHOLDER_RESIDUE)]
    report = {
        "ok": not (missing_text or missing_table or missing_img or residue),
        "missing_text": missing_text,
        "missing_table_cells": missing_table,
        "missing_images": missing_img,
        "placeholder_residue": residue,
        "stats": {"src_texts": len(src_texts), "out_texts": len(out_texts),
                  "src_images": len(src_imgs), "out_images": len(out_imgs),
                  "src_slides": len(src.slides.__iter__.__self__._sldIdLst)
                  if False else len(src.slides._sldIdLst),
                  "out_slides": len(out.slides._sldIdLst)},
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
