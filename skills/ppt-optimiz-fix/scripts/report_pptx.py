# -*- coding: utf-8 -*-
"""PPT 评估报告生成器（自包含 HTML / Markdown）

消费 inspect_pptx.analyze() 的结构化诊断，产出层次分明、推理链严谨的评估报告：
  - 概览卡（源文件 / 总分 / 判级 / 缺陷计数 / 一句话结论）
  - 五维评分卡（每维 分数 + 评分依据(证据) + 亮点 + 问题）
  - 缺陷清单（按 P0/P1/P2/观察 分组；每条含 维度 / 页码定位 / 证据 / 影响 / 建议 四段推理链）
  - 分维度详述（内容 / 排版 / 逻辑 / 视觉，逐条定位）
  - 亮点 / 行动优先级 / 对标说明 / 复评提示

分数由诊断发现「证据推导」，非手拍；人工判断维度显式标注「需人工复核」。

用法:
    python report_pptx.py <file.pptx> [--html <out.html>] [--md <out.md>] [--json <out.json>]
不传 --html/--md 时默认生成 <原名>_评估报告.html 到源文件同目录。
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspect_pptx import analyze

PLACEHOLDER_PAT = re.compile(r"请以|待填|实测填入|【姓名|【部门|【日期|【202X|示例|TOD?O|XXX", re.I)


# --------------------------------------------------------------------------- #
# 1. 缺陷抽取（证据 → 影响 → 建议，结构化）
# --------------------------------------------------------------------------- #
def build_findings(r):
    f = []

    def add(cat, sev, dim, slide, title, evidence, impact, suggestion):
        f.append({
            "cat": cat, "sev": sev, "dim": dim, "slide": slide,
            "title": title, "evidence": evidence, "impact": impact, "suggestion": suggestion,
        })

    st, dt = r["structure"], r["detail"]
    pyr, it, ai = r["pyramid"], r["image_text"], r["ai_tell"]

    # ---- P0 硬缺陷（可自动修） ----
    for e in st["slides"]:
        if e["footer_mismatch"]:
            add("排版", "P0", "逻辑", e["idx"], "页码与绝对序号错位",
                "S%d 页脚数字=%s，但绝对序号应为 %d" % (e["idx"], e["footer"], e["idx"]),
                "翻页跳号，读者对不上页码，专业感直接受损",
                "用 fix_pptx.py 自动校正（保留首 run 格式）；属纯字段错误，一次会话即可清空")
    if st["duplicate_titles"]:
        for t, c in st["duplicate_titles"].items():
            add("逻辑", "P0", "逻辑", None, "重复标题",
                "标题「%s」出现 %d 次" % (t, c),
                "疑似重复页/重复内容，信息冗余且易被抓包矛盾",
                "用 fix_pptx.py --delete-dupes 保留首个；或合并内容")
    if dt["off_band"]:
        add("排版", "P0", "视觉", None, "离谱字号",
            "出现字号 %s pt（应落在 10–60pt 规划带）" % dt["off_band"],
            "极端字号破坏字阶层级，观感失衡",
            "用 font-plan 规划统一字号阶梯，或手动归位")
    if dt["oob"]:
        for (i, L, T, R, B) in dt["oob"][:8]:
            add("排版", "P0", "视觉", i, "元素越出画布",
                "S%d 形状 bbox 越界 L=%.2f T=%.2f R=%.2f B=%.2f" % (i, L, T, R, B),
                "投影/导出时被裁切，关键信息丢失",
                "移回画布内或缩小；fix_pptx 不自动处理，需手动/脚本调整坐标")

    # ---- P1 结构缺陷（应修） ----
    for (i, t) in pyr["topic_titles"]:
        add("逻辑", "P1", "逻辑", i, "话题式标题（未结论化）",
            "S%d 标题「%s」为话题标签，非论断式结论" % (i, t),
            "只读标题读不出该页论点，金字塔叙事断裂，管理者抓不住重点",
            "改写为「谁 + 做什么 + 带来什么」的结论句，如「用 WorkBuddy 4 步产出专业初稿」")
    if not pyr["global_conclusion"]:
        add("逻辑", "P1", "逻辑", 1, "封面无全局结论",
            "封面主标题缺失一句话点题的结论句",
            "开篇未立论，读者前 30 秒不知你要讲什么",
            "补一句全局结论（如「AI 帮你办公，效率肉眼可见地提升」），置于封面")
    if not dt["color_ok"]:
        add("视觉", "P1", "视觉", None, "配色偏杂",
            "有彩色相族数=%d（>4）" % dt["hue_families"],
            "主色过多，60-30-10 失衡，画面显乱、不高级",
            "收敛至 ≤3 主色 + 1 强调色，强调色只点最关键一项")

    # ---- P2 / 观察（打磨） ----
    if it["bad_pages"]:
        for (i, ratio) in it["bad_pages"]:
            add("视觉", "P2", "视觉", i, "图文比 >40%（图压字）",
                "S%d 图片面积占幻灯片 %.1f%%（>40%%）" % (i, ratio),
                "图过大挤占文字空间，文字被压、可读性下降",
                "压缩图片至一侧、改图表或拆页，使文字为主、图为辅")
    if it["no_image_pages"] == it["total_pages"] and it["total_pages"] > 0:
        add("视觉", "P2", "视觉", None, "全篇 0 图（纯字墙）",
            "25 页幻灯片无任何图片/图表（图片页=0）" % () if False else
            "%d/%d 页为纯文字，无任何图片或图表" % (it["no_image_pages"], it["total_pages"]),
            "全程无视觉锚点，长培训/汇报易疲劳；关键概念缺图解，理解门槛高",
            "为抽象概念（如 LLM/Skill/MCP 关系）补示意图，并用图表替代大段罗列数据")
    elif it["no_image_pages"] > it["total_pages"] * 0.6:
        add("视觉", "观察", "视觉", None, "图示化偏少",
            "%d/%d 页无图" % (it["no_image_pages"], it["total_pages"]),
            "视觉节奏偏弱，关键页可读性与记忆点不足",
            "挑 2–3 个核心概念页加示意图或数据图表")
    if not dt["font_unity_ok"]:
        add("排版", "P1", "视觉", None, "字体混搭",
            "字族数=%d（>2）" % dt["font_families"],
            "多字族并排显拼装感，专业度下降",
            "用 fix_pptx.py --normalize-font \"微软雅黑\" 全篇统一")
    if dt["smallest_run"] and dt["smallest_run"] < 11:
        add("排版", "P2", "视觉", None, "存在过小正文",
            "最小字号=%.1fpt（<11pt 阅读吃力）" % dt["smallest_run"],
            "投影场景下小字不可读",
            "正文下限提到 12–14pt，页脚可保留 10–11pt")
    if not dt["title_size_ok"]:
        add("排版", "P0", "视觉", None, "标题字号不足",
            "存在内容页标题 <28pt（封面 <36pt）",
            "标题与正文字号差不足，层级拉不开",
            "内容页标题提到 30–36pt，靠字重+字号建立层级")

    # ---- 语言（AI 味） ----
    if ai.get("transitions"):
        slides = sorted({s for s, _ in ai["transitions"]})
        add("语言", "P1", "说服力", slides[0] if slides else None, "机械化过渡句",
            "检出 %d 处（如 %s），出现于 S%s" % (
                len(ai["transitions"]), ai["transitions"][0][1],
                "/".join("S%d" % s for s in slides[:6])),
            "「总而言之/值得注意的是」等套话暴露生成器审美，削弱真实感",
            "删去过渡句，用结论直接衔接；段间改用「但是/所以」等真实逻辑词")
    if ai.get("buzz"):
        red = sorted({s for s, _, _ in ai["buzz"]})
        add("语言", "P1", "内容", red[0] if red else None, "黑话/套话堆砌",
            "检出 %d 处（如 %s），重灾区 S%s" % (
                len(ai["buzz"]), ai["buzz"][0][1],
                "/".join("S%d" % s for s in red[:6])),
            "「赋能/闭环/范式」等空泛词稀释信息密度，读者抓不住实料",
            "改为口语化业务词（如「赋能业务」→「让销售少做重复活」），单页黑话≤2")
    if ai.get("abstract"):
        slides = sorted({s for s, _ in ai["abstract"]})
        add("语言", "P2", "内容", slides[0] if slides else None, "空洞抽象表述",
            "检出 %d 处（如 %s）" % (len(ai["abstract"]), ai["abstract"][0][1]),
            "「提升效率/创造价值」无主语无数字，缺乏可信度",
            "补具体主语+数字+场景（如「客服响应 8 分钟→90 秒」）")
    if ai.get("parallel"):
        slides = sorted({s for s, _, _ in ai["parallel"]})
        # 教学/清单类页面的结构化并列属正常编排 → 降级为「观察」
        add("语言", "观察", "内容", slides[0] if slides else None, "结构化并列（观察）",
            "S%s 出现整齐并列要点" % "/".join("S%d" % s for s in slides[:6]),
            "步骤/清单类页面本就需并列呈现，通常属正常教学编排，非 AI 痕迹",
            "若追求去 AI 质感，可打破绝对工整（长短交错、留最重要一条），否则保留即可")

    # 占位符检测（内容硬伤，按页去重，避免同一页多条噪声）
    ph_hits = _scan_placeholders(r)
    if ph_hits:
        by_page = {}
        for (i, token) in ph_hits:
            by_page.setdefault(i, set()).add(token)
        for i, toks in sorted(by_page.items()):
            add("内容", "P0", "内容", i, "未完成占位符",
                "S%d 检出未替换占位符：%s" % (i, "、".join(sorted(toks))),
                "占位符未替换即交付，等于把草稿发给受众，严重失专业",
                "用真实数据/实测值替换（如【部门/姓名】填具体人与部门），或删除该占位行")

    # ---- P1 受众/说服力 自动信号缺失 → 明确 P1 项（替代原"需人工复核"） ----
    aud = r.get("aud", {})
    roi = aud.get("roi", {})
    cta = aud.get("cta", {})
    if not roi.get("detected"):
        add("逻辑", "P1", "说服力", None, "缺量化 ROI/回收期页",
            roi.get("evidence", "全篇未检出 ROI/投资回报/回收期/收益 等量化收益关键词"),
            "决策层看不到投入产出与回收周期，说服力大打折扣，易被认定'只讲愿景'",
            "补 ROI/回收期页（成本/收益框架 + 区间 + 柱状图，示意值标注'以实测替换'），置于结论前")
    if not cta.get("detected"):
        add("逻辑", "P1", "受众适配", cta.get("slide") if cta.get("slide") else None,
            "结尾无明确责任人与时间表",
            cta.get("evidence", "未检出「责任人/落地/时间表/Owner」等收口用语"),
            "决策收口缺执行抓手，方案易成'看过了'，落地无主责",
            "补下一步行动页（三步 + 【姓名/部门/日期】占位，置结尾前）；明确 Owner + Deadline")

    return f


def _scan_placeholders(r):
    """跨页扫描未替换占位符。"""
    import json as _json
    try:
        from pptx import Presentation
        prs = Presentation(r["meta"]["path"])
    except Exception:
        return []
    hits = []
    for i, sl in enumerate(prs.slides, 1):
        for sh in sl.shapes:
            if not sh.has_text_frame:
                continue
            txt = sh.text_frame.text
            m = PLACEHOLDER_PAT.search(txt)
            if m:
                hits.append((i, m.group(0)))
    return hits


# --------------------------------------------------------------------------- #
# 2. 五维评分（证据推导，非手拍）
# --------------------------------------------------------------------------- #
def score_dimensions(r, findings):
    dt, pyr, it, ai, st = r["detail"], r["pyramid"], r["image_text"], r["ai_tell"], r["structure"]

    def clamp(x):
        return max(1.0, min(5.0, x))

    # 结构逻辑
    s_logic = 5.0
    ev_logic = []
    if pyr["ratio"] < 60:
        s_logic -= 1.5; ev_logic.append("Action-Title 占比 %.0f%%（<60%%，偏说明文）" % pyr["ratio"])
    elif pyr["ratio"] < 80:
        s_logic -= 0.5; ev_logic.append("Action-Title 占比 %.0f%%（60–80%%，需修）" % pyr["ratio"])
    else:
        ev_logic.append("Action-Title 占比 %.0f%%（≥80%%，结论式叙事到位）" % pyr["ratio"])
    if pyr["topic_titles"]:
        s_logic -= min(1.5, 0.15 * len(pyr["topic_titles"]))
        ev_logic.append("%d 个话题式标题未结论化（S%s）" % (
            len(pyr["topic_titles"]), "/".join(str(i) for i, _ in pyr["topic_titles"][:6])))
    if not pyr["global_conclusion"]:
        s_logic -= 0.5; ev_logic.append("封面无全局结论句")
    else:
        ev_logic.append("封面已点题（%s）" % pyr["global_conclusion"])
    if st["duplicate_titles"]:
        s_logic -= 0.5; ev_logic.append("存在重复标题")
    for e in st["slides"]:
        if e["footer_mismatch"]:
            s_logic -= 0.3; ev_logic.append("S%d 页码错位" % e["idx"]); break

    # 内容深度
    # 内容深度（证据推导，含占位符/黑话/空洞/数据可视）
    s_content = 4.0
    ev_content = []
    buzz_n = len(ai.get("buzz", []))
    abs_n = len(ai.get("abstract", []))
    if buzz_n:
        s_content -= min(1.5, 0.2 * buzz_n); ev_content.append("黑话/套话 %d 处" % buzz_n)
    if abs_n:
        s_content -= min(0.8, 0.1 * abs_n); ev_content.append("空洞抽象 %d 处" % abs_n)
    ph = _scan_placeholders(r)
    if ph:
        ph_pages = len({i for i, _ in ph})
        s_content -= min(1.5, 0.3 * ph_pages); ev_content.append("未完成占位符（S%s）" % "/".join("S%d" % i for i in sorted({i for i, _ in ph})))
    if st["charts"] == 0 and it["no_image_pages"] == it["total_pages"]:
        s_content -= 0.4; ev_content.append("无图表/图片，数据以文字罗列，可读性弱")
    else:
        ev_content.append("未见明显空洞/占位问题（需人工通读复核数据真实性）")

    # 受众适配（P1 自动信号：ROI 页 / CTA 行动页 / 管理者语言密度）
    s_aud = 4.0
    ev_aud = []
    aud = r.get("aud", {})
    roi = aud.get("roi", {})
    cta = aud.get("cta", {})
    if cta.get("detected"):
        s_aud += 0.3; ev_aud.append("自动识别行动收口页(S%d)，决策指引完整" % cta.get("slide"))
    else:
        s_aud -= 0.4; ev_aud.append("未检出责任人/落地/时间表等收口用语，结尾缺执行抓手")
    if roi.get("detected"):
        s_aud += 0.2; ev_aud.append("自动识别 ROI/收益量化页(S%d)，用业务语言谈成本收益" % roi.get("slide"))
    else:
        ev_aud.append("未检出 ROI/回收期量化页，说服力维度需补量化的投入产出")
    if aud.get("manager_lang"):
        s_aud += 0.1; ev_aud.append("管理者语言密度充分（价值/成本/风险 等）")
    ev_aud.append("注：受众密度/语气最终仍结合目标受众(决策/执行)人工复核")

    # 视觉呈现
    s_vis = 5.0
    ev_vis = []
    if not dt["font_unity_ok"]:
        s_vis -= 1.0; ev_vis.append("字体混搭（%d 字族）" % dt["font_families"])
    else:
        ev_vis.append("字体统一（%d 字族）" % dt["font_families"])
    if dt["oob_count"]:
        s_vis -= min(1.0, 0.3 * dt["oob_count"]); ev_vis.append("越界元素 %d 处" % dt["oob_count"])
    if not dt["color_ok"]:
        s_vis -= 0.4; ev_vis.append("配色偏杂（%d 色相）" % dt["hue_families"])
    else:
        ev_vis.append("配色 %d 色相（≤4，符合 60-30-10）" % dt["hue_families"])
    if it["bad_pages"]:
        s_vis -= min(0.6, 0.2 * len(it["bad_pages"])); ev_vis.append("图文比>40%% %d 页" % len(it["bad_pages"]))
    if it["no_image_pages"] == it["total_pages"] and it["total_pages"] > 0:
        s_vis -= 0.4; ev_vis.append("全篇 0 图，纯字墙，缺视觉锚点")
    if not dt["title_size_ok"]:
        s_vis -= 0.2; ev_vis.append("标题字号层级不足")

    # 说服力（P1 自动信号：ROI 量化 + 行动收口）
    s_per = 4.0
    ev_per = []
    if pyr["global_conclusion"] and cta.get("detected"):
        s_per += 0.3; ev_per.append("开篇立论 + 行动收口页，证据链闭环")
    else:
        if not pyr["global_conclusion"]:
            s_per -= 0.2; ev_per.append("封面无全局结论，立论弱")
        if not cta.get("detected"):
            s_per -= 0.4; ev_per.append("缺行动收口页，说服力打折")
    if roi.get("detected"):
        s_per += 0.4; ev_per.append("自动识别量化 ROI/回收期页(S%d)，收益可量化" % roi.get("slide"))
    else:
        s_per -= 0.3; ev_per.append("未检出量化 ROI/回收期，决策层看不到投入产出")
    if buzz_n or abs_n:
        s_per -= min(0.8, 0.15 * (buzz_n + abs_n)); ev_per.append("黑话/空洞削弱论证可信度")
    ev_per.append("注：ROI 数值真实性仍需人工确认")

    dims = {
        "结构逻辑": (clamp(s_logic), ev_logic, "Why—What—How—Next 认知链是否完整、标题是否即结论"),
        "内容深度": (clamp(s_content), ev_content, "是否有量化数据/案例/可溯源证据，无占位符与空话"),
        "受众适配": (clamp(s_aud), ev_aud, "语言与密度是否匹配目标受众决策链（已接入自动信号，人工仅兜底）"),
        "视觉呈现": (clamp(s_vis), ev_vis, "字体/配色/越界/图文比是否统一规范"),
        "说服力": (clamp(s_per), ev_per, "是否痛点→方案→收益→行动闭环（已接入自动信号，ROI 数值真实性人工兜底）"),
    }
    overall = sum(v[0] for v in dims.values()) / len(dims)
    return dims, overall


# --------------------------------------------------------------------------- #
# 3. 渲染
# --------------------------------------------------------------------------- #
SEV_LABEL = {"P0": "P0 必修复", "P1": "P1 应修复", "P2": "P2 打磨", "观察": "观察"}
SEV_ORDER = {"P0": 0, "P1": 1, "P2": 2, "观察": 3}


def _level_badge(overall):
    if overall >= 4.2:
        return "董事会级", "lvl-good"
    if overall >= 3.5:
        return "良好 · 需修校", "lvl-ok"
    return "需重构", "lvl-bad"


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_html(r, dims, overall, findings, out_path):
    m = r["meta"]
    level, lvl_cls = _level_badge(overall)
    # 缺陷计数
    cnt = {"P0": 0, "P1": 0, "P2": 0, "观察": 0}
    for f in findings:
        cnt[f["sev"]] += 1
    # 一句话结论
    top_defect = _headline(r, overall, findings)

    # P0 突出横幅（置于报告顶部，红底强提示）
    p0_list = [f for f in findings if f["sev"] == "P0"]
    if p0_list:
        p0_items = ""
        for f in p0_list:
            slide_chip = '<span class="chip">S%d</span>' % f["slide"] if f["slide"] else '<span class="chip">全篇</span>'
            p0_items += '<li>%s %s <span class="p0-ev">— %s</span></li>' % (
                slide_chip, _esc(f["title"]), _esc(f["evidence"]))
        p0_html = ('<div class="p0-alert"><div class="p0-title">⚠ 发现 %d 项 P0 必修复（硬缺陷，优先处理）</div>'
                   '<ul>%s</ul></div>') % (len(p0_list), p0_items)
    else:
        p0_html = '<div class="p0-ok">✓ 无 P0 硬缺陷，可直接进入结构打磨</div>'

    dim_cards = ""
    for name, (sc, ev, mean) in dims.items():
        ev_html = "".join("<li>%s</li>" % _esc(e) for e in ev)
        dim_cards += """
      <div class="dim">
        <div class="dim-head"><span class="dim-name">%s</span>
          <span class="dim-score">%.1f<span class="dim-sub">/5</span></span></div>
        <div class="dim-mean">%s</div>
        <ul class="dim-ev">%s</ul>
      </div>""" % (_esc(name), sc, _esc(mean), ev_html)

    # 缺陷清单（按严重度分组）
    groups = {}
    for f in sorted(findings, key=lambda x: (SEV_ORDER[x["sev"]], x["slide"] or 0)):
        groups.setdefault(f["sev"], []).append(f)
    defect_html = ""
    for sev in ["P0", "P1", "P2", "观察"]:
        if sev not in groups:
            continue
        items = ""
        for f in groups[sev]:
            slide_chip = '<span class="chip">S%d</span>' % f["slide"] if f["slide"] else '<span class="chip">全篇</span>'
            items += """
        <div class="defect%s">
          <div class="defect-head"><span class="sev sev-%s">%s</span>
            %s <span class="cat">%s</span> %s</div>
          <div class="chain">
            <div><b>证据</b>：%s</div>
            <div><b>影响</b>：%s</div>
            <div><b>建议</b>：%s</div>
          </div>
        </div>""" % (" is-p0" if sev == "P0" else "", sev, SEV_LABEL[sev],
                     slide_chip, _esc(f["cat"]), _esc(f["title"]),
                     _esc(f["evidence"]), _esc(f["impact"]), _esc(f["suggestion"]))
        defect_html += '<div class="grp"><h3 class="grp-h sev-%s">%s · %d 项</h3>%s</div>' % (
            sev, SEV_LABEL[sev], len(groups[sev]), items)

    # 分维度详述
    cat_of_dim = {"内容": "内容", "排版": "排版", "逻辑": "逻辑", "视觉": "视觉", "语言": "语言"}
    dim_sections = ""
    for sec in ["内容", "排版", "逻辑", "视觉"]:
        rel = [f for f in findings if f["cat"] == sec]
        if not rel:
            body = '<p class="ok">该维度未发现明显缺陷。</p>'
        else:
            body = "".join(
                '<div class="mini"><span class="chip">%s</span> %s — %s</div>' % (
                    ("S%d" % f["slide"] if f["slide"] else "全篇"),
                    _esc(f["title"]), _esc(f["suggestion"]))
                for f in rel)
        dim_sections += '<div class="dsec"><h4>%s维度</h4>%s</div>' % (_esc(sec), body)

    # 亮点
    strengths = _strengths(r)
    str_html = "".join("<li>%s</li>" % _esc(s) for s in strengths) if strengths else "<li>未发现显著亮点。</li>"

    # 行动优先级
    action = _action_priority(findings, r)

    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PPT 评估报告</title>
<style>
:root{--p0:#dc2626;--p1:#ea580c;--p2:#ca8a04;--obs:#2563eb;--ink:#1f2329;--mut:#6b7280;--line:#e8eaed;--bg:#fafbfc;--card:#fff;--accent:#3b5bdb;}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,"Microsoft YaHei","PingFang SC",sans-serif;background:var(--bg);color:var(--ink);line-height:1.65;font-size:14px}
.wrap{max-width:1000px;margin:0 auto;padding:24px 20px 48px}
header{background:var(--card);border:1px solid var(--line);border-top:4px solid var(--accent);border-radius:12px;padding:22px 24px;margin-bottom:18px}
.h-row{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
header h1{margin:0;font-size:20px;font-weight:800}
.src{font-size:12px;color:var(--mut)}
.meta{font-size:12.5px;color:var(--mut);margin-top:6px}
.overview{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-top:16px}
.score{font-size:42px;font-weight:800;line-height:1;color:var(--ink)}
.score span{font-size:15px;color:var(--mut);font-weight:600}
.badge{padding:4px 12px;border-radius:16px;font-weight:700;font-size:13px}
.lvl-good{background:#e7f6ec;color:#15803d}.lvl-ok{background:#fef3c7;color:#b45309}.lvl-bad{background:#fde8e8;color:#b91c1c}
.counts{display:flex;gap:8px;margin-left:auto;flex-wrap:wrap}
.counts .c{padding:5px 11px;border-radius:8px;font-size:12.5px;font-weight:700;color:#fff}
.c-P0{background:var(--p0)}.c-P1{background:var(--p1)}.c-P2{background:var(--p2)}.c-观察{background:var(--obs)}
.headline{margin-top:14px;font-size:13px;color:#374151;background:#f4f6f9;border-radius:8px;padding:9px 13px}
.p0-alert{background:#fff5f5;border:1px solid #f1c4c4;border-left:5px solid var(--p0);border-radius:10px;padding:14px 18px;margin-bottom:18px}
.p0-title{font-weight:800;color:var(--p0);font-size:15px;margin-bottom:8px}
.p0-alert ul{margin:0;padding-left:18px}
.p0-alert li{margin:4px 0;font-size:13.5px}
.p0-ev{color:var(--mut);font-size:12.5px}
.p0-ok{background:#e7f6ec;border:1px solid #bfe3cb;border-radius:10px;padding:12px 16px;margin-bottom:18px;color:#15803d;font-weight:700}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:16px}
h2{font-size:16px;margin:0 0 14px;font-weight:800}
h2 .sub{font-size:12px;color:var(--mut);font-weight:500;margin-left:6px}
.dims{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.dim{border:1px solid var(--line);border-radius:9px;padding:13px}
.dim-head{display:flex;justify-content:space-between;align-items:baseline}
.dim-name{font-weight:700}.dim-score{font-size:22px;font-weight:800;color:var(--accent)}
.dim-sub{font-size:12px;color:var(--mut);font-weight:500}
.dim-mean{font-size:12px;color:var(--mut);margin:5px 0}
.dim-ev{margin:0;padding-left:16px;font-size:12.5px;color:#374151}
.defect{border:1px solid var(--line);border-radius:9px;padding:11px 13px;margin-bottom:9px}
.defect.is-p0{border-color:#f1c4c4;background:#fffafa}
.defect-head{font-weight:700;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.sev{color:#fff;padding:2px 9px;border-radius:6px;font-size:12px;font-weight:700}
.sev-P0{background:var(--p0)}.sev-P1{background:var(--p1)}.sev-P2{background:var(--p2)}.sev-观察{background:var(--obs)}
.chip{background:#eef1f5;color:#374151;border-radius:5px;padding:1px 7px;font-size:12px;font-weight:700}
.cat{color:var(--mut);font-size:12px;font-weight:600}
.chain{margin-top:7px;font-size:12.5px;display:grid;gap:2px}
.chain b{color:var(--accent)}
.grp{margin-bottom:14px}.grp-h{font-size:14px;margin:0 0 9px;padding-bottom:4px;border-bottom:1px solid var(--line)}
.dsec{margin-bottom:12px}.dsec h4{margin:0 0 5px;font-size:13.5px}
.mini{font-size:12.5px;margin:3px 0}
.ok{color:#15803d;font-size:13px}
ul.strengths{margin:0;padding-left:18px;font-size:13.5px}
.action{font-size:13.5px;line-height:1.8}
.action b{color:var(--accent)}
footer{text-align:center;color:var(--mut);font-size:12px;margin-top:8px}
</style></head>
<body><div class="wrap">
<header>
  <div class="h-row"><h1>PPT 评估报告</h1><span class="src">%s</span></div>
  <div class="meta">%d 页 · %.2f × %.2f in · 自动页码占位符 %d · 结构化 XML 诊断（非肉眼）</div>
  <div class="overview">
    <div class="score">%.1f<span>/5</span></div>
    <span class="badge %s">%s</span>
    <div class="counts">
      <span class="c c-P0">P0 %d</span><span class="c c-P1">P1 %d</span>
      <span class="c c-P2">P2 %d</span><span class="c c-观察">观察 %d</span>
    </div>
  </div>
  <div class="headline">结论：%s</div>
</header>

%s

<section><h2>五维评分 <span class="sub">分数由诊断证据推导</span></h2>
  <div class="dims">%s</div>
</section>

<section><h2>缺陷清单 <span class="sub">按优先级，每条含 证据→影响→建议</span></h2>
  %s
</section>

<section><h2>分维度详述 <span class="sub">内容 / 排版 / 逻辑 / 视觉</span></h2>
  %s
</section>

<section><h2>亮点</h2><ul class="strengths">%s</ul></section>

<section><h2>行动优先级</h2><div class="action">%s</div></section>

<footer>由 PPT 优化修复顾问 技能自动生成 · 结构化字段核验</footer>
</div></body></html>""" % (
        _esc(m["name"]), m["total_slides"], m["size_in"][0], m["size_in"][1],
        m["sldnum_count"], overall, lvl_cls, level,
        cnt["P0"], cnt["P1"], cnt["P2"], cnt["观察"], _esc(top_defect),
        p0_html, dim_cards, defect_html, dim_sections, str_html, action)

    with open(out_path, "w", encoding="utf-8") as fp:
        fp.write(html)
    return out_path


