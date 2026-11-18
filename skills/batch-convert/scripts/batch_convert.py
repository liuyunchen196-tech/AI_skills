#!/usr/bin/env python3
"""
Batch Convert 批量格式转换黑科技（claude-office-skills 官方版本地适配）
依赖：pandoc + soffice/libreoffice + pdftotext + pymupdf + python-pptx（沙箱预装）
可选：anydoc（npx @firecrawl/anydoc，Office→Markdown 高质量转换）

用法：
  python3 batch_convert.py <输入文件或目录> <目标格式> [--out 输出目录] [--recursive] [--pattern *.md] [--report report.json]

支持矩阵（沙箱实际能力）：
  md/docx/pdf/xlsx/pptx/html -> docx/pdf/md/html（核心）
  doc/xls/ppt/rtf -> docx/xlsx/pptx（旧格式迁移，soffice）
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SUPPORTED_SRC = {'.md', '.docx', '.doc', '.pdf', '.xlsx', '.xls', '.pptx', '.ppt', '.html', '.rtf', '.txt', '.csv'}
SUPPORTED_DST = {'docx', 'pdf', 'md', 'html', 'xlsx', 'pptx', 'csv', 'txt'}


def run(cmd, timeout=300):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd)}\n{r.stderr[:500]}")
    return r


def convert_one(src: Path, dst_fmt: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{src.stem}.{dst_fmt}"
    ext = src.suffix.lower()

    # --- Markdown 目标 ---
    if dst_fmt == 'md':
        if ext in ('.docx', '.html', '.txt', '.rtf'):
            run(['pandoc', str(src), '-t', 'markdown', '-o', str(out)])
        elif ext in ('.xlsx', '.xls'):
            import pandas as pd
            df = pd.read_excel(str(src))
            df.to_markdown(str(out)) if hasattr(df, 'to_markdown') else df.to_csv(out, sep='|', index=False)
        elif ext == '.pptx':
            from pptx import Presentation
            prs = Presentation(str(src))
            lines = []
            for i, slide in enumerate(prs.slides, 1):
                lines.append(f"## Slide {i}")
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            t = "".join(run_.text for run_ in para.runs)
                            if t.strip():
                                lines.append(t)
            out.write_text("\n".join(lines), encoding='utf-8')
        elif ext == '.pdf':
            r = subprocess.run(['pdftotext', '-layout', str(src), '-'], capture_output=True, text=True)
            out.write_text(r.stdout, encoding='utf-8')
        else:
            raise ValueError(f"不支持 {ext} -> md")
    # --- PDF 目标 ---
    elif dst_fmt == 'pdf':
        if ext == '.md':
            # 沙箱无 LaTeX 引擎：pandoc md->docx，soffice docx->pdf 两步
            tmp = out_dir / f"{src.stem}_tmp.docx"
            run(['pandoc', str(src), '-o', str(tmp)])
            run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', str(out_dir), str(tmp)])
            real = out_dir / f"{src.stem}_tmp.pdf"
            real.rename(out)
            tmp.unlink(missing_ok=True)
        elif ext == '.html':
            run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', str(out_dir), str(src)])
            real = out_dir / f"{src.stem}.pdf"
            if real != out:
                real.rename(out)
        elif ext in ('.docx', '.xlsx', '.pptx', '.doc', '.xls', '.ppt', '.rtf', '.txt'):
            run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', str(out_dir), str(src)])
            real = out_dir / f"{src.stem}.pdf"
            if real != out:
                real.rename(out)
        else:
            raise ValueError(f"不支持 {ext} -> pdf")
    # --- DOCX 目标 ---
    elif dst_fmt == 'docx':
        if ext in ('.md', '.html', '.txt', '.rtf'):
            run(['pandoc', str(src), '-o', str(out)])
        elif ext in ('.doc',):
            run(['soffice', '--headless', '--convert-to', 'docx', '--outdir', str(out_dir), str(src)])
            real = out_dir / f"{src.stem}.docx"
            if real != out:
                real.rename(out)
        elif ext == '.pdf':
            r = subprocess.run(['pdftotext', '-layout', str(src), '-'], capture_output=True, text=True)
            (out_dir / f"{src.stem}.txt").write_text(r.stdout, encoding='utf-8')
            run(['pandoc', str(out_dir / f"{src.stem}.txt"), '-o', str(out)])
            (out_dir / f"{src.stem}.txt").unlink(missing_ok=True)
        else:
            raise ValueError(f"不支持 {ext} -> docx")
    # --- HTML 目标 ---
    elif dst_fmt == 'html':
        if ext in ('.md', '.docx', '.txt', '.rtf'):
            run(['pandoc', str(src), '-s', '-o', str(out)])
        elif ext == '.pdf':
            r = subprocess.run(['pdftotext', '-layout', str(src), '-'], capture_output=True, text=True)
            (out_dir / f"{src.stem}.txt").write_text(r.stdout, encoding='utf-8')
            run(['pandoc', str(out_dir / f"{src.stem}.txt"), '-s', '-o', str(out)])
            (out_dir / f"{src.stem}.txt").unlink(missing_ok=True)
        else:
            raise ValueError(f"不支持 {ext} -> html")
    # --- XLSX 目标（旧格式迁移）---
    elif dst_fmt == 'xlsx':
        if ext == '.xls':
            run(['soffice', '--headless', '--convert-to', 'xlsx', '--outdir', str(out_dir), str(src)])
            real = out_dir / f"{src.stem}.xlsx"
            if real != out:
                real.rename(out)
        else:
            raise ValueError(f"不支持 {ext} -> xlsx")
    # --- PPTX 目标（旧格式迁移）---
    elif dst_fmt == 'pptx':
        if ext == '.ppt':
            run(['soffice', '--headless', '--convert-to', 'pptx', '--outdir', str(out_dir), str(src)])
            real = out_dir / f"{src.stem}.pptx"
            if real != out:
                real.rename(out)
        else:
            raise ValueError(f"不支持 {ext} -> pptx")
    # --- CSV 目标 ---
    elif dst_fmt == 'csv':
        if ext in ('.xlsx', '.xls'):
            import pandas as pd
            pd.read_excel(str(src)).to_csv(out, index=False, encoding='utf-8-sig')
        elif ext == '.csv':
            shutil.copy(src, out)
        else:
            raise ValueError(f"不支持 {ext} -> csv")
    # --- TXT 目标 ---
    elif dst_fmt == 'txt':
        if ext == '.pdf':
            r = subprocess.run(['pdftotext', '-layout', str(src), '-'], capture_output=True, text=True)
            out.write_text(r.stdout, encoding='utf-8')
        else:
            run(['pandoc', str(src), '-t', 'plain', '-o', str(out)])
    else:
        raise ValueError(f"目标格式 {dst_fmt} 不支持")

    return out


def main():
    p = argparse.ArgumentParser(description="批量格式转换黑科技")
    p.add_argument('input', help="输入文件或目录")
    p.add_argument('fmt', help="目标格式: docx/pdf/md/html/xlsx/pptx/csv/txt")
    p.add_argument('--out', default=None, help="输出目录（默认：输入目录/converted）")
    p.add_argument('--recursive', action='store_true')
    p.add_argument('--pattern', default='*', help="文件通配符（目录模式）")
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--report', default=None, help="输出转换报告 JSON 路径")
    args = p.parse_args()

    src_path = Path(args.input)
    out_dir = Path(args.out) if args.out else (src_path if src_path.is_file() else src_path / 'converted')

    if src_path.is_file():
        files = [src_path]
    else:
        pat = f"**/{args.pattern}" if args.recursive else args.pattern
        files = [f for f in sorted(src_path.glob(pat)) if f.suffix.lower() in SUPPORTED_SRC]
    if not files:
        print("没有找到可转换的文件"); return 1

    print(f"共 {len(files)} 个文件 -> {args.fmt}，输出到 {out_dir}")
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(convert_one, f, args.fmt, out_dir): f for f in files}
        for fut in as_completed(futs):
            f = futs[fut]
            try:
                o = fut.result()
                results.append({'file': str(f), 'status': 'success', 'output': str(o)})
                print(f"  ✓ {f.name} -> {o.name}")
            except Exception as e:
                results.append({'file': str(f), 'status': 'error', 'error': str(e)[:200]})
                print(f"  ✗ {f.name}: {str(e)[:120]}")

    ok = sum(1 for r in results if r['status'] == 'success')
    print(f"\n完成: {ok}/{len(results)} 成功")
    if args.report:
        Path(args.report).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"报告 -> {args.report}")
    return 0 if ok == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
