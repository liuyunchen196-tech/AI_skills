"""AI 味装饰元素专项检测（+可选修复）。

背景（v3.2.5，用户红框打回 P31 后补的能力缺口）：
v3 禁用清单（SKILL.md）早已列明"卡片顶部色条 / 单边竖条 / 标题竖条 / 下划线 / 渐变"，
但 audit.py 只查几何/配色统计，不识别这些"形状级"装饰元素——识别靠人眼读图，不算能力。
本脚本把禁用清单变成可执行的检测器。

判据（全部来自 场景00 v2.6 P31 的 XML 实测）：
1. overlay-freeform 装饰弧层：FREEFORM 且与同页某形状包围盒 IoU>0.95——
v2.x 的画法是"容器 AUTO_SHAPE + 同尺寸 FREEFORM 叠层"，路径只画顶部弧/底部弧/侧边竖条，
渲染成卡片边缘的彩色弧线/竖条（设计禁令中的 top arc / one-side bar）。
2. title-bar 标题竖条：W<=0.12in 且 0.15<=H<=0.6in 的饱和色竖条，右侧 0.4in 内有文字。
3. underline 标题下划线：H<=0.07in 且 0.3<=W<=2.5in 的饱和色横条，下方 0.6in 内有文字。
4. gradient 浓色渐变：GRADIENT 填充（AI 味/网页件强信号，palette_area 已有，此处定性列出）。
5. off-token 非令牌浓色：饱和填充色不在设计令牌表（渐变均值色一并核对）。

用法：
python ai_flavor.py <pptx>  # 检测，输出逐页清单 + 全册统计
python ai_flavor.py <pptx> --fix <out> # 修复：删 overlay/title-bar/underline 形状，渐变改令牌纯色
"""
from __future__ import annotations
import sys
import json
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.dml import MSO_FILL
from pptx.util import Emu

# 设计令牌表（场景00 deck 逆向 + v3 引擎在用）
TOKENS = {
"1677FF", "0958D9", "0B3A8C", "E6F0FF", "F0F5FF", "BFDBFE", "F3F4F6",
"1F2937", "4B5563", "9CA3AF", "E5E7EB", "FFFFFF", "F9FAFB", "EF4444", "FEF2F2",
}
# 渐变均值色 → 令牌替换表（实测 v2.6 渐变：均值 #0A49B2/#1058C5 不在令牌表）
GRAD_TOKEN_MAP = {"0A49B2": "0958D9", "1058C5": "1677FF"}


def _inch(v) -> float:
try:
return Emu(v).inches
except Exception:
return -1.0


def _rgb(color_fmt) -> str:
try:
return str(color_fmt.rgb).upper()
except Exception:
return ""


def _saturation(hex6: str) -> float:
r, g, b = (int(hex6[i:i + 2], 16) for i in (0, 2, 4))
mx, mn = max(r, g, b), min(r, g, b)
return 0.0 if mx == 0 else (mx - mn) / mx


def _solid_hex(sh) -> str:
try:
if sh.fill.type == MSO_FILL.SOLID:
return _rgb(sh.fill.fore_color)
except Exception:
pass
return ""


def _grad_info(sh) -> tuple[str, str]:
"""返回 (近似主色hex, 停靠色列表)。取不到主色返回 ('', [])。"""
try:
if sh.fill.type != MSO_FILL.GRADIENT:
return "", []
stops = sh.fill.gradient_stops
colors = [_rgb(s.color) for s in stops]
return (colors[0] if colors else ""), colors
except Exception:
return "", []


def _iou(a, b) -> float:
ax1, ay1, ax2, ay2 = a["l"], a["t"], a["l"] + a["w"], a["t"] + a["h"]
bx1, by1, bx2, by2 = b["l"], b["t"], b["l"] + b["w"], b["t"] + b["h"]
ix = max(0.0, min(ax2, bx2) - max(ax1, bx1))
iy = max(0.0, min(ay2, by2) - max(ay1, by1))
inter = ix * iy
ua = a["w"] * a["h"] + b["w"] * b["h"] - inter
return inter / ua if ua > 0 else 0.0


def detect_page(shapes, page_no: int) -> list[dict]:
findings: list[dict] = []
geoms = []
for sh in shapes:
geoms.append({
"sh": sh,
"l": _inch(sh.left), "t": _inch(sh.top),
"w": _inch(sh.width), "h": _inch(sh.height),
"type": sh.shape_type,
"txt": (sh.text_frame.text.strip()[:24] if sh.has_text_frame else ""),
})

