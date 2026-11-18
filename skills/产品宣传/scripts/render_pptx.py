# -*- coding: utf-8 -*-
"""把 pptx 逐页导出 PNG（PowerPoint COM），用于渲染复核。

用法: python render_pptx.py xx.pptx out_dir [宽]
"""
import os
import sys

import win32com.client as win32

src = os.path.abspath(sys.argv[1])
out = os.path.abspath(sys.argv[2])
width = int(sys.argv[3]) if len(sys.argv) > 3 else 1600
os.makedirs(out, exist_ok=True)

app = win32.DispatchEx('PowerPoint.Application')
app.Visible = 1
pres = app.Presentations.Open(src, WithWindow=False)
h = int(width * pres.PageSetup.SlideHeight / pres.PageSetup.SlideWidth)
pres.Export(out, 'PNG', width, h)
n = pres.Slides.Count
pres.Close()
app.Quit()
print('rendered', n, 'slides ->', out, f'{width}x{h}')
