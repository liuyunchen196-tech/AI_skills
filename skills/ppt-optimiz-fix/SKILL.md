---
name: ppt-optimiz-fix
display_name: PPT 优化修复顾问
display_name_en: PPT Optimizer & Fixer
description_zh: 对已有 PPT（.pptx）做专业评估、量化打分与自动修复的技能，涵盖五维评分、P0/P1/P2 缺陷分级、字体统一、金字塔原理、图文比审计、去AI味检测与复评闭环。
description_en: Evaluates, scores and auto-fixes existing PowerPoint (.pptx) decks with five-dimension scoring, P0/P1/P2 defect grading, font normalization, pyramid-principle checks, de-AI polish and multi-round re-review.
metadata:
  title: PPT 优化修复顾问
  display_name: PPT 优化修复顾问
  display_name_en: PPT Optimizer & Fixer
description: 对现有 PPT（.pptx）做专业评估、量化打分与自动修复的技能。当用户要求「评估/审查/体检/打分 PPT」「修正页码/章节/重复页」「统一字体/规范版面」「补齐执行摘要/ROI/行动页」「去AI味/去AI痕迹/人工化润色/更像人工」「金字塔原理/结论先行/Action Title/MECE」「字体规划/字阶字重」「图文比/图压字」「10阶段流程/结构化作业流程」时使用。具备：五维评分、P0/P1/P2 缺陷分级、字体统一强制（--normalize-font）、字体规划套用（--apply-font-plan）、细节审计（字阶/越界/配色/字号阶梯 conformance）、金字塔体检（Action-Title 占比/全局结论/MECE）、图文比≤40% 审计、去AI味检测与修正要点（界面模板感+文本机械化过渡/黑话套话/过度排比/空洞抽象）、自动修复流水线（页码校正/PART 修正/重复页清理/字体归一/zip 清洗）与 python-pptx 关键避坑、复评与多轮闭环（标题序列 diff / 旧问题 grep 追踪 / 问题流转表）。触发词：PPT评估、PPT审查、PPT体检、PPT质量、统一字体、修正PPT、修复PPT、规范版面、去AI味、人工化、去AI痕迹、金字塔原理、结论先行、Action Title、MECE、字体规划、图文比、图压字、10阶段流程、结构化作业、复评、多轮复评、版本对比、问题流转、标题序列对比、diff、QA 计数对比、视觉缺陷计数、文字溢出检测。
version: 1.0.0
category: 效率办公
author: lovebuddy
license: MIT
agent_created: true
---

# PPT 优化修复顾问（专业版 v1.0.0）

对**已有 PPTX** 做「评估 → 分级 → 修复」闭环。所有判定均基于 XML 字段核验，不靠肉眼；修复可全自动落地硬伤并按需补强结构。适用：企业汇报 / 培训 / 投标 / 咨询稿的专业化润色。

## 0. 环境与约束
- 运行环境：隔离 venv 的 python-pptx（首次 `python -m pip install -r requirements.txt`；其中唯一第三方依赖为 `python-pptx>=1.0.0`）。脚本统一用该 venv，勿用系统 python。
- 文件锁（零外部依赖处理）：预览/WPS 占用中的文件无法原地写回，本技能一律用 python-pptx **另存新文件**（`--out`）规避——`run_all.py --mode optimize` 产出 `<原名>_修订.pptx`、复评中间产物落 `--work` 目录。无需安装任何其他技能或编辑器插件即可工作；若用户坚持原地编辑，再由用户自行决定，不在本技能依赖范围内。
- 备份先行：任何修改前复制原文件到 `backups/`（`run_all.py --mode optimize` 会自动执行）。

## 0.5 一键编排器 `run_all.py`（推荐入口）
为把多脚本调用收敛为单命令、直接提升易用性，新增 `scripts/run_all.py`：

