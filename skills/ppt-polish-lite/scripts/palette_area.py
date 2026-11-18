#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
色彩面积体检：算清「色彩到底占多大版面」，并按色彩纪律给出判定。

用法:
    python palette_area.py <pptx路径> [--json 输出文件] [--quiet]

为什么需要它
    audit.py 只数「用了哪些色」，数不出「色用了多大面积」。
    而 AI 味的真正来源常常不是色多，是**浓色拿去做版面、浅色沦为点缀**。
    配色克制与否看两个**互相独立**的维度：
      (1) 色相种数   →  花不花
      (2) 浓淡面积比 →  重不重
    本脚本算的是 (2)。

色彩分档（只按饱和度 S 分，不看亮度高低）
    S ≤ 0.04                中性（白 / 灰 / 黑）
    0.04 < S ≤ 0.15         极浅染色（近白底）
    0.15 < S ≤ 0.45         浅色底        ← 铺底主力，该占大头
    S > 0.45                浓色          ← 该只做点睛
      └ 其中 V < 0.85 记「深色」（navy 类）；V ≥ 0.85 记「鲜色」（亮蓝类）

    ⚠ 常见误判：把「近白」判成「高亮度」是错的。近白的特征是**饱和度低**，
    不是亮度高 —— 纯蓝 #1677FF 的 V=1.0 却浓得很，按 V 上限筛会被整片漏掉。
    所以本脚本对浓色**不设 V 上限**。

色彩纪律（经验阈值，校准样本：一份 38 页实战课件 + 高手稿对比）
    单页浓色面积      ≤ 15%      （> 15% 记「浓墨重彩」）
    单页深色面积      ≤ 6%       （> 6% 记「深色块」）
    浓色 / 浅色底     ≤ 0.5      （比值高 = 浓色在承担版面，该让浅色铺底）
    全册浓色均值      ≤ 8%
    → 深色只留给**文字 / 细线 / 小方点**。**文字色不计面积**，
      所以「深色只给字」在数字上就等于深色面积≈0，这条纪律可量化、不用靠感觉争。

局限（务必知道）
    只统计**自动图形的实心填充**。以下三类测不到，需配合 render.py 目视复核：
      (1) 图片 / 矢量图形承载的画面（脚本会单独报「图片面积」提示）
      (2) 渐变填充（脚本单独列出；渐变面积无法用一个色值代表）
      (3) 主题色 / 样式继承来的填充
