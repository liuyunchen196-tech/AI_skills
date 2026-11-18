# -*- coding: utf-8 -*-
"""PPT 优化修复顾问 · 一键编排器

把分散的 inspect / report / fix / deai / 复评 多脚本收敛为单命令，直接拉满易用性。

用法：
  # 1) 评估（默认）：诊断 + 评估报告(HTML/MD/JSON)
  python run_all.py <deck.pptx>
  python run_all.py <deck.pptx> --mode assess --out DIR --report-formats html,md,json

  # 2) 优化闭环：诊断 → 自动修 P0(页码/删重/字体归一/zip) → 重新评估报告
  python run_all.py <deck.pptx> --mode optimize [--font 微软雅黑] [--plan plan.json] [--delete-dupes]

  # 3) 去AI味要点报告
  python run_all.py <deck.pptx> --mode deai

  # 4) 全套：assess + optimize + deai
  python run_all.py <deck.pptx> --mode all

  # 5) 复评（跨版本 diff / 问题流转）
  python run_all.py --rereview --old 旧版.pptx --new 新版.pptx [--grep "请以贵司" "五步"] [--work DIR]

说明：
  - 用运行本脚本的同一 python（应为隔离 venv）调用各子脚本，保证环境一致。
  - optimize 默认先备份原文件到 <out>/backups/，修复结果另存 <名>_修订.pptx，不破坏原稿。
  - 复评模式自动完成 dump_text + qa_pptx + title_diff 三步，输出标题 diff / QA 计数对比 / 旧问题 grep。
"""
import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable  # 用运行 run_all 的同一 python（venv）


def _run(script, *args):
    """调用同级脚本；返回 CompletedProcess。"""
    cmd = [PY, os.path.join(SCRIPT_DIR, script)] + list(args)
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.stdout.strip():
        print(p.stdout.rstrip())
    if p.returncode != 0:
        if p.stderr.strip():
            print(p.stderr.rstrip(), file=sys.stderr)
        raise RuntimeError("[run_all] 子脚本失败: %s (code=%d)" % (script, p.returncode))
    return p


def _bname(path):
    return os.path.splitext(os.path.basename(path))[0]


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def run_assess(deck, out, fmts, aud_terms=None):
    base = out or os.path.dirname(os.path.abspath(deck))
    os.makedirs(base, exist_ok=True)
    name = _bname(deck)
    args = [deck]
    html_path = None
    if "html" in fmts:
        html_path = os.path.join(base, "%s_评估报告.html" % name)
        args += ["--html", html_path]
    if "md" in fmts:
        args += ["--md", os.path.join(base, "%s_评估报告.md" % name)]
    if "json" in fmts:
        args += ["--json", os.path.join(base, "%s_评估报告.json" % name)]
    if aud_terms:
        args += ["--aud-terms", aud_terms]
    print("\n===== [1/1] 评估：诊断 + 报告 =====")
    _run("report_pptx.py", *args)
    return html_path


def run_optimize(deck, out, font, plan, delete_dupes, backup, aud_terms=None):
    base = out or os.path.dirname(os.path.abspath(deck))
    os.makedirs(base, exist_ok=True)
    name = _bname(deck)
    fixed = os.path.join(base, "%s_修订.pptx" % name)
    if backup:
        bk = os.path.join(base, "backups")
        os.makedirs(bk, exist_ok=True)
        bk_path = os.path.join(bk, "%s_%s.pptx" % (name, _stamp()))
        shutil.copy(deck, bk_path)
        print("[备份] 原稿已备份至", bk_path)
    args = [deck, "--out", fixed]
    if font:
        args += ["--normalize-font", font]
    if plan:
        args += ["--apply-font-plan", plan]
    if delete_dupes:
        args += ["--delete-dupes"]
    print("\n===== [1/2] 自动修复 P0（页码/删重/字体归一/zip） =====")
    _run("fix_pptx.py", *args)
    print("\n===== [2/2] 重新评估修复稿 =====")
    html = run_assess(fixed, base, ["html", "md", "json"], aud_terms)
    print("\n[优化闭环完成] 产出：", fixed)
    return html


def run_deai(deck, out):
    base = out or os.path.dirname(os.path.abspath(deck))
    os.makedirs(base, exist_ok=True)
    name = _bname(deck)
    out_md = os.path.join(base, "去AI味修正要点_%s.md" % name)
    print("\n===== 去AI味要点报告 =====")
    _run("deai_pptx.py", deck, "--out", out_md)


def run_all(deck, out, font, plan, delete_dupes, backup, aud_terms=None):
    print("\n########## 模式 ALL：评估 → 优化 → 去AI味 ##########")
    run_assess(deck, out, ["html", "md", "json"], aud_terms)
    html = run_optimize(deck, out, font, plan, delete_dupes, backup, aud_terms)
    run_deai(deck, out)
    return html


