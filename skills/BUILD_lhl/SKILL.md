---
name: BUILD_lhl
description: 精益建造类板块的结构化数据与图片库建设流水线。当用户要把一份或多份手册/图册/表格类 PDF（精益建造、工艺标准、优化建议、部品部件、高效机具等）提炼成"措施库 + 图片库 + 可出 PDF/PPT 的项目"，或要给已有项目追加素材、补充栏目、查重合并、按分部分项归集、打包发布（EXE / 静态网站）时使用；也给多板块项目群（精益建造/进度/质量/安全）搭「主门户 + 通用数据工厂 + 子项目」架构。触发词：精益建造、措施库、图片库、提炼手册、扩充数据库、加栏目、分部分项归集、查重合并、同部位同做法、效果示意图、生成成果 PDF/PPT、打包 exe、发布网址、花生壳、通用中心、数据工厂、多板块、子项目、列映射、Excel 批量录入、图片位置列、按原表直采、横版双栏、合并同类库、一库一子项目、生成子项目。
version: 1.5.0
author: 萧山项目
---

# BUILD_lhl · 精益建造板块数据建设

把一本（或一套）图文手册，变成**可查询、可筛选、可出成果、可分发**的结构化资产：
措施库（主数据库）+ 图片库（图片信息数据库）+ 项目端（红/蓝模板）+ 成果（PDF / PPT / 统计表）+ 发布包（EXE / 静态网站）。

本技能把「精益建造」项目从零到交付的全过程固化下来，并可直接复用到其他板块
（装配式、绿色施工、智慧工地、标准部品、高效机具……）——**换素材、换目录，流程不变**。

---

## 一、什么时候用它

| 场景 | 典型说法 |
|---|---|
| 新板块从零建设 | 「把这份手册做成措施库和图片库」「按精益建造那套流程做一遍」 |
| 已有板块扩充 | 「这个素材也按要求扩展，再整合」「新增的并进现有库」 |
| 结构调整 | 「给主数据库加一列」「按分部分项归类」「按楼层筛」 |
| 质量治理 | 「全面查重」「很多优化是重复的，只是叫法不同」「图片重命名」「删掉某类内容」 |
| 成果与分发 | 「生成 PDF/PPT/Excel」「做成 exe 给项目上用」「发布成网址」 |

不适用：纯文字报告的写作、单张图片处理、与结构化库无关的排版美化。

---

## 二、六个阶段的硬性要求

流程固定为 **体检 → 提取 → 归一 → 查重 → 落库 → 发布**，每个阶段都有验收条件，不达标不进下一阶段。

### 阶段 1 · 素材体检与路由（不可跳过）

先用 `scripts/probe.py` 体检，再决定提取路径。**不要凭文件名猜版式**。

| 体检结论 | 走哪条路 | 脚本 |
|---|---|---|
| 有文本层 + 规整框线表格 | 矢量框线法 | `scripts/extract_tables.py` |
| 有文本层 + 卡片式（标题条 + 小标签 + 图片区） | 卡片切片法 | `scripts/extract_cards.py` |
| 无文本层 / 文本层乱码（字体缺 ToUnicode） | 渲染 + OCR | `scripts/ocr_scan.py` |
| 横向页 `/Rotate` 为 90/270 | 先做坐标变换再取图 | 内置在提取脚本 |

**验收**：能说清「这份素材是几页、几栏、一张卡几个字段、图片在哪一区」。

### 阶段 2 · 提取（字段映射先定死）

提取前必须先写死字段映射表，**同一个词在不同手册里含义可能相反**。本项目已确认的映射：

| 库字段 | 来源（房屋建筑分册/三局手册） | 来源（优化工艺） |
|---|---|---|
| 优化措施名称 | 表格标题 / 卡片标题 | 卡片标题 |
| 优化内容 | 案例简述 | **工艺要点** |
| 优化效果 | 实施目的 | **实施效果** |

> ⚠️ 「优化工艺」类素材的「实施效果 / 工艺要点」与常规手册**顺序相反**，照抄会全库错位。
> 每接一份新素材，先把它的版式与字段归属写进 `references/schema.md` 的对照表，再动手。

**验收**：抽取条数 = 素材中实际条目数；每条至少能取到 标题 + 两段文字 + ≥1 张图。

### 阶段 3 · 归一（三个维度必须齐全）

| 维度 | 规则 |
|---|---|
| 章节 / 优化类型 | 章节是 8 大类之一；优化类型可带括号子类。**一份素材全属一类时，类型就写这一类**，子类记到「手册分类」 |
| 分部分项 | 必须命中 `assets/divisions.json`（GB 50300-2013）。措施类无对应分部的，归入虚拟分部「措施项目」 |
| 信息词条 | 每条必填，分号分隔的关键词，用于检索匹配（见 `references/schema.md`） |

**验收**：`validate.py` 报「不在标准树 = 0」「信息词条为空 = 0」。

### 阶段 4 · 查重与合并（三种比对，不要混用）

查重**不是一次跑完的**，按「新素材 vs 库」和「库内自查」分两条线，两条线都要先出清单再动手：

