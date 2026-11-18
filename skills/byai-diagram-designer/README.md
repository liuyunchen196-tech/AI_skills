# 流程图设计助手（byai-diagram-designer）

> 一句话需求 → 一张自包含 HTML 流程图。
> 10 大类图型、12 套原创风格、40+ 产品图标、9 类硬契约校验、交互查看器。

**当前版本：v1.0.5**（2026-10-27：修复提审驳回——`skillhub-meta.json` 此前被打包器当成内部档案排除，而 SKILL.md 目录树里写着它，平台按「SKILL.md 引用即必需资源」判定资产包缺 1 项。本版让该文件随包交付，并在打包器里补一条闸门：SKILL.md 声明过的文件必须在包内存在）

**上一版本：v1.0.4**（2026-10-19：二次更换技能图标——深蓝 squircle 圆角底托 + 「起点→决策菱形→终点」流程图形，青绿菱形焦点、柔光连线；**四角真透明**（RGBA alpha=0，深色市场列表不露砖），水印区已修复。512×512 / 213KB）

**上一版本：v1.0.2**（2026-10-19：修正两处过时的交叉引用——`olive-journal` 风格说明中「百应公众号写作助手」已更名「公众号写作助手」；补全 master 侧 LICENSE 文件并将其中产品名同步改为「流程图设计助手」）

**上一版本：v1.0.1**（2026-10-18：中文名由「百应流程图设计助手」改为「流程图设计助手」，引擎修复汇总计数 bug 与 type 误报，新增 `scripts/check.py` 质量门禁）

---

## 更新日志

### v1.0.5（2026-10-27）

- **提审驳回修复**：平台反馈「资产包缺少必需资源 1 项：文件 skillhub-meta.json（SKILL.md 引用）」。根因不是文件不在仓库，而是 `byai-skills/pack_zip.py` 的 `EXCLUDE_FILES` 把它当成"内部提审档案"排除了，包内只剩 SKILL.md 那一行声明。
- 修法两层：① 打包器不再排除 `skillhub-meta.json`，它属于随包交付的元数据；② 打包器新增第 7 条闸门——扫描 SKILL.md 的目录树与 `@path` 引用，声明过的文件在包内缺失即拒绝打包；并在生成 zip 后**从 zip 复验**声明资源是否真的在里面（打包自检不算数）。
- 顺带把 `skillhub-meta.json` 的 `_note` 从内部口吻改成字段说明，因为它现在会随包发给平台。
- 变异反证：把 `skillhub-meta.json` 临时移走后跑闸门，必须报「SKILL.md 声明但包内缺失」，还原后转绿——证明这条闸门抓得住本次事故形态。
- 引擎零改动，`scripts/check.py` 三层（部署闸门 + 样例回归 + 变异反证）仍全绿。

### v1.0.4（2026-10-19）

- **图标二版（Kenny 反馈一版不好看且非透明底）**：改为深蓝渐变 squircle 圆角底托（主流 app 图标形态）+ 内部「起点圆角节点 → 青绿发光决策菱形 → 终点节点」正交连线图形，箭头指示流向；一版的三横排节点构图过于平淡，且米白底在深色市场列表里像贴砖，本版四角抠真透明（RGBA，alpha=0，圆角外区域完全透明，带 1.2px 高斯抗锯齿）。
- 水印处理：右下角水印亮像素区（x904-1012/y965-1013）以邻域底色 (21,26,39) 覆盖 + 圆角外区域直接透明化，双重清除，圆角内残留采样 0。
- 注：ImageGen 的 `background:transparent` 参数实际未生效（产物仍 RGB），透明效果由后处理圆角矩形 mask 实现；圆角半径由边缘扫描自动测定（212px）。

### v1.0.3（2026-10-19）

- **更换技能图标**：新 LOGO 为扁平几何风「三节点 + 正交连线 + 箭头」构图，直接图解流程图语义；深蓝（#1F3A5F 附近）主色 + 青绿（#1FB89A 附近）节点点睛，米白底。512×512 PNG、41KB（平台规范 <500KB），右下角工具水印已用背景色填充清除（残留采样 0）。
- 头像同步更新 master 与安装态两处（`avatars/skill.png`）。

### v1.0.2（2026-10-19）

- **修正交叉引用**：`references/authoring-contract.md` 与 `references/styles.md` 中「百应公众号写作助手」→「公众号写作助手」（对方技能已于 v1.2.7 改名，引用不同步会指错）。
- **补齐 LICENSE**：master 仓库此前缺 LICENSE（仅安装态有），本次补入并将其中的产品名改为「流程图设计助手」，公司/品牌署名（百应AI工作室）保留。
- 名称与元数据复核：display_name「流程图设计助手」、examples 3 条、skillhub 档案均已就位，本次仅做查漏补缺与版本归档。

---

## 这是什么

把"画图难的不是构图，是画对"这句底线落到产品里。**你只管意图，编译器管正确性。**

- 一段自然语言描述，给一张可直接打开的 HTML 图。
- 一段 Mermaid 文本，给一张"编译过"的高质量图。
- 6 行 JSON，输出一张 0 ERROR 通过 hard contract 校验的图。

产物：**单一自包含 HTML**——内联 SVG、内联 CSS/JS、零外链、零运行时依赖。

---

## 三种使用方式

### 1. 自然语言描述（通过 Agent 调起本 skill）

