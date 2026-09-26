from __future__ import annotations

import os
import sys

RESET = 0
BOLD = 1
DIM = 2
RED = 31
GREEN = 32
YELLOW = 33
BLUE = 34
MAGENTA = 35
CYAN = 36


def enable_vt() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        k = ctypes.windll.kernel32
        STD_OUTPUT_HANDLE = -11
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        handle = k.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.c_uint32()
        k.GetConsoleMode(handle, ctypes.byref(mode))
        k.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except (OSError, AttributeError, ValueError):
        pass


def color_enabled() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def style(text: str, *codes: int) -> str:
    if not color_enabled():
        return text
    return f"\033[{';'.join(map(str, codes))}m{text}\033[{RESET}m"
