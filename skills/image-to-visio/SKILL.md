---
name: image-to-visio
display_name: 图片转visio
display_name_en: Image to Visio
description: 把位图（截图/论文插图/结构示意图/流程图）在 Visio 中复刻成原生可编辑图形，每个元素都是可点选、可改色、可改线宽、可改文字的真 shape，而非插入的贴图。流程为像素级测量源图、换算 Visio 坐标、经 COM 生成原生 shape、导出栅格、与原图逐区域墨迹比对并迭代收敛。
description_zh: 把位图（截图/论文插图/结构示意图/流程图）在 Visio 中复刻成原生可编辑图形，每个元素都是可点选、可改色、可改线宽、可改文字的真 shape，而非插入的贴图。流程为像素级测量源图、换算 Visio 坐标、经 COM 生成原生 shape、导出栅格、与原图逐区域墨迹比对并迭代收敛。
description_en: Rebuild a bitmap (screenshot, paper figure, structural diagram, flowchart) into native, fully editable Visio shapes instead of a pasted picture. Each element can be selected, recolored, restroked and retexted. The workflow measures the source image pixel by pixel, converts to Visio coordinates, generates native shapes over COM, exports a raster, then compares ink coverage region by region and iterates until it converges.
category: 设计创意
version: 1.0.0
author: 小小郭
---

# 图片转 Visio（位图 -> 原生可编辑 Visio 图形）

## 何时用 / 不用

**用**：用户给一张图（截图、论文插图、示意图），要求"在 Visio 里复刻/重画/转成 Visio"。
交付物必须是**原生 Visio 图形**——每个元素都是一个可以点选、改颜色、改线宽、改文字的 shape。

**不用**：用户只是要"插入图片到 Visio"、"把图贴进 Visio"（那是 `Insert -> Picture`，一行就完事，
不需要本 skill）。判断依据：用户是否期待**可编辑**。

> **底线**：绝不用「把原图作为图片贴进 Visio 页」冒充复刻。用户要的是矢量重建。

---

## 权限声明

本技能会执行以下动作，安装前请确认可接受：

| 权限 | 具体行为 | 用途 |
|---|---|---|
| 进程操作 | 调用 `tasklist` 探测 VISIO.EXE；必要时 `taskkill /F` 强制结束 VISIO.EXE | 清理上次崩溃残留的僵尸实例，否则 COM 会挂住 |
| COM 自动化 | 通过 pywin32 早期绑定控制本机已安装的 Microsoft Visio | 创建文档、绘制原生 shape、导出 PNG |
| 文件读写 | 写入系统临时目录 `%TEMP%`；读取/写入用户指定的图片与输出目录 | Visio 无法直接写入受限目录，需经 TEMP 中转 |
| 依赖安装 | 首次使用若缺库，需在独立 venv 内安装 pillow、pywin32、numpy、scipy | 图像处理与 COM 调用 |

> **重要提醒**：强制结束 VISIO.EXE 会丢失用户正在编辑且未保存的 Visio 文档内容。
> 执行前务必先提示用户保存。脚本在检测到实例运行时也会打印警告。

本技能**不联网**、**不上传任何数据**、**不读取凭据或系统敏感目录**、**不持久化驻留**。

---

## 环境要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows |
| 应用 | Microsoft Visio 2016 及以上（已在 Visio 16.0 上验证） |
| Python | 3.9 及以上，需含 pywin32、Pillow、numpy、scipy |
| 启动方式 | **必须用 Bash + 独立 venv 的 Python 运行**，不要用 PowerShell（会拦截 COM 实例化） |

**依赖自检**（开工前 30 秒）：

```bash
# 把 PY 换成你本机装了上述依赖的 venv Python 解释器路径
PY="/path/to/your/venv/Scripts/python.exe"
"$PY" -c "import win32com,PIL,numpy,scipy;print('deps ok')"
```

缺依赖时在该 venv 内安装（**不要**全局装）：

```bash
"$PY" -m pip install pillow pywin32 numpy scipy
```

