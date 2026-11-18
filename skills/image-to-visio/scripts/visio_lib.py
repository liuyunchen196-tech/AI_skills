# -*- coding: utf-8 -*-
"""
visio_lib.py -- 「图片转 Visio」通用底座。

把一个位图的像素几何，直接变成原生 Visio 图形（不是贴图）。

设计要点
--------
* 坐标一律用 **源图像素**，y 向下（和图像处理一致）；只在画图那一刻换算成 Visio 英寸。
* SCALE = 48 源像素/英寸  ->  Visio 的 Page.Export 是 96 DPI  ->  导出恰好是源图的 2x。
  于是"源图像素"和"导出像素"是严格的 2:1，比对时不需要重采样。
* 构造时自动画一个**近白细线矩形**当"隐形画框"，把导出取景锁死在 (0,0)..(W,H)。
* 保存时走 %TEMP%（沙箱不让 Visio 直接写工作区），导出带重试，最后自动配准预览。

用法
----
    from visio_lib import Fig
    f = Fig(img_w=362, img_h=333, page_name="My Figure")
    f.line((19, 263.5), (348, 263.5), lc="RGB(52,52,54)", lw=f.LW(2.0))
    f.poly([(0, 0), (10, 0), (10, 10)], fill="RGB(199,199,200)")
    f.text(200.5, 24.5, "Title", 24.0, w=280, h=22)
    print(f.audit())
    f.save(r"D:/out/MyFigure.vsdx", r"D:/out/MyFigure_preview.png")

依赖：pywin32, Pillow, numpy（scipy 只在测量脚本里用）
运行：必须用装了 pywin32 的 Python 解释器，且**不要**通过 PowerShell 跑（COM 会被拦）。
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
import time

import win32com.client
from win32com.client import gencache

TMPDIR = tempfile.gettempdir()

DEFAULT_SCALE = 48.0                  # 源图像素 / 英寸
DEFAULT_PAD = 0.5                     # 英寸；不留边导出会裁掉边缘
FRAME_RGB = "RGB(253,253,253)"        # 近白：白底上肉眼不可见，但导出栅格可检测

# 本机 Visio 16.0 用的旧版单元格名。先探测再写死，见 probe_cells.py。
CELL_FILL_FG = "FillForegnd"          # NOT FillForegroundColor
CELL_END_ARROW = "EndArrow"           # NOT LineEndArrow
CELL_END_ARROW_SIZE = "EndArrowSize"

# 默认配色（可按图覆盖）
C_BLACK = "RGB(32,32,34)"
C_OUTLINE = "RGB(85,85,87)"
C_WHITE = "RGB(255,255,255)"


# --------------------------------------------------------------------------- #
# 进程 / 应用
# --------------------------------------------------------------------------- #
def visio_running():
    """VISIO.EXE 是否在跑。"""
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq VISIO.EXE"],
                           capture_output=True, timeout=20)
        out = (r.stdout or b"").decode("mbcs", "ignore").lower()
        return "visio.exe" in out
    except Exception:
        return False


def kill_visio(quiet=False):
    """清掉残留的 VISIO.EXE。

    **注意：这是 /F 强杀，会丢掉用户正在编辑的 Visio 文档里未保存的内容。**
    之所以必须杀：`EnsureDispatch` 会附着到**已存在**的实例上；上一次脚本崩溃留下的
    僵尸实例（不可见、可能已挂死）会让新脚本一起挂住。
    因此：如果检测到 VISIO.EXE 在跑，先明确警告一次。用户自己开着 Visio 时，
    应让他先存盘再继续。
    """
    if visio_running():
        if not quiet:
            print("   !! 检测到 VISIO.EXE 正在运行，即将 /F 强杀。")
            print("      如果你正在编辑 Visio 文档，请立刻 Ctrl+C 中止并先保存！")
        try:
            subprocess.run(["taskkill", "/F", "/IM", "VISIO.EXE"],
                           capture_output=True, timeout=20)
        except Exception:
            pass
    return True


def open_visio(visible=False):
    """早期绑定打开 Visio。**必须 EnsureDispatch**，否则 DrawPolyline 报'无效的参数数目'。"""
    try:
        app = gencache.EnsureDispatch("Visio.Application")
    except Exception:
        app = win32com.client.Dispatch("Visio.Application")
    for attr, val in (("Visible", int(bool(visible))), ("AlertResponse", 7)):
        try:
            setattr(app, attr, val)
        except Exception:
            pass
    return app


def _pt(px):
    """源图像素线宽 -> 磅。1 源像素 = 2 导出像素 = 1.5 pt @96DPI。"""
    return px * 1.5


# --------------------------------------------------------------------------- #
# Fig
# --------------------------------------------------------------------------- #
class Fig:
    """一张图的绘制上下文。坐标全用源图像素，y 向下。"""

    LW = staticmethod(_pt)

    def __init__(self, img_w, img_h, scale=DEFAULT_SCALE, pad=DEFAULT_PAD,
                 page_name="Figure", kill_existing=True, draw_frame=True):
        self.W = int(img_w)
        self.H = int(img_h)
        self.scale = float(scale)
        self.pad = float(pad)
        if kill_existing:
            kill_visio()
        self.app = open_visio()
        self.doc = self.app.Documents.Add("")
        self.page = self.doc.Pages.Item(1)
        try:
            self.page.Name = page_name
        except Exception:
            pass
        try:
            ps = self.page.PageSheet
            ps.CellsU("PageWidth").FormulaU = "%.4f in" % (self.W / self.scale + 2 * self.pad)
            ps.CellsU("PageHeight").FormulaU = "%.4f in" % (self.H / self.scale + 2 * self.pad)
        except Exception as e:
            print("   page-size warn:", e)
        if draw_frame:
            self._draw_frame()

    # ---------------------------------------------------------------- 坐标
    def VP(self, x, y):
        """源图像素 (y 向下) -> Visio 英寸 (y 向上)。"""
        return (self.pad + x / self.scale,
                self.pad + (self.H - y) / self.scale)

    # ---------------------------------------------------------------- 画框
    def _draw_frame(self):
        """近白细线矩形：把 Export 的取景锁到 (0,0)..(W,H)。"""
        pts = [(0, 0), (self.W, 0), (self.W, self.H), (0, self.H)]
        flat = []
        for (x, y) in pts:
            vx, vy = self.VP(x, y)
            flat += [vx, vy]
        flat += flat[:2]
        shp = self.page.DrawPolyline(flat, 0)
        shp.CellsU("LineColor").FormulaU = FRAME_RGB
        shp.CellsU("LineWeight").FormulaU = "0.25 pt"
        shp.CellsU("LinePattern").FormulaU = "1"
        shp.CellsU("FillPattern").FormulaU = "0"
        self.frame = shp

    # ---------------------------------------------------------------- 样式
    @staticmethod
    def _style(shp, fill, lc, lw, lp):
        if lc is None:
            shp.CellsU("LinePattern").FormulaU = "0"
        else:
            shp.CellsU("LineColor").FormulaU = str(lc)
            shp.CellsU("LineWeight").FormulaU = "%.2f pt" % lw
            shp.CellsU("LinePattern").FormulaU = str(lp)
        if fill is None:
            shp.CellsU("FillPattern").FormulaU = "0"
        else:
            shp.CellsU("FillPattern").FormulaU = "1"
            shp.CellsU(CELL_FILL_FG).FormulaU = str(fill)
        return shp

    # ---------------------------------------------------------------- 图元
    def poly(self, pts, fill=None, lc=C_OUTLINE, lw=1.0, lp=1, close=True):
        """自由多边形。pts 为源图像素。lw 单位 pt。"""
        flat = []
        for (x, y) in pts:
            vx, vy = self.VP(x, y)
            flat += [vx, vy]
        if close and len(flat) >= 4:
            flat += flat[:2]
        return self._style(self.page.DrawPolyline(flat, 0), fill, lc, lw, lp)

    def line(self, p0, p1, lc=C_OUTLINE, lw=1.0, lp=1):
        a = self.VP(*p0)
        b = self.VP(*p1)
        return self._style(self.page.DrawLine(a[0], a[1], b[0], b[1]), None, lc, lw, lp)

    def rect(self, x0, y0, x1, y1, fill=None, lc=C_OUTLINE, lw=1.0, lp=1):
        a = self.VP(min(x0, x1), min(y0, y1))
        b = self.VP(max(x0, x1), max(y0, y1))
        return self._style(self.page.DrawRectangle(a[0], a[1], b[0], b[1]), fill, lc, lw, lp)

    def oval(self, cx, cy, rx, ry, fill=None, lc=C_OUTLINE, lw=1.0, lp=1):
        a = self.VP(cx - rx, cy + ry)
        b = self.VP(cx + rx, cy - ry)
        return self._style(
            self.page.DrawOval(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])),
            fill, lc, lw, lp)

    def dot(self, cx, cy, r=3.0, color="0"):
        """实心圆点（数据标记用）。"""
        return self.oval(cx, cy, r, r, fill=color, lc=None)

    def arrowhead(self, tip, ang_deg, length=11.5, half=4.8, color="0", notch=0.34):
        """实心箭头，顶点在 tip，指向 ang_deg（源图像素坐标系，y 向下，0=向右，90=向下）。
        notch>0 时画成带凹口的燕尾箭头；notch=0 为纯三角。"""
        t = math.radians(ang_deg)
        ux, uy = math.cos(t), math.sin(t)
        nx, ny = -uy, ux
        bx, by = tip[0] - length * ux, tip[1] - length * uy
        p1 = (bx + half * nx, by + half * ny)
        p2 = (bx - half * nx, by - half * ny)
        if notch:
            mid = (bx + notch * length * ux, by + notch * length * uy)
            return self.poly([tip, p1, mid, p2], fill=color, lc=None)
        return self.poly([tip, p1, p2], fill=color, lc=None)

    def rrect(self, x0, y0, x1, y1, r, n=12, lc=C_OUTLINE, lw=1.0):
        """圆角矩形轮廓（一条闭合折线）。"""
        def arc(cx, cy, a0, a1):
            return [(cx + r * math.cos(a0 + (a1 - a0) * i / n),
                     cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
        pts = (arc(x0 + r, y0 + r, math.pi, 1.5 * math.pi) +
               arc(x1 - r, y0 + r, 1.5 * math.pi, 2 * math.pi) +
               arc(x1 - r, y1 - r, 0.0, 0.5 * math.pi) +
               arc(x0 + r, y1 - r, 0.5 * math.pi, math.pi))
        return self.poly(pts, fill=None, lc=lc, lw=lw)

    def dashed(self, p0, p1, on=9.0, off=2.4, lc=C_OUTLINE, lw=1.0):
        """手写虚线：Visio 的 LinePattern=2 渲染成**圆点**，而论文插图要的是矩形短划。
        沿直线按 on/off（源图像素）切片，每片一条 DrawLine。"""
        x0, y0 = p0
        x1, y1 = p1
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 1e-6:
            return
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        t = 0.0
        while t < L:
            e = min(t + on, L)
            self.line((x0 + ux * t, y0 + uy * t), (x0 + ux * e, y0 + uy * e), lc=lc, lw=lw)
            t = e + off

    def text(self, cx, cy, s, size, align=1, font="Times New Roman",
             w=120.0, h=30.0, bold=False, color="0"):
        """透明文本框，中心在 (cx, cy)（源图像素）；w/h 是文本框尺寸（源图像素）。
        align: 0=左 1=中 2=右。
        注意：size 必须**实测标定**（Visio 渲染 TNR 比字体本身宽 ~11%），见 probe_cells.py。"""
        a = self.VP(cx - w / 2.0, cy + h / 2.0)
        b = self.VP(cx + w / 2.0, cy - h / 2.0)
        shp = self.page.DrawRectangle(min(a[0], b[0]), min(a[1], b[1]),
                                      max(a[0], b[0]), max(a[1], b[1]))
        self._style(shp, None, None, 0, 1)
        shp.Text = s
        try:
            shp.CellsU("Char.Size").FormulaU = "%.1f pt" % size
            shp.CellsU("Char.Font").FormulaU = '"%s"' % font
            shp.CellsU("Char.Color").FormulaU = str(color)
            shp.CellsU("Para.HorzAlign").FormulaU = str(align)
            shp.CellsU("VerticalAlign").FormulaU = "1"
            if bold:
                shp.CellsU("Char.Style").FormulaU = "1"
        except Exception as e:
            print("   text cell warn:", e)
        return shp

    # ---------------------------------------------------------------- 自检
    def audit(self, verbose=True):
        """检查有没有 shape 越出隐形画框（越出会让导出取景变大、配准失效）。
        返回越界的 shape 列表。"""
        out = []
        try:
            import numpy as np
        except Exception:
            return out
        n = self.page.Shapes.Count
        for i in range(1, n + 1):
            sh = self.page.Shapes.Item(i)
            if sh.ID == getattr(self.frame, "ID", -1):
                continue
            try:
                x0 = sh.CellsU("PinX").ResultIU - sh.CellsU("Width").ResultIU / 2
                y0 = sh.CellsU("PinY").ResultIU - sh.CellsU("Height").ResultIU / 2
                x1 = x0 + sh.CellsU("Width").ResultIU
                y1 = y0 + sh.CellsU("Height").ResultIU
            except Exception:
                continue
            if (x0 < self.pad - 1e-6 or y0 < self.pad - 1e-6 or
                    x1 > self.pad + self.W / self.scale + 1e-6 or
                    y1 > self.pad + self.H / self.scale + 1e-6):
                out.append((sh.ID, round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)))
        if verbose:
            if out:
                print("   AUDIT: %d shape(s) outside the frame ->" % len(out))
                for o in out[:12]:
                    print("      id=%s  box(in)=%s" % (o[0], o[1:]))
                print("      越界会把导出取景撑大，配准会失效；请缩小该 shape 或加大 PAD。")
            else:
                print("   AUDIT: ok, 所有 shape 都在画框内。")
        return out

    # ---------------------------------------------------------------- 保存
    def save(self, vsdx_path, png_path=None, close=True):
        """存 TEMP -> 导出（带重试）-> 拷回目标路径 -> 自动配准预览。
        返回 dict(vsdx=, png=, offset=(ox,oy), raw_size=)。"""
        base = os.path.splitext(os.path.basename(vsdx_path))[0]
        tmp_vsdx = os.path.join(TMPDIR, base + ".vsdx")
        tmp_png = os.path.join(TMPDIR, base + ".png")
        for f in (tmp_vsdx, tmp_png):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

        self.doc.SaveAs(tmp_vsdx)

        ok = False
        last = None
        for attempt in range(12):
            try:
                self.page.Export(tmp_png)
                ok = True
                break
            except Exception as e:
                last = e
                time.sleep(1.0)
        if close:
            try:
                self.doc.Saved = True
                self.doc.Close()
            except Exception:
                pass
            try:
                self.app.Quit()
            except Exception:
                pass
        if not ok:
            raise RuntimeError("Visio Page.Export failed after 12 attempts: %s" % last)

        shutil.copyfile(tmp_vsdx, vsdx_path)
        res = {"vsdx": vsdx_path, "png": None, "offset": (0, 0), "raw_size": None}
        if png_path:
            ox, oy, size = register_preview(tmp_png, self.W, self.H, png_path)
            res.update(png=png_path, offset=(ox, oy), raw_size=size)
        return res

    def close(self):
        try:
            self.doc.Saved = True
            self.doc.Close()
        except Exception:
            pass
        try:
            self.app.Quit()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# 预览配准
# --------------------------------------------------------------------------- #
def register_preview(export_png, img_w, img_h, out_png, tol=1):
    """把导出栅格贴到 (2*W, 2*H) 的白画布上。

    隐形画框是导出里**最外侧**的东西，所以导出的包围盒 == 画框包围盒 == 源图 (0,0)..(W,H)，
    于是导出左上角就对应源图原点，offset 恒为 (0,0)。

    判据用**导出尺寸**而不是颜色检测——画框是近白的（253），按"非白"阈值根本检不出来，
    而且近白像素会被抗锯齿污染。尺寸是确定性的：
        导出尺寸 == (2W, 2H)  ->  offset = (0,0)
        否则说明有 shape 越出画框把取景撑大了（Fig.audit() 会提前警告），
        此时回退到"非白像素包围盒"配准并给出警告。
    返回 (ox, oy, export_size)。"""
    from PIL import Image
    import numpy as np
    im = Image.open(export_png).convert("RGB")
    ew, eh = im.size
    tw, th = int(round(2 * img_w)), int(round(2 * img_h))
    if abs(ew - tw) <= tol and abs(eh - th) <= tol:
        ox = oy = 0
    else:
        a = np.array(im)
        nonwhite = a.min(axis=2) < 250
        ys, xs = np.nonzero(nonwhite)
        ox = int(xs.min()) if len(xs) else 0
        oy = int(ys.min()) if len(ys) else 0
        print("   WARN: 导出 %dx%d != 预期 %dx%d —— 画框可能被越界形状撑大了，"
              "已回退到内容包围盒配准（可能不准）。检查 Fig.audit() 的输出。"
              % (ew, eh, tw, th))
    canvas = Image.new("RGB", (tw, th), (255, 255, 255))
    canvas.paste(im, (-ox, -oy))
    canvas.save(out_png)
    return ox, oy, im.size


# --------------------------------------------------------------------------- #
# 冒烟测试
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "visio_lib_smoke")
    os.makedirs(out, exist_ok=True)
    f = Fig(img_w=200, img_h=120, page_name="Smoke")
    f.rect(10, 10, 190, 40, fill="RGB(199,199,200)", lw=f.LW(2.0))
    f.line((10, 60), (190, 60), lc=C_BLACK, lw=f.LW(2.0))
    f.dashed((10, 80), (190, 80), on=9, off=3, lc=C_OUTLINE, lw=f.LW(2.0))
    f.arrowhead((100, 100), 90, length=10, half=4)
    f.text(100, 25, "Smoke Test", 18.0, w=160, h=20)
    f.audit()
    r = f.save(os.path.join(out, "smoke.vsdx"), os.path.join(out, "smoke_preview.png"))
    print("OK", r)
