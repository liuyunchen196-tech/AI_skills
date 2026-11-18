---
name: flowchart-design
display_name: 流程图与SVG图表设计
display_name_en: Flowchart & SVG Diagram Designer
description: 生成专业 SVG 流程图——浅色主题，中文优先。支持流程图、架构图、时序图、类图、思维导图、时间线、原理示意图、状态机、数据流图。输出独立 .svg 文件，内嵌样式。
description_zh: 生成专业 SVG 流程图——浅色主题，中文优先。支持流程图、架构图、时序图、类图、思维导图、时间线、原理示意图、状态机、数据流图。输出独立 .svg 文件，内嵌样式。
description_en: Generate professional SVG flowcharts — light theme, Chinese-first. Supports flowcharts, architecture diagrams, sequence diagrams, class diagrams, mind maps, timelines, principle illustrations, state machines, and data-flow diagrams. Outputs a standalone .svg file with embedded styles.
version: 1.117.3
---

# 图表生成器

生成专业 SVG 图表，覆盖多种图表类型。所有输出为单个自包含 `.svg` 文件，内嵌样式与字体。**默认中文输出**。

## 支持的图表类型

| 类型 | 适用场景 | 特征 |
|------|---------|------|
| **Architecture** / 架构图 | 系统组件与关系 | 分组框、连接箭头、区域边界 |
| **Flowchart** / 流程图 | 逻辑判断、流程步骤 | 菱形决策、圆角步骤框、方向箭头 |
| **Sequence** / 时序图 | 参与者间按时间交互 | 竖向生命线、横向消息、激活条 |
| **Structural** / 结构图 | 类图、ER图、组织架构 | 分栏框、类型化关系线 |
| **Mind Map** / 思维导图 | 头脑风暴、主题展开 | 中心节点、辐射分支、有机布局 |
| **Timeline** / 时间线 | 时序事件 | 横向/纵向轴线、事件标记、时间段 |
| **Illustrative** / 原理示意图 | 概念解释、对比说明 | 自由布局、图标、注释、视觉隐喻 |
| **State Machine** / 状态机 | 状态跃迁、生命周期 | 圆角状态节点、标记转移、起止标记 |
| **Data Flow** / 数据流图 | 数据转换管线 | 处理气泡、数据存储、外部实体 |

## 设计系统

### 颜色体系（浅色主题）

| 分类 | 填充 (rgba) | 描边 | 用途 |
|------|------------|------|------|
| Primary / 主色 | `rgba(14, 116, 144, 0.1)` | `#0891b2` (青色) | 前端、用户侧、输入 |
| Secondary / 辅色 | `rgba(5, 150, 105, 0.1)` | `#059669` (翠绿) | 后端、服务、处理 |
| Tertiary / 数据库 | `rgba(124, 58, 237, 0.1)` | `#7c3aed` (紫色) | 数据库、存储、持久化 |
| Accent / 高亮 | `rgba(217, 119, 6, 0.08)` | `#d97706` (琥珀) | 云、基础设施、区域 |
| Alert / 警告 | `rgba(225, 29, 72, 0.1)` | `#e11d48` (玫瑰红) | 安全、错误、警告 |
| Connector / 连接 | `rgba(234, 88, 12, 0.08)` | `#ea580c` (橙色) | 总线、队列、中间件 |
| Neutral / 中性 | `rgba(100, 116, 139, 0.12)` | `#64748b` (石板灰) | 外部、通用、未知 |
| Highlight / 强调 | `rgba(37, 99, 235, 0.1)` | `#2563eb` (蓝色) | 活跃状态、焦点、当前步骤 |

### 排版

```svg
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&amp;display=swap');
  text { font-family: 'JetBrains Mono', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif; }
</style>
```

字号按角色：
- **标题：** 16px, weight 700
- **组件名：** 11-12px, weight 600
- **副标签/说明：** 9px, weight 400, color `#64748b`
- **注释：** 8px, weight 400
- **箭头小标签：** 7-8px

### 核心视觉元素

**背景：** `#f8fafc` (slate-50) 浅色，配合细微网格：
```svg
<defs>
  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e2e8f0" stroke-width="0.5"/>
  </pattern>
</defs>
<rect width="100%" height="100%" fill="#f8fafc"/>
<rect width="100%" height="100%" fill="url(#grid)"/>
```

