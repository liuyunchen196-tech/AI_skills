# -*- coding: utf-8 -*-
"""去AI味 共享词库 + 扫描器

被 inspect_pptx.py 与 deai_pptx.py 复用。纯函数，无副作用。
返回结构化的"AI 味"发现，供体检与修正要点报告使用。
"""
import re
from collections import Counter

EMU = 914400.0

# ---- P0 机械化过渡句（出现即疑似 AI 味） ----
MECH_TRANSITIONS = [
    "总而言之", "综上所述", "总的来说", "总体来看", "值得注意的是", "毋庸置疑",
    "不可否认", "显而易见", "不难发现", "诚然", "众所周知", "在当今", "在当下",
    "随着…的发展", "随着…的不断进步", "随着人工智能的发展", "在这个充满",
    "新时代", "大背景下", "可以说", "我们需要", "我们要", "由此可见",
    "一方面", "另一方面", "不难发现",
]

# ---- P0 黑话/套话（单页>=3 即红；仅收录"空洞套话"类强信号，剔除 落地/打造/闭环 等正常业务词） ----
BUZZWORDS = [
    "赋能", "一站式", "抓手", "颗粒度", "底层逻辑", "范式", "组合拳", "方法论",
    "爽点", "引爆", "颠覆", "重塑", "生态", "飞轮", "第二曲线", "增长黑客",
    "全链路", "多维度", "全方位", "矩阵式", "体感", "心智", "势能", "认知升级",
    "数智化", "新篇章", "新范式", "新引擎", "新机遇", "新风口", "价值赋能",
    "生态闭环", "降维打击", "第一性原理", "指数级", "非线性", "长期主义",
]

# ---- P1 空洞抽象（无具体主语/数字/场景） ----
ABSTRACT_PATTERNS = [
    r"提升.{0,4}效率", r"优化.{0,4}体验", r"创造.{0,4}价值", r"实现.{0,4}价值",
    r"提高.{0,4}质量", r"增强.{0,4}能力", r"显著.{0,2}提升", r"大幅.{0,2}提升",
    r"有效.{0,2}提升", r"进一步.{0,2}优化",
]


def _is_footer_page_number(sh):
    """判断是否为页脚页码（右下角 bbox 内纯数字文本框），与 fix_pptx 口径一致。

    页脚页码不属于正文，收集文本时跳过，避免污染去AI味报告的"原句"上下文。
    """
    if not sh.has_text_frame:
        return False
    t = sh.text_frame.text.strip()
    if not re.fullmatch(r"\d{1,3}", t):
        return False
    if sh.left is None or sh.top is None:
        return False
    L = sh.left / EMU
    T = sh.top / EMU
    return 10.4 <= L <= 12.6 and 6.7 <= T <= 7.35


def get_slide_texts(prs):
    """返回每页文本：[(slide_idx, [paragraph_texts...]), ...]（已剔除页脚页码）"""
    out = []
    for i, sl in enumerate(prs.slides, 1):
        paras = []
        for sh in sl.shapes:
            if not sh.has_text_frame:
                continue
            if _is_footer_page_number(sh):
                continue
            for p in sh.text_frame.paragraphs:
                t = "".join(r.text for r in p.runs).strip()
                if t:
                    paras.append(t)
        out.append((i, paras))
    return out


def detect_transitions(text):
    return [w for w in MECH_TRANSITIONS if w in text]


def detect_buzzwords(text):
    c = Counter()
    for w in BUZZWORDS:
        n = text.count(w)
        if n:
            c[w] = n
    return c


def detect_abstract(text):
    found = []
    for pat in ABSTRACT_PATTERNS:
        for m in re.finditer(pat, text):
            found.append(m.group(0))
    return found