| 场景 | 脚本 | 判据 |
|---|---|---|
| 新素材入库前 | `scripts/dedupe.py` | 新记录 vs 已有库：名称 + 公共子串，出候选后人工确认 |
| 库内重复表述 | `scripts/dedupe_content.py` | 同分部分项 → 同部位 → 同做法，三步筛（下详） |
| 图片内容重复 | dHash 感知哈希 | 见 `references/pitfalls.md` 第 22 条，MD5 查不出重编码图 |

#### 4.1 库内「同部位同做法」识别（dedupe_content.py）

判定的顺序就是业务顺序，**先归位再比做法**：

1. **按分部分项排序**：`分部 → 子分部 → 分项`，只在同一分部分项内两两比较（跨分项的"相似"多是不同对象的同名做法）。
2. **看适用部位**：部位有交集，或同属一个部位域（楼层 / 地下 / 外围 / 全场）才进入比较；部位互斥的两条直接放过。
3. **比做法，不比名字**：名称去掉「施工工艺/技术/做法/优化/应用」等后缀后只占 45% 权重，
   信息词条 Jaccard 占 25%，**优化内容包含度占 30%**（短文本被长文本覆盖的比例）。
   同义改写往往是「一句概括 vs 详细描述」，只比字面会漏。

```bash
# 出候选：终端按组打印，同时落 CSV 供逐条核对
python scripts/dedupe_content.py --lib <lib.json> --out output/去重候选.csv
```

**阈值只用来筛候选，判定必须靠人眼**。本项目 376 条里阈值 0.62 只命中 1 组（而且是个假阳性：
「临边作业安全带挂点（一）（二）」做法确实不同）——真重复的相似度大多落在 0.35~0.55，
因为一条写得详细、一条只写一句。**所以：先按分部分项通读一遍清单，比调阈值有效得多。**

#### 4.2 人工确认 → decisions.json

逐组确认后写成（见 `assets/decisions.example.json`）：

```json
[{"keep": 188, "drop": [13], "why": "承插式烟道：同做法，一条更完整"},
 {"keep": 1,   "drop": [348, 214], "why": "同做法三种叫法，留内容最全的"}]
```

合并动作（`--decisions` 执行）：保留项吸收 drop 项的 **图片（同名去重）、适用部位、信息词条**；
原名称记入 `别名`、原溯源键记入 `来源合并`；id 重排 1..N；首次执行自动备份 `<lib>.prededupe.json`。

```bash
python scripts/dedupe_content.py --lib <lib.json> --decisions merge_decisions.json
python scripts/review_sheet.py --lib <lib.json> \
    --prededupe <lib.prededupe.json> --decisions merge_decisions.json \
    --out "../精益建造措施_按分部分项排序.xlsx"      # 清单 + 合并明细，交人抽查
```

> ⚠️ **哪些不能合并**（本项目实战）：同部位但**构件不同**的不能并——构造柱 / 门过梁 / 门垛 /
> 上反坎「同主体一次浇筑」是四个构件；预制 U 型砌块分别用作「线槽砖」和「过梁模板」，用途不同；
> 临边安全带挂点（一）（二）是两种做法。**名字像 ≠ 做法同，构件不同一律不并。**

**验收**：合并/新增有台账（`decisions.json` + 核对表 Sheet2）；措施名全库唯一；图片 0 缺失 0 孤儿。

### 阶段 5 · 落库（必须幂等）

一次 `ingest.py` 调用 = 一次原子写入。**脚本必须防重跑**：写入前检查「来源表」是否已存在，存在则拒绝或走 `--force`。

> ⚠️ 本项目踩过的坑：同一份脚本连跑两次 → 记录数 376→472、图片库多出 158 张、
> 图片名被加 `_2` 后缀。修复方式是「备份 → 按备份引用集清理孤立图片 → 还原 → 重跑一次」。
> **任何写库脚本执行前先 `cp lean_measures.json lean_measures.bak.json`。**

**验收**：`validate.py` 全绿（见第六节）。

> **人工补录通道**：工具端已内置 `lean_import.py`，在「选择卡片」页提供
> 「模板Excel / 数据库写入」两个按钮——下载模板填 4 个必填列（优化措施名称、优化内容、优化效果、
> 实体案例图片地址）后选文件即可入库，图片自动复制并按「措施名_序号」重命名。
> 单条/少量补充走这条路，成批素材仍走本技能的「体检 → 提取 → 归一 → 查重 → 落库」主流程。

### 阶段 6 · 发布（EXE + 静态网站）

库建好后要能交付给不用装 Python 的人，两条通道并行做：

| 通道 | 脚本 | 产物 |
|---|---|---|
| 单文件 EXE（项目上用，可生成成果、可导库） | `scripts/build_exe.py` | `成果发布/精益建造一体化工具.exe` |
| 静态网站（手机/领导看，只读浏览） | `scripts/make_web_release.py` | `成果发布/网站发布/` + zip |

```bash
python scripts/build_exe.py --root "<工具端>" --out "<板块根>/成果发布" --name 精益建造一体化工具
python scripts/make_web_release.py --data "<工具端>/data" --out "<板块根>/成果发布"
```

**发布前必查**（脚本已内置，但要读懂输出）：

1. 文件数 ≤ 2000、单包 ≤ 100MB（花生壳限制）；脚本按「1900 文件 / 96MB」留余量，超限自动压图
   （最长边 1280，质量 80→70→60→50 逐级降）。本项目 376 条 / 580 图 → **583 文件 / 26.6MB，无需压缩**。