```bash
python scripts/run_all.py <deck.pptx> --mode assess     # 诊断 + 自包含 HTML/MD/JSON 评估报告
python scripts/run_all.py <deck.pptx> --mode optimize --font 微软雅黑   # 诊断 → 自动修 P0 → 再评估
python scripts/run_all.py <deck.pptx> --mode deai       # 去AI味要点报告
python scripts/run_all.py <deck.pptx> --mode all        # assess + optimize + deai
python scripts/run_all.py --rereview --old 旧版.pptx --new 新版.pptx   # 跨版本复评闭环
python scripts/run_all.py <deck.pptx> --mode assess --aud-terms 行业词库.json   # 用外部术语表（适配特定行业）
```

`--mode optimize` 会备份原稿到 `backups/`，并生成 `<原名>_修订.pptx` 与对应的评估报告。**报告由技能直接生成文件（`<原名>_评估报告.html` 等同目录），无需运行任何额外命令，你直接打开该 HTML 即可查看**——Agent 也会直接将报告呈现给你。`--aud-terms <json>` 可传入外部术语表覆盖内置默认（适配医疗/金融等特定行业的 ROI/CTA/管理者语言词库，见 `references/aud-terms.default.json`）。

首次安装环境：`python -m pip install -r requirements.txt`（唯一第三方依赖：`python-pptx`）。

## 1. 诊断（每任务第一步，全 XML 核验）
运行 `scripts/inspect_pptx.py <file>`（或 `run_all.py --mode assess`），输出两块：
- **结构**：页数 / 尺寸 / sldNum 自动页码占位符 / 每页页脚数字与绝对序号是否错位 / PART 章节标签 / 标题（查重复）/ 图表数。
- **细节审计（专治"粗糙"）**：
  - 字体统一度：列出全篇字体族及数量，>2 字族即提示混搭；
  - 字阶：封面/内容页标题最大字号，内容标题 <28pt 标红；
  - 越界：任一图形超出画布即列出坐标；
  - 配色：有彩色相族数（中性灰不计），>4 提示偏杂。

判定问题**必须引用 inspect 输出**，页码类以字段为准，不靠肉眼。

## 2. 质量评估（用户要"评估/打分"时）
### 五维评分（各 1–5，总分=平均）
| 维度 | 核心判据 |
|---|---|
| 结构逻辑 | 金字塔清晰、Action Title 一页一念、MECE、有执行摘要 |
| 内容深度 | 数据/案例密度、技术正确、证据链完整 |
| 受众适配 | 管理者语言（价值/成本/风险）、ROI 量化页、CTA 行动收口页（责任人/时间表） |
| 视觉呈现 | 图表原生度、文字密度、留白、配色一致、页码/章节正确 |
| 说服力 | 量化 ROI/回收期、有 CTA/责任人/时间表、开篇立论 + 结尾闭环 |

判级：≥4.2 董事会级；3.5–4.2 良好需修校；<3.5 需重构。

### 受众适配 / 说服力 自动信号（v1.0.0）
为降低人工复核负担，`inspect_pptx` 已内置可量化关键词库：

- **ROI 量化页检测**：扫描「ROI / 投资回报 / 回收期 / 回本 / 收益率 / 投入产出 / NPV / IRR」等收益量化词；命中则受众适配与说服力自动加分，并在评分依据中给出具体页码；未命中则列为 P1 缺陷「缺量化 ROI/回收期页」。
- **CTA 行动收口页检测**：识别标题命中（下一步/行动/落地/时间表/计划/责任/跟进 等）或单页同时出现 责任主体（责任人/负责人/Owner/落地/分工）+ 时间节点（时间表/里程碑/截止/交付时间/日期）的页面；命中则受众适配/说服力加分；未命中则列为 P1 缺陷「结尾无明确责任人与时间表」。
- **管理者语言密度**：统计全篇「价值 / 成本 / 风险 / 效率 / 投入 / 回报」等决策层词汇密度；达到阈值时给出正面信号。

这些信号让受众适配/说服力两维从「手拍/人工复核」升级为「自动检测 + 人工兜底」，明显减少复核工作量。

