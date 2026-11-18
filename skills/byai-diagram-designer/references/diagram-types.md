# Diagram Types · 10 大类图型

由 `diagram_type` 字段决定走哪条渲染管线。每个图型有「最佳使用场景」「必填字段」「常见坑」三段。

---

## 总览表

| 图型 | 适用场景 | 关键字段 |
|---|---|---|
| `architecture` | 系统/微服务/网络拓扑 | `nodes`, `edges`, `lanes`, `groups` |
| `dataflow` | 流水线/ETL/数据血缘 | `nodes` 带 `type: source/transform/sink` |
| `workflow` | 业务流程/审批/用户旅程 | `nodes` 带 `type: process/decision/start/end` |
| `lifecycle` | 状态机/订单状态 | `nodes[].type=state`，`edges[].kind=event` |
| `sequence` | 时序/协议/接口调用 | `nodes` 视为参与者， `edges` 沿生命线 |
| `comparison` | 选型/2x2 对比矩阵 | `meta.matrix.rows` × `meta.matrix.cols` |
| `mindmap` | 思维导图/概念图 | 一个 `center` 节点 + 多级 `branches` |
| `ai.rag` | RAG 检索增强生成 | 同 architecture + `type: vector\|llm\|retriever` |
| `ai.multi-agent` | 多智能体协作 | 同 architecture + `type: agent` |
| `uml.class` 等 | 类图/组件图/部署图/用例图 | 同 architecture + `kind:uml` |

---

## 1. architecture · 系统架构

最常用。**lane** 是核心概念：每个节点属于一个 swimlane，引擎沿 lane 排序、按 lane 分隔带画横线/竖线。

```json
{
  "diagram_type": "architecture",
  "lanes": [
    { "id": "client", "label": "客户端" },
    { "id": "edge",   "label": "边缘层" },
    { "id": "svc",    "label": "服务层" },
    { "id": "data",   "label": "数据层" }
  ],
  "nodes": [
    { "id": "web",   "label": "Web 端",    "type": "frontend",  "lane": "client", "icon": "browser" },
    { "id": "gw",    "label": "API 网关",  "type": "security",  "lane": "edge",   "icon": "shield" },
    { "id": "order", "label": "订单服务",  "type": "backend",   "lane": "svc",    "icon": "server", "tech": "Go" },
    { "id": "pay",   "label": "支付服务",  "type": "backend",   "lane": "svc",    "icon": "server", "tech": "Java" },
    { "id": "mysql", "label": "订单库",    "type": "database",  "lane": "data",   "icon": "mysql" }
  ],
  "edges": [
    { "source": "web",   "target": "gw",    "label": "HTTPS" },
    { "source": "gw",    "target": "order", "label": "REST" },
    { "source": "gw",    "target": "pay",   "label": "REST" },
    { "source": "order", "target": "mysql", "label": "SQL" }
  ]
}
```

> **坑**：节点过多且 lane 跨度大时会强制出现回边（连线上溯）。此时输出会包含回边通道（右侧蓝灰轨道），不要惊慌——这是预期的。回边多到 `TOO_MANY_BENDS` 报警时，**应当减节点 / 拆图**，不要"凑合用"。

---

## 2. dataflow · 数据流 / 流水线

与 architecture 共享 layered 布局。语义上 `type` 是源/转换/汇；连线的 `kind` 区分：
- `flow`：主流向（粗）
- `sync`：普通调用
- `async`：异步/虚线
- `event`：事件

```json
{
  "diagram_type": "dataflow",
  "nodes": [
    { "id": "src", "label": "上游 MySQL", "type": "source" },
    { "id": "kfk", "label": "Kafka",      "type": "messagebus" },
    { "id": "etl", "label": "清洗任务",   "type": "transform", "tech": "Flink" },
    { "id": "dw",  "label": "数据仓库",   "type": "sink",      "icon": "snowflake" }
  ],
  "edges": [
    { "source": "src", "target": "kfk", "kind": "flow" },
    { "source": "kfk", "target": "etl", "kind": "async" },
    { "source": "etl", "target": "dw",  "kind": "flow" }
  ]
}
```

---

## 3. workflow · 业务流程 / 审批

`type: decision` 节点自动变菱形。引擎自动检测判定分支，按 yes/no 配色区分。

```json
{
  "diagram_type": "workflow",
  "nodes": [
    { "id": "start", "label": "提交申请", "type": "start" },
    { "id": "chk",   "label": "预算充足？", "type": "decision" },
    { "id": "mgr",   "label": "直属经理审批", "type": "process" },
    { "id": "fin",   "label": "财务审批", "type": "process" },
    { "id": "done",  "label": "完成", "type": "end" }
  ],
  "edges": [
    { "source": "start", "target": "chk" },
    { "source": "chk",   "target": "mgr", "label": "是" },
    { "source": "chk",   "target": "done", "label": "否" },
    { "source": "mgr",   "target": "fin", "label": "通过" }
  ]
}
```

---

## 4. lifecycle · 状态机 / 生命周期

节点的 `type=state`，连线的 `kind=event` 表示触发事件。引擎把所有 transition 排成环形，回看箭头走外侧。

