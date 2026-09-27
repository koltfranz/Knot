"""终端控制：VT 启用、尺寸、按键与鼠标事件、cooked 行输入。"""

from __future__ import annotations

import ctypes
import os
import re
import select
import shutil
import struct
import sys

IS_WINDOWS = sys.platform == "win32"

MOUSE_ON = "\033[?1000h\033[?1002h\033[?1006h"
MOUSE_OFF = "\033[?1000l\033[?1002l\033[?1006l"

KEY_ALIASES = {
    b"\x1b[A": "up",
    b"\x1b[B": "down",
    b"\x1b[C": "right",
    b"\x1b[D": "left",
    b"\x1b[5~": "pgup",
    b"\x1b[6~": "pgdn",
    b"\x1b[H": "home",
    b"\x1b[F": "end",
    b"\x1b[3~": "delete",
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
    "S": "delete",
}
NORMALIZE = {
    "\r": "enter",
    "\n": "enter",
    "\x7f": "backspace",
    "\x08": "backspace",
    "\x03": "quit",
    "\x1b": "esc",
}
VK_KEYS = {
    0x25: "left",
    0x26: "up",
    0x27: "right",
    0x28: "down",
    0x21: "pgup",
    0x22: "pgdn",
    0x24: "home",
    0x23: "end",
    0x2E: "delete",
}
MOUSE_BUTTONS = {0: "left", 1: "middle", 2: "right"}

CSI_MOUSE = re.compile(rb"\x1b\[<(\d+);(\d+);(\d+)([Mm])")
ESC_TIMEOUT = 0.05

STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11
ENABLE_PROCESSED_INPUT = 0x0001
ENABLE_LINE_INPUT = 0x0002
ENABLE_ECHO_INPUT = 0x0004
ENABLE_MOUSE_INPUT = 0x0010
ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_EXTENDED_FLAGS = 0x0080
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
FROM_LEFT_1ST_BUTTON_PRESSED = 0x0001
RIGHTMOST_BUTTON_PRESSED = 0x0002
SHIFT_PRESSED = 0x0010
LEFT_CTRL_PRESSED = 0x0008
RIGHT_CTRL_PRESSED = 0x0004
KEY_EVENT = 0x0001
MOUSE_EVENT = 0x0002
WINDOW_BUFFER_SIZE_EVENT = 0x0004
MOUSE_MOVED = 0x0001
MOUSE_WHEELED = 0x0004
INPUT_RECORD_SIZE = 20
SCREEN_BUFFER_INFO_SIZE = 22
PRESSED_BUTTONS = 0x0007

_ACTIVE_RAW: RawMode | None = None


def enable_vt() -> None:
    if not IS_WINDOWS:
        return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.c_uint32()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except (OSError, AttributeError, ValueError):
        pass


def size() -> tuple[int, int]:
    cols, rows = shutil.get_terminal_size((80, 24))
    return rows, cols


def is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def mouse_event(button: str, x: int, y: int, ctrl: bool = False, shift: bool = False) -> str:
    """鼠标事件的统一字符串形式：mouse:ctrl-left:34:7（1 基坐标）。"""
    modifiers = ["ctrl"] if ctrl else []
    if shift:
        modifiers.append("shift")
    return f"mouse:{'-'.join([*modifiers, button])}:{x}:{y}"


def mouse_event_from_code(code: int, x: int, y: int) -> str:
    """SGR 鼠标编码 → 事件字符串（b&3 按钮、b&64 滚轮、b&32 拖拽、b&16/4 修饰键）。"""
    button_code = code & 0b11
    ctrl = bool(code & 16)
    shift = bool(code & 4)
    if code & 64:
        button = "wheel-up" if button_code == 0 else "wheel-down"
    else:
        button = MOUSE_BUTTONS.get(button_code, "left")
        if code & 32:
            button = f"drag-{button}"
    return mouse_event(button, x, y, ctrl=ctrl, shift=shift)


def parse_escape(seq: bytes) -> str:
    """ESC 序列 → 键名或鼠标事件；鼠标释放事件返回空串。"""
    match = CSI_MOUSE.fullmatch(seq)
    if match:
        code, x, y, final = match.groups()
        if final == b"m":
            return ""
        return mouse_event_from_code(int(code), int(x), int(y))
    return KEY_ALIASES.get(seq, "esc")


