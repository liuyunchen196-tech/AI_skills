---
name: scanned-pdf-ocr-pipeline
display_name: 扫描件 OCR 转文本
display_name_en: Scanned PDF OCR Pipeline
agent_created: true
description_zh: 把无文字层的扫描版 PDF OCR 成可检索文本。与同类工具的四点差异：①先用 PyMuPDF 诊断确认真无文字层再决定是否 OCR，不浪费算力；②批量前预估总耗时（实测 1194 页约 100 分钟）让用户先知情；③OCR 后自动做质量自检（繁体占比、重复行占比、单字行占比），问题当场暴露而非留给下游；④断点续跑，中断不丢进度。附 RapidOCR 引擎选型对比与 dpi=120 实测甜点参数。
description_en: "OCR scanned PDFs into searchable text, with four differentiators over generic tools - diagnose before spending compute, estimate total runtime upfront, self-check output quality (traditional-Chinese ratio, duplicate-line ratio, single-char-line ratio) so problems surface immediately, and resume from where it stopped. Includes engine selection data and a measured dpi=120 sweet spot."
description: "把无文字层的扫描版 PDF OCR 成可检索文本"
category: productivity-tools
version: 1.0.0
author: Individual Developer
---

# 扫描版 PDF 的 OCR 流水线

## 核心原则：先诊断，再 OCR

**不要看到抽出内容少就直接上 OCR。** 先用 PyMuPDF 判断是否真无文字层——
有文字层但抽不出来的，可能是编码问题，用 OCR 是浪费。

```python
import fitz
d = fitz.open(p)
for i in 抽样页:            # 前 12 页 + 后 12 页
    chars += len(d[i].get_text().strip())
    withtext += (len(t) > 30)
    imgs  += len(d[i].get_images(full=True))
# chars < 50 或有字页比例 < 10%  → 扫描件
```

实测案例：一个 1156 页 PDF 抽出 1559 字符，看似"空壳"，
实为**只有 3 页有文字层**的 1156 页扫描件——**不是文件坏了，是内容是图片**。

## 引擎选型（Windows，实测）

| 方案 | 结果 | 说明 |
|---|---|---|
| **`rapidocr-onnxruntime`** | ✅ 可用 | 纯 wheel、自带中文模型、pip 5 秒装好、零编译 |
| `winsdk`（Windows 内置 OCR） | ❌ 编译失败 | Python 3.13 不兼容，项目已弃维护 |
| `pytesseract` | ❌ 不可用 | 只是接口，还需另装 tesseract 引擎 |
| Windows 自带 OCR 引擎 | ❌ 不可用 | 系统语言包默认未装（注册表 `OCR\Languages` 键不存在） |
| Tesseract-OCR | ❌ 未安装 | 需另行下载安装 |

**结论**：本机（或类似环境）首选 `rapidocr-onnxruntime`。

```bash
pip install rapidocr-onnxruntime opencc-python-reimplemented
```

## 关键参数：dpi=120 是甜点

实测同一页：

| dpi | 耗时 | 识别字数 | 评价 |
|---|---|---|---|
| 120 | 5.3s | 612 | **推荐** |
| 145 | 5.8s | 583 | 无必要 |
| 170 | 7.1s | 613 | 质量几乎相同，慢 25% |

高 dpi 不提升质量（瓶颈是模型而非分辨率），纯属浪费。

## OCR 后必须清洗

OCR 文本会夹带大量噪声，**不清洗会污染后续所有统计与检索**。四步清洗：

1. **删站点水印行** —— 常见如"关注XX公众号""获取更多免费资料"，每页 1-2 行
2. **删孤立页码行** —— OCR 会把页脚页码识别成孤立数字行
3. **压缩连续空行**
4. **繁简统一** —— 若原书是繁体（繁简混排会降低后续可读性），用 `opencc` t2s

实测：一本 304 页书清洗掉 7016 字噪声。

清洗正则示例见 `scripts/pdf_ocr.py` 的 `clean_text()`。

## 用法

```bash
python scripts/pdf_ocr.py <pdf或目录> [输出目录] --dpi 120 --t2s
```

脚本自动：诊断 → 有文字层直接抽 / 扫描件走 OCR → 清洗 → 合并。

## 批量前先预估耗时

用户面对几十本书时不知道要等多久，**先算总页数与耗时再动手**：

```bash
python scripts/pdf_ocr.py <目录> <输出> --dpi 120
# 脚本先输出：合计 1194 页，预计 100 分钟（按 5.0 秒/页）
```

实测 8 个 PDF / 1194 页 → 100 分钟，与实际耗时吻合。**中断可续跑，不会丢进度。**

## OCR 后质量自检（关键，别跳过）

自动检测三类问题，**问题当场暴露而不是留给下游**：

| 指标 | 阈值 | 含义 |
|---|---|---|
| 繁体占比 | > 2% | 原书是繁体且未转换，需 t2s |
| 重复行占比 | > 30% | 水印/页眉未清干净 |
| 单字行占比 | > 25% | 版面没正确切分 |

**一次失败的判据设计值得记**：最初用"非常用字占比"判断错字率，**实测不可行**——
500 字高频字表对真实文本覆盖率只有 64%，连「女」「话」这类常用字都在表外，
正常文本被误判为"错字率偏高"。**改用不依赖字表的结构指标才稳。**

## 关键：断点续跑是刚需

OCR 1000 页可能跑 40+ 分钟，**必须支持断点续跑**。脚本逐页落盘到
`_pages/<书名>/0000.txt`，重跑时已存在的页直接跳过。中断不丢进度。

## 执行纪律

1. **OCR 是长任务，放后台跑**（`run_in_background`），不要挂在主流程里
2. **不要在命令里加 `| tail`** —— 缓冲住输出看不到进度。脚本内部 `flush=True` 打印进度
3. **OCR 质量受原书影响大**，同一引擎不同书差异明显：
   - 简体书（错字少）→ 可直接使用
   - **繁体书** → 繁简混排 + 同音错字密集，需先 t2s 再靠人工阅读还原
4. **OCR 后仍需人读还原错字**：同音字会被系统性识别错（专有名词尤其明显，
   如某书名被识成形近的另一个词）。精读时 prompt 要明确"能还原就还原，还原不了跳过该句"
5. **不要把 OCR 文本当权威底本引用**，尤其是要逐字引用时——错字会传播

## 成本参考

- dpi=120，每页约 5 秒
- 300 页 ≈ 25 分钟；1200 页 ≈ 100 分钟
- 批量前先算总页数告知用户

## 延伸阅读

完整实测记录（引擎选型逐项失败过程、dpi 对比数据、质量判据的失败版本、清洗四步、
断点续跑实现要点）见 `references/pitfalls.md`。
**尤其要看「质量自检判据的演进」那一节** —— 里面记录了一个看起来合理但在真实语料上
完全失效的判据设计。
