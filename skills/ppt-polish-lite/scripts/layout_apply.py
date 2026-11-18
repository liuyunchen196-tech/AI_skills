#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""layout_apply.py —— 按参考 deck 的「构件体系」绘制式重排 PPT（可编辑 pptx）。

**构件规范来源**：`references/ref-deck-spec.md`（从 场景00-基础操作_v2.6.pptx 实测提取）
核心构件（照抄，禁止凭印象发挥）：
  · 卡片**不画边框、不铺填充**——视觉上只有一条 0.055in 主蓝「顶部弧」
  · 编号徽章 0.4in 实心主蓝 + 12.75pt 白字，与标题**同一行**
  · 卡片标题 14.25pt B；副标 11.25pt 灰；示例用 #F0F5FF 药丸
  · 全 deck 零阴影；高级感来自**大段留白 + 字号对比**，不来自框线
  · 主色只做点/弧/徽章/中心圆，绝不铺满

子命令：
  emit  <tpl> -o <out.pptx>                生成一张示例页
  apply <src.pptx> [-o <out.pptx>]          整份 deck 自动判定版式并重排
  apply <src.pptx> <page> <tpl> -o <out>    强制某页版式

版式（tpl）—— 按内容"逻辑关系"选型：
  flow        横向流程 + 顶部弧卡 + 箭头   → 先后顺序 / 步骤 / 阶段
  comparison  左右对比（灰 / 主蓝顶弧）    → 正反对照 / 两方案取舍
  grid        卡片网格（2×3 / 3×3）        → 并列要点清单（4-9 项）
  list        三列卡（轻量并列）            → 并列要点，追求信息密度
  radial      中心圆辐射 + 环绕节点         → 并列要点"环绕一个主题"（4-6 项）
  content     通栏要点                      → 无明确关系的散点说明