**定位 Visio 安装路径**（不同 Office 版本路径不同，请按实际调整）：

```bash
# 常见位置（按需替换年份/位数）
ls "/c/Program Files/Microsoft Office/root/Office16/VISIO.EXE"
```

> 本技能已在 Visio 16.0 上完整验证。若你的 Visio 版本不同，单元格名可能有差异，
> 请先跑 `scripts/probe_cells.py` 探测，不要照抄文档。

> **开工前提醒用户先保存正在编辑的 Visio 文档。** 自动化会强制结束 VISIO.EXE
> （因为早期绑定会附着到已存在的实例，上次崩溃留下的僵尸实例会让脚本挂住）。
> `visio_lib.kill_visio()` 检测到实例在跑时会打印警告——**看到警告就停下来问用户**。

---

## 总流程（7 步）

```
(1) 取图 & 建工作区  ->  (2) 像素取证（量）  ->  (3) 写生成脚本（画）
        ^                                              |
        +---- (7) 收敛判定  <-  (6) 逐区域比对  <-  (5) 自动配准  <-  (4) 导出
```

| 步 | 做什么 | 产出 |
|---|---|---|
| 1 | 把源图拷成 `src.png`，建 `<work>/` 放测量脚本与中间产物 | 工作目录 |
| 2 | `measure_image.py` 跑通，把所有元素量成数值 | 一份几何清单 |
| 3 | 用 `visio_lib.Fig` 写 `build_<name>.py`，**坐标全部用源图像素** | 生成脚本 |
| 4 | 脚本内 `fig.save(vsdx, png)`：存 TEMP -> 导出 -> 拷回工作区 | `.vsdx` + 2x 预览 |
| 5 | `save()` 自动把导出配准到 2x 画布 | 对齐的预览 |
| 6 | `compare_render.py`：并排 + 红蓝叠加 + 逐区域 ink 比 | 比对图 + 数字 |
| 7 | 按"区域 ink 比 0.85~1.15"判定，不达标就回到 2 精测那一个区域 | — |

**迭代是常态**。每轮只改**一处**，改完立刻重跑第 6 步，否则无法归因。

---

## 坐标系（整个方法的地基）

- 内部一律用**源图像素**坐标，`y 向下`（和图像处理一致），只在画图那一刻转换。
- 转换函数：`VP(x, y) = (PAD + x/SCALE, PAD + (IMG_H - y)/SCALE)`，`SCALE = 48.0`，`PAD = 0.5 in`。
- **为什么是 48**：`Page.Export` 固定 96 DPI，所以 48 px/in 的布局导出后**恰好是源图的 2 倍**，
  像素一一对应，比对时不需要重采样，任何 1px 的偏差都能直接看出来。
- 页面尺寸 = `IMG_W/48 + 2*PAD` 乘 `IMG_H/48 + 2*PAD`（不留 `PAD` 的话导出会裁掉边缘）。

---

## Visio COM 铁律（Visio 16.0 / Windows 上实测）

> 完整踩坑记录见 `references/visio-com-gotchas.md`。这 8 条是必背的：

1. **必须早期绑定**：`gencache.EnsureDispatch("Visio.Application")`。
   用 `Dispatch` 的话 `DrawPolyline` 会报 **"无效的参数数目"**。
2. **`DrawPolyline(xyArray, Flags)` 有两个必填参数**，`Flags=0`。
   `DrawBezier` 是 `(xyArray, degree, Flags)`。
3. **本机用旧版单元格名**：`FillForegnd`（**不是** `FillForegroundColor`）、
   `EndArrow` + `EndArrowSize`（**没有** `LineEndArrow`）。`Char.Spacing` 在这台机器上**不存在**。
   -> 用前先探测（`scripts/probe_cells.py`），不要照抄新文档。
4. **`doc.SaveAs` / `Documents.Open` 写不进工作区目录**（沙箱）。一律存 `%TEMP%`，
   再用 `shutil.copyfile` 搬。`Documents.Open` 同理：先拷到 TEMP 再开。
