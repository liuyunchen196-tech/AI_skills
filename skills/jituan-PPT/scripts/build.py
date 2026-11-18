# -*- coding: utf-8 -*-
"""
jituan-PPT 核心构建器
将结构化内容 JSON 渲染为「集团模板」风格的正式 PPT（16:9, 13.33x7.5in）。

用法:
    python build.py <content.json> [--template 模板.pptx] [--out 输出.pptx] [--cover 封面中文截图] [--right 右侧图]

内容 JSON 结构见 references/content-schema.md。

排版常量全部对齐 D:/AIproject/模板.pptx 实测值（单位: EMU/英寸）。
"""
import sys, os, io, json, argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
import copy

# ---------------------------------------------------------------- 常量
SLIDE_W = 13.3333
SLIDE_H = 7.5

# 品牌色（主题 accent1 = #0070BF）
BRAND = RGBColor(0x00, 0x70, 0xBF)        # 深蓝
BRAND_LIGHT = RGBColor(0x8C, 0xC1, 0x21)  # 亮绿（accent2，目录编号/强调）
TEXT_MAIN = RGBColor(0x26, 0x26, 0x26)
TEXT_GRAY = RGBColor(0x60, 0x60, 0x60)
TITLE_RED = RGBColor(0xFF, 0x00, 0x00)    # 模板目录当前章用红色

FONT_CN = "微软雅黑"

# 字号规范（v1.4）: 正文统一 16 号、表格文字统一 14 号，字体全部微软雅黑
BODY_SIZE = 16
TABLE_SIZE = 14

# 版式页标题位置（模板实测）
PAGE_TITLE_L = 0.58
PAGE_TITLE_T = 0.32
PAGE_TITLE_W = 10.61
PAGE_TITLE_H = 0.67
PAGE_TITLE_SIZE = 24

# 正文区（标题下）
BODY_TOP = 1.35
BODY_LEFT = 0.58
BODY_W = 12.17          # 页宽 - 2*0.58
BODY_BOTTOM = 7.0
NOTE_BOTTOM = 6.40      # 注释条底边：收在页脚 5G 标识（版式图 T6.42）上方

GOLDEN = 0.618


def _add_paragraph(tf, text, size, bold=False, color=TEXT_MAIN,
                   align=PP_ALIGN.LEFT, space_before=None, space_after=None,
                   line_spacing=None, font_name=FONT_CN, bullet=False):
    p = tf.paragraphs[0] if (len(tf.paragraphs) == 1 and not tf.paragraphs[0].runs) else tf.add_paragraph()
    p.alignment = align
    if space_before is not None:
        p.space_before = Pt(space_before)
    if space_after is not None:
        p.space_after = Pt(space_after)
    if line_spacing is not None:
        p.line_spacing = line_spacing
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.name = font_name
    r.font.color.rgb = color
    # 东亚字体
    rPr = r._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea)
        rPr.set("lang", "zh-CN")
        rPr.set("altLang", "en-US")
    ea.set("typeface", font_name)
    rPr.set("lang", "zh-CN")
    rPr.set("altLang", "en-US")
    cs = rPr.find(qn("a:cs"))
    if cs is None:
        cs = rPr.makeelement(qn("a:cs"), {})
        rPr.append(cs)
    cs.set("typeface", font_name)
    _hang_punct(p)
    return p


def _set_fill(shape, color=None, alpha_pct=None):
    """设置纯色填充；color=None 表示无填充"""
    if color is None:
        shape.fill.background()
        return
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    if alpha_pct is not None:
        srgb = shape.fill.fore_color._xFill.find(qn("a:srgbClr"))
        if srgb is None:
            srgb = shape.fill.fore_color._xFill.find(qn("a:schemeClr"))
        if srgb is not None:
            a = srgb.makeelement(qn("a:alpha"), {"val": str(int(alpha_pct * 1000))})
            srgb.append(a)


def _set_line(shape, color=None, width_pt=0.75, dash=None):
    if color is None:
        shape.line.fill.background()
        return
    shape.line.color.rgb = color
    shape.line.width = Pt(width_pt)
    if dash:
        ln = shape.line._get_or_add_ln()
        for d in ln.findall(qn("a:prstDash")):
            ln.remove(d)
        d = ln.makeelement(qn("a:prstDash"), {"val": dash})
        ln.append(d)


def _no_line(shape):
    shape.line.fill.background()


def _set_autofit(shp, shrink=True):
    """自动收缩文字，避免溢出"""
    try:
        tf = shp.text_frame
        tf.word_wrap = True
        if shrink:
            bodyPr = tf._txBody.find(qn("a:bodyPr"))
            if bodyPr is not None:
                for tag in ("a:normAutofit", "a:spAutoFit", "a:noAutofit"):
                    for e in bodyPr.findall(qn(tag)):
                        bodyPr.remove(e)
                na = bodyPr.makeelement(qn("a:normAutofit"), {})
                if shrink:
                    na.set("fontScale", "90000")
                bodyPr.append(na)
    except Exception:
        pass


# ---------------------------------------------------------------- 页工厂

def _hang_punct(p):
    """允许标点悬挂到文本框边界外，避免「。」等标点被挤到下一行单独成行"""
    pPr = p._p.get_or_add_pPr()
    pPr.set("hangingPunct", "1")
    return p


def _is_title_ph(ph):
    try:
        t = ph.placeholder_format.type
        return t in (1, 3, 13) or ph.placeholder_format.idx == 0
    except Exception:
        return False

