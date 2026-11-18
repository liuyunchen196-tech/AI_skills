---
name: interactive-diagram-generator
display_name: 交互流程图专家
display_name_en: Interactive Flowchart Expert
description: 把自然语言描述或 Mermaid 图变成可交互、自包含、带机器可读校验的 HTML 架构图。支持 architecture（组件·服务·云安全边界·基础设施）、workflow（流程·审批·CI-CD·工具调用）、sequence（API 调用链·请求生命周期·异步 trace）、dataflow（ETL/ELT·血缘·治理）、lifecycle（状态机·重试·终态）五类图，并支持 PNG/JPEG/WebP/SVG/WebM 导出与深/浅主题。用户要求画系统架构图、基础设施拓扑、技术流程图、调用时序、数据管道、状态机，或转换/美化 Mermaid 时使用。派生自 tt-a1i/archify（MIT，v3.0.1）。
description_zh: 把自然语言描述或 Mermaid 图变成可交互、自包含、带机器可读校验的 HTML 架构图。支持 architecture、workflow、sequence、dataflow、lifecycle 五类图，支持 PNG/JPEG/WebP/SVG/WebM 导出与深/浅主题。用于画系统架构、基础设施拓扑、技术流程、调用时序、数据管道、状态机，或美化/转换 Mermaid。派生自 tt-a1i/archify（MIT）。
description_en: Turn natural-language descriptions or Mermaid diagrams into interactive, self-contained, machine-verifiable HTML architecture diagrams. Supports architecture, workflow, sequence, dataflow, and lifecycle diagrams with PNG/JPEG/WebP/SVG/WebM export and light/dark themes. Use when the user asks to draw system or infra architecture, technical flows, API sequences, data pipelines, or state machines, or to beautify or convert Mermaid. Derived from tt-a1i/archify (MIT, v3.0.1).
version: 1.0.5
license: MIT
category: 效率工具
upstream: https://github.com/tt-a1i/archify
upstream_version: 3.0.1
author: tt-a1i（蒸馏封装，跨 Agent 通用版）
---


# Archify（蒸馏封装版）

把模糊需求收敛成**可验证**的交互式 HTML 图。核心不是"画图"，而是 **强类型 JSON 中间表示（IR）+ 机器可读校验 + 原子交付** 的闭环。

运行时整包位于本技能根目录（含 `bin/`、`renderers/`、`schemas/`、`references/`、`assets/`、`examples/`）。`bin/archify.mjs` 通过 `../renderers` 相对导入，必须保留这些目录的相对位置，不能只拷 `bin/`。

> 本目录下的 `test-prompts.json` 仅供维护者本地验证使用，**不进上架包**（打包时会自动排除）。

## 何时使用

- 用户要画：系统/服务架构、云或网络安全拓扑、技术工作流、审批/CI-CD 流程、API 调用时序、请求生命周期、数据管道/血缘、状态机/生命周期。
- 用户给了 Mermaid（`flowchart`/`sequenceDiagram`/`stateDiagram`），要求转成更美观、可交互的图。
- 用户要求把某段系统描述导出为 PNG/SVG/WebM 等。

## 运行环境

- **Node >= 18**。优先直接使用 PATH 中的 `node`；若没有，可用本机任意 Node >= 18 的绝对路径（WorkBuddy 受管环境示例：`C:/Users/<用户名>/.workbuddy/binaries/node/versions/22.22.2-3/node.exe`）。
- 命令中的 `<ARCHIFY>` 替换为技能根目录（即 SKILL.md 所在目录）。`archify.mjs` 会自己解析 `skillRoot`，所以从任意工作目录运行均可，只要指向的 `bin/archify.mjs` 路径正确。

## 五类图路由

| 类型 | 用于 | Schema | 示例 |
|---|---|---|---|
| `architecture` | 组件、服务、云/安全边界、基础设施 | `schemas/architecture.schema.json` | `examples/web-app.architecture.json` |
| `workflow` | 流程、审批、工具调用、CI/CD | `schemas/workflow.schema.json` | `examples/agent-tool-call.workflow.json` |
| `sequence` | API 调用链、请求生命周期、异步 trace | `schemas/sequence.schema.json` | `examples/cache-miss-request.sequence.json` |
| `dataflow` | 管道、ETL/ELT、血缘、治理 | `schemas/dataflow.schema.json` | `examples/product-analytics.dataflow.json` |
| `lifecycle` | 状态/状态转移、重试、终态 | `schemas/lifecycle.schema.json` | `examples/deployment-release.lifecycle.json` |

不确定时用 `node <ARCHIFY>/bin/archify.mjs guide "<场景>" --json` 让技能给出推荐类型与结构。

## 快速创作路径（普通生成）