texts = [g for g in geoms if g["txt"]]

for g in geoms:
sh = g["sh"]
# 1. 装饰弧层：FREEFORM 与同页形状几乎完全重叠
if g["type"] == MSO_SHAPE_TYPE.FREEFORM:
host = next((o for o in geoms if o is not g and o["w"] > 0 and _iou(g, o) > 0.95), None)
if host is not None:
findings.append({
"page": page_no, "kind": "overlay-freeform",
"detail": f"FREEFORM 与容器 IoU>0.95（容器 {_inch(host['sh'].left):.2f},{_inch(host['sh'].top):.2f}"
f" {_inch(host['sh'].width):.2f}x{_inch(host['sh'].height):.2f}）——顶弧/侧条/底弧装饰层",
"fix": "delete",
"shape": sh,
"host": host["sh"],
})
continue

fill_hex = _solid_hex(sh)
sat = _saturation(fill_hex) if fill_hex else 0.0

# 2. 标题竖条
if (fill_hex and sat > 0.3 and 0 < g["w"] <= 0.12 and 0.15 <= g["h"] <= 0.6):
near = any(t["txt"] and 0 < (t["l"] - (g["l"] + g["w"])) < 0.4
and abs((t["t"] + t["h"] / 2) - (g["t"] + g["h"] / 2)) < 0.25 for t in texts)
if near:
findings.append({"page": page_no, "kind": "title-bar",
"detail": f"标题左侧竖条 #{fill_hex} {g['w']:.2f}x{g['h']:.2f}in",
"fix": "delete", "shape": sh})
continue

# 3. 标题下划线
if (fill_hex and sat > 0.3 and g["h"] <= 0.07 and 0.3 <= g["w"] <= 2.5):
near = any(t["txt"] and 0 < (t["t"] - g["t"]) < 0.6 and t["l"] < g["l"] + g["w"] for t in texts)
if near:
findings.append({"page": page_no, "kind": "underline",
"detail": f"标题下划线 #{fill_hex} {g['w']:.2f}x{g['h']:.2f}in",
"fix": "delete", "shape": sh})
continue

# 4. 浓色渐变
main, stops = _grad_info(sh)
if main and _saturation(main) > 0.3:
note = "" if main in TOKENS else f"，#{main} 不在令牌表"
findings.append({"page": page_no, "kind": "gradient",
"detail": f"浓色渐变 停靠{stops} {g['w']:.2f}x{g['h']:.2f}in{note}",
"fix": "solid:" + GRAD_TOKEN_MAP.get(main, "0958D9"), "shape": sh})
continue

# 5. 非令牌浓色
if fill_hex and sat > 0.3 and fill_hex not in TOKENS:
findings.append({"page": page_no, "kind": "off-token",
"detail": f"非令牌浓色 #{fill_hex} {g['w']:.2f}x{g['h']:.2f}in",
"fix": "", "shape": sh})

return findings


def detect(pptx: str) -> tuple[list[dict], Presentation]:
prs = Presentation(pptx)
out = []
for i, slide in enumerate(prs.slides, 1):
out.extend(detect_page(slide.shapes, i))
return out, prs


def apply_fix(prs: Presentation, out_path: str, findings: list[dict]) -> dict:
"""删 overlay-freeform/title-bar/underline（宿主无填充则补中性 tint 底）；渐变改令牌纯色。
注意：findings 里的 shape/host 引用必须来自同一个 prs 对象树（live 引用）。"""
from pptx.dml.color import RGBColor
id2slide = {}
for i, slide in enumerate(prs.slides, 1):
id2slide[i] = slide
n_del = n_solid = n_tint = 0
tinted_hosts: set[int] = set()
for f in findings:
slide = id2slide.get(f["page"])
if slide is None:
continue
sh = f["shape"]
if f["fix"] == "delete":
host = f.get("host")
if host is not None and id(host) not in tinted_hosts:
try:
if host.fill.type != MSO_FILL.SOLID:
host.fill.solid()
host.fill.fore_color.rgb = RGBColor.from_string("F3F4F6")
n_tint += 1
tinted_hosts.add(id(host))
except Exception:
pass
sh._element.getparent().remove(sh._element)
n_del += 1
elif f["fix"].startswith("solid:"):
token = f["fix"].split(":", 1)[1]
try:
sh.fill.solid()
sh.fill.fore_color.rgb = RGBColor.from_string(token)
n_solid += 1
except Exception:
pass
prs.save(out_path)
return {"deleted": n_del, "solidified": n_solid, "tinted": n_tint, "out": out_path}