def _headline(r, overall, findings):
    pyr, it = r["pyramid"], r["image_text"]
    parts = []
    if any(f["sev"] == "P0" for f in findings):
        p0 = [f for f in findings if f["sev"] == "P0"]
        parts.append("存在 %d 项 P0 硬缺陷（页码/重复/越界/占位符），可优先自动修清" % len(p0))
    parts.append("五维均分 %.1f（%s）" % (overall, _level_badge(overall)[0]))
    if pyr["ratio"] < 80:
        parts.append("Action-Title 占比 %.0f%%（标题未充分结论化）" % pyr["ratio"])
    if it["no_image_pages"] == it["total_pages"]:
        parts.append("全篇 0 图，建议补关键概念示意图")
    return "；".join(parts[:3])


def _strengths(r):
    dt, pyr, it, ai = r["detail"], r["pyramid"], r["image_text"], r["ai_tell"]
    s = []
    if dt["font_unity_ok"]:
        s.append("字体统一（%d 字族），无混搭" % dt["font_families"])
    if dt["oob_count"] == 0:
        s.append("无元素越界，版式干净")
    if dt["color_ok"]:
        s.append("配色 %d 色相，符合 60-30-10" % dt["hue_families"])
    if pyr["global_conclusion"]:
        s.append("封面已一句话点题（%s）" % pyr["global_conclusion"])
    if pyr["ratio"] >= 60:
        s.append("Action-Title 占比 %.0f%%，叙事基本结论先行" % pyr["ratio"])
    if ai.get("level") == "轻":
        s.append("AI 味指数 %d（轻），文案自然度较好" % ai.get("ai_score", 0))
    if not it["bad_pages"]:
        s.append("无图文比>40%% 的图压字页")
    return s