> "画个 RAG 系统架构图" → Agent 写 IR → `validate` → `deliver` → 一张 HTML

### 2. Mermaid 直接转图

```bash
python scripts/diagram.py mermaid input.mmd output.ir.json
python scripts/diagram.py deliver output.ir.json output.html
```

### 3. 手写 IR，编译成图

```bash
python scripts/diagram.py validate my.json          # 0 ERROR 即可交付
python scripts/diagram.py deliver my.json my.html
python scripts/diagram.py check my.html             # 产物复检
```

---

## 能力速览

| | 数量 / 数量级 |
|---|---|
| 图型 | 10 大类（architecture/dataflow/workflow/lifecycle/sequence/comparison/mindmap/ai.*/uml.*） |
| 风格 | 12 套原创视觉色板 |
| 语义形状 | 30+（LLM 双边框矩形、Agent 六边形、Database 圆柱等） |
| 产品图标 | 40+（OpenAI / Anthropic / Kafka / Redis / K8s 等，纯 SVG 路径） |
| 校验契约 | 9 类（schema/layout/spacing/route/crossing/label/typography/semantics/delivery） |
| 运行时依赖 | **零**（纯 Python stdlib） |

---

## 引擎核心

确定性、零依赖。Python 3.8+，**不需要安装任何第三方包**。

| 模块 | 职责 |
|---|---|
| `scripts/ir_schema.py`    | IR 规范化、自动分层布局、形状映射 |
| `scripts/geometry.py`     | 正交路由、端口分散、跨接桥、画布计算 |
| `scripts/composition.py`  | 9 类硬契约校验、finding 与 supportedFixes |
| `scripts/styles.py`       | 12 套原创风格定义 |
| `scripts/icons.py`        | 40+ 图标 SVG 路径库 |
| `scripts/render_engine.py`| IR → 自包含 HTML 确定性编译 |
| `scripts/mermaid2ir.py`   | Mermaid → IR 转换 |
| `scripts/compare.py`      | Before/After/Delta 对比 |
| `scripts/diagram.py`      | 统一 CLI 入口 |
| `scripts/check.py`       | 质量门禁：部署闸门 + 样例回归 + 变异反证 |

---

## 质量门禁（发布前必跑）

"编译器管正确性"不能只挂在嘴边——**本 skill 的正确性由确定性门禁保证，不靠 prompt 自觉**。

```bash
python scripts/check.py
```

三层校验，**全部通过（EXIT 0）才允许打包发布**：

| 层 | 检什么 | 失败意味着 |
|---|---|---|
| L1 部署闸门 | SKILL.md 元数据、skillhub-meta.json 对齐、11 个必需文件、头像规格、目录层级 ≤2、零中文文件名、无 `__pycache__`、零 CDN、纯 stdlib | 包结构不合规，不许发布 |
| L2 样例回归 | 6 张跨图型样例全量走 validate → deliver → check | 引擎改了合法输入的行为，回归 |
| L3 变异反证 | 4 组坏 IR 必须被 EXIT 1 拒绝且带「不可交付」；1 组缺 type 的合法 IR 必须放行；4 组汇总计数必须自洽 | 校验器漏报或自相矛盾（如汇总说通过却 exit=1） |

> 变异反证是这套范式的核心：**先证明"坏输入一定被抓"，再证明"好输入一定放行"**，两边都钉死，校验器才可信。

---

## 跑通一个最小例子

```bash
# 进入 skill 目录
cd skills/byai-diagram-designer

# 用现成样例
python scripts/diagram.py validate examples/web-app.architecture.json
python scripts/diagram.py deliver  examples/web-app.architecture.json out.html

# 自检产物
python scripts/diagram.py check out.html

# 浏览器打开 out.html ← 内含交互查看器（focus / 上下游可达 / 分享卡）
```

预期：

```
图型        : architecture
节点 / 连线 : 5 / 4
画布        : 488 × 734
交叉        : 0
ERROR 0 · WARNING 0
→ 全部通过，达到 showcase 级别。
已交付：out.html（xxx 字节，sha256=...）
```

---

## 关键设计约束（红线）

> 任何一条违反，产物会被降为"unsafe"——拒绝交付。

1. **几何正确性是底线**：正交、零交叉、不压节点/连线、不出画布。编译器 100% 负责，不允许"看起来差不多"放行。
2. **不传播未授权的样式**：12 套风格是原创色板，**不要从外部网页扒样式表**。
3. **保持语义形状一致**：LLM 永远双边框矩形、Agent 永远六边形。**别给 LLM 用 circle**。
4. **忠实上游、禁止编造**：架构图严禁"模拟"真实服务调用、严禁生成"看起来在跑数据"的伪管道。
5. **降级优先于失败**：cairosvg 不在 → SVG；puppeteer 不在 → 不挂查看器，**老实说明已跳过**。
6. **不要手写 HTML**：所有产物由 `render_engine.py` 编译。手写即失去契约保证。

---

## 目录结构

```
byai-diagram-designer/
├── SKILL.md                       AI Agent 入口（必读）
├── README.md                      你正在读
├── skillhub-meta.json             提审档案（版本/描述/examples）
├── avatars/                       技能头像
├── scripts/                       引擎核心 9 模块 + check.py 质量门禁
├── templates/viewer.html          查看器模板
├── references/                    8 份深度文档
└── examples/                      6 张跨图型样例 IR
```

---