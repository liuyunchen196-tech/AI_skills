# Visio COM 自动化踩坑全集

环境：Windows + Microsoft Visio 16.0（典型安装路径 `C:\Program Files\Microsoft Office\root\Office16\VISIO.EXE`，
不同 Office 版本路径可能不同）+ Python 3.x venv（`pywin32` / `Pillow` / `numpy` / `scipy`）。
以下每条都是**实测复现并验证过**的，不是推测。

---

## 1. 不能用 PowerShell 跑 COM

PowerShell 工具会拦截 COM 实例化（"COM object instantiation can run arbitrary code"）。
**所有 Visio 自动化走 Bash + venv Python**：

```bash
PY="/path/to/your/venv/Scripts/python.exe"     # 换成你自己的 venv 解释器
"$PY" build_x.py
```

---

## 2. 必须早期绑定

```python
from win32com.client import gencache
app = gencache.EnsureDispatch("Visio.Application")     # 对
# app = win32com.client.Dispatch("Visio.Application")  # 错 -> DrawPolyline 报"无效的参数数目"
```

`gencache` 会把类型库生成到 `%TEMP%\gen_py`。如果类型库缓存坏了（生成脚本报奇怪的属性错误），
删掉 `%TEMP%\gen_py` 重跑。稳妥写法：

```python
try:
    app = gencache.EnsureDispatch("Visio.Application")
except Exception:
    app = win32com.client.Dispatch("Visio.Application")
```

---

## 3. 方法签名（位置参数个数是硬性的）

| 方法 | 正确调用 | 说明 |
|---|---|---|
| `Page.DrawPolyline` | `page.DrawPolyline(flat_list, 0)` | **2 个位置参数**。`Flags=0`。typelib 签名 `((24581,1),(2,1))`，`24581 = VT_ARRAY|VT_R8`。少传 `Flags` → "无效的参数数目" |
| `Page.DrawLine` | `page.DrawLine(x1, y1, x2, y2)` | 4 个 double |
| `Page.DrawRectangle` | `page.DrawRectangle(x1, y1, x2, y2)` | 两点定义对角；**要自己保证 x1<x2, y1<y2** |
| `Page.DrawOval` | `page.DrawOval(x1, y1, x2, y2)` | 外接矩形 |
| `Page.DrawBezier` | `page.DrawBezier(xyArray, degree, Flags)` | 3 个参数 |
| `Page.Export` | `page.Export(png_path)` | 只有路径一个参数 |

`flat_list` 是扁平的 `[x0, y0, x1, y1, ...]`（Python list 即可，会自动转 SAFEARRAY）。
闭合多边形要**自己把首点重复到末尾**。

---

## 4. 单元格名（本机 16.0 的旧版命名）

用 `scripts/probe_cells.py` 探测，别猜。

| 想要 | **本机正确名** | 常见误写（会失败） |
|---|---|---|
| 填充色 | `FillForegnd` | `FillForegroundColor` → "意外的文件尾" |
| 线端箭头 | `EndArrow` | `LineEndArrow` |
| 箭头大小 | `EndArrowSize` | `LineEndArrowSize` |
| 字距 | **不存在** | `Char.Spacing` → "意外的文件尾" |

可用且常用的：`LineColor` `LineWeight` `LinePattern` `FillPattern` `FillBkgnd`
`Char.Size` `Char.Font` `Char.Style` `Char.Color` `Para.HorzAlign` `VerticalAlign`
`Rounding` `PageWidth` `PageHeight` `PinX` `PinY` `Width` `Height`。

赋值一律走字符串公式：`shp.CellsU("LineWeight").FormulaU = "1.50 pt"`。
读取数值用 `.ResultIU`（英寸）或 `.ResultStr("")`。

**关掉线 / 填充**：
```python
shp.CellsU("LinePattern").FormulaU = "0"     # 无线
shp.CellsU("FillPattern").FormulaU = "0"     # 无填充
```

**线型编号**：`1` 实线 · `2` 虚线（**渲染成圆点**，见 §7）· `3` 点划线。

---

## 5. 沙箱文件 IO：Visio 写不进工作区

`doc.SaveAs(工作区路径)` 抛 "发生异常"；`documents.Open(工作区路径)` 抛 "文件未找到"。
**但 `%TEMP%` 一切正常。**

```python
import tempfile, shutil, os
tmp = os.path.join(tempfile.gettempdir(), "fig.vsdx")
doc.SaveAs(tmp)
shutil.copyfile(tmp, r"...\工作区\fig.vsdx")      # Python 拷贝没问题
```

打开已有 `.vsdx` 做校验时同理：先 `shutil.copyfile` 到 TEMP 再 `Documents.Open`。

