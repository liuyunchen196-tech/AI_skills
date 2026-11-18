#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
slide_build.py —— slidep 命令封装（lite 版：探测 + best-effort 自动安装）。

把 slidep create / lint / upsert-dsl 三步命令封装成 Python API：
    build(pptx, dsl_files) → 自动跑 create → 逐页 lint → 自动修复溢出 → upsert-dsl

slidep 入口：
    slidep create <pptx>                  → 创建空 pptx
    slidep lint <pptx> --dsl-file <f>     → 校验语法+溢出, 返回 diagnostics
    slidep upsert-dsl <pptx> --dsl-file <f> [--page-index N]  → 写入/替换页

定位策略（按优先级探测已存在的 slidep）：
    环境变量 SLIDEP_INDEX_JS > 路径缓存（bootstrap 安装后写入）> PATH 上的 slidep
    > 托管 node 各版本 > tencent-pptx 插件缓存（WorkBuddy 客户端常已自动安装 tencent-pptx，
    slidep 随之就绪）> bootstrap 安装目录 ~/.workbuddy/ppt-polish-lite。

bootstrap（best-effort 自动安装；绝不抛异常、绝不阻塞主流程）：
    探测失败 → ① SLIDEP_TARBALL_URL 离线包（下载 + sha256 校验）→
    ② npm install @tencent/slidep@5.4.1 --registry <SLIDEP_NPM_REGISTRY，默认 mirrors.tencent.com>
    → 装好写路径缓存并复探；仍失败返回结构化错误，由调用方降级到 layout_apply.py 6 版式兜底。

