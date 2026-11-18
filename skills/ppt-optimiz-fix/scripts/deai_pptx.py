# -*- coding: utf-8 -*-
"""去AI味 修正要点报告生成器

基于 ai_tells.scan 的检测结果，产出**明确覆盖两类**的修正要点：
  A. 界面风格优化要点（版式/配色/字体/间距/层级的人工化）
  B. 文本去AI化要点（过渡句/黑话/排比/空洞的具体位置+原句+建议改写）

用法:
    python deai_pptx.py <file.pptx> [--out <report.md>]
输出: Markdown 报告（默认 去AI味修正要点_<原名>.md），并打印到 stdout。
"""
import os
import re
import sys
from collections import Counter

from pptx import Presentation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_tells import scan as ai_scan


def find_context(full_text, token, width=18):
    """在整页文本中定位 token 的短上下文，便于报告引用原句"""
    idx = full_text.find(token)
    if idx < 0:
        return token
    s = max(0, idx - width)
    e = min(len(full_text), idx + len(token) + width)
    return full_text[s:e].replace("\n", " ")


def build_report(prs, path):
    r = ai_scan(prs)
    name = os.path.splitext(os.path.basename(path))[0]
    lines = []
    lines.append("# 去AI味修正要点报告 · %s\n" % name)

    # 概览
    tp = r["template"]
    template_score = 10 if tp["homogeneous"] else 0
    ai_score = len(r["transitions"]) + len(r["buzz"]) + len(r["abstract"]) + len(r["parallel"]) + template_score
    level = "重" if ai_score >= 15 else ("中" if ai_score >= 6 else "轻")
    lines.append("## 概览")
    lines.append("- AI 味指数(估): **%d** → 程度：**%s**" % (ai_score, level))
    lines.append("- 机械化过渡句: %d 处 ｜ 黑话/套话: %d 处 ｜ 空洞抽象: %d 处 ｜ 过度工整排比: %d 页"
                 % (len(r["transitions"]), len(r["buzz"]), len(r["abstract"]), len(r["parallel"])))
    if tp["homogeneous"]:
        lines.append("- 界面模板感: ⚠️ %d%% 内容页版式签名一致（%s）" % (tp["pct"], tp["mode_sig"]))
    else:
        lines.append("- 界面模板感: ✅ 版式一致性 %d%%（有变化，未达模板感阈值）" % tp["pct"])
    lines.append("")

    # ===== A. 界面风格优化要点 =====
    lines.append("## A. 界面风格优化要点")
    if tp["homogeneous"]:
        slides = tp["slides"]
        rng = "S%d–S%d" % (slides[0], slides[-1]) if len(slides) > 1 else "S%d" % slides[0]
        lines.append("- **[模板感] %s**：%d%% 内容页版式签名 %s 完全一致，呈现明显生成器审美。"
                     % (rng, tp["pct"], tp["mode_sig"]))
        lines.append("  - 改法：在同章节内注入版式变化——调整卡片数量/位置/图文左右互换/留白偏移；"
                     "打破绝对对称，让画面有「人手摆过」的痕迹；强调色只点一处、主色占比故意倾斜。")
    else:
        lines.append("- 版式签名一致性 %d%%（<70%%），已具备一定变化，保持即可。" % tp["pct"])
    lines.append("- **[配色]** 检查：主色是否绝对均匀（60-30-10 精确等分显假）→ 改为故意倾斜；"
                 "掺入低饱和「脏」色、避免荧光纯色，增加真实呼吸感。")
    lines.append("- **[字体]** 检查：标题是否全用安全黑体缺性格 → 标题换一款有特征的中文字体（思源宋体/站酷系列）点睛；"
                 "拉大字重对比，标题紧字距、正文松行距。")
    lines.append("- **[层级]** 检查：是否全靠边框卡片堆叠建立层级 → 改以留白+对齐+字号建立层级，减少全边框卡片。")
    lines.append("- **[细节]** 检查：分隔线是否贯穿、页码/标签是否绝对统一 → 改为非贯穿分隔线、标签位置微变化，加入真实截图/批注感元素。")
    lines.append("")

    # ===== B. 文本去AI化要点 =====
    lines.append("## B. 文本去AI化要点")
    rows = []
    # 过渡句
    for s, w in r["transitions"]:
        ctx = find_context(r["full"][s], w)
        rows.append((s, "机械化过渡句", ctx,
                     "删去此类过渡句，用结论直接衔接；段间改用「但是/所以/换个角度」等真实逻辑词。"))
    # 黑话重灾区
    for s in r["red_slides"]:
        words = [w for w, _ in r["buzz_by_slide"][s].items()]
        sample = "、".join(words[:4])
        rows.append((s, "黑话/套话堆砌", "含：%s" % sample,
                     "将黑话改为口语化业务词（如「赋能业务」→「让销售少做重复活」）；单页黑话控制在 2 个内。"))
    # 空洞抽象
    for s, a in r["abstract"]:
        rows.append((s, "空洞抽象", a,
                     "补充具体主语+数字+场景（如「效率显著提升」→「客服响应 8 分钟→90 秒（内测）」）。"))
    # 排比
    for s, kind, items in r["parallel"]:
        sample = "；".join(items[:3])
        rows.append((s, "过度工整排比(%s)" % kind, sample,
                     "打破工整：长短交错或 2+1，留最重要一条，其余并入正文，避免生成器凑齐感。"))

    if not rows:
        lines.append("- ✅ 未检出具象 AI 味文本痕迹，建议仍人工通读一遍过渡与案例语气。")
    else:
        rows.sort(key=lambda x: x[0])
        lines.append("| 页 | 类型 | 原句/样例 | 建议改写 |")
        lines.append("|---|---|---|---|")
        for s, typ, orig, fix in rows:
            lines.append("| S%d | %s | %s | %s |" % (s, typ, orig, fix))
    lines.append("")

    lines.append("> 说明：A/B 两类要点须同时覆盖，方可达成「视觉+文案」双线去AI味。"
                 "文本改写由人工/智能体按要点落地；界面变化需回到生成脚本或手动调整版式。")
    return "\n".join(lines)


def main(path, out=None):
    try:
        prs = Presentation(path)
    except Exception:
        print("❌ 无法读取该文件：可能不是有效的 .pptx、已损坏，或正被其他程序占用（%s）" % path,
              file=sys.stderr)
        sys.exit(1)
    report = build_report(prs, path)
    print(report)
    if out is None:
        base = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(os.path.dirname(os.path.abspath(path)), "去AI味修正要点_%s.md" % base)
    with open(out, "w", encoding="utf-8") as f:
        f.write(report)
    print("\n[已保存报告] %s" % out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python deai_pptx.py <file.pptx> [--out <report.md>]")
        sys.exit(1)
    out_arg = None
    args = sys.argv[1:]
    if "--out" in args:
        i = args.index("--out")
        out_arg = args[i + 1]
        args = args[:i] + args[i + 2:]
    main(args[0], out_arg)
