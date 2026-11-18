# -*- coding: utf-8 -*-
"""
jituan-PPT 图片提取器
从任意 PPT/PPTX 中提取所有图片到指定目录，用于为 build.py 准备素材。

用法:
    python extract_media.py <源.pptx> [--out 输出目录] [--page 仅提取第N页(1-based, 可多次)] [--info]

说明:
    - 默认提取全部页的图片，按 页码_图片编号_尺寸 命名
    - --page 3 只提取第 3 页的图片
    - --info 只打印清单不解出文件
"""
import sys, os, io, argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pptx import Presentation
from pptx.util import Emu

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", default="extracted_media")
    ap.add_argument("--page", type=int, action="append", default=None,
                    help="只提取指定页码(1-based)，可多次传")
    ap.add_argument("--info", action="store_true", help="只列清单")
    args = ap.parse_args()

    prs = Presentation(args.src)
    pages = set(args.page) if args.page else None
    os.makedirs(args.out, exist_ok=True)
    count = 0
    for i, slide in enumerate(prs.slides, 1):
        if pages and i not in pages:
            continue
        pic_no = 0
        for sh in slide.shapes:
            if sh.shape_type == 13:  # PICTURE
                pic_no += 1
                try:
                    img = sh.image
                    ext = img.ext
                    if ext not in ("png", "jpeg", "jpg", "gif", "bmp", "tiff"):
                        ext = "png"
                    w_in = Emu(sh.width).inches if sh.width else "?"
                    h_in = Emu(sh.height).inches if sh.height else "?"
                    name = f"p{i:02d}_img{pic_no}_{w_in}x{h_in}in.{ext}"
                    if not args.info:
                        with open(os.path.join(args.out, name), "wb") as f:
                            f.write(img.blob)
                    print(f"第{i}页 [{pic_no}] {name} ({len(img.blob)} bytes)")
                    count += 1
                except Exception as e:
                    print(f"第{i}页 [{pic_no}] 提取失败: {e}")
    print(f"共提取 {count} 张图片 -> {args.out}")

if __name__ == "__main__":
    main()