跨平台说明：统一用 `node <index.js> <args>` 调用，Windows / macOS / Linux 通用。
"""

import json
import subprocess
import os
import glob
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Optional

# slidep 包坐标与安装策略默认值（可被环境变量覆盖）
SLIDEP_PKG = "@tencent/slidep@5.4.1"
DEFAULT_NPM_REGISTRY = "https://mirrors.tencent.com/npm/"   # 包 publishConfig 指定的内网镜像
BOOTSTRAP_TIMEOUT = int(os.environ.get("SLIDEP_BOOTSTRAP_TIMEOUT") or 300)


def _slidep_prefix() -> str:
    """bootstrap 安装目录（固定，不污染其他目录）。"""
    return os.path.join(os.path.expanduser("~"), ".workbuddy", "ppt-polish-lite")


def _slidep_cache_file() -> str:
    return os.path.join(_slidep_prefix(), "slidep_path.json")


def _cached_index_js() -> Optional[str]:
    """读取 bootstrap 安装后写下的 index.js 路径缓存（无效/不存在返回 None）。"""
    try:
        cf = _slidep_cache_file()
        if not os.path.isfile(cf):
            return None
        data = json.loads(Path(cf).read_text(encoding="utf-8"))
        p = data.get("index_js")
        if p and os.path.isfile(p):
            return p
    except Exception:
        pass
    return None


def _write_index_js_cache(index_js: str) -> None:
    """把 bootstrap 安装成功的 index.js 路径写入缓存，供后续探测直接命中。"""
    try:
        os.makedirs(_slidep_prefix(), exist_ok=True)
        Path(_slidep_cache_file()).write_text(
            json.dumps({"index_js": index_js}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _find_node():
    """定位 node 运行时，跨平台。优先 PATH，其次托管 node 各版本（取最新）。"""
    n = shutil.which("node")
    if n:
        return n
    base = os.path.join(os.path.expanduser("~"), ".workbuddy", "binaries", "node", "versions")
    if os.path.isdir(base):
        for ver in sorted(os.listdir(base), reverse=True):
            for cand in ("node.exe", "bin/node", "node"):
                p = os.path.join(base, ver, cand)
                if os.path.isfile(p):
                    return p
    return None


def _find_index_js():
    """定位 @tencent/slidep 的 dist/index.js 入口（仅探测，不安装）。"""
    env = os.environ.get("SLIDEP_INDEX_JS") or os.environ.get("SLIDEP_BIN")
    if env and os.path.isfile(env):
        return env
    cached = _cached_index_js()   # bootstrap 自动安装后写下的路径缓存（优先于通配扫描）
    if cached:
        return cached
    # PATH 上的 slidep shim：尝试解析其旁侧的 index.js
    sp = shutil.which("slidep")
    if sp:
        cand = os.path.join(os.path.dirname(sp), "node_modules", "@tencent", "slidep", "dist", "index.js")
        if os.path.isfile(cand):
            return cand
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, ".workbuddy", "ppt-polish-lite", "node_modules",
                     "@tencent", "slidep", "dist", "index.js"),   # bootstrap 安装目录优先
        os.path.join(home, ".workbuddy", "binaries", "node", "versions", "*",
                     "node_modules", "@tencent", "slidep", "dist", "index.js"),
        os.path.join(home, ".workbuddy", "plugins", "cache", "*", "tencent-pptx", "*",
                     "node_modules", "@tencent", "slidep", "dist", "index.js"),
        os.path.join(home, ".workbuddy", "plugins", "cache", "workbuddy-builtin", "tencent-pptx", "*",
                     "node_modules", "@tencent", "slidep", "dist", "index.js"),
    ]
    for pat in patterns:
        hits = sorted(glob.glob(pat), reverse=True)
        if hits:
            return hits[0]
    return None


def locate_slidep():
    """返回 slidep 定位结果 dict：
    - available=True:  {available, node, index_js, how}
    - available=False: {available, node, index_js, how, fix}
    """
    index_js = _find_index_js()
    node = _find_node()
    if index_js and node:
        return {"available": True, "node": node, "index_js": index_js,
                "how": f"node {index_js}"}
    if index_js and not node:
        return {"available": False, "node": None, "index_js": index_js,
                "how": "找到 slidep 的 index.js 但缺少 node 运行时",
                "fix": "请安装 Node.js，或确保 .workbuddy/binaries/node 可用"}
    return {"available": False, "node": node, "index_js": None,
            "how": "未找到 @tencent/slidep",
            "fix": ("未探测到 @tencent/slidep。可运行 `python scripts/slide_build.py bootstrap` "
                    "尝试自动安装（best-effort，失败不阻塞）；也可确认 tencent-pptx 已安装"
                    "（WorkBuddy 客户端可能已自动安装，slidep 会随之就绪）后重跑探测；"
                    "或设置环境变量 SLIDEP_INDEX_JS 指向本机 .../node_modules/@tencent/slidep/dist/index.js；"
                    "自动安装不可用时，重排将降级到 layout_apply.py 的 6 版式兜底。")}


class SlidepNotFoundError(RuntimeError):
    """slidep 不可用（缺失或 node 缺失）时抛出。"""


def check_slidep():
    """供 skill / 对话层在开始前探测可用性，返回 locate_slidep() 的 dict。"""
    return locate_slidep()


def ensure_slidep(auto_install: bool = False) -> dict:
    """探测 slidep；auto_install=True 且探测失败时，先 bootstrap 尝试自动安装再返回。

    返回 locate_slidep() 形状的 dict；若 bootstrap 介入过，附带
    bootstrap_attempted / bootstrap_error 字段，fix 更新为含降级建议的版本。
    """
    info = locate_slidep()
    if info.get("available") or not auto_install:
        return info
    boot = bootstrap()
    if boot.get("ok") and boot.get("info", {}).get("available"):
        return boot["info"]
    out = dict(info)
    out["bootstrap_attempted"] = True
    out["bootstrap_error"] = boot.get("error")
    out["fix"] = boot.get("fix") or info.get("fix")
    return out


def render_check_report(info: dict) -> str:
    """把 locate_slidep() 的结果渲染成给人看的报告（agent 与用户都能直接读）。"""
    if info.get("available"):
        return (
            "[slidep 前置检查] 可用\n"
            f"  调用方式: {info['how']}\n"
            f"  node: {info['node']}\n"
            f"  index.js: {info['index_js']}\n"
            "  -> 重排/生成新页/diagram 路径可正常使用。"
        )
    lines = ["[slidep 前置检查] 当前未检测到 @tencent/slidep"]
    if info.get("index_js") and not info.get("node"):
        lines.append("  - 已找到 slidep 入口，但缺少 node 运行时: " + str(info.get("fix", "")))
    else:
        lines.append("  " + str(info.get("fix", "")))
    if info.get("bootstrap_attempted"):
        lines.append("  - 已尝试自动安装（bootstrap），仍未成功: " + str(info.get("bootstrap_error")))
    lines += [
        "",
        "  下一步（按优先级）:",
        "    1. python scripts/slide_build.py bootstrap    # best-effort 自动安装（失败不阻塞）",
        "    2. 仍不可用 → 重排降级到 layout_apply.py（6 版式，纯 python-pptx，零外部依赖）",
        "",
        "  受影响能力（需要 slidep，当前不可用）:",
        "    - 重排为 16 种版式、diagram 节点连线生成、生成/写入新页",
        "  不受影响能力（走 python-pptx，照常可用）:",
        "    - Phase A 现状分析、Phase B 方案、refine 批量改色、几何/配色体检、视觉验收（前五层）",
    ]
    return "\n".join(lines)


def _npm_cmd_prefix(node: str) -> Optional[list]:
    """定位 npm CLI，返回命令前缀列表（如 ["npm"] 或 [node, npm-cli.js]）；找不到返回 None。"""
    n = shutil.which("npm")
    if n:
        return [n]
    if node:
        d = os.path.dirname(node)
        for cand in ("npm.cmd", "npm.exe", "npm"):
            p = os.path.join(d, cand)
            if os.path.isfile(p):
                return [p]
        cli = os.path.join(d, "node_modules", "npm", "bin", "npm-cli.js")
        if os.path.isfile(cli):
            return [node, cli]
    return None


def _sha256(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 64), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_tarball(url: str, dest: str, timeout: int = 180) -> str:
    """获取 slidep 离线包：支持本机路径 / file:// / http(s) URL。返回本地 tar.gz 路径。失败抛异常。"""
    if os.path.isfile(url):                      # 允许直接给本机 tar.gz 路径
        shutil.copyfile(url, dest)
        return dest
    if url.startswith("file://"):
        src = urllib.request.url2pathname(url[len("file://"):])
        shutil.copyfile(src, dest)
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "ppt-polish-lite-bootstrap"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f, length=1024 * 256)
    if os.path.getsize(dest) == 0:
        raise RuntimeError("下载得到空文件")
    return dest