# ---------- B. 像素级检测（渲染 PNG，v3.2.6） ----------
#
# 判据核心是"孤立薄带"：一条饱和色带，若其两侧（横带看上下、竖带看左右）±10px 内都是低饱和区，
# 才判为装饰元素。这个条件天然排除：
# · 色块边缘（大蓝卡顶行下邻是色块延续 → 不干净 → 不报）
# · 圆形图标端部（圆边列的内侧邻列弦高更大 → 不干净 → 不报）
# · 文字笔画（蓝色粗体竖笔画高 ≤20px，低于 24px 高度阈值；深灰标题字不饱和）
# 另检测"渐变痕迹"：大块同色相饱和区域内明度沿行单调变化。

PNG_BAND_H_MAX = 14 # 横带厚度上限 px（渲染宽 1280 基准）
PNG_BAND_W_MIN = 60 # 横带最小宽度 px（下划线 96px ✓、图标 ≤56px ✗）
PNG_VBAR_H_MIN = 24 # 竖条最小高度 px（标题竖条 34px ✓、文字笔画 ≤20px ✗）
PNG_VBAR_W_MAX = 14 # 竖条宽度上限 px（标题竖条 6px ✓、图标 40-56px ✗）
PNG_SAT_T = 0.30 # 饱和度阈值
PNG_V_T = 0.35 # 明度阈值（排除浅 tint）


def detect_png(png_path: str) -> list[dict]:
"""像素级检测（v3.2.6 连通域版）。

对渲染 PNG 做饱和色掩码 → 4-连通域标记 → 按连通域形状定性：
· 扁平域（宽≥60px、高≤16px、宽高比≥8） → h-band 孤立横带（顶弧/下划线类装饰）
· 细长域（高≥24px、宽≤8px、高宽比≥4） → v-band 孤立竖条（标题竖条/侧边条类）
· 空心大域（bbox>100x40 且填充率<0.5） → 框线图形（模拟界面/边框，合法，不报）
· 实心大域（面积≥3% 且域内明度极差>0.2） → gradient-block 渐变痕迹
行级游程方案的教训：同一行里不同元素的带会粘连（大色块行吞掉弧线行），必须按连通域定性。
"""
from PIL import Image
from collections import deque
img = Image.open(png_path).convert("RGB")
w, h = img.size
if w > 1280:
r = 1280 / w
img = img.resize((1280, max(1, int(h * r))))
w, h = img.size
px = img.load()

def sat_v(r, g, b):
mx, mn = max(r, g, b), min(r, g, b)
return (0.0 if mx == 0 else (mx - mn) / mx), mx / 255.0

mask = bytearray(w * h)
vals = [0.0] * (w * h)
for y in range(h):
base = y * w
for x in range(w):
s, v = sat_v(*px[x, y])
if s > PNG_SAT_T and v > PNG_V_T:
mask[base + x] = 1
vals[base + x] = v

visited = bytearray(w * h)
regions: list[dict] = []
out: list[dict] = []
for start in range(w * h):
if not mask[start] or visited[start]:
continue
# BFS 收集连通域
x0 = x1 = start % w
y0 = y1 = start // w
n = 0
v_min, v_max = 1.0, 0.0
stack = deque([start])
visited[start] = 1
while stack:
idx = stack.popleft()
n += 1
cx, cy = idx % w, idx // w
if cx < x0: x0 = cx
if cx > x1: x1 = cx
if cy < y0: y0 = cy
if cy > y1: y1 = cy
v = vals[idx]
if v < v_min: v_min = v
if v > v_max: v_max = v
if cx > 0 and mask[idx - 1] and not visited[idx - 1]:
visited[idx - 1] = 1; stack.append(idx - 1)
if cx < w - 1 and mask[idx + 1] and not visited[idx + 1]:
visited[idx + 1] = 1; stack.append(idx + 1)
if cy > 0 and mask[idx - w] and not visited[idx - w]:
visited[idx - w] = 1; stack.append(idx - w)
if cy < h - 1 and mask[idx + w] and not visited[idx + w]:
visited[idx + w] = 1; stack.append(idx + w)

bw, bh = x1 - x0 + 1, y1 - y0 + 1
regions.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "bw": bw, "bh": bh,
"n": n, "vmin": v_min, "vmax": v_max})