术语表已**外置为可配置 JSON**（`references/aud-terms.default.json`），含 `roi_terms / cta_title_hint / owner_key_set / timeline_set / manager_terms` 五组。复制该文件、按行业改写对应词表，通过 `inspect_pptx.analyze(aud_terms_path=...)` 或 `run_all.py --aud-terms 行业词库.json` 传入即可，无需改代码；缺省或加载失败自动回退内置默认。

### 对标基准
- 麦肯锡金字塔：结论先行作标题、一页一念、MECE；
- Gartner BOARD：Brief / Accurate / Relevant，用业务语言谈成本风险；
- 董事会级 AI 范式：核心 15–18 页、每页 ≤12 词 so-what、结尾必带 Owner+Date；
- AI Agent 案例五步：场景→痛点→方案→价值(量化)→展望。

### 缺陷分级（报告据此组织）
- **P0 硬缺陷（必修）**：页码错乱、PART 误标、重复页/重复标题、zip 损坏、事实错误。
- **P1 结构缺陷（应修）**：缺执行摘要、无 ROI 量化、结尾无 CTA/责任人/时间表、无篇章收口、受众重心偏移。
- **P2 打磨项**：文字过载、品牌词错置、视觉不一致、版式细节、单页图文比 >40%（图压字）、金字塔 Action-Title 占比 <80%。

### 评估报告（report_pptx.py 自动生成）
运行 `scripts/report_pptx.py <file>` 产出**自包含 HTML**（默认 `<原名>_评估报告.html`，同目录；支持 `--md`/`--json`）。结构层次分明、推理链严谨：
1. **概览卡**：源文件 / 页数 / 尺寸 / 总分(1–5) / 判级 / 缺陷计数(P0·P1·P2·观察) / 一句话结论；
2. **五维评分卡**：每维 分数 + 「评分依据」(挂具体证据) + 亮点 + 问题——**分数由诊断发现推导，非手拍**；受众适配/说服力两维已接入自动信号（ROI 量化页 / CTA 责任人+时间表 / 管理者语言密度），人工复核仅作兜底；
3. **缺陷清单**：按 P0→P1→P2→观察 分组，每条含 **维度 / 页码定位 / 证据 / 影响 / 建议** 四段推理链，帮助快速定位与理解；
4. **分维度详述**：内容 / 排版 / 逻辑 / 视觉，逐条定位；
5. **亮点 / 行动优先级 / 对标说明 / 复评提示**。
排比检测已对教学/清单类有序步骤降级为「观察」（非硬缺陷）；全篇 0 图等视觉信号显式呈现。

精细 10 分制锚点、硬伤速查表与报告/问题流转表模板见 `references/review-rubric.md`；需要**跨版本复评 / 多轮追踪**时见 §10。

## 3. 修正（用户要"修改/修复/规范"时）
### C0 先修 P0（可全自动）
1. **页码全局校正**：`fix_pptx.py <path>` 将右下角页脚数字改写为绝对序号（保留首 run 格式）；任何系统性偏移均可修。
2. **PART 标签修正**：`--part-fix "17:旧=新"`（由诊断定）。
3. **重复标题页删除**：`--delete-dupes`（保留首个）。
4. **字体统一强制（核心能力）**：`--normalize-font "微软雅黑"` 将全篇所有 run 统一为指定字体（同时写 latin+ea，消除中文混搭/缺字）。
5. zip 清洗内置：去重 + 剔除孤立 slide 部件 + 清理 rels，防 PowerPoint 报修复。

### C1 再补 P1（结构补强，按需新增页）
- 执行摘要（Answer-First，3–4 条，引用稿内既有锚点，不虚构）；
- 篇章收口（每篇末"要点回顾"3 条）；
- ROI/回收期页（成本/收益框架+区间+柱状图，示意值标注"以实测替换"）；
- 下一步行动页（三步+【姓名/部门/日期】占位），置结尾前。
- 新增页采样原稿主题色/字体，沿用其页脚惯例。