2. EXE 必须**复制到空目录独立测试**：首启会在同级解出 data（29MB），确认 页面 200、`/api/lean_meta`
   条数正确、PDF / PPT / Excel 三连发都成功。
3. 静态站的数据写在 `data.js`（`window.LEAN_DATA=`）而不是 fetch，**双击 index.html 也能看**。
4. 覆盖旧 EXE 前先关掉正在运行的程序，否则文件被占用写不进去（打包会失败）。

**验收**：独立目录跑通三种成果；网站包 `index.html` 能离线打开、图片全部加载、手机宽度无横向滚动。

---

## 三、目录与文件约定

```
<板块根目录>\
├── 素材\                      原始 PDF（只读，永不修改）
├── 0分部分项划分\              工具端（Flask + launcher + data）
│   └── data\
│       ├── lean_measures.json  主数据（唯一真相源）
│       ├── lean_measures.prededupe.json  合并前备份（去重可回滚）
│       ├── 图片库\             <措施名>_<序号>.jpg
│       └── divisions.json      分部分项标准树
├── 红色项目\  蓝色项目\         两个成品模板（主数据库.db / 图片信息数据库.db / 图片库 / 项目信息.json / 生成成果.py / 输出）
├── 成果发布\                   交付物
│   ├── 精益建造一体化工具.exe   单文件程序（内置 static + data）
│   ├── 网站发布\               静态站（index.html / data.js / img / 发布说明.txt）
│   ├── 精益建造措施库_网站发布.zip
│   └── 使用说明.txt
├── 精益建造措施统计表.xlsx      统计成果
└── 精益建造措施_按分部分项排序.xlsx  查重核对表（清单 + 合并明细）
```

**图片命名铁律**：`<措施名>_<序号>.jpg`，序号从 1 起连续；措施名去掉 `\/:*?"<>|`；
与图片信息数据库的「图片位置」一一对应；不得出现未引用图片，也不得出现引用缺失。

**图片去重铁律**：**先算保留清单 → 把要留的挪到临时名 → 删其余 → 改名回写引用**。
顺序反了会把「唯一保留的那张」自己删掉（本项目踩过，见 pitfalls 第 23 条）。

---

## 四、脚本清单

| 脚本 | 用途 | 关键参数 |
|---|---|---|
| `probe.py` | 素材体检：页数/文本层/框线/图片分布/旋转页 | `<pdf>` |
| `extract_tables.py` | 矢量框线法提表格（列由竖线定，行由横线聚类） | `--pdf --cols --out` |
| `extract_cards.py` | 卡片切片：左栏/右栏、标题、标签分段、案例图 | `--pdf --split-x --out` |
| `ocr_scan.py` | 扫描件：渲染 → OCR → 重组 | `--pdf --dpi --out` |
| `dedupe.py` | 新素材 vs 库的查重候选（不改库） | `--new recs.json --lib lean_measures.json` |
| **`dedupe_content.py`** | **库内同部位同做法识别与合并** | `--lib --out --decisions --threshold --apply` |
| **`review_sheet.py`** | **排序核对表 xlsx（清单 + 合并明细）** | `--lib --prededupe --decisions --out` |
| `ingest.py` | 落库：归一 + 合并 + 图片重命名 + 幂等 | `--recs --lib --img --merge-map` |
| `validate.py` | 七项校验 | `--lib --img` |
| `add_columns.py` | 给现有项目加栏目（扩列 + 回填 + 同步两项目） | `--project --col 名称:TEXT --fill` |
| **`build_exe.py`** | **打单文件 EXE（内置 static + data）** | `--root --out --name --hidden` |
| **`make_web_release.py`** | **生成静态网站包 + zip（含体积/文件数校验与压图）** | `--data --out --name` |

统一约定：`--dry-run` 只打印不落盘；`--force` 跳过幂等保护；所有输出 UTF-8。

---

## 五、给现有项目加栏目

「加栏目」= 在主数据库、图片信息数据库、JSON、项目端四个地方同步加字段，且不破坏既有数据。

```bash
python scripts/add_columns.py --project "D:\...\红色项目" --col "信息词条:TEXT" --col "来源表:TEXT" --fill
```

执行顺序固定：**备份 → ALTER TABLE（ADD COLUMN，可空）→ 回填 → 双项目一致性比对 → 重出成果**。
绝不 DROP、绝不重建表、绝不改既有列名（列名即接口，前端/生成脚本按名取数）。

> 列名改过一次：`措施 → 优化措施名称`、`实施效果 → 优化内容`、`效果示意 → 实体案例`。
> 改列名用 `ALTER TABLE ... RENAME COLUMN`，同时改 JSON 键、前端 `key`、`sync_projects.py`
> 三处，漏一处就报「列名不一致」。**列名即接口，改一次要全链路跟一遍。**

---

## 六、验收清单（九项，全绿才算完成）

