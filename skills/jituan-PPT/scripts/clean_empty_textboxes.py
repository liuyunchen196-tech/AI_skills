# -*- coding: utf-8 -*-
"""clean_empty_textboxes.py — 删除 PPT 里的空占位符、提示占位符与「不可见」空文本框。

用途：源稿/成品 PPT 常残留三类空壳形状：
  1) 空占位符（placeholder）—— 文本为空段落，PowerPoint 会画成虚线框并
     继承版式/母版提示语「单击此处编辑标题 / 单击此处编辑内容」，成品页上
     非常刺眼，必须删；
  2) 提示占位符 —— 文本本身就是「单击此处…」「Click to edit…」这类占位
     提示（出现在版式/母版或未填内容的页面上），同样按空壳删除；
  3) 无填充、无描边的空文本框 —— 肉眼看不见，但会占形状树、干扰统计。

清理范围覆盖三层：幻灯片（slides）、版式（slideLayouts）、母版
（slideMasters）。页面上的空壳占位符若不删，会继承版式提示语；版式/母版
里的提示占位符若不删，新建或未覆盖的页面仍会显示提示语。

用法：
    python clean_empty_textboxes.py <源.pptx>                    # 输出 <源名>_去空框.pptx
    python clean_empty_textboxes.py <源.pptx> --out <目标.pptx>  # 指定输出
    python clean_empty_textboxes.py <源.pptx> --in-place         # 直接改源文件（慎用）
    python clean_empty_textboxes.py <源.pptx> --info             # 只统计不改动

删除规则（宁可漏删，不可误删）：
  - 占位符：文本为空，或文本仅为占位提示语 → 删除
    （图片/图表/表格/媒体类占位符保留，可能是待插图位）；
  - 文本框（cNvSpPr@txBox="1"）：文本为空 且 无可见填充 且 无可见描边 → 删除；
  - 组合形状（GROUP）内逐层递归处理；
  - 其他自选图形（矩形/曲线/箭头等装饰件）即使无文字也一律保留 ——
    模板装饰块没有文字但有填充，误删会破版。

注意：默认不覆盖原文件；确认无误后再用 --in-place。
"""
import argparse
import os
import re
import sys

from pptx import Presentation
from pptx.oxml.ns import qn

_PIC_PH_TYPES = {"pic", "media", "clipart", "dgm", "chart", "tbl", "obj"}

# 占位提示语：中英文，匹配「单击此处编辑标题/内容」「Click to edit …」等
_PROMPT_RE = re.compile(
    r"(单击此处|点击此处|单击以|Click to edit|Click to add|Click to edit Master)",
    re.IGNORECASE,
)


def _sp_pr(el):
    return el.find(qn("p:spPr"))


def _has_visible_fill(el):
    sp = _sp_pr(el)
    if sp is None:
        return False
    for tag in ("a:solidFill", "a:gradFill", "a:pattFill", "a:blipFill"):
        if sp.find(qn(tag)) is not None:
            return True
    return False


def _has_visible_line(el):
    sp = _sp_pr(el)
    if sp is None:
        return False
    ln = sp.find(qn("a:ln"))
    if ln is None:
        return False
    if ln.find(qn("a:noFill")) is not None:
        return False
    return (ln.find(qn("a:solidFill")) is not None
            or ln.find(qn("a:gradFill")) is not None)


def _text(el):
    t = el.find(qn("p:txBody"))
    if t is None:
        return ""
    return "".join(x.text or "" for x in t.iter(qn("a:t"))).strip()


def _is_blank_text(el):
    return _text(el) == ""


def _is_prompt_text(el):
    """文本是否为占位提示语（单击此处… / Click to edit… 等）。

    占位符的提示语可能带多级示例（Second/Third… level），不按长度截断，
    只要命中提示词即判定为提示占位符。
    """
    txt = _text(el)
    if not txt:
        return False
    return bool(_PROMPT_RE.search(txt))


def classify(sp_el):
    """返回 'ph' / 'tb' / None。"""
    if sp_el.tag != qn("p:sp"):
        return None
    nv = sp_el.find(qn("p:nvSpPr"))
    if nv is None:
        return None
    ph = nv.find(qn("p:nvPr") + "/" + qn("p:ph"))
    cnv = nv.find(qn("p:cNvSpPr"))
    is_txbox = cnv is not None and cnv.get("txBox") == "1"
    blank = _is_blank_text(sp_el)
    prompt = _is_prompt_text(sp_el)
    if ph is not None:
        if (ph.get("type") or "").lower() in _PIC_PH_TYPES:
            return None
        # 空占位符，或仅含占位提示语的占位符 → 删
        if blank or prompt:
            return "ph"
        return None
    # 普通文本框：必须为空且不可见才删；提示文本框同样按空壳处理
    if is_txbox and (blank or prompt) and not _has_visible_fill(sp_el) and not _has_visible_line(sp_el):
        return "tb"
    return None


def _clean_shapes(shapes, dry, counter):
    stack = [shapes]
    while stack:
        shapes = stack.pop()
        for sh in list(shapes):
            try:
                if sh.shape_type == 6:  # GROUP
                    stack.append(sh.shapes)
                    continue
            except Exception:
                pass
            kind = classify(sh._element)
            if not kind:
                continue
            if not dry:
                sh._element.getparent().remove(sh._element)
            counter[kind] += 1


def _iter_parts(prs):
    """依次产出 (层级名, 形状集合)：幻灯片 → 版式 → 母版。"""
    for i, slide in enumerate(prs.slides, 1):
        yield f"第{i}页", slide.shapes
    for layout in prs.slide_layouts:
        yield f"版式 {layout.name}", layout.shapes
    for master in prs.slide_masters:
        yield "母版", master.shapes


def main():
    ap = argparse.ArgumentParser(description="删除 PPT 中的空占位符、提示占位符与不可见空文本框")
    ap.add_argument("src", help="源 PPT 路径")
    ap.add_argument("--out", help="输出路径（默认 <源名>_去空框.pptx）")
    ap.add_argument("--in-place", action="store_true", help="直接改写源文件（默认关闭）")
    ap.add_argument("--info", action="store_true", help="只统计不改动")
    args = ap.parse_args()

    prs = Presentation(args.src)
    total = {"ph": 0, "tb": 0}
    detail = []
    for label, shapes in _iter_parts(prs):
        counter = {"ph": 0, "tb": 0}
        _clean_shapes(shapes, dry=args.info, counter=counter)
        if counter["ph"] or counter["tb"]:
            detail.append(f"  {label}：空文本框 {counter['tb']} 个、空/提示占位符 {counter['ph']} 个")
        total["ph"] += counter["ph"]
        total["tb"] += counter["tb"]

    tag = "[预览]" if args.info else "[清理]"
    print(f"{tag} 共发现空文本框 {total['tb']} 个、空/提示占位符 {total['ph']} 个")
    for d in detail:
        print(d)

    if args.info:
        return 0

    if args.in_place:
        prs.save(args.src)
        print(f"[完成] 已写回源文件：{args.src}")
        return 0

    out = args.out
    if not out:
        root, ext = os.path.splitext(args.src)
        out = root + "_去空框" + (ext or ".pptx")
    prs.save(out)
    print(f"[完成] 已保存：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