def parse_console_record(data: bytes, origin: tuple[int, int] = (0, 0)) -> str:
    """Windows 控制台 INPUT_RECORD 字节 → 事件字符串（空串表示忽略）。"""
    event_type = struct.unpack_from("<H", data, 0)[0]
    if event_type == KEY_EVENT:
        if not struct.unpack_from("<i", data, 4)[0]:
            return ""
        vk = struct.unpack_from("<H", data, 10)[0]
        char = struct.unpack_from("<H", data, 14)[0]
        return _key_from_console(vk, chr(char) if char else "")
    if event_type == MOUSE_EVENT:
        x, y = struct.unpack_from("<hh", data, 4)
        buttons = struct.unpack_from("<I", data, 8)[0]
        control = struct.unpack_from("<I", data, 12)[0]
        flags = struct.unpack_from("<I", data, 16)[0]
        return mouse_from_console(x, y, buttons, control, flags, origin)
    if event_type == WINDOW_BUFFER_SIZE_EVENT:
        return "resize"
    return ""


def _key_from_console(vk: int, char: str) -> str:
    """Windows 键事件 → 键名（有字符就按字符走，否则查虚拟键码表）。"""
    if char:
        return NORMALIZE.get(char, char)
    return VK_KEYS.get(vk, "")


def mouse_from_console(
    x: int, y: int, buttons: int, control: int, flags: int, origin: tuple[int, int] = (0, 0)
) -> str:
    """Windows 鼠标事件 → 事件字符串（缓冲坐标经视口原点换算）。"""
    column = x - origin[0] + 1
    row = y - origin[1] + 1
    ctrl = bool(control & (LEFT_CTRL_PRESSED | RIGHT_CTRL_PRESSED))
    shift = bool(control & SHIFT_PRESSED)
    if flags & MOUSE_WHEELED:
        delta = (buttons >> 16) & 0xFFFF
        if delta >= 0x8000:
            delta -= 0x10000
        if delta == 0:
            return ""
        return mouse_event("wheel-up" if delta > 0 else "wheel-down", column, row, ctrl, shift)
    if not buttons & PRESSED_BUTTONS:
        return ""
    if buttons & FROM_LEFT_1ST_BUTTON_PRESSED:
        button = "left"
    elif buttons & RIGHTMOST_BUTTON_PRESSED:
        button = "right"
    else:
        button = "middle"
    if flags & MOUSE_MOVED:
        button = f"drag-{button}"
    return mouse_event(button, column, row, ctrl, shift)


def _read_escape(fd: int) -> bytes:
    """读取以 ESC 起始的完整序列（CSI 到终止字节为止；裸 ESC 用超时兜底）。"""
    data = b"\x1b"
    if not select.select([fd], [], [], ESC_TIMEOUT)[0]:
        return data
    nxt = os.read(fd, 1)
    data += nxt
    if nxt not in (b"[", b"O"):
        return data
    while len(data) < 16:
        if not select.select([fd], [], [], ESC_TIMEOUT)[0]:
            break
        chunk = os.read(fd, 1)
        if not chunk:
            break
        data += chunk
        if 0x40 <= chunk[0] <= 0x7E:
            break
    return data


def cooked_line(prompt: str = "") -> str:
    """切换到 cooked（规范）模式读取一行，保证中文输入法可用。"""
    active = _ACTIVE_RAW
    if active is not None:
        active.suspend()
    try:
        if prompt:
            sys.stdout.write(prompt)
            sys.stdout.flush()
        return input()
    finally:
        if active is not None:
            active.resume()


def _handle(kind: int):
    kernel32 = ctypes.windll.kernel32
    kernel32.GetStdHandle.restype = ctypes.c_void_p
    return ctypes.c_void_p(kernel32.GetStdHandle(kind))


def _viewport_origin() -> tuple[int, int]:
    try:
        kernel32 = ctypes.windll.kernel32
        buffer = ctypes.create_string_buffer(SCREEN_BUFFER_INFO_SIZE)
        if kernel32.GetConsoleScreenBufferInfo(_handle(STD_OUTPUT_HANDLE), buffer):
            return struct.unpack_from("<hh", buffer, 10)
    except (OSError, AttributeError, ValueError):
        pass
    return 0, 0


