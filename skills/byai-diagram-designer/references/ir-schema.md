# IR Schema · 中间表达权威规范

由 `scripts/ir_schema.py` 实施。Schema 版本号 `SCHEMA_VERSION = "1"`。本文件是该版本的权威文档。

---

## 顶层结构

```json
{
  "diagram_type": "<type>",
  "title": "...",
  "meta": {
    "title": "...",
    "subtitle": "...",
    "quality_profile": "showcase"
  },
  "nodes": [ ... ],
  "edges": [ ... ],
  "lanes": [ ... ],
  "groups": [ ... ]
}
```

引擎在收下原始 IR 后，会进行：

1. **类型规范化**（必填字段补默认、字段名统一）
2. **自动分层**（按 edges 拓扑排 layer & column）
3. **派生布局字段**（每个节点生成 `_seq/x/y/w/h`，每条边生成 `_sx/_sy/_tx/_ty`）

> **Agent 不要直接吃渲染引擎**：先把 IR 写出来跑一次 `validate`，再让渲染引擎接手。

---

## `diagram_type`

10 个枚举值，详见 `@diagram-types.md`：

```
architecture | dataflow | workflow | lifecycle
sequence | comparison | mindmap
ai.rag | ai.agentic-rag | ai.agentic-search | ai.memory
| ai.memory-types | ai.multi-agent | ai.tool-call
uml.class | uml.component | uml.deployment | uml.package
| uml.usecase | uml.activity | uml.state | uml.sequence | uml.er
```

**字符串别名**（写 IR 时允许使用，写完校验时统一展开）：

| 别名 | 实际 |
|---|---|
| `arch` / `架构图` / `系统架构` | `architecture` |
| `flow` / `流程` / `流程图` | `workflow` |
| `state` / `状态` / `状态机` | `lifecycle` |
| `seq` / `时序` / `调用链` | `sequence` |
| `compare` / `对比` | `comparison` |
| `rag` / `mem0` / `memory` | `ai.rag` / `ai.memory` |

---

## `nodes[].` 字段表

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `id` | string | **是** | — | 全局唯一，`[A-Za-z_][A-Za-z0-9_.-]*` |
| `label` | string | **是** | `id` | 节点主标题 |
| `desc` | string | 否 | `null` | 节点描述（≤ 40 字），显示在 label 下 |
| `type` | enum | 否 | `default` | 决定形状 + 默认图标，见下表 |
| `icon` | enum | 否 | — | 见 `@icons.md` |
| `lane` | string | 否 | `__all__` | 所属 swimlane id（须在 `lanes[]` 中） |
| `group` | string | 否 | — | 所属分组 |
| `tech` | string | 否 | — | 技术栈标注（如 "Go" / "k8s"） |
| `col` | int | 否 | 自动 | 层内列位置（**通常不写**，由引擎分配） |
| `row` | int | 否 | 自动 | 节点所在层（**通常不写**） |

---

## `nodes[].type` 白名单

```
# neutral
default, process, decision, start, end, state, center, terminal

# 基础设施
frontend, backend, database, storage, cloud, security, messagebus,
vector, llm, agent, multi-agent, retriever, embedding, tool, planner,
memory, queue

# UML 角色
actor, usecase, class, component, deployment
```

`type` 不在白名单 → `UNKNOWN_NODE_TYPE` 报警。

---

## `edges[].` 字段表

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `source` | string | **是** | — | 起点节点 id |
| `target` | string | **是** | — | 终点节点 id |
| `label` | string | 否 | `null` | 连线文字，建议 ≤ 8 字（中文 4 字以上） |
| `kind` | enum | 否 | `sync` | `sync` / `async` / `flow` / `event` / `return` / `branch` |
| `via` | array | 否 | — | 强制经过 [x,y] 点（绕障用） |
| `style` | enum | 否 | `solid` | `solid` / `dashed` / `thick` |
| `weight` | int | 否 | `1` | `flow` 类主线可设 `2` |
| `dir` | enum | 否 | `forward` | `forward` / `back` / `none` |

---

## `lanes[]`

仅当 `diagram_type=architecture|dataflow|uml.deployment` 时生效。

```json
"lanes": [
  { "id": "client", "label": "客户端" },
  { "id": "edge",   "label": "边缘层" }
]
```

`id` 必须全局唯一；`label` 是分隔带上的文字。

> **警告**：lane 数大于 5 时横向过宽会触发 `SPACING_CRAMPED` warning，可考虑拆图。

---

## `groups[]`（可选）

用于 `lifecycle` 或 `architecture` 内的逻辑分组（不会自动分隔画布，靠 `border` 或背景色区分）。

```json
"groups": [
  { "id": "frontend-group", "label": "前端", "members": ["web", "h5"] }
]
```

---

## `meta[]` 字段

| 字段 | 默认值 | 说明 |
|---|---|---|
| `meta.title` | — | 顶栏主标题 |
| `meta.subtitle` | — | 顶栏副标题（灰色） |
| `meta.quality_profile` | `showcase` | `standard`：容忍少量 warning；`showcase`：所有 warning 都视作失败 |
| `meta.story` | string[ ] | `before→after` 故事文本（4–6 段），画卡时使用 |
| `meta.share_card` | object | `{ title, summary, footer }` 自定义分享卡 |

---

## 引擎补全字段（不要手写）

下列 `_x/_y/_seq/.../auto` 前缀字段由 `ir_schema.normalize()` 自动写回 IR，**Agent 不要预设**：

```
_nodes_row (dict[int] -> list[node])         // 每层节点列表
_row_nodes (dict[int] -> list[node])         // 反向索引
by_id (dict[id] -> node)                     // 节点哈希
_layers (list[node])                         // 拓扑序节点
edgelist_count, isolated, ...               // 统计字段
```

直接读会得到 None；要看坐标应在 `geometry.build_geometry` 之后。

---

## 完整示例（最小）

```json
{
  "diagram_type": "workflow",
  "title": "请假审批",
  "meta": { "quality_profile": "standard" },
  "nodes": [
    { "id": "s", "label": "提交", "type": "start" },
    { "id": "m", "label": "经理审批", "type": "process" },
    { "id": "h", "label": "人事备案", "type": "process" },
    { "id": "e", "label": "结束", "type": "end" }
  ],
  "edges": [
    { "source": "s", "target": "m", "label": "提交申请" },
    { "source": "m", "target": "h", "label": "通过" },
    { "source": "h", "target": "e" }
  ]
}
```

把这个输入灌给 `validate`，会得到 0 ERROR、0 WARNING；`deliver` 后产物即一张可分享的流程图。