def _action_priority(findings, r):
    p0 = [f for f in findings if f["sev"] == "P0"]
    p1 = [f for f in findings if f["sev"] == "P1"]
    p2 = [f for f in findings if f["sev"] == "P2"]
    lines = []
    if p0:
        lines.append("<b>① 先清 P0（可全自动）</b>：用 fix_pptx.py 校正页码/删重/归一字体/清洗 zip；"
                     "占位符需人工替换真实数据。共 %d 项。" % len(p0))
    else:
        lines.append("<b>① P0 无硬缺陷</b>：无需紧急修复，直接进入结构打磨。")
    if p1:
        lines.append("<b>② 再修 P1（结构/语言）</b>：把话题式标题改为结论句、补封面全局结论、收敛配色、"
                     "清除黑话套话与机械过渡句。共 %d 项。" % len(p1))
    if p2:
        lines.append("<b>③ 打磨 P2（视觉细节）</b>：图压字页压缩、过小正文提号、关键页补图示。共 %d 项。" % len(p2))
    obs = [f for f in findings if f["sev"] == "观察"]
    if obs:
        lines.append("<b>④ 观察项</b>：结构化并列/图示化偏少等，按需微调，非必须。共 %d 项。" % len(obs))
    return "<br>".join(lines)


# --------------------------------------------------------------------------- #
# Markdown 渲染（对标 review-rubric.md 模板）
# --------------------------------------------------------------------------- #
def render_md(r, dims, overall, findings, out_path):
    m = r["meta"]
    level, _ = _level_badge(overall)
    cnt = {"P0": 0, "P1": 0, "P2": 0, "观察": 0}
    for f in findings:
        cnt[f["sev"]] += 1

    lines = []
    lines.append("# 《%s》专业评估报告\n" % m["name"])
    lines.append("评估对象：%s（%d 页，%.2f×%.2f in）" % (m["name"], m["total_slides"], m["size_in"][0], m["size_in"][1]))
    lines.append("评估方法：结构化 XML 诊断（inspect_pptx）+ 五维评分推导 + 复评追踪可用（§10）")
    lines.append("总体评价：五维均分 **%.1f/5**（%s）；缺陷 P0=%d / P1=%d / P2=%d / 观察=%d\n" % (
        overall, level, cnt["P0"], cnt["P1"], cnt["P2"], cnt["观察"]))

    lines.append("## 一、五维度评分与详评\n")
    for name, (sc, ev, mean) in dims.items():
        lines.append("### %s  %.1f/5" % (name, sc))
        lines.append("> %s" % mean)
        for e in ev:
            lines.append("- %s" % e)
        lines.append("")

    lines.append("## 二、硬伤速查表\n")
    lines.append("| 页码 | 维度 | 类型 | 严重度 | 证据 | 建议 |")
    lines.append("|---|---|---|---|---|---|")
    for f in sorted(findings, key=lambda x: (SEV_ORDER[x["sev"]], x["slide"] or 0)):
        sl = "S%d" % f["slide"] if f["slide"] else "全篇"
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            sl, f["cat"], f["title"], SEV_LABEL[f["sev"]], f["evidence"], f["suggestion"]))
    lines.append("")

    lines.append("## 三、改进建议（按优先级）\n")
    for sev in ["P0", "P1", "P2", "观察"]:
        grp = [f for f in findings if f["sev"] == sev]
        if not grp:
            continue
        lines.append("### %s · %d 项" % (SEV_LABEL[sev], len(grp)))
        for f in grp:
            sl = "S%d" % f["slide"] if f["slide"] else "全篇"
            lines.append("- **[%s] %s**：%s → %s" % (sl, f["title"], f["evidence"], f["suggestion"]))
        lines.append("")

    lines.append("## 四、亮点\n")
    for s in _strengths(r):
        lines.append("- %s" % s)
    lines.append("")

    md = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as fp:
        fp.write(md)
    return out_path


