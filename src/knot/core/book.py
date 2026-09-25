from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from knot.core.aliases import AliasTable
from knot.core.amount import TOLERANCE, fmt_amount, is_zero
from knot.core.diagnostic import Diagnostic
from knot.core.lexer import ROOTS
from knot.core.model import (
    Amount,
    Balance,
    Directive,
    Open,
    Options,
    Posting,
    Transaction,
)
from knot.core.recur import expand_recur

Suggestions = dict[str, str]


def _diag(
    sources: dict[str, list[str]],
    level: str,
    file: str,
    line: int,
    col: int,
    message: str,
    caret: str | None = None,
    suggestion: str | None = None,
) -> Diagnostic:
    lines = sources.get(file)
    snippet = lines[line - 1] if lines and 0 < line <= len(lines) else None
    return Diagnostic(
        level=level,
        file=file,
        line=line,
        col=col,
        message=message,
        suggestion=suggestion,
        snippet=snippet,
        caret=caret,
    )


def _suggest(name: str, known: list[str]) -> str | None:
    matches = difflib.get_close_matches(name, known, n=1, cutoff=0.6)
    if not matches:
        return None
    ratio = difflib.SequenceMatcher(None, name, matches[0]).ratio()
    return f'是否意为 "{matches[0]}"？（相似度 {ratio:.2f}）'


@dataclass
class Book:
    directives: list[Directive]
    options: Options
    accounts: dict[str, Open]
    transactions: list[Transaction]
    sources: dict[str, list[str]] = field(default_factory=dict)

    def default_currency(self, account: str) -> str:
        opened = self.accounts.get(account)
        if opened and opened.currencies:
            return opened.currencies[0]
        return self.options.operating_currency

    def used_accounts(self) -> list[str]:
        names: set[str] = set(self.accounts)
        for tx in self.transactions:
            for posting in tx.postings:
                names.add(posting.account)
        return sorted(names)

    def balance_of(
        self, account: str, upto: date | None = None, include_children: bool = True
    ) -> dict[str, Decimal]:
        totals: dict[str, Decimal] = {}
        for tx in self.transactions:
            if upto is not None and tx.date > upto:
                continue
            for posting in tx.postings:
                if posting.units is None:
                    continue
                name = posting.account
                if name != account and not (include_children and name.startswith(account + ":")):
                    continue
                currency = posting.units.currency or self.default_currency(name)
                totals[currency] = totals.get(currency, Decimal(0)) + posting.units.number
        return totals

    def root_totals(self) -> dict[str, dict[str, Decimal]]:
        return {root: self.balance_of(root) for root in ROOTS}

    def net_worth(self) -> dict[str, Decimal]:
        assets = self.balance_of("资产")
        liabilities = self.balance_of("负债")
        totals = dict(assets)
        for currency, value in liabilities.items():
            totals[currency] = totals.get(currency, Decimal(0)) + value
        return totals

    def summary(self) -> dict:
        balances: dict[str, str] = {}
        for name in self.used_accounts():
            for currency, value in self.balance_of(name, include_children=False).items():
                if not is_zero(value):
                    balances[f"{name} {currency}"] = fmt_amount(value)
        totals = self.root_totals()
        return {
            "交易数": len(self.transactions),
            "科目余额": dict(sorted(balances.items())),
            "收入": {c: fmt_amount(v) for c, v in sorted(totals["收入"].items())},
            "支出": {c: fmt_amount(v) for c, v in sorted(totals["费用"].items())},
            "净资产": {c: fmt_amount(v) for c, v in sorted(self.net_worth().items())},
        }


def _resolve_name(aliases: AliasTable, name: str) -> str:
    resolution = aliases.resolve(name)
    return resolution.target or name


def build(
    directives: list[Directive],
    options: Options,
    sources: dict[str, list[str]] | None = None,
    aliases: AliasTable | None = None,
) -> tuple[Book, list[Diagnostic]]:
    sources = sources or {}
    diags: list[Diagnostic] = []
    aliases = aliases or AliasTable()

    directives = expand_recur(directives)
    directives.sort(key=lambda d: (getattr(d, "date", date.max), getattr(d, "src_line_start", 0)))

    accounts: dict[str, Open] = {}
    transactions: list[Transaction] = []
    for directive in directives:
        if isinstance(directive, Open):
            directive.account = _resolve_name(aliases, directive.account)
            accounts[directive.account] = directive
        elif isinstance(directive, Balance):
            directive.account = _resolve_name(aliases, directive.account)
        elif isinstance(directive, Transaction):
            transactions.append(directive)
            for posting in directive.postings:
                posting.account = _resolve_name(aliases, posting.account)
                if posting.counterparty:
                    posting.counterparty = _resolve_name(aliases, posting.counterparty)

    book = Book(directives, options, accounts, transactions, sources)
    auto_open_accounts(book, diags)
    balance_single_legs(book, diags)
    check_balance(book, diags)
    check_inventory(book, diags)
    check_assertions(book, diags)
    check_identity(book, diags)
    return book, diags


def auto_open_accounts(book: Book, diags: list[Diagnostic]) -> None:
    declared = set(book.accounts)
    known = sorted(declared)
    reported: set[str] = set()
    for tx in book.transactions:
        for posting in tx.postings:
            name = posting.account
            if name in declared or name in reported:
                continue
            reported.add(name)
            if book.options.strict == "on":
                level, message = "error", f"科目未声明：{name}"
            elif book.options.strict == "warn":
                level, message = "warning", f"未声明科目：{name}"
            else:
                level, message = "hint", f"自动开立科目：{name}"
            diags.append(
                _diag(
                    book.sources,
                    level,
                    tx.src_file,
                    tx.src_line_start,
                    1,
                    message,
                    caret=name,
                    suggestion=_suggest(name, known),
                )
            )
            known.append(name)
            known.sort()


