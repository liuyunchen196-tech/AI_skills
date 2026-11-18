---
name: byai-diagram-designer
display_name: 流程图设计助手
display_name_en: "Diagram Designer"
description: "一句话需求到自包含 HTML 流程图：从自然语言描述或 Mermaid 文本自动生成 10 大类技术图（系统架构、流程、时序、生命周期、决策、矩阵、对比等），自包含 HTML 内联 SVG，正交路由 + 零交叉 + 自动避让标签，含 12 套原创视觉风格、AI/Agent/UML 语义形状库、40+ 产品图标，交互查看器支持 focus/上下游可达/分享卡，校验器按 9 类硬契约给出 ERROR/WARNING。触发词：流程图、架构图、时序图、状态图、决策图、对比图、思维导图、组织结构图、UML、架构师画图、画个架构、画个流程、技术绘图、Diagram、Architecture、Flow、Sequence、draw、graph、visualize。"
description_zh: "一句话需求到自包含 HTML 流程图：自然语言描述或 Mermaid 文本自动转 IR、再确定性渲染成正交无交叉、内联 SVG 的自包含 HTML。覆盖系统架构、流程、时序、生命周期、决策、矩阵、对比、AI/Agent 模式、UML 等 10 大类，提供 12 套原创风格、40+ 图标、交互查看器（focus / 上下游可达 / 分享卡），并由 9 类硬契约校验（IR schema / 布局 / 间距 / 路由 / 交叉 / 标签 / 字体 / 语义 / 交付），ERROR 不可交付、WARNING 出具体修复建议。"
description_en: "Turn a one-line description or Mermaid text into a self-contained HTML diagram. Covers 10 diagram types (architecture, workflow, sequence, lifecycle, decision, matrix, comparison, AI/Agent pattern, UML, swimlane) with 12 hand-crafted visual styles, 40+ product icons, deterministic orthogonal routing, zero edge crossing when topologically possible, and an interactive viewer with focus / reachability / story / share card. A 9-rule composer contract validates every artifact before delivery."
category: design
version: 1.0.5
author: 百应AI工作室
---

# 流程图设计助手（v1.0.5）

**一句话需求 → 一张自包含 HTML 流程图**：从自然语言描述或 Mermaid 文本自动生成可粘贴、可打开、可分享的技术图。覆盖 **10 大类图型**、**12 套原创视觉风格**、**40+ 产品图标**、**确定性几何内核**、**9 类硬契约校验**、**交互查看器**。Agent 只管意图，编译器管正确性。

---

## 这个 skill 解决什么

很多技术场景都需要一张图。**但画图难的不是构图，是"画对"**——正交不交叉、标签不压节点、节点不出画布、端点对正端口、布局无歧义。AI 一次性给的 HTML 经常不符合几何要求，靠人盯式修改代价高昂。

这个 skill 把"画对"的责任**全部揽给编译器**：

- **意图层**：你只管"我要表达什么"。
- **编译层**：所有几何规则——正交、避让、零交叉、端口分散、标签安全——由 Python 内核确定性跑出来。
- **契约层**：9 类硬契约校验，**ERROR 不可交付**，每个 WARNING 给出机器可读的 `supportedFixes`。
- **交互层**：自包含 HTML，内置查看器（focus / 上下游可达 / 分享卡），用户随时可穿透每一根线。

---

## 什么时候触发