1. **选类型**：按上表从需求判断。若用户未指定图类型且从描述仍无法判断（如"画一下我们的系统"无上下文），先问一句类型/范围再起稿；明确需求直接开干，不卡确认。
2. **读契约**：读 `references/authoring-defaults.md` + 对应模式的 schema 与该类型一个示例（批量读，避免截断）。示例只教"形状"，不教"事实"——用新的 ID、措辞与布局。
3. **写候选**：直接产出**完整** JSON，不写临时图、不列输出路径。`meta.quality_profile` 默认 `"showcase"`（宽松留白）；`meta.output` 设为工作区内 POSIX 相对 `.html` 路径（如 `.archify/architecture-<slug>-<YYYYMMDD-HHMMSS>/<slug>.html`）。
4. **跑 finalize**（首稿即完整稿，无需预校验）：
   ```bash
   node <ARCHIFY>/bin/archify.mjs finalize <type> <candidate.json> <output.html> --quality showcase --json
   # 真实代码取证时追加：--repo-root <repo-root>
   ```
   通过即代表 validate → deliver → 严格 check → 真实浏览器 browser-check 四道门全过。
   > **自动降级（重要）**：若 `finalize` 退出码非 0 且报错含 `nlink` / `EBUSY` / `spawn` / `hardlink`（沙箱或叠加文件系统常见），**不要反复重试 `finalize`**，立即改用下方「环境注意」里的「nlink 仍失败时的终极绕行」直渲路径产出 HTML；该绕行跳过浏览器可读性门，需自行目检可读性。本轮实测：标准 `finalize` 在叠加文件系统下因收据文件被报 `nlink=2` 而失败，切到直渲路径即成功产出。
5. **非零退出 = 失败**：读 `evidence.summaryReceipt`，按 `diagnostics[].supportedFixes` 只改"连通邻域"，重跑完整 `finalize`（修复上限为两轮）。
   - 修复样例：报 `connection <id> references unknown node <x>` → `from`/`to` 写错或漏建节点，补节点或改正 id 即可，**不要动无关边**；报 `label-collision`（标签碰撞）→ 给冲突边加 `labelDy`/`via` 错开，或调 `fromSide`/`toSide`；报 `viewport-overflow`（超宽）→ 用 `spread` 或拆 lane/列，勿靠缩字号硬塞。每轮只改被点名的最小邻域。

新图请求各自建文件夹 `.archify/<type>-<slug>-<时间戳>/`，保留 `candidate.json` 与 `<slug>.html`；后续修复重跑复用同一文件夹，旧版本自然留存。

## 起稿模板（architecture 最小骨架）

不必先读 references 也能起稿。一个最小可渲染的 architecture JSON 形如（坐标单位为画布像素，原点左上）：

```json
{
  "schema_version": 1,
  "diagram_type": "architecture",
  "meta": {
    "title": "示例 Web 应用",
    "output": ".archify/architecture-demo-20261003-233500/demo.html",
    "quality_profile": "showcase"
  },
  "components": [
    { "id": "users", "type": "external", "label": "用户", "pos": [40, 300], "size": [120, 60] },
    { "id": "api", "type": "backend", "label": "API 服务", "pos": [300, 300], "size": [130, 60] },
    { "id": "db", "type": "database", "label": "PostgreSQL", "pos": [560, 300], "size": [130, 60] }
  ],
  "connections": [
    { "id": "u-api", "from": "users", "to": "api", "label": "HTTPS" },
    { "id": "api-db", "from": "api", "to": "db", "label": "SQL" }
  ]
}
```

要点：
- `components[].type` 取值：`frontend` / `backend` / `database` / `cloud` / `security` / `messagebus` / `external`。
- `pos` 决定布局、`size` 为宽高；**自动路由优先**，仅在分支/回边需避让时才给 `fromSide`/`toSide`/`via`。
- 其余四类（`workflow`/`sequence`/`dataflow`/`lifecycle`）字段结构不同，首次写仍读对应 schema + 一个示例（见上方路由表）。
- 用户未指定图类型且需求仍歧义时，先用 `guide` 或向用户确认类型/范围，再起稿（明确需求不阻断）。

## Mermaid 输入映射

- `flowchart`/`graph` → `workflow`（组件图则 `architecture`）
- `sequenceDiagram` → `sequence`（participants 变语义参与者，arrows 变 messages）
- `stateDiagram` → `lifecycle`（状态与转移保留语义，不保留 Mermaid 样式）

读取 Mermaid 的拓扑与含义后**重新创作** Archify JSON，不要机械渲染 Mermaid 样式。

## 常用命令

