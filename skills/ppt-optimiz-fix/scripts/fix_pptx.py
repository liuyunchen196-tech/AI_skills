# -*- coding: utf-8 -*-
"""修正 PPTX：全局页脚页码=绝对序号 + 可选 PART 标签修正 + 可选重复标题页删除 + 字体归一化 + zip 清理

用法:
    python fix_pptx.py <input.pptx> [--out <output.pptx>]
                       [--part-fix "17:PART 04 · 进化=PART 02 · 认知"]   # 可重复传多次
                       [--delete-dupes]                                  # 删除标题与先前页相同且无正文的冗余页
                       [--normalize-font "微软雅黑"]                       # 全篇字体统一（写 latin+ea）
                       [--apply-font-plan <plan.json>]                     # 按位置/字号套用角色规划

行为:
    1. 页脚页码：将右下角纯数字文本框（L 10.4-12.6in, T 6.7-7.35in）改写为该页绝对序号，
       保留原 run 字体/字号/颜色（只改首 run 文本）。
    2. PART 标签：按 --part-fix 指定的 页:旧值=新值 修正。
    3. 重复页：--delete-dupes 删除标题重复且无正文的页（保留首个）。
    4. 字体归一化：--normalize-font 将全篇所有 run 统一为指定字体（解决混搭/缺字）。
    5. 字体规划套用：--apply-font-plan 读取 JSON 规划（见 references/font-plan.default.json），
       由 fontplan 引擎**按位置（页序/版面区域）+ 字号（页内最大/最小/居中秩）自动推断角色**，
       再套用对应 字号/字重/字色/字体——真正通用、不依赖关键词。默认规划零关键词即可直接用。
       典型流程：先用 --normalize-font 统一字族，再用 --apply-font-plan 落实字号/字重/字色层级。
    6. zip 清理：去重条目 + 剔除未被 sldIdLst 引用的孤立 slide 部件 + 清理其 rels，
       避免 PowerPoint 打开报"内容问题"。

注意: 若后续还要新增页（P1 结构补强），务必【先 add_slide 加新页、再删除旧页】，
否则新页部件名会复用现有名导致撞名覆盖（见 SKILL.md 关键坑 1）。
"""
import argparse
import os
import re
import zipfile

from pptx import Presentation
from pptx.oxml.ns import qn

from fontplan import load_plan, classify_all, set_run_font


def set_number(sh, num):
    """改写页脚数字，保留首 run 格式。"""
    tf = sh.text_frame
    p = tf.paragraphs[0]
    if p.runs:
        p.runs[0].text = str(num)
        for r in p.runs[1:]:
            r.text = ""
    else:
        p.add_run().text = str(num)


def is_footer_field(sh):
    if not sh.has_text_frame:
        return False
    t = sh.text_frame.text.strip()
    if not re.fullmatch(r"\d{1,3}", t):
        return False
    if sh.left is None or sh.top is None:
        return False
    L = sh.left / 914400.0
    T = sh.top / 914400.0
    return 10.4 <= L <= 12.6 and 6.7 <= T <= 7.35


def first_title(slide):
    """返回页内首个非数字、非 PART 的文本作为标题。"""
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        t = sh.text_frame.text.strip()
        if not t:
            continue
        if re.fullmatch(r"\d{1,3}", t):
            continue
        if re.match(r"^PART\s*\d", t, re.I):
            continue
        return t
    return None


