# Composition Contract · 9 类硬契约

由 `scripts/composition.py` 实施。本文件是 validate / check 阶段所有 finding 的**权威解释**。

---

## 总原则

- **ERROR**：图本身有问题，**必须修到 ERROR=0** 才能交付。
- **WARNING**：图的某个质量指标未达 showcase 级别。标准档（`meta.quality_profile=standard`）允许保留；showcase 档需逐条处理。

退出码：

- `0`：可交付。ERROR=0，且（standard 或 WARNING=0）。
- `1`：不可交付。按 finding 的 `supportedFixes` 改 IR。

---

## 第 1 类 · schema

| code | level | 含义 | 修复建议 |
|---|---|---|---|
| `IR_MISSING_FIELD` | error | 节点缺 `id`/`label` | 补全 |
| `IR_TYPE_MISMATCH` | error | 字段类型错 | 按 `ir-schema.md` 改 |
| `IR_DUPLICATE_ID` | error | 同 id 出现两次 | 改其中一个 |
| `IR_INVALID_DIAGRAM_TYPE` | error | diagram_type 不在枚举 | 换有效值 |
| `IR_EDGE_TO_SELF` | error | 自环边 | 通常删除（除非有意） |
| `IR_EDGE_TO_MISSING` | error | source/target 不存在 | 补节点 |
| `NO_NODES` | error | 没有任何节点（matrix 例外） | 加节点 |

---

## 第 2 类 · layout

| code | level | 含义 | 修复建议 |
|---|---|---|---|
| `NODE_OUT_OF_CANVAS` | warning | 节点超出画布边界 | 自动适配，通常只在边角触边出现 |
| `NODE_OVERLAP` | error | 两节点矩形重叠 | 调整 `col` / 拆节点 / 拆图 |
| `TINY_NODE` | warning | 节点过小（w<60 或 h<30） | 加长 label 或合并节点 |

---

## 第 3 类 · spacing

| code | level | 含义 | 修复建议 |
|---|---|---|---|
| `SPACING_CRAMPED` | warning | 同层节点 GAP < 12 或异层 GAP < 24 | 增大画布 / 减节点 |
| `OVERLONG_LABEL` | warning | 标签长度 > 8 字（中文字符） | 拆分或缩短 |

---

## 第 4 类 · route

| code | level | 含义 | 修复建议 |
|---|---|---|---|
| `TOO_MANY_BENDS` | warning | 路径折弯 > 4（回边）/ > 2（普通边） | 调整节点布局 / 给 `via` |

> 默认参数：常规路径最多 2 折，回边最多 4 折。超出会降低可读性。

---

## 第 5 类 · crossing

| code | level | 含义 | 修复建议 |
|---|---|---|---|
| `EDGE_CROSSING` | warning | 两段边交叉 | 调整同层节点顺序 / 拆分过密的连线 / 把细节移入节点 desc |

---

## 第 6 类 · label

| code | level | 含义 | 修复建议 |
|---|---|---|---|
| `LABEL_OVER_NODE` | warning | label 矩形与某节点重叠 | 错开标签垂直高度 / 缩短 label / 改路由 |
| `LABEL_OVER_EDGE` | warning | label 矩形与其他边线段重叠 | 错开两边的路由高度 / 缩短 label / 删冗余 label |
| `LABEL_OUT_OF_CANVAS` | warning | label 超出画布边界 | 缩短 / 改路由 |

---

## 第 7 类 · typography

| code | level | 含义 | 修复建议 |
|---|---|---|---|
| `TEXT_OVERFLOW` | warning | label/desc 文字溢出节点矩形 | 缩短 / 加节点高度 |
| `TEXT_OUT_OF_NODE` | warning | 文字宽度超节点 w | 同上 |

---

## 第 8 类 · semantics

| code | level | 含义 | 修复建议 |
|---|---|---|---|
| `UNKNOWN_NODE_TYPE` | error | node.type 不在白名单 | 查 `@shape-vocabulary.md` 用合法值 |
| `UNKNOWN_ICON` | error | node.icon 不在 40+ 列表 | 查 `@icons.md` |
| `ISOLATED_NODE` | warning | 节点没有任何连线 | 补连线 / 移入备注区 / 删除 |

---

## 第 9 类 · delivery（仅产物 check 阶段）

| code | level | 含义 | 修复建议 |
|---|---|---|---|
| `BAD_HTML` | error | 产物不是合法 HTML | 用 `deliver` 重新生成 |
| `NO_SVG` | error | 产物不含 `<svg>` | 同上 |
| `NO_VIEWER_HOOK` | warning | 产物缺 `byai-diagram` 挂载点 | 同上 |
| `HAS_EXTERNAL` | error | 产物含 http/https 外链 | 重生成（应全部 inline） |
| `NOT_SELF_CONTAINED` | error | 产物体积异常或多次引用外链 | 重生成 |

---

## CLI 协议

```bash
# 验证 IR
python scripts/diagram.py validate <ir.json> [--style <id>] [--quality <profile>]
python scripts/diagram.py validate <ir.json> --json          # JSON 输出

# 渲染（输出自包含 .html）
python scripts/diagram.py render <ir.json> <out.html>

# 交付（输出自包含 .html，带 sha256）
python scripts/diagram.py deliver <ir.json> <out.html>

# 检查产物（最终复检）
python scripts/diagram.py check <out.html>

# Mermaid → IR
python scripts/diagram.py mermaid <in.mmd> <out.json>
python scripts/diagram.py validate <out.json>             # 转换后校验

# 对比两图
python scripts/diagram.py compare <before.ir.json> <after.ir.json> <delta.html>

# 环境诊断
python scripts/diagram.py doctor
```

### `compare` 子命令

前置条件：两份 **IR JSON**（`base` / `head`，即你编写或导出的 .json 源文件；建议先 `validate` 通过）。

输出 `<delta.html>`：**Delta 差异报告**
- 节点差集：新增 / 删除 / 修改（标签·类型·描述·技术变更）/ 移动（层级·泳道·分组变更）
- 连线差集：新增 / 删除 / 重新路由（标签·类型变更）
- 顶部统计卡（新增/删除/修改/移动节点、新增/删除/连线变更），下方明细表
- 不做内容推断，只做拓扑 diff。

---

## Finding 结构（每条）

```json
{
  "level": "error | warning",
  "code": "EDGE_CROSSING",
  "subject": "$.edges[e1]",
  "message": "与 e2 在 (450, 320) 交叉",
  "evidence": { "...": "可机器读取的细节" },
  "supportedFixes": [
    "调整同层节点顺序",
    "拆分过密的连线",
    "把细节移入节点描述而非新增连线"
  ]
}
```

subject 是 JSONPath，`evidence` 包含坐标、id、measure，`supportedFixes` 是人类可读的修复建议（≥ 1 条）。

---

## 写作者契约

下列规则在创作期就要守住，不要等 validate 报警才修：

1. **节点数 + 连线数 ≤ 40**：超过就拆图。
2. **lane 数 ≤ 5**：超过就横向拆。
3. **type 不在白名单**：查 `@shape-vocabulary.md`。
4. **icon 不在 40+ 列表**：查 `@icons.md`；没有就**不加**（让节点变 default 形状 + 文字）。
5. **label ≤ 8 字**（中文）/ ≤ 16 字（英文）：更长就拆成 label + desc。
6. **同一图型不要混用中英 label**（会破坏文本宽度估算）。
7. **相同语义的角色应当用相同 type**：不要给两个 LLM 一个写 `llm` 一个写 `agent`。
