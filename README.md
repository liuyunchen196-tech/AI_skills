# AI技能库

统一的本地技能仓库，供 WorkBuddy、豆包（Doubao）和 MobileWork 共享调用。

## 工作原理

- 统一库现有 40 个技能文件夹；WorkBuddy 侧大部分技能仍是独立真实副本（非全部为联接），新增技能按联接方式接入。
- 运行时依赖（如 OCR 的 venv）放在 `D:\AI技能库\runtime\`，与 `skills\` 分开。
- 三个 AI 的技能目录里放的是**目录联接（Junction）**，指向本仓库，不占额外空间。
- 在本仓库修改技能 = 三个 AI 同时生效；在本仓库新增技能文件夹后，需在三个技能目录各补一个联接。
- ⚠️ MobileWork 侧：联接建好后，需**重启 MobileWork 应用**才会把它同步进系统托管的技能发现投影（`~/.mobilework/xdg/config/opencode/skills/`）和启用列表（`~/.mobilework/skills-enabled/`），新技能才会出现在会话的技能列表里。

## 目录结构

```
D:\AI技能库\
├── README.md          ← 本文件
├── runtime\           ← 运行时依赖（ocr-venv 等，非技能）
└── skills\            ← 全部技能的真实文件
    ├── visio-skill\           （来自豆包：生成/修改 Visio .vsdx 图）
    ├── life-decision-guide\   （来自豆包：人生决策指南问答）
    ├── attach-db\ … xlsx\     （来自 WorkBuddy 的 27 个技能）
    └── …
```

## 2026-11-03 新增：PDF 处理与读取

来自 skills 商店，均为「方法论型」技能：SKILL.md 是主体（处理流程、能力边界、错误码、置信度门控），
`scripts/` 为骨架实现（脚本可导入、自检可跑，但 CLI 只暴露 `--selftest/--dry-run/--verbose/--force`，
真实抽取由 Agent 按 SKILL.md 的流程执行，不提供独立 PDF 引擎）。

| 技能 | 用途 |
|---|---|
| `pdf2md` | PDF → 结构化 Markdown（标题/列表/表格映射、置信度标注、不编造原则） |
| `pdf-inspector` | PDF 体检：判定文本层 PDF / 扫描版 / 混合型，给出后续路由建议（不含 OCR） |

未入库说明：

- 商店里的通用 `pdf`（PDF 文档处理）安装被拒——不在可安装目录中；WorkBuddy 侧已有等价的内建 `workbuddy-pdf`（依赖应用自带 CLI，与 Agent 强耦合，故不复制入库）。
- `pdf-inspector` / `pdf2md` 均不含 OCR，纯扫描件需另配 OCR 技能（商店候选：`scan-pdf-ocr`、`local-ocr-gpu`）。
- `pdf2md/selftest.py` 是模板自检脚本，校验 `slug`/`displayName` 字段，与本库 frontmatter（`name`/`display_name`）不一致会报 AssertionError；这是模板错配，不影响技能本身。真实自检请跑 `python scripts/main.py --selftest`（通过）。

## 2026-11-03 新增：OCR（扫描件转文字）

两个都是**带真实引擎**的技能（RapidOCR / onnxruntime，纯本地离线、不上传），不是方法论壳子。

| 技能 | 定位 |
|---|---|
| `local-ocr` | 通用识别：PNG/JPG/BMP/TIF/WEBP/PDF，单文件或整目录，PDF 自动分流（有文字层直取、无文字层按 dpi 渲染后 OCR），可输出坐标+置信度 |
| `scanned-pdf-ocr-pipeline` | 大文件流水线：先 PyMuPDF 诊断确认真无文字层、批量前预估耗时、OCR 后质量自检、断点续跑（`_pages/` 目录）、`--t2s` 繁转简 |

### 共享运行环境（已部署，一次性）

```powershell
# 环境位置（放在 D 盘，避开 C 盘空间）
D:\AI技能库\runtime\ocr-venv\Scripts\python.exe        # 约 395MB
# 路径已记录在 skills\local-ocr\venv_path.txt