def default_counterparty(account: str, options: Options) -> str | None:
    root = account.split(":")[0]
    if root == "费用":
        return options.default_asset
    if root == "收入":
        return options.default_income
    return None


def balance_single_legs(book: Book, diags: list[Diagnostic]) -> None:
    for tx in book.transactions:
        real = [p for p in tx.postings if not p.generated]
        blanks = [p for p in real if p.units is None]

        if len(real) == 1:
            posting = real[0]
            if posting.units is None:
                diags.append(
                    _diag(
                        book.sources,
                        "error",
                        tx.src_file,
                        tx.src_line_start,
                        1,
                        "单腿交易缺少金额",
                        caret=posting.account,
                    )
                )
                continue
            counterparty = posting.counterparty or default_counterparty(
                posting.account, book.options
            )
            if counterparty is None:
                diags.append(
                    _diag(
                        book.sources,
                        "error",
                        tx.src_file,
                        tx.src_line_start,
                        1,
                        f"单腿交易缺少 @ 对手科目：{posting.account}",
                        caret=posting.account,
                    )
                )
                continue
            currency = posting.units.currency or book.default_currency(posting.account)
            posting.units = Amount(posting.units.number, currency)
            tx.postings.append(
                Posting(
                    account=counterparty,
                    units=Amount(-posting.units.number, currency),
                    generated=True,
                )
            )
            continue

        if not blanks:
            continue
        if len(blanks) > 1:
            diags.append(
                _diag(
                    book.sources,
                    "error",
                    tx.src_file,
                    tx.src_line_start,
                    1,
                    "多于一腿金额留空，无法自动配平",
                    caret=blanks[0].account,
                )
            )
            continue

        others = [p for p in real if p.units is not None]
        currency = next(
            (p.units.currency for p in others if p.units and p.units.currency),
            book.default_currency(others[0].account) if others else book.options.operating_currency,
        )
        total = sum(
            (
                p.units.number
                for p in others
                if p.units and (p.units.currency or book.default_currency(p.account)) == currency
            ),
            Decimal(0),
        )
        blanks[0].units = Amount(-total, currency)


def _cost_value(posting: Posting) -> Decimal | None:
    if posting.cost is None or posting.units is None:
        return None
    if posting.cost.kind == "total":
        return posting.cost.number
    return abs(posting.units.number) * posting.cost.number


def _currency_entries(book: Book, posting: Posting) -> list[tuple[str, Decimal]]:
    """把一条分录折算为若干（币种, 金额）项；带成本的分录按成本币种计价。"""
    if posting.units is None:
        return []
    value = _cost_value(posting)
    if value is None:
        currency = posting.units.currency or book.default_currency(posting.account)
        return [(currency, posting.units.number)]
    cost_currency = posting.cost.currency or book.options.operating_currency
    sign = Decimal(1) if posting.units.number >= 0 else Decimal(-1)
    return [(cost_currency, sign * value)]


def check_balance(book: Book, diags: list[Diagnostic]) -> None:
    for tx in book.transactions:
        sums: dict[str, Decimal] = {}
        commodity: set[str] = set()
        for posting in tx.postings:
            if posting.units is None:
                continue
            if posting.cost is not None and posting.units.currency:
                commodity.add(posting.units.currency)
            for currency, value in _currency_entries(book, posting):
                sums[currency] = sums.get(currency, Decimal(0)) + value
        for currency, total in sorted(sums.items()):
            if currency in commodity or is_zero(total):
                continue
            diags.append(
                _diag(
                    book.sources,
                    "error",
                    tx.src_file,
                    tx.src_line_start,
                    1,
                    f"借贷不平衡：合计 {fmt_amount(total)} {currency}",
                    caret=tx.narration or None,
                )
            )


def check_inventory(book: Book, diags: list[Diagnostic]) -> None:
    for tx in book.transactions:
        for posting in tx.postings:
            if posting.cost is not None and posting.cost.number <= 0:
                diags.append(
                    _diag(
                        book.sources,
                        "error",
                        tx.src_file,
                        tx.src_line_start,
                        1,
                        f"成本必须为正数：{posting.account}",
                        caret=posting.account,
                    )
                )


def check_assertions(book: Book, diags: list[Diagnostic]) -> None:
    for directive in book.directives:
        if not isinstance(directive, Balance):
            continue
        currency = directive.amount.currency or book.default_currency(directive.account)
        actual = book.balance_of(directive.account, upto=directive.date).get(currency, Decimal(0))
        if abs(actual - directive.amount.number) < TOLERANCE:
            continue
        diags.append(
            _diag(
                book.sources,
                "error",
                directive.src_file,
                directive.src_line_start,
                1,
                f"余额断言失败：{directive.account} 在 {directive.date} 应为 "
                f"{fmt_amount(directive.amount.number)} {currency}，"
                f"实际为 {fmt_amount(actual)} {currency}",
                caret=directive.account,
            )
        )


def check_identity(book: Book, diags: list[Diagnostic]) -> None:
    totals: dict[str, Decimal] = {}
    for tx in book.transactions:
        for posting in tx.postings:
            for currency, value in _currency_entries(book, posting):
                totals[currency] = totals.get(currency, Decimal(0)) + value
    for currency, total in sorted(totals.items()):
        if is_zero(total):
            continue
        file = next(iter(book.sources), "")
        diags.append(
            Diagnostic(
                level="error",
                file=file,
                line=1,
                col=1,
                message=f"会计恒等式不成立：全部科目合计 {fmt_amount(total)} {currency}",
            )
        )
