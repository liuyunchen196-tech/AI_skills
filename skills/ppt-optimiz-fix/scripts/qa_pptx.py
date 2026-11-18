#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""逐页 PPTX 视觉 QA：检测文字溢出(text_overflow)与越界(off_slide)，
产出 title_diff.py --qa 所需的 JSON（layout.blocking_findings / layout.warnings
/ finding_count / error_count / warning_count），供多轮复评做「缺陷计数对比」。

零外部依赖（仅 python-pptx）。度量基于 EMU，字号换算 1pt = 12700 EMU。
文字溢出采用「按字宽贪心折行」估算（区分 CJK 全角 / 西文半角），并对
PowerPoint 自动适配（auto_size != NONE 或 word_wrap=False）做豁免，避免误报。

用法：
  python qa_pptx.py <input.pptx> [--out qa.json] [--pretty]
  # --pretty 仅控制缩进（默认即缩进输出，保留以兼容 title_diff 文档）
"""
import argparse
import json
import os
import sys

from pptx import Presentation
from pptx.enum.text import MSO_AUTO_SIZE

EMU_PER_IN = 914400.0
EMU_PER_PT = 12700.0
TOL = 9144  # 越界容差 ~0.01 inch，吸收浮点/对齐误差


def is_cjk(ch):
    return ('\u4e00' <= ch <= '\u9fff') or ('\u3400' <= ch <= '\u4dbf')


def char_w_emu(ch, size_pt):
    """单字符宽度（EMU）。CJK 按全宽(1.0)，西文半角(0.5)，标点缩窄。"""
    if ch in ' \t':
        return size_pt * EMU_PER_PT * 0.25
    if ch in '.,;:!?…、，。；：！？）)':
        return size_pt * EMU_PER_PT * 0.35
    if is_cjk(ch):
        return size_pt * EMU_PER_PT * 1.0
    return size_pt * EMU_PER_PT * 0.5


def _para_size(para):
    sizes = [r.font.size.pt for r in para.runs if r.font.size is not None]
    return max(sizes) if sizes else 18.0


def estimate_overflow(sh, slide_w, slide_h):
    """返回 (overflow_bool, est_text_h_emu, avail_h_emu)。无文本返回 (False,0,0)。"""
    tf = sh.text_frame
    if not tf.text.strip():
        return False, 0, 0
    # 自动适配豁免：PPT 会自行缩放/撑大，不视为溢出
    if tf.auto_size is not None and tf.auto_size != MSO_AUTO_SIZE.NONE:
        return False, 0, 0
    ml = tf.margin_left if tf.margin_left is not None else 91440
    mr = tf.margin_right if tf.margin_right is not None else 91440
    mt = tf.margin_top if tf.margin_top is not None else 45720
    mb = tf.margin_bottom if tf.margin_bottom is not None else 45720
    avail_w = (sh.width or 0) - ml - mr
    avail_h = (sh.height or 0) - mt - mb
    if avail_w <= 0 or avail_h <= 0:
        return False, 0, 0

    wrap = tf.word_wrap  # True / False / None
    total_lines = 0
    line_h_by_para = []
    for para in tf.paragraphs:
        size = _para_size(para)
        line_h = size * 1.2 * EMU_PER_PT
        cur = 0
        plines = 0
        if wrap is False:
            # 不折行：整段占一行，按总宽判断
            tot = 0
            for r in para.runs:
                rs = r.font.size.pt if r.font.size is not None else 18.0
                for ch in r.text:
                    tot += char_w_emu(ch, rs)
            # 单行宽度超可用宽 => 水平溢出
            if tot > avail_w * 1.02:
                return True, 0, 0
            plines = 1 if para.text.strip() else 0
        else:
            for r in para.runs:
                rs = r.font.size.pt if r.font.size is not None else 18.0
                for ch in r.text:
                    if ch == '\n':
                        plines += 1
                        cur = 0
                        continue
                    w = char_w_emu(ch, rs)
                    if cur > 0 and cur + w > avail_w:
                        plines += 1
                        cur = w
                    else:
                        cur += w
            if para.text.strip():
                plines += 1
        total_lines += plines
        line_h_by_para.append((plines, line_h))

    est_h = 0
    for plines, line_h in line_h_by_para:
        est_h += plines * line_h
    return est_h > avail_h * 1.04, est_h, avail_h


def qa(pptx_path):
    prs = Presentation(pptx_path)
    slide_w = prs.slide_width
    slide_h = prs.slide_height
    findings = []
    warnings = []

    for idx, sl in enumerate(prs.slides, start=1):
        for sh in sl.shapes:
            if sh.left is None or sh.top is None or sh.width is None or sh.height is None:
                continue
            # 越界
            if (sh.left < -TOL or sh.top < -TOL or
                    (sh.left + sh.width) > slide_w + TOL or
                    (sh.top + sh.height) > slide_h + TOL):
                findings.append({
                    "slide": idx, "check": "off_slide", "severity": "error",
                    "detail": "形状越出画布(left=%.2f,top=%.2f,w=%.2f,h=%.2f)"
                              % (sh.left / EMU_PER_IN, sh.top / EMU_PER_IN,
                                 sh.width / EMU_PER_IN, sh.height / EMU_PER_IN),
                })
            # 文字溢出
            if sh.has_text_frame:
                ov, est_h, avail_h = estimate_overflow(sh, slide_w, slide_h)
                if ov:
                    warnings.append({
                        "slide": idx, "check": "text_overflow",
                        "detail": "文字超出文本框(估算高 %.0f > 可用 %.0f EMU)"
                                  % (est_h, avail_h),
                    })
                    findings.append({
                        "slide": idx, "check": "text_overflow", "severity": "warning",
                        "detail": warnings[-1]["detail"],
                    })

    finding_count = len(findings)
    error_count = sum(1 for f in findings if f.get("severity") == "error")
    warning_count = len(warnings)
    return {
        "file": os.path.basename(pptx_path),
        "valid": finding_count == 0,
        "layout": {
            "slide_count": len(prs.slides),
            "finding_count": finding_count,
            "error_count": error_count,
            "warning_count": warning_count,
            "blocking_findings": findings,
            "warnings": warnings,
        },
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="待检测 pptx 路径")
    ap.add_argument("--out", help="输出 JSON 路径（缺省打印到 stdout）")
    ap.add_argument("--pretty", action="store_true",
                    help="缩进输出（默认即缩进，保留以兼容 title_diff 文档）")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print("ERROR: 文件不存在 %s" % args.input, file=sys.stderr)
        sys.exit(1)

    result = qa(args.input)
    text = json.dumps(result, ensure_ascii=False, indent=2)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fp:
            fp.write(text + "\n")
        print("QA 完成 -> %s | blocking=%d (err=%d, warn=%d) | valid=%s"
              % (args.out, result["layout"]["finding_count"],
                 result["layout"]["error_count"], result["layout"]["warning_count"],
                 result["valid"]))
    else:
        print(text)


if __name__ == "__main__":
    main()