**箭头标记（标准）：**
```svg
<marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
  <polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8"/>
</marker>
```

**箭头标记（按颜色）：**
```svg
<marker id="arrow-cyan" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
  <polygon points="0 0, 10 3.5, 0 7" fill="#0891b2"/>
</marker>
```

**开口箭头（异步/返回消息）：**
```svg
<marker id="arrow-open" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
  <polyline points="0 0, 10 3.5, 0 7" fill="none" stroke="#94a3b8" stroke-width="1.5"/>
</marker>
```

### SVG 结构 & 图层顺序

按以下顺序绘制（SVG 从后往前渲染）：

1. 背景填充 + 网格
2. 区域/分组边界（虚线）
3. 连接箭头与线条
4. 不透明遮罩层（与组件框相同位置，`fill="#f8fafc"`）
5. 组件框（半透明填充 + 描边）
6. 文字标签
7. 图例（底部右下角）
8. 标题栏（左上角）

不透明遮罩层技巧至关重要——组件框的半透明填充会透出下方的箭头：
```svg
<!-- 遮罩层：不透明背景遮挡箭头 -->
<rect x="100" y="100" width="160" height="60" rx="6" fill="#f8fafc"/>
<!-- 视觉层：样式化组件 -->
<rect x="100" y="100" width="160" height="60" rx="6" fill="rgba(14,116,144,0.1)" stroke="#0891b2" stroke-width="1.5"/>
<text x="180" y="125" fill="#1e293b" font-size="11" font-weight="600" text-anchor="middle">API 网关</text>
<text x="180" y="141" fill="#64748b" font-size="9" text-anchor="middle">Kong / Nginx</text>
```

### 间距规则

严格遵循以下规则，防止重叠和过度留白：

**高度（按文本行数）：**
- 单行框（仅标题）：高度 35-40px
- 双行框（标题 + 副标签）：高度 50-60px
- 三行以上：高度 70-90px

**宽度（按文本长度）：**
- 中文 1-4 个字（标题如"开始"）：120-140px
- 中文 5-8 个字（标题如"填写注册信息"）：160-200px
- 中文 9+ 个字：200-240px
- 长英文短语：每字符 ~7px + 40px 内边距
- **禁止**：固定 220px 宽用来装 6 个中文字，会导致大面积留白

**间距：**
- 框间垂直间距：25-40px（容纳箭头 + 可选标签）
- 横向分支偏移：决策中心 ±160px
- 箭头标签：距任何框边缘 10px
- viewBox：内容 + 两侧 30px 内边距

**决策菱形尺寸：**
- 默认宽度 120-140px，高度 70-80px
- 文字 ≤ 6 个中文字

### 组件模板

**标准框（服务/流程）：**
```svg
<rect x="X" y="Y" width="160" height="60" rx="6" fill="#f8fafc"/>
<rect x="X" y="Y" width="160" height="60" rx="6" fill="FILL" stroke="STROKE" stroke-width="1.5"/>
<text x="CX" y="Y+24" fill="#1e293b" font-size="11" font-weight="600" text-anchor="middle">Name</text>
<text x="CX" y="Y+40" fill="#64748b" font-size="9" text-anchor="middle">description</text>
```

**决策菱形（流程图）：**
```svg
<g transform="translate(CX, CY)">
  <polygon points="0,-35 50,0 0,35 -50,0" fill="#f8fafc"/>
  <polygon points="0,-35 50,0 0,35 -50,0" fill="rgba(217,119,6,0.08)" stroke="#d97706" stroke-width="1.5"/>
  <text y="4" fill="#1e293b" font-size="10" font-weight="600" text-anchor="middle">条件？</text>
</g>
```