"""
import sys, os, io, json
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

EMU_PX = 9525.0
NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

NEUTRAL_MAX = 0.04      # ≤ 中性
PALE_MAX = 0.15         # 极浅染色上界
TINT_MAX = 0.45         # 浅色底上界；> 即浓色
DEEP_V = 0.85           # 浓色里 V < 此值记「深色」

LIM_PAGE_VIVID = 15.0   # 单页浓色红线 %
LIM_PAGE_DEEP = 6.0     # 单页深色红线 %
LIM_RATIO = 0.5         # 浓色 / 浅色底 上限
LIM_AVG_VIVID = 8.0     # 全册浓色均值上限 %
BLOCK_MIN_PCT = 1.0     # 单形状占一页版面 ≥ 此值才算「色块」（否则算小色标，不计入复用统计）

NAMES = ["红0-30", "橙30-60", "黄60-90", "黄绿90-120", "绿120-150", "青绿150-180",
         "青180-210", "蓝210-240", "蓝紫240-270", "紫270-300", "品红300-330", "粉红330-360"]


def rgb_to_hsv(r, g, b):
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    v = mx
    s = 0.0 if mx == 0 else d / mx
    if d == 0:
        h = 0.0
    elif mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60, s, v


def band(s, v):
    if s <= NEUTRAL_MAX:
        return "neutral"
    if s <= PALE_MAX:
        return "pale"
    if s <= TINT_MAX:
        return "tint"
    return "deep" if v < DEEP_V else "vivid"


def solid_fill(sh):
    """(RGBColor, alpha%) —— 非实心填充返回 (None, None)"""
    try:
        f = sh.fill
        if f.type is None or int(f.type) != 1:
            return None, None
        rgb = f.fore_color.rgb
    except Exception:
        return None, None
    alpha = 100.0
    try:
        for a in sh._element.spPr.iter("{%s}alpha" % NS):
            v = a.get("val")
            if v is not None:
                alpha = int(v) / 1000.0
                break
    except Exception:
        pass
    return rgb, alpha


def fill_kind(sh):
    try:
        t = sh.fill.type
        if t is None:
            return "none"
        return {0: "none", 1: "solid", 2: "picture", 3: "gradient",
                4: "pattern", 5: "textured"}.get(int(t), "other")
    except Exception:
        return "none"


def prst_of(sh):
    try:
        g = sh._element.spPr.find("{%s}prstGeom" % NS)
        if g is not None:
            return g.get("prst")
    except Exception:
        pass
    return None


def is_group(sh):
    return str(getattr(sh, "shape_type", "")).endswith("GROUP (6)") or \
        str(getattr(sh, "shape_type", "")).find("GROUP") >= 0


def grad_mean(sh):
    """渐变的色阶均值 RGB。渐变不能只报「有/无」——大面积渐变往往就是浓色块本身，
       排除掉会让面积统计严重偏低（实测某 deck 浓色被少算到 1/17）。"""
    try:
        g = sh._element.spPr.find("{%s}gradFill" % NS)
        if g is None:
            return None
        cs = []
        for gs in g.iter("{%s}gs" % NS):
            c = gs.find("{%s}srgbClr" % NS)
            if c is not None and c.get("val"):
                v = c.get("val")
                cs.append((int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)))
        if not cs:
            return None
        return tuple(sum(c[i] for c in cs) // len(cs) for i in range(3))
    except Exception:
        return None


def custgeom_frac(sh):
    """自定义路径图形：返回**实际绘制范围**占形状包围盒的面积比例 (0–1]。

    ⚠ 这是本脚本最容易算错的地方，务必按路径算、不能按包围盒算。
    实测案例：某引擎把卡片边框导出成 custGeom —— 包围盒 558x249px，
    可路径点只覆盖顶部 10px（一根细线）。按包围盒算面积会把一根线
    当成整张卡，面积虚高 25 倍。凡 custGeom 一律走本函数。
    """
    try:
        sp = sh._element.spPr
        cg = sp.find("{%s}custGeom" % NS)
        if cg is None:
            return 1.0
        tot = 0.0
        for path in cg.iter("{%s}path" % NS):
            try:
                pw, ph = float(path.get("w")), float(path.get("h"))
            except (TypeError, ValueError):
                continue
            if pw <= 0 or ph <= 0:
                continue
            xs, ys = [], []
            for pt in path.iter("{%s}pt" % NS):
                try:
                    xs.append(float(pt.get("x")))
                    ys.append(float(pt.get("y")))
                except (TypeError, ValueError):
                    pass
            if not xs:
                continue
            tot += ((max(xs) - min(xs)) / pw) * ((max(ys) - min(ys)) / ph)
        return min(1.0, tot) if tot > 0 else 1.0
    except Exception:
        return 1.0


def size_bucket(n, step=8):
    """把尺寸归到 step 的整倍数，容忍同一组件在不同页的 1–2px 抖动。"""
    try:
        return int(round(float(n) / step)) * step
    except (TypeError, ValueError):
        return 0


def hexof(rgb):
    return "#%02X%02X%02X" % (rgb[0], rgb[1], rgb[2])


def run(path, quiet=False, as_json=None):
    from pptx import Presentation

    prs = Presentation(path)
    PW, PH = prs.slide_width / EMU_PX, prs.slide_height / EMU_PX
    TOTAL = PW * PH

    pages, hue_area = [], Counter()
    fills, prst = Counter(), Counter()
    grads, alphas = [], []
    repeat = {}      # (fill, w桶, h桶) → {"pages": set, "area": 合计, "n": 出现次数}
    by_fill = {}     # fill → 同上；忽略尺寸，用于识别「同一个色在不同页反复当色块用」
    grad_repeat = {}
    grad_by_fill = {}

    def walk(shapes, acc, sidx):
        for sh in shapes:
            try:
                x, y = sh.left / EMU_PX, sh.top / EMU_PX
                w, h = sh.width / EMU_PX, sh.height / EMU_PX
            except Exception:
                x = y = w = h = 0
            x0, x1 = max(0.0, x), min(PW, x + w)
            y0, y1 = max(0.0, y), min(PH, y + h)
            area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
            cf = custgeom_frac(sh)
            if cf < 1.0:
                area *= cf
                acc["cg_shapes"] += 1

            p = prst_of(sh)
            if p:
                prst[p] += 1

            k = fill_kind(sh)
            rgb = None
            alpha = None
            if k == "gradient":
                gm = grad_mean(sh)
                gh = hexof(gm) if gm else "?"
                grads.append({"page": sidx, "w": round(w), "h": round(h),
                              "area": round(area / TOTAL * 100, 2),
                              "mean": gh if gm else None,
                              "text": (sh.text_frame.text[:30] if sh.has_text_frame else "")})
                if area / TOTAL * 100 >= BLOCK_MIN_PCT:
                    gk = (gh, size_bucket(w), size_bucket(h))
                    gr = grad_repeat.setdefault(gk, {"pages": set(), "area": 0.0, "n": 0,
                                                     "text": (sh.text_frame.text[:26]
                                                              if sh.has_text_frame else "")})
                    gr["pages"].add(sidx)
                    gr["area"] += area
                    gr["n"] += 1
                    gbf = grad_by_fill.setdefault(gh, {"pages": set(), "area": 0.0, "n": 0,
                                                       "sizes": Counter(),
                                                       "text": (sh.text_frame.text[:26]
                                                                if sh.has_text_frame else "")})
                    gbf["pages"].add(sidx)
                    gbf["area"] += area
                    gbf["n"] += 1
                    gbf["sizes"][(size_bucket(w), size_bucket(h))] += 1
                if gm is not None:
                    rgb, alpha = gm, 100.0     # 渐变按色阶均值参与分档
                acc["grad"] += area
            elif k == "picture":
                acc["pic"] += area
                continue
            else:
                rgb, alpha = solid_fill(sh)
            if alpha is not None and alpha < 99:
                alphas.append({"page": sidx, "alpha": alpha, "w": round(w)})
            if rgb is not None:
                hh, s, v = rgb_to_hsv(rgb[0], rgb[1], rgb[2])
                b = band(s, v)
                acc[b] += area
                if b in ("deep", "vivid"):
                    acc["warm"][str(rgb).upper()] = acc["warm"].get(str(rgb).upper(), 0) + area
                    acc["items"].append({"w": round(w), "h": round(h), "band": b,
                                         "fill": str(rgb).upper(), "s": round(s, 2),
                                         "v": round(v, 2),
                                         "pct": round(area / TOTAL * 100, 2),
                                         "text": (sh.text_frame.text[:22]
                                                  if sh.has_text_frame else "")})
                    # 记录「同色」/「同色同尺寸」的**填充块**（≥1% 版面才算块，
                    # 否则 8x32 的文字竖条之类的小色标会淹掉真正的规则信号）
                    if k != "gradient" and area / TOTAL * 100 >= BLOCK_MIN_PCT:
                        fh = hexof(rgb)
                        rk = (fh, size_bucket(w), size_bucket(h))
                        r = repeat.setdefault(rk, {"pages": set(), "area": 0.0, "n": 0,
                                                   "text": (sh.text_frame.text[:26]
                                                            if sh.has_text_frame else "")})
                        r["pages"].add(sidx)
                        r["area"] += area
                        r["n"] += 1
                        bf = by_fill.setdefault(fh, {"pages": set(), "area": 0.0, "n": 0,
                                                     "sizes": Counter(),
                                                     "text": (sh.text_frame.text[:26]
                                                              if sh.has_text_frame else "")})
                        bf["pages"].add(sidx)
                        bf["area"] += area
                        bf["n"] += 1
                        bf["sizes"][(size_bucket(w), size_bucket(h))] += 1
                    hue_area[int(hh // 30)] += area
                    acc["hue_set"].add(int(hh // 30))
                elif b in ("tint", "pale"):
                    fills[str(rgb).upper()] += 1

            if is_group(sh):
                try:
                    walk(sh.shapes, acc, sidx)
                except Exception:
                    pass

    for i, s in enumerate(prs.slides):
        acc = {"neutral": 0.0, "pale": 0.0, "tint": 0.0, "deep": 0.0, "vivid": 0.0,
               "pic": 0.0, "grad": 0.0, "items": [], "hue_set": set(),
               "warm": {}, "cg_shapes": 0}
        walk(s.shapes, acc, i + 1)
        pc = lambda k: acc[k] / TOTAL * 100
        pages.append({"page": i + 1, "neutral": pc("neutral"), "pale": pc("pale"),
                      "tint": pc("tint"), "deep": pc("deep"), "vivid": pc("vivid"),
                      "pic": pc("pic"), "grad": pc("grad"), "hues": len(acc["hue_set"]),
                      "cg": acc["cg_shapes"],
                      "items": sorted(acc["items"], key=lambda d: -d["pct"])[:5]})

    n = len(pages)
    avg = lambda k: sum(p[k] for p in pages) / n if n else 0
    vivid_tot = avg("vivid") + avg("deep")
    tint_tot = avg("tint") + avg("pale")
    ratio = vivid_tot / tint_tot if tint_tot else 0

    if quiet:
        return pages, {"vivid": vivid_tot, "tint": tint_tot, "ratio": ratio}

    print(f"文件: {os.path.basename(path)}")
    print(f"页面: {PW:.0f} x {PH:.0f} px   页数: {n}\n")

    print("=== 全册色彩结构（按面积）===")
    print(f"  中性(白灰黑)   {avg('neutral'):5.1f}%")
    print(f"  浅色           {tint_tot:5.1f}%   ┐ 铺底主力，该占大头")
    print(f"      其中极浅染色 {avg('pale'):5.1f}% / 明显浅色 {avg('tint'):5.1f}%")
    gv = sum(p["grad"] for p in pages) / n if n else 0
    print(f"  浓色           {vivid_tot:5.1f}%   ┘ 其中深色 {avg('deep'):.1f}% / "
          f"鲜色 {avg('vivid'):.1f}%（含渐变 {gv:.1f}%，已按色阶均值计入）")
    print(f"  图片承载       {avg('pic'):5.1f}%   ← 形状口径测不到，需目视复核")
    cg_n = sum(p["cg"] for p in pages)
    if cg_n:
        print(f"  自定义路径图形 {cg_n:5d} 个   ← 已按路径实算，未按包围盒（见 custgeom_frac）")
    print("  （中性含形状重叠，可能 >100%，只看浓/浅两栏即可）")

    print("\n=== 判定 ===")
    def verdict(name, val, lim, unit="%"):
        ok = val <= lim
        print(f"  {name:<16} {val:5.1f}{unit}   上限 {lim}{unit}   {'OK' if ok else '**超标**'}")
        return ok
    v1 = verdict("全册浓色均值", vivid_tot, LIM_AVG_VIVID)
    print(f"  {'浓色/浅色底':<15} {ratio:5.2f}    上限 {LIM_RATIO}      "
          f"{'OK' if ratio <= LIM_RATIO else '**浓色偏多**'}")
    bad = [p for p in pages if p["vivid"] + p["deep"] > LIM_PAGE_VIVID]
    print(f"  单页浓色超 {LIM_PAGE_VIVID}%     共 {len(bad)} 页"
          + ("  → " + ", ".join("P%02d" % p['page'] for p in bad) if bad else ""))

    print("\n=== 逐页（浓色面积降序，前 15）===")
    for p in sorted(pages, key=lambda x: -(x["vivid"] + x["deep"]))[:15]:
        vt = p["vivid"] + p["deep"]
        tag = "  浓墨重彩" if vt > LIM_PAGE_VIVID else ("  深色块" if p["deep"] > LIM_PAGE_DEEP else "")
        if p["pic"] > 40:
            tag += "（画面多为图片，口径不全）"
        print(f"  P{p['page']:02d}  浓 {vt:5.1f}% (深{p['deep']:4.1f} 鲜{p['vivid']:4.1f})  "
              f"浅 {p['tint']+p['pale']:5.1f}%  色相 {p['hues']}{tag}")
        for it in p["items"]:
            if it["pct"] >= 1.5:
                print(f"        - {it['w']}x{it['h']}px #{it['fill']} S{it['s']} V{it['v']} "
                      f"占 {it['pct']}%  '{it['text']}'")

    def rep_line(fill, v, kind=""):
        ps = sorted(v["pages"])
        shown = ", ".join("P%02d" % x for x in ps[:9]) + (" …" if len(ps) > 9 else "")
        sz = "／".join("%dx%d" % s for s, _ in v["sizes"].most_common(2))
        return (f"  {fill:<9} {kind}覆盖 {len(ps):2d} 页（{shown}）\n"
                f"            共 {v['n']} 处，主尺寸 {sz}px，跨全册累计 {v['area'] / TOTAL * 100:5.1f}%"
                f"（页均 {v['area'] / TOTAL * 100 / n:4.1f}%）  '{v['text']}'")

    fill_reps = sorted([kv for kv in list(grad_by_fill.items()) + list(by_fill.items())
                        if len(kv[1]["pages"]) >= 3], key=lambda kv: -len(kv[1]["pages"]))
    grad_fills = {k for k in grad_by_fill}

    print("\n=== 复用色块（同一个色被当成填充块，出现在 ≥3 页）★ ===")
    if fill_reps:
        print("  ⚠ 这不是「某一页画错了」，而是设计系统里的一条规则在反复生效。")
        print("    按页逐个改 = 打地鼠；要改就改这条规则本身，一次改干净。")
        for fill, v in fill_reps[:8]:
            print(rep_line(fill, v, kind="[渐变] " if fill in grad_fills else ""))
    else:
        print("  无：没有哪个色被当成填充块在 ≥3 页复用（深色是逐页独立设计的）。")

    sized = sorted([kv for kv in list(grad_repeat.items()) + list(repeat.items())
                    if len(kv[1]["pages"]) >= 3], key=lambda kv: -len(kv[1]["pages"]))
    if sized:
        print("\n--- 同色且同尺寸（严格复用的同一枚组件）---")
        for (fill, w, h), v in sized[:6]:
            ps = sorted(v["pages"])
            shown = ", ".join("P%02d" % x for x in ps[:8]) + (" …" if len(ps) > 8 else "")
            print(f"  {fill:<9} {w}x{h}px × {v['n']} 处 → {len(ps)} 页（{shown}）"
                  f" 累计 {v['area'] / TOTAL * 100:4.1f}%  '{v['text']}'")

    if grads:
        ga = sum(g["area"] for g in grads)
        print(f"\n=== 渐变填充: {len(grads)} 处 ===")
        print(f"  跨 {n} 页累计 {ga:.1f}%（页均 {ga / n:.1f}%）"
              f"　→ AI 味 / 网页件强信号；大面积渐变通常就是浓色块的来源")
        for g in grads[:15]:
            print(f"  P{g['page']:02d} {g['w']}x{g['h']}px 占{g['area']:5.1f}% "
                  f"均值{g['mean']}  '{g['text']}'")
    if alphas:
        print(f"\n=== 半透明填充: {len(alphas)} 处 ===")
        for a in alphas[:10]:
            print(f"  P{a['page']:02d} alpha={a['alpha']:.0f}%  {a['w']}px")

    print("\n=== 自动图形分布（roundRect/ellipse 多为网页件）===")
    for k, v in prst.most_common(8):
        print(f"  {k:14s} x{v}")

    print("\n=== 浓色用色 TOP8（饱和 >0.45 的填充）===")
    cnt = Counter()
    for p in pages:
        for it in p["items"]:
            cnt[it["fill"]] += 1
    for k, v in cnt.most_common(8):
        print(f"  #{k}  x{v}")

    print("\n=== 色相分布（浓色按面积）===")
    tt = sum(hue_area.values()) or 1
    for k in sorted(hue_area, key=lambda x: -hue_area[x])[:6]:
        print(f"  {NAMES[k]:12s} {hue_area[k]/tt*100:5.1f}%  {'#' * int(hue_area[k]/tt*50)}")

    print("\n=== 整改方向 ===")
    if not v1:
        print("  · 浓色总量超标：把浓色填充块换成「白底 + 1px 线框 + 深色标题字」或浅色底。")
        print("    深色只留给文字 / 细线 / 小方点 —— 文字不计面积，改完数字立刻掉。")
    if ratio > LIM_RATIO:
        print("  · 浓色偏多：核对浓色的角色 —— 它该只做点睛，铺底交给浅色。")
    if tint_tot < 8:
        print("  · 浅色底偏少：铺底改用同一色相的 50–200 档浅色，不要让浓色承担版面。")
    if grads:
        print("  · 有渐变：AI 味强信号，建议删掉改纯色或浅底。")
    if bad:
        print(f"  · {len(bad)} 页浓色超线，优先整改："
              + ", ".join("P%02d(%.0f%%)" % (p['page'], p['vivid'] + p['deep']) for p in bad[:8]))

    if as_json:
        with open(as_json, "w", encoding="utf-8") as f:
            json.dump({"page_px": [PW, PH], "slides": n,
                       "avg": {k: avg(k) for k in
                               ("neutral", "pale", "tint", "deep", "vivid", "pic", "grad")},
                       "vivid_total": vivid_tot, "tint_total": tint_tot, "ratio": ratio,
                       "pages": pages, "gradients": grads, "alpha": alphas,
                       "repeat_by_fill": {k: {"pages": sorted(v["pages"]), "n": v["n"],
                                              "area_pct": round(v["area"] / TOTAL * 100, 2)}
                                          for k, v in by_fill.items()},
                       "repeat_by_fill_grad": {k: {"pages": sorted(v["pages"]), "n": v["n"],
                                                   "area_pct": round(v["area"] / TOTAL * 100, 2)}
                                               for k, v in grad_by_fill.items()},
                       "prst": prst.most_common()}, f, ensure_ascii=False, indent=1)
        print(f"\nJSON 已写入: {as_json}")

    return pages, {"vivid": vivid_tot, "tint": tint_tot, "ratio": ratio}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    j = None
    if "--json" in sys.argv:
        i = sys.argv.index("--json")
        if i + 1 < len(sys.argv):
            j = sys.argv[i + 1]
    run(sys.argv[1], quiet="--quiet" in sys.argv, as_json=j)