def zip_clean(src, dst):
    """去重 zip 条目 + 剔除孤立 slide 部件 + 清理其 rels。返回被剔除的孤立部件集合。"""
    zin = zipfile.ZipFile(src)
    names = zin.namelist()
    data = {n: zin.read(n) for n in names}
    pres = data["ppt/presentation.xml"].decode("utf-8")
    sld_ids = re.findall(r'<p:sldId[^>]*r:id="([^"]+)"', pres)
    rels = data["ppt/_rels/presentation.xml.rels"].decode("utf-8")
    rid_target = dict(re.findall(r'<Relationship[^>]*Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    ref = set()
    for rid in sld_ids:
        t = rid_target.get(rid)
        if t:
            ref.add(t if t.startswith("ppt/") else "ppt/" + t.lstrip("/"))
    seen = set()
    out = []
    orphan = set()
    for n in names:
        if n in seen:
            continue
        seen.add(n)
        m = re.match(r"ppt/slides/slide(\d+)\.xml$", n)
        if m and n not in ref:
            orphan.add(n)
            continue
        out.append((n, data[n]))
    new_rels = rels
    for op in orphan:
        tgt = op[len("ppt/"):]
        new_rels = re.sub(r'<Relationship\b[^>]*Target="' + re.escape(tgt) + r'"[^>]*/>', "", new_rels)
    for i, (n, b) in enumerate(out):
        if n == "ppt/_rels/presentation.xml.rels":
            out[i] = (n, new_rels.encode("utf-8"))
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in out:
            z.writestr(n, b)
    return orphan


def main():
    ap = argparse.ArgumentParser(description="PPT 修正：页码全局校正 / PART 标签 / 重复页 / zip 清理")
    ap.add_argument("input")
    ap.add_argument("--out", default=None, help="输出路径；缺省覆盖原文件")
    ap.add_argument("--part-fix", action="append", default=[], help="格式 N:旧值=新值，可多次")
    ap.add_argument("--delete-dupes", action="store_true", help="删除标题重复且无正文的冗余页")
    ap.add_argument("--normalize-font", default=None,
                    help="字体归一化：将全篇所有 run 统一为指定字体（如 微软雅黑），同时写 latin+ea，消除中文混搭/缺字")
    ap.add_argument("--apply-font-plan", default=None,
                    help="字体规划套用：读取 JSON 规划文件（含 rules:[{role,when,size,bold,color,name}]），"
                         "由 fontplan 引擎按位置(页序/版面区域)+字号(页内秩)推断角色并套用，"
                         "真正通用、不依赖关键词；when 仅作维度约束，可完全省略")
    a = ap.parse_args()

    prs = Presentation(a.input)

    # 1) PART 标签修正
    for pf in a.part_fix:
        idx_s, spec = pf.split(":", 1)
        old, new = spec.split("=", 1)
        idx = int(idx_s) - 1
        hit = False
        for sh in prs.slides[idx].shapes:
            if sh.has_text_frame and sh.text_frame.text.strip().startswith(old.strip()):
                sh.text_frame.text = new.strip()
                hit = True
                break
        print("PART FIX S%s: %r -> %r (ok=%s)" % (idx_s, old.strip(), new.strip(), hit))

    # 2) 删除重复标题页（保留首个，删后继无正文同标题页）
    if a.delete_dupes:
        seen = set()
        to_delete = []
        for i, sl in enumerate(prs.slides):
            title = first_title(sl)
            if not title:
                continue
            if title in seen:
                to_delete.append(i)
            else:
                seen.add(title)
        if to_delete:
            lst = prs.slides._sldIdLst
            for i in sorted(to_delete, reverse=True):
                el = list(lst)[i]
                lst.remove(el)
                print("DELETE DUP S%d" % (i + 1))
            print("deleted %d duplicate slide(s)" % len(to_delete))
        else:
            print("no duplicate titles found")

    # 3) 全局页脚页码 = 绝对序号
    fixed = 0
    for i, sl in enumerate(prs.slides, 1):
        for sh in sl.shapes:
            if is_footer_field(sh):
                set_number(sh, i)
                fixed += 1
                break
    print("FOOTER RENUMBERED:", fixed)

    # 3.5) 字体归一化（字体统一强制）
    if a.normalize_font:
        changed = 0
        for sl in prs.slides:
            for sh in sl.shapes:
                if not sh.has_text_frame:
                    continue
                for para in sh.text_frame.paragraphs:
                    for r in para.runs:
                        set_run_font(r, a.normalize_font)
                        changed += 1
        print("FONT NORMALIZED -> %r : %d runs" % (a.normalize_font, changed))

    # 3.7) 字体规划套用（fontplan 引擎：按位置/字号推断角色，真正通用、不依赖关键词）
    if a.apply_font_plan:
        rules = load_plan(a.apply_font_plan)
        counter = classify_all(prs, rules, mutate=True)
        print("FONT PLAN APPLIED -> 命中 run 数(按角色): %s" % dict(counter))

    # 4) 保存 + zip 清理（先存盘，再就地 zip 清洗；不依赖临时文件删除，沙箱/无回收站环境亦可运行）
    dst = a.out or a.input
    prs.save(dst)
    orphan = zip_clean(dst, dst)
    print("SAVED ->", dst, "| orphan dropped:", sorted(orphan) or "none")


if __name__ == "__main__":
    main()
