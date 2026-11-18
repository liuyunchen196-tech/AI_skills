# -*- coding: utf-8 -*-
"""给成品 PPT 批量写演讲者备注。

用法: python add_notes.py 成品.pptx notes.json
notes.json: {"1": "开场讲法...", "2": "..."}  键为页码（1 起）。
每页写「怎么讲」（节奏、强调点、衔接），不要重复正文文字。
"""
import json
import sys

from pptx import Presentation

pptx_path = sys.argv[1]
notes_path = sys.argv[2]
with open(notes_path, encoding="utf-8") as f:
    NOTES = json.load(f)

prs = Presentation(pptx_path)
total = len(prs.slides._sldIdLst)
written = 0
for i, slide in enumerate(prs.slides, 1):
    note = NOTES.get(str(i))
    if not note:
        continue
    slide.notes_slide.notes_text_frame.text = note
    written += 1
prs.save(pptx_path)
print(f"notes written: {written}/{total} slides")
