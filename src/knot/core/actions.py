"""写操作内核：CLI 与 Web 共用同一套记账/归类逻辑。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from knot.core.aliases import AliasTable
from knot.core.book import default_counterparty
from knot.core.date_cn import parse_date
from knot.core.lexer import is_account
from knot.core.model import Amount, Flag, Options, Posting, Transaction
from knot.core.normalize import KnotError, normalize_text
from knot.core.number_cn import parse_amount
from knot.core.rules import RuleTable
from knot.core.writer import insert_transaction, target_year_file


@dataclass
class EntryRequest:
    amount: str
    account: str
    from_account: str | None = None
    to_account: str | None = None
    when: str | None = None
    note: str = ""
    payee: str | None = None
    tags: tuple[str, ...] = ()
    flag: str = "*"
    sign: Decimal | None = None


@dataclass
class EntryResult:
    transaction: Transaction
    target: Path
    learned: bool = False
    warnings: list[str] = field(default_factory=list)


def resolve_account(aliases: AliasTable, text: str, what: str = "科目", accounts=None) -> str:
    cleaned = normalize_text(text).strip()
    resolution = aliases.resolve(cleaned, accounts)
    if resolution.target:
        return resolution.target
    if resolution.candidates:
        raise KnotError(f"{what}有多个候选，请写全名：{'、'.join(resolution.candidates)}")
    if is_account(cleaned):
        return cleaned
    raise KnotError(f"无法识别的{what}：{text}")


def build_transaction(
    request: EntryRequest,
    *,
    aliases: AliasTable,
    options: Options,
    today: date | None = None,
) -> Transaction:
    amount = parse_amount(request.amount)
    account = resolve_account(aliases, request.account)
    when = parse_date(request.when or "今天", today)

    root = account.split(":")[0]
    if request.sign is not None:
        sign = request.sign
        raw_counterparty = request.from_account or default_counterparty(account, options)
    elif root == "费用":
        sign = Decimal(1)
        raw_counterparty = request.from_account or options.default_asset
    elif root == "收入":
        sign = Decimal(-1)
        raw_counterparty = request.to_account or options.default_income
    elif request.to_account and not request.from_account:
        sign = Decimal(-1)
        raw_counterparty = request.to_account
    elif request.from_account:
        sign = Decimal(1)
        raw_counterparty = request.from_account
    else:
        sign = Decimal(1)
        raw_counterparty = default_counterparty(account, options)
    if raw_counterparty is None:
        raise KnotError("请指定对手科目（-f/--from 或 -t/--to）")
    counterparty = resolve_account(aliases, raw_counterparty, "对手科目")

    posting = Posting(
        account=account,
        units=Amount(sign * amount, options.operating_currency),
        counterparty=counterparty,
    )
    return Transaction(
        date=when,
        flag=Flag(request.flag) if request.flag else Flag.OK,
        payee=normalize_text(request.payee) if request.payee else None,
        narration=normalize_text(request.note or ""),
        postings=[posting],
        tags=frozenset(normalize_text(tag) for tag in request.tags),
    )


def write_entry(
    request: EntryRequest,
    *,
    ledger: Path,
    aliases: AliasTable,
    options: Options,
    rules: RuleTable | None = None,
    files: list[Path] | None = None,
    today: date | None = None,
) -> EntryResult:
    transaction = build_transaction(request, aliases=aliases, options=options, today=today)
    target = target_year_file(ledger, transaction.date.year, files or [])
    insert_transaction(target, transaction)

    learned = False
    if rules is not None and rules.path is not None and request.payee:
        learned = rules.learn(transaction.payee or "", transaction.postings[0].account)
    return EntryResult(transaction=transaction, target=target, learned=learned)


UNCATEGORIZED_ACCOUNT = "费用:待分类"


def reclassify(
    ledger: Path,
    *,
    aliases: AliasTable,
    payee: str,
    account: str,
    rules: RuleTable | None = None,
) -> tuple[int, list[Path]]:
    """把某个收款方的待分类交易整块改写为目标科目（逐块编辑，原子写回）。"""
    from knot.core.loader import load_book
    from knot.core.writer import Edit, apply_edits, detect_style, render_transaction

    target_account = resolve_account(aliases, account)
    _result, book, _diags = load_book(ledger)

    edits_by_file: dict[Path, list[Edit]] = {}
    changed = 0
    for transaction in book.transactions:
        if (transaction.payee or transaction.narration) != payee:
            continue
        touched = False
        for posting in transaction.postings:
            if posting.account == UNCATEGORIZED_ACCOUNT and not posting.generated:
                posting.account = target_account
                touched = True
        if (
            not touched
            or not transaction.src_file
            or transaction.src_line_end < transaction.src_line_start
        ):
            continue
        path = Path(transaction.src_file)
        indent, newline = detect_style(path)
        block = render_transaction(transaction, indent, newline)
        edits_by_file.setdefault(path, []).append(
            Edit(transaction.src_line_start, transaction.src_line_end, block)
        )
        changed += 1

    for path, edits in edits_by_file.items():
        apply_edits(path, edits)

    if rules is not None and rules.path is not None and payee and changed:
        rules.learn(payee, target_account)
    return changed, list(edits_by_file)
