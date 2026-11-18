#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
byai-diagram-designer · 统一命令行

    python diagram.py doctor
    python diagram.py styles
    python diagram.py guide "展示 CI/CD 检查、审批、部署与回滚"
    python diagram.py validate  <ir.json> [--quality showcase] [--json]
    python diagram.py render    <ir.json> <out.html> [--report layout.json] [--json]
    python diagram.py check     <out.html> [--json]
    python diagram.py deliver   <ir.json> <out.html> [--quality showcase] [--json]
    python diagram.py compare   <base.json> <head.json> <out.html> [--json]
    python diagram.py mermaid   <in.mmd> <out.json>
    python diagram.py demo      <outdir>

退出码：0 成功；1 校验未通过；2 输入/环境错误。
纯标准库实现。
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import styles as styles_mod          # noqa: E402
import ir_schema                     # noqa: E402
import geometry                      # noqa: E402
import composition                   # noqa: E402
import render_engine                 # noqa: E402
import mermaid2ir                    # noqa: E402
import compare as compare_mod        # noqa: E402

VERSION = "1.0.1"
EXIT_OK, EXIT_FAIL, EXIT_ERR = 0, 1, 2

GUIDE_RULES = [
    (("ci/cd", "cicd", "部署", "发布", "回滚", "审批", "流水线", "pipeline"),
     "workflow", "列出参与者、顺序、分支与异常路径；审批用 decision 节点"),
    (("时序", "调用链", "sequence", "请求生命周期", "api 调用", "oauth", "鉴权流程"),
     "sequence", "列出调用方、被调方、返回值与时序约束"),
    (("数据流", "etl", "血缘", "管道", "数据管道", "lineage", "数仓"),
     "dataflow", "标明数据源、转换、存储与治理边界"),
    (("状态", "生命周期", "重试", "订单状态", "状态机"),
     "lifecycle", "列出状态、事件、重试与取消路径、终态"),
    (("对比", "对比矩阵", "vs", "选型", "特性对比"),
     "comparison", "每行一个属性维度，每列一个候选方案"),
    (("思维导图", "概念图", "能力地图", "知识结构"),
     "mindmap", "中心一个主题，分支 5-9 个"),
    (("rag", "检索增强"), "ai.rag", "Query → Embed → 向量检索 → 重排 → LLM → 响应"),
    (("multi-agent", "多智能体", "子代理", "orchestrator"),
     "ai.multi-agent", "编排者 → 多个子代理 → 聚合器 → 输出"),
    (("mem0", "记忆", "memory"), "ai.memory", "输入 → 记忆管理 → 存储分层 → 检索"),
    (("tool call", "工具调用", "function calling"),
     "ai.tool-call", "LLM → 工具选择 → 执行 → 解析 → 回到 LLM"),
    (("uml", "类图", "时序图", "部署图"), "uml.component", "明确 UML 图种与抽象层级"),
]


def guide(scenario):
    s = str(scenario or "").lower()
    for keys, dtype, tip in GUIDE_RULES:
        for k in keys:
            if k in s:
                return {"diagram_type": dtype, "tip": tip}
    return {"diagram_type": "architecture",
            "tip": "说明范围、核心组件与主链路；细节写进节点描述而不是多画连线"}


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    head = text.lstrip()
    if head[:1] == "<" or head[:9].lower() == "<!doctype":
        raise SystemExit(
            "✗ 输入 %s 看起来是 HTML，但本命令需要 IR JSON（.json）。\n"
            "  · validate / render / deliver / compare 都吃 IR JSON；\n"
            "  · check 才吃 HTML；mermaid 吃 .mmd 文本。\n"
            "  请传入对应的 IR JSON 文件。" % path)
    return json.loads(text)


def _prepare(raw, cli_style=None, cli_quality=None):
    """normalize → 布局，返回 (ir, errors)。失败时 ir 为 None。"""
    ir, errors = ir_schema.normalize(raw)
    if ir is None:
        return None, errors
    if cli_style:
        ir["meta"]["style"] = cli_style
    if cli_quality:
        ir["meta"]["quality_profile"] = cli_quality
    style = styles_mod.resolve_style(ir["meta"].get("style"))
    ir["_style_obj"] = style
    geom = geometry.build_geometry(ir, style)
    ir["_geom"] = geom
    return ir, errors


