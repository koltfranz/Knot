from __future__ import annotations

import unicodedata


def char_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def str_width(s: str) -> int:
    return sum(char_width(c) for c in s)


def pad(s: str, width: int, align: str = "left") -> str:
    n = max(0, width - str_width(s))
    return s + " " * n if align == "left" else " " * n + s


def truncate(s: str, width: int, ellipsis: str = "…") -> str:
    if str_width(s) <= width:
        return s
    w, out = 0, []
    for c in s:
        cw = char_width(c)
        if w + cw > width - str_width(ellipsis):
            break
        out.append(c)
        w += cw
    return "".join(out) + ellipsis