class PageBuilder:
    """基于给定版式(或空白页)向幻灯片填充内容的构建器"""

    def __init__(self, slide, layout_name):
        self.slide = slide
        self.layout_name = layout_name
        self._find_or_create_title()

    def _find_or_create_title(self):
        self.title_ph = None
        # 首页/封面没有标题占位符的不用管
        for ph in self.slide.placeholders:
            if _is_title_ph(ph):
                self.title_ph = ph
                break
        if self.title_ph is not None:
            self._clear_ph(self.title_ph)

    def _clear_ph(self, ph):
        """清空占位符文字，只保留第一个段落"""
        tf = ph.text_frame
        for p in list(tf.paragraphs[1:]):
            p._p.getparent().remove(p._p)
        for p in tf.paragraphs[0].runs:
            p.text = ""
        tf.paragraphs[0].text = "" if hasattr(tf.paragraphs[0], "text") else None

    def set_title(self, text, size=PAGE_TITLE_SIZE, color=TEXT_MAIN, bold=False):
        if self.title_ph is None:
            return
        tf = self.title_ph.text_frame
        tf.word_wrap = True
        self._clear_ph(self.title_ph)
        _add_paragraph(tf, text, size, bold=bold, color=color)
        # 标题占位符定位
        self.title_ph.left = Inches(PAGE_TITLE_L)
        self.title_ph.top = Inches(PAGE_TITLE_T)
        self.title_ph.width = Inches(PAGE_TITLE_W)
        self.title_ph.height = Inches(PAGE_TITLE_H)

    def add_textbox(self, left, top, width, height, text=None, size=14, bold=False,
                    color=TEXT_MAIN, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
                    space_before=None, space_after=None, line_spacing=None,
                    font_name=FONT_CN, border=None, fill=None, wrap=True):
        tb = self.slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = tb.text_frame
        tf.word_wrap = wrap
        tf.vertical_anchor = anchor
        tf.margin_left = Pt(4)
        tf.margin_right = Pt(4)
        tf.margin_top = Pt(2)
        tf.margin_bottom = Pt(2)
        if fill is not None:
            self._set_shape_fill(tb, fill)
        if border is not None:
            tb.line.color.rgb = border
            tb.line.width = Pt(0.75)
        else:
            tb.line.fill.background()
        if text is not None:
            _add_paragraph(tf, text, size, bold=bold, color=color, align=align,
                           space_before=space_before, space_after=space_after,
                           line_spacing=line_spacing, font_name=font_name)
        return tb

    def _set_shape_fill(self, shape, color):
        shape.fill.solid()
        shape.fill.fore_color.rgb = color

    def add_rect(self, left, top, width, height, fill=BRAND, line=None, radius=False,
                 alpha_pct=None, shadow=False):
        st = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
        shp = self.slide.shapes.add_shape(st, Inches(left), Inches(top), Inches(width), Inches(height))
        if radius:
            try:
                shp.adjustments[0] = 0.12
            except Exception:
                pass
        _set_fill(shp, fill, alpha_pct)
        if line is None:
            _no_line(shp)
        else:
            _set_line(shp, line, 0.75)
        if not shadow:
            self._kill_shadow(shp)
        return shp

    def _kill_shadow(self, shp):
        spPr = shp._element.spPr
        for e in spPr.findall(qn("a:effectLst")):
            spPr.remove(e)

    def add_picture_fit(self, img_path, left, top, width=None, height=None,
                        contain=True, align_x=0.5, align_y=0.5):
        """在指定区域内等比放置图片。返回图片 shape。
        width/height 给定目标外框；contain=True 时图片完整放入，多余留白。
        """
        from PIL import Image
        with Image.open(img_path) as im:
            iw, ih = im.size
        if width is None and height is None:
            width, height = 4, 3
        if contain:
            if width is not None and height is not None:
                scale = min(width / iw, height / ih)
            else:
                scale = (width / iw) if height is None else (height / ih)
            pw, ph = iw * scale, ih * scale
        else:
            pw, ph = width, height
        # 计算放置坐标
        box_w = width if width is not None else pw
        box_h = height if height is not None else ph
        x = left + (box_w - pw) * align_x
        y = top + (box_h - ph) * align_y
        pic = self.slide.shapes.add_picture(img_path, Inches(x), Inches(y), Inches(pw), Inches(ph))
        # 加细边框，正式感
        _set_line(pic, RGBColor(0xC0, 0xC0, 0xC0), 0.75)
        return pic

    def _set_table_style(self, table, header_fill=BRAND, header_color=RGBColor(0xFF, 0xFF, 0xFF),
                         header_bold=True, body_size=TABLE_SIZE, header_size=TABLE_SIZE, body_color=TEXT_MAIN,
                         banding=True, align_map=None, col_widths=None, header_align=None):
        """统一表格样式：表头蓝底白字 + 斑马纹 + 细边框"""
        from pptx.enum.text import MSO_ANCHOR as _ANC
        for c, cell in enumerate(table.rows[0].cells):
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_fill
            cell.vertical_anchor = _ANC.MIDDLE
            for p in cell.text_frame.paragraphs:
                p.alignment = (header_align.get(c) if header_align else PP_ALIGN.CENTER)
                for r in p.runs:
                    r.font.size = Pt(header_size)
                    r.font.bold = header_bold
                    r.font.name = FONT_CN
                    r.font.color.rgb = header_color
                    rPr = r._r.get_or_add_rPr()
                    ea = rPr.makeelement(qn("a:ea"), {"typeface": FONT_CN})
                    rPr.append(ea)
                    rPr.set("lang", "zh-CN")
                    rPr.set("altLang", "en-US")
        # 新版 python-pptx 的 _RowCollection 不支持切片，用索引逐行处理
        for ri in range(1, len(table.rows)):
            row = table.rows[ri]
            for c, cell in enumerate(row.cells):
                if banding and ri % 2 == 0:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = RGBColor(0xEE, 0xF4, 0xFA)
                else:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                cell.vertical_anchor = _ANC.MIDDLE
                for p in cell.text_frame.paragraphs:
                    if align_map and c in align_map:
                        p.alignment = align_map[c]
                    for r in p.runs:
                        r.font.size = Pt(body_size)
                        r.font.bold = False
                        r.font.name = FONT_CN
                        r.font.color.rgb = body_color
                        rPr = r._r.get_or_add_rPr()
                        ea = rPr.makeelement(qn("a:ea"), {"typeface": FONT_CN})
                        rPr.append(ea)
                        rPr.set("lang", "zh-CN")
                        rPr.set("altLang", "en-US")
        # 边框：细灰线
        self._set_table_borders(table, RGBColor(0xBF, 0xBF, 0xBF), 0.5)
        if col_widths:
            for c, w in enumerate(col_widths):
                if c < len(table.columns):
                    table.columns[c].width = Inches(w)

    def _tighten_cell_margins(self, table, lr=0.07, tb=0.02):
        """收紧单元格内边距，避免行高被默认边距撑大"""
        for tc in table._tbl.iter(qn("a:tc")):
            tcPr = tc.find(qn("a:tcPr"))
            if tcPr is None:
                tcPr = tc.makeelement(qn("a:tcPr"), {})
                tc.insert(0, tcPr)
            tcPr.set("marL", str(int(lr * 914400)))
            tcPr.set("marR", str(int(lr * 914400)))
            tcPr.set("marT", str(int(tb * 914400)))
            tcPr.set("marB", str(int(tb * 914400)))

    def _set_table_borders(self, table, color, width_pt):
        from pptx.oxml.ns import qn as _qn
        tbl = table._tbl
        for tc in tbl.iter(_qn("a:tc")):
            tcPr = tc.find(_qn("a:tcPr"))
            if tcPr is None:
                tcPr = tc.makeelement(_qn("a:tcPr"), {})
                tc.insert(0, tcPr)
            for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
                for e in tcPr.findall(_qn(tag)):
                    tcPr.remove(e)
                ln = tcPr.makeelement(_qn(tag), {"w": str(int(width_pt * 12700)), "cap": "flat"})
                fill = ln.makeelement(_qn("a:solidFill"), {})
                srgb = ln.makeelement(_qn("a:srgbClr"), {"val": str(color)})
                fill.append(srgb)
                ln.append(fill)
                tcPr.append(ln)

    def add_table(self, rows, left, top, width, header=True, col_widths=None,
                  row_height=0.28, header_h=0.36, body_size=TABLE_SIZE, header_size=TABLE_SIZE,
                  align_map=None, header_align=None, first_col_bold=False,
                  banding=True):
        """rows: list[list[str]]，含表头时 header=True（第一行作为表头）"""
        data = rows
        n_rows = len(data)
        n_cols = max(len(r) for r in data)
        if header and n_rows > 1:
            tbl_rows, tbl_cols = n_rows, n_cols
        else:
            tbl_rows, tbl_cols = n_rows, n_cols
        gtbl = self.slide.shapes.add_table(tbl_rows, tbl_cols,
                                           Inches(left), Inches(top),
                                           Inches(width), Inches(0.4)).table
        # 填充数据
        for ri in range(tbl_rows):
            for ci in range(tbl_cols):
                val = data[ri][ci] if ri < len(data) and ci < len(data[ri]) else ""
                cell = gtbl.cell(ri, ci)
                cell.text_frame.clear()
                _add_paragraph(cell.text_frame, str(val), body_size, color=TEXT_MAIN)
        # 行高
        if header and tbl_rows > 1:
            gtbl.rows[0].height = Inches(header_h)
            for r in range(1, tbl_rows):
                gtbl.rows[r].height = Inches(row_height)
        self._tighten_cell_margins(gtbl)
        self._set_table_style(
            gtbl,
            col_widths=col_widths,
            body_size=body_size,
            header_size=header_size,
            align_map=align_map,
            header_align=header_align,
            banding=banding,
        )
        return gtbl

    def set_bullets(self, tf, items, size=14, color=TEXT_MAIN, gap=6, bullet_color=BRAND,
                    line_spacing=1.2, bold_prefix=False):
        """把 items 渲染成带项目符号（■/●）的要点列表。items 元素可为 str 或 {text, level}"""
        first = True
        for it in items:
            level = 0
            text = it
            bold = False
            if isinstance(it, dict):
                text = it.get("text", "")
                level = it.get("level", 0)
                bold = it.get("bold", False)
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.level = level
            p.space_after = Pt(gap)
            p.line_spacing = line_spacing
            prefix = "■" if level == 0 else "—"
            if level > 0:
                prefix = "\u3000" * (level - 1) + "·"
            r1 = p.add_run()
            r1.text = prefix + " "
            r1.font.size = Pt(size * (0.85 if level else 1))
            r1.font.name = FONT_CN
            r1.font.color.rgb = bullet_color
            _hang_punct(p)
            r2 = p.add_run()
            r2.text = text
            r2.font.size = Pt(size * (1 if level == 0 else 0.95))
            r2.font.name = FONT_CN
            r2.font.bold = bold
            r2.font.color.rgb = color
            for r in (r1, r2):
                rPr = r._r.get_or_add_rPr()
                ea = rPr.makeelement(qn("a:ea"), {"typeface": FONT_CN})
                rPr.append(ea)
                rPr.set("lang", "zh-CN")
                rPr.set("altLang", "en-US")


# ---------------------------------------------------------------- 版式常量（来自模板实测）
# 目录页元素坐标（模板第2页）
TOC_ITEMS = [
    {"num": "一", "title_x": 2.37, "title_y": 1.44, "title_w": 5.28, "num_x": 1.74, "num_y": 1.44},
    {"num": "二", "title_x": 3.31, "title_y": 2.38, "title_w": 5.28, "num_x": 2.61, "num_y": 2.38},
    {"num": "三", "title_x": 3.55, "title_y": 3.56, "title_w": 5.04, "num_x": 2.92, "num_y": 3.56},
    {"num": "四", "title_x": 3.16, "title_y": 4.75, "title_w": 5.28, "num_x": 2.53, "num_y": 4.75},
    {"num": "五", "title_x": 2.29, "title_y": 5.69, "title_w": 4.19, "num_x": 1.66, "num_y": 5.61},
]
TOC_NUM_W = 0.61
TOC_NUM_H = 0.69
TOC_TITLE_H = 0.58


# ---------------------------------------------------------------- 各类页面构建

def build_cover(prs, cfg, img_left=None):
    """封面：使用标题幻灯片版式，删除自带正文占位符后精确定位。

    v1.4.1: 封面上**所有文本框文字统一居中**（水平居中 + 垂直居中）。
    文本框几何保持 0.92″ 起、宽 11.5″（中心 6.67″ = 页面中线），
    因此居中后文字真正落在页面中线上；需要左对齐时在 cover 里加 "align": "left"。
    """
    layout = _find_layout(prs, "标题幻灯片")
    slide = prs.slides.add_slide(layout)
    pb = PageBuilder(slide, "标题幻灯片")
    title = cfg.get("title", "项目标题")
    _align = PP_ALIGN.LEFT if str(cfg.get("align", "center")).lower() == "left" else PP_ALIGN.CENTER
    # 主标题（占位符）
    if pb.title_ph is not None:
        ph = pb.title_ph
        ph.left, ph.top = Inches(0.92), Inches(2.05)
        ph.width, ph.height = Inches(11.5), Inches(0.95)
        tf = ph.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        _add_paragraph(tf, title, 34, bold=True, color=TEXT_MAIN, align=_align)
        try:
            ph.text_frame.paragraphs[0].runs[0].font.name = FONT_CN
        except Exception:
            pass
    else:
        pb.add_textbox(0.92, 2.05, 11.5, 0.95, title, size=34, bold=True,
                       align=_align, anchor=MSO_ANCHOR.MIDDLE)
    # 删除版式自带的正文占位符（避免空行与重复）
    for ph in list(slide.placeholders):
        if not _is_title_ph(ph):
            ph._element.getparent().remove(ph._element)
    # 副标题 / 工程范围 / 时间（全部居中）
    if cfg.get("subtitle"):
        pb.add_textbox(0.92, 3.10, 11.5, 0.45, cfg["subtitle"], size=17,
                       color=TEXT_GRAY, align=_align, anchor=MSO_ANCHOR.MIDDLE)
    if cfg.get("org"):
        pb.add_textbox(0.92, 3.62, 11.5, 0.45, cfg["org"], size=14,
                       color=TEXT_GRAY, align=_align, anchor=MSO_ANCHOR.MIDDLE)
    lines = []
    if cfg.get("author"):
        lines.append(f"汇报人：{cfg['author']}")
    if cfg.get("date"):
        lines.append(cfg["date"])
    for i, ln in enumerate(lines):
        pb.add_textbox(0.92, 4.85 + i * 0.45, 11.5, 0.42, ln, size=14,
                       color=TEXT_GRAY, align=_align, anchor=MSO_ANCHOR.MIDDLE)
    return slide


def _find_layout(prs, name):
    for master in prs.slide_masters:
        for layout in master.slide_layouts:
            if layout.name == name:
                return layout
    return prs.slide_layouts[-1]


# ---------------------------------------------------------------- 目录页（克隆模板原型，固定版式）

def _toc_items(cfg):
    """取目录条目与标题，兼容列表 / 字典两种写法。"""
    toc_cfg = cfg.get("toc", [])
    if isinstance(toc_cfg, dict):
        items = list(toc_cfg.get("items", []))
        title = toc_cfg.get("toc_title") or cfg.get("toc_title", "目录")
    else:
        items = list(toc_cfg or [])
        title = cfg.get("toc_title", "目录")
    return items, title


