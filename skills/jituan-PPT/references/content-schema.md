# 内容配置 JSON Schema（jituan-PPT）

把源 PPT 的内容按下面的结构整理成 JSON 文件，`build.py` 会用它生成按集团模板排版的正式 PPT。

## 顶层结构

```json
{
  "cover": {
    "title": "主标题（必填）",
    "subtitle": "副标题（可选）",
    "author": "编制人姓名（可选）",
    "date": "时间（可选，如 2026年11月）"
  },
  "toc": {
    "toc_title": "目录（可自定义）",
    "items": [
      {"num": "一", "title": "第一章标题"},
      {"num": "二", "title": "第二章标题"},
      {"num": "三", "title": "第三章标题"},
      {"num": "四", "title": "第四章标题"},
      {"num": "五", "title": "第五章标题"},
      {"num": "六", "title": "第六章标题（条数可增减，1~10）"}
    ]
  },
  "sections": [
    {
      "title": "一、项目概况",
      "chapter": 1,
      "type": "bullets | paragraph | table | picture | table_picture | bullets_picture | split | gallery | compare | flow | pareto",
      "content": "...",
      "intro": "表格/要点上方的引言行（可选）",
      "note": "底部结论/注释条（可选，\\n 分段）",
      "image": "assets/p1_img1.png",
      "images": ["a.png", "b.png"],
      "caption": "图注文字",
      "col_widths": [2.0, 3.5, 6.67],
      "table": [["指标", "内容"]],
      "left": [...],
      "right": [...]
    }
  ],
  "toc_transition": true,
  "ending": {"text": "谢谢！"}
}
```

- `chapter`（可选，整数）：该页属于第几章（1 起）。同一章多页只需在**每页都写**或按顺序递增标注；构建时会**在每章前自动插入一页目录**，当前章标题整条标红。
- `toc_transition`（可选，默认 `true`）：设为 `false` 则只在封面后生成一张目录页，不做章节过渡。
- 若都不写 `chapter`：`sections` 页数等于目录条数时默认「一页一章」，否则整体算一章（只出 1 张目录并打印提示）。

## 各页面类型说明

### toc 目录（条数可增减，1~10；每章前各一页）
```json
{"toc": {"toc_title": "目录",
  "items": [{"num": "一", "title": "工程概况"}, {"num": "二", "title": "节点优化"}]}}
```
- 两种写法都支持：`{"toc_title": ..., "items": [...]}` 或直接 `"toc": [{"title": ...}]`。
- 生成目录页时**整页克隆模板第2页原型**（保留阴影编号方块、蓝绿曲线、装饰图），只替换文字；勿自行重绘。
- 每章正文前各插一页目录，**当前章标题整条标红 #FF0000**，其余条目文字统一白色 #FFFFFF（蓝底标题条）；`current` 由 `chapter` 归属自动推算。
- ≤5 条沿用模板实测坐标；6~10 条自动纵轴等距重排、编号沿模板弧线插值；>10 条会截断并告警。
- `num` 可省略，会自动填「一、二、三……」；目录条目标题**不要带「一、」等数字前缀**（数字由编号方块承担）。

### bullets（默认）全宽要点列表
```json
{"title": "一、建设目标", "type": "bullets",
 "content": ["要点1", "要点2", {"text": "子要点", "level": 1}]}
```

### paragraph 正式段落
```json
{"title": "二、项目背景", "type": "paragraph",
 "content": [{"para": "第一段……"}, {"para": "第二段……"}]}
```

### table 全宽表格
```json
{"title": "三、建设内容", "type": "table",
 "content": [
   ["序号", "建设内容", "规模"],
   ["1", "机房建设", "5000㎡"],
   ["2", "动力中心", "3000㎡"]
 ]}
```
第一行自动作为表头（蓝底白字）。

### table_picture 左表右图（模板第3页风格，最正式）
```json
{"title": "四、工程概况", "type": "table_picture",
 "table": [
   ["工程名称", "中国移动网络通信基础设施项目"],
   ["工程地址", "××省××市"],
   ["建设规模", "××"]
 ],
 "image": "extracted/p4_img1.png",
 "caption": "项目效果图"}
```
- 表格宽 7.0"，右图 3.3"，第一列自动加宽到 2.0" 放指标名。

### bullets_picture 左要点右图
```json
{"title": "五、保障措施", "type": "bullets_picture",
 "content": ["措施1", "措施2", "措施3"],
 "image": "extracted/p5_img1.png"}
```

### picture 全宽大图
```json
{"title": "六、总体布置", "type": "picture",
 "image": "extracted/p6_img1.png",
 "caption": "总体布置图"}
```

### split 左右分栏
```json
{"title": "七、组织分工", "type": "split",
 "left": ["甲方职责1", "甲方职责2"],
 "right": ["施工方职责1", "施工方职责2"],
 "note": "结论：左右两侧同步验收。"
}
```

### gallery 多图并排（1.3 节点深化风格）
```json
{"title": "八、幕墙节点深化", "type": "gallery",
 "intro": "深化说明一句话（可选）",
 "images": [
   {"image": "a.png", "caption": "深化后图纸节点\n骨架·埋件·板块排布"},
   {"image": "b.png", "caption": "龙骨安装节点\n转接件三维调节"}
 ],
 "note": "深化设计原则：……"}
```
- 图片等宽均分版心、顶部对齐；图注按最高图底统一排布（保证齐平、不压图），`caption` 内 `\n` 可换行。