### C2 校验（交付前必做）
重载修正文件，确认：①页码=绝对序号 0 错位；②zip 无重复；③重复标题消除；④新增页文本完整；⑤字体已统一（inspect FONT UNITY 复核）；⑥文件可正常打开。

## 4. 版面与字体设计准则（修复/评估的标尺）
完整方法论见 `references/layout-font-guide.md`，要点：
- **网格对齐**：3 栏/12 列隐形网格，同类型元素全篇对齐一致，每页 1 个视觉焦点。
- **留白**：≥30%，每页 ≤6 行、每行 ≤12 字（6×6）。
- **字体系统（核心）**：全篇 ≤2 字族；中文首选 微软雅黑(安全)/思源黑体(大气)/思源宋体(权威)；字号阶梯 封面40-48·标题32-36·副标24-28·正文18-24·图注14-16·页脚10-12；层级靠字重+字号+颜色；行距1.2-1.5；标题加宽字距 +0.3~0.8pt。
- **配色**：60-30-10，主色 ≤3，强调色仅用于最该被看见的一项。
- **信息层级**：每页一念，标题即结论（完整句、≤15 词）。
- **质感图表**：渐变/阴影克制；图表去网格、系列直标、关键项强调。
- **版面体检 8 项清单**：标题唯一+≥28pt / 正文≥16pt / 字体≤2 / 页边距≥10%且无越界 / 主色≤3 / 对齐一致 / 单焦点 / 页码正确+对比≥4.5:1。

## 5. 内容结构与版面规划增强（F 体系）

在 D（版面字体）与 2（五维评估）之上，新增三项**可量化、可自动检测**的内容/版面硬指标，使"结构逻辑"与"字体一致性"从经验判断转为字段核验。

### F1 金字塔原理（结构化叙事）
- **核心原则**：①结论先行——每页标题是完整句结论（Action Title），不是话题标签；②以上统下——页内要点支撑该页中心论点；③MECE——要点互不重叠、彼此穷尽；④纵向疑问/回答链、横向归纳分组（SCQA 可用作开场：Situation 背景→Complication 冲突→Question 问题→Answer 回答）。
- **自动检测**（`inspect` 的 PYRAMID / ACTION-TITLE AUDIT）：判定每页标题是否"结论式"（含断言动词如 是/等于/在于/让/用/能/成为/提升/解决/表明，或以句号/感叹号/问号结尾，且 ≤15 词）；统计 Action-Title 占比；列出"话题式标题"（概述/背景/案例分析/总结/目录/致谢 等）；另检"全局结论"——封面或执行摘要是否有一句话点题。
- **判级**：内容页 Action-Title 占比 ≥80% 为优；60–80% 需修；<60% 叙事偏"说明文"，建议重构。
- **修复**：把话题标题改写为结论句（谁+做什么+带来什么）；补全局结论页/句。

### F2 字体规划（Font Plan）
- **字体规划表（每角色明确 6 要素）**：

  | 角色 | 字体 | 字重 | 字号(pt) | 字色 | 行距/字距 |
  |---|---|---|---|---|---|
  | Display 封面主标 | 微软雅黑 | Bold | 40–48 | 深蓝/白 | 字距 +0.8 |
  | Title 内容页标题 | 微软雅黑 | Bold | 30–36 | 深蓝 | 字距 +0.6 |
  | Subtitle 副标 | 微软雅黑 | SemiBold | 18–24 | 灰 | — |
  | Body 正文 | 微软雅黑 | Regular | 14–18 | 近黑 | 行距 1.2–1.5 |
  | Caption 图注 | 微软雅黑 | Regular | 12–13 | 灰 | — |
  | Footer 页脚 | 微软雅黑 | Regular | 10–11 | 浅灰 | — |
  | Kicker 章节标签 | 微软雅黑 | Bold | 11–12 | 强调色 | 字距 +0.3 |