def _group_chapters(sections, n_items):
    """把正文页归到章：section 可带 "chapter": k（1 起）标记所属章。

    - 有显式 chapter：按章聚合，同章多页按顺序排；
    - 无显式 chapter 且页数 == 目录条数：一页一章（模板即此结构）；
    - 其它：整体视作一章（不生成章节过渡目录页）。
    """
    if not sections:
        return []
    if any("chapter" in sec for sec in sections):
        chapters = []
        cur = 1
        for sec in sections:
            k = int(sec.get("chapter", cur))
            cur = k
            if not chapters or chapters[-1][0] != k:
                chapters.append((k, []))
            chapters[-1][1].append(sec)
        return chapters
    if n_items and len(sections) == n_items:
        return [(i + 1, [sec]) for i, sec in enumerate(sections)]
    return [(1, sections)]


def _reorder_slides(prs, order):
    """按给定顺序重排页（build 过程中页面是追加的，最后统一排序）。"""
    keys = [str(s.slide_id) for s in order]  # 必须先取 id，清空列表后就查不到了
    lst = prs.slides._sldIdLst
    ids = {}
    for sld in list(lst):
        ids[sld.get("id")] = sld
    for sld in list(lst):
        lst.remove(sld)
    used = set()
    for key in keys:
        el = ids.get(key)
        if el is not None:
            lst.append(el)
            used.add(key)
    for key, el in ids.items():
        if key not in used:
            lst.append(el)


def find_toc_proto(prs):
    """在模板中定位目录页原型（含 ≥5 条「目录N标题」的页）。"""
    for slide in prs.slides:
        n = 0
        for sh in slide.shapes:
            try:
                t = sh.text_frame.text
            except Exception:
                continue
            if t.startswith("目录") and t.endswith("标题"):
                n += 1
        if n >= 5:
            return slide
    return None


def _clear_template_slides(prs, keep=None):
    """删除模板自带示例页，只保留目录页原型（供克隆用）。"""
    lst = prs.slides._sldIdLst
    keep_id = str(keep.slide_id) if keep is not None else None
    # 原型页部件改名：python-pptx 用 len(sldIdLst)+1 生成新页名，保留 slideN 会撞名
    if keep is not None:
        try:
            from pptx.opc.packuri import PackURI
            keep.part.partname = PackURI("/ppt/slides/toc_proto.xml")
        except Exception:
            pass
    removed = 0
    for sld in list(lst):
        if keep_id is not None and sld.get("id") == keep_id:
            continue
        try:
            prs.part.drop_rel(sld.get(qn("r:id")))
        except Exception:
            pass
        lst.remove(sld)
        removed += 1
    if removed:
        print(f"[清理] 移除模板自带示例页 {removed} 页，保留目录页原型")


def _clone_slide(prs, src):
    """整页克隆（含图片关系重映射）：形状、阴影、装饰、占位符全部原样保留。"""
    new = prs.slides.add_slide(src.slide_layout)
    for sh in list(new.shapes):
        sh._element.getparent().remove(sh._element)
    rid_map = {}
    for rel in src.part.rels.values():
        # 版式与备注页不能共用（备注页只能属于一页，共用会被 PowerPoint 判为损坏）
        if rel.reltype.endswith("/slideLayout") or rel.reltype.endswith("/notesSlide"):
            continue
        try:
            if rel.is_external:
                rid_map[rel.rId] = new.part.relate_to(rel.target_ref, rel.reltype, is_external=True)
            else:
                rid_map[rel.rId] = new.part.relate_to(rel.target_part, rel.reltype)
        except Exception:
            continue
    src_tree, new_tree = src.shapes._spTree, new.shapes._spTree
    for el in list(src_tree):
        if el.tag.split("}")[-1] in ("nvGrpSpPr", "grpSpPr"):
            continue
        new_tree.append(copy.deepcopy(el))
    R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    for el in new_tree.iter():
        for attr, val in list(el.attrib.items()):
            if attr.startswith(R) and val in rid_map:
                el.set(attr, rid_map[val])
    return new


def _toc_slots(slide):
    """识别目录页的标题条与编号方块，按纵向位置配对。返回 [[bar, group, top], ...]。"""
    bars, groups = [], []
    for sh in slide.shapes:
        try:
            w, h = Emu(sh.width).inches, Emu(sh.height).inches
            top = Emu(sh.top).inches
        except Exception:
            continue
        if sh.shape_type == 6 and 0.5 < w < 0.8 and 0.55 < h < 0.85:
            groups.append(sh)
        elif sh.has_text_frame and w > 3.5 and h < 0.8 and top > 1.2:
            bars.append(sh)
    bars.sort(key=lambda s: Emu(s.top).inches)
    groups.sort(key=lambda s: Emu(s.top).inches)
    slots = []
    for b in bars:
        bt = Emu(b.top).inches
        near = None
        if groups:
            near = min(groups, key=lambda g: abs(Emu(g.top).inches - bt))
        slots.append([b, near, bt])
    return slots


def _set_para_text(para, text):
    """替换段落文字但保留首个 run 的格式。"""
    runs = para.runs
    if not runs:
        para.text = text
        return None
    runs[0].text = text
    for r in runs[1:]:
        r._r.getparent().remove(r._r)
    return runs[0]


def _clear_run_color(run):
    """去掉显式颜色，回到模板继承色（非当前章用）。"""
    rPr = run._r.find(qn("a:rPr"))
    if rPr is None:
        return
    for tag in ("a:solidFill", "a:srgbClr", "a:schemeClr"):
        for el in rPr.findall(qn(tag)):
            rPr.remove(el)


def _set_slide_title_text(slide, text):
    for ph in slide.placeholders:
        try:
            is_title = (ph.placeholder_format.idx == 0
                        or ph.placeholder_format.type in (1, 3, 13))
        except Exception:
            continue
        if not is_title:
            continue
        for p in ph.text_frame.paragraphs[1:]:
            p._p.getparent().remove(p._p)
        _set_para_text(ph.text_frame.paragraphs[0], text)
        return


def _shift_el(el, x_in=None, y_in=None):
    """直接改形状 XML 的偏移（英寸），用于复制件先错位再统一排布。"""
    xfrm = el.find(".//" + qn("a:xfrm"))
    if xfrm is None:
        return
    off = xfrm.find(qn("a:off"))
    if off is None:
        return
    if x_in is not None:
        off.set("x", str(int(x_in * 914400)))
    if y_in is not None:
        off.set("y", str(int(y_in * 914400)))


def _apply_toc(slide, items, toc_title, current=None):
    """在克隆出的目录页上写文字：条数增减 + 当前章整条标红，其余格式不动。"""
    n = len(items)
    slots = _toc_slots(slide)

    # 1) 条目数：多则删、少则复制最后一条（复制件先临时错位，避免配对错乱）
    if n < len(slots):
        for bar, grp, _ in slots[n:]:
            bar._element.getparent().remove(bar._element)
            if grp is not None:
                grp._element.getparent().remove(grp._element)
        slots = slots[:n]
    elif n > len(slots) and slots:
        bar0, grp0, base_top = slots[-1]
        parent = bar0._element.getparent()
        for i in range(n - len(slots)):
            yb = base_top + 0.4 * (i + 1)
            b_el = copy.deepcopy(bar0._element)
            _shift_el(b_el, None, yb)
            parent.append(b_el)
            if grp0 is not None:
                g_el = copy.deepcopy(grp0._element)
                _shift_el(g_el, None, yb - 0.02)
                parent.append(g_el)
        slots = _toc_slots(slide)
    slots = slots[:n]

    # 2) >5 条时按模板弧线等距重排；≤5 条保持模板实测位置
    font_pt = 20.0
    if n > 5 and len(slots) == n:
        ys = [1.44 + i * (5.61 - 1.44) / (n - 1) for i in range(n)]
        base_t = [i / 4 for i in range(5)]
        # 条目多时按行距等比缩小条高/方块/字号，避免互相压边（6 条时不缩放）
        step = (5.61 - 1.44) / (n - 1)
        k = min(1.0, step / 0.70)
        font_pt = max(14.0, 20.0 * k)

        def _interp(vals, t):
            if t <= base_t[0]:
                return vals[0]
            for kk in range(1, len(base_t)):
                if t <= base_t[kk]:
                    f = (t - base_t[kk - 1]) / (base_t[kk] - base_t[kk - 1])
                    return vals[kk - 1] + (vals[kk] - vals[kk - 1]) * f
            return vals[-1]

        for i, (bar, grp, _) in enumerate(slots):
            t = i / (n - 1)
            y = ys[i]
            if grp is not None:
                grp.left = Inches(_interp([x["num_x"] for x in TOC_ITEMS], t))
                grp.top = Inches(y)
                grp.width = Inches(TOC_NUM_W * k)
                grp.height = Inches(TOC_NUM_H * k)
            bar.left = Inches(_interp([x["title_x"] for x in TOC_ITEMS], t))
            bar.top = Inches(y + (0.08 if i == n - 1 else 0))
            bar.width = Inches(_interp([x["title_w"] for x in TOC_ITEMS], t))
            bar.height = Inches(TOC_TITLE_H * k)

    # 3) 文字与标红
    for i, (bar, grp, _) in enumerate(slots):
        item = items[i] if isinstance(items[i], dict) else {"title": str(items[i])}
        is_cur = (current is not None and i == current)
        for p in bar.text_frame.paragraphs[1:]:
            p._p.getparent().remove(p._p)
        run = _set_para_text(bar.text_frame.paragraphs[0], item.get("title", ""))
        if run is not None:
            run.font.size = Pt(font_pt)
            try:
                run.font.name = FONT_CN
            except Exception:
                pass
            if is_cur:
                run.font.color.rgb = TITLE_RED
            else:
                # v1.4.2: 非当前章标题条文字统一白色（蓝底标题条上清晰）
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        if grp is not None:
            num_text = item.get("num") or _cn_num(i + 1)
            for sub in grp.shapes:
                if sub.has_text_frame and sub.text_frame.text.strip():
                    _set_para_text(sub.text_frame.paragraphs[0], num_text)
                    break

    # 4) 页标题（默认“目录”）
    if toc_title:
        _set_slide_title_text(slide, toc_title)
    return slide