| # | 检查 | 期望 |
|---|---|---|
| 1 | 记录总数 | ≥ 上版条数；新增/合并有台账（`decisions.json`、核对表 Sheet2） |
| 2 | 图片引用 | 引用数 = 图片库文件数；缺失 0；未引用 0 |
| 3 | 无图记录 | 0 |
| 4 | 措施重名 | 0（被合并的原名进 `别名`，仍可检索） |
| 5 | 空字段 | 优化内容 / 优化效果 / 信息词条 均无空 |
| 6 | 分部分项 | 全部命中标准树或「措施项目」虚拟分部 |
| 7 | 双项目一致 | 红/蓝两库条数、图片数完全一致 |
| 8 | 连续导出 | PDF → PPT → Excel 可依次点击，无需重启；回退改选再回来仍可用 |
| 9 | 发布包 | 网站 ≤2000 文件 / ≤100MB；EXE 在空目录独立跑通三种成果 |

`python scripts/validate.py --lib ... --img ...` 一条命令输出前七项。

---

## 七、输出成果

| 成果 | 说明 |
|---|---|
| 精益建造措施统计表.xlsx | 按章节 / 优化类型 / 分部工程三张表 + 条形图 |
| 成果 PDF | 一条措施一页（封面 + 目录 + 正文 + 图片区），卡片三段固定高度、线条跨卡对齐 |
| 成果 PPT | 一个点子一页，每类别一章（集团模板，构建器随包内置） |
| 精益建造措施_按分部分项排序.xlsx | 查重核对表：清单 + 合并明细 |
| EXE / 网站包 | 见阶段 6 |

体量参考（376 条 / 580 图）：PDF 212 页 / 34.3MB（全量约 16 秒）、PPT 426 页（全量约 10 秒）；
单条措施生成 1 秒内。

---

## 八、禁止事项

1. 不改 `素材\` 里的原始 PDF。
2. 不在没有备份的情况下跑写库脚本。
3. 不用字面相似度直接合并（必须人工确认清单；`--apply` 只用于已逐组确认过的情况）。
4. 不把不同手册的「实施效果 / 优化效果」按位置机械对应（先核对版式）。
5. 不产生未引用图片，不删除仍被引用的图片。
6. 不重建表、不改列名；加栏目只做 ADD COLUMN。
7. **不把生成结果做成全屏遮罩弹窗**——会挡住格式卡片，用户点完 PDF 就点不了 PPT（本项目返工过）。
8. **合并前不删图**：先定保留清单，再删冗余（顺序错了会删掉唯一的那张）。

详细字段字典见 `references/schema.md`，版式提取要点见 `references/extract-patterns.md`，
分部分项口径见 `references/divisions.md`，成果版式参数见 `references/output-layout.md`，
全部踩坑记录见 `references/pitfalls.md`。

---

## 九、快速上手（照抄即可）

```bash
PY="C:/Users/<user>/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
S="D:/AI技能库/skills/BUILD_lhl/scripts"
WS="D:/项目/精益建造"          # 板块根目录
LIB="$WS/0分部分项划分/data/lean_measures.json"
IMG="$WS/0分部分项划分/data/图片库"

# 0 先备份
cp "$LIB" "$LIB.bak.$(date +%Y%m%d%H%M)"

# 1 体检，确定版式与提取路径
$PY $S/probe.py "$WS/素材/新素材.pdf"

# 2 提取（按版式选一条）
$PY $S/extract_cards.py --pdf "$WS/素材/新素材.pdf" --split-x 480 \
    --label-map "实施效果=优化效果;工艺要点=优化内容;实体案例=图片" \
    --out "$WS/_tmp/recs.json" --dpi 200
# 或
$PY $S/extract_tables.py --pdf "$WS/素材/新素材.pdf" --probe-cols 19
$PY $S/extract_tables.py --pdf "$WS/素材/新素材.pdf" --columns 92,149,270,503 \
    --column-map "1=优化措施名称;2=优化内容" --pages 18-23 --out "$WS/_tmp/recs.json"
# 或（扫描件/乱码）
$PY $S/ocr_scan.py --pdf "$WS/素材/新素材.pdf" --pages 1-20 --out "$WS/_tmp/ocr.json"

# 3 新素材查重（只出清单，不改库）
$PY $S/dedupe.py --new "$WS/_tmp/recs.json" --lib "$LIB" --out "$WS/_tmp/cand.csv"

# 4 归一：写 map.json（措施名 → 分部/子分部/分项/适用部位）
#   {"铝模快拆体系施工工艺": ["主体结构","混凝土结构","模板","全楼层"], ...}

# 5 落库（幂等，同一 --source 二次执行会拒绝）
$PY $S/ingest.py --recs "$WS/_tmp/recs.json" --lib "$LIB" --img "$IMG" \
    --map-file "$WS/_tmp/map.json" --merge-map "$WS/_tmp/merge_map.json" \
    --source 新素材 --chapter 工艺优化 --type 工艺优化

# 6 库内同部位同做法自查（出候选 → 人工确认 → 合并）
$PY $S/dedupe_content.py --lib "$LIB" --out "$WS/_tmp/去重候选.csv"
#   逐组看原文，写 merge_decisions.json（见 assets/decisions.example.json）
$PY $S/dedupe_content.py --lib "$LIB" --decisions "$WS/_tmp/merge_decisions.json"
$PY $S/review_sheet.py --lib "$LIB" --prededupe "$LIB.prededupe.json" \
    --decisions "$WS/_tmp/merge_decisions.json" --out "$WS/精益建造措施_按分部分项排序.xlsx"

