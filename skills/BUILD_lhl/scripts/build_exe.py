# -*- coding: utf-8 -*-
"""
build_exe.py — 把「工具端」打成免安装单文件 EXE（PyInstaller onefile + noconsole）

内置：static（前端）+ data（措施库 / 图片库 / 分部标准 / PPT 构建器）
运行：首启后在 EXE 同级生成可写 data 副本（_MEIPASS 只读，写库必须落到同级）

用法：
    python build_exe.py --root "D:/项目/精益建造/0分部分项划分" --out "D:/项目/精益建造/成果发布"
    python build_exe.py --root <工具端> --out <输出目录> --name 精益建造一体化工具 --hidden lean_import

前置：pip install pyinstaller flask openpyxl python-pptx pillow reportlab
      （reportlab 缺了 exe 启动即崩，见 references/pitfalls.md 第 19 条）

⚠️ 覆盖旧 EXE 前必须先关掉正在运行的程序，否则文件被占用写不进去。
"""
import argparse
import os
import subprocess
import sys

SEP = ';' if sys.platform.startswith('win') else ':'

HIDDEN = ['openpyxl', 'openpyxl.styles', 'openpyxl.chart',
          'openpyxl.worksheet.datavalidation',
          'reportlab', 'reportlab.pdfbase.ttfonts', 'reportlab.platypus',
          'pptx', 'pptx.oxml.ns',
          'PIL', 'PIL.Image',
          'tkinter', 'tkinter.filedialog',
          'werkzeug', 'jinja2']


def make_icon(root, text='精', color=(47, 85, 151)):
    """生成圆角蓝底白字图标（没有现成 .ico 时兜底）"""
    icon = os.path.join(root, 'app.ico')
    if os.path.exists(icon):
        return icon
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None
    size = 256
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 8, size - 8, size - 8], radius=52, fill=color + (255,))
    d.rounded_rectangle([8, 8, size - 8, 108], radius=52, fill=(58, 107, 189, 255))
    d.rectangle([8, 60, size - 8, 110], fill=(58, 107, 189, 255))
    font = None
    for p in (r'C:\Windows\Fonts\msyhbd.ttc', r'C:\Windows\Fonts\simhei.ttf'):
        if os.path.exists(p):
            try:
                font = ImageFont.truetype(p, 150)
                break
            except Exception:
                pass
    if font:
        box = d.textbbox((0, 0), text, font=font)
        d.text(((size - (box[2] - box[0])) / 2 - box[0],
                (size - (box[3] - box[1])) / 2 - box[1] + 6), text, font=font, fill='white')
    im.save(icon, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    return icon


def build(root, out_root, name, entry='launcher.py', hidden=(), icon_text='精'):
    root = os.path.abspath(root)
    out_root = os.path.abspath(out_root)
    os.makedirs(out_root, exist_ok=True)
    work = os.path.join(root, 'build_release')
    icon = make_icon(root, icon_text)

    cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
           '--onefile', '--noconsole',
           '--name', name,
           '--distpath', out_root,
           '--workpath', work,
           '--specpath', work,
           # 注意：--specpath 会让相对路径按 spec 目录解析，--add-data 必须用绝对路径
           '--add-data', f'{os.path.join(root, "static")}{SEP}static',
           '--add-data', f'{os.path.join(root, "data")}{SEP}data']
    for h in list(HIDDEN) + list(hidden):
        cmd += ['--hidden-import', h]
    if icon:
        cmd += ['--icon', icon]
    cmd.append(os.path.join(root, entry))

    print('>>>', ' '.join(cmd))
    subprocess.run(cmd, cwd=root, check=True)

    exe = os.path.join(out_root, name + ('.exe' if os.name == 'nt' else ''))
    if os.path.exists(exe):
        print(f'EXE: {exe}  {os.path.getsize(exe) / 1024 / 1024:.1f} MB')
    else:
        print('EXE 缺失：', exe)
    return exe


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True, help='工具端目录（含 app.py / launcher.py / static / data）')
    ap.add_argument('--out', required=True, help='EXE 输出目录（一般为 <板块根>/成果发布）')
    ap.add_argument('--name', default='精益建造一体化工具')
    ap.add_argument('--entry', default='launcher.py')
    ap.add_argument('--hidden', action='append', default=[], help='额外 hidden-import，可重复')
    ap.add_argument('--icon-text', default='精', help='自动生成图标时的字')
    a = ap.parse_args()
    build(a.root, a.out, a.name, a.entry, a.hidden, a.icon_text)