def build_toc(prs, cfg, current=None, proto=None, reuse=False):
    """目录页：克隆模板原型，固定版式只改文字与标红。

    current：当前章下标（0 起），该条目标题整条标红；None 表示不标红。
    proto  ：模板目录页原型；reuse=True 时直接复用原型本身（首张目录）。
    """
    items, toc_title = _toc_items(cfg)
    if len(items) > 10:
        items = items[:10]
        print("[警告] 目录超过 10 条（编号上限：十），已截断为 10 条")
    if proto is not None:
        slide = proto if reuse else _clone_slide(prs, proto)
        return _apply_toc(slide, items, toc_title, current)
    return _build_toc_fallback(prs, cfg, current=current)


def _build_toc_fallback(prs, cfg, current=None):
    """（退化版）模板里找不到目录页原型时，按坐标重绘 1~10 条。

    - ≤5 条：直接用模板实测坐标（不补空白占位条目）；
    - >5 条：纵轴等距重排，编号 X / 标题 X / 宽度沿模板原 5 点曲线插值，
      保持模板「编号圆随纵轴先右移再左收」的弧线感。
    """
    layout = _find_layout(prs, "标题_内容")
    slide = prs.slides.add_slide(layout)
    pb = PageBuilder(slide, "标题_内容")
    # toc 支持两种写法：列表 [{"title": ...}] 或 {"toc_title": ..., "items": [...]}
    toc_cfg = cfg.get("toc", [])
    if isinstance(toc_cfg, dict):
        items = list(toc_cfg.get("items", []))
        toc_title = toc_cfg.get("toc_title") or cfg.get("toc_title", "目录")
    else:
        items = list(toc_cfg or [])
        toc_title = cfg.get("toc_title", "目录")
    if len(items) > 10:
        items = items[:10]
        print("[警告] 目录超过 10 条（编号上限：十），已截断为 10 条")
    pb.set_title(toc_title)
    # 左侧渐变装饰块（模板 Freeform2 位置）
    deco = pb.add_rect(0.72, 1.37, 2.46, 4.93, fill=RGBColor(0xE8, 0xF1, 0xF9), alpha_pct=40)
    # 条目坐标
    n = len(items)
    if n <= 5:
        pos_list = [dict(TOC_ITEMS[i]) for i in range(n)]
    else:
        ys = [1.44 + i * (5.61 - 1.44) / (n - 1) for i in range(n)]
        # 原曲线参数 t=0..1 对应 num_x / title_x / title_w
        base_t = [i / 4 for i in range(5)]

        def _interp(vals, t):
            if t <= base_t[0]:
                return vals[0]
            for k in range(1, len(base_t)):
                if t <= base_t[k]:
                    f = (t - base_t[k - 1]) / (base_t[k] - base_t[k - 1])
                    return vals[k - 1] + (vals[k] - vals[k - 1]) * f
            return vals[-1]

        pos_list = []
        for i in range(n):
            t = i / (n - 1)
            pos_list.append({
                "num": "",
                "num_x": _interp([x["num_x"] for x in TOC_ITEMS], t),
                "num_y": ys[i],
                "title_x": _interp([x["title_x"] for x in TOC_ITEMS], t),
                "title_y": ys[i],
                "title_w": _interp([x["title_w"] for x in TOC_ITEMS], t),
            })
    for i, item in enumerate(items):
        t = pos_list[i]
        num_text = item.get("num") or _cn_num(i + 1)
        title_text = item.get("title", "章节标题")
        is_cur = (current is not None and i == current)
        # 编号圆（渐变感：实心蓝）
        num = pb.add_rect(t["num_x"], t["num_y"], TOC_NUM_W, TOC_NUM_H,
                          fill=BRAND, radius=True)
        tf = num.text_frame
        tf.word_wrap = False
        _add_paragraph(tf, num_text, 20, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF),
                       align=PP_ALIGN.CENTER)
        # 标题条（蓝底矩形 + 文字：当前章红、其余白，与克隆版目录一致）
        title_color = TITLE_RED if is_cur else RGBColor(0xFF, 0xFF, 0xFF)
        bar = pb.add_rect(t["title_x"], t["title_y"] + 0.04, t["title_w"],
                          TOC_TITLE_H - 0.08, fill=BRAND)
        btf = bar.text_frame
        btf.word_wrap = True
        btf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = _add_paragraph(btf, title_text, 18, bold=is_cur, color=title_color)
        _set_autofit(bar, shrink=True)
    return slide


def _cn_num(n):
    return ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"][n - 1]


def build_section(prs, idx, section):
    """章节页：根据 section 类型排版"""
    kind = section.get("type", "bullets")
    title = section.get("title", f"第{idx}章")
    layout = _find_layout(prs, "标题_内容")
    slide = prs.slides.add_slide(layout)
    pb = PageBuilder(slide, "标题_内容")
    pb.set_title(title, size=PAGE_TITLE_SIZE, color=TEXT_MAIN, bold=False)
    content = section.get("content", [])
    if kind == "bullets":
        _layout_bullets(pb, slide, section, content)
    elif kind == "paragraph":
        _layout_paragraph(pb, slide, section, content)
    elif kind == "table":
        _layout_table(pb, slide, section, content)
    elif kind == "picture":
        _layout_picture(pb, slide, section, content)
    elif kind == "table_picture":
        _layout_table_picture(pb, slide, section, content)
    elif kind == "bullets_picture":
        _layout_bullets_picture(pb, slide, section, content)
    elif kind == "split":
        _layout_split(pb, slide, section, content)
    elif kind == "gallery":
        _layout_gallery(pb, slide, section)
    elif kind == "compare":
        _layout_compare(pb, slide, section)
    elif kind == "flow":
        _layout_flow(pb, slide, section, content)
    elif kind == "kpi":
        _layout_kpi(pb, slide, section)
    elif kind == "pareto":
        _layout_pareto(pb, slide, section)
    else:
        _layout_bullets(pb, slide, section, content)
    return slide

def _list_text(content):
    if not content:
        return []
    if isinstance(content, list):
        return content
    return []


def _add_note(pb, top, note, size=BODY_SIZE, left=BODY_LEFT, width=BODY_W, height=0.9,
              color=TEXT_GRAY, bold_prefix=True):
    """在指定顶部位置渲染灰色注释行（支持多段，以 \n 分隔）"""
    if not note:
        return
    tb = pb.add_textbox(left, top, width, height, fill=RGBColor(0xF4, 0xF8, 0xFC),
                        border=RGBColor(0xC5, 0xD9, 0xEC))
    tf = tb.text_frame
    tf.word_wrap = True
    lines = note.split("\n") if isinstance(note, str) else [str(note)]
    for j, ln in enumerate(lines):
        p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
        p.space_after = Pt(4)
        p.line_spacing = 1.15
        # 支持「标签：内容」首词加粗
        if bold_prefix and ("：" in ln) and len(ln.split("：")[0]) <= 12:
            head, rest = ln.split("：", 1)
            r1 = p.add_run(); r1.text = head + "："
            r1.font.size = Pt(size); r1.font.bold = True
            r1.font.name = FONT_CN; r1.font.color.rgb = BRAND
            rPr = r1._r.get_or_add_rPr()
            ea = rPr.makeelement(qn("a:ea"), {"typeface": FONT_CN}); rPr.append(ea); rPr.set("lang", "zh-CN"); rPr.set("altLang", "en-US")
            rPr.set("lang", "zh-CN")
            rPr.set("altLang", "en-US")
            r2 = p.add_run(); r2.text = rest
            r2.font.size = Pt(size); r2.font.name = FONT_CN; r2.font.color.rgb = color
            rPr = r2._r.get_or_add_rPr()
            ea = rPr.makeelement(qn("a:ea"), {"typeface": FONT_CN}); rPr.append(ea); rPr.set("lang", "zh-CN"); rPr.set("altLang", "en-US")
            rPr.set("lang", "zh-CN")
            rPr.set("altLang", "en-US")
        else:
            r = p.add_run(); r.text = ln
            r.font.size = Pt(size); r.font.name = FONT_CN; r.font.color.rgb = color
            rPr = r._r.get_or_add_rPr()
            ea = rPr.makeelement(qn("a:ea"), {"typeface": FONT_CN}); rPr.append(ea); rPr.set("lang", "zh-CN"); rPr.set("altLang", "en-US")
            rPr.set("lang", "zh-CN")
            rPr.set("altLang", "en-US")


def _layout_gallery(pb, slide, section):
    """一行多图 + 图注 + 说明（1.3 幕墙节点深化风格）"""
    imgs = section.get("images", [])
    note = section.get("note")
    intro = section.get("intro")
    top = BODY_TOP
    if intro:
        tb = pb.add_textbox(BODY_LEFT, top, BODY_W, 0.7)
        tf = tb.text_frame; tf.word_wrap = True
        _add_paragraph(tf, intro, BODY_SIZE, color=TEXT_MAIN, line_spacing=1.2)
        top += 0.8
    n = max(len(imgs), 1)
    gap = 0.25
    cell_w = (BODY_W - gap * (n - 1)) / n
    img_h = 3.35 if not note else 3.15

    # 先全部放图（顶部对齐），再按最高图底统一放图注，保证图注齐平且贴近图片
    max_bottom = top
    for i, im in enumerate(imgs):
        x = BODY_LEFT + i * (cell_w + gap)
        pic = pb.add_picture_fit(im.get("image"), x, top, width=cell_w - 0.1,
                                 height=img_h, align_y=0)
        max_bottom = max(max_bottom, Emu(pic.top).inches + Emu(pic.height).inches)
    for i, im in enumerate(imgs):
        cap = im.get("caption", "")
        if not cap:
            continue
        x = BODY_LEFT + i * (cell_w + gap)
        pb.add_textbox(x, max_bottom + 0.08, cell_w, 0.5 + 0.24 * cap.count("\n"),
                       cap, size=11, color=TEXT_GRAY, align=PP_ALIGN.CENTER)
    if note:
        nl = note.count("\n") + 1
        nh = 0.32 * nl + 0.24
        _add_note(pb, max(max_bottom + 0.72, NOTE_BOTTOM - nh), note, height=nh)


KPI_COLORS = [RGBColor(0x00, 0x70, 0xBF),   # 品牌蓝
              RGBColor(0x2A, 0x7F, 0x62),   # 深青绿
              RGBColor(0xC9, 0x7A, 0x16),   # 琥珀
              RGBColor(0x4A, 0x6F, 0xA5),   # 灰蓝
              RGBColor(0x8A, 0x3F, 0x6B),   # 酒紫
              RGBColor(0x56, 0x6B, 0x2F)]   # 橄榄


