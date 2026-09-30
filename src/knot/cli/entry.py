"""桌面入口：选择窗口 + 在新窗口里拉起界面（三平台，仅用系统自带工具）。

约束：
- 不引入任何第三方依赖：Windows 用系统 PowerShell + WinForms，macOS 用 osascript，
  Linux 用 zenity / kdialog；都没有时退回终端菜单（非交互环境直接走默认）。
- 选择窗口超时（默认 10 秒）由 Python 侧统一控制：超时按默认项（浏览器界面）继续。
- MUST 支持「无控制台」环境（Windows 桌面快捷方式用 pythonw.exe 启动）：那里
  `sys.stdin` / `sys.stdout` / `sys.stderr` 都是 None，任何 `.isatty()` 与写流都要先判空。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"

DEFAULT_CHOICE = "browser"
CHOICES = ("browser", "tui", "demo")
LABELS = {"browser": "浏览器界面", "tui": "终端界面", "demo": "示例账本"}
BY_LABEL = {label: key for key, label in LABELS.items()}
PROMPT = "选择要打开的界面（10 秒后自动进入浏览器界面）"
TITLE = "结绳 Knot"

WINDOWS_CREATE_NEW_CONSOLE = 0x00000010
WINDOWS_CREATE_NO_WINDOW = 0x08000000
MB_ICONERROR = 0x10


# ---------- 标准流安全判空（pythonw 下为 None） ----------


def stream_is_tty(stream) -> bool:
    if stream is None:
        return False
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def in_terminal() -> bool:
    """当前是否处于交互式终端；无控制台（pythonw）时恒为 False。"""
    return stream_is_tty(sys.stdin) and stream_is_tty(sys.stdout)


# ---------- 选择窗口 ----------


def choose(timeout: float = 10.0) -> str:
    """弹出选择窗口 → browser / tui / demo / quit；超时或无法弹窗时返回默认项。"""
    dialog = _pick_dialog()
    if dialog is None:
        return _tty_menu() if in_terminal() else DEFAULT_CHOICE
    command = dialog()
    options: dict = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "stdin": subprocess.DEVNULL,
        "timeout": timeout,
        "check": False,
    }
    if IS_WINDOWS:
        # 无控制台时不给子进程弹控制台窗口
        options["creationflags"] = WINDOWS_CREATE_NO_WINDOW
    try:
        result = subprocess.run(command, **options)
    except subprocess.TimeoutExpired:
        return DEFAULT_CHOICE
    except (OSError, ValueError):
        return DEFAULT_CHOICE
    answer = (result.stdout or "").strip().splitlines()
    if not answer:
        return "quit"
    return answer[-1].strip()


def _pick_dialog():
    if IS_WINDOWS and shutil.which("powershell"):
        return _windows_dialog
    if IS_MACOS and shutil.which("osascript"):
        return _macos_dialog
    if shutil.which("zenity"):
        return _zenity_dialog
    if shutil.which("kdialog"):
        return _kdialog_dialog
    return None


def _windows_dialog() -> list[str]:
    script = "\n".join(
        [
            "Add-Type -AssemblyName System.Windows.Forms",
            "Add-Type -AssemblyName System.Drawing",
            "$form = New-Object System.Windows.Forms.Form",
            f"$form.Text = '{TITLE}'",
            "$form.ClientSize = New-Object System.Drawing.Size(320, 216)",
            "$form.StartPosition = 'CenterScreen'",
            "$form.TopMost = $true",
            "$form.FormBorderStyle = 'FixedDialog'",
            "$form.MaximizeBox = $false",
            "$form.MinimizeBox = $false",
            "$label = New-Object System.Windows.Forms.Label",
            f"$label.Text = '{PROMPT}'",
            "$label.SetBounds(16, 12, 292, 32)",
            "$form.Controls.Add($label)",
            "$script:choice = 'quit'",
            "$handler = { param($sender, $eventArgs) $script:choice = $sender.Tag; $form.Close() }",
        ]
        + [
            item
            for index, key in enumerate(CHOICES)
            for item in (
                f"$b{index} = New-Object System.Windows.Forms.Button",
                f"$b{index}.Text = '{LABELS[key]}'",
                f"$b{index}.Tag = '{key}'",
                f"$b{index}.SetBounds(16, {52 + index * 36}, 292, 30)",
                f"$b{index}.Add_Click($handler)",
                f"$form.Controls.Add($b{index})",
            )
        ]
        + [
            "$quit = New-Object System.Windows.Forms.Button",
            "$quit.Text = '退出'",
            "$quit.Tag = 'quit'",
            "$quit.SetBounds(16, 168, 292, 30)",
            "$quit.Add_Click($handler)",
            "$form.Controls.Add($quit)",
            "[void]$form.ShowDialog()",
            "[Console]::Out.WriteLine($script:choice)",
        ]
    )
    path = _temp_file(".ps1", script, bom=True)
    return [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-STA",
        "-File",
        str(path),
    ]


def _macos_dialog() -> list[str]:
    items = ", ".join(f'"{LABELS[key]}"' for key in CHOICES)
    script = (
        f"set choices to {{{items}}}\n"
        f'set picked to choose from list choices with title "{TITLE}" '
        f'with prompt "{PROMPT}" default items {{"{LABELS[DEFAULT_CHOICE]}"}}\n'
        'if picked is false then\n return "quit"\nelse\n return item 1 of picked\nend if\n'
    )
    return ["osascript", "-e", script]


def _zenity_dialog() -> list[str]:
    return [
        "zenity",
        "--list",
        "--title",
        TITLE,
        "--text",
        PROMPT,
        "--column",
        "界面",
        "--hide-header",
        *[LABELS[key] for key in CHOICES],
        "--height",
        "240",
    ]


def _kdialog_dialog() -> list[str]:
    args = ["kdialog", "--title", TITLE, "--menu", PROMPT]
    for key in CHOICES:
        args.extend([key, LABELS[key]])
    return args


def _tty_menu() -> str:
    lines = [f"{TITLE}：{PROMPT}", "  1. 浏览器界面", "  2. 终端界面", "  3. 示例账本", "  0. 退出"]
    print("\n".join(lines))
    try:
        answer = input("请选择（回车 = 浏览器界面）：").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "quit"
    keys = {"1": "browser", "2": "tui", "3": "demo", "0": "quit", "": "browser"}
    return keys.get(answer, "browser")


def _temp_file(suffix: str, content: str, *, bom: bool = False) -> Path:
    directory = Path(tempfile.mkdtemp(prefix="knot-entry-"))
    path = directory / f"entry{suffix}"
    text = ("\ufeff" + content) if bom else content
    path.write_text(text, encoding="utf-8", newline="")
    return path


# ---------- 在新窗口里拉起界面 ----------


def spawn_tui(python: str, ledger: Path) -> bool:
    """在独立窗口里打开终端界面；成功返回 True。"""
    return _spawn([python, "-m", "knot", "界面", "--账本", str(ledger)])


def spawn_browser(python: str, ledger: Path) -> bool:
    """在独立窗口里启动本地服务并打开浏览器；成功返回 True。"""
    return _spawn([python, "-m", "knot", "服务", "--打开浏览器", "--账本", str(ledger)])


def _spawn(command: list[str]) -> bool:
    quoted = subprocess.list2cmdline(command)
    if IS_WINDOWS:
        try:
            subprocess.Popen(
                ["cmd", "/k", quoted], creationflags=WINDOWS_CREATE_NEW_CONSOLE, close_fds=True
            )
        except OSError:
            return False
        return True

    if IS_MACOS:
        script = _temp_file(".command", f"#!/bin/sh\nexec {quoted}\n")
        script.chmod(0o755)
        try:
            subprocess.Popen(["open", "-a", "Terminal", str(script)])
        except OSError:
            return False
        return True

    terminal = _linux_terminal()
    if terminal is None:
        return False
    try:
        subprocess.Popen([*terminal, "sh", "-c", f"{quoted}; exec sh"])
    except OSError:
        return False
    return True


def _linux_terminal() -> list[str] | None:
    candidates: tuple[tuple[str, list[str]], ...] = (
        ("x-terminal-emulator", ["-e"]),
        ("gnome-terminal", ["--"]),
        ("konsole", ["-e"]),
        ("xfce4-terminal", ["-e"]),
        ("alacritty", ["-e"]),
        ("xterm", ["-e"]),
    )
    for name, flag in candidates:
        found = shutil.which(name)
        if found:
            return [found, *flag]
    return None


def console_executable() -> str:
    """带控制台的解释器：用于在新窗口里跑界面（能看到输出、可 Ctrl+C 停止）。

    pythonw.exe 启动时 sys.executable 指向 pythonw，这里换回同目录的 python.exe。
    """
    if IS_WINDOWS:
        current = Path(sys.executable)
        if current.name.lower() == "pythonw.exe":
            console = current.with_name("python.exe")
            if console.exists():
                return str(console)
    return sys.executable


def windowless_executable() -> str:
    """无控制台解释器（Windows 的 pythonw.exe）：用于桌面快捷方式，避免弹出黑窗。"""
    if IS_WINDOWS:
        windowless = Path(sys.executable).with_name("pythonw.exe")
        if windowless.exists():
            return str(windowless)
    return sys.executable


def _message_box(message: str) -> bool:
    if not IS_WINDOWS:
        return False
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, TITLE, MB_ICONERROR)
    except (OSError, AttributeError, ValueError):
        return False
    return True


def report_error(message: str) -> None:
    """把失败原因告诉用户：Windows 弹消息框（pythonw 下没有 stderr），否则写 stderr。"""
    text = f"{TITLE} 启动失败：\n\n{message}"
    if _message_box(text):
        return
    try:
        if sys.stderr is not None:
            print(text, file=sys.stderr)
    except (ValueError, OSError):
        pass


def label_of(choice: str) -> str:
    return LABELS.get(choice, choice)


def home_from_env() -> Path | None:
    value = os.environ.get("KNOT_HOME")
    return Path(value).expanduser() if value else None
