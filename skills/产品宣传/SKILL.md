---
name: 产品宣传
description: 给自研项目/工具/平台制作产品宣传推广 PPT（集团模板风格）。当用户要求"给 XX 项目做宣传 PPT / 推广 PPT / 产品介绍 PPT / 汇报材料"且内容是自研产品或内部工具时使用。负责完整流水线：项目取材（数据统计+真实界面截图）→ 内容组织（六段式结构）→ 集团模板构建 → 逐页渲染复核 → 演讲者备注。
agent_created: true
---

# 产品宣传 PPT 制作

给自研项目制作正式的宣传推广 PPT：集团模板版式（16:9、微软雅黑、中国移动蓝白配色）、
内容全部来自项目真实数据与真实界面截图，产出可直接用于汇报与推广。

构建依赖本机已有的 **jituan-PPT** 技能（`C:\Users\liuwust\.workbuddy\skills\jituan-PPT\`，
真实源在 `D:\AI技能库\skills\jituan-PPT\`），本技能负责其上游的内容组织与下游的复核交付。

## 总体流程

```
① 项目取材 → ② 界面截图 → ③ 内容 JSON → ④ 构建 → ⑤ 渲染复核 → ⑥ 演讲者备注 → ⑦ 交付
```

## ① 项目取材

动笔前必须拿到真实数据，禁止编造：

1. 读项目 `README.md` / 主要源码，弄清产品定位、核心能力、关键流程；
2. 统计硬指标（数据量、文件数、耗时、库数……）——能从数据库/接口实测的实测：
   ```bash
   python -c "import sqlite3; ..."   # 或 curl 接口 /api/meta 之类
   ```
3. 记录页脚/署名信息（单位、部门、版本号）——封面 author 与日期要用；
4. 参考同类旧稿（如有）确定章节划分与口径，例如：
   `D:\AIproject\项目管理平台\推广材料\content_lean.json`（精益建造宣传，六段式标杆）。

## ② 界面截图（全部用真实截图，不用示意图）

按 `references/screenshots.md` 的方法抓取。要点：

- 优先启动项目真实服务，用**无头 Edge + 临时状态注入路由**截取各交互状态；
- 中文路径下必须用 **PowerShell** 调 Edge（Bash 传参会乱码导致静默失败）；
- Excel/表格类素材用 Excel COM `CopyPicture + Chart.Export` 导出 PNG；
- 单文件 HTML 产物先拷到 ASCII 路径再 `file:///` 截图；
- 截完逐张 `ViewImage` 检查：状态是否到位、有无截断，不合格重抓。

一般抓 8~10 张覆盖：首页、列表页、详情页、导航页、检索页、各弹窗、模板/产物。

## ③ 组织内容 JSON

按 `references/content-guide.md` 写 `content.json`（六段式骨架 + 各页 type 选择）。
写法要求：

- 每页都有 `intro` 或 `note`，note 是"结论/升华"，不是重复正文；
- 量化口径标注"保守估算 / 测算样本"，不写绝对承诺；
- 图片路径用绝对路径指向截图工作区；
- 全稿控制在 22~30 页（封面+目录过渡+正文+结尾）。

## ④ 构建

```powershell
python "C:\Users\liuwust\.workbuddy\skills\jituan-PPT\scripts\build.py" content.json --out "D:\...\产品名_产品宣传.pptx"
```

- flow 页默认走 Visio 矢量渲染（需 Visio + pywin32），失败自动回退原生版式；
- 构建日志确认：页数 = 封面1 + 目录N + 正文M + 结尾1，无"回退原生版式"告警（除非预期）。

## ⑤ 渲染复核（必做，不许跳）

```powershell
python <本技能>\scripts\render_pptx.py "成品.pptx" "渲染输出目录" 1400
```

逐页用读图能力检查：

- 封面/目录：文字完整、当前章标红；
- 表格页：表头蓝底白字、无文字溢出、行高合理；
- 图文页：图片等比无变形、图注不压图、元素不重叠；
- KPI/流程页：数字与节点完整；
- 发现硬伤 → 改 content.json → 重新 build，直到合格。

## ⑥ 演讲者备注

```powershell
python <本技能>\scripts\add_notes.py "成品.pptx" notes.json
```

`notes.json` 为 `{"1": "开场讲法", "2": "..."}`（按页码）。
每页一条，写"怎么讲"而不是重复正文；开场页与收尾页要有节奏提示。

## ⑦ 交付

1. `clean_empty_textboxes.py "<成品>.pptx" --info` 应为 0 空 占位符/文本框；
2. `present_files` 打开成品；
3. 汇报：页数、章节映射、截图数量、量化口径说明、素材工作区位置（保留 content.json 与截图，
   便于后续改字重出稿）。

## 陷阱速查

| 坑 | 对策 |
|---|---|
| Bash 传中文路径给 Edge 静默失败 | 一律用 PowerShell 调 Edge |
| 临时注入路由写在 `/?s=` 不生效 | 注入必须走专用路由（如 `/__shot?s=`），普通首页路由不会带脚本 |
| Edge 截图全是同一张首页 | 检查截图 URL 是否用了注入路由、`--virtual-time-budget` 是否够大（≥14000） |
| 编造数据/夸大口径 | 全部实测；测算值标注"保守口径" |
| 截图分辨率低 | `--force-device-scale-factor=2` + `--window-size=1600,1000` |
| 每个截图用独立 `--user-data-dir` | 避免配置目录锁冲突 |

## Resources

- `references/content-guide.md` — 六段式章节骨架、各版式 type 选择表、note/intro 写法
- `references/screenshots.md` — 界面截图完整操作手册（注入模板、Excel COM、单HTML）
- `scripts/render_pptx.py` — PowerPoint COM 渲染复核
- `scripts/add_notes.py` — 批量写演讲者备注
