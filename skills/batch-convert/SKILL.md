---
name: batch-convert
description: 批量文档格式转换黑科技（claude-office-skills 官方版本地适配）。当用户需要批量转换文档格式——批量 PDF 转 Word、批量 Markdown 转 PDF/HTML、Office 文件转 Markdown、图片批量转 PDF、旧格式 .doc/.xls/.ppt 迁移为 .docx/.xlsx/.pptx 时使用。触发词：\"批量转换\"、\"批量转格式\"、\"所有PDF转Word\"、\"这个文件夹的文档转成\"、\"批量转markdown\"、\"格式批量转换\"、\"旧格式迁移\"、\"batch convert\"、\"bulk convert\"。基于 pandoc + LibreOffice + pdftotext 本地实现，支持 md/docx/pdf/xlsx/pptx/html 互转及旧格式迁移，多线程并行处理。不适用于：单文件精修转换（用 pandoc-pdf-converter / text-io）、扫描件 OCR（用 textin-xparse）。
version: 2.0.0
display_name: 批量文档格式转换黑科技（cl
display_name_en: Batch Convert
description_zh: 批量文档格式转换黑科技（claude-office-skills 官方版本地适配）。当用户需要批量转换文档格式——批量 PDF 转 Word、批量 Markdown 转 PDF/HTML、Office 文件转 Markdown、图片批量转 PDF、旧格式 .doc/.xls/.ppt 迁移为 .docx/.xlsx/.pptx 时使用。触发词：\"批量转换\"、\"批量转格式\"、\"所有PDF转Word\"、\"这个文件夹的文档转成\"、\"批量转markdown\"、\"格式批量转换\"、\"旧格式迁移\"、\"batch convert\"、\"bulk convert\"。基于 pandoc + LibreOffice + pdftotext 本地实现，支持 md/docx/pdf/xlsx/pptx/html 互转及旧格式迁移，多线程并行处理。不适用于：单文件精修转换（用 pandoc-pdf-converter / text-io）、扫描件 OCR（用 textin-xparse）。
description_en: 'WorkBuddy edition of ''Batch Convert''. Domain: 批量文档格式转换黑科技（claude-office-skills 官方版本地适配） Trigger scenarios: \"批量转换\". For full Chinese description and capabilities, see description_zh. You may edit this English description on the platform after publishing.'

---
# Batch Convert 批量格式转换（本地适配版）

> v2.0.0 专家级（2026-09-07）：补齐九要素——分步工作流带检查点、输出规范（report.json）、边界与反模式、依赖降级、实战范例；修正脚本绝对路径；支持矩阵与分工原文保留。

## 〇、专家级路由（v2.0.0）

**专家定位**：目录级批量格式转换专家。一个命令整批换格式，带并行、错误隔离与 report.json 报告。

**五维评估**：
- 适用场景：整批 PDF 转 Word；Markdown 导出 PDF/HTML；旧 .doc/.xls/.ppt 迁移；台账批量转 xlsx
- 能力边界：不做单文件精修、扫描件 OCR；不支持矩阵外格式
- 依赖资产：scripts/batch_convert.py + pandoc + LibreOffice + pdftotext
- 交付质量：试转通过、report.json 成功失败清单齐全、抽查产物可打开
- 性能表现：默认 4 线程并行；单批 10-50 份最顺

**四级响应（L1-L4）**：
- L1 问支持矩阵/命令用法 → 直接答
- L2 单文件转换 → 一条命令 + 产物抽查
- L3 目录批量 → 先试转 1 份，再批量，后核对 report
- L4 全库迁移归档 → 试转 + 批量 + 报告 + 失败修复 + 交付清单

**黄金窗口**：单批 10-50 个文件；大文件批次降 --workers 2
**专家件索引**：scripts/batch_convert.py（唯一入口）；支持矩阵与降级表见正文

## 定位声明

本技能是多文件批量格式转换器：一个命令把整个目录的文档统一转成目标格式，带并行处理、错误隔离和转换报告。给"一批文件要换格式"的归档、迁移、入库任务用。ima 沙箱适配为本地工具链：**pandoc + LibreOffice(soffice) + pdftotext + python-pptx**，无需外部服务。

## 触发条件

**场景清单**（与 description 呼应）：

