# Icons · 40+ 产品图标

由 `scripts/icons.py` 实施。所有图标都是**纯 SVG 路径**（不是图片文件），内联到产物 HTML 中。

---

## 索引（按字母）

| id | 含义 | 关联 type |
|---|---|---|
| `ai-brain` | 神经网络 / 决策中枢 | `llm` |
| `agent` | Agent / 智能体 | `agent` |
| `anthropic` | Anthropic Logo | `llm` |
| `api` | API 接口 | `backend` |
| `arrow-flow` | 数据流箭头 | `dataflow` |
| `aws` | AWS 云 | `cloud` |
| `azure` | Azure 云 | `cloud` |
| `bash` | Bash 终端 | `tool` |
| `book` | 文档 / 知识 | `retriever` |
| `browser` | 浏览器 | `frontend` |
| `cdn` | CDN | `frontend` |
| `chart` | 图表 / BI | `planner` |
| `chat` | 对话气泡 | `frontend` |
| `cloud` | 云 | `cloud` |
| `code` | 代码编辑器 | `tool` |
| `cpu` | CPU | `backend` |
| `docker` | Docker | `backend` |
| `embed` | 嵌入 / embedding | `embedding` |
| `eye` | 监控 / 观测 | `planner` |
| `filter` | 过滤 / 转换 | `transform` |
| `firewall` | 防火墙 | `security` |
| `flow` | 流 | `dataflow` |
| `gear` | 齿轮 / 设置 | `tool` |
| `github` | GitHub 标识 | `tool` |
| `gpt` | GPT 模型 | `llm` |
| `helm` | 调度 / 舵 | `planner` |
| `huggingface` | HuggingFace | `llm` |
| `kafka` | Kafka 队列 | `messagebus` |
| `k8s` | Kubernetes | `cloud` |
| `langchain` | LangChain 框架 | `llm` |
| `llamaindex` | LlamaIndex | `llm` |
| `lock` | 锁 / Auth | `security` |
| `mail` | 邮件 / MQ | `messagebus` |
| `memory` | 记忆 | `memory` |
| `mobile` | 移动端 | `frontend` |
| `monitor` | 监控 | `planner` |
| `mysql` | MySQL | `database` |
| `node` | Node.js | `backend` |
| `openai` | OpenAI | `llm` |
| `pinecone` | Pinecone | `vector` |
| `postgres` | Postgres | `database` |
| `python` | Python | `backend` |
| `rabbitmq` | RabbitMQ | `messagebus` |
| `radar` | 雷达 / 检索 | `retriever` |
| `redis` | Redis | `database` |
| `router` | 路由 | `planner` |
| `s3` | S3 存储 | `storage` |
| `search` | 搜索 | `retriever` |
| `server` | 服务器 | `backend` |
| `shield` | 盾牌 / 网关 | `security` |
| `shop` | 商城 / 电商 | `frontend` |
| `snowflake` | Snowflake / 数仓 | `storage` |
| `spark` | Apache Spark | `dataflow` |
| `storage` | 存储桶 | `storage` |
| `tool` | 工具 | `tool` |
| `transform` | 转换 | `transform` |
| `user` | 用户 | `user` |
| `vector` | 向量库 | `vector` |
| `vue` | Vue.js | `frontend` |
| `worker` | Worker | `backend` |
| `zhipu` | 智谱 GLM | `llm` |

---

## 引用规则

```json
{ "id": "ord", "label": "订单服务", "type": "backend", "icon": "server" }
```

写 `icon` 时必须用上面列表的 id，否则 `UNKNOWN_ICON` 报警。

---

## 自定义图标（Advanced）

如果你想新增：

1. 在 `scripts/icons.py::ICONS` 追加新条目：
   ```python
   ICONS["my-product"] = {
       "viewBox": "0 0 24 24",
       "path": "M3 3 L21 21 ..."   # SVG path d 属性
   }
   ```
2. 用 SVG 编辑器（Figma / Inkscape）导出 24×24 path。
3. 在本文件追加新行。
4. 在 `examples/` 加一张样例图验证。

---

## 不允许的行为

- ❌ **不要用 emoji 当图标**：emoji 渲染依赖系统字体，会让不同操作系统看到不同结果。
- ❌ **不要引用外链 URL**（如 `https://...`）：违反自包含契约。
- ❌ **不要写 `<img>` 标签**：渲染引擎只接受 SVG path d-attr。
