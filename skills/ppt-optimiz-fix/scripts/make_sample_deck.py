# -*- coding: utf-8 -*-
"""生成一个带典型缺陷的样例 deck，用于：
  - 验证 inspect/report 的自动信号（ROI 页 / CTA 收口页缺失 / 占位符 / 页码错位等）；
  - 产出 P2「SkillHub 简介门面」所需的样例评估报告截图。

用法：
    python make_sample_deck.py [out.pptx]
默认输出到 脚本同级的 assets/企业AI办公提效_样例.pptx
"""
import os
import sys

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.text import PP_ALIGN

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def _box(slide, l, t, w, h, text, size=18, font="微软雅黑", bold=False,
         color=(0x22, 0x22, 0x22), align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.name = font
    r.font.bold = bold
    from pptx.dml.color import RGBColor
    r.font.color.rgb = RGBColor(*color)
    return tb


def _footer(slide, num, font="微软雅黑"):
    tb = slide.shapes.add_textbox(Inches(11.3), Inches(6.95), Inches(1.2), Inches(0.4))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    r = p.add_run()
    r.text = str(num)
    r.font.size = Pt(11)
    r.font.name = font
    return tb


def build(path):
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]

    # S1 封面（含全局结论 + 行动式标题）
    s = prs.slides.add_slide(blank)
    _box(s, Inches(0.8), Inches(2.4), Inches(11.7), Inches(1.4),
         "用 AI 办公，把重复工时砍掉一半", size=40, bold=True, color=(0x2b, 0x58, 0x76))
    _box(s, Inches(0.8), Inches(3.9), Inches(11.0), Inches(0.8),
         "—— 企业全员 AI 基础能力落地方案", size=20, color=(0x6b, 0x72, 0x80))
    _footer(s, 1)

    # S2 话题式标题（P1 话题式）
    s = prs.slides.add_slide(blank)
    _box(s, Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.0),
         "背景与痛点", size=34, bold=True, color=(0x1f, 0x23, 0x29))
    _box(s, Inches(0.8), Inches(2.0), Inches(11.7), Inches(2.0),
         "员工每天在周报、整理、查找资料上耗费大量时间，效率有待提升。"
         "随着人工智能的发展，办公场景迎来新机会。", size=18)
    _footer(s, 2)

    # S3 行动式标题（正常）
    s = prs.slides.add_slide(blank)
    _box(s, Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.0),
         "三类重复工作最耗人", size=32, bold=True, color=(0x1f, 0x23, 0x29))
    _box(s, Inches(0.8), Inches(2.0), Inches(11.7), Inches(3.0),
         "· 周报/日报撰写——平均每周 3 小时\n"
         "· 跨系统资料查找——平均每周 2.5 小时\n"
         "· 会议纪要整理——平均每周 2 小时", size=18)
    # 故意制造页码错位（页脚写 99）
    _footer(s, 99)

    # S4 ROI 量化页（自动信号命中）
    s = prs.slides.add_slide(blank)
    _box(s, Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.0),
         "投资回报：4 个月回本，年化收益 38%", size=32, bold=True, color=(0x1f, 0x23, 0x29))
    _box(s, Inches(0.8), Inches(2.0), Inches(11.7), Inches(3.5),
         "· 年节省工时：约 3200 小时\n"
         "· 投入成本：工具订阅 + 培训 约 12 万元\n"
         "· 回收期：4 个月\n"
         "· 年化收益率（ROI）：38%\n"
         "（示意值，以实测替换）", size=18, color=(0x16, 0x65, 0x34))
    _footer(s, 4)

    # S5 行动式标题（正常）
    s = prs.slides.add_slide(blank)
    _box(s, Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.0),
         "实施三步走", size=32, bold=True, color=(0x1f, 0x23, 0x29))
    _box(s, Inches(0.8), Inches(2.0), Inches(11.7), Inches(3.0),
         "第一步：全员开通 AI 助手账号\n"
         "第二步：梳理 10 个高频重复场景模板\n"
         "第三步：两周试点 + 复盘迭代", size=18)
    _footer(s, 5)

    # S6 占位符未替换（P0 硬缺陷）
    s = prs.slides.add_slide(blank)
    _box(s, Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.0),
         "试点负责人与排期", size=32, bold=True, color=(0x1f, 0x23, 0x29))
    _box(s, Inches(0.8), Inches(2.0), Inches(11.7), Inches(2.0),
         "请填写：\n负责人：【姓名】\n所属部门：【部门】\n启动日期：【日期】\n"
         "（占位符未替换，仅为示例）", size=18, color=(0xc0, 0x39, 0x2b))
    _footer(s, 6)

    # S7 字体混搭（P1）+ 话题式标题
    s = prs.slides.add_slide(blank)
    _box(s, Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.0),
         "总结", size=34, bold=True, color=(0x1f, 0x23, 0x29))
    # 故意用 Calibri 制造字族混搭
    _box(s, Inches(0.8), Inches(2.0), Inches(11.7), Inches(2.0),
         "AI 办公是降本增效的关键抓手，建议尽快落地。", size=18, font="Calibri")
    _footer(s, 7)

    # S8 重复标题（P0 重复标题，与 S3 同标题）
    s = prs.slides.add_slide(blank)
    _box(s, Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.0),
         "三类重复工作最耗人", size=32, bold=True, color=(0x1f, 0x23, 0x29))
    _box(s, Inches(0.8), Inches(2.0), Inches(11.7), Inches(2.0),
         "（与第 3 页标题重复，构成冗余页）", size=16, color=(0x6b, 0x72, 0x80))
    _footer(s, 8)

    prs.save(path)
    print("SAMPLE DECK ->", path, "| %d slides" % len(prs.slides))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "assets", "企业AI办公提效_样例.pptx")
    build(out)
