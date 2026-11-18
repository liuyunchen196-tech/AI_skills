# 多板块架构（项目群 + 通用中心 + 子项目）

> 适用：一个项目要同时交付「精益建造 / 进度 / 质量 / 安全」等多个板块，素材同源、成果各异，
> 且要分批交付、后台批量出成果。**先定架构再干活**——架构定错，后面每个板块都要返工。

---

## 一、三层，各管一件事

```
分部分项（主门户 :5080）
  管：标准分部分项树、范围下发、子项目进程与端口、门户内嵌预览
  不管：任何业务数据
        │  ①/subapi/scope（范围）  ②/api/hub/launch（拉起）
        ▼
通用中心 · 数据工厂 :5090
  管：素材→结构化库（数据集/关键词条/记录/图片/分部分项）、列映射、同步、发布 exe·html
  不管：某板块的成果版式
        │  ③写快照 data/factory/*.json + ④POST /api/factory_sync
        ▼
子项目（精益建造 :5099 / 进度 / 质量 / 安全 …，各自独立目录、独立 data、可单独启动）
  管：本板块的库、版式、PDF/PPT/Excel 成果
  不管：素材解析、跨板块复用
```

**硬约束**

- 主门户不读子项目库，子项目不依赖主门户；只走 HTTP 三接口。
- 通用中心与子项目之间只走两条通道：**文件快照（必做）+ HTTP 推送（尽力）**。
  子项目没启动时快照照样更新，下次启动即生效——这是「通用项目后台跑、子项目随时开」的基础。
- 子项目不硬编码列名：列名由 `factory_target.json` 的槽位声明，改叫法不改代码。

---

## 二、目录与端口约定

```
D:\...\实施\
├── 分部分项\                    主门户
│   ├── main.py / hub_lib.py
│   ├── config\subprojects.json  唯一注册表（含 role=factory 的通用中心）
│   ├── data\divisions.json      标准树（各处保持同一份）
│   └── scaffold\                新建子项目骨架（已内置通用库接入）
├── 分部分项\通用中心\            通用中心（:5090，role=factory）
│   ├── app.py / run.py / 启动.bat
│   ├── factory\{db,ingest,divmap,mapping,exporter,sync,pack}.py
│   ├── data\factory.db + 图片库\ + divisions.json
│   └── static\ (总览/素材/数据集/列映射/同步发布)
└── 精益建造\0分部分项划分\       子项目①（:5099）
    ├── app.py(含 /api/factory_sync) / factory_target.json
    ├── data\factory\*.json       通用中心写的快照（原始结构，发布用）
    ├── data\factory_items\*.json 本项目转换后的结构（避免互相覆盖）
    ├── data\图片库\              同步来的图片（文件名全局唯一）
    └── 成果发布\                 exe + 网站发布/
```

| 角色 | 端口 | 备注 |
|---|---|---|
| 主门户 | 5080 | `MAIN_PORT` 可改 |
| 通用中心 | 5090 | 固定，`role=factory`，不参与「按范围出成果」的勾选 |
| 子项目 | 5099 起 / 5101~5199 池 | `SUB_PORT` 由门户下发 |

---

## 三、四个协议

| 接口 | 谁实现 | 用途 |
|---|---|---|
| `GET /api/health` | 全部 | `{"ok":true}` |
| `GET /api/hub_info` | 全部 | 身份、条数、能力、`factory.count` |
| `GET/POST/DELETE /api/scope` | 全部 | 主门户下发分部分项范围（通用中心只存档不筛） |
| `POST /api/factory_sync` | 子项目 | 通用中心推送快照（原样存 `data/factory/<key>.json`） |

`/api/factory_sync` 报文（schema 1，字段名不要改）：

```json
{
  "schema": 1, "source": "通用中心",
  "dataset": {"key":"ds2c5e5","name":"优化工艺","version":3,"records":63,"images":127},
  "columns": [{"code":"f01","label":"优化措施名称","slot":"title"}],
  "records": [{
    "title": "铝模快拆体系施工工艺",
    "row":   {"优化措施名称":"…","优化内容":"…"},
    "slots": {"title":"…","content":"…","effect":"…","div1":"主体结构","div2":"混凝土结构",
               "div3":"模板","pos":"标准层","image":[{"file":"ds2c5e5_ab12cd34ef.jpg"}]},
    "div":   {"div1":"主体结构","div2":"混凝土结构","div3":"模板","pos":"标准层"}
  }]
}
```

`slots` 是语义层（子项目只认它），`row` 是展示层（按改过的列名），`div` 冗余给范围筛选用。
图片已拷进子项目 `data/图片库/`，`slots.image[].file` 直接当文件名用。

---

## 四、新增一个板块（三步，10 分钟）

1. **建目录**：门户「+ 添加 → 新建」，用 `scaffold` 生成（已含三接口、范围过滤、`/api/factory_sync`、Excel 导出）。
2. **声明槽位**：改 `factory_target.json` 的 `slots`（如质量板块：`title=质量问题名称`、`content=问题描述`、`effect=防治措施`）。
3. **注册**：门户会自动写入 `config/subprojects.json`；打开通用中心「同步与发布」点刷新即可看到它。

之后：通用中心选数据集 → 选该板块 → 改列名 → 同步 → 板块页面立刻有数据。

---

## 五、分批交付的正确姿势

| 阶段 | 通用中心 | 子项目 |
|---|---|---|
| 先交付精益建造 | 导入 2~3 份手册，映射到 `jlkj`，同步 | 出 PDF/PPT/Excel，打包 exe/网站 |
| 再交付质量 | 同一批素材按质量词条重新映射（不用重新解析） | 骨架 + 质量版式，取同一份库 |
| 后台批处理 | 批量导入（拖多个文件）、批量同步（同步全部）、批量发布 | 不参与，只被动收快照 |

**一个素材只解析一次**，多板块靠「列映射」复用——这是通用中心存在的唯一理由。
所以映射要按板块分别保存（`mappings` 表按 `dataset_id × target_key` 唯一），不要把某板块的列名改成通用名。

---

## 六、启动顺序与自检

```bash
# 1 主门户（可选，单独用通用中心也能跑）
python D:\萧山项目\实施\分部分项\main.py          # http://127.0.0.1:5080/
# 2 通用中心
python D:\萧山项目\实施\分部分项\通用中心\app.py   # http://127.0.0.1:5090/
# 3 子项目（可单独，或由门户拉起）
python D:\萧山项目\实施\精益建造\0分部分项划分\app.py
```

自检三连（缺一个就是没接通）：

```bash
curl -s 127.0.0.1:5090/api/hub_info    # 通用中心活着，count>0
curl -s 127.0.0.1:5099/api/hub_info    # 子项目活着，factory.count = 收到的条数
ls  <子项目>/data/factory/             # 快照在，说明文件通道通
```

常见不通报错：

| 现象 | 原因 |
|---|---|
| 通用中心里看不到子项目 | 门户注册表没登记，或目录下没有 `factory_target.json` |
| 同步显示「快照」不显示「已推」 | 子项目没启动（正常，快照已写） |
| 子项目 `factory.count` 一直是 0 | `data/factory/` 被写成别的结构（见下条） |
| 第二次同步把第一次的数据集冲掉 | 子项目把「转换结果」写回了 `data/factory/`；应写 `data/factory_items/` |
