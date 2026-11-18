#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""复评三合一对比工具：标题序列 diff + 旧问题标记 grep + QA 计数对比。

用法：
  # 1) 标题序列 diff（识别增页/删页/标题修改）
  python title_diff.py <old_dump.md> <new_dump.md>

  # 2) 在文本 dump 中检索旧问题特征串（判定 已修/未修）
  python title_diff.py --grep <dump.md> "请以贵司" "五步" "3000 万"

  # 3) QA 计数对比（blocking / overflow 逐页变化）
  python title_diff.py --qa <old_qa.json> <new_qa.json>

文本 dump 格式（python-pptx 回退 dump，与 pptx 技能流程一致）：
  === SLIDE N ===
  <文本行...>
  === SLIDE N+1 ===
  ...

QA JSON 为 qa_pptx.py --pretty 的输出，含 layout.blocking_findings 与
layout.warnings（check == 'text_overflow'）。
"""
import argparse
import json
import re
import sys
from difflib import SequenceMatcher

SLIDE_RE = re.compile(r"=== SLIDE (\d+) ===")
# 打印页码启发式：整行纯数字（1-3 位）视为页码，不作为标题
PAGE_NO_RE = re.compile(r"^\d{1,3}$")


def parse_dump(path):
    """返回 {slide_num: [lines]}。"""
    slides = {}
    cur = None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        m = SLIDE_RE.match(line)
        if m:
            cur = int(m.group(1))
            slides[cur] = []
            continue
        if cur is not None and line.strip():
            slides[cur].append(line)
    return slides


def slide_title(lines):
    """标题启发式：第一个非空、非页码、长度>=2 的行。"""
    for line in lines:
        s = line.strip()
        if len(s) >= 2 and not PAGE_NO_RE.match(s):
            return s
    return "<无文本>"


def cmd_title_diff(args):
    old = parse_dump(args.old_dump)
    new = parse_dump(args.new_dump)
    old_titles = {n: slide_title(old[n]) for n in sorted(old)}
    new_titles = {n: slide_title(new[n]) for n in sorted(new)}
    old_seq = [old_titles[n] for n in sorted(old_titles)]
    new_seq = [new_titles[n] for n in sorted(new_titles)]

    print(f"旧版: {len(old_seq)} 页 | 新版: {len(new_seq)} 页 | "
          f"页数变化: {len(new_seq) - len(old_seq):+d}")
    print()

    sm = SequenceMatcher(None, old_seq, new_seq, autojunk=False)
    new_by_old = {}  # 旧页码 -> 新页码（仅在无增删区间内可靠）
    op_blocks = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        op_blocks.append((tag, i1, i2, j1, j2))
        if tag == "equal":
            for off in range(i2 - i1):
                new_by_old[i1 + off] = j1 + off

    print("【标题序列 diff】")
    for tag, i1, i2, j1, j2 in op_blocks:
        if tag == "equal":
            continue
        for idx in range(i1, i2):
            old_pg = idx + 1
            shown = False
            if idx in new_by_old:
                new_pg = new_by_old[idx]
                print(f"  修改  旧P{old_pg} -> 新P{new_pg}: "
                      f"{old_seq[idx][:40]}  ==>  {new_seq[new_pg - 1][:40]}")
                shown = True
            if not shown and tag in ("delete", "replace"):
                print(f"  删除  旧P{old_pg}: {old_seq[idx][:40]}")
        for idx in range(j1, j2):
            new_pg = idx + 1
            matched = any(k in new_by_old and new_by_old[k] == idx for k in new_by_old)
            if not matched:
                print(f"  新增  新P{new_pg}: {new_seq[idx][:40]}")
    if not any(t != "equal" for t, _, _, _, _ in op_blocks):
        print("  无标题变化")

    # 输出页码映射（等长区间内）供后续聚焦目检
    if new_by_old:
        print()
        print("【同区间页码映射（旧->新，供聚焦目检）】")
        print("  " + ", ".join(f"{k}->{v}" for k, v in sorted(new_by_old.items())))


def cmd_grep(args):
    slides = parse_dump(args.dump)
    print(f"【旧问题标记检索】目标 dump: {args.dump}（{len(slides)} 页）")
    print()
    for pat in args.patterns:
        hits = [n for n in sorted(slides) if any(pat in ln for ln in slides[n])]
        if hits:
            print(f"  「{pat}」 → 命中页: {hits}")
        else:
            print(f"  「{pat}」 → 未命中（该问题可能已修复）")


def cmd_qa(args):
    def load(path):
        d = json.load(open(path, encoding="utf-8"))
        lay = d["layout"]
        blocking = {}
        overflow = set()
        for f in lay["blocking_findings"]:
            blocking[f["slide"]] = blocking.get(f["slide"], 0) + 1
        for f in lay["warnings"]:
            if f.get("check") == "text_overflow":
                overflow.add(f["slide"])
        return {
            "valid": d.get("valid"),
            "blocking_total": lay["finding_count"],
            "blocking_err": lay["error_count"],
            "blocking_warn": lay["warning_count"],
            "blocking": blocking,
            "overflow": overflow,
        }

    a = load(args.old_qa)
    b = load(args.new_qa)
    print("【QA 计数对比】")
    print(f"  blocking: {a['blocking_total']} -> {b['blocking_total']} "
          f"({b['blocking_total'] - a['blocking_total']:+d})")
    print(f"  errors:   {a['blocking_err']} -> {b['blocking_err']}")
    print(f"  warnings: {a['blocking_warn']} -> {b['blocking_warn']}")
    print()
    all_pg = sorted(set(a["blocking"]) | set(b["blocking"]))
    if all_pg:
        print("  blocking 逐页变化（旧->新，仅列出有变化或仍存在页）：")
        for pg in all_pg:
            av, bv = a["blocking"].get(pg, 0), b["blocking"].get(pg, 0)
            if av != bv or bv > 0:
                mark = "+" if bv > av else ("-" if bv < av else " ")
                print(f"    P{pg:<4} {av} -> {bv}  {mark}")
    print()
    print("  text_overflow 页集合变化：")
    only_a = sorted(a["overflow"] - b["overflow"])
    only_b = sorted(b["overflow"] - a["overflow"])
    print(f"    仅旧版: {only_a or '无'}")
    print(f"    仅新版: {only_b or '无'}")
    print(f"    仍存在: {sorted(a['overflow'] & b['overflow']) or '无'}")
    print()
    print("  提示：blocking 中的章节分隔页（大数字 watermark）属装饰性重叠，"
          "统计真实缺陷时应豁免。")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grep", nargs="+", metavar=("DUMP", "PATTERN"),
                    help="在文本 dump 中检索特征串")
    ap.add_argument("--qa", nargs=2, metavar=("OLD_QA", "NEW_QA"),
                    help="对比两份 qa_pptx.py JSON")
    ap.add_argument("old_dump", nargs="?", help="旧版文本 dump")
    ap.add_argument("new_dump", nargs="?", help="新版文本 dump")
    args = ap.parse_args()

    if args.grep:
        args.dump = args.grep[0]
        args.patterns = args.grep[1:]
        cmd_grep(args)
    elif args.qa:
        args.old_qa, args.new_qa = args.qa
        cmd_qa(args)
    elif args.old_dump and args.new_dump:
        cmd_title_diff(args)
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