# 7 校验（七项必须全绿）
$PY $S/validate.py --lib "$LIB" --img "$IMG" --strict

# 8 同步到红/蓝项目 + 加新栏目 + 重出统计表
$PY $S/sync.py --workspace "$WS"
$PY $S/add_columns.py --workspace "$WS" --col "信息词条:TEXT" --fill
$PY "$WS/0分部分项划分/lean_stats.py"

# 9 发布：EXE + 静态站（先关掉正在运行的程序）
$PY $S/build_exe.py --root "$WS/0分部分项划分" --out "$WS/成果发布" --hidden lean_import
$PY $S/make_web_release.py --data "$WS/0分部分项划分/data" --out "$WS/成果发布"
```

### 增量补信息词条（老库升级）

```bash
$PY $S/ingest.py --lib "$LIB" --img "$IMG" --backfill-terms --dry-run   # 先看样例
$PY $S/ingest.py --lib "$LIB" --img "$IMG" --backfill-terms             # 再写入
```

---

## 十、多板块项目群（2026-11 定型）

当一个项目要交付**多个板块**（精益建造 / 进度 / 质量 / 安全…）且素材同源时，不要每个板块各建一套提取脚本，
按三层拆：**主门户管范围与进程 → 通用中心管数据 → 子项目管成果**。完整协议、目录、端口见
`references/architecture.md`，这里只列必须记住的四条：

1. **一个素材只解析一次**。多板块靠「列映射」复用：同一数据集，对每个子项目保存一套列名/槽位映射
   （`mappings` 表按 `dataset_id × target_key` 唯一）。不要为了适配某板块去改通用列名。
2. **同步双通道**：文件快照必写（子项目没启动也生效）+ `POST /api/factory_sync` 尽力推。快照写子项目
   `data/factory/<数据集>.json`，子项目自己的转换结果写 `data/factory_items/`——**两者必须分目录**，
   否则后一次同步会覆盖前一次的数据集。
3. **子项目不硬编码列名**：目录下放 `factory_target.json` 声明 `slots`（title/content/effect/image/div1…），
   通用中心读它做一键映射；改叫法只改这个文件。
4. **通用中心是 `role=factory` 的固定板块**（:5090），门户里不参与「按范围出成果」的勾选，只提供启动与打开。

新增板块：门户「+ 添加 → 新建」生成骨架（已内置 `/api/factory_sync`、范围过滤、Excel 导出）
→ 改 `factory_target.json` → 通用中心点刷新 → 选数据集映射 → 同步，10 分钟接通。

发布仍在子项目维度做：通用中心「同步与发布」对任一子项目出静态站（自动压图控 1900 文件 / 96MB）
或调它的 `build_release.py` 打包 exe（打包后统一把最新 exe 复制到 `<子项目>/成果发布/`）。

---

## 十一、手动录入与平台目录（2026-11-14）

### 11.1 手动录入页：素材之外的第二条数据入口

素材里没有的做法、现场拍的照片，都在这一页进库，不要逼用户先做成 Office 文件。
一个合格的手动录入页必须同时有三件东西，缺一件就会被绕开：

| 要素 | 落地 |
|---|---|
| 表单按词条自动生成 | 读 `fields`（按 `ord`），正文/效果用多行框，`div1/div2/div3/pos` 从字段区剔除、统一走底部带候选的专用区块（否则会出现「分部」输入框重复两遍） |
| 图片 | 拖拽 + 多选 + 缩略图 + 单张删除；**最长边压 1920 存 JPEG q88**，sha1 内容去重（同一张图第二次上传不占空间）；未保存就删的图调 `DELETE .../image?filename=` 清孤儿，被记录引用的一律保留 |
| 确认后的节奏 | 两个按钮：`确认，录入下一条`（保存→清空→光标回第一个框）与 `确认并完成`（保存→小结「本次已录入 N 条」+ 继续/去查看）；`Ctrl+Enter` 等同下一条；右侧常驻本次会话已录入清单，心理上有进度 |

接口四件套（通用中心 app.py）：

```
POST /api/dataset/<key>/entry          保存一条；title 取 role=title 的字段，空则正文前 40 字
POST /api/dataset/<key>/image          multipart 多图 → 压图 + sha1 去重 → 返回元数据
DELETE /api/dataset/<key>/image?filename=  清未被引用的图
POST /api/dataset/<key>/field          追加词条，code = f{max+1}，ord 追加到末尾
```

分部留空 → `divmap.guess(标题 + 正文前 600 字)` 自动识别，响应回 `auto_div` 与 `msg`，
前端 toast 直接显示「第 65 条已保存（自动分部：建筑装饰装修）」，用户就知道不用手填。
保存后必做三件事：`dataset_stats` → `bump`（版本+1）→ `mark_dirty`（45 秒内自动同步子项目）。

### 11.2 平台目录：三项目分文件夹

```
D://AIproject//项目管理平台//
├─ 启动平台.bat
├─ 门户\        主项目 5080
├─ 通用中心\    通用项目 5090
└─ 精益建造\    子项目 5099
```

迁移/复制项目时按这个顺序改，漏一条就会出现「打不开 / 数字不对 / 同步不到」：

1. `门户\config\subprojects.json` 里每个 `dir` 改绝对新路径（这是唯一的注册表）。
2. 通用中心找门户配置的搜索顺序：`HUB_HOME` 环境变量 → `<上级>\门户\config` → `<上级>\config` → 同级任意子目录。
   门户 `hub_lib.start()` 拉子项目时注入 `env['HUB_HOME'] = HERE`，这样无论从门户还是双击 bat 启动都能找到。
3. SQLite 里的**绝对路径**要重写（`images.path`、`sources.path`）。
   不要用 `LIKE 'D://旧//%'` 猜字符串，直接按尾巴定位：`p.lower().find(os.sep+'data'+os.sep)`，
   取尾巴拼新根。迁移后校验 `SELECT COUNT(*) FROM images` 与「文件不存在的条数 = 0」。
4. `build_release.py` 的 `OUT_ROOT`：独立文件夹形态下应是 `ROOT/成果发布`，不是 `ROOT/../成果发布`。
5. 复制时排除 `build/ dist/ build_release/ __pycache__/ *.log .preview/`、发布目录里的 `网站发布_old_*`、
   `data`（exe 首次运行会自己生成）——352MB 的项目实际有效内容约 100MB。
6. 素材放进子项目自己的 `素材\`，并把通用中心 `data/settings.json` 的「素材目录」指过去，做到每个文件夹自包含。

### 11.3 Excel 批量录入：用户已经整理好表时，别让他再逐条敲

素材解析（PDF/PPT）是从排版里「猜」结构；Excel 录入是用户已经把结构**定好**了：
一行一条记录、一列一个关键词条，其中一列填图片位置。这条路的重点不是解析，而是**让用户核对映射**。

```
POST /api/dataset/<key>/xlsx/preview   文件(multipart) 或 {token|path, sheet, header_row, img_root}
POST /api/dataset/<key>/xlsx/import    {token, sheet, header_row, columns[], img_root, auto_div, dup}
```

实现要点（通用中心 `factory/xlsin.py` + `app.py` 三个函数）：

| 环节 | 硬要求 |
|---|---|
| 认表头 | 前 14 行里挑「非空≥2 + 短文本为主 + 下一行也有内容」得分最高者；容忍顶部大标题横幅/空行；**允许用户改「表头行」后重读**（Excel 行号，1 起） |
| 列→词条 | **语义列以角色为准**（标题/正文/效果/分部/子分部/分项/部位/楼层/图片），其余按词条名与别名匹配（全等 1.0、包含 0.8），都不中才「新建词条」；下拉可随时改成「现有：xx」「＋新建（角色）」「不导入」 |
| 图片位置 | 一格多张按 `; ； , 、 \|` 或换行拆；三种基准依次尝试：绝对路径 → 图片根目录 → Excel 所在目录（再按文件名在整个根目录里兜底） |
| 单元格内嵌图 | `ws._images` 按 `anchor._from.row` 归行；**锚定行没有数据时挂到上面最近的数据行（差 ≤3 行）**，否则用户缩放/合并单元格贴歪一张就丢 |
| 写库 | 复用逐条录入那套：压 1920/JPEG q88、sha1 去重、`divmap.guess` 补分部、`dataset_stats → bump → mark_dirty`；同名标题默认**更新原记录**（可选跳过/再存一条）；后台 job + 进度条 |

踩过的坑（都真实发生过）：

- **`secure_filename('测试录入.xlsx')` 会把中文整段吃掉，只剩 `xlsx` 没点号** → openpyxl 报
  `does not support  file format`。落盘名必须自己拼：`时间戳_英文部分+短哈希+ext`，原始中文名只用于显示。
- **上传的 Excel 已不在原目录，相对路径必然失效** → 预览里给黄色提示框「N 处图片是相对路径，填图片根目录后再重读」，
  并且导入结果的 msg 必须写「N 处图片路径没找到」。**不能静默丢图**——静默丢是这类功能最容易被投诉的点。
- **「图片位置」会先命中「位置」→ 被当成适用部位**：角色关键字表里图片规则必须排在部位/位置之前。
- **「子分部」按名字相似度会被错配到「分部」词条**（包含关系 0.8）：所以语义列先按角色取词条，名字只做兜底。
- **图片按 sha1 全局去重 → 同一张图被多个数据集共用**：删数据集时先
  `SELECT COUNT(*) FROM images WHERE filename=? AND dataset_id<>?`，没人引用才删实体文件，否则会把别人的图删掉。
- 预览表列多时用 `table-layout:fixed` + `overflow:hidden` + `title` 悬浮全名，只显示「要导入的列」，
  否则 7 列表格在 900px 面板里被挤成横向滚动条、最后一列被裁。

验证方式：curl/urllib 跑通接口只能证明「不报错」；**必须 CDP 真点**（`DOM.setFileInputFiles` 选文件 → 等预览表格 →
填图片根目录 → 点「按此重读」→ 点导入 → 等 `.ok-box`），模式切换、拖拽区、下拉改映射这些都只有真点才暴露问题。

---

## 十二、适配性四件套（2026-11-14 第二版）

上一版通用中心只能吃「结构规整、列名对得上词条」的素材；这一版解决四个真实反馈：
**列名对不上 → 直采**、**横版两栏串行 → 智能分栏**、**同类库分批来 → 合并扩展**、**一库要能独立交付 → 生成子项目**。

### 12.1 直采：不再映射到具体词条，用素材原有信息名

用户原话：「加强适配性，不再映射到具体词条，直接用原有素材的信息名」。

```
factory/xlsin.py   guess_columns(headers, fields, direct=True) → _guess_direct(headers)
app.py             _xls_direct(p)：'0'/'false'/'no'/'off' 才关，默认开
```

| 环节 | 直采（默认） | 并入现有词条（旧路数） |
|---|---|---|
| 列 → 词条 | **列名原样入库**，`action='new'`，`label=列名[:40]` | 语义列按角色取词条，其余按名字/别名匹配（全等 1.0、包含 0.8） |
| 角色 | 只推断 role（标题/正文/效果/图片/分部…） | 同左 |
| 空列名 | `ignore` + 「空列名，跳过」 | 同左 |
| 序号/编号列 | `role_of_label` 判 `ignore`：「序号/编号，不导入」 | 同左 |
| 重名列 | 自动加 `(2)`：`label = f'{name[:36]}({n})'[:40]` | 不会出现（会匹配到同一词条） |
| 标题列缺失 | **不报错**（记录标题取第一条长文本） | 必须有一列是标题/正文，否则前端禁用导入 |
| 前端 | 「导入方式」单选：按原表直采 / 并入现有词条，切换即按新方式重读；表头写「词条名（默认取原列名）」 | 表头写「映射到词条」 |

要点：**直采只决定「叫什么」，不决定「是什么」**——角色仍然要推断，否则子项目不知道哪列当标题、哪列当图片。
重名列加后缀是必须的，`fields` 表 `code` 唯一但 `label` 不唯一，不加后缀记录里两列会同名互相覆盖。

### 12.2 横版双栏 PDF：先整页找表，没表再分栏

用户原话：「有时候不是竖版，是横版两栏，需要智能判断」。横版手册一页左右两栏各自独立成条，
整页解析会把左右栏文字按 y 排序拼成一句（「预制叠合板 PC-DHB-60 预制楼梯 PC-LT-1200 …」）。

```
factory/ingest.py
  parse_pdf()          → ① 整页 _pdf_parse_region(tables_only=True) 先找表
                          有表 → 整页解析（并排双栏表只有整页才认得全，靠 _expand_dual 拆行）
                          没表 → ② _column_rects(page) 找栏缝 → ③ 一栏一栏走 表格→卡片→文本卡片
  _column_rects(page)  x 投影直方图（2pt 网格）找 ≥12pt 的缝，左右各 ≥5 行才算栏
  _pdf_parse_region(..., clip)   表格 / 卡片 / 文本卡片全部支持 clip
  _pdf_images(..., clip)         只认落在本栏里的图（多取 cx 中点判断）
