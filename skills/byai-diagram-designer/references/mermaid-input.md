# Mermaid Input · Mermaid 输入子集与转换表

由 `scripts/mermaid2ir.py` 实施。Mermaid 只是个**意图层**——把它当骨架，再走完整 IR 流程。

---

## 支持与不支持

**支持**：
- `flowchart TD/LR/BT/RL`（顶层声明）
- `graph TD/LR/BT/RL`（同 flowchart）
- `sequenceDiagram` 与 `sequenceDiagram-v2` 语法
- `stateDiagram` / `stateDiagram-v2`

**不支持**（自动忽略，不报错）：
- `classDiagram`
- `erDiagram`
- `gantt`
- `pie`
- `journey`
- `gitGraph`
- `C4 Context / Container`
- 主题/主题变量、`themeVariables`
- HTML 标签嵌入（`<br>`、`<i>`）
- `style` `class` `classDef` 等装饰指令

---

## Flowchart 语法映射

### 节点形状 → node.type

| Mermaid 形态 | IR node.type | 引擎渲染 |
|---|---|---|
| `A[Label]` | `process` | 矩形 |
| `A(Label)` | `process` | 圆角矩形 |
| `A([Label])` | `process` | 圆角矩形（圆头大） |
| `A[[Label]]` | `process` | 矩形（subroutine） |
| `A((Label))` | `terminal` | 椭圆形 |
| `A{Label}` | `decision` | 菱形 |
| `A{{Label}}` | `decision` | 六边形 |
| `A>Label]` | `process` | 不对称形 |
| `A[/Label/]` | `process` | 平行四边形 |
| `A[\Label\]` | `process` | 反平行四边形 |
| `A[/Label\]` | `process` | 梯形 |
| `A[\Label/]` | `process` | 反梯形 |
| `A(((((Label))))`（双圆）| `terminal` | 双圆 |

### 连线 → edge.kind

| Mermaid 箭头 | IR edge.kind |
|---|---|
| `A --> B` | `sync` |
| `A -- text --> B` | `sync`（text → label） |
| `A -->|text| B` | `sync`（text → label） |
| `A -.-> B` | `async`（虚线箭头） |
| `A -.text.-> B` | `async`（虚线 + label） |
| `A ==> B` | `flow`（粗线） |
| `A -- text --- B` | `flow` |
| `A ~~~ B` | `flow`（无箭头） |
| `A --x B` | `event`（×头箭头） |
| `A --o B` | `event`（空心圈） |

> `[label]` 与 `-- text --` 内的 text 会同时回到 IR 的 `edges[].label`，**不会**被错当成节点 id。

### `subgraph` → lanes

```
subgraph svc[服务层]
  ...
end
```

会被翻译成 `{id: "svc", label: "服务层"}` 写入 `lanes[]`，内部节点 `lane="svc"`。

### 节点命名推断

如果节点 id/label 含 db / redis / cache / kafka / queue / llm / gpt / agent / vector / embedding / user / web / api / server / cloud / s3 / storage / auth 等关键字，引擎会自动赋一个默认 `type`。**这个推断只是兜底**——精确控制请直接在产物 IR 上写 `type`。

---

## Sequence 语法映射

### 参与者声明

```
sequenceDiagram
  participant U as 用户
  actor Admin
  U->>S: 点击登录
  S-->>U: 200 OK
  U->>S: 拉取列表
  S->>DB: 查
  DB-->>S: rows
  S-->>U: 列表
```

- `participant X as 显示名` / `actor X as 显示名` → node.id=X, label=显示名
- 未声明的参与者若在箭头里出现，**自动注册**，用 id 当 label。

### 连线映射

| Mermaid | IR edge.kind |
|---|---|
| `A->>B` 或 `A->B` | `sync` |
| `A-->>B` 或 `A-->B` | `sync`（虚线表示异步返回：映射为 `kind=async`） |
| `A-x B` 或 `A--x B` | `return` |
| `A--)` | `async` |

> 文本消息放在箭头后 `: message`，写入 `edge.label`。

---

## StateDiagram 语法映射

```
stateDiagram-v2
  [*] --> Pending
  Pending --> Paid: 支付完成
  Paid --> Shipping: 出库
  Shipping --> Completed: 签收
  Paid --> Refunded: 申请退款
  state "高优先级订单" as HP {
    [*] --> Urgent
    Urgent --> Paid
  }
```

- `[start]` `[*]` 节点默认不引入（视为 `state` 起点/终点）。
- `state A as 显示名` → label 取显示名，否则 id。
- `state 块 { ... }` → 翻译为 groups。

---

## 转换输出

转换脚本输出一个 IR JSON（含 `meta.title="转换自 Mermaid"` 和 `warnings`），后续走 `validate` → `deliver`。**转换得到的 IR 可以手改后再编译**，因此适合作为快速骨架。

---

## 已知转换陷阱

| 输入 | 行为 | 备注 |
|---|---|---|
| 节点 label 含 `|` 字符 | 会与箭头 label 段冲突 | 用转义 `\|` 或换写法 |
| 节点 id 含中文 | 不允许（Mermaid 自己也不允许） | 把 id 设英文、label 设中文 |
| subgraph 嵌套 | 仅一层嵌套被吃 | 深层会被 flat 化 |
| `subgraph` 名字含空格 | 内部的空格会被替换为 `-` | id 规则限定 |
| `style X fill:xxx` | 忽略，不影响最终配色 | 风格以 IR meta/style 为准 |

---

## 完整流程示例

```bash
# 1. 写 mermaid
$ cat > e.mmd <<'MMD'
flowchart TD
  U[User] --> W[Web App]
  W --> API[API Gateway]
  API --> R[Retrieval]
  R --> V[(Vector DB)]
  R --> LLM[LLM]
MMD

# 2. 转 IR
$ python scripts/diagram.py mermaid e.mmd e.json
{
  "converted": true,
  "diagram_type": "workflow",
  "nodes": 6,
  "edges": 5,
  "warnings": []
}

# 3. 编译前手改 IR（升级 type，加 lane 等）
$ # 用 Edit 编辑 e.json

# 4. 编译
$ python scripts/diagram.py deliver e.json e.html
   → 已交付：e.html

# 5. 复检
$ python scripts/diagram.py check e.html
   → 全部通过
```