| 用户在说 | 触发的图型 | 备注 |
|---|---|---|
| 画个架构 / 系统拓扑 / 微服务图 | `architecture` | 按 lane 分层可加 `lanes` 字段 |
| 画个流程 / 业务流 / 用户旅程 / 决策 | `workflow` 或 `decision` | 带菱形判定时走 decision |
| 画个时序 / 协议 / 接口调用 | `sequence` | Mermaid `sequenceDiagram` 自动转 |
| 画个状态机 / 生命周期 / 状态流转 | `lifecycle` | Mermaid `stateDiagram` 自动转 |
| 画个对比 / 选型 / Before-After | `comparison` | 左 vs 右两栏布局 |
| 画个矩阵 / 2D 关系表 / 双向交叉 | `matrix` | 只画单元格，可不画节点 |
| RAG / Agent / Tool Call 流程 | `architecture` + type 提示 | AI/Agent 模式库 |
| 类图 / UML | `architecture`+ `kind:uml` | 14 种 UML 子集 |
| 泳道 / 跨角色协作图 | `architecture` + lanes | 自动画分隔带 |
| Mermaid 代码转图 | 自动判 flowchart/sequence/state | 走 `mermaid` 子命令 |

---

## 流程总览

| 阶段 | 名称 | 关键产物 |
|---|---|---|
| 0 | 意图解析 | 用户需求 → 选定 `diagram_type`、`style`、UML/AI 模式 |
| 1 | 写 IR JSON | `{diagram_type, nodes, edges, meta}`，传到 `validate` |
| 2 | 跑校验 | `diagram.py validate` 输出 ERROR/WARNING + supportedFixes |
| 3 | 渲染交付 | `diagram.py deliver` 输出自包含 HTML，自带 sha256 回执 |
| 4 | 复检产物 | `diagram.py check` 验自包含、SVG 存在、查看器挂载点 |
| 5 | 交付 | 文件路径 + sha256 摘要，供用户复用/分享 |

每条 command 的完整签名、退出码语义、`supportedFixes` 字段含义，详见 `@references/composition-contract.md`。

---

## 阶段 0 · 意图解析

先问 3 件事：

1. **图型**：参考上表。模糊时给 2–3 个候选 + 各自的取舍，**让用户选**，不要替他定。
2. **风格**：12 套可选（详见 `@references/styles.md`）。默认 **`flat-icon`（扁平图标）**，科技感强、图标优先；想柔文学感可推 `ink-landscape` 或 `paper-zen`。
3. **语义形状**：是否走 AI/Agent/UML 模式库。是的话交给编译器自动选形（LLM=双边框矩形、Agent=六边形、Database=圆柱、User=人形），详见 `@references/shape-vocabulary.md`。

> 用户**给 Mermaid** 文本 → 直接进 `mermaid` 子命令自动转 IR、再走阶段 1–5。
> 用户**给"画个类似 X 的图"** 模糊需求 → 走示例引导（先看 `@examples` 选最近的那张，仿其骨架填新内容）。

---

## 阶段 1 · 写 IR JSON

### IR 速查（完整规范见 `@references/ir-schema.md`）

```json
{
  "diagram_type": "architecture",
  "title": "电商订单系统架构",
  "meta": { "quality_profile": "showcase" },
  "nodes": [
    { "id": "web", "label": "用户端", "type": "frontend", "icon": "browser",
      "lane": "client", "tech": "Vue 3" },
    { "id": "gw",  "label": "API 网关", "type": "backend", "icon": "shield",
      "lane": "edge" },
    { "id": "ord", "label": "订单服务", "type": "backend", "icon": "server",
      "lane": "svc", "tech": "Go" }
  ],
  "edges": [
    { "source": "web", "target": "gw",  "label": "HTTPS", "kind": "sync" },
    { "source": "gw",  "target": "ord", "label": "REST",   "kind": "sync" }
  ],
  "lanes": [
    { "id": "client", "label": "客户端" },
    { "id": "edge",   "label": "边缘层" },
    { "id": "svc",    "label": "服务层" }
  ]
}
```

### 字段要点

| 字段 | 必填 | 说明 |
|---|---|---|
| `diagram_type` | 是 | 10 个枚举之一 |
| `nodes` | 是（matrix 可空） | 每节点至少 `id`、`label` |
| `edges` | 否 | `source`/`target` 必填，`label`、`kind` 可选 |
| `lanes` | 否 | architecture/architecture with sub-systems 才有意义 |
| `groups` | 否 | lifecyle/architecture 内的逻辑分组 |
| `meta.title` | 否 | 顶栏标题 |
| `meta.quality_profile` | 否 | `standard` 或 `showcase`，默认 `showcase` |
| `icons` | 否 | 节点 `icon` 字段引用，详见 `@references/icons.md` |