```

栏缝判定必须带**通栏行否决**：标题带以外出现跨栏行（页眉横幅、整段说明）就意味着这份 PDF 其实不是双栏，
直接退回整页解析，否则会解析出重复记录。页脚通栏单行不算（横版手册页脚常见），
但如果只找到页脚通栏、没有标题带，也退回整页——宁可少拆，不可拆错。

卡片标题判据补一条：`^\s*[（(]?\d{1,2}\s*[、.．)）]` 命中就当正文，不当标题。
否则分栏后左栏第一条会变成「4、 在混凝土浇筑过程中…」，正文为空、图全挂在它下面。

实测（同一份横版手册）：
```
优化工艺.pdf        64 条（每页 2 条，正文 157~185 字，各 2 图，标题全对）
标准部品部件建议.pdf  36 条（并排双栏表，整页找表 + _expand_dual 拆行，未分栏）
中建三局指导手册.pdf  81 条（竖版，误判分栏也不退化：正文均值 99 vs 94）
任务提示会写：N 页按横版/双栏拆栏解析：P3, P4…
```

### 12.3 合并同类库：词条并表 + 标题/内容指纹去重

用户原话：「解析出的数据库可以选择和已有数据库合并扩展（如果是同类），扩展后需要去重」。

```
factory/merge.py
  candidates(target_key)   词条 Jaccard：≥0.5 同类 / ≥0.2 部分相同 / 否则不同类
  merge_into(target, sources, dedup='content', keep_source=False)
    词条：_norm(label) 归一化并表；目标 role 是 other 而源更明确 → 被源覆盖；重名同类合并
    记录：rid = existing_title[tkey] → 命中则「同名合并」（只补空字段，不覆盖已有值）
          rid 为空且长字段（≥10 字）指纹命中 → 「内容重复」跳过
          都不命中 → 新增
    图片：按 sha1 去重，同图只挂一次；删源库时按引用计数清文件，别把别人在用的图删了