| 命令 | 作用 |
|---|---|
| `finalize <type> <in.json> <out.html> --quality showcase --json` | 一键交付（推荐） |
| `validate <type> <in.json> --quality showcase --json` | 仅校验（含渲染） |
| `deliver <type> <in.json> <out.html> --quality showcase --json` | 渲染并原子交付 |
| `preview <type> <in.json> <out.html> --quality showcase` | loopback 桌面预览（随机 127.0.0.1 端口，Ctrl-C 停止） |
| `guide "<场景>" --json` | 推荐类型与结构 |
| `doctor` | 运行环境自检 |
| `demo <输出目录>` | 生成演示图 |

## 输出与质量承诺

返回：HTML **绝对路径**、图类型、校验摘要、交付收据、浏览器证据状态、**真实的视觉复核状态**（没做就不谎称"已目检"）。非零退出绝不报成功。

## 查看器可选能力（按需）

默认静态输出。`meta.animation: "trace"` 开启读者可控的轨迹动效。生成的 HTML 已内置：聚焦/上下游追溯、Route/Reach 探针、语义透镜、查找、演示模式、深/浅主题切换、导出菜单（PNG/JPEG/WebP/双主题 SVG/WebM）。需要这些能力时再读 `references/viewer-runtime.md`，普通生成无需实现。

## 环境注意（重要）

- **本技能依赖 Node 能派生子进程**：`finalize`/`validate`/`deliver` 通过 `spawnSync` 拉起渲染子进程。若运行环境禁止 Node 派生子进程（报 `EBUSY`/`internal/renderer-process`），请改用**直接调用对应渲染器**的方式产出 HTML，绕过内部 spawn：
  ```bash
  node <ARCHIFY>/renderers/render-<type>.mjs <in.json> <out.html> --quality showcase
  ```
  该路径由 Bash 直接拉起 Node（单进程内渲染），不触发 archify 的内部 spawn；但会跳过浏览器可读性回归门，需自行目检可读性。
- **原子输出安全断言**：渲染器要求临时候选文件 `nlink === 1`。若输出所在文件系统的新文件被报告为 `nlink > 1`（某些沙箱/叠加文件系统），会报 `Temporary output candidate has multiple hard-link names`。把输出写到普通本地盘（如用户目录或 `C:/Windows/Temp`）通常可规避。
- **nlink 仍失败时的终极绕行**：叠加文件系统下连普通盘也可能报 `nlink>1`，此时**绕开 `writeDiagram`**，自行组装并直写（不经原子替换）：
  ```js
  const { loadDiagram } = await import('<ARCHIFY>/renderers/cli.mjs');
  const { compileWorkflow } = await import('<ARCHIFY>/renderers/workflow-compiler.mjs'); // 其他类型换对应 compiler
  const { applyTemplate, renderCards } = await import('<ARCHIFY>/renderers/utils.mjs');
  const { diagram, template } = loadDiagram({ rendererDir: '<ARCHIFY>/renderers', diagramType, defaultExample, argv });
  const compiled = compileWorkflow({ workflow: diagram, qualityProfile: diagram.meta?.quality_profile, sourceEvidence: null });
  fs.writeFileSync(out, applyTemplate(template, {
    title: diagram.meta.title, svg: compiled.svg, cards: renderCards(diagram.cards),
    visualPreset: diagram.meta.visual_preset || 'classic', sourceEvidence: null,
  }));
  ```
  用同步的 `loadDiagram` 而非异步的 `loadDiagramWithBrandMarks`（后者会联网抓品牌标记），避免沙箱无网时挂起。代价：跳过原子交付与浏览器可读性门，需自行目检。
- **workflow 创作硬约束**：`nodes[].col` 与 `phases[].fromCol/toCol` 最大为 **5**（最多 6 列）；`phases` 的列区间**不可互相重叠**；同一 lane 内多节点必须占**不同 col**（同 lane 同 col 会报 node-overlap）；`label`/`sublabel` 不得超出节点 `width`。跨泳道同列交接用默认路由即可，强加 `route: "outside-right"` 易触发 route-preset-conflict。
- **从产物 HTML 抽 SVG 转 PNG**：HTML 里的 `<svg>` 缺少 `xmlns`，resvg 会报 "document does not have a root node"——抽取后先补 `xmlns="http://www.w3.org/2000/svg"` 再转。
- 不自动联网升级；`finalize` 收据含 `update` 字段，必要时向用户提示一次更新即可。

## 参考索引

- 创作默认值：`references/authoring-defaults.md`
- 创作契约（几何/标签/组合修复）：`references/authoring-contract.md`
- 交付契约（失败修复/独立命令/导出/打开）：`references/delivery-contract.md`
- 真实代码取证：`references/repository-authoring.md`
- 架构布局修复：`references/architecture-layout-repair.md`
- 品牌标记：`references/brand-marks.md`
- 更新意识：`references/update-awareness.md`
- 查看器运行时：`references/viewer-runtime.md`
- JSON Schema：`schemas/*.schema.json`（公共定义在 `common.schema.json`）