### IR 撰写红线

- **id 必须全局唯一**，且符合 `[A-Za-z_][A-Za-z0-9_.-]*`。
- **label 写中文不要写"判断"二字**写到菱形节点外（菱形专给判定）。
- **不要手写 layout 坐标**：编译器算。
- **不要给 `< 4` 字短 label**：文字层最少 4 个宽度单位（汉字算 1）。
- **不要塞无关节点**：宁可少节点不堆砌；warning 出来再补。

---

## 阶段 2 · 跑校验

```bash
python scripts/diagram.py validate <ir.json>
```

退出码：

- `0`：ERROR=0 且 (`profile==standard` 或 WARNING=0)。**可交付**。
- `1`：ERROR>0，或 showcase 档有 WARNING。**不可交付，按 supportedFixes 修**。

每个 finding 的结构：

```json
{
  "level": "error",
  "code": "EDGE_CROSSING",
  "subject": "$.edges[e1]",
  "message": "与 e2 在 (450, 320) 交叉",
  "evidence": { "edges": ["e1", "e2"], "at": [450, 320] },
  "supportedFixes": [
    "调整同层节点顺序",
    "拆分过密的连线",
    "把细节移入节点描述而非新增连线"
  ]
}
```

**硬契约**有 9 类（详见 `@references/composition-contract.md`）：schema、layout、spacing、route、crossing、label、typography、semantics、delivery。

---

## 阶段 3–4 · 渲染交付与产物复检

```bash
# 渲染（强制先通过校验；ERROR 时拒绝覆盖已有产物）
python scripts/diagram.py render <ir.json> <diagram.html>
python scripts/diagram.py deliver <ir.json> <output.html>

# 检查产物的可交付性（自包含、SVG 存在、查看器挂载点）
python scripts/diagram.py check <output.html>
```

`deliver` 产物为**单一自包含 HTML**：

- 内联 SVG（无外链）
- 内联 CSS / JS
- 含 `byai-diagram` 挂载点（查看器）
- SHA-256 摘要附在底部

> **PNG 导出**是可选能力（cairosvg）。未安装 `cairosvg` 时自动降级为 SVG 提示——**绝不能因为缺依赖而失败**。详见「降级策略」段。

---

## 阶段 5 · 派查看器能力

产物 HTML 自带交互查看器，用户可直接在浏览器中：

- **focus**：单击节点查看自身信息
- **上下游可达**：双击节点 / 长按节点 → 高亮所有入链/出链 + 关联节点
- **图表分享卡**：右键 → 「生成分享卡」→ 导出一张主题图卡片（标题 + 缩略 + 摘要）
- **键盘快捷键**：`f` 聚焦搜索、`+`/`-` 缩放、`0` 复位

> **千万别声称运行时影响**——查看器只对**已 authored 的拓扑**做交互，**不模拟真实流量**，**不执行任何节点动作**。这是 AI/Agent 模式图的核心红线。

---

## Mermaid 输入（自动判型）

```bash
python scripts/diagram.py mermaid <input.mmd> <ir.json>
python scripts/diagram.py validate <ir.json>          # 转换后校验
```

支持 `flowchart` / `graph` / `sequenceDiagram` / `stateDiagram(-v2)`。转换细节与已支持子集详见 `@references/mermaid-input.md`。

转换出来的 IR 可手改后再走阶段 1–5。等价于先用 mermaid"按住骨架"，再用 IR 调风格/语义层。

---

## 对比图（Before vs After）

```bash
python scripts/diagram.py compare <before.ir.json> <after.ir.json> <delta.html>
```

对比两份 **IR JSON**（即你编写/导出的 .json 源文件），输出 **Delta 差异报告 HTML**：以表格列出新增 / 删除 / 修改 / 移动节点与连线变更，并给出统计。详见 `@references/composition-contract.md#compare`。