```

去重三档给用户选：`content`（标题+指纹，默认）/ `title`（只按标题）/ `none`（全量追加拼库）。
界面上必须把「同类程度」摆在候选旁边（`同类 · 词条重合 100%`），否则用户会拿两个不相干的库硬并，
合并完词条翻倍、记录全在，还以为是 bug。

### 12.4 一个数据集 = 一个子项目

用户原话：「一个数据库对应一个子项目，需要新建子项目文件夹，填充全部子项目代码进去，子项目能独立运行和发布」。

```
门户/scaffold_full/          完整子项目模板（18 个文件，从 精益建造/ 复制并换键名）
factory/provision.py
  provision(dataset_key, name, sub_id, port, board, launch, parent, job)
    _copy_template → _substitute(__ID__/__NAME__/__BOARD__/__PORT__/__DATASET__/__DATASET_NAME__/__CNAME__/__ICON__)
    → data/subproject.json（身份 + 绑定数据集 + labels/slots）
    → factory_target.json（槽位声明）
    → data/library.json = []（自有库留空，只吃通用中心）
    → 门户 config/subprojects.json 追加（唯一注册表）
    → sync.discover_targets() + sync.sync_dataset(key, [sid])
    → 可选 _spawn(SUB_PORT=port)
  delete_subproject(sid, drop_files=True)  退登记 + os.replace 挪进 子项目/_回收站/