# 统一判定（收集完再做孤立性分析）
for r in regions:
bw, bh = r["bw"], r["bh"]
# 扁平横带（顶弧/下划线）
if bw >= PNG_BAND_W_MIN and bh <= PNG_BAND_H_MAX and bw >= 8 * bh and r["n"] >= 40:
out.append({"kind": "h-band", "at": f"({r['x0']},{r['y0']})-({r['x1']},{r['y1']})",
"detail": f"孤立横带 {bw}x{bh}px（顶弧/下划线类装饰）"})
# 细长竖条（标题竖条/侧边条）——需孤立：文字笔画的窗口内必有同伴笔画
elif bh >= PNG_VBAR_H_MIN and bw <= 8 and bh >= 4 * bw and r["n"] >= 15:
wx0, wx1 = r["x0"] - 60, r["x1"] + 60
wy0, wy1 = r["y0"] - 12, r["y1"] + 12
neighbors = sum(
1 for o in regions if o is not r
and o["x0"] < wx1 and o["x1"] > wx0 and o["y0"] < wy1 and o["y1"] > wy0
)
if neighbors <= 1:
out.append({"kind": "v-band", "at": f"({r['x0']},{r['y0']})-({r['x1']},{r['y1']})",
"detail": f"孤立竖条 {bw}x{bh}px（标题竖条/侧边条类）"})
# 实心大域：查渐变痕迹（纯色卡 V 极差小，渐变域 V 沿方向展开）
elif bw * bh >= 0.03 * w * h and r["n"] >= 0.5 * bw * bh and (r["vmax"] - r["vmin"]) > 0.22 and bh >= 12:
out.append({"kind": "gradient-block", "at": f"({r['x0']},{r['y0']})-({r['x1']},{r['y1']})",
"detail": f"大块渐变痕迹 {bw}x{bh}px 明度极差{r['vmax'] - r['vmin']:.2f}"})
return out


def detect_png_dir(d: str) -> dict:
"""目录批量。返回 {文件名: [finding...]}，只含有嫌疑的页。"""
from pathlib import Path as _P
res = {}
for p in sorted(_P(d).glob("*")):
if p.suffix.lower() != ".png" or p.name.startswith("_"):
continue
try:
f = detect_png(str(p))
except Exception:
continue
if f:
res[p.name] = f
return res


def main():
if len(sys.argv) < 2:
print(__doc__)
sys.exit(1)
src = sys.argv[1]
if "--render" in sys.argv:
# 像素级模式：参数是渲染 PNG 目录
res = detect_png_dir(src)
total = sum(len(v) for v in res.values())
print(f"AI 味像素检测: {src}")
print(f"共 {total} 处嫌疑，涉及 {len(res)}/{len(list(__import__('pathlib').Path(src).glob('*.png')))} 张")
for name in sorted(res):
print(f" {name}:")
for f in res[name]:
print(f" [{f['kind']}] {f['at']} {f['detail']}")
return
findings, prs = detect(src)

by_kind: dict[str, int] = {}
pages: dict[int, list] = {}
for f in findings:
by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
pages.setdefault(f["page"], []).append(f)

print(f"AI 味装饰元素检测: {Path(src).name}")
print(f"共 {len(findings)} 处 " + " ".join(f"{k}x{v}" for k, v in sorted(by_kind.items())))
for pg in sorted(pages):
print(f"\n--- P{pg:02d} ---")
for f in pages[pg]:
print(f" [{f['kind']}] {f['detail']} → 建议: {f['fix'] or '人工复核'}")

if "--fix" in sys.argv:
out = sys.argv[sys.argv.index("--fix") + 1]
# 只修机械可修项；off-token 留人工
fixable = [f for f in findings if f["fix"] in ("delete",) or f["fix"].startswith("solid:")]
r = apply_fix(prs, out, fixable)
print(f"\n修复完成: 删除 {r['deleted']} 处装饰元素(补 tint 底 {r['tinted']} 处), 渐变改纯色 {r['solidified']} 处 → {r['out']}")
remain = len(findings) - len(fixable)
if remain:
print(f"（另有 {remain} 处 off-token 需人工定夺，未动）")
elif "--json" in sys.argv:
slim = [{k: f[k] for k in ("page", "kind", "detail", "fix")} for f in findings]
print(json.dumps(slim, ensure_ascii=False, indent=1))


if __name__ == "__main__":
main()