def _analyze(ir, errors, html=None):
    style = ir["_style_obj"]
    finds, report = composition.check(ir, ir["_geom"], style, html)
    # IR 规范化阶段的错误必须计入汇总。此前只数契约 finding，导致「上面列着
    # [ERROR]，汇总却写 ERROR 0 / 全部通过」——用户会照着误导性结论直接交付。
    ir_findings = [e.to_dict() for e in errors]
    report["errors"] = int(report.get("errors", 0)) + len(ir_findings)
    report["warnings"] = int(report.get("warnings", 0))
    if ir_findings:
        report["passed"] = False
    all_findings = ir_findings + [f.to_dict() for f in finds]
    return {"report": report, "findings": all_findings, "irErrors": ir_findings}


def _print_human(result, ir):
    rep = result["report"]
    print("图型        : %s" % ir["diagram_type"])
    print("风格        : %s（%s）" % (ir["_style_obj"]["id"], ir["_style_obj"]["name_zh"]))
    print("节点 / 连线 : %d / %d" % (rep["nodes"], rep["edges"]))
    print("画布        : %.0f × %.0f" % (rep["canvas"]["w"], rep["canvas"]["h"]))
    print("交叉        : %d" % rep["crossings"])
    print("交付检查    : %d/%d 通过" % (rep["checksPassed"], rep["checksTotal"]))
    for c in rep["artifactChecks"]:
        flag = {"pass": "  OK  ", "warn": " WARN ", "fail": " FAIL "}[c["status"]]
        print("   [%s] %-11s %d" % (flag, c["check"], c["findings"]))
    for f in result["findings"]:
        mark = "ERROR  " if f["level"] == "error" else "WARNING"
        print("  [%s] %s %s" % (mark, f["code"], f["subject"]))
        print("          %s" % f["message"])
        if f.get("supportedFixes"):
            print("          修复：%s" % " / ".join(f["supportedFixes"]))
    print("ERROR %d · WARNING %d" % (rep["errors"], rep["warnings"]))
    if rep["errors"]:
        print("→ 存在 ERROR，不可交付：先按上面的 supportedFixes 修复。")
    elif rep["warnings"]:
        print("→ 可交付，但有 %d 条 WARNING，未达 showcase 级别，应向用户如实说明。"
              % rep["warnings"])
    else:
        print("→ 全部通过，达到 showcase 级别。")


def cmd_validate(args):
    raw = _load(args.input)
    ir, errors = _prepare(raw, args.style, args.quality)
    if ir is None:
        out = {"passed": False, "irErrors": [e.to_dict() for e in errors],
               "findings": [], "report": {"errors": len(errors), "warnings": 0}}
        if args.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print("IR 无法解析")
            for e in errors:
                print("  [ERROR] %s %s" % (e.code, e.subject))
        return EXIT_FAIL

    html = render_engine.render_html(
        ir, ir["_geom"], ir["_style_obj"],
        render_engine.render_svg(ir, ir["_geom"], ir["_style_obj"]))
    result = _analyze(ir, errors, html)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump({"report": result["report"], "findings": result["findings"],
                       "geometry": {k: v for k, v in ir["_geom"].items() if k != "matrix"}},
                      f, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result, ir)
    ok = result["report"]["passed"] and not result["irErrors"]
    return EXIT_OK if ok else EXIT_FAIL


