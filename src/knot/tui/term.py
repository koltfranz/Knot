"""终端控制：VT 启用、尺寸、按键读取、cooked 行输入。"""

from __future__ import annotations

import ctypes
import os
import shutil
import sys

IS_WINDOWS = sys.platform == "win32"

KEY_ALIASES = {
    b"\x1b[A": "up",
    b"\x1b[B": "down",
    b"\x1b[C": "right",
    b"\x1b[D": "left",
    b"\x1b[5~": "pgup",
    b"\x1b[6~": "pgdn",
    b"\x1b[H": "home",
    b"\x1b[F": "end",
}
WINDOWS_KEYS = {
    "H": "up",
    "P": "down",
    "K": "left",
    "M": "right",
    "I": "pgup",
    "Q": "pgdn",
    "G": "home",
    "O": "end",
}
NORMALIZE = {
    "\r": "enter",
    "\n": "enter",
    "\x7f": "backspace",
    "\x08": "backspace",
    "\x03": "quit",
    "\x1b": "esc",
}


def enable_vt() -> None:
    if not IS_WINDOWS:
        return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except (OSError, AttributeError, ValueError):
        pass


def size() -> tuple[int, int]:
    cols, rows = shutil.get_terminal_size((80, 24))
    return rows, cols


def is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def cooked_line(prompt: str = "") -> str:
    """切换到 cooked（规范）模式读取一行，保证中文输入法可用。"""
    if prompt:
        sys.stdout.write(prompt)
        sys.stdout.flush()
    return input()


class RawMode:
    """进入 raw 模式（POSIX 用 termios；Windows 由 msvcrt 直接读取）。"""

    def __enter__(self):
        self._saved = None
        if not IS_WINDOWS and sys.stdin.isatty():
            import termios
            import tty

            self._saved = termios.tcgetattr(sys.stdin.fileno())
            tty.setraw(sys.stdin.fileno())
        return self

    def __exit__(self, *exc_info) -> None:
        self.restore()

    def restore(self) -> None:
        if self._saved is not None:
            import termios

            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._saved)
            self._saved = None


def read_key() -> str:
    """读取一个按键：'up'/'down'/'pgup'/'enter'/'esc' 或字符本身。"""
    if IS_WINDOWS:
        import msvcrt

        char = msvcrt.getwch()
        if char in ("\x00", "\xe0"):
            return WINDOWS_KEYS.get(msvcrt.getwch(), "")
        return NORMALIZE.get(char, char)
    data = os.read(sys.stdin.fileno(), 1)
    if data == b"\x1b":
        for _ in range(3):
            try:
                data += os.read(sys.stdin.fileno(), 1)
            except OSError:
                break
        return KEY_ALIASES.get(data, "esc")
    return NORMALIZE.get(data.decode("utf-8", "replace"), data.decode("utf-8", "replace"))
