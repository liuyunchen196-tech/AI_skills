# Shape Vocabulary · 语义形状库

由 `scripts/ir_schema.py::TYPE_SHAPES` 实施。一份 `nodes[].type` 决定三件事：**渲染什么 SVG 形状** + **默认图标** + **配色**。本表是 AI/Agent/UML 模式图的核心约束。

---

## 铁律

**LLM 永远画双边框矩形、Agent 永远画六边形、Database 永远圆柱、User 永远人形、Vector 永远柱状——** 别用错。

---

## 总表（基础）

| type | 形状（SVG） | 用途 |
|---|---|---|
| `default` | 矩形 | 通用 |
| `process` | 矩形 | 工作流默认节点 |
| `decision` | 菱形 | 工作流判定节点 |
| `start` | 圆角矩形 | 工作流起点（带颜色填充） |
| `end` | 双圆 + 横线 | 工作流终点 |
| `terminal` | 椭圆形 | 备用起点/终点 |
| `center` | 大圆 | 思维导图中心 |
| `state` | 圆角矩形 | 状态机节点 |

---

## 基础设施

| type | 形状 | 用途 |
|---|---|---|
| `frontend` | 矩形 | 前端/Web/H5 |
| `backend` | 矩形 | 后端服务 |
| `database` | **圆柱** | MySQL/Postgres/Redis/SQLite |
| `storage` | **圆柱** | 对象存储 / 文件系统 |
| `cloud` | 云 | SaaS / 公有云 |
| `security` | 盾形 | 网关 / WAF / Auth |
| `messagebus` | 跑道形 | Kafka / RabbitMQ |

---

## AI / Agent 模式

| type | 形状 | 用途 |
|---|---|---|
| `llm` | **双边框矩形** | GPT-4 / Claude / Zhipu |
| `agent` | **六边形** | 单 Agent |
| `multi-agent` | 嵌套六边形 | 群组 / Squad |
| `retriever` | 文档形（含放大镜） | RAG 检索器 |
| `vector` | **柱状图** | 向量库 / Faiss / Milvus |
| `embedding` | 矩阵格 | 嵌入模型 / BGE |
| `tool` | 工具形（扳手/齿轮） | 工具调用 |
| `planner` | 折线路径 | 规划器 / Router |
| `memory` | 时钟形 | 记忆系统 / Mem0 |

---

## UML 角色

| type | 形状 | 用途 |
|---|---|---|
| `actor` | **人形** | 用例图 actor |
| `usecase` | 椭圆 | 用例图用例 |
| `class` | 三段矩形（带 attribute/method） | 类图 |
| `component` | 大矩形（带两个小矩形） | 组件图 |
| `deployment` | 三维盒 | 部署图节点 |
| `package` | 带标签的大矩形 | 包图 |

---

## 形状落入规则

引擎的优先级是：**显式 `icon` 字段 > type 推断**。

```json
{ "id": "db", "label": "用户库", "type": "database", "icon": "postgres" }
```

- 有 `type` 无 `icon` → 走 type 默认形状 + 默认图标。
- 有 `icon` 无 `type` → 走 default 形状 + 指定图标。
- 两者都有 → 用 type 的形状，用 icon 的图标。

---

## 颜色与形状的耦合（为什么不能改）

形状影响信息密度，也参与语义——LLM 节点的双边框视觉上"自带权重感"，让读者一眼分辨 AI 模型与服务节点。**改形状 = 改语义**。下列例外**禁止**触犯：

1. ❌ 把 `llm` 节点的形状改成普通矩形。
2. ❌ 把 `database` 改成矩形。
3. ❌ 把 `agent` 改成矩形。
4. ❌ 把 `decision` 改成矩形。

如果你想"统一视觉"，去选一套**柔和的形状库**（如 `paper-zen`），不要去改语义形状本身。

---

## 自定义形状（Advanced）

如果你有专业场景需要新增形状，按以下步骤：

1. 在 `scripts/ir_schema.py::TYPE_SHAPES` 追加新映射：
   ```python
   TYPE_SHAPES["my-thing"] = "hexagon-double"
   ```
2. 在 `scripts/render_engine.py` 的 `draw_node` 追加形状分支。
3. 在 `examples/` 添一份样例验证。
4. 在本文件 + `SKILL.md` 同步登记。

> 不要试图在 IR 里直接写"画一个三角形"——形状是**枚举**，不是字符串。

---

## 关联概念

- **图标库**（`@icons.md`）：形状决定 SVG path，图标决定叠加小图。
- **风格**（`@styles.md`）：风格决定填充色，边框色，字体色——但不改形状。
- **契约**（`@composition-contract.md`）：形状不在契约硬性校验里；语义错配由 `UNKNOWN_NODE_TYPE` 兜底。