def cmd_render(args):
    raw = _load(args.input)
    ir, errors = _prepare(raw, args.style, args.quality)
    if ir is None:
        print("IR 无法解析", file=sys.stderr)
        return EXIT_FAIL
    svg = render_engine.render_svg(ir, ir["_geom"], ir["_style_obj"])
    html = render_engine.render_html(ir, ir["_geom"], ir["_style_obj"], svg)
    result = _analyze(ir, errors, html)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump({"report": result["report"], "findings": result["findings"]},
                      f, ensure_ascii=False, indent=2)

    payload = {"output": os.path.abspath(args.output), "report": result["report"],
               "findings": result["findings"], "irErrors": result["irErrors"]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_human(result, ir)
        print("已输出：%s" % payload["output"])
    ok = result["report"]["passed"] and not result["irErrors"]
    return EXIT_OK if ok else EXIT_FAIL


def cmd_deliver(args):
    """原子交付：先渲染到同目录候选文件，全部校验通过才替换目标。"""
    raw = _load(args.input)
    ir, errors = _prepare(raw, args.style, args.quality)
    if ir is None:
        print("IR 无法解析", file=sys.stderr)
        return EXIT_FAIL
    svg = render_engine.render_svg(ir, ir["_geom"], ir["_style_obj"])
    html = render_engine.render_html(ir, ir["_geom"], ir["_style_obj"], svg)
    result = _analyze(ir, errors, html)

    target = os.path.abspath(args.output)
    ok = result["report"]["passed"] and not result["irErrors"]
    if not ok:
        payload = {"delivered": False, "output": target,
                   "report": result["report"], "findings": result["findings"]}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_human(result, ir)
            print("存在未修复问题，未覆盖已有产物。")
        return EXIT_FAIL

    directory = os.path.dirname(target) or "."
    if not os.path.isdir(directory):
        os.makedirs(directory)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".candidate")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(tmp, target)

    data = html.encode("utf-8")
    spec = json.dumps(raw, ensure_ascii=False, sort_keys=True).encode("utf-8")
    payload = {
        "delivered": True,
        "output": target,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "specBytes": len(spec),
        "specSha256": hashlib.sha256(spec).hexdigest(),
        "report": result["report"],
        "findings": result["findings"],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_human(result, ir)
        print("已交付：%s（%d 字节，sha256=%s…）"
              % (target, payload["bytes"], payload["sha256"][:16]))
    return EXIT_OK


def cmd_check(args):
    with open(args.input, "r", encoding="utf-8") as f:
        html = f.read()
    checks = []
    # 基本（所有产物都过）：html-root + 不含 CDN 外链
    checks.append(("html-root", html.lstrip().startswith("<!DOCTYPE html>")))
    external = [u for u in ("https://cdn", "http://cdn", "https://unpkg")
                if u in html]
    checks.append(("no-external-assets", not external))
    # 图类（仅当含 svg 才检查）：SVG、查看器挂载点、内嵌数据
    if "<svg" in html or "bd-svg" in html:
        checks.append(("has-svg", "<svg" in html))
        checks.append(("viewer-hook", "bd-svg" in html))
        checks.append(("has-data", '"nodes"' in html and '"edges"' in html))
    failed = [c for c, ok in checks if not ok]
    report = {"file": os.path.abspath(args.input), "bytes": len(html.encode("utf-8")),
              "checks": [{"check": c, "status": "pass" if ok else "fail"}
                         for c, ok in checks],
              "passed": not failed}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for c, ok in checks:
            print("  [%s] %s" % (" OK " if ok else "FAIL", c))
        print("产物 %d 字节" % report["bytes"])
    return EXIT_OK if not failed else EXIT_FAIL


def cmd_compare(args):
    base = _load(args.base)
    head = _load(args.head)
    result = compare_mod.diff(base, head)
    html = compare_mod.render_report(result, args.base, args.head)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        s = result.get("summary", {})
        print("新增 %d · 删除 %d · 修改 %d · 移动 %d · 连线 +%d -%d ~%d"
              % (s.get("nodesAdded", 0), s.get("nodesRemoved", 0), s.get("nodesChanged", 0),
                 s.get("nodesMoved", 0), s.get("edgesAdded", 0),
                 s.get("edgesRemoved", 0), s.get("edgesRerouted", 0)))
        print("已输出：%s" % os.path.abspath(args.output))
    return EXIT_OK


def cmd_mermaid(args):
    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()
    ir, warnings = mermaid2ir.convert(text)
    if ir is None:
        print(json.dumps({"converted": False, "warnings": warnings},
                         ensure_ascii=False, indent=2))
        return EXIT_FAIL
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(ir, f, ensure_ascii=False, indent=2)
    print(json.dumps({"converted": True, "output": os.path.abspath(args.output),
                      "diagram_type": ir.get("diagram_type"),
                      "nodes": len(ir.get("nodes") or []),
                      "edges": len(ir.get("edges") or []),
                      "warnings": warnings}, ensure_ascii=False, indent=2))
    return EXIT_OK


def cmd_styles(args):
    rows = []
    for sid, zh, base, best in styles_mod.STYLE_INDEX:
        rows.append({"id": sid, "name": zh, "base": base, "best_for": best})
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print("%-16s %-12s %-6s %s" % ("ID", "名称", "底色", "适用"))
        for r in rows:
            print("%-16s %-12s %-6s %s" % (r["id"], r["name"], r["base"], r["best_for"]))
    return EXIT_OK


def cmd_guide(args):
    out = guide(args.scenario)
    out["scenario"] = args.scenario
    print(json.dumps(out, ensure_ascii=False, indent=2) if args.json
          else "%s —— %s" % (out["diagram_type"], out["tip"]))
    return EXIT_OK


def cmd_doctor(args):
    import platform
    tpl = os.path.join(HERE, "..", "templates", "viewer.html")
    checks = [
        ("python", sys.version_info >= (3, 7), platform.python_version()),
        ("stdlib-only", True, "无第三方依赖"),
        ("viewer-template", os.path.isfile(tpl), os.path.basename(tpl)),
        ("styles", len(styles_mod.STYLES) == 12, "%d 套" % len(styles_mod.STYLES)),
        ("diagram-types", True, "%d 种" % len(ir_schema.DIAGRAM_TYPES)),
        ("icons", True, "%d 个" % len(__import__("icons").ICONS)),
    ]
    ok = all(c[1] for c in checks)
    if args.json:
        print(json.dumps({"ok": ok, "version": VERSION,
                          "checks": [{"check": c[0], "status": "pass" if c[1] else "fail",
                                      "detail": c[2]} for c in checks]},
                         ensure_ascii=False, indent=2))
    else:
        print("流程图设计助手 byai-diagram-designer v%s" % VERSION)
        for name, good, detail in checks:
            print("  [%s] %-18s %s" % (" OK " if good else "FAIL", name, detail))
    return EXIT_OK if ok else EXIT_ERR


def cmd_version(args):
    print("byai-diagram-designer %s" % VERSION)
    return EXIT_OK


def cmd_demo(args):
    outdir = args.output
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    exdir = os.path.join(HERE, "..", "examples")
    made = []
    for name in sorted(os.listdir(exdir)):
        if not name.endswith(".json"):
            continue
        src = os.path.join(exdir, name)
        raw = _load(src)
        ir, _ = _prepare(raw)
        if ir is None:
            continue
        svg = render_engine.render_svg(ir, ir["_geom"], ir["_style_obj"])
        html = render_engine.render_html(ir, ir["_geom"], ir["_style_obj"], svg)
        dst = os.path.join(outdir, name[:-5] + ".html")
        with open(dst, "w", encoding="utf-8") as f:
            f.write(html)
        made.append(dst)
    print(json.dumps({"generated": made}, ensure_ascii=False, indent=2))
    return EXIT_OK


def main(argv=None):
    p = argparse.ArgumentParser(prog="diagram.py",
                                description="流程图设计助手 · 统一命令行")
    sub = p.add_subparsers(dest="cmd")

    def add(name, fn):
        s = sub.add_parser(name)
        s.set_defaults(fn=fn)
        return s

    add("version", cmd_version)
    add("doctor", cmd_doctor)
    add("styles", cmd_styles)

    g = add("guide", cmd_guide)
    g.add_argument("scenario")

    for name, fn in (("validate", cmd_validate), ("render", cmd_render),
                     ("deliver", cmd_deliver)):
        s = sub.add_parser(name)
        s.set_defaults(fn=fn)
        s.add_argument("input")
        if name != "validate":
            s.add_argument("output")
        s.add_argument("--style")
        s.add_argument("--quality", choices=["showcase", "standard"])
        s.add_argument("--report")
        s.add_argument("--json", action="store_true")

    c = sub.add_parser("check")
    c.set_defaults(fn=cmd_check)
    c.add_argument("input")
    c.add_argument("--json", action="store_true")

    cp = sub.add_parser("compare")
    cp.set_defaults(fn=cmd_compare)
    cp.add_argument("base")
    cp.add_argument("head")
    cp.add_argument("output")
    cp.add_argument("--json", action="store_true")

    m = sub.add_parser("mermaid")
    m.set_defaults(fn=cmd_mermaid)
    m.add_argument("input")
    m.add_argument("output")

    d = sub.add_parser("demo")
    d.set_defaults(fn=cmd_demo)
    d.add_argument("output")

    args = p.parse_args(argv)
    if not getattr(args, "cmd", None):
        p.print_help()
        return EXIT_ERR
    for flag in ("json", "style", "quality", "report"):
        if not hasattr(args, flag):
            setattr(args, flag, None)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
