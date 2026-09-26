"""全角 / 半角一键规范化。

原则：句法层一律半角（解析器要求）；引号内的自然语言文本默认不动，
仅在 `--范围 全部` 时按方向转换，且引号本身在文本层 MUST NOT 被转换
（转换会产生嵌套引号而破坏字符串）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from knot.core.diagnostic import Diagnostic
from knot.core.normalize import read_text_raw

DIRECTION_TO_HALF = "to_half"
DIRECTION_TO_FULL = "to_full"
DIRECTION_AUTO = "auto"

SCOPE_SYNTAX = "syntax"
SCOPE_ALL = "all"

_FULLWIDTH_BLOCK = {chr(code): chr(code - 0xFEE0) for code in range(0xFF01, 0xFF5F)}

SYNTAX_TO_HALF: dict[str, str] = {
    **_FULLWIDTH_BLOCK,
    "　": " ",
    "￥": "¥",
    "。": ".",
    "、": ",",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "《": "<",
    "》": ">",
    "【": "[",
    "】": "]",
    "～": "~",
}

TEXT_TO_HALF: dict[str, str] = {
    "，": ",",
    "。": ".",
    "！": "!",
    "？": "?",
    "：": ":",
    "；": ";",
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "《": "<",
    "》": ">",
    "、": ",",
    "～": "~",
}

TEXT_TO_FULL: dict[str, str] = {
    ",": "，",
    ".": "。",
    "!": "！",
    "?": "？",
    ":": "：",
    ";": "；",
    "(": "（",
    ")": "）",
    "[": "【",
    "]": "】",
    "~": "～",
}

_DIGIT_GUARDED = ".,"


@dataclass
class ConvertReport:
    text: str = ""
    changes: dict[str, int] = field(default_factory=dict)
    unclosed_lines: list[int] = field(default_factory=list)
    unbalanced_lines: list[int] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def change_count(self) -> int:
        return sum(self.changes.values())

    @property
    def changed(self) -> bool:
        return bool(self.changes) or bool(self.unclosed_lines) or bool(self.unbalanced_lines)


def _split_segments(line: str) -> tuple[list[tuple[str, bool]], bool]:
    """拆成 (文本, 是否在引号内) 段；返回是否以未闭合状态结束。"""
    segments: list[tuple[str, bool]] = []
    buffer: list[str] = []
    in_string = False
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if ch == "\\" and in_string and i + 1 < n:
            buffer.append(line[i : i + 2])
            i += 2
            continue
        if ch == '"':
            if in_string:
                segments.append(("".join(buffer), True))
                buffer = ['"']
                in_string = False
            else:
                buffer.append('"')
                segments.append(("".join(buffer), False))
                buffer = []
                in_string = True
            i += 1
            continue
        buffer.append(ch)
        i += 1
    if buffer:
        segments.append(("".join(buffer), in_string))
    return segments, in_string


def _apply(
    text: str, mapping: dict[str, str], guard_digits: bool = False
) -> tuple[str, dict[str, int]]:
    out: list[str] = []
    counts: dict[str, int] = {}
    for i, ch in enumerate(text):
        replacement = mapping.get(ch)
        if replacement is not None and guard_digits and ch in _DIGIT_GUARDED:
            prev_ch = text[i - 1] if i > 0 else ""
            next_ch = text[i + 1] if i + 1 < len(text) else ""
            if prev_ch.isdigit() and next_ch.isdigit():
                replacement = None
        if replacement is None:
            out.append(ch)
        else:
            out.append(replacement)
            key = f"{ch}→{replacement}"
            counts[key] = counts.get(key, 0) + 1
    return "".join(out), counts


def _merge(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + value


def _brace_balance(line: str) -> int:
    segments, _ = _split_segments(line)
    depth = 0
    for text, in_string in segments:
        if in_string:
            continue
        depth += text.count("{") - text.count("}")
    return depth


def convert_line(line: str, direction: str, scope: str) -> tuple[str, dict[str, int], bool, int]:
    segments, unclosed = _split_segments(line)
    counts: dict[str, int] = {}
    out: list[str] = []
    for text, in_string in segments:
        if in_string:
            if scope == SCOPE_ALL:
                mapping = TEXT_TO_FULL if direction == DIRECTION_TO_FULL else TEXT_TO_HALF
                converted, piece_counts = _apply(
                    text, mapping, guard_digits=direction == DIRECTION_TO_FULL
                )
                out.append(converted)
                _merge(counts, piece_counts)
            else:
                out.append(text)
            continue
        converted, piece_counts = _apply(text, SYNTAX_TO_HALF)
        out.append(converted)
        _merge(counts, piece_counts)
    return "".join(out), counts, unclosed, _brace_balance(line)


def convert_text(
    text: str,
    direction: str = DIRECTION_AUTO,
    scope: str = SCOPE_SYNTAX,
    fix_unclosed: bool = False,
    filename: str = "",
) -> ConvertReport:
    if direction == DIRECTION_AUTO:
        direction = DIRECTION_TO_HALF
    report = ConvertReport()
    lines = text.splitlines(keepends=True)
    converted_lines: list[str] = []
    for number, raw in enumerate(lines, start=1):
        newline = ""
        body = raw
        if raw.endswith("\r\n"):
            body, newline = raw[:-2], "\r\n"
        elif raw.endswith("\n"):
            body, newline = raw[:-1], "\n"

        line, counts, unclosed, brace = convert_line(body, direction, scope)
        _merge(report.changes, counts)

        if unclosed:
            report.unclosed_lines.append(number)
            if fix_unclosed:
                line += '"'
                report.changes["补全引号"] = report.changes.get("补全引号", 0) + 1
        if brace > 0:
            report.unbalanced_lines.append(number)
            if fix_unclosed:
                line += "}" * brace
                report.changes["补全花括号"] = report.changes.get("补全花括号", 0) + brace

        converted_lines.append(line + newline)

    report.text = "".join(converted_lines)

    for number in report.unclosed_lines:
        report.diagnostics.append(
            Diagnostic(
                level="warning",
                file=filename,
                line=number,
                col=1,
                message="字符串未闭合",
                suggestion="已补全引号" if fix_unclosed else "可加 --修复未闭合 自动补全",
            )
        )
    for number in report.unbalanced_lines:
        report.diagnostics.append(
            Diagnostic(
                level="warning",
                file=filename,
                line=number,
                col=1,
                message="花括号不配对",
                suggestion="已补全 }" if fix_unclosed else "可加 --修复未闭合 自动补全",
            )
        )
    return report


def convert_file(
    path: Path,
    direction: str = DIRECTION_AUTO,
    scope: str = SCOPE_SYNTAX,
    fix_unclosed: bool = False,
    write: bool = True,
) -> ConvertReport:
    text = read_text_raw(path)
    report = convert_text(
        text, direction=direction, scope=scope, fix_unclosed=fix_unclosed, filename=str(path)
    )
    if write and report.text != text:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(report.text, encoding="utf-8", newline="")
        tmp.replace(path)
    return report
