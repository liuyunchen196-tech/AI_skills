# -*- coding: utf-8 -*-
"""add_columns.py — 给现有项目加栏目（BUILD_lhl）

只做 ADD COLUMN + 回填，绝不 DROP、不重建表、不改既有列名。

用法:
  # 给单个项目加「信息词条」并从 lean_measures.json 回填
  python add_columns.py --project "D:/.../红色项目" --lib "D:/.../data/lean_measures.json" \
      --col "信息词条:TEXT" --fill

  # 给两个项目一起加（自动探测 红色项目 / 蓝色项目）
  python add_columns.py --workspace "D:/萧山项目/实施/精益建造" --col "信息词条:TEXT" --fill

  # 只看会做什么
  python add_columns.py --project ... --col "信息词条:TEXT" --fill --dry-run
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import time

MAIN_DB = ('主数据库.db', '优化措施')
IMG_DB = ('图片信息数据库.db', '图片信息')


def cols(con, table):
    return [r[1] for r in con.execute('PRAGMA table_info("%s")' % table)]


def add_col(con, table, name, typ, dry):
    if name in cols(con, table):
        return False
    if not dry:
        con.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (table, name, typ))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', action='append', default=[])
    ap.add_argument('--workspace', help='板块根目录，自动探测 红色项目/蓝色项目')
    ap.add_argument('--lib', help='lean_measures.json，用于回填')
    ap.add_argument('--col', action='append', required=True, help='列名:TYPE，如 信息词条:TEXT')
    ap.add_argument('--fill', action='store_true', help='从 lib 回填')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    projects = list(a.project)
    if a.workspace:
        for d in ('红色项目', '蓝色项目'):
            p = os.path.join(a.workspace, d)
            if os.path.isdir(p):
                projects.append(p)
    if not projects:
        print('未指定项目（--project 或 --workspace）')
        sys.exit(2)

    lib = {}
    if a.fill:
        path = a.lib or next((os.path.join(p, '..', '0分部分项划分', 'data', 'lean_measures.json')
                              for p in projects
                              if os.path.exists(os.path.join(p, '..', '0分部分项划分', 'data', 'lean_measures.json'))), None)
        if not path or not os.path.exists(path):
            print('找不到 lean_measures.json，请用 --lib 指定')
            sys.exit(2)
        for r in json.load(open(os.path.abspath(path), encoding='utf-8')):
            lib[r['优化措施名称']] = r
        print('回填源: %s（%d 条）' % (os.path.abspath(path), len(lib)))

    want = []
    for c in a.col:
        name, _, typ = c.partition(':')
        want.append((name.strip(), (typ or 'TEXT').strip().upper()))

    for proj in projects:
        print('\n=== %s' % proj)
        for fname, table in (MAIN_DB, IMG_DB):
            db = os.path.join(proj, fname)
            if not os.path.exists(db):
                print('  跳过（无 %s）' % fname)
                continue
            if not a.dry_run:
                bak = db + '.%s.bak' % time.strftime('%Y%m%d%H%M%S')
                shutil.copy(db, bak)
            con = sqlite3.connect(db)
            added = []
            for name, typ in want:
                if add_col(con, table, name, typ, a.dry_run):
                    added.append(name)
            n = con.execute('select count(*) from "%s"' % table).fetchone()[0]
            filled = 0
            if a.fill:
                key = '优化措施名称' if table == MAIN_DB[1] else '所属措施'
                sample = next(iter(lib.values())) if lib else {}
                for name, _ in want:
                    if name not in sample:
                        print('    ! lib 中无字段「%s」，跳过回填' % name)
                        continue
                    rows = con.execute('select rowid, "%s" from "%s"' % (key, table)).fetchall()
                    for rid, k in rows:
                        rec = lib.get(k)
                        if not rec:
                            continue
                        v = rec.get(name)
                        if v in (None, ''):
                            continue
                        if not a.dry_run:
                            con.execute('update "%s" set "%s"=? where rowid=?' % (table, name),
                                        (v if not isinstance(v, list) else ';'.join(v), rid))
                        filled += 1
            if not a.dry_run:
                con.commit()
            con.close()
            print('  %s[%s] 行 %d | 新增列 %s | 回填 %d 处' % (fname, table, n, added or '无', filled))

    print('\n%s' % ('演练模式，未改动任何文件' if a.dry_run else '完成。请重出成果并跑 validate.py'))


if __name__ == '__main__':
    main()