def _layout_kpi(pb, slide, section):
    """指标卡版式：N 张卡，每卡「标签 / 大数字+单位 / 说明」

    section 字段：
      kpis   [{value, unit, label, desc}]  desc 可为 str 或 list
      cols   每行卡数（默认一行排满）
      intro  表格上方一句前提（如测算样本与口径）
      note   底部结论条
    """
    cards = section.get("kpis") or []
    if not cards:
        return
    note = section.get("note")
    intro = section.get("intro")
    n = len(cards)
    cols = max(1, int(section.get("cols") or n))
    rows = -(-n // cols)
    top = BODY_TOP
    if intro:
        pb.add_textbox(BODY_LEFT, top - 0.06, BODY_W, 0.42, intro, size=BODY_SIZE,
                       color=TEXT_GRAY)
        top += 0.50
    note_h = (0.30 * (note.count("\n") + 1) + 0.30) if note else 0.0
    bottom = NOTE_BOTTOM - (note_h + 0.16 if note else 0.0)
    gap = 0.34 if cols <= 4 else 0.24
    cw = (BODY_W - gap * (cols - 1)) / cols
    avail = bottom - top
    ch = (avail - gap * (rows - 1)) / rows
    cap_h = 3.40                       # 单卡最大高度，超出则整块垂直居中
    if rows == 1 and ch > cap_h:
        top += (avail - cap_h) / 2
        ch = cap_h
    # 字号随卡高自适应
    if ch >= 2.95:
        v_size, d_size, l_size = 32, 12.5, 13
    elif ch >= 2.45:
        v_size, d_size, l_size = 26, 12, 12.5
    else:
        v_size, d_size, l_size = 22, 11.5, 12
    v_h = v_size / 72.0 * 1.35
    desc_top_pad = 0.52 + v_h + 0.30
    for i, card in enumerate(cards):
        r, c = divmod(i, cols)
        x = BODY_LEFT + c * (cw + gap)
        y = top + r * (ch + gap)
        color = KPI_COLORS[i % len(KPI_COLORS)]
        pb.add_rect(x, y, cw, ch, fill=RGBColor(0xF6, 0xFA, 0xFE),
                    line=RGBColor(0xDC, 0xE9, 0xF5), radius=True)
        pb.add_rect(x, y + 0.16, 0.075, ch - 0.32, fill=color)      # 左侧色条
        # 标签
        pb.add_textbox(x + 0.22, y + 0.14, cw - 0.36, 0.34,
                       card.get("label", ""), size=l_size, bold=True, color=color)
        # 大数字
        pb.add_textbox(x + 0.22, y + 0.50, cw - 0.36, v_h,
                       str(card.get("value", "")), size=v_size, bold=True, color=color)
        # 单位（独立一行小字，避免把数字挤换行）
        unit = card.get("unit") or ""
        if unit:
            pb.add_textbox(x + 0.24, y + 0.50 + v_h + 0.05, cw - 0.36, 0.28,
                           unit, size=max(11, v_size * 0.34), bold=True, color=color)
        # 分隔细线
        line_y = y + desc_top_pad + 0.02
        from pptx.enum.shapes import MSO_CONNECTOR
        ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x + 0.22),
                                        Inches(line_y), Inches(x + cw - 0.22),
                                        Inches(line_y))
        ln.line.color.rgb = RGBColor(0xC6, 0xDA, 0xEC)
        ln.line.width = Pt(1.0)
        # 说明
        desc = card.get("desc") or []
        lines = desc if isinstance(desc, list) else [desc]
        dht = max(y + ch - line_y - 0.16, 0.6)
        dtb = pb.add_textbox(x + 0.22, line_y + 0.10, cw - 0.38, dht, None,
                             size=d_size, color=TEXT_GRAY)
        dtf = dtb.text_frame
        dtf.word_wrap = True
        for j, t in enumerate(lines):
            pp = dtf.paragraphs[0] if j == 0 else dtf.add_paragraph()
            pp.line_spacing = 1.22
            pp.space_after = Pt(3)
            rr = pp.add_run()
            rr.text = t
            rr.font.size = Pt(d_size)
            rr.font.name = FONT_CN
            rr.font.color.rgb = TEXT_GRAY
            rPr = rr._r.get_or_add_rPr()
            ea = rPr.makeelement(qn("a:ea"), {"typeface": FONT_CN})
            rPr.append(ea)
            rPr.set("lang", "zh-CN")
            rPr.set("altLang", "en-US")
    if note:
        _add_note(pb, NOTE_BOTTOM - note_h, note, height=note_h)


def _layout_compare(pb, slide, section):
    """左右对比版式（原设计 vs 优化后），可选中间大图"""
    left = section.get("left", {})
    right = section.get("right", {})
    center = section.get("center_image")
    note = section.get("note")
    top = BODY_TOP
    if center:
        col_w = 4.05
        center_w = 2.55
        gap = (BODY_W - col_w * 2 - center_w) / 2
        xs = [BODY_LEFT, BODY_LEFT + col_w + gap, BODY_LEFT + col_w + gap + center_w + gap]
        center_x = xs[1]
    else:
        col_w = (BODY_W - 0.4) / 2
        xs = [BODY_LEFT, BODY_LEFT + col_w + 0.4]
        center_x = None
    img_h = 3.0 if not note else 1.95
    for side, x in ((left, xs[0]), (right, xs[2] if center else xs[1])):
        if not side:
            continue
        # 标签条
        lab = pb.add_rect(x, top, col_w, 0.42, fill=BRAND, radius=True)
        tf = lab.text_frame; tf.word_wrap = False
        _add_paragraph(tf, side.get("label", ""), 14, bold=True,
                       color=RGBColor(0xFF, 0xFF, 0xFF), align=PP_ALIGN.CENTER)
        sub = side.get("subtitle", "")
        if sub:
            pb.add_textbox(x, top + 0.48, col_w, 0.34, sub, size=13, bold=True,
                           color=TEXT_MAIN, align=PP_ALIGN.CENTER)
        # 图片（单图或多图横排）
        imgs = side.get("images") or ([side["image"]] if side.get("image") else [])
        img_top = top + 0.88
        if len(imgs) == 1:
            pb.add_picture_fit(imgs[0], x, img_top, width=col_w - 0.15, height=img_h)
        elif imgs:
            iw = (col_w - 0.15) / len(imgs)
            for k, im in enumerate(imgs):
                pb.add_picture_fit(im, x + k * iw, img_top, width=iw - 0.1, height=img_h)
        # 优缺点文字（无图时不预留图片高度，条目紧跟标签条）
        items = side.get("items", [])
        if items:
            items_top = img_top + (img_h + 0.12 if imgs else 0.10)
            nh_i = (0.32 * (note.count("\n") + 1) + 0.24) if note else 0.0
            items_h = max(NOTE_BOTTOM - nh_i - items_top - 0.12, 1.2)
            tb = pb.add_textbox(x, items_top, col_w, items_h)
            tf2 = tb.text_frame; tf2.word_wrap = True
            if not imgs:
                # 纯文字对照：条目在标签条与页脚之间垂直居中，避免内容全堆在上方
                tf2.vertical_anchor = MSO_ANCHOR.MIDDLE
            pb.set_bullets(tf2, [{"text": t} for t in items], size=12, gap=4,
                           line_spacing=1.12)
    if center_x is not None:
        ch = 4.3 if not note else 2.95
        pic = pb.add_picture_fit(center, center_x, top + 0.88, width=center_w, height=ch)
        bottom = Emu(pic.top).inches + Emu(pic.height).inches
        cap = section.get("center_caption")
        if cap:
            pb.add_textbox(center_x, bottom + 0.05, center_w, 0.35, cap, size=11,
                           color=TEXT_GRAY, align=PP_ALIGN.CENTER)
    if note:
        nh = 0.32 * (note.count("\n") + 1) + 0.24
        _add_note(pb, NOTE_BOTTOM - nh, note, height=nh)


def _layout_pareto(pb, slide, section):
    """排列图（帕累托图）：柱状频数 + 累计频率折线 + 双轴"""
    from pptx.enum.shapes import MSO_CONNECTOR
    cats = section.get("categories", [])
    vals = section.get("values", [])
    cums = section.get("cumulative", [])
    note = section.get("note")
    n = len(cats)
    if not n:
        return
    plot_l = BODY_LEFT + 0.85
    plot_r = BODY_LEFT + BODY_W - 1.05
    plot_t = BODY_TOP + 0.45
    plot_b = 5.55 if note else 6.15
    plot_w = plot_r - plot_l
    plot_h = plot_b - plot_t
    vmax = max(vals) * 1.18
    step = plot_w / n
    bar_w = step * 0.46
    grey = RGBColor(0x8C, 0x8C, 0x8C)
    # 网格线 + 左轴刻度（频数）
    ticks = 5
    for i in range(ticks + 1):
        y = plot_b - plot_h * i / ticks
        ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(plot_l),
                                        Inches(y), Inches(plot_r), Inches(y))
        ln.line.color.rgb = RGBColor(0xE3, 0xEA, 0xF2) if i else RGBColor(0xBF, 0xBF, 0xBF)
        ln.line.width = Pt(0.75 if i == 0 else 0.5)
        # 左轴标签
        pb.add_textbox(plot_l - 0.82, y - 0.14, 0.72, 0.28,
                       f"{int(round(vmax * i / ticks))}", size=10, color=grey,
                       align=PP_ALIGN.RIGHT)
        # 右轴标签（累计频率）
        pb.add_textbox(plot_r + 0.12, y - 0.14, 0.8, 0.28,
                       f"{int(round(100 * i / ticks))}%", size=10, color=grey,
                       align=PP_ALIGN.LEFT)
    # 柱状
    pts = []
    for i, (c, v) in enumerate(zip(cats, vals)):
        cx = plot_l + step * (i + 0.5)
        h = plot_h * v / vmax
        bar = pb.add_rect(cx - bar_w / 2, plot_b - h, bar_w, h, fill=BRAND)
        pb.add_textbox(cx - 0.45, plot_b - h - 0.34, 0.9, 0.3, str(v), size=11.5,
                       bold=True, color=BRAND, align=PP_ALIGN.CENTER)
        pb.add_textbox(cx - step / 2, plot_b + 0.10, step, 0.62, c, size=11.5,
                       color=TEXT_MAIN, align=PP_ALIGN.CENTER)
        if i < len(cums):
            pts.append((cx, plot_b - plot_h * cums[i] / 100.0, cums[i]))
    # 累计频率折线
    for k in range(1, len(pts)):
        x1, y1, _ = pts[k - 1]
        x2, y2, _ = pts[k]
        seg = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1),
                                         Inches(y1), Inches(x2), Inches(y2))
        seg.line.color.rgb = TITLE_RED
        seg.line.width = Pt(1.75)
    for (x, y, pct) in pts:
        dot = pb.add_rect(x - 0.055, y - 0.055, 0.11, 0.11, fill=TITLE_RED, radius=True)
        pb.add_textbox(x - 0.5, y - 0.42, 1.0, 0.28, f"{pct:.1f}%", size=10.5,
                       bold=True, color=TITLE_RED, align=PP_ALIGN.CENTER)
    # 轴标题
    pb.add_textbox(BODY_LEFT - 0.25, BODY_TOP - 0.02, 2.4, 0.3, "频数（点）",
                   size=10.5, color=grey)
    pb.add_textbox(plot_r + 0.05, BODY_TOP - 0.02, 1.6, 0.3, "累计频率",
                   size=10.5, color=grey)
    # 左竖轴线
    ax = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(plot_l),
                                    Inches(plot_t - 0.1), Inches(plot_l), Inches(plot_b))
    ax.line.color.rgb = RGBColor(0xBF, 0xBF, 0xBF)
    ax.line.width = Pt(0.75)
    if note:
        nl = note.count("\n") + 1
        nh = 0.32 * nl + 0.24
        _add_note(pb, max(plot_b + 0.12, NOTE_BOTTOM - nh), note, height=nh)