def run_rereview(old, new, work, greps):
    import tempfile
    # 核对源文件是否真更新（mtime + size），未变则直接告知无需复评，避免白跑管线
    try:
        st_old = os.stat(old)
        st_new = os.stat(new)
        if st_old.st_mtime == st_new.st_mtime and st_old.st_size == st_new.st_size:
            print("\n[无需复评] 新旧文件相同（mtime 与 size 一致），未发生变化。")
            return
    except OSError:
        pass
    work = work or tempfile.mkdtemp(prefix="rereview_")
    os.makedirs(work, exist_ok=True)
    old_dump = os.path.join(work, "old_dump.md")
    new_dump = os.path.join(work, "new_dump.md")
    old_qa = os.path.join(work, "old_qa.json")
    new_qa = os.path.join(work, "new_qa.json")
    print("########## 模式 REREVIEW：跨版本复评 ##########")
    print("[工作目录]", work)
    print("\n----- dump 文本 -----")
    _run("dump_text.py", old, "--out", old_dump)
    _run("dump_text.py", new, "--out", new_dump)
    print("\n----- 逐页 QA -----")
    _run("qa_pptx.py", old, "--out", old_qa)
    _run("qa_pptx.py", new, "--out", new_qa)
    print("\n===== 标题序列 diff =====")
    _run("title_diff.py", old_dump, new_dump)
    print("\n===== QA 计数对比 =====")
    _run("title_diff.py", "--qa", old_qa, new_qa)
    if greps:
        print("\n===== 旧问题标记检索（判定 已修/未修） =====")
        _run("title_diff.py", "--grep", new_dump, *greps)
    print("\n[复评完成] dump/qa 产物位于", work)


def main():
    ap = argparse.ArgumentParser(
        prog="run_all.py",
        description="PPT 优化修复顾问 · 一键编排器（评估/优化/去AI味/复评）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", nargs="?", help="目标 pptx（assess/optimize/deai/all 模式）")
    ap.add_argument("--mode", default="assess",
                    choices=["assess", "optimize", "deai", "all"],
                    help="运行模式（默认 assess 评估）")
    ap.add_argument("--out", default=None, help="产出目录（默认源文件同目录）")
    ap.add_argument("--font", default=None, help="optimize 模式：字体归一目标字体（如 微软雅黑）")
    ap.add_argument("--plan", default=None, help="optimize 模式：字体规划 JSON（--apply-font-plan）")
    ap.add_argument("--delete-dupes", action="store_true", help="optimize 模式：删除重复标题页")
    ap.add_argument("--no-backup", action="store_true", help="optimize 模式：跳过原稿备份")
    ap.add_argument("--report-formats", default="html,md,json",
                    help="评估报告格式（逗号分隔：html,md,json）")
    ap.add_argument("--aud-terms", default=None,
                    help="外部受众/说服力术语表 JSON（覆盖内置默认，适配特定行业）")
    ap.add_argument("--rereview", action="store_true", help="进入复评模式（需 --old/--new）")
    ap.add_argument("--old", default=None, help="复评：旧版 pptx")
    ap.add_argument("--new", default=None, help="复评：新版 pptx")
    ap.add_argument("--work", default=None, help="复评：中间产物目录")
    ap.add_argument("--grep", nargs="+", default=None, help="复评：旧问题特征串（判定已修/未修）")
    a = ap.parse_args()

    if a.rereview:
        if not a.old or not a.new:
            ap.error("复评模式需同时提供 --old 与 --new")
        run_rereview(a.old, a.new, a.work, a.grep)
        return

    if not a.deck:
        ap.error("需提供目标 deck.pptx，或使用 --rereview")
    if not os.path.exists(a.deck):
        ap.error("文件不存在: %s" % a.deck)

    fmts = [x.strip().lower() for x in a.report_formats.split(",") if x.strip()]
    backup = not a.no_backup

    print("═══════════════════════════════════════════════")
    print(" PPT 优化修复顾问 · 一键编排器")
    print(" 目标：%s" % a.deck)
    print(" 模式：%s" % a.mode)
    print("═══════════════════════════════════════════════")

    try:
        if a.mode == "assess":
            html = run_assess(a.deck, a.out, fmts, a.aud_terms)
        elif a.mode == "optimize":
            html = run_optimize(a.deck, a.out, a.font, a.plan, a.delete_dupes, backup, a.aud_terms)
        elif a.mode == "deai":
            run_deai(a.deck, a.out)
            html = None
        elif a.mode == "all":
            html = run_all(a.deck, a.out, a.font, a.plan, a.delete_dupes, backup, a.aud_terms)
    except RuntimeError as e:
        print("\n❌ 处理失败：%s" % e, file=sys.stderr)
        print("   可能原因：文件不是有效的 .pptx、已被损坏、或正被其他程序占用。", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print("\n❌ 处理失败：%s" % e, file=sys.stderr)
        sys.exit(1)

    print("\n✅ 全部完成。评估报告已生成，请直接打开对应 HTML 文件查看。")


if __name__ == "__main__":
    main()