def _run_install(cmd: list, timeout: int) -> str:
    """执行安装命令；stdout/stderr 落临时文件再读回（避免 capture_output 管道死锁）。失败抛异常。"""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        out_f, err_f = os.path.join(td, "out.log"), os.path.join(td, "err.log")
        with open(out_f, "w", encoding="utf-8", errors="replace") as fo, \
                open(err_f, "w", encoding="utf-8", errors="replace") as fe:
            proc = subprocess.run(cmd, stdout=fo, stderr=fe, timeout=timeout)
        out = Path(out_f).read_text(encoding="utf-8", errors="replace").strip()
        err = Path(err_f).read_text(encoding="utf-8", errors="replace").strip()
    if proc.returncode != 0:
        raise RuntimeError(f"安装失败(退出码 {proc.returncode}): {(err or out)[-800:]}")
    return out[-300:]


def _prefix_index_js(prefix: str) -> Optional[str]:
    p = os.path.join(prefix, "node_modules", "@tencent", "slidep", "dist", "index.js")
    return p if os.path.isfile(p) else None


def bootstrap(timeout: int = BOOTSTRAP_TIMEOUT) -> dict:
    """探测失败后 best-effort 自动安装 @tencent/slidep。绝不抛异常、绝不阻塞主流程。

    安装策略（按优先级）：
      1. SLIDEP_TARBALL_URL 指向离线 tar.gz（支持 file:// 或本机路径）→ 下载 + sha256 校验 → npm install
      2. npm install @tencent/slidep@5.4.1 --registry <SLIDEP_NPM_REGISTRY，默认 mirrors.tencent.com>
    安装目标固定为 ~/.workbuddy/ppt-polish-lite（--prefix），不污染其他目录。

    返回:
      {ok:True,  available:True,  installed:bool, info, prefix, attempts, note}
      {ok:False, available:False, error, fix, fallback:"layout_apply", attempts}
    """
    info = locate_slidep()
    if info.get("available"):
        return {"ok": True, "available": True, "installed": False,
                "info": info, "attempts": [], "note": "本机已有 slidep，无需安装"}

    node = _find_node()
    if not node:
        return {"ok": False, "available": False, "installed": False,
                "error": "node_missing", "fallback": "layout_apply",
                "fix": ("未找到 node 运行时，无法自动安装。请安装 Node.js 后重试 bootstrap；"
                        "重排可先降级到 layout_apply.py 的 6 版式兜底（纯 python-pptx，零外部依赖）。"),
                "attempts": []}

    npm = _npm_cmd_prefix(node)
    if not npm:
        return {"ok": False, "available": False, "installed": False,
                "error": "npm_missing", "fallback": "layout_apply",
                "fix": ("找到 node 但未找到 npm，无法自动安装。请补齐 npm 后重试 bootstrap；"
                        "重排可先降级到 layout_apply.py 的 6 版式兜底。"),
                "attempts": []}

    prefix = _slidep_prefix()
    os.makedirs(prefix, exist_ok=True)
    attempts = []

    # 策略 1：离线包（下载 + sha256 校验）
    tarball_url = (os.environ.get("SLIDEP_TARBALL_URL") or "").strip()
    if tarball_url:
        t0 = time.time()
        try:
            dest = os.path.join(prefix, "slidep-tarball.tgz")
            local = _download_tarball(tarball_url, dest)
            expect = (os.environ.get("SLIDEP_TARBALL_SHA256") or "").strip().lower()
            if expect:
                got = _sha256(local)
                if got != expect:
                    raise RuntimeError(f"sha256 校验失败: 期望 {expect}，实际 {got}")
            detail = _run_install(npm + ["install", local, "--prefix", prefix,
                                         "--no-audit", "--no-fund", "--loglevel", "error"], timeout)
            attempts.append({"strategy": "tarball", "url": tarball_url, "ok": True,
                             "elapsed_s": round(time.time() - t0, 1), "detail": detail})
        except Exception as e:
            attempts.append({"strategy": "tarball", "url": tarball_url, "ok": False,
                             "elapsed_s": round(time.time() - t0, 1), "detail": str(e)[:500]})

    # 策略 2：镜像源 npm install（策略 1 未成功或未配置时）
    info2 = locate_slidep()
    if not info2.get("available"):
        registry = (os.environ.get("SLIDEP_NPM_REGISTRY") or "").strip() or DEFAULT_NPM_REGISTRY
        t0 = time.time()
        try:
            detail = _run_install(npm + ["install", SLIDEP_PKG, "--prefix", prefix,
                                         "--registry", registry,
                                         "--no-audit", "--no-fund", "--loglevel", "error"], timeout)
            attempts.append({"strategy": "npm", "registry": registry, "package": SLIDEP_PKG,
                             "ok": True, "elapsed_s": round(time.time() - t0, 1), "detail": detail})
        except Exception as e:
            attempts.append({"strategy": "npm", "registry": registry, "package": SLIDEP_PKG,
                             "ok": False, "elapsed_s": round(time.time() - t0, 1),
                             "detail": str(e)[:500]})

    # 复探（优先走 locate；失败再直查安装目录）
    info3 = locate_slidep()
    if not info3.get("available"):
        idx = _prefix_index_js(prefix)
        if idx:
            info3 = {"available": True, "node": node, "index_js": idx,
                     "how": f"node {idx}（bootstrap 自动安装）"}
    if info3.get("available"):
        _write_index_js_cache(info3["index_js"])
        return {"ok": True, "available": True, "installed": True, "info": info3,
                "prefix": prefix, "attempts": attempts,
                "note": "已通过 bootstrap 自动安装 @tencent/slidep，重排/生成路径可用"}

    return {"ok": False, "available": False, "installed": False,
            "error": "install_failed", "fallback": "layout_apply",
            "fix": ("自动安装未成功（常见原因：镜像源不可达 / 需内网 / 原生依赖编译失败）。"
                    "核心能力（体检/改色/去 AI 味/七层视检）不受影响；"
                    "重排将降级到 layout_apply.py 的 6 版式兜底（纯 python-pptx，零外部依赖）。"),
            "attempts": attempts}


