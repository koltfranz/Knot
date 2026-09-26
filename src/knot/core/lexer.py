from __future__ import annotations

import re
from dataclasses import dataclass

from knot.core.diagnostic import Diagnostic
from knot.core.keywords import DIRECTIVE_LOOKUP

ACCOUNT_CHARS = (
    r"\u4e00-\u9fff"
    r"\u3400-\u4dbf"
    r"\uf900-\ufaff"
    r"A-Za-z0-9_\-"
)
ACCOUNT_RE = re.compile(f"[{ACCOUNT_CHARS}]+(:[{ACCOUNT_CHARS}]+)*")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DATE_LINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\b")
FLAG_RE = re.compile(r"[*!?P]")
NUMBER_RE = re.compile(r"-?\d[\d,]*(\.\d+)?")
CURRENCY_RE = re.compile(r"[A-Z][A-Z0-9]{1,7}")

ROOTS = ("资产", "负债", "权益", "收入", "费用")

KEYWORDS = tuple(sorted(DIRECTIVE_LOOKUP))

TOKEN_RE = re.compile(
    r"(?P<ws>[ \t]+)"
    r"|(?P<comment>;.*)"
    r'|(?P<string>"(?:[^"\\]|\\.)*"?)'
    r'|(?P<tag>\#[^\s;"]*)'
    r'|(?P<link>\^[^\s;"]*)'
    r"|(?P<atat>@@)"
    r"|(?P<at>@)"
    r"|(?P<lbrace>\{)"
    r"|(?P<rbrace>\})"
    r'|(?P<word>[^\s;"@#^{}]+)'
)


@dataclass(slots=True)
class Token:
    kind: str
    text: str
    line: int
    col: int


def _unescape(text: str) -> str:
    return text.replace('\\"', '"').replace("\\\\", "\\")


def is_closed_string(raw: str) -> bool:
    return len(raw) >= 2 and raw.endswith('"')


def lex_line(text: str, line_no: int) -> tuple[list[Token], list[Diagnostic]]:
    tokens: list[Token] = []
    diags: list[Diagnostic] = []
    pos = 0
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if m is None:
            diags.append(
                Diagnostic(
                    level="error",
                    file="",
                    line=line_no,
                    col=pos + 1,
                    message=f"无法识别的字符：{text[pos]!r}",
                    snippet=text,
                    caret=text[pos],
                )
            )
            pos += 1
            continue
        pos = m.end()
        kind = m.lastgroup
        raw = m.group()
        if kind == "ws":
            continue
        if kind == "string":
            if not is_closed_string(raw):
                diags.append(
                    Diagnostic(
                        level="error",
                        file="",
                        line=line_no,
                        col=m.start() + 1,
                        message="字符串未闭合",
                        snippet=text,
                        caret=raw,
                    )
                )
                if raw == '"':
                    continue
            tokens.append(
                Token(
                    "string",
                    _unescape(raw[1:-1] if is_closed_string(raw) else raw[1:]),
                    line_no,
                    m.start() + 1,
                )
            )
            continue
        if kind == "tag":
            tokens.append(Token("tag", raw[1:], line_no, m.start() + 1))
            continue
        if kind == "link":
            tokens.append(Token("link", raw[1:], line_no, m.start() + 1))
            continue
        tokens.append(Token(kind, raw, line_no, m.start() + 1))
    return tokens, diags


def is_date(text: str) -> bool:
    return bool(DATE_RE.fullmatch(text))


def is_flag(text: str) -> bool:
    return bool(FLAG_RE.fullmatch(text))


def is_number(text: str) -> bool:
    return bool(NUMBER_RE.fullmatch(text))


def is_currency(text: str) -> bool:
    return bool(CURRENCY_RE.fullmatch(text))


def is_account(text: str) -> bool:
    return bool(ACCOUNT_RE.fullmatch(text))