```json
{
  "diagram_type": "lifecycle",
  "nodes": [
    { "id": "pending",   "label": "待支付",   "type": "state" },
    { "id": "paid",      "label": "已支付",   "type": "state" },
    { "id": "shipping",  "label": "配送中",   "type": "state" },
    { "id": "completed", "label": "已完成",   "type": "state" },
    { "id": "refunded",  "label": "已退款",   "type": "state" }
  ],
  "edges": [
    { "source": "pending",   "target": "paid",      "label": "支付完成" },
    { "source": "paid",      "target": "shipping",  "label": "出库" },
    { "source": "shipping",  "target": "completed", "label": "签收" },
    { "source": "paid",      "target": "refunded",  "label": "申请退款" }
  ]
}
```

---

## 5. sequence · 时序图

节点=参与者（沿 X 排列），edges=消息沿生命线下行，kind 三选一：
- `sync`：实线箭头
- `async`：虚线箭头
- `return`：末端 `x` 形回箭头

```json
{
  "diagram_type": "sequence",
  "nodes": [
    { "id": "u",  "label": "用户",     "type": "user" },
    { "id": "s",  "label": "客户端",   "type": "frontend" },
    { "id": "a",  "label": "认证服务", "type": "backend" },
    { "id": "db", "label": "用户库",   "type": "database" }
  ],
  "edges": [
    { "source": "u",  "target": "s",  "label": "点击登录", "kind": "sync" },
    { "source": "s",  "target": "a",  "label": "POST /login", "kind": "sync" },
    { "source": "a",  "target": "db", "label": "查 user", "kind": "sync" },
    { "source": "db", "target": "a",  "label": "user row", "kind": "return" },
    { "source": "a",  "target": "s",  "label": "200 + token", "kind": "return" }
  ]
}
```

---

## 6. comparison · 对比 / 矩阵

引擎优先读 `meta.matrix.rows × meta.matrix.cols` 渲染表格外壳；`nodes` 作为对比主体（左右两栏）。

```json
{
  "diagram_type": "comparison",
  "meta": {
    "matrix": {
      "rows":    ["知识更新", "幻觉率",   "私有数据", "可解释性"],
      "cols":    ["RAG",       "微调",      "提示词工程"]
    }
  },
  "nodes": [
    { "id": "rag",  "label": "RAG · 检索增强" },
    { "id": "ft",   "label": "Fine-tuning · 微调" },
    { "id": "pt",   "label": "Prompt Engr · 提示工程" }
  ],
  "edges": []
}
```

---

## 7. mindmap · 思维导图

以 `nodes[0]` 为 center，向四周辐射 branches。`edges[i].kind=branch` 表示主题分支，level=分支层级（0 一级、1 二级）。

```json
{
  "diagram_type": "mindmap",
  "nodes": [
    { "id": "c", "label": "AI Agent", "type": "center" },
    { "id": "p", "label": "Perception" },
    { "id": "m", "label": "Memory" },
    { "id": "t", "label": "Tool Use" },
    { "id": "r", "label": "Reasoning" }
  ],
  "edges": [
    { "source": "c", "target": "p", "kind": "branch", "level": 1 },
    { "source": "c", "target": "m", "kind": "branch", "level": 1 },
    { "source": "c", "target": "t", "kind": "branch", "level": 1 },
    { "source": "c", "target": "r", "kind": "branch", "level": 1 }
  ]
}
```

---

## 8. ai.* 系列

适用于 LLM、Agent、RAG、Multi-Agent、Memory、Tool Call 等 AI 模式。**type 必须落在白名单**——否则 `UNKNOWN_NODE_TYPE` 报警：

| type | 默认形状 | 用途 |
|---|---|---|
| `llm` | 双边框矩形 | GPT / Claude / Zhipu |
| `agent` | 六边形 | 单 agent |
| `multi-agent` | 嵌套六边形 | 群组 |
| `retriever` | 文档图标 | 检索器 |
| `vector` | 柱状图 | 向量库 |
| `embedding` | 矩阵图标 | 嵌入模型 |
| `tool` | 工具图标 | 工具调用 |
| `planner` | 折线路径 | 规划器 |
| `memory` | 时钟图标 | 记忆系统 |

引擎对 `ai.rag` / `ai.multi-agent` 等图型会**自动选这些形状**，无需手画。

---

## 9. uml.* 系列

| 图型 | 等价 |
|---|---|
| `uml.class` | 类图（type 含 `+x:int` 字段） |
| `uml.component` | 组件图 |
| `uml.deployment` | 部署图（自带 lanes） |
| `uml.usecase` | 用例图（人形 actor + 椭圆用例） |
| `uml.activity` | 活动图 |
| `uml.state` | 等同 lifecycle |
| `uml.sequence` | 等同 sequence |
| `uml.er` | 实体关系图 |

---

## 10. 选型速查表

| 我要画的 | 选这个 |
|---|---|
| 一个系统服务的整体拓扑 | architecture + lanes |
| 一个 ETL 流水线 / 数据血缘 | dataflow |
| 一个业务审批 / 用户操作流程 | workflow |
| 一个状态机（订单状态流转） | lifecycle |
| 两个服务之间的接口调用协议 | sequence |
| 几条方案对比（2-3 列） | comparison |
| 一个 AI Agent / RAG 系统 | ai.rag / ai.multi-agent |
| 一次脑中风暴的概念发散 | mindmap |
| 选 Type 与 GraphQL 的差异 | comparison + matrix |
| 服务-数据库 ER 图 | uml.er |