_SLIDEP_CACHE = None


def _get_slidep():
    global _SLIDEP_CACHE
    if _SLIDEP_CACHE is None:
        _SLIDEP_CACHE = ensure_slidep()
    if not _SLIDEP_CACHE.get("available"):
        raise SlidepNotFoundError(_SLIDEP_CACHE.get("fix", "slidep 不可用"))
    return _SLIDEP_CACHE


def _run_slidep(args, cwd=None):
    """执行 slidep 子命令，返回 stdout 解析后的 JSON。"""
    info = _get_slidep()
    proc = subprocess.run(
        [info["node"], info["index_js"]] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"slidep 失败: {' '.join(args)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
    if not lines:
        raise RuntimeError(f"slidep 未返回 JSON: {proc.stdout!r} / stderr={proc.stderr!r}")
    return json.loads(lines[-1])


def create_pptx(pptx_path: str) -> dict:
    """创建空 pptx。返回 {ok, file_id, file_path, latest_version}。"""
    return _run_slidep(["create", pptx_path], cwd=str(Path(pptx_path).parent))


def lint(pptx_path: str, dsl_path: str, page_index: int = 0) -> dict:
    """lint 一页 .slide。返回 {ok, diagnostics[]}。"""
    return _run_slidep(
        ["lint", pptx_path, "--dsl-file", dsl_path],
        cwd=str(Path(pptx_path).parent),
    )


def upsert_dsl(pptx_path: str, dsl_path: str, page_index: Optional[int] = None) -> dict:
    """写入/替换一页。page_index=None 表示追加，指定则替换该页。"""
    args = ["upsert-dsl", pptx_path, "--dsl-file", dsl_path]
    if page_index is not None:
        args += ["--page-index", str(page_index)]
    return _run_slidep(args, cwd=str(Path(pptx_path).parent))


def is_overflow_diagnostic(diag: dict) -> bool:
    """判断一条 diagnostic 是否为 no-overflow 错。"""
    return diag.get("ruleId") == "no-overflow" and diag.get("severity") == "error"


def autofix_overflow(dsl_path: str, diag: dict, max_attempts: int = 3) -> bool:
    """根据 lint 溢出诊断自动修改 .slide 源文件。

    策略：按溢出方向（Bottom/Right/Top/Left）按比例缩字号或缩 padding。
    返回 True 表示修复成功（修改了文件），False 表示无法修复。
    """
    src = Path(dsl_path).read_text(encoding="utf-8")
    msg = diag.get("message", "")

    import re
    overflows = re.findall(r"(Bottom|Top|Left|Right)\+(\d+)px", msg)
    if not overflows:
        return False

    max_overflow = max(int(px) for _, px in overflows)

    if max_overflow > 200:
        return False

    def shrink_fontsize(m):
        n = int(m.group(1))
        new_n = max(8, int(n * 0.9))
        return f"fontSize: {new_n}"

    new_src = re.sub(r"fontSize:\s*(\d+)", shrink_fontsize, src)
    if new_src != src:
        Path(dsl_path).write_text(new_src, encoding="utf-8")
        return True
    return False


def build(
    pptx_path: str,
    dsl_paths: list,
    auto_fix: bool = True,
    autofix_max_rounds: int = 3,
) -> dict:
    """主入口。

    流程: create → 逐页 lint → auto_fix (可选) → upsert-dsl
    返回: {
        ok: bool,
        page_results: [{dsl, ok, diagnostics, upsert_result}, ...]
    }
    """
    Path(pptx_path).parent.mkdir(parents=True, exist_ok=True)
    avail = ensure_slidep()
    if not avail.get("available"):
        return {
            "ok": False,
            "slidep_available": False,
            "error": "slidep_unavailable",
            "fix": avail.get("fix"),
            "page_results": [],
        }
    create_result = create_pptx(pptx_path)

    page_results = []
    all_ok = True

    for idx, dsl_path in enumerate(dsl_paths):
        current_dsl = dsl_path
        ok = False
        last_diag = None

        for round_i in range(autofix_max_rounds + 1):
            lint_result = lint(pptx_path, current_dsl, page_index=idx)
            if lint_result.get("ok"):
                ok = True
                last_diag = lint_result.get("diagnostics", [])
                break

            diags = lint_result.get("diagnostics", [])
            last_diag = diags
            if auto_fix and any(is_overflow_diagnostic(d) for d in diags):
                overflow_diag = next(d for d in diags if is_overflow_diagnostic(d))
                if not autofix_overflow(current_dsl, overflow_diag):
                    break
            else:
                break

        if not ok:
            all_ok = False
            page_results.append({
                "dsl": current_dsl,
                "ok": False,
                "diagnostics": last_diag,
                "upsert_result": None,
            })
            continue

        upsert_result = upsert_dsl(pptx_path, current_dsl, page_index=idx)
        page_results.append({
            "dsl": current_dsl,
            "ok": True,
            "diagnostics": last_diag,
            "upsert_result": upsert_result,
        })

    return {"ok": all_ok, "file_id": create_result.get("file_id"), "page_results": page_results}


# CLI 入口
if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if args and args[0] == "check":
        info = check_slidep()
        print(render_check_report(info))
        sys.exit(0 if info.get("available") else 1)
    if args and args[0] == "bootstrap":
        boot = bootstrap()
        if boot.get("ok"):
            print(render_check_report(boot["info"]))
            print(f"  -> 自动安装完成（安装目录: {boot.get('prefix')}）")
            sys.exit(0)
        print(render_check_report(check_slidep()))
        print()
        print("[bootstrap] 自动安装未成功（核心能力不受影响，重排将走 layout_apply 兜底）:")
        print(json.dumps({k: v for k, v in boot.items() if k != "info"},
                         ensure_ascii=False, indent=2))
        sys.exit(2)
    if len(args) < 2:
        print("用法:")
        print("  python slide_build.py check                                # 仅做 slidep 可用性检查（只读）")
        print("  python slide_build.py bootstrap                            # 探测失败时 best-effort 自动安装（不阻塞）")
        print("  python slide_build.py <pptx> <dsl1.slide> [dsl2.slide ...] # 构建 deck（需本机已具备 slidep）")
        sys.exit(1)
    pptx = args[0]
    slides = args[1:]
    result = build(pptx, slides)
    if not result.get("slidep_available", True):
        info = ensure_slidep()
        print(render_check_report(info))
        print()
        print("build() 详情: " + json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("ok") else 1)