- **通用引擎（核心）**：`--apply-font-plan plan.json` 由 `scripts/fontplan.py` 按**位置 + 字号**自动推断每个 run 的角色，**真正通用、不依赖关键词**——拿来即用，无需你事先知道稿子里有什么词。判定维度：
  - 位置（版面区域）：底部 15% = footer / 顶部 15% = kicker / 其余 = body；
  - 位置（页序）：封面 first / 非封面 content；
  - 字号（标题带内最大）：仅在**顶部 30% 标题带**内取最大，避免底部大号装饰/统计数字抢占「标题」角色；
  - 页码：纯数字且位于页脚/页眉角 → 真实页码（Footer），与步骤号区分。
  - 每个 run 按 rules **自上而下首个全维度命中**的规则套用；可选 `when.match:"关键词"` 仅作高级覆盖。
  - **非破坏性默认**：规则只套用写出的字段；默认规划的 `Body` 不写 `size`，只统一字族/字色，**保留稿内原有正文字号层级**，绝不会把大号装饰数字压成 15pt 或把标题压成小字。
  - `inspect` 的 FONT PLAN 段会**预览**角色分布（按位置/字号推断，不改文件），套用前即可核对命中是否合理。
- **铁律**：全篇 ≤2 字族；同角色跨页完全一致；标题与正文字重差 ≥1 级（靠字重而非全边框拉层级）。

### F3 图文比 ≤40%（视觉占比）
- **原则**：文字为主、图像为辅；单页图片占用面积 ≤ 幻灯片总面积 40%；超则压缩图、改图表/要点、或拆页；0 图纯字墙页提示"关键页是否需图示化"。
- **自动检测**（`inspect` 的 IMAGE-TEXT RATIO）：逐页算 图片面积/总面积，标 >40% 的页；分级：≤30% 优 / 30–40% 可接受 / >40% 偏图需修。
- **修复**：超占比页——去背景大图改色块、图缩至一侧、关键图保留其余转文字要点。

完整方法论（金字塔 SCQA/MECE 模板、字体规划样例、图文比测算）见 `references/content-structure-guide.md`，示例规划见 `references/font-plan.default.json`。

## 6. 去AI味（人工化润色）（E 体系）
让 AI 生成的 PPT 在**视觉**与**文案**两层都呈现"人工打磨"质感，消除典型 AI 痕迹。完整方法论见 `references/de-ai-guide.md`。

### 触发与输出红线（务必遵守）
用户要"去AI味/人工化/别像AI生成"时，**输出必须明确覆盖两类修正要点**：①界面风格优化（版式/配色/字体/间距/层级）；②文本去AI化（过渡句/黑话/排比/空洞）。两类缺一不可。

### E1 界面去AI化（视觉人工质感）
六原则（打破生成器审美）：①打破绝对对称，主从不对称+故意留白偏移；②版式有节奏变化（同章节微调卡片数/位置/图文互换）；③配色有呼吸（60-30-10 故意倾斜、强调色只点一处、掺低饱和"脏"色）；④字体有性格（标题用有特征中文字体点睛、拉大字重对比、标题紧字距正文松行距）；⑤细节有手作感（非几何图标、非贯穿分隔线、标签位置微变化、真实截图/批注元素）；⑥层级靠对比而非靠框（减全边框卡片，多用留白+对齐+字号）。
- **检测**：`inspect_pptx.py` 的 AI-TELL SCAN 计算每页版式签名，>70% 内容页一致即判模板感重。

### E2 文本去AI化（文案人工质感）
**AI 味体检清单**（inspect AI-TELL SCAN 自动标出）：
- P0 硬痕迹：机械化过渡句（`总而言之/综上所述/值得注意的是/毋庸置疑/随着…的发展/首先…其次…再次…最后`）；黑话套话单页 ≥3 个（`赋能/打造/闭环/抓手/底层逻辑/范式/护城河/组合拳/方法论/痛点/颠覆/重塑/生态/飞轮/链路/矩阵…`）。
- P1 软痕迹：过度工整排比（≥3 条字数/结构高度一致）；空洞抽象（`提升效率/优化体验/创造价值` 无具体主语/数字/场景）；千篇一律模板感。
- P2 打磨：案例"假设化"（`例如某企业通过…`）、数据无来源/无单位。
**改写六法**：砍过渡句、破排比、给具体、换人话、加视角（踩坑/反例/现场提问）、叙事有起伏。前后对照见参考文档。