---

## 视觉与合规基准（红线）

下列任何一条违反都会让产物被降为「unsafe」——不要交付。

1. **几何正确性优先**：路由正交、节点不重叠、标签不压节点/连线。这些由编译器 100% 保证，不由你"看起来差不多就行"放行。
2. **不传播未授权的样式**：12 套风格是**原创**生成的色板+字体栈，**不要从外部网页扒样式表**；引用色值必须用 `style/theme` 字段或 12 套默认之一。
3. **保持语义形状一致**：LLM 永远画双边框矩形、Agent 永远画六边形、Database 永远圆柱。**别给 LLM 节点用 circle**。
4. **忠实上游，禁止编造**：架构图内严禁"模拟"真实服务调用、严禁生成"看起来在跑数据"的伪管道。
5. **降级优先于失败**：cairosvg 不在 → 走 SVG；puppeteer 不在 → 走静态截图；查看器 webhook 不可用 → 不挂钩。当不确定时**老实说明已跳过哪些步骤**。

---

## 工程红线（给 AI 执行者）

1. **不要手写 HTML**：所有产物由 `render_engine.py` 确定性编译。手写即失去合约保证。
2. **不要 fork 校验**：`check()` 给出 ERROR 时不要交付；改 IR 不要绕过校验。
3. **不要省校验跑交付**：先 `validate` 看 ERROR=0，再 `deliver`，最后 `check`。
4. **不要避让 supportedFixes**：当 `check` 报告某条 finding、给出 supportedFixes 时，**优先按 supportedFixes 改 IR**，不要改校验器。
5. **不要遗失向下兼容**：跑旧 IR 文件时如果发现新契约不通过，**先升级 IR**，不要改旧契约。
6. **输出路径要明确**：渲染产物写到明确指定的路径（调用方以参数传入，如 `python scripts/diagram.py render <ir.json> <out.html>`），避免路径歧义导致产物丢失。
7. **不要绕过质量门禁**：改了引擎（scripts/ 下任何 .py）必须重跑 `python scripts/check.py`，EXIT 0 才算改完；不许删变异体或弱化断言来"让门禁变绿"。

---

## 9 类硬契约（速记）

| # | 类 | 关键 ERROR 码 | 触发条件 |
|---|---|---|---|
| 1 | schema | `IR_*` | IR 字段缺失/类型错 |
| 2 | layout | `NODE_OUT_OF_CANVAS` `NODE_OVERLAP` | 节点超出画布/互相重叠 |
| 3 | spacing | `SPACING_CRAMPED` | GAP_X/Y 不足 |
| 4 | route | `TOO_MANY_BENDS` | 折弯 >2 |
| 5 | crossing | `EDGE_CROSSING` | 边互相交叉 |
| 6 | label | `LABEL_OVER_NODE` `LABEL_OVER_EDGE` `LABEL_OUT_OF_CANVAS` | 标签压线/压节点/出边 |
| 7 | typography | `TEXT_OVERFLOW` | 节点标题/描述溢出 |
| 8 | semantics | `UNKNOWN_NODE_TYPE` | 节点 type 不在白名单 |
| 9 | delivery | `BAD_HTML` `NO_SVG` `NO_VIEWER_HOOK` | 产物非自包含或缺挂载点 |

完整列表与修复策略见 `@references/composition-contract.md`。

---

## CLI 速查

```bash
# 诊断环境与依赖
python scripts/diagram.py doctor

# 辅助：图型建议 / 列出全部风格
python scripts/diagram.py guide "画个 RAG 架构"
python scripts/diagram.py styles

# 单图全链
python scripts/diagram.py validate <ir.json>
python scripts/diagram.py render <ir.json> <diagram.html>
python scripts/diagram.py deliver <ir.json> <output.html>
python scripts/diagram.py check <output.html>

# Mermaid 转 IR
python scripts/diagram.py mermaid <in.mmd> <out.json>

# 对比两图并产出 Delta HTML
python scripts/diagram.py compare <before.ir.json> <after.ir.json> <delta.html>
```

