from __future__ import annotations

import contextlib
import os
import sys


def setup_console() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    if sys.platform == "win32":
        try:
            import ctypes

            k = ctypes.windll.kernel32
            k.SetConsoleCP(65001)
            k.SetConsoleOutputCP(65001)
        except (OSError, AttributeError):
            pass

    for stream, errors in ((sys.stdout, "replace"), (sys.stderr, "replace")):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8", errors=errors)
