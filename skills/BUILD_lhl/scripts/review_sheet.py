# -*- coding: utf-8 -*-
"""
review_sheet.py — 输出「按分部分项 + 适用部位排序」的核对表（含合并明细）

为什么要有这张表：查重算法只能筛候选，是否真重复必须人眼逐组看原文。
把全库排好序、合并痕迹标在行末，一次性过一遍比在 CSV 里翻快得多。

输出：
  Sheet1 措施清单：分部 → 子分部 → 分项 → 适用部位 排序，标注图片数、词条、合并说明
  Sheet2 合并明细：每条被合并的措施 → 并入哪条、原名称、原字数/图数

用法：
    python review_sheet.py --lib <lib.json> \
        --prededupe <lib.prededupe.json> --decisions merge_decisions.json \
        --out "D:/项目/精益建造措施_按分部分项排序.xlsx"

  --prededupe / --decisions 可省：只出 Sheet1 清单。
"""
import argparse
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUT = ''
PRE = ''
DEC = ''
LIB = ''

DIV_ORDER = ['地基与基础', '主体结构', '建筑装饰装修', '屋面', '建筑给水排水及供暖',
             '通风与空调', '建筑电气', '智能建筑', '建筑节能', '电梯', '措施项目', '室外工程']
POS_ORDER = ['基础', '地下室', '首层', '标准层', '全楼层', '室内', '外墙', '外立面',
             '屋面', '管道井', '电梯井', '机房', '室外', '全场', '加工场']

HEAD_FILL = PatternFill('solid', fgColor='2F5597')
HEAD_FONT = Font(name='微软雅黑', size=10, bold=True, color='FFFFFF')
BODY_FONT = Font(name='微软雅黑', size=9)
THIN = Side(style='thin', color='D9D9D9')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def pos_rank(rec):
    parts = [p.strip() for p in (rec.get('适用部位') or '').split('、') if p.strip()]
    ranks = [POS_ORDER.index(p) if p in POS_ORDER else 99 for p in parts] or [99]
    return min(ranks), rec.get('适用部位') or ''


def norm_div(name):
    return str(name or '').split('（')[0].strip()


def div_rank(rec):
    d = norm_div(rec['分部工程'])
    return DIV_ORDER.index(d) if d in DIV_ORDER else 98


def sheet_table(ws, headers, widths, rows, title=None):
    r0 = 1
    if title:
        ws.cell(1, 1, title).font = Font(name='微软雅黑', size=12, bold=True, color='2F5597')
        r0 = 3
    for c, h in enumerate(headers, 1):
        cell = ws.cell(r0, c, h)
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(c)].width = widths[c - 1]
    ws.row_dimensions[r0].height = 26
    for i, row in enumerate(rows, r0 + 1):
        for c, v in enumerate(row, 1):
            cell = ws.cell(i, c, v)
            cell.font = BODY_FONT
            cell.border = BORDER
            cell.alignment = Alignment(vertical='top', wrap_text=(c in (4, 5, 6, 7, 8)))
    ws.freeze_panes = ws.cell(r0 + 1, 1)


def main():
    with open(LIB, 'r', encoding='utf-8') as f:
        rows = json.load(f)
    rows.sort(key=lambda r: (div_rank(r), r['子分部工程'], r['分项工程']) + pos_rank(r))

    wb = Workbook()
    ws = wb.active
    ws.title = '措施清单'
    data = []
    for i, r in enumerate(rows, 1):
        note = ''
        if r.get('别名'):
            note = '已并入：' + '、'.join(r['别名'])
        data.append([i, r['id'], norm_div(r['分部工程']), r['子分部工程'], r['分项工程'],
                     r.get('适用部位') or '', r['优化措施名称'], r.get('优化内容') or '',
                     r.get('优化效果') or '', len(r.get('图片') or []),
                     r.get('信息词条') or '', note])
    sheet_table(ws, ['序号', '库内编号', '分部工程', '子分部工程', '分项工程', '适用部位', '优化措施名称',
                     '优化内容（做法）', '优化效果', '图片数', '信息词条', '合并说明'],
                [6, 8, 16, 16, 18, 14, 26, 62, 40, 7, 30, 26], data,
                title=f'精益建造措施清单（按分部分项 + 适用部位排序，共 {len(rows)} 条）')

    # 合并明细（没有 prededupe / decisions 时跳过）
    if not (PRE and DEC and os.path.isfile(PRE) and os.path.isfile(DEC)):
        wb.save(OUT)
        print('输出：', OUT, f'（措施 {len(rows)} 条，无合并明细）')
        return
    ws2 = wb.create_sheet('合并明细')
    pre = {r['id']: r for r in json.load(open(PRE, encoding='utf-8'))}
    dec = json.load(open(DEC, encoding='utf-8'))
    detail = []
    for k, g in enumerate(dec, 1):
        kp = next((r for r in rows if r['优化措施名称'] == pre[g['keep']]['优化措施名称']), None)
        keep_name = pre[g['keep']]['优化措施名称']
        keep_id = kp['id'] if kp else ''
        for did in g['drop']:
            r = pre[did]
            detail.append([k, keep_id, keep_name, r['优化措施名称'],
                           f"{r['分部工程']}/{r['分项工程']}", r.get('适用部位') or '',
                           len(r.get('优化内容') or ''), len(r.get('图片') or []),
                           '保留内容更完整的一条，图片全部并入'])
    sheet_table(ws2, ['组号', '保留编号', '保留措施', '被合并措施', '分部分项', '适用部位',
                      '原文字数', '原图片数', '处理方式'],
                [6, 9, 34, 34, 26, 14, 9, 9, 30], detail,
                title=f'重复措施合并明细（共 {len(dec)} 组 / {len(detail)} 条被合并）')

    wb.save(OUT)
    print('输出：', OUT)
    print(f'措施 {len(rows)} 条，合并 {len(dec)} 组 / 删除 {len(detail)} 条')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--lib', required=True, help='当前 lean_measures.json')
    ap.add_argument('--prededupe', default='', help='合并前的备份 <lib>.prededupe.json（出合并明细用）')
    ap.add_argument('--decisions', default='', help='人工确认的合并清单 decisions.json')
    ap.add_argument('--out', default='', help='输出 xlsx 路径')
    a = ap.parse_args()

    LIB = os.path.abspath(a.lib)
    PRE = os.path.abspath(a.prededupe) if a.prededupe else ''
    DEC = os.path.abspath(a.decisions) if a.decisions else ''
    OUT = os.path.abspath(a.out or os.path.join(os.path.dirname(LIB), '..', '精益建造措施_按分部分项排序.xlsx'))
    main()