# 通用识别
& "D:\AI技能库\runtime\ocr-venv\Scripts\python.exe" "D:\AI技能库\skills\local-ocr\scripts\ocr.py" "<图片/PDF/文件夹>" [--box] [--out x.txt] [--dpi 400]

# 大 PDF 流水线（第二个位置参数是"输出目录"，不是文件名）
& "D:\AI技能库\runtime\ocr-venv\Scripts\python.exe" "D:\AI技能库\skills\scanned-pdf-ocr-pipeline\scripts\pdf_ocr.py" "<PDF>" "<输出目录>" [--dpi 120] [--t2s]
```

实测（200dpi 模拟扫描件，1 页）：两个脚本均正确识别 `OCR TEST 2026 / Contract No. A-1234 Amount: 5800 / Date 2026-11-03 Page 1`，零错字。

注意事项：

- 两个技能共用同一个 venv（`rapidocr_onnxruntime` + PyMuPDF + pillow 已在其中）。**不要**用系统 Python 直接跑 `pdf_ocr.py`——系统 Python 没装 rapidocr，会 ImportError。
- `venv_path.txt` 与 venv 均为**本机绝对路径**，换机器需重跑 `python skills\local-ocr\scripts\setup.py --venv-dir <路径>`。
- 能力边界：手写体识别差；不还原表格结构（只要文字）；金额/日期/证件号必须人工复核（形近字风险）；单页 CPU 约 1–3 秒。
- 未安装的同类候选：`scan-pdf-ocr`（合同/标书模板+质检清单，方法论型）、`fadada-special-ocr`、`legal-document-ocr`（法律文书，**按页计费**，1 元=10 积分，50 页=5 元）、`local-ocr-gpu`（需 GPU）。

## 2026-11-04 新增：PPT 模板套用三件套

| 技能 | 定位 |
|---|---|
| `ppt-template`（PPT复刻） | 商店技能，美图设计室 designkit CLI 在线通道：按参考PPT复刻版式生成新页面 |
| `ppt-optimiz-fix` | 商店技能，PPT 五维评分 + P0/P1/P2 缺陷分级自动修复（字体统一、图文比审计、去AI味） |
| `jituan-PPT`（集团PPT模板套用） | **自研**：按集团模板（默认 `D:\AIproject\模板.pptx`）把其他PPT内容完整迁入——除目录外内容零改动，目录按实际章节重建（改目录页 AutoShape 文本，不动装饰图形），正文图/文/表按正式公文排版 |

`jituan-PPT` 综合了库内 `ppt-da-nuo-yi`（内容迁移）、`ppt-beautify`/`ppt-polish`（排版规范）、
`ppt-optimiz-fix`（成品体检）的能力，自含两个实测脚本：

- `scripts/analyze_pptx.py`：只读解析双PPT结构（母版/版式/占位符/图片/表格/坐标字号），python-pptx 实测通过
- `scripts/verify_pptx.py`：迁移完整性校验（文本段落/图片哈希/表格单元格逐项比对 + 占位残留检测），对原始模板正确报出"填写标题"等残留项

模板 `D:\AIproject\模板.pptx` 实测结构：16:9，11 页，单母版 7 版式（标题幻灯片/目录_单栏/标题_内容/目录_双栏/1_空白/空白/1_标题_内容）；目录页由 5 个"目录N标题" AutoShape + 装饰组合构成，**非占位符**。

联接：WorkBuddy 侧、豆包 `.user_skills` 侧、MobileWork 侧均已建立。

## 联接位置

| AI | 技能目录 | 联接数 |
|---|---|---|
| WorkBuddy | `C:\Users\liuwust\.workbuddy\skills\` | 9（visio-skill、life-decision-guide、pdf-inspector、pdf2md、local-ocr、scanned-pdf-ocr-pipeline、ppt-template、ppt-optimiz-fix、jituan-PPT） |
| 豆包 | `C:\Users\liuwust\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\` | 45（**全部为联接**，2026-11-12 起无真实副本） |
| MobileWork | `C:\Users\liuwust\.mobilework\skills\` | 73（全部技能 + 上述 3 个新技能） |

## 版本统一说明（2026-10-29 第二次整理）

6 个曾分叉的技能已统一为「跨 Agent 通用版」：

- **统一基底**：以功能最全的 WorkBuddy 完整版为基底，SKILL.md 中的 Agent 专属措辞已改为通用表述。
- **Agent 适配拆分**：Agent 专属适配内容放 `agents/` 子目录（如 `find-skills/agents/workbuddy.md`），SKILL.md 正文保持通用。
- **可选能力标注**：依赖特定平台的能力（如 architecture-flowchart 的超星云盘上传）已在 SKILL.md 标注为"可选步骤"，其他 Agent 跳过并交付本地文件。
- **豆包侧联接**：architecture-flowchart、byai-diagram-designer、find-skills、flowchart-design、interactive-diagram-generator 已替换为联接（两侧同步）。
- **例外**：perfect-world-gs-editor 豆包侧保留带 .git 的原版（用户选择），不参与同步；WB 侧与统一库版本一致。visio-skill、life-decision-guide 豆包侧为原版真实文件夹，内容与库中完全一致。（**2026-11-12 已更新**：豆包侧全部改为联接，perfect-world-gs-editor 的 `.git` 与 data 产物已随库保留在 `skills\perfect-world-gs-editor\`）
- **归档备份**：替换前的豆包原版（含 perfect-world-gs-editor 的 .git 历史与 data 产物）存于 `archive\doubao-versions-20261029\`。

## 已知的 Agent 耦合点（如实标注）

以下技能与 WorkBuddy 环境有较深耦合，在其他 Agent 中可能需要手动调整：

- `ppt-polish-lite`：脚本硬编码 `~/.workbuddy/` 下的 Node/插件路径（其他 Agent 需自备 Node >= 18）
- `ppt-beautify`：依赖 WorkBuddy 内置工具（present_files 等）交付产物
- `attach-db` / `query` / `read-file`：LOCAL-ENV.md 记录了 WorkBuddy 内置 Python 的绝对路径（其他 Agent 换用本机 Python 即可）
- `interactive-diagram-generator`：Node 路径已改为通用表述，优先用 PATH 中的 node

## 常用维护命令

```powershell
# 新增技能到三个平台（以 my-skill 为例）
New-Item -ItemType Junction -Path "C:\Users\liuwust\.workbuddy\skills\my-skill" -Target "D:\AI技能库\skills\my-skill"
New-Item -ItemType Junction -Path "C:\Users\liuwust\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\my-skill" -Target "D:\AI技能库\skills\my-skill"
New-Item -ItemType Junction -Path "C:\Users\liuwust\.mobilework\skills\my-skill" -Target "D:\AI技能库\skills\my-skill"

