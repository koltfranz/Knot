from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from knot.core.keywords import canonical_option_key, canonical_option_value


class Flag(StrEnum):
    OK = "*"
    PENDING = "!"
    UNKNOWN = "?"
    CLEARED = "P"


@dataclass(frozen=True, slots=True)
class Amount:
    number: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class Cost:
    number: Decimal
    currency: str
    kind: str = "unit"
    date: date | None = None


@dataclass(slots=True)
class Posting:
    account: str
    units: Amount | None = None
    cost: Cost | None = None
    counterparty: str | None = None
    meta: dict[str, str] = field(default_factory=dict)
    generated: bool = False


@dataclass(slots=True)
class Transaction:
    date: date
    flag: Flag
    payee: str | None
    narration: str
    postings: list[Posting]
    tags: frozenset[str] = frozenset()
    links: frozenset[str] = frozenset()
    meta: dict[str, str] = field(default_factory=dict)
    src_file: str = ""
    src_line_start: int = 0
    src_line_end: int = 0


@dataclass(slots=True)
class Balance:
    date: date
    account: str
    amount: Amount
    src_file: str = ""
    src_line_start: int = 0
    src_line_end: int = 0


@dataclass(slots=True)
class Open:
    date: date
    account: str
    currencies: tuple[str, ...] = ()
    meta: dict[str, str] = field(default_factory=dict)
    src_file: str = ""
    src_line_start: int = 0
    src_line_end: int = 0


@dataclass(slots=True)
class Close:
    date: date
    account: str
    src_file: str = ""
    src_line_start: int = 0
    src_line_end: int = 0


@dataclass(slots=True)
class Price:
    date: date
    commodity: str
    amount: Amount
    src_file: str = ""
    src_line_start: int = 0
    src_line_end: int = 0


@dataclass(slots=True)
class Commodity:
    date: date
    code: str
    src_file: str = ""
    src_line_start: int = 0
    src_line_end: int = 0


@dataclass(slots=True)
class Recur:
    date: date
    period: str
    description: str
    date_from: date
    date_to: date | None
    postings: list[Posting]
    src_file: str = ""
    src_line_start: int = 0
    src_line_end: int = 0


@dataclass(slots=True)
class Budget:
    date: date
    period: str
    account: str
    amount: Amount
    src_file: str = ""
    src_line_start: int = 0
    src_line_end: int = 0


@dataclass(slots=True)
class Event:
    date: date
    name: str
    value: str
    src_file: str = ""
    src_line_start: int = 0
    src_line_end: int = 0


@dataclass(slots=True)
class Option:
    key: str
    value: str
    src_file: str = ""
    src_line_start: int = 0
    src_line_end: int = 0


@dataclass(slots=True)
class Include:
    pattern: str
    src_file: str = ""
    src_line_start: int = 0
    src_line_end: int = 0


Directive = (
    Transaction
    | Balance
    | Open
    | Close
    | Price
    | Commodity
    | Recur
    | Budget
    | Event
    | Option
    | Include
)

DATED_DIRECTIVES = (Transaction, Balance, Open, Close, Price, Commodity, Recur, Budget, Event)


@dataclass(slots=True)
class Options:
    operating_currency: str = "CNY"
    strict: str = "warn"
    account_language: str = "zh"
    default_asset: str = "资产:现金"
    default_income: str = "收入:其他"
    write_bom: str = "off"
    sort_accounts: str = "unicode"
    pinyin: str = "off"
    keyword_language: str = "auto"

    @classmethod
    def from_pairs(cls, pairs: dict[str, str]) -> Options:
        opts = cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}
        for key, value in pairs.items():
            canonical_key = canonical_option_key(key)
            if canonical_key in known:
                setattr(opts, canonical_key, canonical_option_value(canonical_key, value))
        return opts