### E3 输出格式（去AI味修正要点）
运行 `deai_pptx.py <file>` 生成报告，结构固定为：
- **A. 界面风格优化要点**：位置(页/区域) / 问题(模板感/对称/配色均匀) / 改法。
- **B. 文本去AI化要点**：表格列 页 / 类型 / 原句(样例) / 建议改写。
两类必须同时呈现；文本改写由人工/智能体按要点落地，界面变化回到生成脚本或手动调整版式。

## 7. 交付规范
- 命名：`<原名>_修订.pptx` / `<原名>_字体已统一.pptx`；原文件与备份均保留。
- 附**修订说明清单**（改了什么、证据、未动原因）。
- 提醒：发布前替换占位符（ROI 示意值、【姓名/部门/日期】）。
- 品牌词等厂商话术默认不删，除非用户明确要求。

## 8. 结构化作业流程 · 10 阶段 SOP（G 体系）

技能对任一 PPT 的标准作业程序，确保"评估→修复"不漏项、可追溯；阶段 9 后可回跑 2–7 形成闭环。最快入口：`python scripts/run_all.py <deck.pptx> --mode all` 一次跑完 2–7 阶段并产出评估报告 + 修复稿 + 去AI味要点。

| 阶 | 阶段 | 主要动作 | 工具 / 产物 |
|---|---|---|---|
| 1 | 接稿与目标对齐 | 明确受众/场景/核心结论/页数约束/去AI化程度 | 需求确认 |
| 2 | 结构诊断 | 页码/PART/标题重复/图表/sldNum 错位 | `inspect` 结构块 / `run_all.py --mode assess` |
| 3 | 五维量化评分 | 结构逻辑/内容深度/受众适配/视觉/说服力（受众/说服力已自动信号化） | 五维卡 + 判级 |
| 4 | 金字塔体检 | Action-Title 占比、全局结论、MECE | `inspect` PYRAMID |
| 5 | 字体规划审计 | 字族数/字阶/字号阶梯 conformance | `inspect` FONT PLAN |
| 6 | 版面细节审计 | 越界/配色/留白/网格/图文比 | `inspect` DETAIL + IMAGE-TEXT |
| 7 | 去AI味扫描 | 过渡句/黑话/排比/空洞/模板感 | `inspect` AI-TELL + `deai_pptx.py` / `run_all.py --mode deai` |
| 8 | 缺陷分级与报告 | 归 P0/P1/P2，出 HTML/要点报告 | `report_pptx.py` / `run_all.py --mode assess` |
| 9 | 自动修复硬伤 | 页码/PART/删重/字体归一/zip + 按字体规划套用 | `fix_pptx.py` / `run_all.py --mode optimize` |
| 10 | 复检与交付 | 重载校验 6 项 + 修订清单 + 占位符提醒 | 复检报告 / `run_all.py --mode all` |

阶段 10 后若需**跨版本追踪问题修复情况（多轮复评）**，进入 §10 复评与多轮闭环。

## 9. 关键坑（务必遵守）
1. **部件名撞名**：删页后再 add_slide 会复用名→覆盖。先加新页(从 max+1)、后删旧页；重排用 desired 索引一次性重建 sldIdLst。
2. **孤立部件**：删页后其部件仍序列化→保存必须 zip 级清理（脚本已内置）。
3. **文件锁**：占用中写不回→一律另存新路径（`--out`），不依赖任何外部编辑器；如实告知用户原文件被占用。
4. **editor_sdk 样式重置**：find_replace 会清空 run 样式→之后 `slide_set_text_property` 恢复，编辑后勿主动 close_file。
5. **页码识别边界**：仅右下角 bbox 内纯数字是页脚；章节号/步骤号/象限号不可动。
6. **页脚改写保留格式**：只改首 run 文本并清空其余 run，不重建 text_frame。
7. **sldNum 占位符**：若存在自动页码，手工无需也不能改；错位多半来自"手动文本框+自动占位符并存"，需单独判断。

