# -*- coding: utf-8 -*-
r"""
Local OCR (RapidOCR) - offline after install
Usage:
    python ocr.py --selftest
    python ocr.py D:\scan\page1.png
    python ocr.py D:\scan\a.pdf D:\scan\b.jpg
    python ocr.py D:\scan\all --out result.txt
    python ocr.py D:\scan\a.pdf --box
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def ocr_image(img):
    """img: file path or numpy array (BGR). Returns list of (text, score, box)."""
    result, _ = get_engine()(img)
    items = []
    if result:
        for box, text, score in result:
            items.append((str(text).strip(), float(score), box))
    return items


def ocr_pdf(path, dpi=300, box=False):
    import fitz
    import numpy as np
    doc = fitz.open(path)
    lines = []
    total = doc.page_count
    for i, page in enumerate(doc, 1):
        print(f"    page {i}/{total}", flush=True)
        txt = page.get_text().strip()
        if len(txt) >= 20:
            lines.append(f"----- Page {i} (text layer) -----")
            lines.append(txt)
            continue
        pix = page.get_pixmap(dpi=dpi)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            arr = arr[:, :, :3]
        arr = arr[:, :, ::-1].copy()  # RGB -> BGR
        lines.append(f"----- Page {i} -----")
        for text, score, bx in ocr_image(arr):
            lines.append(f"[{score:.2f}] {text}" if box else text)
    doc.close()
    return lines


def ocr_file(path, dpi=300, box=False):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return ocr_pdf(path, dpi, box)
    lines = []
    for text, score, bx in ocr_image(path):
        lines.append(f"[{score:.2f}] {text}" if box else text)
    return lines


def selftest():
    from PIL import Image, ImageDraw, ImageFont
    tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_selftest.png")
    font = None
    for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"):
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 48)
                break
            except Exception:
                pass
    img = Image.new("RGB", (900, 200), "white")
    ImageDraw.Draw(img).text((40, 60), "OCR Test 2026", fill="black", font=font)
    img.save(tmp)

    print("[..] recognizing test image ...")
    items = ocr_image(tmp)
    text = " ".join(t for t, _, _ in items)
    print("    raw result:", text if text else "(empty)")
    os.remove(tmp)
    if "2026" not in text.replace(" ", ""):
        print("[FAIL] engine ran but text mismatch.")
        return 1
    print("[OK] engine works. Model is bundled, no internet needed from now on.")
    return 0


def main():
    args = [a for a in sys.argv[1:]]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if "--selftest" in args:
        return selftest()

    box = "--box" in args
    out = None
    if "--out" in args:
        idx = args.index("--out")
        if idx + 1 < len(args):
            out = args[idx + 1]
            del args[idx:idx + 2]
        args.remove("--out") if "--out" in args else None
    dpi = 300
    if "--dpi" in args:
        idx = args.index("--dpi")
        dpi = int(args[idx + 1])
        del args[idx:idx + 2]

    files = []
    for a in args:
        if os.path.isdir(a):
            for root, _, fs in os.walk(a):
                for f in fs:
                    if os.path.splitext(f)[1].lower() in IMAGE_EXT | {".pdf"}:
                        files.append(os.path.join(root, f))
        elif os.path.isfile(a):
            files.append(a)
    if not files:
        print("[ERROR] no file found.")
        return 1

    all_lines = []
    for f in files:
        print(f"[OCR] {f}")
        try:
            lines = ocr_file(f, dpi, box)
        except Exception as e:
            print(f"    failed: {e}")
            continue
        all_lines.extend(lines)
        if out is None:
            dst = os.path.splitext(f)[0] + ".ocr.txt"
            with open(dst, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
            print(f"    -> {dst}  ({len(lines)} lines)")
        else:
            print(f"    {len(lines)} lines")

    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("\n".join(all_lines))
        print(f"[DONE] -> {out}  (total {len(all_lines)} lines)")
    else:
        print(f"[DONE] {len(files)} file(s) processed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
