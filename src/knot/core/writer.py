from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from knot.core.amount import fmt_amount
from knot.core.lexer import DATE_LINE_RE
from knot.core.model import Flag, Posting, Transaction
from knot.core.normalize import read_text_raw
from knot.core.width import pad, str_width

POSTING_HEAD_RE = re.compile(r"^[ \t]+\S")


@dataclass
class Edit:
    line_start: int
    line_end: int
    new_lines: list[str]


def apply_edits(path: Path, edits: list[Edit]) -> None:
    text = read_text_raw(path) if path.exists() else ""
    lines = text.splitlines(keepends=True)
    applied_start: int | None = None
    for e in sorted(edits, key=lambda x: x.line_start, reverse=True):
        # 重叠编辑会互相吞掉对方的结果：按行号降序应用时，跳过与已应用区间相交的编辑
        if applied_start is not None and e.line_end >= applied_start:
            continue
        lines[e.line_start - 1 : e.line_end] = e.new_lines
        applied_start = e.line_start
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(lines), encoding="utf-8", newline="")
    tmp.replace(path)


def detect_style(path: Path) -> tuple[str, str]:
    indent, newline = "  ", "\n"
    if not path.exists():
        return indent, newline
    text = read_text_raw(path)
    if "\r\n" in text:
        newline = "\r\n"
    for line in text.splitlines():
        if line[:1] in (" ", "\t") and line.strip() and not line.lstrip().startswith(";"):
            indent = line[: len(line) - len(line.lstrip())]
            break
    return indent, newline


def render_cost(posting: Posting) -> str:
    cost = posting.cost
    if cost is None:
        return ""
    if cost.kind == "unit":
        return f" {{{cost.number} {cost.currency}}}"
    if cost.kind == "price":
        return f" @ {cost.number} {cost.currency}"
    return f" @@ {cost.number} {cost.currency}"


def render_transaction(tx: Transaction, indent: str = "  ", newline: str = "\n") -> list[str]:
    head = tx.date.isoformat()
    if tx.flag is not Flag.OK:
        head += f" {tx.flag.value}"
    if tx.payee is not None:
        head += f' "{tx.payee}"'
    if tx.narration:
        head += f' "{tx.narration}"'
    for tag in sorted(tx.tags):
        head += f" #{tag}"
    for link in sorted(tx.links):
        head += f" ^{link}"

    postings = [p for p in tx.postings if not p.generated]
    account_width = max((str_width(p.account) for p in postings), default=0)
    amounts = [fmt_amount(p.units.number) for p in postings if p.units is not None]
    amount_width = max((len(a) for a in amounts), default=0)

    lines = [head + newline]
    for key, value in tx.meta.items():
        lines.append(f"{indent}; {key}: {value}" + newline)
    for posting in postings:
        line = indent + pad(posting.account, account_width)
        if posting.units is not None:
            text = fmt_amount(posting.units.number)
            line += "  " + text.rjust(amount_width)
            if posting.units.currency:
                line += f" {posting.units.currency}"
        line += render_cost(posting)
        if posting.counterparty is not None:
            line += f"  @ {posting.counterparty}"
        lines.append(line.rstrip() + newline)
        for key, value in posting.meta.items():
            lines.append(f"{indent}; {key}: {value}" + newline)
    return lines


def target_year_file(ledger: Path, year: int, files: list[Path]) -> Path:
    """新增交易写入哪个文件：优先已被 include 的年份文件，否则写主账本。"""
    name = f"{year}.knot"
    for file in files:
        if file.name == name:
            return file
    return ledger


def find_insert_index(lines: list[str], when: date) -> int:
    for i, line in enumerate(lines):
        if line and not line[0].isspace() and DATE_LINE_RE.match(line):
            try:
                candidate = date.fromisoformat(line[:10])
            except ValueError:
                continue
            if candidate > when:
                return i
    return len(lines)


def insert_transaction(path: Path, tx: Transaction) -> None:
    indent, newline = detect_style(path)
    block = render_transaction(tx, indent, newline)

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(block), encoding="utf-8", newline="")
        return

    text = read_text_raw(path)
    lines = text.splitlines(keepends=True)
    idx = find_insert_index(lines, tx.date)

    if idx > 0 and lines[idx - 1].strip():
        block = [newline, *block]
    if idx == len(lines) and lines and not lines[-1].endswith(("\n", "\r")):
        block = [newline, *block]
    elif idx < len(lines) and lines[idx].strip():
        block = [*block, newline]

    apply_edits(path, [Edit(idx + 1, idx, block)])