## 10. 复评与多轮闭环（Re-review）

当用户拿**更新后的 deck** 回来，要求「复评 / 重新评估 / 对比上一版 / 看问题是否修复 / 问题流转」，进入本模式。它复用 §1/§2 的诊断与评分能力，并新增**跨版本 diff 追踪**——这是与单次评估最大的区别。本能力由 `pptx-deck-evaluation` 技能的评估方法论合并而来。

### 10.1 前置
- 保留上一轮的 **文本 dump**（`dump_text.py` 产物）与**评估报告**（从中提炼问题特征串）。
- 若上一轮 dump 丢失，用当前旧版 pptx 重新生成一份归档。

### 10.2 复评流程
1. **核对源文件真更新**：`ls -la` + `date` 比对 mtime/size；未变则直接告知"无需复评"，不要白跑管线。
2. **生成新旧 dump**：`python dump_text.py <old.pptx> old_dump.md` 与 `python dump_text.py <new.pptx> new_dump.md`（格式 `=== SLIDE N ===`，`title_diff.py` 依赖此格式）。
3. **标题序列 diff**：`python title_diff.py old_dump.md new_dump.md` → 识别增页/删页/标题修改 + 同区间页码映射（供聚焦目检）。
4. **旧问题标记 grep**：从上轮报告每条问题提炼特征串（如「请以贵司」「五步」「3000 万」），`python title_diff.py --grep new_dump.md "请以贵司" "五步" "3000 万"` → 逐条判定 已修 / 未修。
5. **QA 计数对比（逐页视觉缺陷增减）**：先生成两份 JSON——`python qa_pptx.py <old.pptx> --out old_qa.json` 与 `python qa_pptx.py <new.pptx> --out new_qa.json`，再 `python title_diff.py --qa old_qa.json new_qa.json` 量化 blocking / off_slide / text_overflow 的逐页增减（含 `仅旧版 / 仅新版 / 仍存在` 三态集合）。`qa_pptx.py` 已内置于本技能，按 title_diff 的 JSON 契约自研（纯 python-pptx，零外部依赖），无需外部脚本。
6. **聚焦目检**：只读变更区域 + 上轮缺陷点位（参考 §1 诊断结论），逐项核对。
7. **复评报告**：在 §2 报告基础上增加「版本对比」章节——**修对的 / 未动的老问题 / 新引入的问题**；多轮复评追加「问题流转表」（模板见 `references/review-rubric.md` §六）。

### 10.3 评分与净效果
- 仍按 §2 五维评分（或 `references/review-rubric.md` 的 10 分制精细锚点）。
- 给出「净效果」判断：修对数量 vs 删错/新增数量 → 净效果为正/负。

### 10.4 关键坑
- 复评前**必须双查 mtime/size**，避免重复劳动。
- 页码提取是启发式（页脚纯数字≠页码，可能混入章节号），以目检为准；报告页码须与视觉一致。
- 每个维度分数须带证据锚点（具体页/具体发现），不给无依据分。
- 删页一致性：回顾页/总结页引用的内容页若已删除，复评须专项核对（"翻页即被抓包"矛盾）。

