# Styles · 12 套原创视觉风格

由 `scripts/styles.py` 实施。每套风格都是**原创色板 + 字体栈 + 节点圆角 / 阴影 / 边框**的组合，**不要从外部网页扒样式表**。

---

## 总览

| id | 中文名 | 适用场景 | 主色 |
|---|---|---|---|
| `flat-icon`  | 扁平图标 | **默认**。科技、架构、PPT 截图 | 深蓝 + 灰阶 |
| `soft-pastel`| 柔粉淡彩 | 适合产品/教育/分享 | 粉橙 + 雾蓝 |
| `tech-blue`  | 科技蓝 | 后端/数据/工程 | 纯蓝 + 青 |
| `ink-landscape`| 水墨山水 | 中文报告、内容创作 | 浅墨 + 朱砂 |
| `paper-zen`  | 留白纸系 | 思想导图 / 流程 / 主题文章 | 米白 + 灰 |
| `mono-minimal`| 单色极简 | 严肃、合同、技术文档 | 全灰 |
| `neon-night`| 霓虹夜色 | 活动运营 / 主题演讲 | 紫红 + 青 |
| `grass-fresh`| 草绿清新 | 自然 / 户外 / 健康 | 鲜绿 + 草黄 |
| `olive-journal`| 橄榄手记 | 与公众号同源配色 | 橄榄绿 + 暖灰 |
| `cobalt-grid`| 钴蓝网格 | 工程/开发者向 | 钴蓝 + 钢灰 |
| `clay-amber`| 琥珀陶土 | 复古、人文、博物馆 | 焦糖 + 沙黄 |
| `arctic-frost`| 极地霜蓝 | 安全 / 医疗 / 金融 | 浅蓝 + 白 |

---

## 默认 vs 选择策略

- **默认**：用户没指定时一律 `flat-icon`。
- **关注度高的初学者场景**：用 `paper-zen`（简洁） / `ink-landscape`（中国文化感）。
- **科技自媒体**：用 `tech-blue` / `cobalt-grid` / `flat-icon`。
- **公众号长文插图**：用 `olive-journal`（与公众号写作助手色系一致）。
- **主题演讲 / 视觉冲击**：用 `neon-night`。
- **不要默认出多版本**——出用户指定的那一版即可，避免生成多余文件。

---

## 风格字段速查

每套风格由 `scripts/styles.py` 中的 dict 定义，影响整个图的渲染。核心字段：

```python
{
  "id": "flat-icon",
  "name": "扁平图标",
  "canvas_bg": "#FFFFFF",
  "node": {
    "fill": "#FFFFFF",
    "stroke": "#1F2A44",
    "title_size": 13,
    "desc_size": 11,
    "radius": 8,
    "shadow": False,
  },
  "edge": {
    "label_size": 11,
    "stroke": "#3B4660",
    "width": 1.4,
  },
  "lane_band": {
    "fill": "#F2F5FA",
    "text": "#5C6680",
  },
  "accent": "#2D6CDF",
  "font_stack": "'Inter','PingFang SC','Microsoft YaHei',sans-serif"
}
```

> 风格的所有具体值由编译器读取 `scripts/styles.py` 单一来源；本文**仅说明意图与用途**，不复制色值以免漂移。

---

## 修改风格的红线

- ✅ 加新风格：在 `scripts/styles.py` 注册一个完整 dict，并在 `STYLES` 表中追加 id。
- ❌ 不要改产物 HTML 里的 inline color——那是渲染引擎自动生成的。
- ❌ 不要"借鉴"外部品牌色板——坚持使用原创 12 套色。
- ❌ 不要只改某一个组件的颜色（quote 蓝 / 引用块橙）——联动会失效。

---

## 风格选型建议（按用户身份）

| 身份 / 场景 | 推荐 |
|---|---|
| 后端工程师 → 微服务架构 | `flat-icon` / `tech-blue` / `cobalt-grid` |
| 算法工程师 → 数据流 / 模型 pipeline | `flat-icon` / `tech-blue` |
| AI Agent 内容创作 | `flat-icon` / `neon-night` |
| 产品经理 → 业务流程 | `soft-pastel` / `paper-zen` |
| 公众号长文 → 插图 | `olive-journal` / `ink-landscape` |
| 教育培训 → 概念图 | `paper-zen` / `soft-pastel` |
| 主题演讲 / 直播 | `neon-night` / `cobalt-grid` |
| 法律 / 财务 / 合规文档 | `mono-minimal` |
| 医疗 / 生命科学 | `arctic-frost` / `soft-pastel` |
| ESG / 农业 / 自然 | `grass-fresh` |

> **不要试图"无风格"**：永远选一套，因为渲染引擎需要色板来生成节点 fill、连线 stroke、文字色三组配合。
