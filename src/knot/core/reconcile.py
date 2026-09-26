"""对账：账本与账单（银行/信用卡）核对，标记已对账交易并写入余额断言。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from knot.core.amount import fmt_amount
from knot.core.book import Book
from knot.core.model import Balance, Flag, Transaction


@dataclass
class ReconcileReport:
    account: str
    as_of: date
    ledger_balance: Decimal
    statement_balance: Decimal | None = None
    difference: Decimal | None = None
    pending: list[Transaction] = field(default_factory=list)
    pending_total: Decimal = Decimal(0)
    cleared: int = 0
    generated: int = 0

    @property
    def balanced(self) -> bool:
        return self.difference is not None and abs(self.difference) < Decimal("0.005")

    @property
    def suggestion(self) -> str:
        if self.statement_balance is None:
            return "给出 --余额 即可计算差额"
        if self.balanced:
            return "账实相符，可用 --标记 把待对账交易标为 P"
        if self.difference is not None and -self.difference == self.pending_total:
            return "差额正好等于待对账合计：标记这些交易即可对齐"
        return "差额与待对账合计不一致，请核对漏记或未达账项"


def reconcile(
    book: Book,
    account: str,
    statement_balance: Decimal | None = None,
    as_of: date | None = None,
    limit: int = 20,
) -> ReconcileReport:
    from knot.core.recur import is_generated

    when = as_of or (max((tx.date for tx in book.transactions), default=date.today()))
    currency = book.options.operating_currency
    balances = book.balance_of(account, upto=when)
    ledger_balance = balances.get(currency, Decimal(0))

    report = ReconcileReport(
        account=account,
        as_of=when,
        ledger_balance=ledger_balance,
        statement_balance=statement_balance,
    )
    if statement_balance is not None:
        report.difference = statement_balance - ledger_balance

    for tx in book.transactions:
        if tx.date > when:
            continue
        if not any(
            posting.account == account or posting.account.startswith(account + ":")
            for posting in tx.postings
        ):
            continue
        if tx.flag is Flag.CLEARED:
            report.cleared += 1
            continue
        if is_generated(tx):
            # 定期模板展开出的交易没有独立源行，不参与对账标记
            report.generated += 1
            continue
        report.pending.append(tx)

    report.pending.sort(key=lambda tx: tx.date, reverse=True)
    report.pending = report.pending[:limit]
    report.pending_total = sum(
        (
            posting.units.number
            for tx in report.pending
            for posting in tx.postings
            if posting.units
            and (posting.account == account or posting.account.startswith(account + ":"))
        ),
        Decimal(0),
    )
    return report


def render_report(report: ReconcileReport, currency: str = "CNY") -> str:
    lines = [
        f"科目：{report.account}    截止：{report.as_of.isoformat()}",
        f"账本余额：{fmt_amount(report.ledger_balance)} {currency}",
    ]
    if report.statement_balance is not None:
        lines.append(f"账单余额：{fmt_amount(report.statement_balance)} {currency}")
        lines.append(f"差额：{fmt_amount(report.difference or Decimal(0))} {currency}")
    lines.append(
        f"已对账 {report.cleared} 笔，待对账 {len(report.pending)} 笔"
        f"（合计 {fmt_amount(report.pending_total)}）"
    )
    for tx in report.pending:
        amount = next(
            (
                fmt_amount(posting.units.number)
                for posting in tx.postings
                if posting.units and report.account in posting.account
            ),
            "—",
        )
        lines.append(f"  {tx.date.isoformat()} {tx.payee or tx.narration or '—'}  {amount}")
    lines.append("建议：" + report.suggestion)
    return "\n".join(lines)


def balance_assertion(book: Book, account: str, amount: Decimal, as_of: date) -> Balance:
    """生成一条余额断言指令（供写入年份文件）。"""
    from knot.core.model import Amount

    return Balance(
        date=as_of, account=account, amount=Amount(amount, book.options.operating_currency)
    )


def mark_cleared(transactions: list[Transaction]) -> int:
    """把交易标记为已对账（`P`），整块重写、原子写回。

    定期模板展开出的交易没有独立源行（其区间指向模板），MUST NOT 改写；
    同一源行区间只处理一次，避免重叠编辑。
    """
    from knot.core.recur import is_generated
    from knot.core.writer import Edit, apply_edits, detect_style, render_transaction

    edits_by_file: dict[Path, list[Edit]] = {}
    seen_blocks: set[tuple[str, int, int]] = set()
    for transaction in transactions:
        if is_generated(transaction):
            continue
        if not transaction.src_file or transaction.src_line_end < transaction.src_line_start:
            continue
        block_key = (transaction.src_file, transaction.src_line_start, transaction.src_line_end)
        if block_key in seen_blocks:
            continue
        seen_blocks.add(block_key)
        transaction.flag = Flag.CLEARED
        path = Path(transaction.src_file)
        indent, newline = detect_style(path)
        edits_by_file.setdefault(path, []).append(
            Edit(
                transaction.src_line_start,
                transaction.src_line_end,
                render_transaction(transaction, indent, newline),
            )
        )

    for path, edits in edits_by_file.items():
        apply_edits(path, edits)
    return sum(len(edits) for edits in edits_by_file.values())


def write_assertion(ledger: Path, assertion: Balance, files: list[Path]) -> Path:
    """把余额断言写入对应年份文件（按日期位置插入，沿用文件关键字语言）。"""
    from knot.core.keywords import detect_language, directive_spelling
    from knot.core.normalize import read_text_raw
    from knot.core.writer import (
        Edit,
        apply_edits,
        detect_style,
        find_insert_index,
        target_year_file,
    )

    target = target_year_file(ledger, assertion.date.year, files)
    _indent, newline = detect_style(target)
    existing = read_text_raw(target) if target.exists() else ""
    language = detect_language(existing.splitlines()) if existing else "zh"
    keyword = directive_spelling("balance", language)
    line = (
        f"{assertion.date.isoformat()} {keyword} {assertion.account} "
        f"{fmt_amount(assertion.amount.number)} {assertion.amount.currency}"
    )

    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(line + newline, encoding="utf-8", newline="")
        return target

    lines = existing.splitlines(keepends=True)
    index = find_insert_index(lines, assertion.date)
    block = [line + newline]
    if index > 0 and lines[index - 1].strip():
        block = [newline, *block]
    if index < len(lines) and lines[index].strip():
        block = [*block, newline]
    apply_edits(target, [Edit(index + 1, index, block)])
    return target