def _read_windows_event() -> str | None:
    """读取一个控制台事件（键或鼠标）；不可用时返回 None 以回退 msvcrt。"""
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.ReadConsoleInputW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        kernel32.ReadConsoleInputW.restype = ctypes.c_int
        handle = _handle(STD_INPUT_HANDLE)
        buffer = ctypes.create_string_buffer(INPUT_RECORD_SIZE)
        read = ctypes.c_uint32()
        while True:
            if not kernel32.ReadConsoleInputW(handle, buffer, 1, ctypes.byref(read)):
                return None
            event = parse_console_record(buffer.raw, _viewport_origin())
            if event:
                return event
    except (OSError, AttributeError, ValueError):
        return None


def _read_key_msvcrt() -> str:
    import msvcrt

    char = msvcrt.getwch()
    if char in ("\x00", "\xe0"):
        return WINDOWS_KEYS.get(msvcrt.getwch(), "")
    return NORMALIZE.get(char, char)


def read_key() -> str:
    """读取一个事件：键名、鼠标事件字符串，或字符本身。"""
    if IS_WINDOWS:
        event = _read_windows_event()
        return event if event is not None else _read_key_msvcrt()
    fd = sys.stdin.fileno()
    while True:
        data = os.read(fd, 1)
        if data == b"\x1b":
            event = parse_escape(_read_escape(fd))
            if event:
                return event
            continue
        char = data.decode("utf-8", "replace")
        return NORMALIZE.get(char, char)


def _enable_windows_raw() -> int | None:
    """关回显/行输入、开鼠标输入、关快速编辑；返回旧模式以便恢复。"""
    try:
        kernel32 = ctypes.windll.kernel32
        handle = _handle(STD_INPUT_HANDLE)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return None
        saved = int(mode.value)
        new_mode = saved & ~(
            ENABLE_ECHO_INPUT | ENABLE_LINE_INPUT | ENABLE_PROCESSED_INPUT | ENABLE_QUICK_EDIT_MODE
        )
        new_mode |= ENABLE_MOUSE_INPUT | ENABLE_EXTENDED_FLAGS
        kernel32.SetConsoleMode(handle, ctypes.c_uint32(new_mode))
        return saved
    except (OSError, AttributeError, ValueError):
        return None


def _restore_windows_mode(saved: int) -> None:
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(_handle(STD_INPUT_HANDLE), ctypes.c_uint32(saved))
    except (OSError, AttributeError, ValueError):
        pass


class RawMode:
    """raw 模式：POSIX 用 termios，Windows 用控制台模式；同时开启鼠标上报。"""

    def __init__(self) -> None:
        self._saved = None
        self._saved_mode: int | None = None
        self._mouse = False

    def __enter__(self):
        global _ACTIVE_RAW
        if sys.stdout.isatty():
            self._mouse = True
            sys.stdout.write(MOUSE_ON)
            sys.stdout.flush()
        if IS_WINDOWS:
            self._saved_mode = _enable_windows_raw()
        elif sys.stdin.isatty():
            import termios
            import tty

            self._saved = termios.tcgetattr(sys.stdin.fileno())
            tty.setraw(sys.stdin.fileno())
        _ACTIVE_RAW = self
        return self

    def __exit__(self, *exc_info) -> None:
        self.restore()

    def suspend(self) -> None:
        """暂时恢复 cooked 模式（读取中文输入时用）。"""
        if self._mouse:
            sys.stdout.write(MOUSE_OFF)
            sys.stdout.flush()
        if self._saved is not None:
            import termios

            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._saved)
        if self._saved_mode is not None:
            _restore_windows_mode(self._saved_mode)

    def resume(self) -> None:
        if IS_WINDOWS:
            self._saved_mode = _enable_windows_raw() or self._saved_mode
        elif self._saved is not None:
            import tty

            tty.setraw(sys.stdin.fileno())
        if self._mouse:
            sys.stdout.write(MOUSE_ON)
            sys.stdout.flush()

    def restore(self) -> None:
        global _ACTIVE_RAW
        if self._mouse:
            sys.stdout.write(MOUSE_OFF)
            sys.stdout.flush()
            self._mouse = False
        if self._saved is not None:
            import termios

            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._saved)
            self._saved = None
        if self._saved_mode is not None:
            _restore_windows_mode(self._saved_mode)
            self._saved_mode = None
        _ACTIVE_RAW = None