## 参考脚本
- `scripts/run_all.py <deck.pptx> [--mode assess|optimize|deai|all] [--out DIR] [--font 字体] [--plan plan.json] [--delete-dupes] [--aud-terms JSON]`：一键编排器（P0 易用性），把 inspect/report/fix/deai 多脚本收敛为单命令；报告由技能直接生成 HTML 文件，无需额外命令打开；`--aud-terms` 传外部术语表 JSON（适配特定行业）；也支持 `run_all.py --rereview --old OLD.pptx --new NEW.pptx`
- `scripts/inspect_pptx.py <path> [--json <out.json>]`：结构诊断 + 细节审计（字体/字阶/越界/配色）+ FONT PLAN（字号阶梯 conformance）+ PYRAMID/ACTION-TITLE AUDIT（结论式标题占比/话题式标题/全局结论）+ IMAGE-TEXT RATIO（图文比≤40%）+ AI-TELL SCAN（去AI味前置检测：过渡句/黑话/排比/空洞/模板感）+ 受众/说服力自动信号（ROI/CTA/管理者语言）；`analyze()` 返回结构化结果，供报告生成器消费
- `scripts/report_pptx.py <path> [--html <out.html>] [--md <out.md>] [--json <out.json>]`：评估报告生成器（消费 inspect 结构化数据，产自包含 HTML/MD）；含五维评分推导、P0/P1/P2/观察 缺陷清单（证据→影响→建议推理链）、分维度详述、亮点、行动优先级
- `scripts/fix_pptx.py <path> [--out <dst>] [--part-fix "N:旧=新"] [--delete-dupes] [--normalize-font "字体"] [--apply-font-plan <plan.json>]`：页码校正 / PART / 重复页 / 字体统一 / 字体规划套用 / zip 清洗
- `scripts/deai_pptx.py <path> [--out <report.md>]`：去AI味修正要点报告（界面优化 + 文本去AI化两类要点）
- `scripts/ai_tells.py`：去AI味共享词库 + 扫描器（被上述两脚本复用）
- `scripts/dump_text.py <input.pptx> [--out <dump.md>]`：将 pptx 全文 dump 为 `=== SLIDE N ===` 格式（文本框/表格/备注），供 `title_diff.py` 复评对比使用
- `scripts/title_diff.py <old_dump.md> <new_dump.md>`：复评三合一对比（标题序列 diff / 旧问题 grep / QA 计数对比），详见 §10
- `scripts/qa_pptx.py <input.pptx> [--out <qa.json>] [--pretty]`：逐页视觉 QA，检测 text_overflow（文字溢出文本框）/ off_slide（形状越出画布），输出 title_diff.py --qa 所需的 JSON（含 layout.blocking_findings / layout.warnings / finding_count / error_count / warning_count / valid）；对 PowerPoint 自动适配（auto_size≠NONE 或 word_wrap=False）做豁免以免误报
- `scripts/make_sample_deck.py [out.pptx]`：生成带典型缺陷的样例 deck（用于验证与 SkillHub 门面截图）
- `references/layout-font-guide.md`：版面与字体设计完整方法论（D1–D7）
- `references/de-ai-guide.md`：去AI味（界面+文本）完整方法论与前后对照示例
- `references/content-structure-guide.md`：金字塔原理（SCQA/MECE）+ 字体规划角色表 + 图文比测算与修复完整方法论
- `references/font-plan.default.json`：字体规划通用示例（零关键词，纯位置/字号匹配规则），`fontplan.py` 读取它做角色推断与套用
- `references/aud-terms.default.json`：受众/说服力自动信号术语表（roi_terms / cta_title_hint / owner_key_set / timeline_set / manager_terms），复制改写后通过 `--aud-terms` 传入即可适配特定行业，缺省回退内置
- `references/review-rubric.md`：复评与评估精细细则（10 分制锚点 / 硬伤速查表 / P0-P1-P2 / 报告模板 / 问题流转表），合并自 pptx-deck-evaluation
- `assets/PPT优化修复顾问_Skill专家评估报告_v1.0.0.html`、`assets/企业AI办公提效_样例_评估报告.html`：评估报告样例（自包含 HTML），SkillHub 简介门面
- `assets/企业AI办公提效_样例_评估报告.json`：上例对应的结构化评估结果样例（可与 HTML 对照查看）
- `requirements.txt`：唯一第三方依赖 `python-pptx>=1.0.0`，`pip install -r requirements.txt` 一键装环境