完整 flag 与示例见 `@references/composition-contract.md#cli`。

---

## 默认风格

12 套风格种，**默认 `flat-icon`（扁平图标）**——科技感强、图标优先、对比度足，适合公众号/Notion/Confluence/PPT 截图。

如果用户有偏好（如"看起来柔和些"），换 `ink-landscape`（水墨）/ `paper-zen`（留白）；不要默认出多版本——出用户指定的那一版。详见 `@references/styles.md`。

---

## 路径速查

```
skills/byai-diagram-designer/
├── SKILL.md                       ← 你正在读
├── skillhub-meta.json             ← 提审档案（版本/描述/examples）
├── README.md                       ← 项目门面，对外可发布
├── avatars/                        ← 技能头像
├── scripts/
│   ├── diagram.py                  ← 统一 CLI 入口
│   ├── ir_schema.py                ← IR 规范化 + 自动分层
│   ├── geometry.py                 ← 正交路由 + 端口分散 + 跨接桥
│   ├── composition.py              ← 9 类硬契约校验器
│   ├── styles.py                   ← 12 套原创风格
│   ├── icons.py                    ← 40+ 产品图标（纯 SVG 路径）
│   ├── render_engine.py            ← IR → 自包含 HTML 确定性编译
│   ├── mermaid2ir.py               ← Mermaid → IR
│   ├── compare.py                  ← Before / After / Delta
│   └── check.py                    ← 质量门禁（部署闸门 + 样例回归 + 变异反证）
├── templates/
│   └── viewer.html                 ← 查看器主模板
├── references/
│   ├── diagram-types.md            ← 10 大类图型详解
│   ├── ir-schema.md                ← IR 字段权威规范
│   ├── styles.md                   ← 12 套风格视觉指南
│   ├── shape-vocabulary.md         ← 语义形状库（LLM/Agent/UML）
│   ├── icons.md                    ← 40+ 图标索引与用法
│   ├── composition-contract.md     ← 9 类硬契约 + supportedFixes
│   ├── mermaid-input.md            ← Mermaid 子集与转换表
│   └── authoring-contract.md       ← 创作期规范（命名/lane/type/icon）
├── examples/                       ← 6 个跨图型样例 + IR
│   ├── web-app.architecture.json
│   ├── ai-rag-pipeline.json
│   ├── ai-memory-lanes.json
│   ├── seq-oauth2.json
│   ├── lifecycle-order.json
│   └── comparison-rag-finetune.json
```

---

## 质量门禁（EXIT 0 才许打包）

本 skill 的正确性不靠 prompt 自觉，靠 `scripts/check.py` 确定性卡关。**任何引擎改动后、打包发布前，必须重跑**：

```bash
python scripts/check.py
```

| 层 | 检什么 | 失败意味着 |
|---|---|---|
| L1 部署闸门 | SKILL.md 元数据 · skillhub-meta.json 版本对齐 · 11 个必需文件 · 头像规格 · 目录层级 ≤2 · 零中文文件名 · 无 `__pycache__` · 零 CDN · 纯 stdlib | 包结构不合规，不许发布 |
| L2 样例回归 | 6 张跨图型样例全量走 validate → deliver → check | 引擎改了合法输入的行为，先修回归再谈别的 |
| L3 变异反证 | 4 组坏 IR 必须 EXIT 1 拒绝且带「不可交付」；1 组缺 type 的合法 IR 必须放行；4 组汇总计数自洽 | 校验器漏报或自相矛盾（如汇总打印"全部通过"却 exit=1） |

> 核心思想：**先证明"坏输入一定被抓"，再证明"好输入一定放行"**。变异体抓不住，说明校验器有洞；合法输入被误杀，说明校验器太紧。两边都钉死，交付才可信。