---

## 6. 导出取景：`Page.Export` 用的是**可绘制形状的并集**，不是页面

这是最费时间的一个坑。表现：页面明明是 8.54×7.94 in，导出却是 823×478，长宽比 1.72（应为 1.405）。

实测结论：

| 试验 | 结果 |
|---|---|
| 页面留 `PAD=0.5 in` 边距 | 823×478 —— 边距没用 |
| 一个"跳过不可见"的矩形（`LinePattern=0, FillPattern=0`） | 导出 193×97 —— 完全不算 |
| 一个**白色细线**矩形（`LinePattern=1, LineColor=RGB(255,255,255), 0.25pt`） | 导出 816×576 —— **正确锁死** |

**正解**：先画一个白色（本 skill 用 `RGB(253,253,253)`，肉眼同样不可见，但栅格可检测）
细线矩形，四角 = `(0,0) (W,0) (W,H) (0,H)`。它把导出范围钉死在源图区域上。

副作用（好事）：因为它是导出里**最外侧**的东西，"非白像素包围盒的左上角"就等于源图 `(0,0)`，
配准直接 `offset = bbox.topleft`，不需要猜。

**注意**：如果有任何 shape 越出这个画框（尤其文本框溢出），导出范围就会被撑大、配准失效。
`Fig.audit()` 会检查并报警。

---

## 7. 虚线：`LinePattern=2` 渲染成圆点

Visio 内置虚线是**圆点**，而论文插图里的虚线是**矩形短划**。
→ 手写 `dashed()`：沿直线按 `on/off`（源图像素）切片，每片一条 `DrawLine`。
典型 `on=9, off=2.4`（源像素）。代价是 shape 数量上升（一条长虚线约 30 个 shape），可接受。

---

## 8. `Page.Export` 偶发失败

报 `被呼叫方拒绝接收呼叫`。**不是权限问题，是时序问题。**
→ 12 次重试 + `time.sleep(1.0)`，实测总能成功。

---

## 9. 导出分辨率固定 96 DPI

所以 `SCALE = 48 源像素/英寸` → 导出恰好 2×源图像素。
`LW(px) = px * 1.5`（1 源像素 = 2 导出像素 = 1.5 pt @96DPI）。

---

## 10. 收尾三件套 & 清残留

```python
app.AlertResponse = 7      # 禁掉所有弹窗（否则可能挂住）
...
doc.Saved = True
doc.Close()
app.Quit()
```

跑之前先清残留实例，否则新实例会挂：

```python
import subprocess
subprocess.run(["taskkill", "/F", "/IM", "VISIO.EXE"], capture_output=True)
```

`Fig.__init__` 已自动调用。

---

## 11. pywin32 不支持参数化属性赋值

```python
ch = shp.Characters
ch.CharProps(1) = 1          # SyntaxError！pywin32 不支持这种写法
```

→ 粗体/常规混排只能**拆成两个文本框**，各自设 `Char.Style`。

（如果非要在一个 shape 内做混排，可试 `shp.Characters.Begin/End` 后设 `CharProps`，
但在本机实测走不通，不值得投入。）

---

## 12. 文本渲染比字体本身宽约 11%

实测：`"Rocking Podium Structures"` 在 26.5 pt 下渲染 12.34 em，而 AFM 理论值只有 11.056 em。
`Char.Spacing` 又不存在（§4），没法用负字距压缩。

→ **字号一律实测标定**：`needed = size_ref * target_src_px / measured_src_px`。
见 `scripts/probe_cells.py --cal`。

**标定时注意导出栅格的 y 是上下翻转的**：Visio 页面 y 向上、导出图像 y 向下，
所以从上往下数的第 i 个 band 对应**最后**画的那个形状。对齐错了会得到
"字号越大宽度越小"的荒谬结果。

---

## 13. 形状计数与自检

```python
n = page.Shapes.Count
pg.PageSheet.CellsU("PageWidth").ResultIU      # 英寸
```

交付前务必做一次**往返校验**：把 `.vsdx` 拷到 TEMP → `Documents.Open` → 再 `Export` 一次
→ 和交付的预览逐像素比 `max |diff|`，应为 **0**。这能证明文件自洽没写坏。

---

## 14. 工作流节奏

- 一个脚本一次跑完「画 → 存 → 导出 → 配准」，**不要**分多次 COM 交互，容易挂。
- 迭代时每轮只改一处，改完立刻重跑比对脚本。两张已验证的图各迭代了 4~6 轮。
- 脚本失败后 Visio 可能留残留进程 → 下次开跑前 `taskkill`。