5. **`Page.Export` 的取景 = 所有可绘制形状的并集**，不是页面。
   -> **画一个近白细线矩形当"隐形画框"**（`LineColor = RGB(253,253,253)`，0.25pt），
   它让导出范围锁定到 `(0,0)..(IMG_W,IMG_H)`，同时几乎不可见。
   `visio_lib.Fig` 构造时自动画好。
6. **`Page.Export` 会偶发失败**（"被呼叫方拒绝接收呼叫"）-> 包一层 12 次重试 + `sleep(1)`。
7. **收尾三件套**：`app.AlertResponse = 7`（禁弹窗）、`doc.Saved = True` 再 `doc.Close()`、`app.Quit()`。
   跑之前先 `taskkill /F /IM VISIO.EXE` 清残留实例，否则会挂。
8. **pywin32 不支持参数化属性赋值**：`ch.CharProps(1) = 1` 是**语法错误**。
   粗体/常规混排只能拆成两个文本框。

---

## 像素取证：怎么"量"（第 2 步）

用 `scripts/measure_image.py`，它把下面五类测量一次跑完：

| 手段 | 用来量什么 | 关键做法 |
|---|---|---|
| **灰度分层 + 连通域** | 填充块（柱、梁、板、地面、色块） | 按目标灰度 加减 8 取 mask，`ndimage.label`，输出 `x[y]` 包围盒 |
| **逐行/逐列扫描** | 线、边框、带状结构 | 对每行取 `<thr` 的像素的 min/max，看突变定位边界 |
| **最小外接旋转矩形** | **倾斜**的矩形（摇摆柱、斜杆） | `cv2.minAreaRect` 或 scipy 近似 |
| **字形连通域 + 横向膨胀** | 文本行 | 取高度 < 约 26px 的连通域，按 y 重叠分组 -> 得到每行的 x/y 范围 |
| **颜色直方图** | 每个元素的**精确 RGB** | 在元素内部取样，取众数，**不要**目测估色 |

**倾斜矩形有个必踩的坑**：`minAreaRect` 量的是**含描边的外轮廓**。
直接拿它的四个角画线，图形会整体胖约 `lw` 个像素。
正解 -> 按「中心 + 角度 + 内缩」参数化重建：

```python
t = math.radians(ANGLE)
u = (math.cos(t), math.sin(t)); v = (-math.sin(t), math.cos(t))
hw, hh = W/2 - INSET, H/2 - INSET          # INSET 约等于 lw/2，把描边中心线放回原轮廓
pts = [(cx + su*hw*u[0] + sv*hh*v[0], cy + su*hw*u[1] + sv*hh*v[1])
       for su, sv in ((-1,-1),(1,-1),(1,1),(-1,1))]
```

---

## 文本：字号必须**实测标定**，不能套字体理论值

本机 Visio 渲染 Times New Roman 比字体本身的 AFM 宽度**宽约 11%**，而 `Char.Spacing`
又不可用，没法用负字距压缩。所以：

**规则：字号 = 让"渲染出来的墨迹宽度"等于"源图墨迹宽度"的那个值。**

流程：先跑 `scripts/probe_cells.py --cal cal.json`，用 2~3 个参考字号渲染目标字符串、
导出后量墨迹宽度，线性外推：

```python
size_needed = size_ref * target_src_px / measured_src_px
```

其它文本要点：
- 文本框 = 一个 `DrawRectangle` + `LinePattern=0` + `FillPattern=0`（透明）+ `Para.HorzAlign`。
- **不超过 4 个字母的短词（如 "Slab"）不要用宽度反推字号**，边距误差太大；用 cap-height 与宽度折中。
- 导出栅格的 y 是**上下翻转**的，标定脚本里第 i 个 band 对应**最后**画的那个形状——
  对齐错了会得到"字号越大宽度越小"的荒谬结果。