- "这个文件夹里的 PDF 都转成 Word"
- 整批 Markdown 汇报材料导出 PDF/HTML
- 旧格式 .doc/.xls/.ppt 批量迁移为 .docx/.xlsx/.pptx
- 多个 Excel 台账批量转 csv/汇总前格式统一
- 单文件转换需求量大（≥3 个）时也走本技能

**中文触发词**：批量转换、批量转格式、旧格式迁移、格式批量转换、所有PDF转Word、批量转markdown。
**English triggers**：batch convert、bulk convert、convert folder to pdf。

**不适用**：单个文件的精细转换（用 pandoc-pdf-converter / text-io）；扫描件 OCR（用 textin-xparse / scan-extract）；PDF 创建编辑（用 ima-pdf）；Word 创建编辑（用 ima-doc）。

## 分步工作流

**输入**：文件或目录 + 目标格式 → **处理**：匹配工具链并行转换 → **输出**：目标格式文件 + 可选 report.json → **检查点**：试转单文件、抽查产物。

1. **确认目标格式在支持矩阵内**（见下表），范围外格式先告知用户改方案。
2. **先试单个**：批量前先转换一个文件验证目标格式效果：
   ```bash
   python3 /root/.skills/batch-convert/scripts/batch_convert.py <单个文件> <目标格式> --out /tmp/test_out
   ```
3. **检查点 A**：打开 /tmp/test_out 产物确认排版、表格、中文编码正常；异常时换工具链或放弃该方向。
4. **批量执行**：
   ```bash
   python3 /root/.skills/batch-convert/scripts/batch_convert.py <输入文件或目录> <目标格式> [--out 输出目录] [--recursive] [--pattern *.md] [--workers 4] [--report report.json]
   ```
5. **检查点 B**：读 report.json——成功数/失败数/失败原因清单；失败文件单独处理或重跑。
6. **交付**：汇报成功 N 个、失败 M 个及原因，产物位置与输出目录结构。

**命令**：

```bash
python3 /root/.skills/batch-convert/scripts/batch_convert.py <输入文件或目录> <目标格式> [--out 输出目录] [--recursive] [--pattern *.md] [--workers 4] [--report report.json]
```

**示例：**

- `batch_convert.py ./合同/ pdf --recursive` —— 目录下所有文档批量转 PDF
- `batch_convert.py ./汇报材料/ docx --pattern *.md` —— 所有 Markdown 转 Word
- `batch_convert.py 旧资料/ xlsx --pattern *.xls` —— 旧 .xls 迁移为 .xlsx
- `batch_convert.py 扫描件.pdf md` —— 单文件 PDF 提取为 Markdown 文本
- `batch_convert.py ./docs html --recursive --report export.json` —— 批量转 HTML 并输出报告

## 支持矩阵（沙箱实测能力）

| 目标\来源 | MD | DOCX | DOC | PDF | XLSX | XLS | PPTX | PPT | HTML | RTF | TXT |
|----------|----|------|-----|-----|------|-----|------|-----|------|-----|-----|
| **docx** | ✅pandoc | - | ✅soffice | ✅文本级 | - | - | - | - | ✅pandoc | ✅ | ✅ |
| **pdf** | ✅pandoc | ✅soffice | ✅soffice | - | ✅soffice | ✅soffice | ✅soffice | ✅soffice | ✅pandoc | ✅ | ✅ |
| **md** | - | ✅pandoc | - | ✅pdftotext | ✅pandas | ✅pandas | ✅pptx库 | - | ✅pandoc | ✅ | ✅ |
| **html** | ✅pandoc | ✅pandoc | - | ✅文本级 | - | - | - | - | - | ✅ | ✅ |
| **xlsx** | - | - | - | - | - | ✅soffice | - | - | - | - | - |
| **pptx** | - | - | - | - | - | - | - | ✅soffice | - | - | - |

说明：

- **PDF→Word/HTML** 为文本级转换（pdftotext+pandoc），保留文字不保留排版；扫描件 PDF 无文字层需先 OCR（用 textin-xparse）
- **DOCX→MD** 沙箱优先用 pandoc；需要高质量含表格转换时可用 anydoc（`npx -y @firecrawl/anydoc file.docx -o out.md`）
- MD→PPTX 需 marp CLI（未预装，`npm install -g @marp-team/marp-cli` 后可启用）

## 输出规范

