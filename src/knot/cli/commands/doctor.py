"""`knot 自检`：环境、安装与账本健康检查（安装脚本的安装后验证）。"""

from __future__ import annotations

import json
import platform
import sys
import tempfile
from pathlib import Path

from knot.cli.ansi import BOLD, GREEN, RED, YELLOW, style
from knot.core.diagnostic import count
from knot.core.loader import load_book
from knot.core.width import pad
from knot.version import __version__

OK = "ok"
WARN = "warn"
FAIL = "fail"
MARK = {OK: ("✓", GREEN), WARN: ("!", YELLOW), FAIL: ("✗", RED)}

ALIAS_FILE = "别名.knot"
RULE_FILE = "规则/分类规则.knot"


def add_parser(sub) -> None:
    p = sub.add_parser("doctor", aliases=["自检"], help="环境与账本自检")
    p.add_argument("--json", dest="as_json", action="store_true", help="输出 JSON")
    p.set_defaults(func=run)


def _windows_code_page() -> int | None:
    try:
        import ctypes

        return int(ctypes.windll.kernel32.GetConsoleOutputCP())
    except (OSError, AttributeError, ValueError):
        return None


def _python_check() -> tuple[str, str, str]:
    current = sys.version_info
    detail = f"{current.major}.{current.minor}.{current.micro}（要求 ≥3.11）"
    return (OK if current >= (3, 11) else FAIL), "Python", detail


def _version_check() -> tuple[str, str, str]:
    return OK, "Knot 版本", f"{__version__} · 解释器 {sys.executable}"


def _platform_check() -> tuple[str, str, str]:
    return OK, "平台", platform.platform()


def _encoding_check() -> tuple[str, str, str]:
    encoding = sys.stdout.encoding or "未知"
    if sys.platform != "win32":
        return OK, "控制台编码", f"stdout {encoding}"
    code_page = _windows_code_page()
    normalized = encoding.lower().replace("-", "")
    if code_page == 65001 and normalized in ("utf8", "utf_8"):
        return OK, "控制台编码", f"UTF-8（代码页 {code_page}）"
    return WARN, "控制台编码", f"代码页 {code_page or '未知'}，stdout {encoding}；建议 chcp 65001"


def _vt_check() -> tuple[str, str, str]:
    if sys.platform != "win32":
        return OK, "ANSI/VT", "POSIX 终端原生支持"
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(kernel32.GetStdHandle(-11), ctypes.byref(mode)):
            return WARN, "ANSI/VT", "输出不是控制台（已被重定向）"
        if mode.value & 0x0004:
            return OK, "ANSI/VT", "已启用虚拟终端处理"
        return WARN, "ANSI/VT", "未启用虚拟终端处理，彩色与 TUI 可能异常"
    except (OSError, AttributeError, ValueError):
        return WARN, "ANSI/VT", "无法读取控制台模式"


def _tty_check() -> tuple[str, str, str]:
    if sys.stdin.isatty() and sys.stdout.isatty():
        return OK, "交互终端", "stdin/stdout 均为终端"
    return WARN, "交互终端", "非交互式：TUI 不可用，其余命令正常"


def _ledger_check(ledger: Path) -> tuple[str, str, str]:
    if not ledger.exists():
        return WARN, "账本", f"未找到 {ledger}；可用 `knot create 我的账本` 新建"
    _result, _book, diags = load_book(ledger, missing_ok=True)
    errors = count(diags, "error")
    warnings = count(diags, "warning")
    if errors:
        return FAIL, "账本", f"{ledger}：错误 {errors}，警告 {warnings}；运行 `knot 检查` 查看"
    return OK, "账本", f"{ledger}：错误 0，警告 {warnings}"


def _writable_check(ledger: Path) -> tuple[str, str, str]:
    directory = ledger.parent if str(ledger.parent) else Path()
    if not directory.exists():
        return WARN, "账本目录", f"{directory} 不存在（`knot create` 会创建）"
    try:
        with tempfile.NamedTemporaryFile(
            dir=directory, prefix=".knot-自检-", suffix=".tmp", delete=True
        ):
            pass
    except OSError as exc:
        return FAIL, "账本目录", f"{directory} 不可写：{exc}"
    return OK, "账本目录", f"{directory} 可写"


def _sidecar_check(ledger: Path, name: str) -> tuple[str, str, str]:
    path = ledger.parent / name
    if not path.exists():
        return OK, name, "未使用（可选）"
    try:
        path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return WARN, name, f"读取失败：{exc}"
    return OK, name, str(path)


def _mouse_check() -> tuple[str, str, str]:
    if sys.platform != "win32":
        return OK, "鼠标支持", "TUI 鼠标：终端原生鼠标上报（1000/1002/1006）"
    return OK, "鼠标支持", "TUI 鼠标：Windows 控制台鼠标事件（进入界面时自动关闭快速编辑）"


def checks(ledger: Path) -> list[tuple[str, str, str]]:
    return [
        _python_check(),
        _version_check(),
        _platform_check(),
        _encoding_check(),
        _vt_check(),
        _tty_check(),
        _ledger_check(ledger),
        _writable_check(ledger),
        _sidecar_check(ledger, ALIAS_FILE),
        _sidecar_check(ledger, RULE_FILE),
        _mouse_check(),
    ]


def run(args) -> int:
    ledger = Path(args.ledger)
    results = checks(ledger)
    failures = [item for item in results if item[0] == FAIL]
    warnings = [item for item in results if item[0] == WARN]

    if args.as_json:
        print(
            json.dumps(
                {
                    "版本": __version__,
                    "账本": str(ledger),
                    "结果": [
                        {"项目": name, "状态": status, "说明": detail}
                        for status, name, detail in results
                    ],
                    "失败": len(failures),
                    "警告": len(warnings),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if failures else 0

    print(style("结绳 Knot 自检", BOLD))
    for status, name, detail in results:
        mark, color = MARK[status]
        print(f"  {style(mark, color)} {pad(name, 20)} {detail}")
    passed = len(results) - len(failures) - len(warnings)
    summary = f"通过 {passed}，警告 {len(warnings)}，失败 {len(failures)}"
    print(style(summary, RED if failures else (YELLOW if warnings else GREEN)))
    if failures:
        print(style("有失败项，请按上方说明处理后重试", RED), file=sys.stderr)
        return 1
    print(style("一切就绪" if not warnings else "基本就绪（有提示项）", GREEN))
    return 0