def _flow_via_visio(section, content):
    """调用 flow_to_visio.py（Visio COM）生成矢量流程图。
    返回 (emf_path, page_w, page_h) 或 None（Visio 不可用/失败时回退原生版式）。"""
    import subprocess, tempfile
    stages = section.get("stages")
    if stages:
        flow_spec = {"title": section.get("title", ""), "stages": stages}
    else:
        steps = [s if isinstance(s, str) else s.get("text", "") for s in _list_text(content)]
        flow_spec = {"title": section.get("title", ""), "steps": [s for s in steps if s]}
    if not flow_spec.get("steps") and not flow_spec.get("stages"):
        return None
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flow_to_visio.py")
    outdir = tempfile.mkdtemp(prefix="flow_visio_")
    spec_path = os.path.join(outdir, "_flow_spec.json")
    vsdx_path = os.path.join(outdir, "流程图.vsdx")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(flow_spec, f, ensure_ascii=False, indent=1)
    try:
        r = subprocess.run([sys.executable, script, spec_path, vsdx_path],
                           capture_output=True, text=True, timeout=240, encoding="utf-8",
                           errors="replace")
        meta = None
        for line in (r.stdout or "").strip().splitlines():
            line = line.strip()
            if line.startswith("{"):
                meta = json.loads(line)
        if r.returncode != 0 or not meta or not os.path.exists(meta.get("emf", "")):
            print("[flow] Visio 矢量渲染失败, 回退原生版式:", (r.stderr or "")[-300:])
            return None
        print("[flow] Visio 矢量图已生成(可再编辑):", meta.get("vsdx", vsdx_path))
        return meta["emf"], float(meta["page_w"]), float(meta["page_h"])
    except Exception as e:
        print("[flow] Visio 矢量渲染异常, 回退原生版式:", e)
        return None


def _layout_flow(pb, slide, section, content):
    """流程链版式（v1.4）: 默认经 Visio 转为矢量图（EMF）插入, 风格与
    设计后期管理流程.vsdx 一致; section 加 "flow_engine": "native" 时用原生形状版式。
    支持 stages 分阶段结构: {"stages": [{"label": "...", "steps": [...]}]}。"""
    if section.get("flow_engine", "visio") != "native":
        meta = _flow_via_visio(section, content)
        if meta:
            emf, pw, ph = meta
            note = section.get("note")
            nh = (0.32 * (note.count("\n") + 1) + 0.24) if note else 0.0
            box_h = NOTE_BOTTOM - nh - 0.20 - BODY_TOP
            scale = min(BODY_W / max(pw, 0.01), box_h / max(ph, 0.01))
            w, h = pw * scale, ph * scale
            x = BODY_LEFT + (BODY_W - w) / 2
            y = BODY_TOP + (box_h - h) / 2
            # EMF 为矢量, 在 PPT 内无损缩放; 不加边框（与参考文件一致）
            slide.shapes.add_picture(emf, Inches(x), Inches(y), Inches(w), Inches(h))
            if note:
                _add_note(pb, NOTE_BOTTOM - nh, note, height=nh)
            return
    _layout_flow_native(pb, slide, section, content)


def _layout_flow_native(pb, slide, section, content):
    """流程链原生版式（回退）: 圆角矩形依次排列，可换行"""
    steps = [s if isinstance(s, str) else s.get("text", "") for s in _list_text(content)]
    note = section.get("note")
    per_row = 6
    box_w, box_h = 1.72, 0.62
    gap_x, gap_y = 0.34, 0.75
    # 节点较少时放大节点并把整条流程下移，避免顶部一小条 + 大片空白
    if 0 < len(steps) <= 4:
        box_w, box_h = 2.15, 0.95
        gap_x = 0.45
    nh_pre = (0.32 * (note.count("\n") + 1) + 0.24) if note else 0.0
    if len(steps) <= per_row:
        # 单行流程：在正文区（标题下沿至注释条上沿）内垂直居中
        y0 = BODY_TOP + max(((NOTE_BOTTOM - nh_pre - BODY_TOP) - box_h) / 2, 0.4)
    else:
        y0 = BODY_TOP + 0.15
    arrow_color = BRAND
    for i, st in enumerate(steps):
        r, c = divmod(i, per_row)
        row_start = r * per_row
        n_in_row = min(per_row, len(steps) - row_start)
        total_w = n_in_row * box_w + (n_in_row - 1) * gap_x
        left0 = BODY_LEFT + (BODY_W - total_w) / 2
        x = left0 + c * (box_w + gap_x)
        y = y0 + r * (box_h + gap_y)
        box = pb.add_rect(x, y, box_w, box_h, fill=BRAND if r == 0 else RGBColor(0xE8, 0xF1, 0xF9),
                          radius=True)
        tf = box.text_frame; tf.word_wrap = True
        _add_paragraph(tf, st, 12 if box_h < 0.8 else 14, bold=(r == 0),
                       color=RGBColor(0xFF, 0xFF, 0xFF) if r == 0 else TEXT_MAIN,
                       align=PP_ALIGN.CENTER)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        if c < n_in_row - 1 and i < len(steps) - 1:
            ar = pb.add_textbox(x + box_w + 0.02, y + box_h / 2 - 0.2, gap_x - 0.04, 0.4,
                                "→", size=14, bold=True, color=arrow_color,
                                align=PP_ALIGN.CENTER)
    rows_used = (len(steps) - 1) // per_row + 1
    if note:
        nh = 0.32 * (note.count("\n") + 1) + 0.24
        top = y0 + rows_used * (box_h + gap_y) + 0.10
        # 单行流程：注释条贴页脚，避免流程与注释之间留大片空白
        if rows_used == 1:
            top = NOTE_BOTTOM - nh
        _add_note(pb, min(NOTE_BOTTOM - nh, top), note, height=nh)


# ---- 各排版实现 ----


