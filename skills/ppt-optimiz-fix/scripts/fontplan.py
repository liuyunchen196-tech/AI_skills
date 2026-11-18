# -*- coding: utf-8 -*-
"""字体规划引擎（通用版）：按位置 + 字号推断角色，真正通用、不依赖关键词。

设计目标
--------
旧版引擎要求用户在规划文件里为每个角色填写「关键词 match」才能命中对应文本框，
对陌生 PPT 极不友好（必须事先知道稿子里有哪些词）。本引擎改为**结构性推断**：

  · 位置维度（版面区域 zone）：footer 底部 15% / kicker 顶部 15% / body 其余；
  · 位置维度（页序 slide）：first 封面 / content 非封面 / any 任意；
  · 字号维度（标题带内最大 size）：largest 本页【标题带(顶部 30%)】内最大字号；
       ——只在标题带内取最大，避免底部大号装饰数字/统计数字抢占「标题」角色；
  · 页码维度（pagenum）：纯数字且位于页脚/页眉角的 run（真正的页码，不是步骤号）；
  · 可选关键词（when.match）：仅当某角色无法用位置/字号区分时作高级覆盖。

每个 run 按 rules 顺序匹配**首个同时满足所有指定维度的规则**，再套用
字号/字重/字色/字体。默认规划可完全不含关键词，做到「拿来即用」。

安全性约定（默认即非破坏性）
  · 引擎只套用规则里**显式给出**的字段；规则不写 size，就不改字号。
  · 默认规划的 Body 角色不写 size —— 保留稿内原有的正文字号层级，
    只统一字族/字色；标题/页脚/章节标签等「高置信角色」才强制字号。
  · 因此即使某页推断不完美，也不会把大号装饰数字压成 15pt、把标题压成小字。

本模块是单一事实源：fix_pptx.py（mutate=True 套用）与 inspect_pptx.py
（mutate=False 预览角色分布）都复用 classify_all，二者永不分歧。
"""
import json
import os
import re

from pptx import Presentation
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn

EMU = 914400.0
TITLE_BAND = 0.30  # 顶部 30% 视为「标题带」，标题/封面主标在此区域内取最大字号


def load_plan(path):
    """读取规划 JSON，返回 rules 列表（兼容 [..] 与 {"rules":[..]} 两种写法）。"""
    with open(path, "r", encoding="utf-8") as f:
        plan = json.load(f)
    if isinstance(plan, dict):
        return plan.get("rules", [])
    if isinstance(plan, list):
        return plan
    return []


def zone_of(sh, SW, SH):
    """版面区域：footer(底部15%) / kicker(顶部15%) / body(其余)。"""
    if sh.left is None or sh.top is None:
        return "body"
    T = sh.top / EMU
    if T >= 0.85 * SH:
        return "footer"
    if T <= 0.15 * SH:
        return "kicker"
    return "body"


def in_title_band(sh, SH):
    """run 所属形状是否落在顶部标题带（顶部 30%）内。"""
    if sh.top is None:
        return False
    return (sh.top / EMU) <= TITLE_BAND * SH


def match_rule(run, idx, zone, in_top, smax, smin, rules):
    """返回首个命中该 run 的规则；无命中返回 None。

    维度（仅在规则里显式给出时才约束，未给则视为 any）：
      when.slide   : "first" | "content" | "any"
      when.zone    : "footer" | "kicker" | "body" | "any"
      when.size    : "largest"(标题带内最大) | "smallest"(全页最小) | "body" | "any"
      when.pagenum : true  → run 为纯 1-3 位数字且位于页脚/页眉角（真实页码）
      when.match   : 关键词字符串（可选，run 文本包含即命中）
    """
    rsz = run.font.size.pt if run.font.size else None
    for rule in rules:
        when = rule.get("when", {})
        sc = when.get("slide", "any")
        if sc == "first" and idx != 1:
            continue
        if sc == "content" and idx == 1:
            continue
        zc = when.get("zone", "any")
        if zc != "any" and zc != zone:
            continue
        if when.get("pagenum") is True:
            if not re.fullmatch(r"\d{1,3}", (run.text or "").strip()):
                continue
            if zone not in ("footer", "kicker"):
                continue
        src = when.get("size", "any")
        if src != "any":
            if rsz is None:
                continue
            if src == "largest" and (not in_top or rsz != smax):
                continue
            if src == "smallest" and rsz != smin:
                continue
            if src == "body" and (rsz == smax or rsz == smin):
                continue
        kw = when.get("match")
        if kw and kw not in (run.text or ""):
            continue
        return rule
    return None


def set_run_font(run, name):
    """统一 run 字体：同时写 latin + ea（中文走 ea），避免中文缺字/混搭。"""
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", name)


def apply_rule_to_run(run, rule):
    """按规则套用字号/字重/字色/字体（仅套用规则里给出的字段）。"""
    if rule.get("size"):
        run.font.size = Pt(float(rule["size"]))
    if "bold" in rule:
        run.font.bold = bool(rule["bold"])
    if rule.get("name"):
        set_run_font(run, rule["name"])
    if rule.get("color"):
        hx = rule["color"].lstrip("#")
        run.font.color.rgb = RGBColor(int(hx[0:2], 16),
                                      int(hx[2:4], 16),
                                      int(hx[4:6], 16))


def classify_all(prs, rules, mutate=False):
    """遍历全篇 run，按位置/字号匹配角色。

    mutate=True  → 真正套用字号/字重/字色/字体（供 fix_pptx.py 使用）；
    mutate=False → 仅统计每个 run 会落入哪个角色（供 inspect_pptx.py 预览）。
    返回 {role: 命中的 run 数}。
    """
    SW = prs.slide_width / EMU
    SH = prs.slide_height / EMU
    counter = {}
    for i, sl in enumerate(prs.slides, 1):
        # 全页字号（用于 smallest）
        all_sizes = [r.font.size.pt
                     for sh in sl.shapes if sh.has_text_frame
                     for p in sh.text_frame.paragraphs for r in p.runs
                     if r.font.size]
        # 标题带内字号（用于 largest，避免底部大装饰数字抢占标题）
        top_sizes = [r.font.size.pt
                     for sh in sl.shapes if sh.has_text_frame and in_title_band(sh, SH)
                     for p in sh.text_frame.paragraphs for r in p.runs
                     if r.font.size]
        smax = max(top_sizes) if top_sizes else (max(all_sizes) if all_sizes else None)
        smin = min(all_sizes) if all_sizes else None
        for sh in sl.shapes:
            if not sh.has_text_frame:
                continue
            zone = zone_of(sh, SW, SH)
            itb = in_title_band(sh, SH)
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    rule = match_rule(r, i, zone, itb, smax, smin, rules)
                    if rule:
                        if mutate:
                            apply_rule_to_run(r, rule)
                        role = rule.get("role", "?")
                        counter[role] = counter.get(role, 0) + 1
    return counter


# 便捷别名
def apply_plan(prs, rules):
    """套用规划（mutate=True 的语义别名）。"""
    return classify_all(prs, rules, mutate=True)


def preview_roles(prs, rules):
    """预览角色分布（mutate=False 的语义别名）。"""
    return classify_all(prs, rules, mutate=False)