def detect_parallelism(paras):
    """检测过度工整排比（强信号，避免误报）：
    >=4 条实质性要点，且 同首2字(>=4) 与 等长(长度差<=2) 同时满足（AND），
    仅捕捉"生成器凑齐"式机械排比，普通列表不触发。
    先剔除页眉/页脚装饰文本（章节标签、页码徽标、纯符号、标题行），避免误报。
    重要：编号步骤清单（1./①/(1) 等有序步骤，多见于教学/操作类 PPT）属正常编排，
    一律从候选集中剔除，避免把"4 步出专业初稿"这类有序步骤误判为 AI 痕迹。"""
    import re as _re

    ORDERED = _re.compile(r"^\s*([①②③④⑤⑥⑦⑧⑨⑩\d]+[\.、)）]?\s*)")

    def is_chrome(p):
        if _re.fullmatch(r"\d{1,3}\s*/\s*\d{1,3}", p):
            return True                      # 页码徽标 10 / 25
        if _re.fullmatch(r"\d{2}\s+\S+", p):
            return True                      # 章节标签 02 核心概念
        if _re.fullmatch(r"[\d\s/·•\-—:：.]+", p):
            return True                      # 纯数字/符号行
        return False

    content = [p for p in paras if not is_chrome(p)]
    if content:
        title = max(content, key=len)        # 跳过（疑似）标题行
        content = [p for p in content if p != title]
    raw = [p for p in content
           if 6 <= len(p) <= 30
           and not _re.fullmatch(r"[\d\s\.、，。：:·\-—]+", p)]
    # 剔除编号步骤清单（有序步骤），仅对"无编号的自由并列要点"判定机械排比
    bullets = [p for p in raw if not ORDERED.match(p)]
    if len(bullets) < 4:
        return []

    def opener(s):
        m = _re.search(r"[\u4e00-\u9fa5a-zA-Z0-9]", s)
        if not m:
            return ""
        st = m.start()
        return s[st:st + 2]

    lens = [len(b) for b in bullets]
    mn = min(lens)
    tight = [b for b in bullets if mn <= len(b) <= mn + 2]
    openers = Counter(opener(b) for b in bullets if opener(b))
    same = [k for k, v in openers.items() if v >= 4]
    flag = []
    if len(tight) >= 4:
        flag.append(("等长", tight))
    if same:
        matched = [b for b in bullets if opener(b) in same]
        if len(matched) >= 4:
            flag.append(("同首", matched))
    return flag


def detect_template_homogeneity(prs):
    """计算每页版式签名（矩形数, 文本块数, 椭圆数），>70% 一致则模板感重"""
    sigs = {}
    for i, sl in enumerate(prs.slides, 1):
        rect = txt = oval = 0
        for sh in sl.shapes:
            st = str(sh.shape_type)
            if "RECTANGLE" in st or "AUTO_SHAPE" in st:
                rect += 1
            elif "OVAL" in st or "OVAL" in st.upper():
                oval += 1
            if sh.has_text_frame and sh.text_frame.text.strip():
                txt += 1
        sigs[i] = (rect, txt, oval)
    from collections import Counter as C
    cnt = C(sigs.values())
    mode, freq = cnt.most_common(1)[0]
    total = len(sigs)
    pct = round(freq / total * 100)
    homo_slides = [k for k, v in sigs.items() if v == mode]
    return {"mode_sig": mode, "freq": freq, "total": total, "pct": pct,
            "slides": homo_slides, "homogeneous": pct >= 70}


def scan(prs):
    """主扫描：返回结构化发现字典"""
    texts = get_slide_texts(prs)
    full = {i: "\n".join(ps) for i, ps in texts}

    transitions = []   # (slide, phrase)
    buzz = []          # (slide, word, count)
    abstract = []      # (slide, phrase)
    parallel = []      # (slide, kind, items)

    for i, ps in texts:
        joined = "\n".join(ps)
        for w in detect_transitions(joined):
            transitions.append((i, w))
        bc = detect_buzzwords(joined)
        for w, n in bc.items():
            buzz.append((i, w, n))
        for a in detect_abstract(joined):
            abstract.append((i, a))
        for kind, items in detect_parallelism(ps):
            parallel.append((i, kind, items))

    template = detect_template_homogeneity(prs)

    # 聚合统计
    buzz_by_slide = {}
    for i, w, n in buzz:
        buzz_by_slide.setdefault(i, Counter())[w] += n
    red_slides = [i for i, c in buzz_by_slide.items() if sum(c.values()) >= 3]

    return {
        "texts": texts,
        "full": full,
        "transitions": transitions,
        "buzz": buzz,
        "buzz_by_slide": buzz_by_slide,
        "red_slides": red_slides,
        "abstract": abstract,
        "parallel": parallel,
        "template": template,
    }
