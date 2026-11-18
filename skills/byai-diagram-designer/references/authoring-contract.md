# Authoring Contract · 创作期规范

这份是给 **AI 写作者**（Agent）在写 IR 之前就要守住的规范——不要等 validate 报警才纠正。

---

## 1. 命名规则

### 节点 id

- `[A-Za-z_][A-Za-z0-9_.-]*`（短而稳定）
- 推荐短前缀：
  - `gw-` `api-` `svc-`（网关/服务）
  - `db-` `cache-` `mq-`（数据）
  - `ui-` `web-` `mob-`（前端）
  - `fe-` `be-`（前后端）
  - `act-` `ev-`（actor / event）
- 别用太人性化的命名（`用户登录中间件` 等）；用稳定短前缀便于结构引用。

### lane id

- 小写短串（`client`、`edge`、`svc`、`data`、`infra`、`obs`）。
- lane label 写中文/英文展示文字。

### 节点 label

- 中文 4–8 字以内。
- 英文 ≤ 16 字。
- 严禁：`"判断"`作为非菱形节点 label、`"数据库"` 作为非 cylinder 节点 label。

---

## 2. 节点数控制

| 图型 | 推荐 | 上限 |
|---|---|---|
| architecture | 8–15 | 30 |
| dataflow | 6–12 | 25 |
| workflow | 5–10 | 20 |
| lifecycle | 4–8 | 12 |
| sequence | 3–5 个 actor | 6 |
| comparison | 2–3 主体 | 3 |
| ai.rag | 8–14 | 25 |
| ai.multi-agent | 5–10 | 18 |

> 超出上限时先**拆图**而不是硬塞。

---

## 3. 连线规则

### kind

| kind | 含义 | 用在哪 |
|---|---|---|
| `sync` | 同步调用 | 普通 HTTP/RPC/gRPC |
| `async` | 异步 / 虚线 | 消息消费、回调 |
| `flow` | 数据流（粗） | 流水线主流向 |
| `event` | 事件触发 | 状态机 transition |
| `return` | 末端 x 型回箭头 | 时序图响应 |
| `branch` | 主题分支 | 思维导图 |

### 控制回边

回边（`source.row > target.row`）会增加折弯数。当出现 2–3 个回边时**强烈建议**重排节点层序：
- 提取公共上游节点放到更高层
- 把"输出方"放到"输入方"下方
- 或者拆成两张图

---

## 4. lane 用法

- 架构图优先用 3–5 个 lane（client / edge / svc / data），明确上下游。
- 部署图（`uml.deployment`）用 3–4 个 lane（dc / cluster / node / pod）。
- 不用 lane 时，所有节点视为同一区，引擎自动按列分组。

---

## 5. type 选型速查

> 见 `@shape-vocabulary.md` 拿完整清单。

| 节点角色 | type |
|---|---|
| Web/H5/App | `frontend` |
| Java/Go/Python 服务 | `backend` |
| MySQL/PG/Mongo/Redis | `database` |
| S3/MinIO | `storage` |
| AWS/Azure | `cloud` |
| Kong/SpringSecurity/auth | `security` |
| Kafka/RabbitMQ | `messagebus` |
| OpenAI/Anthropic/智谱 | `llm` |
| LangChain agent | `agent` |
| RAG 检索器 | `retriever` |
| Faiss/Milvus | `vector` |
| Embedding 模型 | `embedding` |
| 工具调用 | `tool` |
| 规划器 | `planner` |
| 记忆系统 | `memory` |
| 决策判定 | `decision` |
| 工作流起点 | `start` |
| 工作流终点 | `end` |
| 状态机节点 | `state` |
| 用例 | `usecase` |
| Actor | `actor` |
| 类 | `class` |
| 组件 | `component` |

---

## 6. icon 选型速查

> 见 `@icons.md` 拿完整清单。**选对不选多**：同图里同类角色尽量用同一 icon，方便读者一眼对齐。

- LLM：`openai` `anthropic` `gpt` `huggingface` `langchain` `llamaindex` `zhipu`
- 数据库：`mysql` `postgres` `redis` `snowflake`
- 消息：`kafka` `rabbitmq` `mail`
- 云：`aws` `azure` `cloud` `k8s` `docker`
- 框架：`vue` `python` `node` `bash` `code`
- 通用：`server` `cpu` `storage` `shield` `lock` `gear` `book`

---

## 7. label 写法

### 标签该有什么

- `<动作 / 名字> + <关键属性>`：避免单字标签。
- 同一节点最多两行：主标 + 描述。

```
{ "label": "订单服务", "desc": "下单/支付/退款" }
{ "label": "API 网关", "desc": "Auth + 限流" }
{ "label": "Vector DB", "desc": "Faiss · 1024 维" }
```

### 不该写什么

- ❌ 长句字面（"这个模块负责处理来自客户端的请求然后转发给后端服务集群"）→ 拆 desc
- ❌ 重复词（"订单订单订单"）→ 简化
- ❌ 拼写混杂（"OrderSvc" + "订单服务"）→ 统一

### 关系标签（edge.label）

- ≤ 8 字（中文字符）或 ≤ 16 字（英文）
- 关系动词：`调用 / REST / TCP / SQL / 写 / 读 / 缓存 / 验证 / 转发 / 返回`
- 标签放在箭头方向**更上游**的语义位置：

```
A --REST--> B  →  "客户端 → 服务端调用"
A --查--> B    →  "数据库语句"
```

---

## 8. 同一图型内的\"角色一致\"原则

**同一种节点在图里只能对应一个 type**：

- 三个 LLM 节点：全 `llm` + 全 `icon=openai`，不要 LLM A 用 `llm` 而 LLM B 用 `agent`。
- 三个 Redis：全 `database` + 全 `icon=redis`。
- 三个 User actor：全 `actor` + 全 `icon=user`。

这样读者才能在视觉上快速对齐——视觉一致性是图的「隐性契约」。

---

## 9. 风格选择

> 见 `@styles.md`。

- **默认 `flat-icon`**——大多场景适合。
- 公众号长文 → `olive-journal`（与公众号写作助手色系一致）。
- 不要默认多版本；出一张用户指定的版本即可。

---

## 10. 写后自检清单（写完跑 validate 之前先过一遍）

- [ ] 节点数是否 < 上限
- [ ] 所有 `type` 是否在白名单（详见 `@shape-vocabulary.md`）
- [ ] 所有 `icon` 是否在 40+ 列表（详见 `@icons.md`）
- [ ] label 长度是否 < 8/16 字
- [ ] 每张图有没有 style/quality 字段？
- [ ] 有没有孤立节点（应改成连线或删除）
- [ ] 有没有回边（>3 时强烈建议拆图）

通过上面七点后，validate 一般只剩几何微调 warning，可以直接出图。