# 删除单个联接（只删联接，不影响真实文件）
cmd /c rmdir "C:\Users\liuwust\.workbuddy\skills\my-skill"
cmd /c rmdir "C:\Users\liuwust\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\my-skill"
cmd /c rmdir "C:\Users\liuwust\.mobilework\skills\my-skill"

# 恢复原始状态（删除所有联接后，把豆包的 2 个技能复制回豆包目录）
```

## 2026-11-12：豆包侧统一为「全联接」（库成为唯一真实源）

改动前的问题：豆包 `.user_skills` 里 39 个是**真实副本**，而 `D:\AI技能库\skills` 下同名 36 个目录是**空壳**、
另外 3 个（visio-skill / life-decision-guide / perfect-world-gs-editor）是 2026-10-19 及更早的**旧副本**。
结果：库和豆包互不同步，改库不生效、改豆包也不同步。

本次处理（逐个技能校验，非批量盲拷）：

1. 按「库为唯一真实源」把豆包侧真实内容搬到库：先 `robocopy /E` 复制，再逐个文件比对 **SHA256**，
   文件数 + 总字节数双校验一致后才动下一步。
2. 豆包侧原目录改名为 `.__bak`，随后在原位置建 `Junction` 指向 `skills\<技能名>`，再验证联接可读、`SKILL.md` 存在。
3. 全部 45 个技能逐一通过校验后再归档临时备份（**没有就地删除任何内容**）。

结果：

| 项 | 数量 | 位置 |
|---|---|---|
| 豆包侧技能条目 | 45，全部 Junction | `.user_skills\` |
| 库内真实技能目录 | 45，均含 `SKILL.md`、无空壳 | `skills\` |
| 豆包侧原版备份 | 39 个目录 / 18.2 MB | `archive\doubao-user-skills-backup-20261112\` |
| 原库内旧副本（3 个） | 3 个目录 | `archive\skills-stale-20261112\` |

影响：以后在 `D:\AI技能库\skills\` 里改技能、加文件，豆包会话里立即用到的就是这一份（同一份文件，非拷贝）。

### 维护脚本 `relink-skills.ps1`

```powershell
# 只预览（不建任何东西）
pwsh D:\AI技能库\relink-skills.ps1 -WhatIfOnly
# 真正补联接：库里有、目标侧缺的，逐条建 Junction
pwsh D:\AI技能库\relink-skills.ps1
```

脚本默认检查三个位置（豆包 / WorkBuddy / MobileWork），**只创建联接，绝不删除或覆盖**：
目标已是真实目录时跳过并提示，指向别处的联接也会单独列出。

注意事项：

- 豆包新增联接后需**重启豆包客户端或新开会话**，技能列表才会刷新。
- 豆包侧若因商店安装/更新又长出真实副本，会表现为「同名技能两份」，跑一次上面的脚本即可看出（会列入"真实目录"提示）。
- WorkBuddy 侧截至本次仍有 33 个真实副本（见「联接位置」表），未在本轮改动；如需统一，同样先人工确认内容新旧再改联接。
- 单独删除一条联接（只删链接，不动真实文件）：`cmd /c rmdir "<技能目录路径>"`。

---

## 2026-11-13 新增：`BUILD_lhl`（精益建造板块数据建设流水线）

自有技能，非商店来源。把一本图文手册变成「措施库 + 图片库 + 可出 PDF/PPT 的项目」，
并已跑通四类版式、五次素材扩充（房屋建筑分册 → 三局手册 → 住宅指南 2.0 → 优化工艺），
当前沉淀 424 条措施 / 595 张图。

| 组成 | 内容 |
|---|---|
| `SKILL.md` | 五阶段主流程（体检→提取→归一→查重→落库）+ 硬性要求 + 七项验收清单 + 禁止事项 |
| `references/schema.md` | 字段字典（含**信息词条**生成规则）、两库表结构、枚举值、派生字段口径 |
| `references/extract-patterns.md` | 四类版式（框线表格 / 卡片 / A3 多表 / 双栏卡片）的识别与提取要点 |
| `references/divisions.md` | GB 50300 分部分项判定决策树 + 高频关键词映射 + 「措施项目」虚拟分部 |
| `references/pitfalls.md` | 18 条真实故障的「症状→根因→修复」 |
| `assets/divisions.json` | 分部分项标准树（11 分部） |
| `scripts/` | probe / extract_tables / extract_cards / ocr_scan / dedupe / ingest / sync / add_columns / validate |

用法见 `skills/BUILD_lhl/SKILL.md`。WorkBuddy 侧已建立联接，重启会话后可在技能列表中看到。

注意：`extract_tables.py` 对「一格一矩形 + 合并单元格」的复杂表只能做粗提取，
需用 `--probe-cols` 探出列坐标后人工核定，或按表写 `--tables-config`；这一点已写入 SKILL.md。