- **产物文件**：与源文件同名、扩展名为目标格式，集中在 `--out` 指定目录（默认：输入目录/converted）。
- **报告文件**：`--report report.json` 输出转换清单，含每个文件的源路径、目标路径、成功/失败与原因——交付时必附。
- **命名规则**：不修改源文件名；同名冲突时后到者覆盖前到者（先转出的文件移走或换 --out）。
- **汇报格式**：成功 N / 失败 M / 跳过 K（不在支持矩阵内），失败逐条列原因。

## 边界与反模式

**不适用场景**：见"触发条件 → 不适用"。

**禁止行为**：

- 禁止跳过单文件试转直接批量跑——格式效果问题会在整批上放大。
- 禁止对扫描件 PDF 反复重试转 docx——无文字层必失败，先 OCR。
- 禁止把 --workers 拉满到大文件批次——内存压力导致进程被杀，大文件用 `--workers 2`。
- 禁止删除或覆盖源文件——本技能只读源、写目标目录。

**常见错误**：

- soffice 转换进程残留：批量结束后 `pkill -f soffice` 清理再复跑。
- .xls 老格式打不开：先 `soffice --headless --convert-to xlsx` 转 xlsx 再处理。
- 中文文件名乱码：确认 locale 为 UTF-8，或先重命名再批量。

## 依赖说明

| 依赖 | 用途 | 缺失时的降级 |
|------|------|-------------|
| pandoc | md/docx/html 互转 | 用 anydoc（docx→md）或 soffice 兜底 |
| LibreOffice (soffice) | doc/ppt/xls 系转换 | 无则该方向不可用，告知用户改在本机转换 |
| pdftotext | PDF 文本级提取 | 用 pymupdf（chat-with-pdf 的 extract）替代 |
| pandas + openpyxl | xlsx/xls→md 表格提取 | 用 excel-automation 的 excel_tools.py 替代 |
| Python 3.8+ | 运行 batch_convert.py | 必需，沙箱已预装 |

## 与既有技能分工

- 单文件转换/格式互转 → pandoc-pdf-converter / text-io
- **批量多文件转换 → 本技能（并行 + 报告 + 错误隔离）**
- 扫描件 OCR → textin-xparse / scan-extract
- PDF 创建编辑 → ima-pdf；Word 创建编辑 → ima-doc

## 最佳实践

1. **先试单个**：批量前先转换一个文件验证目标格式效果
2. **错误隔离**：单个失败不影响整批，--report 输出完整清单
3. **并行度**：默认 4 线程，大文件可降 --workers 2 防内存压力
4. **输出校验**：转换后抽查文件（大小/打开/内容）

## 实战范例

### 范例：旧合同台账批量迁移归档

用户：「这批 2019 年的 .xls 合同台账要迁到新系统，统一转成 .xlsx。」

1. **输入**：`./旧台账/` 目录，约 40 份 .xls（【待核：实际份数】）。
2. **试转**：`batch_convert.py ./旧台账/某项目合同台账.xls xlsx --out /tmp/test_out` → 打开确认数据完整。
3. **批量**：`batch_convert.py ./旧台账/ xlsx --pattern *.xls --out ./新台账/ --report ./新台账/report.json --workers 2`。
4. **检查点**：report.json 显示成功 40 / 失败 0；抽查 3 份数据行数与源文件一致。
5. **输出**：`./新台账/` 下 40 份 .xlsx + report.json；汇报迁移结果与失败清单（如有）。

### 范例 2：月度汇报材料批量导出 PDF

用户：「汇报材料文件夹里的 Markdown 都导出成 PDF 发领导。」

1. 试转 1 份确认中文字体与表格渲染正常。
2. `batch_convert.py ./汇报材料/ pdf --pattern *.md --out ./汇报PDF/ --report ./汇报PDF/report.json`。
3. 抽查页数与图表；失败的用 pandoc 单独排查后重跑。

## 版本与变更记录

- **v2.0.0（2026-09-07）**：补齐九要素；脚本路径修正为 /root/.skills/batch-convert/scripts/；新增输出规范、边界与反模式、依赖降级表、实战范例；支持矩阵与最佳实践原文保留。
- **v1.1.0**：本地工具链适配（pandoc + soffice + pdftotext）。
- **v1.0.0**：首版（office-mcp batch_convert）。
