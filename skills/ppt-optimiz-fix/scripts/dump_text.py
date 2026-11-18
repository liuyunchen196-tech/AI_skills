# -*- coding: utf-8 -*-
"""将 pptx 全文逐页 dump 为 title_diff.py 所需的对比格式：

    === SLIDE N ===
    <文本行...>
    === SLIDE N+1 ===
    ...

覆盖范围：文本框（含各 paragraph 的 runs 拼接）、表格单元格、幻灯片备注。
输出纯 UTF-8 文本，每行一条文本项。title_diff.py 的 parse_dump 依赖此格式。

用法：
    python dump_text.py <input.pptx> [--out <dump.md>]

说明：
    - 不传 --out 则直接打印到 stdout；传 --out 则写文件并打印摘要。
    - 表格行以 " | " 连接各单元格；备注以 "[NOTES] " 前缀。
"""
import argparse

from pptx import Presentation


def dump(path, out):
    prs = Presentation(path)
    lines = []
    for i, sl in enumerate(prs.slides, 1):
        lines.append("=== SLIDE %d ===" % i)
        for sh in sl.shapes:
            if sh.has_text_frame:
                for para in sh.text_frame.paragraphs:
                    t = "".join(r.text for r in para.runs).strip()
                    if t:
                        lines.append(t)
            if sh.has_table:
                for row in sh.table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    line = " | ".join(c for c in cells if c)
                    if line:
                        lines.append(line)
        if sl.has_notes_slide:
            nt = sl.notes_slide.notes_text_frame.text.strip()
            if nt:
                lines.append("[NOTES] " + nt)
    text = "\n".join(lines)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("DUMPED -> %s (%d slides)" % (out, len(prs.slides)))
    else:
        print(text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="源 pptx 文件")
    ap.add_argument("--out", default=None, help="输出 dump 文件路径（缺省打印到 stdout）")
    a = ap.parse_args()
    dump(a.input, a.out)