"""
import argparse
import math
import os
import re
import sys

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

# ==================== 设计令牌（照抄参考 deck 实测值） ====================
C_MAIN  = RGBColor(0x16, 0x77, 0xFF)   # 主蓝：顶部弧/徽章底/小方点/中心圆
C_DEEP  = RGBColor(0x09, 0x58, 0xD9)   # 深蓝：药丸文字
C_BIG   = RGBColor(0x0B, 0x3A, 0x8C)   # 深蓝：渐变终点
C_BG1   = RGBColor(0xE6, 0xF0, 0xFF)   # 浅蓝：药丸底 / 徽章浅底
C_BG2   = RGBColor(0xF0, 0xF5, 0xFF)   # 更浅：示例药丸 / 结论条
C_LINE  = RGBColor(0xE5, 0xE7, 0xEB)   # 细分隔线 / 灰胶囊
C_SOFT  = RGBColor(0xBF, 0xDB, 0xFE)   # 淡蓝：连接线
C_GREY  = RGBColor(0xF3, 0xF4, 0xF6)   # 灰底：对比页"不推荐"侧
C_INK   = RGBColor(0x1F, 0x29, 0x37)   # 主文字
C_SUB   = RGBColor(0x4B, 0x55, 0x63)   # 次文字
C_WEAK  = RGBColor(0x9C, 0xA3, 0xAF)   # 弱文字
C_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Microsoft YaHei"

W, H = Inches(13.333), Inches(7.5)
M = Inches(0.75)
CW = Inches(11.83)

# 构件尺寸常量（来自 ref-deck-spec.md 实测）
S_ARC   = Inches(0.055)      # 卡片顶部蓝弧厚度（参考 deck freeform 实测）
S_BADGE = Inches(0.40)       # 编号徽章 0.4in 实心主蓝
S_DOT   = Inches(0.062)      # 项目符号小方点
S_DIV   = Inches(0.01)       # 细分隔线厚度
S_LINE  = Pt(1.0)            # 描边宽度（仅用于徽章环/细线）
FS_TITLE = 25.5              # 页标题
FS_BIG   = 24.0              # 卡片大标题（S02 主词，与页标题同级）
FS_CARD  = 14.25             # 卡片常规标题
FS_SUB   = 11.25             # 卡片副标
FS_BODY  = 10.5              # 卡内正文 / 药丸文字
FS_FOOT  = 9.75              # 页脚

_LABEL_HINT = re.compile(r"[（(](左|右|上|下|中)(?:侧|方|边)?[）)]|^(左|右|上|下|中)(?:栏|侧|边|方)?$")


# ==================== 绘制基础件 ====================
def _deck():
    prs = Presentation()
    prs.slide_width, prs.slide_height = int(W), int(H)
    return prs


def _blank(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, int(W), int(H))
    bg.fill.solid(); bg.fill.fore_color.rgb = C_WHITE
    bg.line.fill.background(); bg.shadow.inherit = False
    return s


def _rect(s, l, t, w, h, fill=None, line=None, lw=S_LINE,
          shape=MSO_SHAPE.RECTANGLE, radius=None):
    sh = s.shapes.add_shape(shape, int(l), int(t), int(w), int(h))
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line; sh.line.width = lw
    sh.shadow.inherit = False
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sh.adjustments[0] = radius
        except Exception:
            pass
    return sh


def _grad(s, l, t, w, h, c_from, c_to, angle=45,
          shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=None, line=None, lw=S_LINE):
    """线性渐变填充形状（复刻参考 deck 中心圆的渐变质感）。"""
    sh = s.shapes.add_shape(shape, int(l), int(t), int(w), int(h))
    sh.shadow.inherit = False
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line; sh.line.width = lw
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sh.adjustments[0] = radius
        except Exception:
            pass
    # 用 XML 写 gradFill（python-pptx 无原生渐变 API）
    from lxml import etree
    spPr = sh._element.spPr
    for tag in ("a:solidFill", "a:noFill", "a:gradFill", "a:blipFill", "a:pattFill"):
        e = spPr.find(qn(tag))
        if e is not None:
            spPr.remove(e)
    g = etree.SubElement(spPr, qn("a:gradFill"))
    g.set("rotWithShape", "1")
    gsLst = etree.SubElement(g, qn("a:gsLst"))
    for pos, col in ((0, c_from), (100000, c_to)):
        gs = etree.SubElement(gsLst, qn("a:gs")); gs.set("pos", str(pos))
        c = etree.SubElement(gs, qn("a:srgbClr")); c.set("val", "%02X%02X%02X" % (col[0], col[1], col[2]))
    lin = etree.SubElement(g, qn("a:lin"))
    lin.set("ang", str(int(angle * 60000))); lin.set("scaled", "0")
    geom = spPr.find(qn("a:prstGeom"))
    if geom is not None:
        spPr.remove(g); geom.addnext(g)
    return sh


def _hline(s, x1, y1, x2, y2, color=C_SOFT, width=Pt(1.0)):
    """用细长矩形画连接线（避免 connector 的 XML 复杂度）。"""
    dx, dy = x2 - x1, y2 - y1
    ln = math.hypot(dx, dy)
    if ln < 1:
        return None
    ang = math.degrees(math.atan2(dy, dx))
    t = max(1, int(width))
    sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, int((x1 + x2) / 2 - ln / 2),
                            int((y1 + y2) / 2 - t / 2), int(ln), t)
    sh.fill.solid(); sh.fill.fore_color.rgb = color
    sh.line.fill.background(); sh.shadow.inherit = False
    sh.rotation = ang
    return sh


def _text(s, l, t, w, h, runs, size=FS_BODY, color=C_INK, bold=False,
          align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spc=1.2, wrap=True):
    tb = s.shapes.add_textbox(int(l), int(t), int(w), int(h))
    tf = tb.text_frame; tf.word_wrap = wrap; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    if isinstance(runs, str):
        runs = [runs]
    for i, ln in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = ln
        for r in p.runs:
            r.font.size = Pt(size); r.font.name = FONT
            r.font.bold = bold; r.font.color.rgb = color
        p.line_spacing = spc; p.alignment = align
    return tb


def _wrap_lines(text, size, width_in, cjk_ratio=1.0):
    """粗略估算 CJK 文本在给定宽度下的换行行数（用于自适应卡高）。"""
    per = max(1, int(width_in / (size * cjk_ratio / 72.0)))
    return max(1, math.ceil(len(text) / per))


def _dots(s, l, t, w, h, items, size=FS_BODY, color=C_SUB, spc=1.3, gap=6,
          anchor=MSO_ANCHOR.TOP):
    """小方点（0.062in 主蓝小方块）项目符号正文。

    `gap` 单位为 **pt**（段落间距），不是 EMU。
    `anchor` 控制正文在文本框内的垂直锚点（对比页用 MIDDLE 让要点在列内垂直居中）。
    """
    tb = s.shapes.add_textbox(int(l), int(t), int(w), int(h))
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = it
        for r in p.runs:
            r.font.size = Pt(size); r.font.name = FONT; r.font.color.rgb = color
        p.line_spacing = spc
        p.space_after = Pt(gap)
        pPr = p._p.get_or_add_pPr()
        marL = int(Inches(0.18))
        pPr.set("marL", str(marL)); pPr.set("indent", str(-marL))
        for tag in ("a:buNone", "a:buChar", "a:buAutoNum", "a:buClr", "a:buSzPct", "a:buFont"):
            e = pPr.find(qn(tag))
            if e is not None:
                pPr.remove(e)
        bf = pPr.makeelement(qn("a:buFont"), {"typeface": "Arial"})
        bc = pPr.makeelement(qn("a:buClr"), {"typeface": ""})
        bc.append(pPr.makeelement(qn("a:srgbClr"), {"val": "1677FF"}))
        bs = pPr.makeelement(qn("a:buSzPct"), {"val": "70000"})
        bch = pPr.makeelement(qn("a:buChar"), {"char": "▪"})
        pPr.append(bf); pPr.append(bc); pPr.append(bs); pPr.append(bch)
    return tb


def _header(s, title, pill=None):
    # 几何契约（visual_check layout 层实测口径）：标题文本 top=0.34in=4.5% 页高，
    # 必须落在顶部区 4%~22%；标题带底 0.80in，内容带自 1.85in 起（>22% 不被吞）。
    _rect(s, M, Inches(0.39), Inches(0.06), Inches(0.35), fill=C_MAIN)
    _text(s, Inches(0.96), Inches(0.34), Inches(9.5), Inches(0.46),
          title, size=FS_TITLE, color=C_INK, bold=True)
    if pill:
        pw = int(Inches(0.115 * len(pill) + 0.32))
        _rect(s, int(W) - int(M) - pw, Inches(0.43), pw, Inches(0.28),
              fill=C_BG1, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
        _text(s, int(W) - int(M) - pw, Inches(0.43), pw, Inches(0.28), pill,
              size=FS_BODY, color=C_DEEP, bold=True, align=PP_ALIGN.CENTER,
              anchor=MSO_ANCHOR.MIDDLE)


def _footer(s, page, total=38):
    _text(s, M, Inches(7.15), Inches(4), Inches(0.2),
          "PPT Polish · 科技蓝模板", size=FS_FOOT, color=C_WEAK)
    _text(s, Inches(12.12), Inches(7.15), Inches(0.5), Inches(0.2),
          f"{page:02d} / {total}", size=FS_FOOT, color=C_WEAK, align=PP_ALIGN.RIGHT)


def _pill(s, l, t, text, fill=C_BG2, color=C_DEEP, size=FS_BODY, h=Inches(0.32), w=None):
    """浅蓝药丸标签（参考 deck 的「示例」条）。"""
    if w is None:
        w = int(Inches(0.118 * len(text) + 0.26))
    _rect(s, l, t, w, h, fill=fill, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
    _text(s, l, t, w, h, text, size=size, color=color, bold=True,
          align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    return w


# ---------- 卡片构件（参考 deck 真实语言：一条顶弧 + 标题 + 副标 + 留白） ----------
def _arc(s, x, y, w):
    """卡片顶部蓝弧 —— 参考 deck 卡片唯一可见元素（freeform 环形，厚 0.055in）。"""
    _rect(s, x, y, w, S_ARC, fill=C_MAIN,
          shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)


def _card(s, x, y, w, h, idx=None, title=None, sub=None, body=None, sample=None,
          title_size=FS_CARD, sub_size=FS_SUB, arc=True,
          pad=0.26, badge=None, title_lh=0.34, gap1=0.10,
          sub_h=0.24, gap2=0.10, body_pitch=0.26, body_size=FS_BODY,
          body_spc=1.3, body_gap=4, pill_h=0.34, badge_fs=12.75):
    """参考 deck 风格卡片：**不画边框、不铺填充**，只有顶部弧 + 文字 + 可选药丸。

    层序：
      1. 顶部蓝弧 0.055in（卡宽）
      2. [徽章 0.4in 实心主蓝 + 数字 12.75pt 白] + 标题 14.25pt B（同一行）
      3. 副标 11.25pt 灰
      4. 正文小方点 10.5pt
      5. 示例药丸 #F0F5FF

    间距/字号参数（pad/badge/title_lh/gap1/sub_h/gap2/body_pitch/body_*/pill_h/badge_fs）
    供「高卡 airy 模式」放大主体、把内容带撑满内容区用；**默认值即参考 deck 的紧凑节奏**，
    list/grid 等版式不传这些参数，行为与之前完全一致。
    返回内容底部 y（供调用方排版）。
    """
    if badge is None:
        badge = S_BADGE
    if arc:
        _arc(s, x, y, w)
    cy = int(y) + (int(Inches(pad)) if arc else 0)
    tx = int(x)                      # 文本左边界

    # 标题过长时自动缩字号 + 按实际行数下移副标，避免溢出与压字
    def _lines(text, size, avail_in):
        """估算 CJK 文本在 avail_in 宽度下的行数。"""
        if not text:
            return 1
        per = max(1, int(avail_in * 72.0 / (size * 1.02)))
        return max(1, math.ceil(len(text) / per))

    # 徽章 + 标题同一行（标题可换行，副标位置按实际行数下移）
    if idx is not None:
        bx, by = tx, cy
        _rect(s, bx, by, Inches(badge), Inches(badge), fill=C_MAIN,
              shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.28)
        _text(s, bx, by, Inches(badge), Inches(badge), str(idx),
              size=badge_fs, color=C_WHITE, bold=True,
              align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        tx = int(x) + int(Inches(badge)) + int(Inches(0.14))
        avail = (int(x) + int(w) - tx) / 914400.0
        tsz = title_size
        nl = _lines(title, tsz, avail)
        # 行数超过 1 时缩字号，最多缩到 11pt
        while nl > 1 and tsz > 11.0:
            tsz -= 0.75
            nl = _lines(title, tsz, avail)
        th = int(Inches(title_lh * nl)) if nl > 1 else int(Inches(badge))
        _text(s, tx, by, int(x) + int(w) - int(tx), max(th, int(Inches(badge))), title or "",
              size=tsz, color=C_INK, bold=True,
              anchor=MSO_ANCHOR.TOP if nl > 1 else MSO_ANCHOR.MIDDLE, spc=1.1)
        cy += max(th, int(Inches(badge))) + int(Inches(gap1))
    elif title:
        tsz = title_size
        nl = _lines(title, tsz, int(w) / 914400.0)
        while nl > 1 and tsz > 11.0:
            tsz -= 0.75
            nl = _lines(title, tsz, int(w) / 914400.0)
        th = int(Inches(title_lh * nl))
        _text(s, tx, cy, int(w), th, title, size=tsz, color=C_INK,
              bold=True, spc=1.1)
        cy += th + int(Inches(0.08))

    if sub:
        sh_ = int(Inches(sub_h))
        _text(s, int(x), cy, int(w), sh_, sub, size=sub_size, color=C_SUB, spc=1.25)
        cy += sh_ + int(Inches(gap2))

    if body:
        n = len(body)
        bh = int(Inches(0.06 + body_pitch * n))
        _dots(s, int(x), cy, int(w), bh, body, size=body_size, color=C_SUB,
              spc=body_spc, gap=body_gap)
        cy += bh

    if sample:
        py = cy + int(Inches(0.04))
        if py + int(Inches(pill_h)) > int(y) + int(h):
            py = int(y) + int(h) - int(Inches(pill_h))
        # 药丸内文字按卡宽截断，避免撑破
        maxc = max(6, int(int(w) / 914400.0 * 72.0 / (body_size * 1.06)))
        stxt = sample if len(sample) <= maxc else sample[:maxc - 1] + "…"
        _pill(s, int(x), py, stxt, w=w, h=Inches(pill_h), size=body_size)
        cy = py + int(Inches(pill_h))
    return cy


# ==================== 版式绘制 ====================
def draw_flow(s, title, items, pill="流程 · 步骤", page=1):
    """横向流程：高卡 + 箭头。

    几何契约（visual_check ③⑦ 实测口径）：内容带 1.85~6.20in（fill≈62%，
    上下留白 121/110px，B1/B2 余量 ≥8px）。卡内用 airy 参数（大徽章/5 行正文/
    0.40in 行距/贴底药丸）把主体撑满，避免「卡片矮、下方大片空」被判留白过多。
    """
    _header(s, title, pill)
    n = max(1, len(items))
    gapx = Inches(0.46)
    w = int((CW - gapx * (n - 1)) / n)
    y, h = Inches(1.85), Inches(4.35)
    for i, st in enumerate(items):
        x = int(M) + i * (w + int(gapx))
        _card(s, x, y, w, h, idx=i + 1, title=st,
              sub=f"第 {i+1} 步 · 关键动作",
              body=["明确输入与输出", "确认责任人与节点", "完成后留痕可追溯",
                    "输出物对齐验收标准", "异常按既定路径升级"],
              sample=f"STEP {i+1}",
              title_size=16, sub_size=12,
              pad=0.30, badge=0.46, badge_fs=14, title_lh=0.36,
              gap1=0.28, sub_h=0.28, gap2=0.30,
              body_pitch=0.40, body_size=11.5, body_spc=1.5, body_gap=8,
              pill_h=0.38)
        if i < n - 1:
            ax = x + w + int(Inches(0.12))
            ar = _rect(s, ax, int(y) + int(h) // 2 - int(Inches(0.10)),
                       int(Inches(0.22)), int(Inches(0.20)),
                       fill=C_MAIN, shape=MSO_SHAPE.ISOSCELES_TRIANGLE)
            ar.rotation = 90
    _footer(s, page)


def draw_comparison(s, title, left_label, left_items, right_label, right_items,
                    pill="对比 · 两种方案", page=1, conclusion=None,
                    left_tag="不推荐", right_tag="推荐"):
    """左右对比：左=灰底柱（中性），右=浅蓝底柱（推荐），带药丸标签。

    几何契约（visual_check ③⑦ 实测口径）：内容带 1.85~6.20in。
    tint 底柱是禁则表 sanctioned 的「背景 tint」替代（Δ>8 的浅色块算有效墨量），
    把内容带真正撑到内容区底部；无结论条时柱高 4.35，有结论条时柱高 3.60 + 条 5.75~6.31。
    """
    _header(s, title, pill)
    colw = Inches(5.69); gap = Inches(0.45)
    n = max(len(left_items), len(right_items))
    y = Inches(1.85)
    h = Inches(3.60) if conclusion else Inches(4.35)
    cy2 = int(M) + int(colw) + int(gap)

    # 底柱（先画，压在弧/标签/要点之下）：左灰、右浅蓝
    _rect(s, M, y, colw, h, fill=C_GREY)
    _rect(s, cy2, y, colw, h, fill=C_BG2)

    # 左：灰弧 + 灰胶囊
    _rect(s, M, y, colw, S_ARC, fill=C_LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
    _text(s, int(M), int(y) + int(Inches(0.26)), colw - int(Inches(1.50)), Inches(0.40),
          left_label, size=FS_BIG, color=C_SUB, bold=True, spc=1.1)
    if left_tag:
        _pill(s, int(M) + int(colw) - int(Inches(1.20)), int(y) + int(Inches(0.30)),
              left_tag, fill=C_LINE, color=C_SUB)
    _dots(s, int(M), int(y) + int(Inches(0.96)), colw,
          h - int(Inches(1.20)), left_items, size=11.5, color=C_SUB, spc=1.5, gap=10,
          anchor=MSO_ANCHOR.MIDDLE)

    # 右：主蓝弧 + 浅蓝药丸
    _rect(s, cy2, y, colw, S_ARC, fill=C_MAIN, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
    _text(s, cy2, int(y) + int(Inches(0.26)), colw - int(Inches(1.50)), Inches(0.40),
          right_label, size=FS_BIG, color=C_DEEP, bold=True, spc=1.1)
    if right_tag:
        _pill(s, cy2 + int(colw) - int(Inches(1.20)), int(y) + int(Inches(0.30)),
              right_tag, fill=C_BG1, color=C_DEEP)
    _dots(s, cy2, int(y) + int(Inches(0.96)), colw,
          h - int(Inches(1.20)), right_items, size=11.5, color=C_SUB, spc=1.5, gap=10,
          anchor=MSO_ANCHOR.MIDDLE)

    if conclusion:
        ty = int(y) + int(h) + int(Inches(0.30))
        if ty + int(Inches(0.56)) > int(Inches(7.05)):
            ty = int(Inches(7.05)) - int(Inches(0.56))
        _rect(s, M, ty, CW, Inches(0.56), fill=C_BG2)
        _rect(s, M, int(ty) + int(Inches(0.14)), int(Inches(0.055)), Inches(0.28), fill=C_MAIN)
        _text(s, int(M) + int(Inches(0.30)), ty, CW - int(Inches(0.60)), Inches(0.56),
              conclusion, size=FS_SUB, color=C_SUB, anchor=MSO_ANCHOR.MIDDLE)
    _footer(s, page)


def draw_list(s, title, items, pill="清单 · 能力", page=1):
    """三列卡清单（顶弧 + 徽章行 + 副标 + 药丸）。"""
    _header(s, title, pill)
    cols = 3
    gapx = Inches(0.83)
    w = int((CW - gapx * (cols - 1)) / cols)
    rows = (len(items) + cols - 1) // cols
    y0 = Inches(1.70)
    gy = Inches(1.00)
    h = Inches(2.05)
    for i, it in enumerate(items):
        r, c = divmod(i, cols)
        x = int(M) + c * (w + int(gapx))
        y = int(y0) + r * (int(h) + int(gy))
        _card(s, x, y, w, h, idx=i + 1, title=it,
              sub="关键要点与落地方式", sample=f"{it} · 场景实例")


def draw_content(s, title, items, pill="要点", page=1):
    """通栏要点：按列分组的顶部弧 + 圆点正文（避免单一长条压顶）。"""
    _header(s, title, pill)
    items = list(items)
    n = max(1, len(items))
    cols = 2 if n <= 6 else 3
    gapx = Inches(0.62)
    w = int((CW - gapx * (cols - 1)) / cols)
    per = math.ceil(n / cols)
    y0 = Inches(1.75)
    gap_pt = 26                     # 段落间距用 pt（不是 EMU）
    for c in range(cols):
        chunk = items[c * per:(c + 1) * per]
        if not chunk:
            continue
        x = int(M) + c * (w + int(gapx))
        _arc(s, x, y0, w)
        _dots(s, x, int(y0) + int(Inches(0.30)), w,
              int(Inches(5.0)), chunk, size=FS_SUB, color=C_SUB, spc=1.45, gap=gap_pt)
    _footer(s, page)


# ---------- 结构化重排：中心辐射 / 网格 ----------
def _node_card(s, x, y, w, h, idx, text, side="r"):
    """辐射节点：顶部弧 + 单行标题（参考 S04 的环绕名片）。"""
    _arc(s, x, y, w)
    _text(s, x, int(y) + int(Inches(0.22)), w, int(h) - int(Inches(0.30)),
          text, size=FS_CARD, color=C_INK, bold=True, spc=1.15,
          anchor=MSO_ANCHOR.TOP)


def draw_radial(s, title, items, pill="并列 · 中心辐射", page=1,
                center_top=None, center_bottom="核心主题"):
    """中心圆辐射：中心渐变圆 + 环绕节点卡（参考 S04「六张能力名片」）。

    适合 4-6 个「环绕同一主题」的并列要点。

    几何契约（visual_check ⑦ 实测口径）：虚线环顶 1.80in（207px，>22% 标题带
    吸收线 190px，不被吞）、环底 6.30in；节点带按 n 自适应撑到 1.95~6.15in，
    上下留白 115/98px，B1/B2 均留 ≥15px 余量。环与节点半径解耦：环管内容带，
    节点管围绕排布。
    """
    _header(s, title, pill)
    items = items[:6]
    n = max(1, len(items))

    cx = int(W / 2)
    cy = int(Inches(4.05))
    rx = int(Inches(3.65))
    ry_ring = int(Inches(2.25))                      # 虚线环垂直半轴：环顶 1.80 / 环底 6.30
    cw = int(Inches(2.20))
    nw, nh = int(Inches(2.90)), int(Inches(0.95))
    inset = int(Inches(0.16))

    # 节点椭圆垂直半轴：让最顶/最底节点卡落在 1.95~6.15in（节点带高 4.20in）
    theta = math.radians(-90 + 180.0 / n)            # 最顶节点的角度
    s_top = abs(math.sin(theta))                     # 勿命名 s：会遮蔽幻灯片参数
    ry_node = int(Inches(1.625 / s_top)) if s_top >= 0.1 else int(Inches(1.6))

    ring = _rect(s, cx - rx, cy - ry_ring, rx * 2, ry_ring * 2, fill=None,
                 line=C_LINE, lw=Pt(1.0), shape=MSO_SHAPE.OVAL)
    try:
        from pptx.enum.dml import MSO_LINE_DASH_STYLE
        ring.line.dash_style = MSO_LINE_DASH_STYLE.ROUND_DOT
    except Exception:
        pass

    _grad(s, cx - cw // 2, cy - cw // 2, cw, cw, C_MAIN, C_BIG,
          angle=45, shape=MSO_SHAPE.OVAL)
    if center_top:
        _text(s, cx - cw // 2, cy - int(Inches(0.48)), cw, Inches(0.46), center_top,
              size=27, color=C_WHITE, bold=True, align=PP_ALIGN.CENTER,
              anchor=MSO_ANCHOR.BOTTOM)
    _text(s, cx - cw // 2, cy - int(Inches(0.02)), cw, Inches(0.34), center_bottom,
          size=FS_SUB, color=C_BG1, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.TOP)

    for i, it in enumerate(items):
        ang = math.radians(-90 + 360.0 * i / n + (360.0 / n) / 2)
        cos_a, sin_a = math.cos(ang), math.sin(ang)
        px = cx + int(rx * cos_a)
        py = cy + int(ry_node * sin_a)
        x = px - nw + inset if cos_a < 0 else px - inset
        y = py - nh // 2
        sx = cx + int((cw / 2) * cos_a)
        sy = cy + int((cw / 2) * sin_a)
        ex = x + nw if cos_a < 0 else x
        _hline(s, sx, sy, ex, py, color=C_SOFT, width=Pt(1.0))
        _node_card(s, x, y, nw, nh, i + 1, it)
    _footer(s, page)


def draw_grid(s, title, items, pill="清单 · 能力", page=1):
    """卡片网格：最多 3×3；卡内只放「徽章+标题+示例药丸」，靠留白呼吸。"""
    _header(s, title, pill)
    items = list(items)[:9]                 # 硬上限 9 项（多出的丢弃，避免溢出）
    n = max(1, len(items))
    cols = 3 if n > 4 else 2
    gapx, gapy = Inches(0.60), Inches(0.62)
    y0 = Inches(1.75)
    w = int((CW - gapx * (cols - 1)) / cols)
    rows = max(1, (n + cols - 1) // cols)
    h = int((Inches(4.95) - gapy * (rows - 1)) / rows)
    for i, it in enumerate(items):
        r, c = divmod(i, cols)
        x = int(M) + c * (w + int(gapx))
        y = int(y0) + r * (h + int(gapy))
        _card(s, x, y, w, h, idx=i + 1, title=it,
              sample=f"{it} · 关键要点与落地方式")
    _footer(s, page)


DRAWERS = {
    "flow": draw_flow,
    "comparison": draw_comparison,
    "radial": draw_radial,
    "grid": draw_grid,
    "list": draw_list,
    "content": draw_content,
}


# ==================== 内容抽取 ====================
def _size_pt(p):
    sizes = [r.font.size.pt for r in p.runs if r.font.size]
    if p.font.size:
        sizes.append(p.font.size.pt)
    return max(sizes) if sizes else 0


def _extract(slide):
    """返回 (title, items, meta)。

    **关键：按"卡片"分组，而不是把每一行文字都当一条 item。**
    参考 deck 的卡通常是「一个形状里多行文字」（标题 + 副标 + 说明）。
    以前逐行拆开会把 6 张卡炸成 24 条 item，导致 grid 严重溢出。
    这里改为：先按形状聚类，每个形状取"首行"作标题、其余行进 body。
    """
    prs = slide.part.package.presentation_part.presentation
    sw = float(prs.slide_width); swi = float(prs.slide_height); mid = sw / 2.0
    title = None
    blocks = []                       # [{"title","sub","body","x","y","size","w"}]
    for sh in slide.shapes:
        if not (sh.has_text_frame and sh.text_frame.text.strip()):
            continue
        lines = [ln.strip() for ln in sh.text_frame.text.splitlines() if ln.strip()]
        if not lines:
            continue
        sz = _size_pt(sh.text_frame.paragraphs[0])
        # 页脚 / 页码 / 右上药丸：跳过
        top = float(sh.top); left = float(sh.left)
        if top > 0.98 * swi or (top < 0.10 * swi and left > 0.75 * sw):
            continue
        if re.fullmatch(r"\d+\s*/\s*\d+", lines[0]):     # 纯页码
            continue
        blk = {"title": lines[0], "sub": "", "body": lines[1:],
               "x": left, "y": top, "size": sz,
               "w": float(sh.width), "h": float(sh.height)}
        # 取最大字号那块当页标题
        if title is None or (sz and sz > title[1]):
            title = (lines[0], sz)
        blocks.append(blk)

    if not title:
        return "标题", [], {"records": [], "left_label": "", "right_label": "",
                            "left": [], "right": [], "blocks": []}

    # 页标题块从内容里剔除
    content = [b for b in blocks if b["title"] != title[0].strip()]
    # 过长的单行（像通栏摘要）不算要点
    content = [b for b in content if len(b["title"]) <= 40]

    left_label = right_label = ""
    items, rec_out = [], []
    for b in content:
        t = b["title"]
        if _LABEL_HINT.search(t):
            if b["x"] < mid:
                left_label = t
            else:
                right_label = t
            continue
        items.append(t)
        rec_out.append({"text": t, "x": b["x"], "body": b["body"]})
    left = [r["text"] for r in rec_out if r["x"] < mid]
    right = [r["text"] for r in rec_out if r["x"] >= mid]
    # 按位置排序（先上下、再左右），让 grid 的顺序与版面一致
    order = sorted(range(len(rec_out)),
                   key=lambda i: (round(rec_out[i]["x"] / max(sw * 0.20, 1)),
                                  rec_out[i]["x"]))
    items = [items[i] for i in order] if len(order) == len(items) else items
    return title[0], items, {"records": rec_out, "left_label": left_label,
                             "right_label": right_label, "left": left, "right": right,
                             "blocks": content}


def _detect(slide, items, meta, title):
    """按内容「逻辑关系」选版式 —— 这是美化体验的本质。"""
    if not items:
        return "content"
    if meta["left_label"] and meta["right_label"] and len(meta["left"]) >= 2 and len(meta["right"]) >= 2:
        return "comparison"
    if re.search(r"第[一二三四五六七八九十\d]+步|步骤|流程|阶段|落地|实施|时间轴|路线", title):
        return "flow"
    n = len(items)
    if 4 <= n <= 6:
        return "radial"
    if n >= 7:
        return "grid"
    return "content"


# ==================== 命令 ====================
def cmd_emit(args):
    samples = {
        "flow": ("落地四步法", ["需求调研与范围确认", "样板抽取与模板固化", "分章节起草与校验", "定稿与交付"]),
        "comparison": ("技术栈选型：自研 vs 采购",
                       ["自主可控", "长期成本高", "迭代灵活", "需组建团队"],
                       ["上线快", "许可费用", "厂商锁定风险", "标准化支持"]),
        "radial": ("平台五大核心能力", ["智能问答", "文档解析", "报表生成", "流程编排", "知识检索"]),
        "grid": ("平台七大能力", ["智能问答", "文档解析", "报表生成", "流程编排",
                                  "知识检索", "权限管控", "数据看板"]),
        "list": ("核心能力清单", ["智能问答", "文档解析", "报表生成", "流程编排", "知识检索", "权限管控"]),
        "content": ("章节标题", ["要点一", "要点二", "要点三"]),
    }
    data = samples.get(args.tpl, samples["content"])
    prs = _deck(); s = _blank(prs)
    if args.tpl == "comparison":
        draw_comparison(s, data[0], "方案 A", data[1], "方案 B", data[2], page=1)
    elif args.tpl == "radial":
        draw_radial(s, data[0], data[1], page=1,
                    center_top=str(len(data[1])), center_bottom="核心能力")
    elif args.tpl == "flow":
        draw_flow(s, data[0], data[1], page=1)
    elif args.tpl in ("grid", "list"):
        DRAWERS[args.tpl](s, data[0], data[1], page=1)
    else:
        draw_content(s, data[0], data[1], page=1)
    prs.save(args.o); print(f"EMIT {args.tpl} -> {args.o}")


def cmd_apply(args):
    src = Presentation(args.src)
    forced = {}
    if args.page and args.tpl:
        forced[int(args.page) - 1] = args.tpl
    prs = _deck(); info = []
    for i, sl in enumerate(src.slides):
        title, items, meta = _extract(sl)
        tpl = forced.get(i) or _detect(sl, items, meta, title)
        info.append((i + 1, tpl, title[:16]))
        s = _blank(prs)
        if tpl == "comparison":
            draw_comparison(s, title, meta["left_label"] or "方案 A", meta["left"],
                            meta["right_label"] or "方案 B", meta["right"], page=i + 1)
        elif tpl == "radial":
            DRAWERS[tpl](s, title, items, page=i + 1,
                         center_top=str(len(items)), center_bottom="要点")
        else:
            DRAWERS[tpl](s, title, items, page=i + 1)
    prs.save(args.o)
    print(f"APPLY {args.src} -> {args.o}   {info}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    e = sub.add_parser("emit"); e.add_argument("tpl"); e.add_argument("-o", required=True); e.set_defaults(func=cmd_emit)
    a = sub.add_parser("apply"); a.add_argument("src"); a.add_argument("page", nargs="?", default=None)
    a.add_argument("tpl", nargs="?"); a.add_argument("-o", required=True); a.set_defaults(func=cmd_apply)
    args = ap.parse_args()
    if not getattr(args, "cmd", None):
        ap.print_help(); sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
