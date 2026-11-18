# -*- coding: utf-8 -*-
"""extract_cards.py — 卡片式版式提取（BUILD_lhl）

适用于：横版幻灯片式图册，每页 N 张卡片，卡内有固定小标签 + 图片区。
核心：**先按 x 分栏，再按 y 切段**，否则左右栏会串卡。

用法:
  python extract_cards.py --pdf 素材/优化工艺.pdf --split-x 480 \
      --label-map "实施效果=优化效果;工艺要点=优化内容;实体案例=图片" \
      --out _tmp/recs.json --img-dir _tmp/img --dpi 200

  # 标签按原样映射（手册字段与库字段同名时）
  python extract_cards.py --pdf x.pdf --split-x 480 --out recs.json

输出 recs.json:
  [{"title","优化内容","优化效果","files":[...],"page","side","raw":{标签:文本}}]
"""
import argparse
import json
import os
import re

import pymupdf as fitz

DEFAULT_LABELS = ('实施效果', '工艺要点', '实体案例', '实例案例', '实际案例')


def norm(s):
    s = (s or '').replace('\u3000', ' ').replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def join_lines(lines):
    """中文断行合并：行首序号或行尾标点直接相接，数字/字母间补空格。"""
    out = ''
    for ln in lines:
        t = norm(ln)
        if not t:
            continue
        if not out:
            out = t
            continue
        if re.match(r'^[\d①-⑳一二三四五六七八九十]+[、.．)）]', t):
            out += ' ' + t
        elif re.search(r'[，。；：、,.;:）)]$', out):
            out += t
        elif re.search(r'[A-Za-z0-9%]$', out) and re.match(r'^[A-Za-z0-9（(]', t):
            out += ' ' + t
        else:
            out += t
    out = re.sub(r'(\d)\s+([、.．])', r'\1\2', out)
    return out


def spans_of(page):
    res = []
    for b in page.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            for s in l['spans']:
                if s['text'].strip():
                    res.append({'text': s['text'], 'bbox': s['bbox'], 'size': s['size']})
    return res


def parse_map(s):
    m = {}
    for part in (s or '').split(';'):
        if '=' in part:
            k, v = part.split('=', 1)
            m[k.strip()] = v.strip()
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--split-x', type=float, default=0, help='左右栏分界 x；0=按页宽一半')
    ap.add_argument('--header-y', type=float, default=40, help='页眉底线')
    ap.add_argument('--labels', default=','.join(DEFAULT_LABELS))
    ap.add_argument('--label-map', default='', help='标签=库字段;标签=库字段;标签=图片')
    ap.add_argument('--out', default='recs.json')
    ap.add_argument('--img-dir', default='')
    ap.add_argument('--dpi', type=int, default=200)
    ap.add_argument('--min-w', type=float, default=50, help='内容图最小宽（滤图标）')
    ap.add_argument('--min-h', type=float, default=60)
    a = ap.parse_args()

    labels = [x.strip() for x in a.labels.split(',') if x.strip()]
    fmap = parse_map(a.label_map)
    img_dir = a.img_dir or os.path.join(os.path.dirname(os.path.abspath(a.out)), 'img')
    os.makedirs(img_dir, exist_ok=True)

    doc = fitz.open(a.pdf)
    recs = []
    for pi in range(doc.page_count):
        page = doc[pi]
        split = a.split_x or page.rect.width / 2
        sp = spans_of(page)
        tags = []
        for s in sp:
            t = norm(s['text'])
            core = re.sub(r'^[♦◆◊\s]+', '', t)
            if s['bbox'][1] <= a.header_y:
                continue
            for lb in labels:
                if core.startswith(lb):
                    tags.append({'y': s['bbox'][1], 'x': s['bbox'][0], 'kind': core})
                    break
        if not tags:
            continue
        imgs = [im for im in page.get_image_info(xrefs=True)
                if im['bbox'][1] > a.header_y * 2.5
                and (im['bbox'][2] - im['bbox'][0]) > a.min_w
                and (im['bbox'][3] - im['bbox'][1]) > a.min_h]
        for side, (x0, x1) in (('L', (0, split)), ('R', (split, 1e9))):
            ts = sorted([t for t in tags if x0 <= t['x'] < x1], key=lambda t: t['y'])
            if not ts:
                continue
            top = ts[0]['y']
            head = [s for s in sp if x0 <= s['bbox'][0] < x1
                    and a.header_y < s['bbox'][1] < top - 1
                    and not any(norm(s['text']).startswith(lb) for lb in labels)]
            head.sort(key=lambda s: (round(s['bbox'][1]), s['bbox'][0]))
            title = join_lines([s['text'] for s in head]).strip()
            if len(re.sub(r'\s+', '', title)) < 4:
                continue
            rec = {'title': title, 'page': pi + 1, 'side': side, 'raw': {},
                   '优化内容': '', '优化效果': '', 'files': []}
            for i, t in enumerate(ts):
                y_end = ts[i + 1]['y'] if i + 1 < len(ts) else 1e9
                body = [s for s in sp if x0 <= s['bbox'][0] < x1
                        and t['y'] + 8 <= s['bbox'][1] < y_end - 1]
                body.sort(key=lambda s: (round(s['bbox'][1]), s['bbox'][0]))
                txt = re.sub(r'^[♦◆◊\s]+', '', join_lines([s['text'] for s in body]))
                rec['raw'][t['kind']] = txt
                dst = fmap.get(t['kind'])
                if dst and dst != '图片':
                    rec[dst] = txt
            if not fmap:
                keys = [t['kind'] for t in ts]
                if len(keys) >= 2:
                    rec['优化内容'], rec['优化效果'] = rec['raw'].get(keys[0], ''), rec['raw'].get(keys[1], '')
            # 图片：最后一个含「案例」的标签之后
            ytop = next((t['y'] - 4 for t in ts if '案例' in t['kind']), 1e9)
            mine = [im for im in imgs if x0 <= im['bbox'][0] < x1]
            tail = [im for im in mine if im['bbox'][1] >= ytop]
            chosen = tail or mine
            chosen.sort(key=lambda im: (round(im['bbox'][1] / 12), im['bbox'][0]))
            for j, im in enumerate(chosen, 1):
                fn = 'c_%03d_%d.png' % (len(recs) + 1, j)
                page.get_pixmap(clip=fitz.Rect(*im['bbox']), dpi=a.dpi).save(os.path.join(img_dir, fn))
                rec['files'].append(fn)
                rec.setdefault('bboxes', []).append([round(v, 1) for v in im['bbox']])
            recs.append(rec)

    json.dump(recs, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('卡片 %d 张 / 图片 %d 张 -> %s' % (len(recs), sum(len(r['files']) for r in recs), a.out))
    miss = [r['title'] for r in recs if not r.get('优化内容') or not r.get('优化效果')]
    if miss:
        print('!! 字段为空 %d 条（检查 --label-map）: %s' % (len(miss), miss[:5]))
    for r in recs[:3]:
        print('  -', r['title'], '| 效果', len(r['优化效果']), '字 | 图', len(r['files']))


if __name__ == '__main__':
    main()
