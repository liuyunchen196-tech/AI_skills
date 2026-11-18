r"""
local-ocr / SETUP - one-click environment bootstrap.

Priority for the base interpreter:
  1) WorkBuddy bundled Python  (~/.workbuddy/binaries/python/versions/*/python.exe)
  2) system python / python3 / py

Creates <skill_dir>/.venv, installs requirements.txt, writes venv_path.txt, runs selftest.
"""

import glob
import os
import pathlib
import shutil
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
VENV_DIR = SKILL_DIR / ".venv"
VENV_PY = VENV_DIR / "Scripts" / "python.exe"
MARKER = SKILL_DIR / "venv_path.txt"
REQ = SKILL_DIR / "requirements.txt"
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
OFFICIAL = "https://pypi.org/simple"


def run(cmd, **kw):
    return subprocess.run(cmd, **kw)


def find_python():
    home = pathlib.Path.home()
    pattern = str(home / ".workbuddy" / "binaries" / "python" / "versions" / "*" / "python.exe")
    cands = sorted(glob.glob(pattern))
    if cands:
        return cands[-1], "WorkBuddy 自带 Python"
    for name in ("python", "python3", "py"):
        p = shutil.which(name)
        if p:
            return p, "系统 Python"
    return None, None


def check_version(py):
    try:
        out = subprocess.run(
            [py, "-c", "import sys;print('%d.%d'%sys.version_info[:2])"],
            capture_output=True, text=True, timeout=60,
        ).stdout.strip()
        major, minor = (int(x) for x in out.split("."))
        return (major, minor), out
    except Exception:
        return None, "unknown"


def pip_install(py, *args):
    for src in (MIRROR, OFFICIAL):
        r = run([py, "-m", "pip", "install", *args, "-i", src, "--disable-pip-version-check"])
        if r.returncode == 0:
            return True
        print(f"[WARN] 镜像 {src} 失败，换下一个")
    return False


def parse_venv_dir(argv):
    """Optional: --venv-dir PATH  -> put the venv somewhere else (e.g. a drive with more space)."""
    for i, a in enumerate(argv):
        if a.startswith("--venv-dir=") and len(a) > len("--venv-dir="):
            return pathlib.Path(a.split("=", 1)[1]).expanduser().resolve()
        if a == "--venv-dir" and i + 1 < len(argv):
            return pathlib.Path(argv[i + 1]).expanduser().resolve()
    return None


def main():
    global VENV_DIR, VENV_PY
    custom = parse_venv_dir(sys.argv[1:])
    if custom:
        VENV_DIR = custom
        VENV_PY = VENV_DIR / "Scripts" / "python.exe"

    print("=" * 56)
    print(" local-ocr 环境部署（只需跑一次）")
    print("=" * 56)

    recorded = MARKER.read_text(encoding="utf-8").strip() if MARKER.exists() else ""
    if VENV_PY.exists() and recorded == str(VENV_PY):
        print(f"[OK] 环境已就绪：{VENV_DIR}")
        print("     如需重装，删除 .venv 与 venv_path.txt 后重跑本脚本")
        return 0

    py, src = find_python()
    if not py:
        print("[ERROR] 没找到 Python。请安装 Python 3.9-3.13 或安装 WorkBuddy")
        return 1

    ver, vstr = check_version(py)
    print(f"[OK] 找到 {src}：{py}")
    print(f"     版本 {vstr}")
    if ver and not ((3, 9) <= ver <= (3, 13)):
        print("[ERROR] 版本不支持（需 3.9-3.13，3.14+ 依赖未跟上）")
        return 1

    print(f"\n[1/4] 创建虚拟环境 -> {VENV_DIR}")
    if run([py, "-m", "venv", str(VENV_DIR)]).returncode != 0:
        print("[ERROR] venv 创建失败")
        return 1

    print("[2/4] 升级 pip")
    pip_install(str(VENV_PY), "--upgrade", "pip")

    print("[3/4] 安装依赖（约 3-5 分钟，走清华源）")
    if not pip_install(str(VENV_PY), "-r", str(REQ)):
        print("[ERROR] 依赖安装失败，检查网络/代理后重跑")
        return 1

    MARKER.write_text(str(VENV_PY), encoding="utf-8")
    print(f"[OK] 已记录解释器路径 -> {MARKER.name}")

    print("[4/4] 自检")
    ocr_py = SKILL_DIR / "scripts" / "ocr.py"
    r = run([str(VENV_PY), str(ocr_py), "--selftest"])
    if r.returncode != 0:
        print("[ERROR] 自检未通过")
        return 1

    print("\n" + "=" * 56)
    print(" SETUP DONE")
    print(f" 之后调用：{VENV_PY} {ocr_py} <图片/PDF/文件夹>")
    print(" 装完永久离线可用，无需再联网")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
