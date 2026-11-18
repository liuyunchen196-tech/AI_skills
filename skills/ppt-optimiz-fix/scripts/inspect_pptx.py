# -*- coding: utf-8 -*-
"""诊断 + 细节审计 PPTX（结构化引擎）

用法:
    python inspect_pptx.py <file.pptx> [--json <out.json>]

核心 API:
    analyze(path) -> dict    # 全部检测结果，结构化，供 report_pptx.py 消费
    print_report(result)      # 人类可读 stdout（保留旧行为）

输出两大块:
  A. 结构诊断  —— 页数 / 页码 / PART 标签 / 标题重复 / 图表 / sldNum 占位符
  B. 细节审计  —— 字体统一性 / 字阶 / 越界 / 配色数 / 字号阶梯 / 字体规划角色 /
                  金字塔 Action-Title 占比 / 图文比 / 去AI味扫描
所有判定均基于 XML 字段，不靠肉眼。
"""
import json
import re
import sys
from collections import Counter

from pptx import Presentation
from pptx.oxml.ns import qn
from colorsys import rgb_to_hsv
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.dml import MSO_FILL

EMU = 914400.0


def _add_hue(hue_buckets, rgb_hex):
    try:
        r = int(rgb_hex[0:2], 16) / 255.0
        g = int(rgb_hex[2:4], 16) / 255.0
        b = int(rgb_hex[4:6], 16) / 255.0
        h, s, _ = rgb_to_hsv(r, g, b)
        if s >= 0.18:                       # 低饱和视为中性，不计主色
            hue_buckets.add(int(h * 360 // 30))   # 30°一桶
    except Exception:
        pass


def analyze(path, aud_terms_path=None):
    """返回结构化诊断结果（dict）。aud_terms_path 可选，指定外部术语表 JSON。"""
    try:
        prs = Presentation(path)
    except Exception:
        raise ValueError(
            "无法读取该文件：可能不是有效的 .pptx、已损坏，或正被其他程序占用（%s）" % path)
    SW = prs.slide_width / EMU
    SH = prs.slide_height / EMU

    result = {
        "meta": {
            "path": path,
            "name": _base(path),
            "total_slides": len(prs.slides),
            "size_in": [round(SW, 2), round(SH, 2)],
            "sldnum_count": 0,
        },
        "structure": {"slides": [], "duplicate_titles": {}, "charts": 0},
        "detail": {
            "fonts": {}, "font_families": 0, "font_unity_ok": True,
            "cover_title_size": 0.0, "content_min_title_size": 0.0,
            "title_size_ok": True, "smallest_run": 0.0,
            "oob": [], "oob_count": 0, "hue_families": 0, "color_ok": True,
            "size_ladder": {}, "off_band": [],
        },
        "font_plan": {"role_map": {}, "conformance_off": []},
        "pyramid": {"content_pages": 0, "action_titles": 0, "ratio": 0.0,
                    "level": "", "topic_titles": [], "global_conclusion": None},
        "image_text": {"bad_pages": [], "no_image_pages": 0, "total_pages": len(prs.slides)},
        "ai_tell": {"transitions": [], "buzz": [], "abstract": [], "parallel": [],
                    "template": {}, "ai_score": 0, "level": ""},
    }

    # ---- 结构诊断 ----
    n_sldnum = 0
    for sl in prs.slides:
        for ph in sl.element.findall(".//" + qn("p:ph")):
            if ph.get("type") == "sldNum":
                n_sldnum += 1
    result["meta"]["sldnum_count"] = n_sldnum

    titles = []
    for i, sl in enumerate(prs.slides, 1):
        nums, parts, title = [], [], None
        for sh in sl.shapes:
            if not sh.has_text_frame:
                continue
            t = sh.text_frame.text.strip()
            if not t:
                continue
            if re.match(r"^PART\s*\d", t, re.I):
                parts.append(t[:40])
            if re.fullmatch(r"\d{1,3}", t) and sh.left is not None and sh.top is not None:
                nums.append((round(sh.left / EMU, 2), round(sh.top / EMU, 2), t))
            if title is None and not re.fullmatch(r"\d{1,3}", t) and not re.match(r"^PART\s*\d", t, re.I):
                title = t[:60]
        titles.append(title)
        footer = [n for n in nums if 10.4 <= n[0] <= 12.6 and 6.7 <= n[1] <= 7.35]
        fn = footer[0][2] if footer else None
        mismatch = fn is not None and int(fn) != i
        entry = {
            "idx": i, "title": title, "footer": fn, "footer_mismatch": mismatch,
            "part": parts if parts else None,
            "other_nums": nums if len(nums) > len(footer) else [],
            "is_content": i > 1,
        }
        result["structure"]["slides"].append(entry)
    result["structure"]["duplicate_titles"] = {
        k: v for k, v in Counter([t for t in titles if t]).items() if v > 1}
    result["structure"]["charts"] = sum(
        1 for sl in prs.slides for sh in sl.shapes if sh.has_chart)

    # ---- 细节审计 ----
    fonts = Counter()
    size_ladder = Counter()
    hue_buckets = set()
    oob = []
    slide_max = {}
    slide_title = {}
    global_min = 999
    for i, sl in enumerate(prs.slides, 1):
        mx = 0
        sl_title_txt = ""
        for sh in sl.shapes:
            # 越界检测
            if sh.left is not None and sh.width is not None:
                L, T = sh.left / EMU, sh.top / EMU
                R, B = L + sh.width / EMU, T + sh.height / EMU
                if L < -0.05 or T < -0.05 or R > SW + 0.05 or B > SH + 0.05:
                    oob.append((i, round(L, 2), round(T, 2), round(R, 2), round(B, 2)))
            # 形状填充色（仅实色；渐变计为设计语言；仅记有彩色相）
            try:
                if sh.fill.type == MSO_FILL.SOLID and sh.fill.fore_color.type is not None:
                    _add_hue(hue_buckets, str(sh.fill.fore_color.rgb))
            except Exception:
                pass
            if not sh.has_text_frame:
                continue
            for para in sh.text_frame.paragraphs:
                for r in para.runs:
                    if r.font.name:
                        fonts[r.font.name] += 1
                    if r.font.size:
                        sz = round(r.font.size.pt, 1)
                        size_ladder[int(round(sz))] += 1
                        global_min = min(global_min, sz)
                        if sz > mx:
                            mx = sz
                            sl_title_txt = (r.text or para.text or "").strip()[:60]
                    try:
                        if r.font.color and r.font.color.type is not None:
                            _add_hue(hue_buckets, str(r.font.color.rgb))
                    except Exception:
                        pass
        slide_max[i] = mx
        slide_title[i] = sl_title_txt

    d = result["detail"]
    d["fonts"] = dict(fonts)
    d["font_families"] = fam = len(fonts)
    d["font_unity_ok"] = fam <= 2
    d["cover_title_size"] = cover = slide_max.get(1, 0)
    d["content_min_title_size"] = content_min = min(
        [v for k, v in slide_max.items() if k > 1], default=0)
    bad_title = [k for k, v in slide_max.items() if (k == 1 and v < 36) or (k > 1 and v < 28)]
    d["title_size_ok"] = not bad_title
    d["smallest_run"] = global_min if global_min < 999 else 0
    d["oob"] = oob
    d["oob_count"] = len(oob)
    n_hue = len(hue_buckets)
    d["hue_families"] = n_hue
    d["color_ok"] = n_hue <= 4
    d["size_ladder"] = dict(sorted(size_ladder.items()))
    d["off_band"] = [s for s in size_ladder if s < 10 or s > 60]

    # ---- 字体规划 conformance（FONT PLAN） ----
    try:
        import os as _os
        from fontplan import load_plan, classify_all
        _dft = _os.path.join(_os.path.dirname(__file__), "..", "references", "font-plan.default.json")
        if _os.path.exists(_dft):
            _rules = load_plan(_dft)
            _cnt = classify_all(prs, _rules, mutate=False)
            result["font_plan"]["role_map"] = dict(_cnt)
        else:
            result["font_plan"]["role_map"] = {}
    except Exception as e:
        result["font_plan"]["role_map"] = {"_error": str(e)}

    # ---- 金字塔 / Action-Title 体检 ----
    ACTION_VERBS = ("是", "等于", "为", "在于", "让", "用", "能", "成为", "提升", "降低",
                    "解决", "表明", "证明", "带来", "决定", "帮", "替", "靠", "从", "把",
                    "给", "做", "打", "省", "赢", "破", "需", "要", "该", "应",
                    "出", "看", "懂", "写", "讲", "说", "学", "会", "翻", "选", "查", "找",
                    "建", "搭", "管", "控", "优", "增", "减", "赚", "收", "获", "将", "提",
                    "解", "表", "证", "带", "决", "成", "收获")
    TOPIC_LABELS = ("概述", "简介", "背景", "引言", "目录", "致谢", "附录", "总结", "回顾",
                    "案例分析", "案例", "介绍", "说明", "讲解", "展望", "思考", "讨论", "参考")
    content_slides = list(range(2, len(prs.slides) + 1))
    action_ok, topic_titles = [], []
    for i in content_slides:
        t = (slide_title.get(i, "") or "").strip()
        if not t:
            continue
        has_verb = any(v in t for v in ACTION_VERBS)
        has_end = t.endswith(("。", "！", "？", "."))
        is_action = has_verb or has_end
        if is_action:
            action_ok.append(i)
        else:
            topic_titles.append((i, t))
    total_c = len(content_slides)
    ratio = len(action_ok) / total_c * 100 if total_c else 0
    lvl = "优(>=80%)" if ratio >= 80 else ("需修(60-80%)" if ratio >= 60 else "偏说明文(<60%)，建议重构")
    pyr = result["pyramid"]
    pyr["content_pages"] = total_c
    pyr["action_titles"] = len(action_ok)
    pyr["ratio"] = round(ratio, 0)
    pyr["level"] = lvl
    pyr["topic_titles"] = topic_titles
    cover_sub = (slide_title.get(1, "") or "").strip()
    pyr["global_conclusion"] = cover_sub if cover_sub else None

    # ---- 图文比 ≤40% 体检 ----
    bad_img, no_img = [], 0
    total_area = SW * SH
    for i, sl in enumerate(prs.slides, 1):
        img_area = 0.0
        has_pic = False
        for sh in sl.shapes:
            try:
                is_pic = (sh.shape_type == MSO_SHAPE_TYPE.PICTURE)
            except Exception:
                is_pic = False
            if is_pic:
                has_pic = True
                if sh.left is not None and sh.width is not None:
                    img_area += (sh.width / EMU) * (sh.height / EMU)
        ratio_img = img_area / total_area * 100 if total_area else 0
        if ratio_img > 40:
            bad_img.append((i, round(ratio_img, 1)))
        if not has_pic:
            no_img += 1
    it = result["image_text"]
    it["bad_pages"] = bad_img
    it["no_image_pages"] = no_img

    # ---- AI 味体检（去AI化前置检测） ----
    try:
        from ai_tells import scan as ai_scan
        r = ai_scan(prs)
        ai = result["ai_tell"]
        ai["transitions"] = r["transitions"]
        ai["buzz"] = r["buzz"]
        ai["abstract"] = r["abstract"]
        ai["parallel"] = r["parallel"]
        ai["template"] = r["template"]
        # 综合判定
        ai_score = (len(r["transitions"]) + len(r["buzz"]) + len(r["abstract"])
                    + len(r["parallel"]) + (10 if r["template"]["homogeneous"] else 0))
        ai["ai_score"] = ai_score
        ai["level"] = "重" if ai_score >= 15 else ("中" if ai_score >= 6 else "轻")
    except Exception as e:
        result["ai_tell"]["_error"] = str(e)

    # ---- 受众适配 / 说服力 自动信号（P1，减少人工复核负担） ----
    try:
        _aud_terms = _load_aud_terms(aud_terms_path)
        result["aud"] = _detect_audience_persuasion(prs, _aud_terms)
    except Exception as e:
        result["aud"] = {"_error": str(e)}

    return result


# --------------------------------------------------------------------------- #
# 受众适配 / 说服力 自动信号（P1）
# 用可量化关键词库替代原「需人工复核」弱信号：
#   - ROI 量化页检测：投资回报/回收期/收益率/NPV/IRR 等收益量化词
#   - CTA 责任页检测：责任人/Owner/落地 + 时间表/截止 等收口用语库
#   - 管理者语言密度：价值/成本/风险 等业务语言是否充分
# --------------------------------------------------------------------------- #
ROI_TERMS = ("ROI", "投资回报", "回收期", "回本", "收益率", "年化收益", "投入产出",
             "成本节约", "成本节省", "成本下降", "降本", "增效", "回报周期",
             "payback", "Payback", "NPV", "IRR", "投入产出比", "盈亏平衡", "回收年限")
CTA_TITLE_HINT = ("下一步", "行动", "Q&A", "q&a", "计划", "落地", "安排", "分工", "时间表",
                  "责任", "跟进", "执行")
OWNER_KEY_SET = {"责任人", "负责人", "Owner", "owner", "落地", "谁来做", "分工"}
TIMELINE_SET = {"时间表", "时间节点", "里程碑", "截止", "排期", "交付时间",
                "Deadline", "deadline", "日期"}
MANAGER_TERMS = ("价值", "成本", "风险", "收益", "效率", "投入", "回报", "ROI", "降本",
                 "增效", "回收", "亏损", "利润", "预算", "产出", "产能")

# 内置默认术语表（与源码常量一致）；外部 JSON 可覆盖任意列表
_DEFAULT_AUD_TERMS = {
    "roi": ROI_TERMS,
    "cta_title": CTA_TITLE_HINT,
    "owner": OWNER_KEY_SET,
    "timeline": TIMELINE_SET,
    "manager": MANAGER_TERMS,
}


def _load_aud_terms(path=None):
    """加载外部术语表 JSON；缺失/失败回退内置默认。

    适配特定行业：复制 references/aud-terms.default.json，修改对应列表后
    通过 inspect_pptx.analyze(aud_terms_path=...) 或 run_all.py --aud-terms 传入。
    """
    import os, json
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            return {
                "roi": tuple(d.get("roi_terms", ROI_TERMS)),
                "cta_title": tuple(d.get("cta_title_hint", CTA_TITLE_HINT)),
                "owner": set(d.get("owner_key_set", OWNER_KEY_SET)),
                "timeline": set(d.get("timeline_set", TIMELINE_SET)),
                "manager": tuple(d.get("manager_terms", MANAGER_TERMS)),
            }
        except Exception:
            pass
    return dict(_DEFAULT_AUD_TERMS)


def _detect_audience_persuasion(prs, terms=None):
    """自动识别 ROI 量化页、CTA 行动收口页、管理者语言密度。terms 可外部注入。"""
    if terms is None:
        terms = _DEFAULT_AUD_TERMS
    roi_terms = terms["roi"]
    cta_title_hint = terms["cta_title"]
    owner_key_set = terms["owner"]
    timeline_set = terms["timeline"]
    manager_terms = terms["manager"]
    roi_hit, roi_slide = None, None
    cta_slide = None
    owner_terms_found = set()
    manager_count = 0
    n_slides = len(prs.slides)

    for i, sl in enumerate(prs.slides, 1):
        title = None
        text = []
        for sh in sl.shapes:
            if not sh.has_text_frame:
                continue
            t = sh.text_frame.text
            if not t.strip():
                continue
            text.append(t)
            if title is None and not re.fullmatch(r"\d{1,3}", t.strip()) and \
                    not re.match(r"^PART\s*\d", t.strip(), re.I):
                title = t.strip()[:60]
        full = "\n".join(text)

        # ROI 量化页（首次命中即记）
        if roi_hit is None:
            for term in roi_terms:
                if term.lower() in full.lower():
                    roi_hit, roi_slide = term, i
                    break

        # CTA 行动收口页（标题命中 或 本页同时出现 责任主体 + 时间节点）
        slide_owner = {x for x in owner_key_set if x in full}
        slide_timeline = {x for x in timeline_set if x in full}
        if cta_slide is None and title and any(h in title for h in cta_title_hint):
            cta_slide = i
        elif cta_slide is None and slide_owner and slide_timeline:
            cta_slide = i
        owner_terms_found |= (slide_owner | slide_timeline)

        for term in manager_terms:
            manager_count += full.count(term)

    has_cta = cta_slide is not None
    has_owner = bool(owner_terms_found & owner_key_set)
    has_timeline = bool(owner_terms_found & timeline_set)
    # 管理者语言密度阈值：至少约每页 1 处
    manager_lang = manager_count >= max(6, n_slides)

    return {
        "roi": {
            "detected": roi_hit is not None,
            "slide": roi_slide,
            "term": roi_hit,
            "evidence": ("S%d 检出「%s」" % (roi_slide, roi_hit)) if roi_hit
                       else "全篇未检出 ROI/投资回报/回收期/收益 等量化收益关键词",
        },
        "cta": {
            "detected": has_cta,
            "slide": cta_slide,
            "has_owner": has_owner,
            "has_timeline": has_timeline,
            "owner_terms": sorted(owner_terms_found),
            "evidence": ("S%d 检出行动/责任收口页（含 %s 等用语）"
                         % (cta_slide, "、".join(sorted(owner_terms_found)[:4]))) if has_cta
                        else "未检出「责任人/落地/时间表/Owner」等收口用语，结尾缺执行抓手",
        },
        "manager_lang": manager_lang,
        "manager_count": manager_count,
    }


def _base(path):
    import os
    return os.path.splitext(os.path.basename(path))[0]


def print_report(result):
    """人类可读 stdout（保留旧行为）。"""
    m = result["meta"]
    print("TOTAL SLIDES:", m["total_slides"])
    print("SLIDE SIZE (in): %.2f x %.2f" % (m["size_in"][0], m["size_in"][1]))
    print("SLIDES WITH SLDNUM PLACEHOLDER:", m["sldnum_count"])

    for e in result["structure"]["slides"]:
        mark = "  <-- MISMATCH" if e["footer_mismatch"] else ""
        extra = ("  other_nums=%s" % e["other_nums"]) if e["other_nums"] else ""
        print("S%2d | footer=%s%s | PART=%s | %s%s"
              % (e["idx"], e["footer"], mark, e["part"] if e["part"] else "-",
                 e["title"], extra))

    dups = result["structure"]["duplicate_titles"]
    print("\nDUPLICATE TITLES:", dups or "NONE")
    print("CHARTS:", result["structure"]["charts"])

    d = result["detail"]
    print("\n--- DETAIL AUDIT (字体 / 字阶 / 越界 / 配色) ---")
    print("FONTS USED:", d["fonts"])
    if d["font_unity_ok"]:
        print("FONT UNITY: ✅ 字族数=%d (<=2，统一)" % d["font_families"])
    else:
        print("FONT UNITY: ⚠️ 字族数=%d (>2，存在混搭，建议统一)" % d["font_families"])

    print("TITLE SIZE: cover=%.0fpt, content pages min=%.0fpt"
          % (d["cover_title_size"], d["content_min_title_size"]))
    print("TITLE SIZE CHECK:", "✅ 全部 >=28pt" if d["title_size_ok"] else "⚠️ 偏小")
    print("SMALLEST RUN: %.1fpt" % d["smallest_run"])
    print("OUT-OF-BOUNDS SHAPES:", "0 ✅" if not d["oob"] else "%d ⚠️ %s" % (d["oob_count"], d["oob"][:5]))
    note = "（主色<=3，符合 60-30-10；含语义红/绿可放宽至4）" if d["color_ok"] else "⚠️ (>4 色相，配色偏杂，建议收敛)"
    print("COLOR HUE FAMILIES: %d %s" % (d["hue_families"], note))

    print("\n--- FONT PLAN (字号阶梯 conformance) ---")
    print("实际字号分布(pt: 出现次数):", d["size_ladder"])
    if d["off_band"]:
        print("⚠️ 离谱字号(应落在 10–60pt 规划带): %s" % d["off_band"])
    else:
        print("✅ 所有字号落在 10–60pt 规划带内")

    print("\n--- PYRAMID / ACTION-TITLE AUDIT (结构逻辑) ---")
    pyr = result["pyramid"]
    print("内容页: %d 页 | Action-Title(结论式): %d 页 | 占比 %.0f%%"
          % (pyr["content_pages"], pyr["action_titles"], pyr["ratio"]))
    print("金字塔判级:", pyr["level"])
    if pyr["topic_titles"]:
        print("话题式标题(建议改为结论句):")
        for i, t in pyr["topic_titles"]:
            print("   S%d: %s" % (i, t))
    print("全局结论(封面点题):", "✅ 有（%s）" % pyr["global_conclusion"] if pyr["global_conclusion"] else "⚠️ 封面无明确结论句")

    print("\n--- IMAGE-TEXT RATIO (图文比，单页图面积/总面积) ---")
    it = result["image_text"]
    if it["bad_pages"]:
        print("⚠️ 图文比 >40%% 的页(图压字，建议压缩/改图表): %s" % it["bad_pages"])
    else:
        print("✅ 无单页图文比 >40%%（图压字风险低）")
    print("纯字墙页(0 图): %d 页（可读性另判，关键页可图示化）" % it["no_image_pages"])

    print("\n--- AI-TELL SCAN (去AI味前置检测) ---")
    ai = result["ai_tell"]
    if ai.get("_error"):
        print("AI-TELL SCAN: 跳过 (%s)" % ai["_error"])
        return
    tr, bz, ab, pl = ai["transitions"], ai["buzz"], ai["abstract"], ai["parallel"]
    print("机械化过渡句: %d 处 %s" % (len(tr), tr[:6] if tr else "✅ 无"))
    print("黑话/套话词: %d 处；单页>=3 的重灾区页 S%s" % (len(bz), [s for s, _, _ in bz] if bz else "无"))
    if bz:
        top = Counter(w for _, w, _ in bz).most_common(6)
        print("  高频黑话:", dict(top))
    print("空洞抽象短语: %d 处 %s" % (len(ab), ab[:4] if ab else "✅ 无"))
    print("过度工整排比: %d 页 %s" % (len(pl), [s for s, _, _ in pl] if pl else "✅ 无"))
    tp = ai["template"]
    if tp.get("homogeneous"):
        print("界面模板感: ⚠️ %d%% 内容页版式签名一致 %s（建议注入版式变化）" % (tp["pct"], tp["mode_sig"]))
    else:
        print("界面模板感: ✅ 版式签名一致性 %d%%（<70%%，有变化）" % tp["pct"])
    print("AI 味指数(估): %d → %s" % (ai["ai_score"], ai["level"]))


def main(path, json_out=None):
    try:
        result = analyze(path)
    except ValueError as e:
        print("❌ %s" % e, file=sys.stderr)
        sys.exit(1)
    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("JSON 已写出: %s" % json_out)
    else:
        print_report(result)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python inspect_pptx.py <file.pptx> [--json <out.json>]")
        sys.exit(1)
    json_out = None
    args = sys.argv[1:]
    if "--json" in args:
        i = args.index("--json")
        json_out = args[i + 1]
        args = args[:i] + args[i + 2:]
    main(args[0], json_out)