**数据库圆柱：**
```svg
<g transform="translate(X, Y)">
  <rect x="0" y="10" width="120" height="50" rx="2" fill="#f8fafc"/>
  <ellipse cx="60" cy="10" rx="60" ry="12" fill="#f8fafc"/>
  <ellipse cx="60" cy="60" rx="60" ry="12" fill="#f8fafc"/>
  <rect x="0" y="10" width="120" height="50" fill="rgba(124,58,237,0.1)"/>
  <ellipse cx="60" cy="10" rx="60" ry="12" fill="rgba(124,58,237,0.1)" stroke="#7c3aed" stroke-width="1.5"/>
  <ellipse cx="60" cy="60" rx="60" ry="12" fill="rgba(124,58,237,0.1)" stroke="#7c3aed" stroke-width="1.5"/>
  <line x1="0" y1="10" x2="0" y2="60" stroke="#7c3aed" stroke-width="1.5"/>
  <line x1="120" y1="10" x2="120" y2="60" stroke="#7c3aed" stroke-width="1.5"/>
  <text x="60" y="40" fill="#1e293b" font-size="11" font-weight="600" text-anchor="middle">PostgreSQL</text>
</g>
```

**区域边界：**
```svg
<rect x="X" y="Y" width="W" height="H" rx="12" fill="none" stroke="#d97706" stroke-width="1" stroke-dasharray="8,4"/>
<text x="X+12" y="Y+16" fill="#d97706" font-size="9" font-weight="600">AWS us-east-1</text>
```

**安全组：**
```svg
<rect x="X" y="Y" width="W" height="H" rx="8" fill="none" stroke="#e11d48" stroke-width="1" stroke-dasharray="4,4"/>
<text x="X+10" y="Y+14" fill="#e11d48" font-size="8" font-weight="500">VPC / 安全组</text>
```

## 类型特定的布局参考

确定此 SKILL.md 所在目录为 `{baseDir}`。在开始布局前，读取对应类型的参考文件，路径为 `{baseDir}/references/`。

### 架构图
→ 读取 `{baseDir}/references/architecture.md`

要点：从左到右或从上到下的数据流。用区域边界对相关服务分组。层间使用总线/连接器。数据库放置在底部或右侧。

### 流程图
→ 读取 `{baseDir}/references/flowchart.md`

要点：自上而下的主流程。决策用菱形，Yes/No 标签标在出口箭头。起止用大圆角矩形。Highlight 色标"正确路径"。

### 时序图
→ 读取 `{baseDir}/references/sequence.md`

要点：参与者为顶部分栏框，垂直虚线生命线，水平箭头代表消息（实线=同步，虚线=返回）。时间向下流动。激活条表示处理。复杂场景编号消息。

### 结构图
→ 读取 `{baseDir}/references/structural.md`

要点：分栏框（类图的名称/属性/方法）。关系线：实线+实心菱形=组合，实线+空心菱形=聚合，虚线箭头=依赖，实线三角=继承。

## 输出规则

1. 输出**单个 `.svg` 文件**——除 Google Fonts 引入外无外部依赖
2. `viewBox` 需包含所有内容并留 30px 边距；**不设固定的 `width`/`height`** 属性（让 SVG 自适应缩放）
3. 根 `<svg>` 元素需包含 `xmlns="http://www.w3.org/2000/svg"`
4. 所有 `<style>`、`<defs>`、标记和模式放在 SVG 顶部
5. 居中标签使用 `text-anchor="middle"`；确保文字不溢出框
6. **保存路径：** 若输入为文件，保存到 `{inputFileDir}/diagram/`。否则保存到 `{projectDir}/diagram/{topic-slug}/`。目录不存在时自动创建

## 脚本

确定此 SKILL.md 所在目录为 `{baseDir}`。脚本路径：`{baseDir}/scripts/main.ts`。

### SVG → @2x PNG

保存 SVG 后，可转换为其 @2x PNG：

```bash
${BUN_X} {baseDir}/scripts/main.ts <svg-path> [options]
```

选项：
- `-s, --scale <n>` — 缩放倍率（默认：2）
- `-o, --output <path>` — 自定义输出路径（默认：`<input>@2x.png`）
- `--json` — JSON 输出

## 处理流程

1. 从用户请求中识别图表类型
2. 若有对应参考文件则读取
3. 规划布局：列举所有组件，确定分组与流动方向，计算位置
4. 按上述图层顺序编写 SVG
5. 验证间距规则——无重叠、图例在边界外、viewBox 足够大
6. 保存 SVG 文件
