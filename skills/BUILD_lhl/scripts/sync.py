# -*- coding: utf-8 -*-
"""sync.py — 把主数据同步到项目端（BUILD_lhl）

一次同步四处：主数据库.db / 图片信息数据库.db / 图片库/ / 表格提炼.md
主数据（lean_measures.json）是唯一真相源；项目端是派生产物，可随时重建。

用法:
  python sync.py --workspace "D:/萧山项目/实施/精益建造"
  python sync.py --workspace ... --projects 红色项目,蓝色项目 --dry-run
"""
import argparse
import json
import os
import re
import shutil
import sqlite3

SCHEMA_MAIN = '''CREATE TABLE 优化措施(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    章节 TEXT, 优化类型 TEXT, 手册分类 TEXT,
    分部工程 TEXT, 子分部工程 TEXT, 分项工程 TEXT,
    优化措施名称 TEXT, 优化内容 TEXT, 优化效果 TEXT,
    适用部位 TEXT, 适用楼层 TEXT, 实体案例 TEXT,
    信息词条 TEXT, 表号 TEXT, 图片来源页 TEXT
);'''
SCHEMA_IMG = '''CREATE TABLE 图片信息(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    图片名称 TEXT, 图片位置 TEXT,
    所属措施 TEXT, 优化类型 TEXT, 分部工程 TEXT,
    信息词条 TEXT, 表号 TEXT, 来源页码 INTEGER
);'''


def floor_of(part, up, down, height):
    """按项目层数把适用部位换算成楼层表述。"""
    p = part or ''
    if any(k in p for k in ('地下', '基础', '底板')):
        return '地下 1~%d 层' % down if down else '地下各层'
    if any(k in p for k in ('屋面', '外墙', '外立面', '女儿墙')):
        return '全楼层（含屋面）'
    if any(k in p for k in ('首层', '一层', '大堂')):
        return '首层'
    if any(k in p for k in ('标准层', '楼层', '全楼层', '室内', '户内')):
        return '2~%d 层' % up if up else '标准层'
    return '全楼层'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--lib', default='')
    ap.add_argument('--img', default='')
    ap.add_argument('--projects', default='红色项目,蓝色项目')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    ws = a.workspace
    lib_p = a.lib or os.path.join(ws, '0分部分项划分', 'data', 'lean_measures.json')
    img_p = a.img or os.path.join(ws, '0分部分项划分', 'data', '图片库')
    rows = json.load(open(lib_p, encoding='utf-8'))
    print('数据源 %d 条 / 图片 %d 张' % (len(rows), len(os.listdir(img_p))))

    for pj in [x.strip() for x in a.projects.split(',') if x.strip()]:
        pdir = os.path.join(ws, pj)
        if not os.path.isdir(pdir):
            print('跳过（不存在）%s' % pj)
            continue
        info = {}
        f = os.path.join(pdir, '项目信息.json')
        if os.path.exists(f):
            info = json.load(open(f, encoding='utf-8'))
        up = int(info.get('地上层数') or 0)
        down = int(info.get('地下层数') or 0)
        height = info.get('单层层高') or ''

        if a.dry_run:
            print('[dry] %s: 将写入 %d 条 + 图片 %d 张' % (pj, len(rows), len(rows) and
                                                    sum(len(r.get('图片') or []) for r in rows)))
            continue

        # 图片库
        dst = os.path.join(pdir, '图片库')
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        os.makedirs(dst)
        for r in rows:
            for n in (r.get('图片') or []):
                s = os.path.join(img_p, n)
                if os.path.exists(s):
                    shutil.copy(s, os.path.join(dst, n))

        # 数据库
        for dbf, schema in ((os.path.join(pdir, '主数据库.db'), SCHEMA_MAIN),
                            (os.path.join(pdir, '图片信息数据库.db'), SCHEMA_IMG)):
            if os.path.exists(dbf):
                os.remove(dbf)
            con = sqlite3.connect(dbf)
            con.executescript(schema)
            if '优化措施' in schema:
                for r in rows:
                    imgs = r.get('图片') or []
                    con.execute('INSERT INTO 优化措施(章节,优化类型,手册分类,分部工程,子分部工程,分项工程,'
                                '优化措施名称,优化内容,优化效果,适用部位,适用楼层,实体案例,信息词条,表号,图片来源页)'
                                ' VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                (r.get('章节', ''), r.get('优化类型', ''), r.get('手册分类', ''),
                                 r.get('分部工程', ''), r.get('子分部工程', ''), r.get('分项工程', ''),
                                 r.get('优化措施名称', ''), r.get('优化内容', ''), r.get('优化效果', ''),
                                 r.get('适用部位', ''), floor_of(r.get('适用部位'), up, down, height),
                                 ';'.join('图片库/' + n for n in imgs), r.get('信息词条', ''),
                                 r.get('来源表', ''), str(r.get('来源页', ''))))
            else:
                for r in rows:
                    for n in (r.get('图片') or []):
                        con.execute('INSERT INTO 图片信息(图片名称,图片位置,所属措施,优化类型,分部工程,'
                                    '信息词条,表号,来源页码) VALUES(?,?,?,?,?,?,?,?)',
                                    (n, '图片库/' + n, r.get('优化措施名称', ''), r.get('优化类型', ''),
                                     r.get('分部工程', ''), r.get('信息词条', ''),
                                     r.get('来源表', ''), int(r.get('来源页') or 0) if str(r.get('来源页', '')).isdigit() else 0))
            con.commit()
            n = con.execute('select count(*) from "%s"' % ('优化措施' if '优化措施' in schema else '图片信息')).fetchone()[0]
            con.close()
            print('  %s %-16s %d 行' % (pj, os.path.basename(dbf), n))

        # 表格提炼.md
        md = os.path.join(pdir, '表格提炼.md')
        with open(md, 'w', encoding='utf-8') as fh:
            fh.write('# 措施提炼表\n\n共 %d 条 / 图片 %d 张\n\n' %
                     (len(rows), sum(len(r.get('图片') or []) for r in rows)))
            for ch in dict.fromkeys(r.get('章节', '') for r in rows):
                fh.write('\n## %s\n\n| # | 措施 | 优化类型 | 分部分项 | 图片 | 信息词条 |\n|---|---|---|---|---|---|\n' % ch)
                for r in rows:
                    if r.get('章节') != ch:
                        continue
                    fh.write('| %s | %s | %s | %s/%s/%s | %d | %s |\n' % (
                        r.get('id'), r.get('优化措施名称'), r.get('优化类型'), r.get('分部工程'),
                        r.get('子分部工程'), r.get('分项工程'), len(r.get('图片') or []),
                        r.get('信息词条', '')))
        print('  %s 表格提炼.md 已更新' % pj)

    print('\n完成%s' % ('（演练）' if a.dry_run else '。请重出 PDF / PPT / 统计表'))


if __name__ == '__main__':
    main()
