#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check.py —— 流程图设计助手的部署闸门 + 样例回归 + 变异反证

三层：
  L1 部署闸门：SKILL.md/skillhub-meta.json 版本一致、头像规格、目录层级、
               零中文名、无 __pycache__、零 CDN、必需文件齐全
  L2 样例回归：examples/ 全量走 validate → deliver → check 三链路，必须全 EXIT 0
  L3 变异反证：注入坏 IR 必须被校验器抓住（EXIT 1 且汇总 ERROR > 0）；
               合法但省略 type 的 IR 必须放行（防"过度严格"误报）

用法：python scripts/check.py [技能目录]
退出码：0 = 全部通过；1 = 有失败项
"""

import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(HERE)
DIAGRAM = os.path.join(HERE, "diagram.py")

failed = []


def ok(msg):
    print("  [OK]   " + msg)


def bad(msg):
    print("  [FAIL] " + msg)
    failed.append(msg)


def section(title):
    print("")
    print("── " + title + " " + "─" * max(0, 50 - len(title)))


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------ L1 闸门
section("L1 部署闸门")

skill_md = os.path.join(ROOT, "SKILL.md")
if not os.path.isfile(skill_md):
    print("  [FAIL] 找不到 SKILL.md")
    sys.exit(1)

fm = read(skill_md)
m = re.search(r'^version:\s*["\']?([^"\'\s]+)', fm, re.M)
skill_ver = m.group(1) if m else None
if skill_ver:
    ok("SKILL.md version = " + skill_ver)
else:
    bad("SKILL.md 缺 version 字段")

name_m = re.search(r'^name:\s*["\']?([^"\'\s]+)', fm, re.M)
disp_m = re.search(r'^display_name:\s*["\']?([^"\'\n]+)', fm, re.M)
if disp_m:
    ok("display_name = " + disp_m.group(1).strip())
else:
    bad("SKILL.md 缺 display_name")

# 中文描述：技能的 description_zh 不受 100 字限制（那是专家 displayDescription 的口径；
# 课件/工具类技能的 description 普遍较长），这里只要求存在且非空。
for key in ("description_zh",):
    dm = re.search(r'^%s:\s*"(.*)"\s*$' % key, fm, re.M)
    if dm and dm.group(1).strip():
        ok("%s 存在（%d 字，技能形态不限长）" % (key, len(dm.group(1))))
    else:
        bad("SKILL.md 缺 %s" % key)

# skillhub-meta.json 版本对齐（提审档案）。
# 安装态副本（~/.workbuddy/skills/）里同一份信息叫 _skillhub_meta.json，两种命名都认，
# 但版本对齐与 examples=3 的要求不打折——本地详情页与提审档案必须同版本。
meta_path = None
for cand in ("skillhub-meta.json", "_skillhub_meta.json"):
    p = os.path.join(ROOT, cand)
    if os.path.isfile(p):
        meta_path = p
        break
if meta_path:
    meta_name = os.path.basename(meta_path)
    try:
        meta = json.loads(read(meta_path))
        mv = meta.get("version")
        if mv == skill_ver:
            ok("%s version 对齐（%s）" % (meta_name, mv))
        else:
            bad("%s version=%s != SKILL.md %s" % (meta_name, mv, skill_ver))
        ex = meta.get("examples_zh") or []
        if len(ex) == 3:
            ok("examples_zh = 3 条")
        else:
            bad("examples_zh 应为 3 条，当前 %d" % len(ex))
    except Exception as e:
        bad("%s 解析失败: %s" % (meta_name, e))
else:
    bad("缺 skillhub-meta.json（提审档案；安装态副本为 _skillhub_meta.json）")

# 必需文件
required = [
    "SKILL.md", "README.md",
    "scripts/diagram.py", "scripts/ir_schema.py", "scripts/geometry.py",
    "scripts/composition.py", "scripts/styles.py", "scripts/icons.py",
    "scripts/render_engine.py", "scripts/mermaid2ir.py",
    "templates/viewer.html",
]
miss = [p for p in required if not os.path.isfile(os.path.join(ROOT, p))]
if miss:
    bad("缺必需文件: " + "、".join(miss))
else:
    ok("必需文件齐全（%d 项）" % len(required))

# 头像
av = os.path.join(ROOT, "avatars", "skill.png")
if os.path.isfile(av):
    size = os.path.getsize(av)
    with open(av, "rb") as f:
        head = f.read(24)
    is_png = head[12:16] == b"IHDR"
    w = int.from_bytes(head[16:20], "big")
    h = int.from_bytes(head[20:24], "big")
    kb = size // 1024
    if is_png and w == 512 and h == 512 and kb < 500:
        ok("头像 512x512 %dKB" % kb)
    else:
        bad("头像不合规: %s %dx%d %dKB" % ("PNG" if is_png else "非PNG", w, h, kb))
else:
    bad("缺 avatars/skill.png")

# 目录层级：包根下最多 3 层目录
deep = []
for dp, dn, fn in os.walk(ROOT):
    rel = os.path.relpath(dp, ROOT)
    if rel != "." and rel.count(os.sep) + 1 >= 4:
        deep.append(rel)
if deep:
    bad("目录超过 3 层: " + "、".join(deep[:3]))
else:
    ok("目录层级 <= 3（包根下）")

# 中文名 / __pycache__ / CDN
cn = []
pyc = []
cdn = []
for dp, dn, fn in os.walk(ROOT):
    for d in dn:
        if re.search(u"[\u4e00-\u9fff]", d):
            cn.append(os.path.relpath(os.path.join(dp, d), ROOT))
        if d == "__pycache__":
            pyc.append(os.path.relpath(os.path.join(dp, d), ROOT))
    for f in fn:
        if re.search(u"[\u4e00-\u9fff]", f):
            cn.append(os.path.relpath(os.path.join(dp, f), ROOT))
        if not re.search(r"\.(html|js|mjs|md|json|py)$", f):
            continue
        try:
            txt = read(os.path.join(dp, f))
        except Exception:
            continue
        hits = re.findall(r"https?://(cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com)", txt)
        if hits:
            cdn.append(os.path.relpath(os.path.join(dp, f), ROOT))

if cn:
    bad("包内中文名: " + "、".join(cn[:3]))
else:
    ok("零中文文件名 / 目录名")
if pyc:
    bad("包内含 __pycache__: " + "、".join(pyc[:3]))
else:
    ok("无 __pycache__")
if cdn:
    bad("引用外部 CDN: " + "、".join(cdn[:3]))
else:
    ok("零外部 CDN 引用")

# 引擎零第三方依赖（红线：纯 stdlib）
third_party = re.findall(r"^\s*(?:import|from)\s+(?!os|sys|re|json|math|html|io|copy|hashlib|argparse|collections|itertools|textwrap|dataclasses|typing|__future__)\w+",
                         read(os.path.join(ROOT, "scripts", "ir_schema.py")))
if third_party:
    bad("ir_schema.py 出现非 stdlib import: " + str(third_party[:3]))
else:
    ok("引擎仅依赖 Python stdlib")

# ------------------------------------------------------------------ L2 样例回归
section("L2 样例回归（validate → deliver → check）")

examples = sorted(
    os.path.join(ROOT, "examples", f)
    for f in os.listdir(os.path.join(ROOT, "examples"))
    if f.endswith(".json")
)
if not examples:
    bad("examples/ 为空，无法回归")
else:
    tmp = tempfile.mkdtemp(prefix="dgd-check-")
    for src in examples:
        base = os.path.splitext(os.path.basename(src))[0]
        html = os.path.join(tmp, base + ".html")
        steps = []
        for cmd in (["validate", src], ["deliver", src, html], ["check", html]):
            r = subprocess.run([sys.executable, DIAGRAM] + cmd,
                               capture_output=True, encoding="utf-8")
            steps.append(r.returncode)
        if all(s == 0 for s in steps):
            ok("%s  v=%d d=%d c=%d" % (base, steps[0], steps[1], steps[2]))
        else:
            bad("%s  三链路退出码 %s（应全为 0）" % (base, steps))

# ------------------------------------------------------------------ L3 变异反证
section("L3 变异反证（抓不住即审计失效）")

tmp = tempfile.mkdtemp(prefix="dgd-mut-")


def write_ir(name, obj):
    p = os.path.join(tmp, name)
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return p


def run_validate(path):
    r = subprocess.run([sys.executable, DIAGRAM, "validate", path],
                       capture_output=True, encoding="utf-8")
    err_n = 0
    m = re.search(r"ERROR (\d+) · WARNING (\d+)", r.stdout)
    if m:
        err_n = int(m.group(1))
    return r.returncode, err_n, r.stdout


# 坏 IR：必须 EXIT 1 且汇总 ERROR > 0
MUTANTS = [
    ("mutant-unknown-diagram-type", "diagram_type 填非法值",
     {"diagram_type": "not-a-real-type", "nodes": [{"id": "a", "label": "节点甲"}], "edges": []}),
    ("mutant-duplicate-id", "两个节点同一 id",
     {"diagram_type": "architecture",
      "nodes": [{"id": "a", "label": "节点甲"}, {"id": "a", "label": "节点乙"}], "edges": []}),
    ("mutant-dangling-edge", "edge 指向不存在的节点",
     {"diagram_type": "architecture", "nodes": [{"id": "a", "label": "节点甲"}],
      "edges": [{"source": "a", "target": "ghost"}]}),
    ("mutant-unknown-node-type", "显式写非法 type",
     {"diagram_type": "architecture",
      "nodes": [{"id": "a", "label": "节点甲", "type": "teleporter"}], "edges": []}),
]
for name, desc, obj in MUTANTS:
    code, err_n, out = run_validate(write_ir(name + ".json", obj))
    if code == 1 and err_n > 0 and "不可交付" in out:
        ok("%s：%s → EXIT 1 / ERROR %d / 明确不可交付" % (name, desc, err_n))
    else:
        bad("%s：%s 未被抓住（exit=%d, ERROR=%d）" % (name, desc, code, err_n))

# 合法但省略 type：必须放行（防过度严格误报）
GOOD_NO_TYPE = {"diagram_type": "architecture",
                "nodes": [{"id": "a", "label": "节点甲"}, {"id": "b", "label": "节点乙"}],
                "edges": [{"source": "a", "target": "b"}]}
code, err_n, out = run_validate(write_ir("good-no-type.json", GOOD_NO_TYPE))
if code == 0 and err_n == 0:
    ok("good-no-type：省略 type 合法放行（EXIT 0 / ERROR 0）")
else:
    bad("good-no-type 被误杀（exit=%d, ERROR=%d）——缺 type 应是合法的" % (code, err_n))

# 汇总一致性：有 ERROR 时汇总行必须报 ERROR 且不得出现"全部通过"
for name, desc, obj in MUTANTS:
    p = write_ir(name + "-sum.json", obj)
    r = subprocess.run([sys.executable, DIAGRAM, "validate", p],
                       capture_output=True, encoding="utf-8")
    m = re.search(r"ERROR (\d+) · WARNING (\d+)", r.stdout)
    listed = len(re.findall(r"^\s*\[ERROR", r.stdout, re.M))
    if m and int(m.group(1)) >= listed and int(m.group(1)) > 0 and "全部通过" not in r.stdout:
        ok("%s：汇总 ERROR %s >= 列出 %d，且未误报「全部通过」" % (name, m.group(1), listed))
    else:
        bad("%s：汇总与列表不一致（汇总=%s, 列出=%d）" % (name, m.group(1) if m else "无", listed))

# ------------------------------------------------------------------ 汇总
print("")
print("═" * 54)
if not failed:
    print("全部通过（闸门 + 样例回归 + 变异反证）")
    sys.exit(0)
print("失败 %d 项，不得打包发布" % len(failed))
sys.exit(1)