def main(path, html_out=None, md_out=None, json_out=None, aud_terms=None):
    r = analyze(path, aud_terms_path=aud_terms)
    findings = build_findings(r)
    dims, overall = score_dimensions(r, findings)
    if json_out:
        import json
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump({"meta": r["meta"], "overall": round(overall, 2),
                       "dims": {k: v[0] for k, v in dims.items()},
                       "findings": findings}, f, ensure_ascii=False, indent=2)
        print("JSON 已写出: %s" % json_out)
    if md_out or (not html_out and not md_out and not json_out):
        if not md_out:
            md_out = os.path.join(os.path.dirname(os.path.abspath(path)),
                                  "%s_评估报告.md" % r["meta"]["name"])
        print("MD 已写出:", render_md(r, dims, overall, findings, md_out))
    if html_out or (not md_out and not json_out):
        if not html_out:
            html_out = os.path.join(os.path.dirname(os.path.abspath(path)),
                                   "%s_评估报告.html" % r["meta"]["name"])
        print("HTML 已写出:", render_html(r, dims, overall, findings, html_out))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python report_pptx.py <file.pptx> [--html <out.html>] [--md <out.md>] [--json <out.json>]")
        sys.exit(1)
    p = sys.argv[1]
    html = md = js = None
    args = sys.argv[2:]
    if "--html" in args:
        html = args[args.index("--html") + 1]
    if "--md" in args:
        md = args[args.index("--md") + 1]
    if "--json" in args:
        js = args[args.index("--json") + 1]
    aud = None
    if "--aud-terms" in args:
        aud = args[args.index("--aud-terms") + 1]
    try:
        main(p, html, md, js, aud)
    except ValueError as e:
        print("❌ %s" % e, file=sys.stderr)
        sys.exit(1)
