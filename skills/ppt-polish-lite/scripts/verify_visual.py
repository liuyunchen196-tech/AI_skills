"""渲染即验收编排器（v3.2.6，方案 A）：一条命令串完「渲染 → L3 像素分析 → AI 味双检测 → L1 必读清单」。

为什么需要（用户问题："是否需要让 skill 也具备看到图片的能力"）：
  此前 L1 读图靠执行 agent 自觉，渲染/L3/AI 味检测是三条散命令——忘了跑就退化为"lint 通过就交差"。
  本脚本把"看图"变成渲染的强制后置动作：漏看在机制上不可能。

流程：
  1. render.py        渲染 PNG（WPS/PowerPoint COM）
  2. visual_check     逐张 L3 像素分析（verdict: PASS/WARN）
  3. ai_flavor XML    形状级 AI 味检测（顶弧层/标题竖条/下划线/渐变/非令牌色）
  4. ai_flavor PNG    像素级 AI 味检测（连通域：孤立横带/竖条/渐变痕迹）
  5. 汇总输出：
     · 每页三列体检结果
     · L1 必读页清单 = L3 WARN 页 ∪ AI 味嫌疑页（无嫌疑时抽首尾 2 页做基线）
     · 最终结论：CLEAN（可直接交付）/ READ_REQUIRED（按清单读图）/ FIX_REQUIRED（先修复再渲染）

用法：
  python verify_visual.py <pptx> --out <render_dir> [--skip-render] [--json]
"""
from __future__ import annotations
import sys
import json
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS))

from ai_flavor import detect as xml_detect, detect_png_dir  # noqa: E402


def main():
    if len(sys.argv) < 2 or "--out" not in sys.argv:
        print(__doc__)
        sys.exit(1)
    pptx = sys.argv[1]
    out_dir = sys.argv[sys.argv.index("--out") + 1]
    skip_render = "--skip-render" in sys.argv

    # 1. 渲染
    if not skip_render:
        print("[1/4] 渲染 PNG ...")
        subprocess.run([sys.executable, str(SCRIPTS / "render.py"), pptx, out_dir],
                       capture_output=True, text=True)

    # 2. L3 逐张分析
    print("[2/4] L3 像素分析 ...")
    pngs = sorted(Path(out_dir).glob("*.png"))
    verdicts: dict[str, dict] = {}
    for p in pngs:
        if p.name.startswith("_"):
            continue
        try:
            r = subprocess.run([sys.executable, str(SCRIPTS / "visual_check.py"), "analyze", str(p)],
                               capture_output=True, text=True, timeout=120)
            d = json.loads(r.stdout[r.stdout.index("{"):])
            verdicts[p.name] = {"verdict": d.get("verdict", "?"), "problems": d.get("problems", [])}
        except Exception as e:
            verdicts[p.name] = {"verdict": "ERR", "problems": [str(e)[:80]]}

    # 3. XML 级 AI 味（detect 返回 (findings, prs)，只需 findings）
    print("[3/4] AI 味形状检测 ...")
    xml_hits, _prs = xml_detect(pptx)
    xml_by_page: dict[int, list] = {}
    for f in xml_hits:
        xml_by_page.setdefault(f["page"], []).append(f["kind"])

    # 4. 像素级 AI 味
    print("[4/4] AI 味像素检测 ...")
    px_hits = detect_png_dir(out_dir)

    # 汇总
    total = len(verdicts)
    warn_pages = sorted(k for k, v in verdicts.items() if v["verdict"] == "WARN")
    xml_pages = sorted(f"P{n:02d}" for n in xml_by_page)
    px_pages = sorted(px_hits.keys())
    suspect = set()
    for k in warn_pages:
        suspect.add(k)
    for name in px_hits:
        suspect.add(name)
    # XML 嫌疑页 → 幻灯片N.PNG 名映射（按页序）
    n_slides = total
    for n in xml_by_page:
        if n <= n_slides:
            suspect.add(f"幻灯片{n}.PNG")
    must_read = sorted(suspect)
    baseline = []
    if not must_read and pngs:
        keep = [pngs[0].name, pngs[-1].name]
        baseline = [k for k in keep if k in verdicts]

    print("\n========== 渲染即验收报告 ==========")
    print(f"文件: {Path(pptx).name}   渲染: {total} 张")
    l3_warn = len(warn_pages)
    xml_n = len(xml_hits)
    px_n = sum(len(v) for v in px_hits.values())
    print(f"L3 像素分析 : {total - l3_warn}/{total} PASS，{l3_warn} WARN")
    print(f"AI 味(形状) : {xml_n} 处 / {len(xml_by_page)} 页")
    print(f"AI 味(像素) : {px_n} 处 / {len(px_hits)} 页")

    if l3_warn:
        for k in warn_pages:
            print(f"  L3 WARN {k}: {verdicts[k]['problems']}")
    if xml_by_page:
        for n in sorted(xml_by_page):
            print(f"  XML 嫌疑 P{n:02d}: {', '.join(sorted(set(xml_by_page[n])))}")
    if px_hits:
        for name in sorted(px_hits):
            kinds = [f["kind"] for f in px_hits[name]]
            print(f"  像素嫌疑 {name}: {', '.join(sorted(set(kinds)))}")

    if must_read:
        print(f"\n结论: READ_REQUIRED — L1 必读 {len(must_read)} 页: {'、'.join(must_read)}")
        print("（读图复核定性：AI 味→修复重渲；布局 WARN→按 visual_check 口径处理）")
        code = 1
    elif baseline:
        print(f"\n结论: CLEAN — 全部机器检查通过；按惯例抽读基线页 {'、'.join(baseline)} 后可交付")
        code = 0
    else:
        print("\n结论: CLEAN — 全部机器检查通过")
        code = 0

    if "--json" in sys.argv:
        # findings 里含 live Shape 引用（供 --fix 用），JSON 输出只保留可序列化字段
        xml_safe = [{k: v for k, v in f.items() if isinstance(v, (str, int, float, bool))}
                    for f in xml_hits]
        print(json.dumps({
            "total": total, "l3_warn_pages": warn_pages,
            "xml_hits": xml_safe, "px_hits": {k: len(v) for k, v in px_hits.items()},
            "must_read": must_read, "verdict": "READ_REQUIRED" if must_read else "CLEAN",
        }, ensure_ascii=False, indent=1))
    sys.exit(code)


if __name__ == "__main__":
    main()
