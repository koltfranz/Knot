from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from knot.core.model import Transaction


@dataclass
class Filter:
    account: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    tags: frozenset[str] = frozenset()
    payee: str | None = None
    min_amount: Decimal | None = None
    currency: str | None = None
    limit: int | None = None
    keywords: list[str] = field(default_factory=list)


def _account_match(name: str, account: str) -> bool:
    return name == account or name.startswith(account + ":")


def match(tx: Transaction, f: Filter) -> bool:
    if f.date_from is not None and tx.date < f.date_from:
        return False
    if f.date_to is not None and tx.date > f.date_to:
        return False
    if f.tags and not (tx.tags & f.tags):
        return False
    if f.payee:
        haystack = f"{tx.payee or ''} {tx.narration}"
        if f.payee not in haystack:
            return False
    for keyword in f.keywords:
        haystack = f"{tx.payee or ''} {tx.narration} {' '.join(p.account for p in tx.postings)}"
        if keyword not in haystack:
            return False
    if f.account and not any(_account_match(p.account, f.account) for p in tx.postings):
        return False
    if f.currency and not any(p.units and (p.units.currency == f.currency) for p in tx.postings):
        return False
    if f.min_amount is not None:
        return any(p.units and abs(p.units.number) >= f.min_amount for p in tx.postings)
    return True


def select(transactions: list[Transaction], f: Filter) -> list[Transaction]:
    result = [tx for tx in transactions if match(tx, f)]
    if f.limit is not None:
        result = result[-f.limit :]
    return result
