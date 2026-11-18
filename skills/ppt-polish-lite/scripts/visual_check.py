#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
visual_check.py —— PPT 视检（视觉检查）模块。

设计原则（v2.7 重写）：验证分七层 —— **前五层 renderer-free、后两层需渲染 PNG**，做到"无渲染器也能交付可验证成品"。

  ① 结构完整性      completeness()      ：封面/目录/正文/过渡页/结束页 契约核对（renderer-free）
  ② 几何正确性      geometry_check()    ：越界/溢出检测（renderer-free）
  ③ 三区布局与密度  layout_check()      ：标题固定顶 / 页脚固定底 / 内容居中 + 全体正文页位置一致性
                                          + 内容区填充率（MIN_FILL=0.55）（renderer-free）
  ④ 卡片密度与比例  card_check()        ：组件级——卡片墨量比 / 高宽比，抓「瘦高空卡」（renderer-free）
  ⑤ 构图多样化      composition_check() ：构图原型分布 / 归一化熵 / 最大占比 / 图形化 / 装饰占比（renderer-free）
  ⑥ 渲染像素分析    render()+analyze()  ：渲染成图后像素级分析（按链降级；无渲染器则跳过）
  ⑦ 垂直均衡        balance_check()     ：内容区上下留白是否近似（B1/B2/B3 三判据，需渲染 PNG）

⚠️ 编号纪律：**层号只有 ①~⑦ 这一套；层内判据一律用 B1/B2/B3。**
   旧稿曾在层内判据上用 ①②③，与层号撞车，读者数不出"七层"，v2.7 起禁用。

渲染器探测链（render() 自动按序尝试，任一成功即用，全部失败→几何兜底）：
  1. slidep screenshot（editor_sdk）   —— 与构建同源，最忠实、零额外安装
  2. LibreOffice（soffice --headless）  —— 实验室/开源环境常见
  3. PowerPoint COM（win32com）         —— 装了 MS Office 的 Windows
  4. WPS COM（KWPS.Application）         —— 装了 WPS 的 Windows（最佳努力）
  5. 几何兜底：无渲染器时仅跑 ①②，报告 mode='geometry_only'，并显式声明"未做视觉亲验"

其它子命令：
  L2  tiles 子命令：切块+缩图 → 重试 Read（绕过整图过滤）
  L3  analyze 子命令：像素级确定性分析（包围盒/留白/空洞网格/主色统计）

    用法：
    # 端到端视检（推荐，七层全跑）：①完整性 + ②几何 + ③三区布局与密度 + ④卡片
    #                          + ⑤构图 + ⑥渲染像素 + ⑦垂直均衡
    python visual_check.py fullcheck <pptx> [--outdir DIR]

    # 仅渲染（产出 PNG，不做分析）
    python visual_check.py render <pptx> [--outdir DIR]

    # 单项检查（均 renderer-free）：①完整性 / ②几何 / ③三区布局与密度 / ④卡片 / ⑤构图
    python visual_check.py completeness <pptx>
    python visual_check.py geometry <pptx>
    python visual_check.py layout <pptx>
    python visual_check.py card <pptx>
    python visual_check.py composition <pptx>

    # ⑦ 垂直均衡（B1 上/下不均 · B2 上下对称地都空 · B3 块内开天窗；可复用已有 PNG 目录）
    python visual_check.py balance <pptx> [--png-dir DIR]

    # 分析已有 PNG / 切块 / 批量
    python visual_check.py analyze <png> [--quiet]
    python visual_check.py tiles <png> --out <dir>
    python visual_check.py check <dir>
