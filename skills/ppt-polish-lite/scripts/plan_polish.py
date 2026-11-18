#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase B — 形成统一方案：读 analysis.json（+ 用户意图/主色覆盖），产出 polish_plan.json。

决策顺序（主色）:
    用户 --primary 覆盖  >  主题 accent1  >  全 deck dominant  >  兜底科技蓝 #1677FF
并据此生成完整色板（深主色 / 浅底 / 图标底），再按色相推荐命名方案。

逐页动作:
    bespoke（用户随手写、不用母版）  -> unify   （逐页挖色/字，按 plan 色板统一）
    master-driven 且颜色一致        -> keep    （保留，仅必要时微调）
    意图含 reflow 且内容可映射版式  -> reflow  （交 slide_emit 重排）

语义色（红/绿/黄）默认列入「保留例外」，不强行并入主色——是否真语义需 context.py 确认。

用法:
    python plan_polish.py analysis.json [--intent beautify,unify,remove_ai,reflow]
                                    [--primary #1677FF] [--scheme tech-blue]
                                    [--out polish_plan.json] [--emit-rules refine_rules.json]

Phase B 按用户选择「自动执行」：本脚本只产出方案（记录），不暂停；执行由 Phase C 读取 plan 进行。
"""
import sys, os, io, json, argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# slide_emit 提供 _make_palette / PALETTES / DEFAULT_PALETTE
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slide_emit import _make_palette, PALETTES, DEFAULT_PALETTE

DEFAULT_FALLBACK = "#1677FF"
NEUTRAL_GRAYS = {"#1F2937", "#4B5563", "#9CA3AF", "#E5E7EB", "#FFFFFF", "#F8FAFF", "#F3F4F6"}


# ---------------------------------------------------------------- 颜色工具
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join("%02X" % max(0, min(255, int(c))) for c in rgb)


def hsl_of(h):
    r, g, b = (c / 255.0 for c in hex_to_rgb(h))
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    l = (mx + mn) / 2
    if d == 0:
        return 0.0, 0.0, l
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h_ = (g - b) / d + (6 if g < b else 0)
    elif mx == g:
        h_ = (b - r) / d + 2
    else:
        h_ = (r - g) / d + 4
    return h_ * 60, s * 100, l * 100


def from_hsl(h, s, l):
    h = ((h % 360) + 360) % 360
    s /= 100.0
    l /= 100.0
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return rgb_to_hex(( (r + m) * 255, (g + m) * 255, (b + m) * 255 ))


def hue_name(h):
    hh, s, l = hsl_of(h)
    if s < 18 or l < 12 or l > 92:
        return "neutral"
    if hh < 15 or hh >= 345:
        return "red"
    if hh < 45:
        return "orange"
    if hh < 70:
        return "yellow"
    if hh < 165:
        return "green"
    if hh < 195:
        return "teal"
    if hh < 255:
        return "blue"
    if hh < 290:
        return "indigo"
    return "purple"


def is_neutral(h):
    if not h:
        return True
    r, g, b = hex_to_rgb(h)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn < 24:            # 近灰（饱和低）
        return True
    if mn >= 245:              # 近白（三通道都亮，注意不能用 mx>=245 否则误杀纯黄/纯青）
        return True
    if mx <= 12:               # 近黑
        return True
    return False


def make_triad(primary):
    """由主色生成 深主色 / 浅底 / 图标底。"""
    h, s, l = hsl_of(primary)
    deep = from_hsl(h, max(s, 35), max(l - 38, 12))
    tint = from_hsl(h, min(s, 55), 95)
    icon_bg = from_hsl(h, min(s, 60), 88)
    return deep, tint, icon_bg


HUE_TO_SCHEME = {
    "red": "cherry-bold",
    "orange": "warm-terracotta",
    "yellow": "warm-terracotta",
    "green": "forest-moss",
    "teal": "teal-trust",
    "blue": "tech-blue",
    "indigo": "midnight-executive",
    "purple": "berry-cream",
    "neutral": "tech-blue",
}


def resolve_primary(an, args):
    """决策主色：用户 > theme_accent1 > dominant > 兜底。"""
    if args.primary:
        p = args.primary.strip()
        if p.startswith("#") or (len(p) == 6 and all(c in "0123456789abcdefABCDEF" for c in p)):
            return ("#" + p.lstrip("#")).upper(), "user_override"
    ta = an.get("theme_accent1")
    if ta and not is_neutral(ta):
        return ta.upper(), "theme_accent1"
    dom = an.get("dominant_color", {}).get("hex")
    if dom and not is_neutral(dom):
        return dom.upper(), "dominant"
    return DEFAULT_FALLBACK.upper(), "fallback_tech_blue"


def recommend_scheme(primary, args):
    if args.scheme and args.scheme in PALETTES:
        return args.scheme
    return HUE_TO_SCHEME.get(hue_name(primary), "tech-blue")


def build_plan(an, args):
    primary, src = resolve_primary(an, args)
    deep, tint, icon_bg = make_triad(primary)
    scheme = recommend_scheme(primary, args)
    palette = _make_palette(primary, deep, tint, icon_bg)

    intent = set(x.strip() for x in (args.intent or "beautify,unify").split(",") if x.strip())

    # 字体统一：取出现最多的字体；无则默认
    font_dist = an.get("font_distribution", {})
    font_family = (max(font_dist, key=font_dist.get) if font_dist
                   else '"微软雅黑", "PingFang SC", "Microsoft YaHei", sans-serif')

    # 逐页动作
    pages = an.get("pages", [])
    actions = []
    for pg in pages:
        if pg.get("bespoke"):
            act = "unify" if ("unify" in intent or "beautify" in intent) else "keep"
        else:
            act = "keep"
        if "reflow" in intent and pg.get("char_count", 0) > 80:
            act = "reflow"
        actions.append({
            "index": pg["index"],
            "action": act,
            "layout": pg.get("layout"),
            "master_driven": pg.get("master_driven"),
        })

    # 语义色例外
    semantic = []
    for c in an.get("color_distribution", {}):
        if is_neutral(c):
            continue
        hn = hue_name(c)
        if hn in ("red", "green", "yellow") and c.upper() != primary.upper():
            semantic.append(c)

    plan = {
        "source": an.get("source"),
        "primary_color": {"hex": primary, "source": src},
        "recommended_scheme": scheme,
        "palette": palette,
        "font_family": font_family,
        "intent": sorted(intent),
        "unify_items": [
            "色板收敛到 1 个主色 + 中性灰阶（禁用多彩色并存）",
            "字体收敛到 %s" % font_family,
            "标题层级 / 页脚 / 间距按 references/layout-whitespace-graphics.md 标准化",
            "浓色只做点睛，铺底用 tint 或白",
        ],
        "per_page_actions": actions,
        "semantic_exceptions": sorted(set(semantic)),
        "master_usage_rate": an.get("master_usage_rate"),
        "overall_issues": an.get("overall_issues", []),
        "note": "Phase B 自动执行：本方案为记录，Phase C 读取 plan.palette 进行统一/重排。",
    }
    return plan, primary, intent


def emit_refine_rules(an, primary, plan, path):
    """把 plan 落成 refine.py 的 rules.json（仅 unify 意图时）。"""
    fills = []
    primary_u = primary.upper()
    seen = set()
    for c in an.get("color_distribution", {}):
        cu = c.upper()
        if cu in seen or cu == primary_u:
            continue
        if is_neutral(c):
            continue
        if cu in {s.upper() for s in plan.get("semantic_exceptions", [])}:
            continue
        seen.add(cu)
        fills.append({"from": cu, "to": primary_u})
    fonts = []
    target = plan["font_family"]
    for f in an.get("font_distribution", {}):
        if f != target:
            fonts.append({"from": f, "to": target})
    rules = {}
    if fills:
        rules["fill"] = fills
    if fonts:
        rules["font"] = fonts
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(rules, fp, ensure_ascii=False, indent=2)
    return rules


def render_plan_md(plan, an=None):
    """把结构化方案渲染成人读的检查清单 Markdown（脚本生成，不依赖 LLM）。

    这是 Phase B 的「美化方案」交付物：机器契约由 polish_plan.json 承担，
    本函数产出同义可读版，供对话层直接 present 给用户审阅。
    """
    pal = plan.get("palette", {})
    pc = plan.get("primary_color", {})
    lines = []
    lines.append("# PPT 美化方案（Phase B 产物）\n")
    src = plan.get("source") or (an.get("source") if an else "")
    if src:
        lines.append("**源文件**：`%s`  " % src)
    lines.append("**页面数**：%s  " % (an.get("slide_count") if an else "?"))
    lines.append("**母版使用率**：%s  " % plan.get("master_usage_rate"))
    lines.append("**意图**：%s\n" % "、".join(plan.get("intent", [])))

    lines.append("## 1. 主色决策")
    lines.append("- 采用主色：**%s**" % pc.get("hex"))
    lines.append("- 来源：%s（优先级：用户指定 > 主题 accent1 > 全篇 dominant > 兜底科技蓝）" % pc.get("source"))
    lines.append("- 推荐配色方案：**%s**（见 references/color-schemes.md）\n" % plan.get("recommended_scheme"))

    lines.append("## 2. 建议色板")
    lines.append("- 主色 `primary`：%s" % pal.get("primary"))
    lines.append("- 深主色 `primary_deep`：%s" % pal.get("primary_deep"))
    lines.append("- 浅底 `accent_tint`：%s" % pal.get("accent_tint"))
    lines.append("- 图标底 `icon_bg`：%s" % pal.get("icon_bg"))
    lines.append("- 主文字 `text_main`：%s" % pal.get("text_main"))
    lines.append("- 次文字 `text_sub`：%s" % pal.get("text_sub"))
    lines.append("- 分隔线 `divider`：%s" % pal.get("divider"))
    lines.append("- 语义色：成功 %s ｜ 警告 %s ｜ 危险 %s\n" % (
        pal.get("success"), pal.get("warning"), pal.get("danger")))

    lines.append("## 3. 字体")
    lines.append("- 统一字体族：%s\n" % plan.get("font_family"))

    lines.append("## 4. 统一项清单（unify_items）")
    for it in plan.get("unify_items", []):
        lines.append("- [ ] %s" % it)
    lines.append("")

    lines.append("## 5. 逐页动作表")
    lines.append("| 页 | 母版驱动 | 动作 | 说明 |")
    lines.append("| --- | --- | --- | --- |")
    pages = {p["index"]: p for p in (an.get("pages", []) if an else [])}
    for a in plan.get("per_page_actions", []):
        idx = a.get("index")
        lay = a.get("layout") or (pages.get(idx, {}).get("layout") or "—")
        note = ""
        if a.get("action") == "keep":
            note = "母版承载良好，保留"
        elif a.get("action") == "unify":
            note = "逐页挖色/字统一（非母版页）"
        elif a.get("action") == "reflow":
            note = "内容偏多，建议重排"
        lines.append("| %s | %s | %s | %s |" % (
            idx + 1, "是" if a.get("master_driven") else "否", a.get("action"), note))
    lines.append("")

    sem = plan.get("semantic_exceptions", [])
    if sem:
        lines.append("## 6. 语义色例外（不强制统一）")
        lines.append("以下颜色作为状态/语义色保留：%s\n" % "、".join(sem))

    issues = plan.get("overall_issues", [])
    if issues:
        lines.append("## 7. 现状问题（来自 Phase A）")
        for it in issues:
            lines.append("- %s" % it)
        lines.append("")

    lines.append("## 8. 执行说明")
    lines.append("- 本方案为 **Phase B 记录产物**，Phase C 读取 `plan.palette` / `unify_items` 执行统一或重排。")
    lines.append("- 用户对方案的修改（如\"主色换成 X\"\"标题再大些\"）由对话层更新意图/参数后重新运行本脚本迭代生成新方案。")
    lines.append("- 机器契约见同目录 `polish_plan.json`；批量改色规则见 `refine_rules.json`（由 `--emit-rules` 生成）。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("analysis")
    ap.add_argument("--intent", default="beautify,unify")
    ap.add_argument("--primary", default=None)
    ap.add_argument("--scheme", default=None)
    ap.add_argument("--out", default=None, help="默认 <analysis 同目录>/polish_plan.json")
    ap.add_argument("--emit-rules", default=None, help="输出 refine.py 的 rules.json；默认 <analysis 同目录>/refine_rules.json")
    ap.add_argument("--render-md", default=None,
                    help="渲染人读方案 MD；默认 <analysis 同目录>/polish_plan.md；传 'no' 可关闭")
    args = ap.parse_args()

    # 默认输出目录 = analysis.json 所在目录（固定约定，便于对话层调出交付）
    base = os.path.dirname(os.path.abspath(args.analysis))
    out = args.out or os.path.join(base, "polish_plan.json")
    emit_rules = args.emit_rules or (os.path.join(base, "refine_rules.json")
                                     if ("unify" in (args.intent or "") or "beautify" in (args.intent or "")) else None)
    render_md = args.render_md
    if render_md is None:
        render_md = os.path.join(base, "polish_plan.md")

    an = json.load(open(args.analysis, encoding="utf-8"))
    plan, primary, intent = build_plan(an, args)

    with open(out, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    msg = "wrote %s | primary=%s (from %s) scheme=%s pages=%d" % (
        out, primary, plan["primary_color"]["source"], plan["recommended_scheme"],
        len(plan["per_page_actions"]))
    print(msg)

    if emit_rules and ("unify" in intent or "beautify" in intent):
        rules = emit_refine_rules(an, primary, plan, emit_rules)
        print("wrote %s | fill=%d font=%d" % (emit_rules, len(rules.get("fill", [])), len(rules.get("font", []))))

    if render_md and str(render_md).lower() != "no":
        md = render_plan_md(plan, an)
        with open(render_md, "w", encoding="utf-8") as f:
            f.write(md)
        print("wrote %s" % render_md)


if __name__ == "__main__":
    main()
