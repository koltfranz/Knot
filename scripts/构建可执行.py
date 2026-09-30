"""用 Nuitka 构建单文件可执行程序（三平台各自构建，不支持交叉编译）。

用法：python scripts/构建可执行.py
需要先安装：python -m pip install nuitka
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if platform.system() == "Windows":
        print(
            "提示：Nuitka 在 Windows 上会调用 depends.exe（Dependency Walker）探测 DLL 依赖，"
            "在无交互环境（如 CI）中可能长时间无响应，因此本仓库的发布流水线只构建 "
            "Linux / macOS 可执行程序；Windows 请使用免安装的 knot.pyz，或用 安装.ps1 安装。"
        )
    sys.path.insert(0, str(ROOT / "src"))
    from knot.core.console import setup_console
    from knot.version import __version__

    setup_console()

    output = ROOT / "dist" / "可执行"
    output.mkdir(parents=True, exist_ok=True)
    system = platform.system().lower()
    suffix = ".exe" if system == "windows" else ""
    target = output / f"knot-{__version__}-{system}{suffix}"

    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        "--assume-yes-for-downloads",
        f"--output-dir={output}",
        f"--output-filename={target.name}",
        "--include-package-data=knot",
        "--nofollow-import-to=pytest,unittest",
    ]
    command.append(str(ROOT / "src" / "knot" / "__main__.py"))
    environment = dict(os.environ, PYTHONUTF8="1")

    print("执行：", " ".join(command))
    result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    if result.returncode != 0:
        print(
            "Nuitka 构建失败：请确认已安装编译器（Windows 需 MSVC，Linux 需 gcc，macOS 需 clang）",
            file=sys.stderr,
        )
        return result.returncode
    print(f"已生成：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
