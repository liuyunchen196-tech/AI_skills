---
name: ppt-deck-studio
version: 1.0.0
display_name: PPT 演示文稿工作站
display_name_en: PPT Deck Studio
description_zh: 把「一键生成演示文稿」与「瑞士国际主义排版规范」两套能力合成一个 PPT 工作站，覆盖从主题输入到 pptx 落盘的全流程。能力一：给定主题/大纲/参考材料，调云端生成接口产出完整演示文稿（scripts/generate.sh 提交、poll 轮询进度、resume 断点续跑）；能力二：按瑞士网格系统（8pt 基线 / 严格对齐 / 留白呼吸感）手工精修版式，含版式库、主题库、组件库、自检清单与内容框架。触发词：做PPT、生成PPT、PPT排版、瑞士风格、汇报演示、提案 deck、把这份材料改成幻灯片。author=xuanpu。
description_en: A unified PPT workstation combining one-click deck generation (submit/poll/resume scripts) with Swiss International typographic discipline (8pt baseline grid, strict alignment, generous whitespace). Covers topic-to-pptx delivery plus layout libraries, themes, components, a self-check checklist, and a content framework. author=xuanpu.
agent_created: true
---

# PPT 演示文稿工作站

两条能力线，按需求选一条或串联使用。

| 能力 | 解决什么 | 核心资产 |
|---|---|---|
| **A 一键生成** | 有主题/材料，要快速出一整副 deck | `scripts/`（generate / poll / resume） |
| **B 瑞士精修** | 要版式专业、可直接汇报的高质量幻灯片 | `references/ppt-*.md`（版式/主题/组件/自检/内容框架） |

## 路由
- 用户要「快速出一版 / 先有个稿」→ **A**
- 用户要「排版专业 / 瑞士风 / 汇报级 / 精修」→ **B**
- 用户要「生成完再精修」→ A → B 串联

---

## 能力 A · 一键生成（scripts）

三支脚本构成完整异步流程：

```bash
# 1) 提交生成任务（主题 + 可选大纲/材料）
scripts/generate.sh "<主题>" --outline "<大纲>" 
# 2) 轮询进度直到完成
scripts/poll.sh <task_id>
# 3) 若中断，断点续跑
scripts/resume.sh <task_id>
```

Windows 环境用同名 `.ps1`（PowerShell）。产出 pptx 落本地目录。

> 提交后**不要**反复重提同一任务（会重复计费/排队），一律先 `poll` 看状态。

---

## 能力 B · 瑞士国际主义精修

核心纪律（违反即不出片）：

1. **8pt 基线网格**：所有元素间距、字号、行高都是 8 的倍数。
2. **严格对齐**：左对齐为主，禁止居中乱排；元素边缘必须落在网格线上。
3. **留白即呼吸**：内容不超过版心 70%，四周留白是设计的一部分。
4. **字体克制**：一套无衬线走到底，最多两级字重，禁混 3 种以上字体。
5. **色彩节制**：主色 1 + 辅助 1 + 中性灰阶，禁止彩虹配色。

### 资产清单

| 文件 | 内容 |
|---|---|
| `references/ppt-layouts-swiss.md` | **瑞士版式库**（8pt 网格下的各类版面骨架） |
| `references/ppt-solution-v3.md` | 解决方案型 deck 的完整方法论 |
| `references/ppt-content-framework.md` | 内容框架（论点 → 论据 → 结论的页面分配） |
| `references/ppt-deck-generator.md` | deck 生成器用法 |
| `references/ppt-pptx-generator.md` | pptx 落盘生成器用法 |

### 工作流
1. **定框架**：读 `ppt-content-framework.md`，把材料拆成「结论页 / 论证页 / 数据页」三类，先定页数与骨架。
2. **选型版式**：从 `ppt-layouts-swiss.md` 挑匹配每页内容的版式（标题页 / 图文 / 数据 / 引用 / 全图）。
3. **填内容**：按 8pt 网格填，每页只讲一件事，禁文字墙。
4. **自检**：逐页过瑞士纪律五条（网格 / 对齐 / 留白 / 字体 / 色彩），不过就改。

---

## 红线
- 作品署名统一 **xuanpu**，不带第三方署名。
- 瑞士精修必过 8pt 网格与对齐自检，不达不出片。
- 生成任务提交后先 poll 再决定下一步，不重复提交。
- 汇报型 deck 首页必须有结论，不把结论藏到最后。
