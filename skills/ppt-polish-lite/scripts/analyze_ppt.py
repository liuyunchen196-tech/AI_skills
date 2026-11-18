#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase A — 现状分析：读目标 PPT 的母版 / 主题 / 逐页样式，输出 analysis.json。

做的事：
  1. 读 slide master + theme（clrScheme / accent1..6）拿到 deck「本来的」intended 主色。
  2. 全 deck 扫色：聚合所有实色填充 / 字体色，排除中性色后取 dominant 主色候选。
  3. 逐页挖：布局名、占位符 vs 自由形状、颜色、字体、字號、字符量。
  4. 判每页 master-driven（用母版）还是 bespoke（用户随手写、不靠母版）。
  5. 算 master_usage_rate（用母版页面占比），用于决定「整 deck 统一」还是「逐页挖」。

用法:
    python analyze_ppt.py <pptx路径> [--out analysis.json]

输出 analysis.json 结构见 main() 末尾注释。
"""
import sys, os, io, json
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Emu


# ---------------------------------------------------------------- 颜色工具
NEUTRAL = None  # sentinel

def norm_hex(v):
    """'8B5CF6' / '#8B5CF6' / '8b5cf6' -> '#8B5CF6'；非法返回 None。"""
    if not v:
        return None
    s = str(v).strip().lstrip("#")
    if len(s) == 6 and all(c in "0123456789abcdefABCDEF" for c in s):
        return "#" + s.upper()
    if len(s) == 8:  # aRGB
        return "#" + s[2:].upper()
    return None


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join("%02X" % max(0, min(255, int(c))) for c in rgb)


def is_neutral(h):
    """灰 / 近白 / 近黑 视为中性，不作为主色候选。

    注意：必须用「全通道都亮」判近白（mn>=245），不能用 mx>=245——
    否则纯黄 #FFFF00 / 纯青 #00FFFF / 纯品红等会被误判为中性色而漏掉。
    """
    if not h:
        return True
    r, g, b = hex_to_rgb(h)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn < 24:           # 近灰（饱和低）
        return True
    if mn >= 245:              # 近白（三通道都亮）
        return True
    if mx <= 12:               # 近黑（三通道都暗）
        return True
    return False


def rel_luminance(h):
    r, g, b = (c / 255.0 for c in hex_to_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def hsl_of(h):
    r, g, b = (c / 255.0 for c in hex_to_rgb(h))
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    l = (mx + mn) / 2
    if d == 0:
        h_ = s = 0.0
    else:
        s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r:
            h_ = (g - b) / d + (6 if g < b else 0)
        elif mx == g:
            h_ = (b - r) / d + 2
        else:
            h_ = (r - g) / d + 4
        h_ /= 6
    return h_ * 360, s * 100, l * 100


def hue_name(h):
    """粗分色相，供 plan_polish 选命名方案。"""
    h, s, l = hsl_of(h)
    if s < 18 or l < 12 or l > 92:
        return "neutral"
    if h < 15 or h >= 345:
        return "red"
    if h < 45:
        return "orange"
    if h < 70:
        return "yellow"
    if h < 165:
        return "green"
    if h < 195:
        return "teal"
    if h < 255:
        return "blue"
    if h < 290:
        return "indigo"
    return "purple"


# ---------------------------------------------------------------- 提取器
THEME_RELTYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"


def extract_theme_colors(prs):
    """从 slide master 的 theme part 拿 clrScheme（dk1/lt1/dk2/lt2/accent1..6）。"""
    out = {}
    try:
        master = prs.slide_masters[0]
        theme_part = None
        for rel in master.part.rels.values():
            if rel.reltype == THEME_RELTYPE:
                theme_part = rel.target_part
                break
        if theme_part is None:
            return out
        root = theme_part.element
        clr = root.find(".//" + qn("a:clrScheme"))
        if clr is None:
            return out
        for child in clr:
            tag = child.tag.split("}")[-1]
            srgb = child.find(qn("a:srgbClr"))
            if srgb is not None:
                out[tag] = norm_hex(srgb.get("val")) or out.get(tag)
    except Exception as e:
        out["_error"] = repr(e)
    return out


def shape_fill_hex(sh):
    try:
        f = sh.fill
        if f.type is not None and int(f.type) == 1:  # solid
            return norm_hex(str(f.fore_color.rgb))
    except Exception:
        pass
    return None


def shape_line_hex(sh):
    try:
        ln = sh.line
        if ln.fill.type is not None and int(ln.fill.type) == 1:
            return norm_hex(str(ln.fill.fore_color.rgb))
    except Exception:
        pass
    return None


def iter_run_colors(sh):
    """收集一个形状内所有 run 的字体色（实色）。"""
    colors = []
    try:
        if not sh.has_text_frame:
            return colors
        for para in sh.text_frame.paragraphs:
            for run in para.runs:
                try:
                    if run.font.color and run.font.color.type is not None:
                        c = norm_hex(str(run.font.color.rgb))
                        if c:
                            colors.append(c)
                except Exception:
                    pass
    except Exception:
        pass
    return colors


def iter_run_fonts(sh):
    fonts = []
    sizes = []
    try:
        if not sh.has_text_frame:
            return fonts, sizes
        for para in sh.text_frame.paragraphs:
            for run in para.runs:
                if run.font.name:
                    fonts.append(run.font.name)
                if run.font.size:
                    sizes.append(round(run.font.size.pt, 1))
    except Exception:
        pass
    return fonts, sizes


def scan_slide(slide, idx):
    page_colors = Counter()    # 按「面积」加权，避免小块高亮盖过大色块
    page_fonts = Counter()
    page_sizes = Counter()
    char_count = 0
    ph = 0
    free = 0
    for sh in slide.shapes:
        if sh.is_placeholder:
            ph += 1
        else:
            free += 1
        try:
            area = (sh.width or 0) * (sh.height or 0)
        except Exception:
            area = 0
        # 收集本形状内出现的「非中性」颜色集合（去重后按形状面积计权）
        present = set()
        fh = shape_fill_hex(sh)
        if fh and not is_neutral(fh):
            present.add(fh)
        lh = shape_line_hex(sh)
        if lh and not is_neutral(lh):
            present.add(lh)
        for rc in iter_run_colors(sh):
            if not is_neutral(rc):
                present.add(rc)
        for c in present:
            page_colors[c] += max(area, 1)   # 纯文本无尺寸时至少计 1，避免丢失
        fonts, sizes = iter_run_fonts(sh)
        for f_ in fonts:
            page_fonts[f_] += 1
        for s_ in sizes:
            page_sizes[s_] += 1
        try:
            char_count += len(sh.text_frame.text)
        except Exception:
            pass

    master_driven = (ph >= free) and (ph > 0)
    layout_name = "?"
    try:
        layout_name = slide.slide_layout.name
    except Exception:
        pass

    return {
        "index": idx,
        "layout": layout_name,
        "master_driven": master_driven,
        "bespoke": not master_driven,
        "placeholder_shapes": ph,
        "free_shapes": free,
        "char_count": char_count,
        "colors": [c for c, _ in page_colors.most_common(6)],
        "color_area": dict(page_colors),
        "fonts": [f for f, _ in page_fonts.most_common(4)],
        "top_sizes": [s for s, _ in page_sizes.most_common(4)],
    }


def analyze(path):
    prs = Presentation(path)
    theme_colors = extract_theme_colors(prs)

    pages = []
    global_color_area = Counter()   # 面积加权
    global_fonts = Counter()
    master_pages = 0

    for i, slide in enumerate(prs.slides):
        pg = scan_slide(slide, i)
        ca = Counter(pg.pop("color_area", {}))
        pages.append(pg)
        master_pages += 1 if pg["master_driven"] else 0
        global_color_area += ca
        for f in pg["fonts"]:
            global_fonts[f] += 1

    slide_count = len(pages)
    master_usage_rate = round(master_pages / slide_count, 3) if slide_count else 0.0

    # dominant：全 deck 面积最大的非中性强色（面积加权，避免小块高亮盖过大色块）
    dominant = global_color_area.most_common(1)
    dominant_hex = dominant[0][0] if dominant else None
    dominant_count = dominant[0][1] if dominant else 0

    # theme accent1 作为 intended 主色候选
    theme_accent1 = theme_colors.get("accent1")

    # 一致性问题（粗判）：出现 ≥3 种彼此差异大的主色候选
    distinct_strong = [c for c in global_color_area if not is_neutral(c)]
    issues = []
    if len(distinct_strong) >= 4:
        issues.append("主色不统一：deck 内出现 %d 种差异较大的彩色，建议收敛到 1 个主色"
                      % len(distinct_strong))
    if master_usage_rate < 0.5:
        issues.append("多数页面未使用母版（master_usage_rate=%.2f），为随手写页面，"
                      "需逐页挖色/字而非依赖母版统一" % master_usage_rate)
    if len(global_fonts) >= 4:
        issues.append("字体不统一：出现 %d 种字体，建议收敛到 1 套" % len(global_fonts))

    return {
        "source": os.path.abspath(path),
        "slide_count": slide_count,
        "theme_colors": theme_colors,
        "theme_accent1": theme_accent1,
        "dominant_color": {"hex": dominant_hex, "count": dominant_count},
        "color_distribution": {k: int(v) for k, v in global_color_area.most_common(20)},
        "font_distribution": dict(global_fonts.most_common(10)),
        "master_usage_rate": master_usage_rate,
        "pages": pages,
        "overall_issues": issues,
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    out = None
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    else:
        # 默认输出到 <源目录>/<文件名(去扩展)>_ppt-polish/analysis.json（固定目录，便于对话层调出交付）
        stem = os.path.splitext(os.path.basename(path))[0]
        d = os.path.join(os.path.dirname(os.path.abspath(path)), stem + "_ppt-polish")
        os.makedirs(d, exist_ok=True)
        out = os.path.join(d, "analysis.json")
    data = analyze(path)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote", out, "| slides=%d master_usage_rate=%.2f dominant=%s"
          % (data["slide_count"], data["master_usage_rate"], data["dominant_color"]["hex"]))


if __name__ == "__main__":
    main()