- 混排粗细（如 "Figure 6." 粗体 + 后面常规）-> **两个居中文本框**。

---

## 虚线：不要用 `LinePattern=2`

Visio 的 `LinePattern=2` 渲染成**圆点**，而论文插图里的虚线是**矩形短划**。
-> 手写 `dashed(p0, p1, on, off)`：沿直线按 `on/off` 长度切片，每片画一条 `DrawLine`。
`visio_lib.Fig.dashed` 已实现。破折号长度按源图实测（典型 `on=9, off=2.4` 源像素）。

---

## 收敛判定（第 7 步）

`scripts/compare_render.py` 输出**逐区域 ink 像素比**（复刻 / 源，阈值 `L<200`）：

| 比值 | 判定 | 动作 |
|---|---|---|
| 0.95 ~ 1.05 | 优秀 | 放过 |
| 0.85 ~ 1.15 | 可接受 | 结构类放过；文本类可再调 |
| < 0.80 或 > 1.25 | 不合格 | 回到第 2 步精测该区域 |

**文本区域的比值天生偏低（0.4~0.6），这是正常的**——源图是缩放过的位图，字形笔画比矢量渲染更"胖"。
文本只看**位置和宽度**：字串中心偏差应 < 2 源像素，墨迹宽度比应在 0.9~1.1。

叠加图（红=源、蓝=复刻）里，结构线应该基本重合；出现成对的"红蓝双线"就说明有平移偏差。

---

## 交付物（固定四件 + 脚本）

```
<work>/<Name>.vsdx              <- 原生 Visio，主交付物
<work>/<Name>_preview.png       <- 2 倍源图尺寸的预览（自动配准）
<work>/<Name>_compare.png       <- 左原图 / 右复刻 并排
<work>/<Name>_overlay.png       <- 红蓝叠加
<work>/build_<name>.py          <- 可重跑的生成脚本
```

收尾必做：**重新打开 `.vsdx` 再导出一次，和预览逐像素比对**（`max diff` 应为 0），
证明文件自洽没写坏。然后把 `.vsdx` + 预览 + 两张对比图一起展示。

---

## 工具箱

| 文件 | 作用 |
|---|---|
| `scripts/visio_lib.py` | **底座**：`Fig` 类（画框、坐标换算、poly/line/rect/oval/arrowhead/rrect/dashed/text、保存导出配准、audit） |
| `scripts/measure_image.py` | 像素取证 CLI：分层连通域 / 行列扫描 / 文本行 / 颜色直方图 / 放大裁图 |
| `scripts/compare_render.py` | 并排 + 红蓝叠加 + 逐区域 ink 比 |
| `scripts/probe_cells.py` | 探测可用单元格名 + 文本宽度标定 |
| `references/visio-com-gotchas.md` | COM / 单元格 / 导出 / 沙箱 IO 的完整踩坑与验证记录 |
| `references/pixel-forensics.md` | 像素取证配方详解 + 两张已验证图的完整几何清单（可当标定样例） |

**最小骨架**（复制即用；把 scripts 路径换成你的实际安装位置）：

```python
import sys
sys.path.insert(0, r"<路径>/图片转visio/scripts")   # 换成实际 scripts 目录
from visio_lib import Fig

f = Fig(img_w=362, img_h=333, page_name="My Figure")     # 自动画隐形画框
f.line((19, 263.5), (348, 263.5), lc="RGB(52,52,54)", lw=f.LW(2.0))   # 地面线
f.rect(48, 136, 339, 170.5, fill="RGB(147,150,152)", lw=f.LW(2.0))    # 楼板
f.text(200.5, 24.5, "Rocking Podium Structures", 24.0, w=280, h=22)   # 标题
print(f.audit())                                          # 检查有没有越出画框
f.save(r"...\MyFigure.vsdx", r"...\MyFigure_preview.png")
```

`f.LW(px)` 把源图像素线宽换算成 pt（`px * 1.5`，因为 1 源像素 = 2 导出像素 = 1.5pt 在 96DPI 下）。