"""
import glob
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

# ---- 阈值（按 1280x720 校准，其他分辨率按比例生效，因为全部用占比） ----
# 18 = 覆盖 accent_tint #F0F5FF（与白底色距 25）；再浅的近白底视作背景
BG_DIST_THRESH = 18
BLANK_COVERAGE = 0.03   # 覆盖率低于此值 → 整页空白/渲染失败（硬伤）
COLLAPSE_COVERAGE = 0.70 # 正文页偏聚时，覆盖率低于此值才判塌陷（避免误伤窄版式）
EXTREME_MARGIN = 0.40   # 正文页某侧留白超过此值 → 仅作软提示


def _content_mask(img: Image.Image):
    """返回 (mask, bg_color)。mask: 与背景差异显著的内容像素布尔阵（已缩样）。"""
    small = img.convert("RGB")
    if small.width > 640:
        ratio = 640 / small.width
        small = small.resize((640, max(1, int(small.height * ratio))))
    px = small.load()
    w, h = small.size
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    bg = tuple(sorted(c[i] for c in corners)[1] for i in range(3))  # 中位数
    mask = []
    for y in range(h):
        row = []
        for x in range(w):
            r, g, b = px[x, y]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > BG_DIST_THRESH:
                row.append(1)
            else:
                row.append(0)
        mask.append(row)
    return mask, bg, (w, h)


def analyze(png_path: str, quiet: bool = False, page_type: str | None = None) -> dict:
    """像素级确定性分析（v2.2 智能分级）。

    把「设计留白」与「真实硬伤」分开，避免对极简页/正常版式误报：
      - 极简页(cover/toc/transition/ending)：只查空白，不报警留白/空洞。
      - 硬伤 BLOCKER（判 WARN）：(a) 整页空白/渲染失败；(b) 正文页内容偏聚塌陷。
      - 软提示 ADVISORY（仅记录）：正文页某侧留白 > 40%。
    page_type=None 时按覆盖率自动推断（<12% 视为极简页）。
    """
    img = Image.open(png_path)
    mask, bg, (w, h) = _content_mask(img)

    # 1) 内容包围盒与四边留白
    col_any = [any(mask[y][x] for y in range(h)) for x in range(w)]
    row_any = [any(mask[y][x] for x in range(w)) for y in range(h)]
    try:
        left = col_any.index(True)
        right = (w - 1) - col_any[::-1].index(True)
        top = row_any.index(True)
        bottom = (h - 1) - row_any[::-1].index(True)
    except ValueError:
        report = {"png": str(png_path), "verdict": "WARN",
                  "problems": ["整页几乎无内容像素（可能渲染失败或全空页）"],
                  "bg_color": "#%02X%02X%02X" % bg}
        if not quiet:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return report
    margins = {"left": left / w, "right": (w - 1 - right) / w,
               "top": top / h, "bottom": (h - 1 - bottom) / h}

    # 2) 主色统计
    q = img.convert("RGB").resize((160, 90)).quantize(colors=8)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)[:6]
    total = 160 * 90
    dominant = [{"hex": "#%02X%02X%02X" % tuple(pal[i * 3:i * 3 + 3]),
                 "ratio": round(c / total, 3)} for c, i in counts]

    # 3) 结论：智能分级（硬伤阻断交付 / 软提示仅记录）
    cov = (right - left + 1) * (bottom - top + 1) / (w * h)
    if page_type in (None, "auto"):
        page_type = "minimalist" if cov < 0.12 else "body"
    minimalist = page_type in ("cover", "toc", "transition", "ending", "minimalist")

    problems, advisories = [], []
    if cov < BLANK_COVERAGE:
        # 硬伤 (a)：整页空白 / 渲染失败
        problems.append("整页几乎无内容（疑似空白/渲染失败）")
    elif not minimalist:
        # 硬伤 (b)：正文页内容偏聚塌陷检测
        #   bottom<0.5h → 内容全在顶部半区；top>0.5h → 内容全在底部半区
        conf_top = bottom < 0.5 * h
        conf_bottom = top > 0.5 * h
        conf_left = right < 0.5 * w
        conf_right = left > 0.5 * w
        if (conf_top or conf_bottom or conf_left or conf_right) and cov < COLLAPSE_COVERAGE:
            where = []
            if conf_top:
                where.append("顶部")
            if conf_bottom:
                where.append("底部")
            if conf_left:
                where.append("左侧")
            if conf_right:
                where.append("右侧")
            problems.append("内容偏聚于%s（疑似错位/塌陷，建议人工确认）" % "·".join(where))
        # 软提示：极端留白（仅记录，不判 WARN）
        for side, ratio in margins.items():
            if ratio > EXTREME_MARGIN:
                advisories.append("%s 边留白 %.0f%% 偏大" % (side, ratio * 100))

    verdict = "WARN" if problems else "PASS"
    report = {
        "png": str(png_path),
        "verdict": verdict,
        "page_type": page_type,
        "margins": {k: "%.1f%%" % (v * 100) for k, v in margins.items()},
        "bbox_coverage": "%.1f%%" % (cov * 100),
        "dominant_colors": dominant,
        "problems": problems,
        "advisories": advisories,
        "note": "像素级兜底分析：硬伤可信；配色/文字/美观仍需 L1 读图或用户确认",
    }
    if not quiet:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def tiles(png_path: str, out_dir: str) -> list:
    """生成衍生图供 L1 重试：上/下半、左/右半、四象限、缩小图。"""
    img = Image.open(png_path).convert("RGB")
    w, h = img.size
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(png_path).stem
    made = []
    regions = {
        "top_half": (0, 0, w, h // 2),
        "bottom_half": (0, h // 2, w, h),
        "left_half": (0, 0, w // 2, h),
        "right_half": (w // 2, 0, w, h),
        "small": None,
    }
    for name, box in regions.items():
        im = img.resize((w // 2, h)) if name == "small" else img.crop(box)
        p = out / f"{stem}_{name}.png"
        im.save(p)
        made.append(str(p))
    return made


def check_dir(d: str) -> int:
    seen = {}
    for p in list(Path(d).glob("*.png")) + list(Path(d).glob("*.PNG")):
        seen[str(p).lower()] = p   # Windows 大小写不敏感，去重
    pngs = sorted(seen.values())
    if not pngs:
        print(json.dumps({"error": f"目录无 PNG: {d}"}, ensure_ascii=False))
        return 2
    warn = 0
    for p in pngs:
        r = analyze(str(p), quiet=False)
        if r["verdict"] == "WARN":
            warn += 1
    print(json.dumps({"summary": f"{len(pngs)} 张检查完毕，{warn} 张 WARN",
                      "dir": str(d)}, ensure_ascii=False))
    return 1 if warn else 0


# =====================================================================
#  L0 渲染流水线：pptx → PDF → PNG（新增）
# =====================================================================

RENDER_SCALE = 1.6   # ~150 dpi for 13.33×7.5in → 1537×864 px


def _find_soffice() -> str | None:
    """定位 LibreOffice soffice.exe。"""
    for cand in [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]:
        if os.path.isfile(cand):
            return cand
    return shutil.which("soffice") or shutil.which("libreoffice")


def _roundtrip_normalize(pptx_path: str, out_path: str) -> bool:
    """python-pptx round-trip save 规范化 OOXML（修复 LibreOffice 不兼容问题）。"""
    try:
        from pptx import Presentation
        prs = Presentation(pptx_path)
        prs.save(out_path)
        return os.path.getsize(out_path) > 1000
    except Exception as e:
        print(f"[visual_check] round-trip 失败: {e}", file=sys.stderr)
        return False


def _convert_to_pdf(soffice: str, pptx_path: str, outdir: str) -> str | None:
    """LibreOffice headless 转换 pptx → pdf。返回 pdf 路径或 None。"""
    profile_dir = os.path.join(outdir, "_lo_profile")
    os.makedirs(profile_dir, exist_ok=True)
    # 杀残留 soffice
    try:
        subprocess.run(["taskkill", "/f", "/im", "soffice.exe"],
                       capture_output=True, timeout=10)
    except Exception:
        pass
    time.sleep(0.5)

    lo_uri = profile_dir.replace("\\", "/")
    cmd = [
        soffice, f"-env:UserInstallation=file:///{lo_uri}",
        "--headless", "--norestore", "--nofirststartwizard",
        "--convert-to", "pdf:impress_pdf_Export",
        "--outdir", outdir, pptx_path,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
        if r.returncode == 0:
            base = os.path.splitext(os.path.basename(pptx_path))[0]
            pdf = os.path.join(outdir, base + ".pdf")
            return pdf if os.path.isfile(pdf) else None
        print(f"[visual_check] LibreOffice rc={r.returncode}", file=sys.stderr)
        print(f"  stderr: {(r.stderr or '')[-500:]}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("[visual_check] LibreOffice 超时", file=sys.stderr)
    except Exception as e:
        print(f"[visual_check] LibreOffice 异常: {e}", file=sys.stderr)
    return None


def _render_pdf_pages(pdf_path: str, outdir: str, scale: float = RENDER_SCALE) -> list[str]:
    """pypdfium2 PDF → 逐页 PNG。返回 png 路径列表。"""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise RuntimeError(
            "pypdfium2 未安装（LibreOffice/PowerPoint/WPS 渲染链的 PDF→PNG 步骤需要它；"
            "pip install pypdfium2 后重试，或无渲染器时自动降级为前五层检查）")
    doc = pdfium.PdfDocument(pdf_path)
    paths = []
    for i in range(len(doc)):
        pil = doc[i].render(scale=scale).to_pil()
        p = os.path.join(outdir, f"page-{i + 1:02d}.png")
        pil.save(p)
        paths.append(p)
    return paths


# =====================================================================
#  渲染器探测链（渲染器无关）：slidep > LibreOffice > PowerPoint COM > WPS
#  任一可用即渲染；全部失败 → 几何兜底（仍可跑结构 + 几何检查）
# =====================================================================
PREFER_RENDERERS = ["slidep", "libreoffice", "powerpoint_com", "wps"]


def _get_slidep_local():
    """复用 slide_build 的 slidep 定位（避免重复实现）。"""
    try:
        sb_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "slide_build.py")
        spec = importlib.util.spec_from_file_location("slide_build", sb_path)
        sb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sb)
        return sb._get_slidep()
    except Exception:
        return None


def _pngs_in(outdir):
    """目录内的渲染页 PNG（按文件名排序）。

    ⚠️ 两个模式 `.png` / `.PNG` 是为大小写**敏感**文件系统准备的，但在 Windows 上
    文件系统大小写**不敏感**，两个 glob 会各自匹配到同一批文件 → 相加后列表翻倍。
    后果很隐蔽也很严重：列表与 `page_types` 错位，后半段全部回落为 "body"，
    于是**过渡页 / 封面被当成正文页误报**（实测 32 页 deck 报出 checked=57、
    把 4 个过渡页全报成「上下留白不均」）。必须按规范化绝对路径去重。
    """
    hits = (glob.glob(os.path.join(outdir, "page-*.png")) +
            glob.glob(os.path.join(outdir, "page-*.PNG")))
    seen, out = set(), []
    for p in hits:
        k = os.path.normcase(os.path.abspath(p))
        if k not in seen:
            seen.add(k)
            out.append(p)
    return sorted(out)


def _try_slidep(pptx_path, outdir):
    """slidep screenshot 依赖 editor_sdk 渲染服务（默认 http://localhost:39099）。
    该服务通常不后台运行，故本函数多作为「有则用之」的优先项，失败即降级。
    语法：slidep screenshot <file> --page-index <n> --out <png> [--base-url <url>]
    """
    info = _get_slidep_local()
    if not info:
        return False, [], None, "slidep 不可用"
    try:
        from pptx import Presentation
        n = len(Presentation(pptx_path).slides)
    except Exception:
        n = 0
    base_url = os.environ.get("TENCENT_DOCS_LOCAL_MCP") or "http://localhost:39099"
    pngs = []
    try:
        for i in range(n):
            out_png = os.path.join(outdir, f"page-{i + 1:02d}.png")
            r = subprocess.run(
                [info["node"], info["index_js"], "screenshot", pptx_path,
                 "--page-index", str(i), "--out", out_png, "--base-url", base_url],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            if os.path.exists(out_png):
                pngs.append(out_png)
            else:
                # 任一页失败即判定服务不可用，停止重试
                return False, [], None, f"slidep 渲染第{i}页失败（editor_sdk 可能未运行）: {(r.stderr or '')[-200:]}"
        if pngs:
            return True, pngs, None, "slidep screenshot (editor_sdk)"
        return False, [], None, "slidep 无输出"
    except Exception as e:
        return False, [], None, f"slidep: {e}"


def _try_libreoffice(pptx_path, outdir):
    try:
        soffice = _find_soffice()
        if not soffice:
            return False, [], None, "未找到 LibreOffice"
        norm = os.path.join(outdir, "_normalized.pptx")
        src = norm if _roundtrip_normalize(pptx_path, norm) else pptx_path
        pdf = _convert_to_pdf(soffice, src, outdir)
        if not pdf:
            return False, [], None, "LibreOffice 转 PDF 失败"
        pngs = _render_pdf_pages(pdf, outdir)
        return True, pngs, pdf, "LibreOffice"
    except Exception as e:
        # 缺 pypdfium2 / 转换异常等都不得穿透主循环（旧版在此裸崩，见 known-pitfalls）
        return False, [], None, f"LibreOffice: {e}"


def _try_powerpoint_com(pptx_path, outdir):
    try:
        import win32com.client  # noqa
    except ImportError:
        return False, [], None, "未安装 pywin32"
    app = None
    try:
        norm = os.path.join(outdir, "_normalized.pptx")
        src = norm if _roundtrip_normalize(pptx_path, norm) else pptx_path
        app = win32com.client.Dispatch("PowerPoint.Application")
        pres = app.Presentations.Open(os.path.abspath(src), WithWindow=False)
        pdf = os.path.join(outdir, Path(pptx_path).stem + ".pdf")
        pres.ExportAsFixedFormat(pdf, 2)  # 2 = ppFixedFormatTypePDF
        pres.Close()
        pngs = _render_pdf_pages(pdf, outdir)
        return True, pngs, pdf, "PowerPoint COM"
    except Exception as e:
        return False, [], None, f"PowerPoint COM: {e}"
    finally:
        try:
            if app:
                app.Quit()
        except Exception:
            pass


def _try_wps(pptx_path, outdir):
    """WPS COM 最佳努力；API 不稳定，失败即降级。"""
    try:
        import win32com.client  # noqa
    except ImportError:
        return False, [], None, "未安装 pywin32"
    app = None
    try:
        norm = os.path.join(outdir, "_normalized.pptx")
        src = norm if _roundtrip_normalize(pptx_path, norm) else pptx_path
        app = win32com.client.Dispatch("KWPS.Application")
        pres = app.Presentations.Open(os.path.abspath(src), WithWindow=False)
        pdf = os.path.join(outdir, Path(pptx_path).stem + ".pdf")
        pres.ExportAsFixedFormat(pdf, 2)
        pres.Close()
        pngs = _render_pdf_pages(pdf, outdir)
        return True, pngs, pdf, "WPS COM"
    except Exception as e:
        return False, [], None, f"WPS COM: {e}"
    finally:
        try:
            if app:
                app.Quit()
        except Exception:
            pass


def detect_renderers() -> list:
    """返回本机可用渲染器名称列表（按优先级）。

    注意：LibreOffice / PowerPoint COM / WPS 三条链的 PDF→PNG 都依赖 pypdfium2，
    缺它即不可用——旧版只探 soffice/pywin32 不探 pypdfium2，会把 libreoffice 误报为可用，
    实际一跑就崩（v2.1.3 修复）。
    """
    avail = []
    try:
        import pypdfium2  # noqa
        has_pdfium = True
    except ImportError:
        has_pdfium = False
    if _get_slidep_local():
        avail.append("slidep")
    if _find_soffice() and has_pdfium:
        avail.append("libreoffice")
    try:
        import win32com.client  # noqa
        if has_pdfium:
            avail.append("powerpoint_com")
            avail.append("wps")
    except ImportError:
        pass
    return avail


def render(pptx_path: str, output_dir: str | None = None) -> dict:
    """L0 渲染：按优先级链把 pptx → 逐页 PNG。

    任一渲染器成功即返回其名称；全部失败返回 mode='geometry_only'。
    Returns:
        {"ok": bool, "renderer": str|None, "pngs": [...], "pdf": path|None,
         "mode": "full_visual"|"geometry_only", "error": ...}
    """
    pptx_path = os.path.abspath(pptx_path)
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(pptx_path), "_visual_check")
    os.makedirs(output_dir, exist_ok=True)

    for name in PREFER_RENDERERS:
        try:
            if name == "slidep":
                ok, pngs, pdf, note = _try_slidep(pptx_path, output_dir)
            elif name == "libreoffice":
                ok, pngs, pdf, note = _try_libreoffice(pptx_path, output_dir)
            elif name == "powerpoint_com":
                ok, pngs, pdf, note = _try_powerpoint_com(pptx_path, output_dir)
            elif name == "wps":
                ok, pngs, pdf, note = _try_wps(pptx_path, output_dir)
            else:
                continue
        except Exception as e:
            # 防御性兜底：任一渲染器实现的未预期异常都不得中断整条链，
            # 按"该渲染器不可用"继续往下尝试，全部失败则 geometry_only 降级。
            ok, pngs, pdf, note = False, [], None, f"{name}: {e}"
        print(f"  [render] 尝试 {name}: {'OK' if ok else '× ' + note}")
        if ok:
            return {"ok": True, "renderer": name, "pngs": pngs,
                    "pdf": pdf, "mode": "full_visual", "note": note}

    return {"ok": False, "renderer": None, "pngs": [], "pdf": None,
            "mode": "geometry_only",
            "error": "无可用渲染器（slidep/LibreOffice/PowerPoint/WPS 均不可用）；仅结构+几何检查"}


# =====================================================================
#  结构完整性检查（renderer-free）与几何检查（renderer-free）
# =====================================================================

def _first_text(slide) -> str:
    for sh in slide.shapes:
        if sh.has_text_frame:
            txt = sh.text_frame.text.strip()
            if txt:
                return txt.split("\n")[0].strip()[:50]
    return ""


def _shape_desc(sh) -> str:
    name = sh.name or "shape"
    txt = ""
    if sh.has_text_frame:
        txt = sh.text_frame.text.strip().replace("\n", " ")[:20]
    return f"{name}({txt})" if txt else name


def completeness(pptx_path: str) -> dict:
    """结构完整性检查（renderer-free）：封面/目录/正文/过渡页/结束页 契约核对。"""
    from pptx import Presentation
    try:
        prs = Presentation(pptx_path)
    except Exception as e:
        return {"ok": False, "error": str(e), "total": 0, "issues": [f"无法打开: {e}"]}
    slides = list(prs.slides)
    n = len(slides)
    titles = [_first_text(s) for s in slides]
    has_cover = n >= 1
    has_toc = any(re.search(r"目录|大纲|contents|agenda|总览", t, re.I) for t in titles)
    has_ending = any(re.search(r"谢谢|感谢|结束|总结|结语|封底|q\s*&?\s*a|thank", t, re.I) for t in titles)
    transitions = []
    for i, s in enumerate(slides, 1):
        t = titles[i - 1]
        if 0 < len(t) <= 12 and len(s.shapes) <= 5:
            transitions.append(i)
    body = [i for i in range(1, n + 1) if i not in transitions and i != 1
            and not re.search(r"目录|大纲|contents|谢谢|感谢|结束|总结|结语|封底", titles[i - 1], re.I)]
    issues = []
    if not has_toc and n >= 5:
        issues.append("建议补充目录页")
    if not has_ending:
        issues.append("建议补充结束页")
    if len(body) < 2:
        issues.append("正文页数偏少，可能缺少实质内容")
    return {
        "ok": True,
        "total": n,
        "has_cover": has_cover,
        "has_toc": has_toc,
        "has_ending": has_ending,
        "body_pages": body,
        "body_count": len(body),
        "transition_pages": transitions,
        "titles": titles,
        "issues": issues,
    }


def geometry_check(pptx_path: str) -> dict:
    """几何体检（renderer-free）：越界 / 溢出检测。"""
    from pptx import Presentation
    try:
        prs = Presentation(pptx_path)
    except Exception as e:
        return {"ok": False, "error": str(e), "issues": [str(e)], "pages": []}
    SW, SH = prs.slide_width, prs.slide_height
    TOL = 20000  # EMU 容差
    per_page = []
    all_issues = []
    for i, slide in enumerate(prs.slides, 1):
        pg = []
        for sh in slide.shapes:
            try:
                if sh.left is None or sh.top is None:
                    continue
                w = sh.width or 0
                h = sh.height or 0
                if (sh.left < -TOL or sh.top < -TOL or
                        sh.left + w > SW + TOL or sh.top + h > SH + TOL):
                    pg.append(f"{_shape_desc(sh)} 越界(L={sh.left} T={sh.top} W={w} H={h})")
            except Exception:
                pass
        per_page.append({"page": i, "issues": pg})
        for x in pg:
            all_issues.append(f"P{i}: {x}")
    return {"ok": True, "total": len(per_page), "issues": all_issues, "pages": per_page}


def _page_types(comp: dict) -> list:
    """根据结构完整性结果，给每页打上类型标签（供 analyze 感知页面语义）。

    类型：cover / toc / transition / ending / body
    """
    n = comp.get("total", 0)
    titles = comp.get("titles", [])
    transitions = set(comp.get("transition_pages", []))
    toc_re = re.compile(r"目录|大纲|contents|agenda|总览", re.I)
    end_re = re.compile(r"谢谢|感谢|结束|总结|结语|封底|q\s*&?\s*a|thank", re.I)
    types = []
    for i in range(1, n + 1):
        if i == 1:
            types.append("cover")
        elif i in transitions:
            types.append("transition")
        elif i - 1 < len(titles) and toc_re.search(titles[i - 1]):
            types.append("toc")
        elif i - 1 < len(titles) and end_re.search(titles[i - 1]):
            types.append("ending")
        else:
            types.append("body")
    return types


def _shape_extent(shape):
    """返回形状的 (top, bottom) EMU；group 形状取内部极值；无坐标返回 None。"""
    try:
        from pptx.enum.shapes import MSO_SHAPE_TYPE
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            pts = []
            for sub in shape.shapes:
                e = _shape_extent(sub)
                if e:
                    pts.append(e)
            if not pts:
                return None
            return (min(p[0] for p in pts), max(p[1] for p in pts))
    except Exception:
        pass
    try:
        if shape.top is None or shape.height is None:
            return None
        return (shape.top, shape.top + shape.height)
    except Exception:
        return None


def layout_check(pptx_path: str) -> dict:
    """三区布局规范检查（renderer-free，基于 pptx 真实坐标）。

    规则（用户明确提出的版式契约）：
      标题区固定顶部 ｜ 内容区在中间并垂直居中 ｜ 页脚区固定底部；
      且【所有正文页】的标题 top、页脚 bottom 必须一致（每页都一样）。

    实现：用 python-pptx 读真实 EMU 坐标，专挑带「页码 NN / MM」的文本框
    作为正文页（封面/过渡/结束页无此页码，自动排除），再校验：
      1) 标题 top 落在顶部区（4%~22% 高度）；
      2) 页脚 bottom 落在底部区（86%~99% 高度）；
      3) 标题与页脚之间确有内容形状（内容区未塌陷）；
      4) 全体正文页标题 top 的方差 < TOL、页脚 bottom 的方差 < TOL（一致性）。
    Returns:
        {"layer","body_pages","title_top_range","footer_bottom_range","issues"}
    """
    from pptx import Presentation
    FOOTER_RE = re.compile(r"\d+\s*/\s*\d+")  # 形如 "14 / 21" 的页码
    TOL = 0.04      # 正文页标题/页脚位置允许的最大偏差（占高度比）
    MIN_FILL = 0.55 # 内容区填充率下限：低于此值判「上下留白过多」

    prs = Presentation(pptx_path)
    H = prs.slide_height or 1
    body = []
    for idx, slide in enumerate(prs.slides, 1):
        texts = [s for s in slide.shapes
                 if s.has_text_frame and s.text_frame.text.strip()
                 and s.top is not None and s.height is not None]
        footers = [s for s in texts if FOOTER_RE.search(s.text_frame.text)]
        if not footers:
            continue  # 非正文页：封面/过渡页/结束页，不参与三区一致性校验
        title_top = min(s.top for s in texts)
        fb = max((s.top + s.height) for s in footers)
        zone_h = fb - title_top
        # 内容包围盒：排除 (a) 标题区 / (b) 页脚区 / (c) 占满全区的容器盒，只量真实内容
        header_band = title_top + zone_h * 0.10
        footer_band = fb - zone_h * 0.06
        cands = []
        for s in slide.shapes:
            e = _shape_extent(s)
            if not e:
                continue
            t, b = e
            if s in footers:
                continue
            if t < header_band or b > footer_band:
                continue
            if (b - t) > 0.85 * zone_h:   # 全内容区容器，不算内容本身
                continue
            cands.append((t, b))
        if cands:
            c_top = min(t for t, _ in cands)
            c_bot = max(b for _, b in cands)
            fill = (c_bot - c_top) / zone_h
        else:
            fill = 0.0
        body.append({"page": idx,
                     "title_top": title_top / H,
                     "footer_bottom": fb / H,
                     "fill": round(fill, 3)})

    issues = []
    if not body:
        issues.append("未识别到带页码的正文页（三区布局无可校验对象）")
        return {"layer": "layout_3zone", "body_pages": 0,
                "title_top_range": None, "footer_bottom_range": None,
                "fill_ratios": [], "issues": issues}

    tt = [r["title_top"] for r in body]
    fb_ = [r["footer_bottom"] for r in body]
    fills = [r["fill"] for r in body]
    for r in body:
        if not (0.04 <= r["title_top"] <= 0.22):
            issues.append(f"第{r['page']}页标题 top={r['title_top']:.0%} 不在顶部区(4%~22%)")
        if not (0.86 <= r["footer_bottom"] <= 0.99):
            issues.append(f"第{r['page']}页页脚 bottom={r['footer_bottom']:.0%} 不在底部区(86%~99%)")
        if r["fill"] == 0.0:
            issues.append(f"第{r['page']}页标题与页脚之间无内容形状（内容区塌陷/错乱）")
        elif r["fill"] < MIN_FILL:
            issues.append(
                f"第{r['page']}页内容区填充率仅 {r['fill']:.0%}（阈值 {MIN_FILL:.0%}），"
                f"上下留白过多 → 应调整信息组织方式（放大字号/增加间距/改用网格填满内容区）")
    tt_var = max(tt) - min(tt)
    fb_var = max(fb_) - min(fb_)
    if tt_var > TOL:
        issues.append(f"正文页标题 top 不一致：{min(tt):.0%}~{max(tt):.0%}（偏差 {tt_var:.0%} > {TOL:.0%}），标题区未固定")
    if fb_var > TOL:
        issues.append(f"正文页页脚 bottom 不一致：{min(fb_):.0%}~{max(fb_):.0%}（偏差 {fb_var:.0%} > {TOL:.0%}），页脚区未固定")

    return {"layer": "layout_3zone", "body_pages": len(body),
            "title_top_range": [round(min(tt), 3), round(max(tt), 3)],
            "footer_bottom_range": [round(min(fb_), 3), round(max(fb_), 3)],
            "fill_ratios": fills, "min_fill": round(min(fills), 3),
            "issues": issues}


def card_check(pptx_path: str) -> dict:
    """组件级（卡片）密度与比例检查（renderer-free，基于 pptx 真实坐标）。

    用户提出的痛点：一整页被「拉伸成等高高卡、但卡内内容极稀疏」的卡片占满，
    看起来就是一排「瘦高空卡」。页面级填充率会被「卡片拉伸填满内容区」骗过，
    必须在**组件级**定义规则才能抓出来。

    规则：对每页里所有「卡片」（实心填充矩形 + 内部含文字/图片子形状）计算：
      ink_ratio = 卡内所有内容形状高度之和 / 卡片自身高度   （卡内真实墨量占比）
      aspect   = 卡片高度 / 卡片宽度                       （高宽比，扁<1<瘦高）
    触发 WARN 的条件（任一）：
      A) ink_ratio < INK_MIN(0.40) 且 aspect > 1.2  → 高卡但内部墨量过低（瘦高空卡）
      B) aspect > ASPECT_MAX(1.8)                    → 无论墨量，比例已失调
    排除：全幅背景板（占满整页的实心矩形）、无文字的小图标圆底。
    Returns:
        {"layer","cards":[{page,ink_ratio,aspect,flag}],"issues":[...]}
    """
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    INK_MIN = 0.40       # 卡片内部墨量占比下限
    ASPECT_MAX = 1.8     # 卡片高宽比上限（超过即偏瘦高）
    MIN_W = 0.09         # 候选卡片最小宽（占页宽比），过滤小图标圆底
    MIN_H = 0.10         # 候选卡片最小高（占页高比）
    EPS = 12000          # 容差 EMU（约 0.013in），判定"子形状在卡内"

    prs = Presentation(pptx_path)
    SW, SH = prs.slide_width, prs.slide_height
    cards = []
    issues = []
    for idx, slide in enumerate(prs.slides, 1):
        shapes = list(slide.shapes)
        # --- 1) 候选卡片：实心 AUTO_SHAPE，较大，且内部含有文字 ---
        cands = []
        for sh in shapes:
            try:
                if sh.shape_type != MSO_SHAPE_TYPE.AUTO_SHAPE:
                    continue
                if sh.fill.type != 1:  # 1=MSO_FILL.SOLID
                    continue
            except Exception:
                continue
            if sh.top is None or sh.height is None or sh.width is None or sh.left is None:
                continue
            # 排除全幅背景板
            if sh.width >= 0.95 * SW and sh.height >= 0.95 * SH:
                continue
            if sh.width < MIN_W * SW or sh.height < MIN_H * SH:
                continue
            cx = sh.left + sh.width / 2
            cy = sh.top + sh.height / 2
            has_text_inside = False
            for o in shapes:
                if o is sh or not (o.has_text_frame and o.text_frame.text.strip()):
                    continue
                if o.top is None or o.height is None or o.left is None:
                    continue
                ox = o.left + o.width / 2
                oy = o.top + o.height / 2
                if (sh.left - EPS <= ox <= sh.left + sh.width + EPS and
                        sh.top - EPS <= oy <= sh.top + sh.height + EPS):
                    has_text_inside = True
                    break
            if not has_text_inside:
                continue
            cands.append(sh)
        # --- 2) 计算每张卡的墨量与比例 ---
        for card in cands:
            ink_h = 0.0
            for o in shapes:
                if o is card:
                    continue
                if o.top is None or o.height is None or o.left is None:
                    continue
                ox = o.left + o.width / 2
                oy = o.top + o.height / 2
                inside = (card.left - EPS <= ox <= card.left + card.width + EPS and
                          card.top - EPS <= oy <= card.top + card.height + EPS)
                if inside and ((o.has_text_frame and o.text_frame.text.strip()) or
                               o.shape_type == MSO_SHAPE_TYPE.PICTURE):
                    ink_h += o.height
            ink_ratio = ink_h / card.height if card.height else 0.0
            aspect = card.height / card.width if card.width else 0.0
            flag = (ink_ratio < INK_MIN and aspect > 1.2) or (aspect > ASPECT_MAX)
            cards.append({"page": idx,
                          "ink_ratio": round(ink_ratio, 3),
                          "aspect": round(aspect, 3),
                          "flag": flag})
            if flag:
                issues.append(
                    f"第{idx}页 卡片(高宽比{aspect:.2f}, 卡内墨量{ink_ratio:.0%}) 瘦高/内部稀疏 "
                    f"→ 建议改为 2×2 网格或按内容收矮卡片、放大卡内字号间距")
    return {"layer": "card_density", "card_count": len(cards),
            "flagged": sum(1 for c in cards if c["flag"]),
            "cards": cards, "issues": issues}


def composition_check(pptx_path: str) -> dict:
    """第6层：构图多样化 + 图形化表达 + 装饰占比检查（renderer-free，基于 pptx 真实形状）。

    用户痛点：
      (a) 整篇内容组织与构图过于单一 → 视觉疲劳，不像人写的；
      (b) 图形化表达不足（架构图 / 流程图 / 代码块 / 对比表 / 多边形图示缺席）；
      (c) 装饰图片比例失控：过多会拉低统一风格，缺位则留白空洞。

    实现：
      1) 用 completeness 区分【正文页】（排除封面/目录/过渡/结束页，以及极简分隔页）。
      2) 提取形状特征（矢量图/位图/卡/连接线/箭头/真表格/深色代码块），归一为构图原型。
         矢量图与位图的区分：slidep 的 `<svg>` 落为 PICTURE 但**取不到内嵌 blob**。
      3) 统计原型占比 → 归一化香农熵 H 与最大占比 max_share。
      4) 三项量化判定：
         - 构图多样性：max_share > 0.40 或 H < 0.55 → WARN（视觉疲劳）
         - 图形化覆盖率 graphic_ratio < 0.80 → WARN（仍有正文页是纯文字）
         - 装饰占比 decor_ratio > 0.25 → WARN（装饰喧宾夺主，拉低统一风格）

    原型（archetype）清单：
        data_table / code_block / layout_gallery / wide_diagram / step_band /
        radial_board / vector_diagram / layered_stack / image_showcase /
        image_annotated / comparison_table / two_column / card_grid /
        card_row / flow_process / text_only / mixed / decor_diagram
        （decor_diagram = 无卡无图，但有无底装饰/连线结构：细弧、药丸、tint 柱、
        渐变圆、细长连线等「画出像素的 autoshape」，此前被误判为 text_only）

    Returns:
        {"layer","body_pages","archetypes":{name:count},"distinct","entropy",
         "max_share","graphic_ratio","decor_ratio","decor_pages",
         "text_only_pages":[...],"detail":[...],"issues":[...]}
    """
    import math
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    MAX_SHARE = 0.40    # 单一构图占比上限（超过即判单调）
    ENTROPY_MIN = 0.55  # 归一化熵下限（低于即多样性不足）
    GRAPHIC_MIN = 0.40  # 图形化覆盖率下限（低于即"满是文字+卡片，缺图形表达"）
    DECOR_MAX = 0.25    # 装饰图形总面积占内容区上限
    DECOR_UNIT = 0.08   # 单张图形面积 < 8% 页面积 → 视为装饰（而非内容主图）
    MIN_W = 0.05        # 候选卡片最小宽（占页宽比）
    MIN_H = 0.05        # 候选卡片最小高（占页高比）
    EPS = 12000         # 容差 EMU，判定"子形状在卡内"
    # 连接器类型在 python-pptx 中不属于 MSO_SHAPE_TYPE，按名字安全取用（取不到则置 None）
    CONNECTOR = getattr(MSO_SHAPE_TYPE, "CONNECTOR", None)

    prs = Presentation(pptx_path)
    SW, SH = prs.slide_width, prs.slide_height
    CONTENT_W = SW * 0.90   # 内容区宽（左右各 ~5% 边距）
    CONTENT_H = SH * 0.74   # 内容区高（标题区 + 页脚约占 26%）
    comp = completeness(pptx_path)
    body = set(comp.get("body_pages", []))

    def _is_solid_auto(sh):
        """实心 AUTO_SHAPE（1 = MSO_FILL.SOLID）。"""
        try:
            return sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and sh.fill.type == 1
        except Exception:
            return False

    def _is_full_bg(sh):
        try:
            return sh.width >= 0.95 * SW and sh.height >= 0.95 * SH
        except Exception:
            return False

    def _is_dark(sh):
        """深色填充（用于识别 CodeBlock 底色块）。"""
        try:
            if sh.fill.type != 1:
                return False
            c = sh.fill.fore_color.rgb
            return (0.299 * int(c[0]) + 0.587 * int(c[1]) + 0.114 * int(c[2])) < 90
        except Exception:
            return False

    def _pics(slide):
        """返回 (矢量图形列表, 位图列表)。

        矢量 = slidep 由 `<svg>` 渲染出的 PICTURE，python-pptx 取不到内嵌 blob；
        位图 = 普通照片/截图，能取到 blob。
        """
        vec, ras = [], []
        for sh in slide.shapes:
            if sh.shape_type != MSO_SHAPE_TYPE.PICTURE:
                continue
            try:
                sh.image.blob
                ras.append(sh)
            except Exception:
                vec.append(sh)
        return vec, ras

    def _solids(slide):
        """返回本页所有「实心 AUTO_SHAPE 且含文字」的形状（任意尺寸，排除全幅背景）。"""
        out = []
        for sh in slide.shapes:
            if not _is_solid_auto(sh) or _is_full_bg(sh):
                continue
            if sh.top is None or sh.width is None or sh.height is None or sh.left is None:
                continue
            has_txt = any(o is not sh and o.has_text_frame and o.text_frame.text.strip()
                          and sh.left - EPS <= (o.left + o.width / 2) <= sh.left + sh.width + EPS
                          and sh.top - EPS <= (o.top + o.height / 2) <= sh.top + sh.height + EPS
                          for o in slide.shapes)
            if not has_txt:
                continue
            out.append({"l": sh.left, "t": sh.top, "w": sh.width, "h": sh.height})
        return out

    # —— 装饰/结构 autoshape 判据（结构口径，不挑形状名）——
    DECO_STRONG = 0.004   # 面积 ≥0.4% 页面积的实心/渐变/描边图形算「强图形」（药丸/徽章）
    DECO_BIG = 0.02       # 单个 ≥2% 页面积 → 独木成林（tint 柱 / 渐变中心圆 / 虚线环）
    DECO_SLIM_AR = 8      # 长宽比 ≥8 且长 ≥0.5in → 细长连线/结构条
    DECO_SLIM_MIN = 457200  # 0.5in（EMU）

    def _deco(slide):
        """本页是否存在「画出像素」的装饰/结构 autoshape（返回 bool）。

        为什么存在：layout_apply 的绘制语言是「细弧 + 药丸 + tint 柱 + 细长连线 +
        渐变圆 + 无填充描边环」，全部是 AUTO_SHAPE——既不是 PICTURE（进不了
        vec/ras），也大多无填充或面积太小（进不了 solids 卡片），此前被 text_only
        误判为「纯文字无图形元素」。

        结构判据（满足任一即算有图形结构）：
        - ≥2 个面积 ≥0.4% 页面积的实心/渐变/描边 autoshape；
        - 或 1 个面积 ≥2% 页面积的（独木成林）；
        - 或 ≥2 个细长连线形（长宽比 ≥8 且长 ≥0.5in）。

        边界（双向验证的「牙」）：纯文本 TEXT_BOX 与全幅背景永不算；单个小药丸
        或单条标题竖条不够格——真·纯文字页（0 个 autoshape）必须仍然报警。
        """
        strong = slim = 0
        big = False
        for sh in slide.shapes:
            if sh.shape_type != MSO_SHAPE_TYPE.AUTO_SHAPE or _is_full_bg(sh):
                continue
            if not sh.width or not sh.height:
                continue
            paints = False
            try:
                paints = sh.fill.type in (1, 2, 3)   # solid / pattern / gradient
            except Exception:
                pass
            if not paints:
                try:
                    paints = sh.line.fill.type == 1  # 无填充但有实心/虚线描边（如虚线环）
                except Exception:
                    pass
            if not paints:
                continue
            w, h = sh.width, sh.height
            area = w * h
            if area >= DECO_BIG * SW * SH:
                big = True
            if area >= DECO_STRONG * SW * SH:
                strong += 1
            mx, mn = max(w, h), min(w, h)
            if mn > 0 and mx / mn >= DECO_SLIM_AR and mx >= DECO_SLIM_MIN:
                slim += 1
        return bool(big or strong >= 2 or slim >= 2)

    def _has_table(slide):
        return any(getattr(sh, "has_table", False) for sh in slide.shapes)

    def _has_code(slide):
        """深色底块 + 覆盖其 ≥70% 面积的**多行**文本 → 代码块（CodeBlock 的产物特征）。

        为什么必须判「多行」：普通的深色标题带 / 主卡也是「深色块 + 单行文字」，
        只用底色判会把它们全部误判成代码块。
        """
        blocks = [sh for sh in slide.shapes
                  if _is_solid_auto(sh) and not _is_full_bg(sh)
                  and sh.width >= 0.45 * SW and sh.height >= 0.08 * SH and _is_dark(sh)]
        for b in blocks:
            for o in slide.shapes:
                if o is b or not o.has_text_frame:
                    continue
                txt = o.text_frame.text.strip()
                if not txt or "\n" not in txt:
                    continue
                if None in (o.left, o.top, o.width, o.height):
                    continue
                iw = min(b.left + b.width, o.left + o.width) - max(b.left, o.left)
                ih = min(b.top + b.height, o.top + o.height) - max(b.top, o.top)
                if iw <= 0 or ih <= 0:
                    continue
                if iw * ih >= 0.70 * (o.width * o.height):
                    return True
        return False

    def _decor_area(vec, ras):
        """装饰图形面积：单张面积 < DECOR_UNIT 页面积的图形视为装饰。"""
        page_area = SW * SH
        tot = 0
        for sh in vec + ras:
            if sh.width is None or sh.height is None:
                continue
            a = sh.width * sh.height
            if a < DECOR_UNIT * page_area:
                tot += a
        return tot

    def _arch(slide, solids, vec, ras, deco=False):
        cards = [c for c in solids if c["w"] >= MIN_W * SW and c["h"] >= MIN_H * SH]
        n_card = len(cards)
        n_vec, n_ras = len(vec), len(ras)
        n_conn = sum(1 for s in slide.shapes
                     if CONNECTOR is not None and s.shape_type == CONNECTOR)
        arrow = any(("→" in s.text_frame.text or "↓" in s.text_frame.text)
                    for s in slide.shapes if s.has_text_frame)
        # 横向条带堆叠（架构层 / 时间轴）
        wide_short = [c for c in solids if c["w"] > 0.5 * SW and c["h"] < 0.13 * SH]

        # 0) 最强信号优先：真表格 / 代码块（形状类型唯一，不会误判）
        if _has_table(slide):
            return "data_table"
        if _has_code(slide):
            return "code_block"
        # 1) 纯矢量图形页（SVG 图示 / 图廊 / 架构图 / 流程图），按图形尺度细分
        if n_vec >= 1 and n_ras == 0 and n_card == 0:
            big = max(vec, key=lambda s: (s.width or 0) * (s.height or 0))
            bw = (big.width or 0) / SW
            bh = (big.height or 0) / SH
            ar = (big.width or 0) / big.height if big.height else 0   # 真实长宽比（不受画布比例影响）
            if bw >= 0.85 and bh <= 0.35:
                return "layout_gallery"    # 宽扁线框图谱
            if bw >= 0.70:
                return "wide_diagram"      # 架构图 / 流程图
            if ar >= 3.0:
                return "step_band"         # 菱形 / 节点步骤带（细长横向）
            if 0.80 <= ar <= 1.30 and bw <= 0.50:
                return "radial_board"      # 五边形 / 蜂巢 / 环形示意（近方形整体图）
            return "vector_diagram"
        # 2) 原有卡片类判定
        if len(wide_short) >= 3:
            return "layered_stack"
        if n_ras >= 2 and n_card == 0:
            return "image_showcase"
        if n_card == 0 and n_vec == 0 and n_ras == 0 and not deco:
            return "text_only"
        if n_card == 0 and n_vec == 0 and n_ras == 0 and deco:
            return "decor_diagram"
        if n_ras >= 1 and n_card >= 1:
            return "image_annotated"
        if n_card >= 6:
            return "comparison_table"
        if n_card == 2 and all(c["w"] > 0.33 * SW for c in cards):
            return "two_column"
        # 有连接线 / 箭头 → 流程语义优先（否则「四步流程」会被误判成普通卡片行 / 网格）
        if n_conn >= 1 or (arrow and n_card >= 2):
            return "flow_process"
        if n_card >= 4:
            tops = sorted(set(round(c["t"] / SH, 2) for c in cards))
            return "card_grid" if len(tops) >= 2 else "card_row"
        if n_card >= 2:
            return "card_row"
        if n_vec >= 1:
            return "vector_diagram"
        return "mixed"

    counts, text_only, detail = {}, [], []
    n_graphic = 0
    decor_total = 0.0
    decor_pages = []
    for idx in sorted(body):
        slide = prs.slides[idx - 1]
        # 排除分隔/章节页：含纯数字大标号（如 01~04）且整体文字很少（≤4 段）的页才视为分隔页，
        # 避免误伤「带编号徽章的正文页」（如四步流程、四级大纲）。
        texts = [s.text_frame.text.strip() for s in slide.shapes
                 if s.has_text_frame and s.text_frame.text.strip()]
        if any(re.fullmatch(r"\d{1,2}", t) for t in texts) and len(texts) <= 4:
            continue
        solids = _solids(slide)
        vec, ras = _pics(slide)
        deco = _deco(slide)
        # 丢弃极简/分隔页（无图无卡且形状很少），避免误判为纯文字；
        # 但「整页就是一张真表格」的页形状也很少，必须保留（否则 data_table 页被静默漏掉）；
        # 文字量大的页同样不算极简页——文本框不进 solids/vec/ras，满页正文的纯文字页
        # 若在这里被跳过，text_only 报警就对典型 deck 失去牙（双向验证实测发现的另一半盲区）。
        n_shapes = len(list(slide.shapes))
        txt_chars = sum(len(t) for t in texts)
        if (not solids and not vec and not ras and not _has_table(slide)
                and n_shapes <= 8 and txt_chars < 120):
            continue
        da = _decor_area(vec, ras)
        decor_total += da
        if da > 0:
            decor_pages.append(idx)
        a = _arch(slide, solids, vec, ras, deco)
        counts[a] = counts.get(a, 0) + 1
        graphic = bool(vec or ras or _has_table(slide) or _has_code(slide) or deco)
        if graphic:
            n_graphic += 1
        detail.append({"page": idx, "archetype": a, "cards": len(solids),
                       "vec": len(vec), "ras": len(ras), "deco": int(bool(deco)),
                       "decor": round(da / (SW * SH), 4), "graphic": graphic})
        if a == "text_only":
            text_only.append(idx)

    total = sum(counts.values()) or 1
    H = 0.0
    for c in counts.values():
        p = c / total
        if p > 0:
            H -= p * math.log2(p)
    Hn = H / math.log2(total) if total > 1 else 1.0
    max_share = max(counts.values()) / total if counts else 0.0
    distinct = len(counts)
    graphic_ratio = (n_graphic / total) if counts else 0.0
    # 装饰占比：装饰图形总面积 / (正文页数 × 内容区面积)
    decor_ratio = (decor_total / (total * CONTENT_W * CONTENT_H)) if counts else 0.0

    issues = []
    if total < 3:
        issues.append("正文页过少（<%d），无法评估构图多样性" % 3)
    else:
        if max_share > MAX_SHARE:
            top = max(counts, key=counts.get)
            issues.append(
                f"构图过于单一：『{top}』占正文页 {max_share:.0%}（阈值 {MAX_SHARE:.0%}），"
                f"建议引入更多构图类型（对比/网格/流程/矩阵/图形/表格）以缓解视觉疲劳")
        if Hn < ENTROPY_MIN:
            issues.append(
                f"构图多样性不足：归一化熵 H={Hn:.2f}（阈值 {ENTROPY_MIN:.2f}），"
                f"正文页仅 {distinct} 种构图，建议丰富版式骨架")
        if graphic_ratio < GRAPHIC_MIN:
            issues.append(
                f"图形化表达偏弱：仅 {graphic_ratio:.0%} 的正文页含图形元素"
                f"（阈值 {GRAPHIC_MIN:.0%}），建议补架构图 / 流程图 / 图示 / 表格")
    for p in text_only:
        issues.append(
            f"第{p}页 纯文字无图形元素（无图/无卡/无表格），缺乏图形化表达，"
            f"建议补充图标 / 图示 / 图表")
    if decor_ratio > DECOR_MAX:
        issues.append(
            f"装饰占比偏高：装饰图形占内容区 {decor_ratio:.0%}（阈值 {DECOR_MAX:.0%}），"
            f"会拉低整篇统一风格，建议减少装饰或放大为内容主图")

    return {"layer": "composition_diversity", "body_pages": total,
            "archetypes": counts, "distinct": distinct,
            "entropy": round(Hn, 3), "max_share": round(max_share, 3),
            "graphic_ratio": round(graphic_ratio, 3),
            "decor_ratio": round(decor_ratio, 4),
            "decor_pages": decor_pages,
            "text_only_pages": text_only, "detail": detail, "issues": issues}


# ============================================================
# ⑦ 垂直均衡（像素法；需渲染 PNG）
# ============================================================
# 治的是「内容浮在上半页、下方一片空」——几何层量不到（形状都在框内）、
# 构图层分不出（原型判定与位置无关），只有看渲染像素才暴露。
# 典型病：表格页 / 卡片页主体被 `space-between` 顶到上半区，收束句贴页脚，
#        主体下方留白远大于上方 → 观感「重心偏上、下半页空」。
BAL_TOL = 0.08          # 内容区上下留白差 > 页高 8%  → 判定「不均衡」
# BAL_BOTTOM_MAX 已移除：单侧底部偏大由 BAL_MIN_GAP 统一管（它同时覆盖「只下方空」与「上下都空」）。
BAL_MIN_GAP = 0.15      # 上下留白**较小者** > 页高 15% → 内容垂直占比不足（对称地都空）
BAL_INNER_GAP = 0.08    # 内容块**内部**最大连续空白 > 页高 8% → 块内开天窗
HDR_MAX_H = 0.10        # 「标题带」单块最大高度（页高占比）
HDR_MAX_BLOCKS = 2      # 标题带最多吸纳的块数（标题 / 副标）——**不含引导句**
HDR_ZONE = 0.22         # 标题带必须落在页高前 22% 内（引导句实测起于 0.24，据此分流）
FOOT_MAX_H = 0.05       # 页脚单块最大高度
FOOT_NEAR_BOTTOM = 0.12 # 页脚距底边最大距离
BG_DIST = 8             # 与底色差异超过此值即视为内容像素（≈人眼可辨的色差边界）
NEAR_BG_LO = 4          # Δ∈(LO, HI] 的像素 = 「近白底」：观感上≈空白，但确有色块
NEAR_BG_HI = 8
NEAR_BG_AREA = 0.08     # 近白底像素占比 > 此值 → 提示留白量测可能偏低
#                        取 8% 而非 3%：实测 3% 档只是描边/抗锯齿的零星像素（v8 page-16 = 3.1%），
#                        成片极浅色块会到 11%~25%，两者之间留出安全间隔避免噪音提示。


def _row_flags(png_path: str):
    """逐行判定「本行是否有内容像素」。

    返回 (H, W, flags, near_bg_ratio)。
    `near_bg_ratio` = Δ∈(NEAR_BG_LO, NEAR_BG_HI] 的像素占全图比例 —— 极浅底色块，
    观感上≈空白、但确有色块，会让留白量测结果失真（见 NEAR_BG_* 常量注释）。

    性能说明：内容行命中 3 个采样点即 break，只有**判定为背景**的行才整行扫完，
    而 near_bg 恰恰只需要背景行的数据 —— 所以统计不额外增加开销。
    """
    im = Image.open(png_path).convert("RGB")
    W, H = im.size
    px = im.load()
    cs = [px[0, 0], px[W - 1, 0], px[0, H - 1], px[W - 1, H - 1]]
    bg = tuple(sorted(c[i] for c in cs)[1] for i in range(3))
    per_row = (W + 1) // 2
    flags, near, tot = [], 0, 0
    for y in range(H):
        hit = ln = 0
        for x in range(0, W, 2):
            r, g, b = px[x, y]
            d = max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2]))
            if d > BG_DIST:
                hit += 1
                if hit >= 3:
                    break
            elif d > NEAR_BG_LO:
                ln += 1
        flags.append(hit >= 3)
        tot += per_row
        if hit < 3:
            near += ln
    return H, W, flags, (near / max(1, tot))


def _max_inner_gap(flags, y0: int, y1: int) -> int:
    """区间 [y0,y1] **内部**的最大连续空白长度（px）。带与带之间的空白不参与。"""
    best, cur = 0, None
    for y in range(y0, y1 + 1):
        if not flags[y]:
            cur = [y, y] if cur is None else [cur[0], y]
        else:
            if cur:
                best = max(best, cur[1] - cur[0])
            cur = None
    if cur:
        best = max(best, cur[1] - cur[0])
    return best


def _row_bands(png_path: str):
    """返回 (H, bands, flags, near_bg)：非背景像素的**行区间**列表（近邻 ≤6px 合并）。"""
    H, W, flags, near_bg = _row_flags(png_path)
    bands, cur = [], None
    for y, f in enumerate(flags):
        if f:
            cur = [y, y] if cur is None else [cur[0], y]
        elif cur is not None:
            bands.append(tuple(cur))
            cur = None
    if cur is not None:
        bands.append(tuple(cur))
    merged = []
    for b in bands:
        if merged and b[0] - merged[-1][1] <= 6:
            merged[-1] = (merged[-1][0], b[1])
        else:
            merged.append(b)
    return H, [b for b in merged if b[1] - b[0] >= 2], flags, near_bg


def balance_check(pngs, page_types=None) -> dict:
    """⑦ 垂直均衡：正文页的内容块在「标题带下 / 页脚上」之间是否**上下留白近似**。

    上留白 = 内容首块顶 − 标题带底；下留白 = 页脚顶 − 内容末块底。
    只查正文页（cover / toc / transition / ending 的大留白属设计意图）。

    层内三条判据（编号用 **B1/B2/B3** —— 不要写成 ①②③，那会与层号撞车；
    阈值均以**页高占比**表达，故与渲染分辨率无关）：
      B1 不均衡   |上−下| > BAL_TOL(8%)           —— 重心偏上 / 偏下
      B2 垂直稀疏 min(上,下) > BAL_MIN_GAP(15%)   —— **对称地都空**，B1 的 diff 对此完全无感
      B3 块内空洞 带内最大连续空白 > BAL_INNER_GAP(8%) —— 元素被撑开 / 漏排
    另出 advisory：近白底色块占比过高会压低留白量测（该底色观感≈空白，但确有色块）。

    ⚠️ 三个已踩过的坑（改动前务必保留）：
      1. **标题带只吸纳「标题 + 副标」，不含引导句**。引导句是内容，不是页眉；
         被吞掉后测量从「主体」起算 → 32 页里误报 9 页。
         判据＝「薄」且「落在页高前 22%」（引导句实测起于 0.24H）。
      2. B2 **不能用二维填充率（fill）替代**：宽而扁的内容（全宽色条）fill 很高、
         垂直却只占一半 —— 实测 v8 page-07 fill 63.7%，上下仍各空 111~123px。
      3. B2 阈值 15% 的标定依据（实测 v8 全 32 页 + v3 对照）：
         正常正文页 min 留白 3.9~4.7% 页高；离群页 8.9~12.8%；v3 问题页 19.9%。
         取 15% → v8 全部通过、v3 page-11 被准确抓出（双向验证）。
    """
    issues, advisories, detail = [], [], []
    for i, p in enumerate(pngs or []):
        pt = page_types[i] if page_types and i < len(page_types) else "body"
        if pt != "body":
            continue
        H, bands, flags, near_bg = _row_bands(p)
        if not bands:
            continue
        hdr_end = 0
        for k, (y0, y1) in enumerate(bands[:HDR_MAX_BLOCKS]):
            # 必须同时满足「薄」与「在顶部区域」——否则会把页面的**引导句**当成标题带吞掉，
            # 于是测量从「主体」起算，凭空多出一段上留白（踩过：32 页里误报 9 页）。
            # 实测：标题 0.086H、副标 0.164H、引导句 0.24H 起 → HDR_ZONE=0.22 可干净分流。
            if (y1 - y0) <= H * HDR_MAX_H and y0 <= H * HDR_ZONE:
                hdr_end = y1
            else:
                break
        foot_top = None
        y0, y1 = bands[-1]
        if (y1 - y0) <= H * FOOT_MAX_H and (H - y1) <= H * FOOT_NEAR_BOTTOM:
            foot_top = y0
            body_bands = bands[:-1]
        else:
            body_bands = bands
        content = [b for b in body_bands if b[0] >= hdr_end] or body_bands
        if not content:
            continue
        c_top, c_bot = content[0][0], content[-1][1]
        c_floor = foot_top if foot_top is not None else int(H * 0.94)
        gap_t, gap_b = c_top - hdr_end, c_floor - c_bot
        d = gap_t - gap_b
        name = os.path.basename(p)

        # 块内空洞：只查够大的带（< 3% 页高的窄带，其内部空白无诊断意义）
        inner, inner_at = 0, None
        for (a, b) in content:
            if b - a < H * 0.03:
                continue
            g = _max_inner_gap(flags, a, b)
            if g > inner:
                inner, inner_at = g, [a, b]

        detail.append({"png": name, "h": H, "hdr_end": hdr_end,
                       "content": [c_top, c_bot], "foot_top": foot_top,
                       "gap_top": gap_t, "gap_bottom": gap_b, "diff": d,
                       "inner_gap": inner, "inner_gap_at": inner_at,
                       "near_bg": round(near_bg, 4)})

        # B1 不均衡：重心偏上 / 偏下
        if abs(d) > H * BAL_TOL:
            side = "下方" if d < 0 else "上方"
            issues.append(
                "%s 内容区上下留白不均：上 %dpx / 下 %dpx（%s偏空 %dpx，"
                "整页重心偏%s）——把主体在内容区垂直居中" %
                (name, gap_t, gap_b, side, abs(d), "上" if d < 0 else "下"))
        # B2 垂直稀疏：上下**对称地**都空 —— B1 的 diff 对此完全无感（实测离群页 diff 仅 12px）
        g_min = min(gap_t, gap_b)
        if g_min > H * BAL_MIN_GAP:
            issues.append(
                "%s 内容垂直占比不足：上 %dpx / 下 %dpx（较小者 %dpx = %.0f%% 页高，"
                "阈值 %.0f%%）——上下对称但都空，应**加大主体**而非拉大间隙" %
                (name, gap_t, gap_b, g_min, 100 * g_min / H, 100 * BAL_MIN_GAP))
        # B3 块内空洞：元素被撑开 / 漏排，行带法原先看不见这层
        if inner > H * BAL_INNER_GAP:
            issues.append(
                "%s 内容块内部开天窗：%s 区间内连续空白 %dpx（%.0f%% 页高）"
                "——检查该块元素是否被撑开或漏排" %
                (name, inner_at, inner, 100 * inner / H))
        # advisory：近白底让留白量测偏低（观感≈空白，但确有色块，属可解释偏差而非 bug）
        if near_bg > NEAR_BG_AREA:
            advisories.append(
                "%s 存在近白底色块（Δ∈(%d,%d] 占比 %.1f%%）——该底色观感≈空白，"
                "若需承载内容请改用 Δ>%d 的底色" %
                (name, NEAR_BG_LO, NEAR_BG_HI, 100 * near_bg, BG_DIST + 4))
    return {"layer": "vertical_balance", "checked": len(detail),
            "issues": issues, "advisories": advisories, "detail": detail}


def fullcheck(pptx_path: str, output_dir: str | None = None) -> dict:
    """端到端视检：七层全跑 —— ①完整性 + ②几何 + ③三区布局与密度 + ④卡片 + ⑤构图
    + ⑥渲染像素 + ⑦垂直均衡。

    渲染器无关的五层（①完整性 · ②几何 · ③三区布局与密度 · ④卡片 · ⑤构图）必跑；
    ⑥渲染像素与 ⑦垂直均衡 仅在渲染器可用时跑，否则 mode='geometry_only' 并显式声明未做视觉亲验。
    Returns:
        完整报告 dict（含 completeness / geometry / layout / cards / composition /
        pages / balance / overall）。
    """
    pptx_path = os.path.abspath(pptx_path)
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(pptx_path), "_visual_check")
    os.makedirs(output_dir, exist_ok=True)

    report = {
        "pptx": pptx_path,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "output_dir": output_dir,
    }

    # ---- ① 结构完整性（renderer-free） ----
    comp = completeness(pptx_path)
    report["completeness"] = comp
    print(f"  [完整性] 共 {comp.get('total', 0)} 页 | 封面={comp.get('has_cover')} "
          f"目录={comp.get('has_toc')} 结束页={comp.get('has_ending')} "
          f"正文={comp.get('body_count')} 过渡页={comp.get('transition_pages')}")

    # ---- ② 几何体检（renderer-free） ----
    geo = geometry_check(pptx_path)
    report["geometry"] = geo
    if geo.get("issues"):
        print(f"  [几何] {len(geo['issues'])} 处越界/溢出")
    else:
        print("  [几何] 无越界/溢出")

    # ---- ③ 三区布局与密度（renderer-free，基于真实坐标） ----
    lay = layout_check(pptx_path)
    report["layout"] = lay
    if lay.get("issues"):
        print(f"  [布局] 三区规范 {len(lay['issues'])} 项不符（正文页={lay['body_pages']}）")
    else:
        print(f"  [布局] 三区规范通过（正文页={lay['body_pages']} "
              f"标题top={lay['title_top_range']} 页脚bottom={lay['footer_bottom_range']}）")

    # ---- ④ 卡片密度与比例（renderer-free，基于真实坐标） ----
    cards = card_check(pptx_path)
    report["cards"] = cards
    if cards.get("issues"):
        print(f"  [卡片] {cards['flagged']}/{cards['card_count']} 张卡片瘦高/内部稀疏")
    else:
        print(f"  [卡片] 组件级密度通过（扫描 {cards['card_count']} 张卡片，0 处瘦高/稀疏）")

    # ---- ⑤ 构图多样化占比（renderer-free，基于真实形状） ----
    compo = composition_check(pptx_path)
    report["composition"] = compo
    if compo.get("issues"):
        print(f"  [构图] 需改进：{compo.get('distinct')} 种原型 / 正文 {compo.get('body_pages')} 页 "
              f"熵={compo.get('entropy')} 最大占比={compo.get('max_share')} "
              f"图形化={compo.get('graphic_ratio', 0):.0%} 装饰={compo.get('decor_ratio', 0):.1%}")
    else:
        print(f"  [构图] 多样性通过（{compo.get('distinct')} 种原型 / 正文 {compo.get('body_pages')} 页，"
              f"熵={compo.get('entropy')} 最大占比={compo.get('max_share')} "
              f"图形化覆盖={compo.get('graphic_ratio', 0):.0%} 装饰占比={compo.get('decor_ratio', 0):.1%}）")

    # ---- ⑥ 渲染 + 像素分析（渲染器无关，按链降级） ----
    rend = render(pptx_path, output_dir)
    report["mode"] = rend["mode"]
    report["renderer"] = rend.get("renderer")
    report["available_renderers"] = detect_renderers()
    page_types = _page_types(comp)
    if not rend["ok"]:
        report["visual_note"] = ("未做视觉亲验（无可用渲染器）；仅结构+几何检查通过"
                                 if rend["mode"] == "geometry_only" else rend.get("error"))
        report["pages"] = []
    else:
        report["pdf"] = rend["pdf"]
        pages = []
        ok_count = warn_count = 0
        for idx, png_path in enumerate(rend["pngs"], 1):
            pt = page_types[idx - 1] if idx - 1 < len(page_types) else None
            r = analyze(png_path, quiet=True, page_type=pt)
            pages.append(r)
            icon = {"PASS": "OK", "WARN": "W!"}.get(r["verdict"], "?")
            tag = f"[{pt}]" if pt else ""
            print(f"  [{icon}] {os.path.basename(png_path)} {tag} verdict={r['verdict']}  "
                  f"problems={len(r.get('problems', []))} advisories={len(r.get('advisories', []))}")
            if r["verdict"] == "WARN":
                warn_count += 1
            else:
                ok_count += 1
        report["pages"] = pages
        report["summary"] = {"total": len(pages), "pass": ok_count, "warn": warn_count,
                             "advisories": sum(len(p.get("advisories", [])) for p in pages)}

    # ---- ⑦ 垂直均衡（像素法；须有渲染 PNG） ----
    if rend["ok"] and rend.get("pngs"):
        bal = balance_check(rend["pngs"], page_types)
        report["balance"] = bal
        if bal["issues"]:
            print(f"  [均衡] {len(bal['issues'])} 项垂直均衡问题")
            for x in bal["issues"][:5]:
                print(f"        {x}")
        else:
            print(f"  [均衡] 垂直均衡通过（检查 {bal['checked']} 页正文："
                  f"上下差 ≤ {BAL_TOL:.0%}，单侧留白 ≤ {BAL_MIN_GAP:.0%}，"
                  f"块内空白 ≤ {BAL_INNER_GAP:.0%}，均为页高占比）")
        for x in (bal.get("advisories") or [])[:3]:
            print(f"        [提示] {x}")

    # ---- 综合判定 ----
    # 只有「硬伤」(结构性/几何/视觉阻断项) 才决定 overall=WARN；
    # 软提示(advisories) 仅记录，不阻断交付。
    problems = []
    if comp.get("issues"):
        problems.extend(["[完整性] " + x for x in comp["issues"]])
    if geo.get("issues"):
        problems.extend(["[几何] " + x for x in geo["issues"]])
    if lay.get("issues"):
        problems.extend(["[布局] " + x for x in lay["issues"]])
    if cards.get("issues"):
        problems.extend(["[卡片] " + x for x in cards["issues"]])
    if compo.get("issues"):
        problems.extend(["[构图] " + x for x in compo["issues"]])
    if (report.get("balance") or {}).get("issues"):
        problems.extend(["[均衡] " + x for x in report["balance"]["issues"]])
    if rend["mode"] == "full_visual" and report.get("summary", {}).get("warn", 0) > 0:
        problems.append(f"[视觉] {report['summary']['warn']} 页疑似硬伤（空白/塌陷/溢出），需人工确认")
    if rend["mode"] == "geometry_only":
        problems.append("[视觉] 未亲验（无渲染器）：结构+几何通过不代表视觉无误")

    report["problems"] = problems
    report["overall"] = "PASS" if not problems else "WARN"
    _save_report(report, output_dir)
    return report


def _save_report(report: dict, output_dir: str) -> str:
    """保存 JSON 报告到文件。"""
    path = os.path.join(output_dir, "visual_check_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    report["_report_file"] = path
    print(f"\n[visual_check] 报告: {path}  overall={report['overall']}")
    return path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)

    cmd = sys.argv[1]

    if cmd == "fullcheck" and len(sys.argv) >= 3:
        outdir = None
        if "--outdir" in sys.argv:
            outdir = sys.argv[sys.argv.index("--outdir") + 1]
        r = fullcheck(sys.argv[2], output_dir=outdir)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        sys.exit(0 if r.get("overall") == "PASS" else 1)

    elif cmd == "render" and len(sys.argv) >= 3:
        outdir = None
        if "--outdir" in sys.argv:
            outdir = sys.argv[sys.argv.index("--outdir") + 1]
        r = render(sys.argv[2], output_dir=outdir)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        sys.exit(0 if r.get("ok") else 1)

    elif cmd == "analyze" and len(sys.argv) >= 3:
        quiet = "--quiet" in sys.argv
        rep = analyze(sys.argv[2], quiet=quiet)
        if not quiet:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        sys.exit(1 if rep["verdict"] == "WARN" else 0)

    elif cmd == "tiles" and len(sys.argv) >= 3:
        out = "./_tiles"
        if "--out" in sys.argv:
            out = sys.argv[sys.argv.index("--out") + 1]
        for f in tiles(sys.argv[2], out):
            print("made:", f)

    elif cmd == "completeness" and len(sys.argv) >= 3:
        r = completeness(sys.argv[2])
        print(json.dumps(r, ensure_ascii=False, indent=2))
        sys.exit(0 if not r.get("issues") else 1)

    elif cmd == "geometry" and len(sys.argv) >= 3:
        r = geometry_check(sys.argv[2])
        print(json.dumps(r, ensure_ascii=False, indent=2))
        sys.exit(0 if not r.get("issues") else 1)

    elif cmd == "layout" and len(sys.argv) >= 3:
        r = layout_check(sys.argv[2])
        print(json.dumps(r, ensure_ascii=False, indent=2))
        sys.exit(0 if not r.get("issues") else 1)

    elif cmd == "card" and len(sys.argv) >= 3:
        r = card_check(sys.argv[2])
        print(json.dumps(r, ensure_ascii=False, indent=2))
        sys.exit(0 if not r.get("issues") else 1)

    elif cmd == "composition" and len(sys.argv) >= 3:
        r = composition_check(sys.argv[2])
        print(json.dumps(r, ensure_ascii=False, indent=2))
        sys.exit(0 if not r.get("issues") else 1)

    elif cmd == "balance" and len(sys.argv) >= 3:
        # 用法: balance <pptx> [--png-dir <dir>]；无 --png-dir 时先渲染
        png_dir = None
        if "--png-dir" in sys.argv:
            png_dir = sys.argv[sys.argv.index("--png-dir") + 1]
        pptx = sys.argv[2]
        if png_dir:
            pngs = sorted(_pngs_in(png_dir))
        else:
            rd = render(pptx, os.path.join(os.path.dirname(os.path.abspath(pptx)),
                                           "_visual_check"))
            pngs = rd.get("pngs") or []
        comp = completeness(pptx)
        r = balance_check(pngs, _page_types(comp))
        r["pages"] = len(pngs)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        sys.exit(0 if not r.get("issues") else 1)

    elif cmd == "check" and len(sys.argv) >= 3:
        sys.exit(check_dir(sys.argv[2]))

    else:
        print(__doc__)
        sys.exit(2)