def _est_lines(text, col_w_in, font_pt):
    """估算单元格文字行数（中文按 1 字宽 = 字号）"""
    if not text:
        return 1
    usable = max(col_w_in - 0.14, 0.3)
    char_w = font_pt / 72.0
    cpl = max(int(usable / char_w), 4)
    total = 0
    for seg in str(text).split("\n"):
        # 英文数字按 0.55 字宽计
        eff = 0.0
        for ch in seg:
            eff += 0.55 if ord(ch) < 128 else 1.0
        total += max(1, -(-int(eff + 0.999) // cpl))
    return max(total, 1)


def _layout_bullets(pb, slide, section, content):
    """全宽要点列表（正文统一 16 号）"""
    top = BODY_TOP
    if section.get("intro"):
        pb.add_textbox(BODY_LEFT, BODY_TOP - 0.05, BODY_W, 0.4, section["intro"],
                       size=BODY_SIZE, color=TEXT_GRAY)
        top = BODY_TOP + 0.5
    tb = pb.add_textbox(BODY_LEFT, top, BODY_W, 4.2,
                        fill=None, border=None)
    tf = tb.text_frame
    tf.word_wrap = True
    items = [c if isinstance(c, dict) else {"text": c} for c in _list_text(content)]
    n_items = len(items)
    total_chars = sum(len(it.get("text", "")) for it in items)
    size = BODY_SIZE  # v1.4: 正文固定 16 号，不再按条数缩字号；溢出由 autofit 兜底
    note = section.get("note")
    nh = (0.32 * (note.count("\n") + 1) + 0.24) if note else 0.0
    est_lines = sum(_est_lines(it["text"], BODY_W - 0.2, size) for it in items)
    note_top = (NOTE_BOTTOM - nh) if note else NOTE_BOTTOM
    if section.get("spread") and n_items > 1:
        # 条目少、页面空：按可用高度把条间距拉开，整页铺满（gap 上限 26pt）
        avail = note_top - 0.30 - top
        used = est_lines * (size * 1.30 / 72.0)
        gap = max(10, min(26, (avail - used) / (n_items - 1) * 72))
        pb.set_bullets(tf, items, size=size, gap=gap, line_spacing=1.30)
        if note:
            _add_note(pb, note_top, note, height=nh)
        return
    pb.set_bullets(tf, items, size=size, gap=10, line_spacing=1.25)
    est_h = est_lines * (size * 1.25 / 72.0) + 10 * n_items / 72.0
    note_top = (NOTE_BOTTOM - nh) if note else NOTE_BOTTOM
    avail = note_top - 0.30 - top
    # 内容偏少时整体下移居中，避免全部堆在页面上部、下方大片留白
    if est_h < avail - 1.0:
        tb.top = Inches(top + (avail - est_h) * 0.40)
    if note:
        body_bottom = Emu(tb.top).inches + est_h
        _add_note(pb, max(NOTE_BOTTOM - nh, body_bottom + 0.40),
                  note, height=nh)


def _layout_paragraph(pb, slide, section, content):
    """正式段落（可多段）"""
    paras = content if isinstance(content, list) and content and isinstance(content[0], dict) and ("para" in content[0]) else content
    # 段落较短时整体下移，避免全部堆在页面上部
    est_chars = sum(len(str(x.get("para", "") if isinstance(x, dict) else x)) for x in (paras or []))
    note = section.get("note")
    est_h = est_chars / 52.0 * 0.42 + 0.3 * len(paras or [])
    top = BODY_TOP + max(0.0, min(1.6, (5.4 - est_h) * 0.45))
    box_h = (NOTE_BOTTOM - 0.80) - top if note else 4.8
    tb = pb.add_textbox(BODY_LEFT, top, BODY_W, box_h, fill=None, border=None)
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    if isinstance(paras, list):
        for item in paras:
            text = item.get("para", "") if isinstance(item, dict) else str(item)
            if not text:
                continue
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.space_after = Pt(10)
            p.line_spacing = 1.5
            p.alignment = PP_ALIGN.JUSTIFY
            _hang_punct(p)
            r = p.add_run()
            r.text = text
            r.font.size = Pt(16)
            r.font.name = FONT_CN
            r.font.color.rgb = TEXT_MAIN
            rPr = r._r.get_or_add_rPr()
            ea = rPr.makeelement(qn("a:ea"), {"typeface": FONT_CN})
            rPr.append(ea)
            rPr.set("lang", "zh-CN")
            rPr.set("altLang", "en-US")
    else:
        _add_paragraph(tf, str(paras), 16, color=TEXT_MAIN, align=PP_ALIGN.JUSTIFY,
                       line_spacing=1.5)
    if note:
        nh = 0.62 if len(str(note)) < 62 else 0.86
        _add_note(pb, NOTE_BOTTOM - nh, note, height=nh)


def _layout_table(pb, slide, section, content):
    """整页表格（行高按文字量估算，注释置于表格下方）"""
    tbl = content if isinstance(content, list) else []
    if not tbl:
        return
    n_cols = max(len(r) for r in tbl)
    n_rows = len(tbl)
    width = BODY_W
    left = BODY_LEFT
    body_size, header_size = TABLE_SIZE, TABLE_SIZE  # v1.4: 表格文字统一 14 号

    # 列宽
    cw = section.get("col_widths")
    if cw and len(cw) == n_cols and abs(sum(cw) - width) < 1.2:
        col_widths = cw
    elif n_cols == 11:
        col_widths = [0.95] + [(width - 0.95) / 10] * 10
    elif n_cols <= 4:
        first = max(1.2, width / n_cols * 0.8)
        col_widths = [first] + [(width - first) / (n_cols - 1)] * (n_cols - 1)
    else:
        col_widths = [width / n_cols] * n_cols

    # 逐行估算高度
    heights = []
    for ri, row in enumerate(tbl):
        f = header_size if ri == 0 else body_size
        lines = max(_est_lines(row[c] if c < len(row) else "", col_widths[c], f)
                    for c in range(n_cols))
        h = lines * (f * 1.30 / 72.0) + (0.16 if ri == 0 else 0.13)
        heights.append(max(h * 1.06, 0.40 if ri == 0 else 0.345))

    note = section.get("note")
    note_h = 0.0
    if note:
        note_lines = note.count("\n") + 1
        note_h = min(1.9, 0.32 * note_lines + 0.30)

    intro = section.get("intro")
    intro_h = 0.0
    if intro:
        pb.add_textbox(BODY_LEFT, BODY_TOP - 0.05, BODY_W, 0.4, intro, size=BODY_SIZE,
                       color=TEXT_GRAY)
        intro_h = 0.48

    # 行高预算：表格 + 注释条必须落在 NOTE_BOTTOM 之内（不压页脚 5G 标识）
    budget = (NOTE_BOTTOM - BODY_TOP) - intro_h - ((note_h + 0.14) if note else 0.0)
    total_h = sum(heights)
    if total_h > budget:
        mins = [0.36 if i == 0 else 0.30 for i in range(len(heights))]
        if sum(mins) <= budget:      # 先压到最小行高为止，剩余按比例分配
            slack = budget - sum(mins)
            extra = total_h - sum(mins)
            heights = [m + (h - m) * slack / extra if extra > 0 else m
                       for h, m in zip(heights, mins)]
        else:                        # 行数太多，只能等比缩（此时允许多占到 NOTE_BOTTOM）
            k = budget / total_h
            heights = [h * k for h in heights]

    block_h = sum(heights) + (note_h + 0.14 if note else 0) + intro_h
    table_top = BODY_TOP + intro_h
    slack = (NOTE_BOTTOM - BODY_TOP) - block_h
    if slack > 1.0:
        # 行数少、下方留白多时把行高适度撑开（最多 1.3 倍），表格更饱满
        k = min(1.30, 1 + slack * 0.55 / max(sum(heights), 0.01))
        heights = [h * k for h in heights]
        block_h = sum(heights) + (note_h + 0.14 if note else 0) + intro_h
        slack = (NOTE_BOTTOM - BODY_TOP) - block_h
        table_top = BODY_TOP + intro_h + max(0.0, slack) * 0.45

    gtbl = pb.add_table(tbl, left, table_top, width,
                        col_widths=col_widths, row_height=0.3, header_h=heights[0],
                        body_size=body_size, header_size=header_size,
                        align_map={0: PP_ALIGN.CENTER},
                        first_col_bold=True)
    for ri, h in enumerate(heights):
        gtbl.rows[ri].height = Inches(h)
    if note:
        top = table_top + sum(heights) + 0.14
        floor_top = table_top + sum(heights) + 0.10
        # 保证不压表：先受 NOTE_BOTTOM 约束，再不高于表格底部
        _add_note(pb, max(floor_top, min(top, NOTE_BOTTOM - note_h)), note, height=note_h,
                  size=BODY_SIZE)


def _layout_picture(pb, slide, section, content):
    """全宽大图（居中）"""
    img = section.get("image") or (content[0] if isinstance(content, list) and content else None)
    caption = section.get("caption")
    if not img:
        pb.add_textbox(BODY_LEFT, BODY_TOP, BODY_W, 1.0, "（未提供图片）", size=14, color=TEXT_GRAY)
        return
    # 图片区 12.17 x 4.6，居中；有注释条时压到 4.05 给底条留位
    note = section.get("note")
    img_top = BODY_TOP + 0.1
    img_box_w = BODY_W
    img_box_h = 3.60 if note else 4.6
    pb.add_picture_fit(img, BODY_LEFT, img_top, width=img_box_w, height=img_box_h)
    if caption:
        pb.add_textbox(BODY_LEFT, img_top + img_box_h + 0.12, BODY_W, 0.36,
                       caption, size=13, color=TEXT_GRAY, align=PP_ALIGN.CENTER)
    if note:
        nh = 0.62 if len(str(note)) < 62 else 0.86
        _add_note(pb, NOTE_BOTTOM - nh, note, height=nh)


def _layout_table_picture(pb, slide, section, content):
    """左侧表格 + 右侧图片（模板第3页样式）"""
    tbl = section.get("table", content if isinstance(content, list) and content and isinstance(content[0], list) else [])
    img = section.get("image")
    caption = section.get("caption")
    # 左表: 宽 7.0，右图: 3.3
    table_w = 7.0
    img_w = 3.3
    gap = 0.3
    left = BODY_LEFT
    img_left = left + table_w + gap
    if tbl:
        n_rows = len(tbl)
        n_cols = max(len(r) for r in tbl)
        row_h = max(0.30, min(0.52, (BODY_BOTTOM - BODY_TOP) / max(n_rows, 1)))
        minor_col = 2.0
        col_widths = [minor_col, table_w - minor_col]
        pb.add_table(tbl, left, BODY_TOP, table_w,
                     col_widths=col_widths, row_height=row_h, header_h=0.36,
                     body_size=TABLE_SIZE, header_size=TABLE_SIZE,
                     align_map={0: PP_ALIGN.CENTER}, first_col_bold=True)
    if img:
        pb.add_picture_fit(img, img_left, BODY_TOP + 0.2, width=img_w, height=4.6)
        if caption:
            pb.add_textbox(img_left, BODY_TOP + 4.85, img_w, 0.6, caption,
                           size=11, color=TEXT_GRAY, align=PP_ALIGN.CENTER)


def _layout_bullets_picture(pb, slide, section, content):
    """左侧要点 + 右侧图片（支持多图）"""
    img = section.get("image")
    imgs = section.get("images") or ([img] if img else [])
    caption = section.get("caption")
    note = section.get("note")
    items = [c if isinstance(c, dict) else {"text": c} for c in _list_text(content)]
    tb_w = 7.6 if imgs else BODY_W
    tb = pb.add_textbox(BODY_LEFT, BODY_TOP, tb_w, 4.8, fill=None, border=None)
    tf = tb.text_frame
    tf.word_wrap = True
    n_items = len(items)
    size = BODY_SIZE  # v1.4: 正文固定 16 号
    pb.set_bullets(tf, items, size=size, gap=8, line_spacing=1.2)
    if imgs:
        img_left = BODY_LEFT + tb_w + 0.3
        img_w = BODY_W - tb_w - 0.3
        img_h = 4.6 if not note else 4.0
        bottom = BODY_TOP + 0.2
        if len(imgs) == 1:
            pic = pb.add_picture_fit(imgs[0], img_left, BODY_TOP + 0.2, width=img_w, height=img_h)
            bottom = Emu(pic.top).inches + Emu(pic.height).inches
        else:
            from PIL import Image as _Img
            with _Img.open(imgs[0]) as _im:
                _w, _h = _im.size
            portrait = (_h / max(_w, 1)) > 1.25
            if portrait:  # 竖图为并排，避免被压成窄条
                each_w = (img_w - 0.15 * (len(imgs) - 1)) / len(imgs)
                for k, im in enumerate(imgs):
                    pic = pb.add_picture_fit(im, img_left + k * (each_w + 0.15),
                                             BODY_TOP + 0.2, width=each_w, height=img_h)
                    bottom = max(bottom, Emu(pic.top).inches + Emu(pic.height).inches)
            else:  # 横图为上下排列
                each_h = (img_h - 0.2) / len(imgs)
                for k, im in enumerate(imgs):
                    pic = pb.add_picture_fit(im, img_left, BODY_TOP + 0.2 + k * (each_h + 0.2),
                                             width=img_w, height=each_h)
                    bottom = Emu(pic.top).inches + Emu(pic.height).inches
        if caption:
            pb.add_textbox(img_left, bottom + 0.08, img_w, 0.45, caption,
                           size=11, color=TEXT_GRAY, align=PP_ALIGN.CENTER)
    if note:
        nl = note.count("\n") + 1
        nh = 0.32 * nl + 0.24
        _add_note(pb, min(5.85, NOTE_BOTTOM - nh), note, height=nh)


def _layout_split(pb, slide, section, content):
    """左右等宽分栏（两短栏）"""
    left_items = section.get("left", [])
    right_items = section.get("right", [])
    note = section.get("note")
    nh = (0.32 * (note.count("\n") + 1) + 0.24) if note else 0.0
    col_w = (BODY_W - 0.5) / 2

    li = [c if isinstance(c, dict) else {"text": c} for c in left_items]
    ri = [c if isinstance(c, dict) else {"text": c} for c in right_items]
    size = BODY_SIZE  # v1.4: 正文固定 16 号

    # 估算两栏高度，短内容时整体下移居中
    def _est(items):
        lines = sum(_est_lines(it["text"], col_w - 0.2, size) for it in items)
        return lines * (size * 1.28 / 72.0) + 8 * len(items) / 72.0

    est_h = max(_est(li), _est(ri))
    note_top = (NOTE_BOTTOM - nh) if note else NOTE_BOTTOM
    avail = note_top - 0.30 - BODY_TOP
    top = BODY_TOP + ((avail - est_h) * 0.40 if est_h < avail - 1.0 else 0)

    # 左栏
    tb = pb.add_textbox(BODY_LEFT, top, col_w, 4.8, fill=None, border=None)
    tf = tb.text_frame
    tf.word_wrap = True
    pb.set_bullets(tf, li, size=size, gap=8)
    # 右栏
    tb2 = pb.add_textbox(BODY_LEFT + col_w + 0.5, top, col_w, 4.8, fill=None, border=None)
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    pb.set_bullets(tf2, ri, size=size, gap=8)
    if note:
        _add_note(pb, max(NOTE_BOTTOM - nh, top + est_h + 0.40), note, height=nh)


# ---------------------------------------------------------------- 空形状清理
import re as _re

_PROMPT_RE = _re.compile(
    r"(单击此处|点击此处|单击以|Click to edit|Click to add|Click to edit Master)",
    _re.IGNORECASE,
)


def _ppr(el):
    """取形状的 spPr（p:sp 下），没有返回 None。"""
    return el.find(qn("p:spPr"))


def _has_visible_fill(el):
    """形状是否带可见填充（纯色/渐变/图案/图片）。aq:noFill 不算。"""
    sp = _ppr(el)
    if sp is None:
        return False
    for tag in ("a:solidFill", "a:gradFill", "a:pattFill", "a:blipFill"):
        if sp.find(qn(tag)) is not None:
            return True
    return False


def _has_visible_line(el):
    """形状是否带可见描边（有线宽且线本身不是 noFill）。"""
    sp = _ppr(el)
    if sp is None:
        return False
    ln = sp.find(qn("a:ln"))
    if ln is None:
        return False
    if ln.find(qn("a:noFill")) is not None:
        return False
    if ln.find(qn("a:solidFill")) is not None or ln.find(qn("a:gradFill")) is not None:
        return True
    return False


def _is_blank_text(sp_el):
    """形状文本 strip 后是否为空（无 txBody 视为空）。"""
    t = sp_el.find(qn("p:txBody"))
    if t is None:
        return True
    buf = []
    for para in t.iter(qn("a:t")):
        if para.text:
            buf.append(para.text)
    return "".join(buf).strip() == ""


def _is_blank_text(sp_el):
    """形状文本 strip 后是否为空（无 txBody 视为空）。"""
    t = sp_el.find(qn("p:txBody"))
    if t is None:
        return True
    buf = []
    for para in t.iter(qn("a:t")):
        if para.text:
            buf.append(para.text)
    return "".join(buf).strip() == ""


def _is_prompt_text(sp_el):
    """文本是否为占位提示语（单击此处… / Click to edit… 等）。

    占位符提示语可能带多级示例（Second/Third… level），不按长度截断，
    只要命中提示词即判定为提示占位符。
    """
    t = sp_el.find(qn("p:txBody"))
    if t is None:
        return False
    txt = "".join(p.text or "" for p in t.iter(qn("a:t"))).strip()
    if not txt:
        return False
    return bool(_PROMPT_RE.search(txt))


def _strip_empty_shape(sp_el):
    """判断该形状是否为「该删的空壳」，返回 'ph' / 'tb' / None。"""
    if sp_el.tag != qn("p:sp"):
        return None
    nv = sp_el.find(qn("p:nvSpPr"))
    if nv is None:
        return None
    ph = nv.find(qn("p:nvPr") + "/" + qn("p:ph"))
    cnv = nv.find(qn("p:cNvSpPr"))
    is_txbox = cnv is not None and cnv.get("txBox") == "1"
    blank = _is_blank_text(sp_el)
    prompt = _is_prompt_text(sp_el)
    # 图片/媒体类占位符不删（可能是待插图位置）
    if ph is not None:
        ptype = (ph.get("type") or "").lower()
        if ptype in ("pic", "media", "clipart", "dgm", "chart", "tbl", "obj"):
            return None
        if blank or prompt:
            return "ph"
        return None
    if is_txbox and (blank or prompt) and not _has_visible_fill(sp_el) and not _has_visible_line(sp_el):
        return "tb"
    return None


def _strip_shapes(shapes, n_ph, n_tb):
    """遍历一组形状（含组合递归），就地删除空壳，计数累加。"""
    for sh in list(shapes):
        kind = _strip_empty_shape(sh._element)
        if kind:
            sh._element.getparent().remove(sh._element)
            if kind == "ph":
                n_ph[0] += 1
            else:
                n_tb[0] += 1
            continue
        # 组合形状递归
        if sh.shape_type == 6:  # GROUP
            for sub in list(sh.shapes):
                kind = _strip_empty_shape(sub._element)
                if kind:
                    sub._element.getparent().remove(sub._element)
                    if kind == "ph":
                        n_ph[0] += 1
                    else:
                        n_tb[0] += 1


def _strip_empty_shapes(prs, verbose=True):
    """保存前清理：删除空占位符/提示占位符 + 真正不可见的空文本框。

    覆盖三层：幻灯片、版式（slideLayouts）、母版（slideMasters）。
    为什么必须清：
      1) 页面上继承来的空正文/标题占位符，PowerPoint 会渲染成虚线框并
         显示提示语「单击此处编辑内容/标题」——成品页上非常显眼；
      2) 版式/母版里残留的提示占位符，未被页面覆盖时会直接显示提示语；
      3) 源稿迁移过来的无填充无描边空文本框，看不见但占形状树、影响统计。
    为什么不能一刀切「无文字就删」：
      模板里的装饰形状（曲线 Freeform、编号底块 Rectangle 等）也没有文字，
      但它们有可见填充/描边，属于版式元素，删了会破版。
    """
    n_ph = [0]
    n_tb = [0]
    for slide in prs.slides:
        _strip_shapes(slide.shapes, n_ph, n_tb)
    for layout in prs.slide_layouts:
        _strip_shapes(layout.shapes, n_ph, n_tb)
    for master in prs.slide_masters:
        _strip_shapes(master.shapes, n_ph, n_tb)
    if verbose and (n_ph[0] or n_tb[0]):
        print(f"[清理] 删除空/提示占位符 {n_ph[0]} 个、不可见空文本框 {n_tb[0]} 个")
    return n_ph[0], n_tb[0]


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("content_json")
    ap.add_argument("--template", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--cover", default=None, help="封面背景图(可选)")
    ap.add_argument("--right", default=None, help="全局右侧图(正文表图页)可选")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    template_path = args.template or os.path.join(here, "..", "assets", "集团模板.pptx")
    if not os.path.exists(template_path):
        # 尝试靠技能位置找
        template_path = os.path.join(here, "assets", "集团模板.pptx")
    if not os.path.exists(template_path):
        print(f"[错误] 找不到模板: {template_path}")
        sys.exit(2)

    with open(args.content_json, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    out = args.out or (os.path.splitext(args.content_json)[0] + ".pptx")
    prs = Presentation(template_path)

    # 目录页原型：模板第2页的固定版式（装饰块/阴影编号/装饰图/标题占位符）
    proto = find_toc_proto(prs)
    _clear_template_slides(prs, keep=proto)

    items, _toc_name = _toc_items(cfg)
    sections = cfg.get("sections", [])
    chapters = _group_chapters(sections, len(items))
    transitions = bool(cfg.get("toc_transition", True)) and len(chapters) > 1
    order = []

    # 封面
    cover_cfg = cfg.get("cover", cfg)
    order.append(build_cover(prs, cover_cfg))

    # 首张目录：标红第 1 章（与模板第 2 页一致）
    toc_pages = 0
    if cfg.get("toc"):
        if proto is not None:
            order.append(build_toc(prs, cfg, current=0, proto=proto, reuse=True))
        else:
            print("[警告] 模板中未找到目录页原型，目录改用坐标重绘（固定装饰会缺失）")
            order.append(build_toc(prs, cfg, current=0))
        toc_pages += 1

    # 正文：每章开始前插入一页目录，当前章整条标红（模板行为：每章结束即出现目录页）
    for pos, (_k, secs) in enumerate(chapters):
        if pos > 0 and transitions:
            cur = pos if pos < len(items) else None
            if proto is not None:
                order.append(build_toc(prs, cfg, current=cur, proto=proto))
            else:
                order.append(build_toc(prs, cfg, current=cur))
            toc_pages += 1
        for idx, sec in enumerate(secs):
            order.append(build_section(prs, idx, sec))

    # 结尾页（可选）
    if cfg.get("ending"):
        order.append(build_ending(prs, cfg["ending"]))

    _reorder_slides(prs, order)
    _strip_empty_shapes(prs)

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    prs.save(out)
    print(f"[完成] 输出: {out}")
    print(f"[统计] 封面1 + 目录{toc_pages} + 正文{len(sections)} + 结尾{1 if cfg.get('ending') else 0} = {len(order)} 页")
    if cfg.get("toc") and not transitions and len(items) > 1:
        print("[提示] 未识别出多章结构，只生成 1 张目录页；"
              "多章请在 sections 用 \"chapter\": 1 / 2 / 3 标注章节起始页")


def build_ending(prs, ending):
    layout = _find_layout(prs, "标题幻灯片")
    slide = prs.slides.add_slide(layout)
    pb = PageBuilder(slide, "标题幻灯片")
    text = ending.get("text", "谢谢！")
    # 清已有占位符
    for ph in slide.placeholders:
        tf = ph.text_frame
        for p in list(tf.paragraphs[1:]):
            p._p.getparent().remove(p._p)
        for r in tf.paragraphs[0].runs:
            r.text = ""
    tb = pb.add_textbox(1.0, 3.2, 11.3, 1.2, text, size=40, bold=True,
                        color=BRAND, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    return slide


if __name__ == "__main__":
    main()
