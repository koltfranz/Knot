from __future__ import annotations

import re
from pathlib import Path

from knot.core.lexer import ACCOUNT_RE, DATE_LINE_RE
from knot.core.normalize import read_text_raw
from knot.core.width import pad, str_width
from knot.core.writer import detect_style

POSTING_RE = re.compile(
    rf"^(?P<indent>[ \t]+)(?P<account>{ACCOUNT_RE.pattern})[ \t]+"
    r"(?P<amount>-?\d[\d,]*(?:\.\d+)?)?[ \t]*(?P<tail>.*)$"
)


def _format_block(block: list[str], indent_hint: str | None) -> list[str]:
    parsed: list[tuple[str, tuple[str, str, str] | None]] = []
    for line in block[1:]:
        if line.lstrip().startswith(";"):
            parsed.append((line, None))
            continue
        m = POSTING_RE.match(line)
        if m is None or not m.group("amount"):
            parsed.append((line, None))
            continue
        parsed.append((line, (m.group("account"), m.group("amount"), m.group("tail").strip())))

    postings = [p for _, p in parsed if p is not None]
    if not postings:
        return block

    indent = indent_hint or "  "
    account_width = max(str_width(p[0]) for p in postings)
    amount_width = max(len(p[1]) for p in postings)
    result: list[str] = [block[0]]
    for line, parsed_posting in parsed:
        if parsed_posting is None:
            result.append(line)
            continue
        account, amount, tail = parsed_posting
        rebuilt = indent + pad(account, account_width) + "  " + amount.rjust(amount_width)
        if tail:
            rebuilt += f" {tail}"
        result.append(rebuilt.rstrip())
    return result


def format_text(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line and not line[0].isspace() and DATE_LINE_RE.match(line):
            block = [line]
            j = i + 1
            while j < len(lines) and lines[j].strip() and lines[j][0].isspace():
                block.append(lines[j])
                j += 1
            indent_hint = None
            for candidate in block[1:]:
                if candidate[:1] in (" ", "\t") and not candidate.lstrip().startswith(";"):
                    indent_hint = candidate[: len(candidate) - len(candidate.lstrip())]
                    break
            out.extend(_format_block(block, indent_hint))
            i = j
        else:
            out.append(line)
            i += 1
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def format_file(path: Path) -> bool:
    _, newline = detect_style(path)
    text = read_text_raw(path)
    formatted = format_text(text)
    if format_text(formatted) != formatted:
        raise ValueError(f"格式化结果不稳定，已跳过：{path}")
    if newline != "\n":
        formatted = formatted.replace("\n", newline)
    if formatted == text:
        return False
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(formatted, encoding="utf-8", newline="")
    tmp.replace(path)
    return True