### compare 前后对比（原设计 / 优化后）
```json
{"title": "九、阳角构造对比", "type": "compare",
 "left":  {"label": "原设计：大阳角 · 三条线脚",
           "images": ["old1.png", "old2.png"],
           "items": ["施工麻烦、线脚不顺直", "立面效果不佳"]},
 "right": {"label": "优化后：大阳角 · 一条线脚（150mm）",
           "images": ["new1.png", "new2.png"],
           "items": ["施工方便", "成型效果好"]},
 "center_image": "site.png",
 "center_caption": "现场成型效果",
 "note": "原设计：……\n优化后：……"}
```
- `left`/`right` 是对象：`label`（蓝底白字标签条）、`subtitle`（可选副行）、`images` 或 `image`、`items`（优缺点条目）。
- 中间图 `center_image` 可选；有 `note` 时中间图自动压到 2.95″，给结论条留位。

### flow 工序流程链（v1.4: Visio 矢量渲染）
```json
{"title": "十、施工工艺流程", "type": "flow",
 "content": ["测量放线", "埋件安装", "转接件安装", "龙骨安装", "面板安装", "打胶"],
 "note": "样板引路：大面积施工前先做样板。"}
```
- **默认经 Visio 转为矢量图（EMF）插入 PPT**，样式与 `C:\Users\liuwust\Desktop\PPT\素材\设计后期管理流程.vsdx` 一致
  （步骤节点淡蓝填充深蓝边框、微软雅黑加粗；连接线黑色实心箭头）。依赖：Windows + Visio + pywin32。
- **分阶段结构**（推荐，与基准文件同款：阶段标签沿左列竖排、彩色虚线框）：
```json
{"title": "十、设计后期管理流程", "type": "flow",
 "stages": [
   {"label": "施工图交付", "steps": ["确定参加交底人员名单", "编写设计交底方案", "作好交底会议记录", "组织签署交底记录"]},
   {"label": "施工验收", "steps": ["确定参加予验收人员名单", "带有文件去现场", "记录问题并请顾客签认"]},
   {"label": "归档", "steps": ["按《归档清单》要求整理归档"]}
 ]}
```
- 阶段颜色按紫→橙→红→蓝→绿循环；`stages` 省略时全部步骤视为单链，横向排满自动换行。
- 强制用原生形状版式（不用 Visio）时，在该页加 `"flow_engine": "native"`。
- 构建时生成的 `.vsdx` 路径会打印在日志中（`[flow] Visio 矢量图已生成`），可在 Visio 中再编辑。

### pareto 排列图
```json
{"title": "十一、质量缺陷排列图", "type": "pareto",
 "categories": ["竖缝直线度", "垂直度偏差", "进出位差", "拼缝宽度差", "其它"],
 "values": [25, 17, 10, 5, 3],
 "cumulative": [41.7, 70.0, 86.7, 95.0, 100.0],
 "note": "结论：前三项累计 86.7%，为关键问题。"}
```
- 柱状（频数，左轴）+ 累计频率折线（右轴 0~100%），全部为原生形状，可在 PPT 内直接改数据。

## 通用字段

| 字段 | 作用 |
|---|---|
| `intro` | 表格/要点上方的引言行（16pt 灰字），表格页会自动预留高度 |
| `note` | 底部注释/结论条（浅蓝底 16pt，`\n` 分段，「标签：」自动加粗）；底边固定在 6.40″，不压页脚 |
| `col_widths` | 表格列宽（英寸数组，长度须等于列数，总和≈12.17 才生效） |
| `images` | 多图：`bullets_picture` 按长宽比自动并排/上下；`gallery` 传 `[{"image","caption"}]`；`compare` 放在 `left/right.images` |
| `caption` | 单图图注（`picture` / `table_picture` / `bullets_picture`）；`gallery` 每图各自带 `caption` |

## 工具调用约定

- 没有 `content` 的字段省略即可，不要在 JSON 里留空数组也写 `"content": []`（除非内容确实为空）。
- 图片路径写相对 `build.py` 工作目录或绝对路径均可；推荐放到技能 assets 或任务工作区子目录。
- 目录条数 1~10 自动适配：≤5 条用模板实测坐标，6~10 条等距重排 + 弧线插值，>10 条才需要合并章节。

## 生成命令

```powershell
python build.py content.json --out 成品.pptx
# 使用默认模板 assets/集团模板.pptx
```

## 验收标准（Agent 交付前必须自查）

1. 所有正文页标题完整（不超过 30 字一行的显示宽度）
2. 表格第一行是表头且为蓝底白字
3. 图片等比且不越出版心（右边距 ≥0.3"）
4. 页面无重叠元素（表格与图、文本框互不压盖）
5. 字体全部微软雅黑（含流程图节点）
6. 章节号连续：一、二、三……与目录一致
7. **字号规范（v1.4）**：正文全部 16 号；表格文字全部 14 号；流程图为 Visio 矢量图（EMF）
8. **目录配色（v1.4.2）**：当前章标题红色，其余条目白色（蓝底标题条）