```

槽位兜底（这段是「子项目 PDF/PPT 卡片整段空白」的根治办法）：

```python
# provision._slots_from_dataset
# ① 源表有 content/effect 词条 → 直接用
# ② 没有 → 扫 80 条真实记录算每列平均长度，把最长的两列「其它信息」升级为 content / effect
spare = [f for f in fields if f['role'] in ('other','tag','type') and f['code'] not in roles.values()]
spare.sort(key=lambda f: -avg.get(f['code'], 0));  # 平均长度 <4 的列跳过
db.x('UPDATE fields SET role=? WHERE id=?', (role, f['id']))
```

不能再只看 `f['sample']`：词条上的 sample 经常是空的（解析时没回填），只看 sample 会全部判 0 → 一个都不升级。
`sub_lib.load_factory_items()` 里另有一层兜底：快照没有 content 槽位时取最长字段当 content，保证老快照也能出图。

模板改造清单（把 精益建造 变成通用 sub_*）：

| 原文件 | 新文件 | 改什么 |
|---|---|---|
| lean_lib.py | sub_lib.py | `CFG/NAME/SUB_ID/BOARD/DATASET_KEY/LABELS/CHAPTER_ORDER`；`load_measures()` = 自有库 + 绑定数据集快照（外部 id 90001 起，同名以自有为准）；`_from_snapshot` 按 slots 取语义值 |
| lean_pdf/ppt/excel.py | sub_pdf/ppt/excel.py | 分段标题与表头读 `sub_lib.LABELS`；**键名全量换英文**（`优化内容→content`、`优化效果→effect`、`优化措施名称→title`、`图片→images`、`分部工程→div1`、`章节→chapter`、`优化类型→type`） |
| app.py | app.py | `SUB_ID/SUB_NAME = sub_lib.*`；`/api/factory_sync` 只存快照并校验绑定数据集（不匹配 409）；`PORT` 读 `SUB_PORT` / `data/subproject.json`；`lean_cards` 章节遍历改 `list(CHAPTER_ORDER) + 其它出现的章节` |
| make_web_release.py | web_release.py | `load()` 改走 `sub_lib.load_measures()`，字段映射改英文键 |

### 12.5 这一版踩过的坑

- **改完模板但已生成的子项目没变**：provision 只复制不覆盖已存在的目录（同名自动加 `2`），
  改模板后必须重新生成；想省事就让 `delete_subproject` 挪走旧目录再生成。
- **`shutil.rmtree` 被安全策略拦**（`[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] count=50`）：
  Windows 下几百个文件的目录既慢又可能被占用锁住。改成 `os.replace(d, 子项目/_回收站/<名>_<时间>)`，
  毫秒级、可恢复，顺带给用户一个「撤销」而不是「删了就没了」。
- **映射缓存导致角色升级不生效**：`mappings` 表里的旧映射 `slot` 是空的，`get_mapping` 只补「新字段」不刷「老字段的空槽」，
  结果快照里 `slot:""` → 子项目拿不到正文。修法：`get_mapping` 里逐字段比对，`c.get('slot')` 为空且 `f['role']` 是合法槽位 → 回填并 `dirty` 落库。
- **`.split('、')` 之外还有 `1、` 编号行**：卡片标题判据不排除编号行，分栏后标题会变成编号条目（见 12.2）。
- **并排双栏表先分栏就废了**：必须在整页上先跑一次 `find_tables`，有表就整页解析，否则一行被切成两半（36 条 → 50 条带 `+Lae` 碎片）。
- **`targets` 列表重复**：`syncs` 表每次同步插一条，列表接口直接 `SELECT target_key` 就会重复；
  改 `GROUP BY target_key ORDER BY MAX(id) DESC`。
- **同一个数据集生成了两个子项目没关系，但端口别撞**：`alloc_port` 用 `socket.connect_ex` 探活，
  再从 `5101-5199` 里挑第一个空的；已生成的子项目记在门户注册表里，重复生成会分配到不同端口。
- **生产实例要重启才加载新代码**：Flask 关掉 debug 就没有自动重载；改完 `factory/*.py` 必须杀掉 5090 进程重开
  （Windows 上 `taskkill /PID <pid> /F`，别用 `netstat` 找到的第一个 pid —— 曾出现两个进程同时 listen 同一端口，
  请求被旧进程接走，表现为「新接口 404」）。
