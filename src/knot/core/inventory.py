"""投资库存与成本基础：FIFO / 移动平均、已实现与未实现盈亏、最新报价。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from knot.core.amount import is_zero
from knot.core.book import Book, cost_value
from knot.core.model import Price

METHOD_FIFO = "fifo"
METHOD_AVERAGE = "average"


@dataclass
class Lot:
    when: date
    units: Decimal
    unit_cost: Decimal
    currency: str


@dataclass
class Position:
    account: str
    commodity: str
    units: Decimal = Decimal(0)
    cost_total: Decimal = Decimal(0)
    cost_currency: str = ""
    market_price: Decimal | None = None
    realized: Decimal = Decimal(0)
    lots: list[Lot] = field(default_factory=list)

    @property
    def unit_cost(self) -> Decimal:
        return self.cost_total / self.units if self.units else Decimal(0)

    @property
    def market_value(self) -> Decimal | None:
        if self.market_price is None:
            return None
        return self.units * self.market_price

    @property
    def unrealized(self) -> Decimal | None:
        value = self.market_value
        return None if value is None else value - self.cost_total


def price_directives(book: Book) -> list[Price]:
    return [d for d in book.directives if isinstance(d, Price)]


def latest_price(book: Book, commodity: str, when: date | None = None) -> Decimal | None:
    """取该商品最近一次报价（不晚于 when）。"""
    prices = [
        item
        for item in price_directives(book)
        if item.commodity == commodity and (when is None or item.date <= when)
    ]
    if not prices:
        return None
    return max(prices, key=lambda item: item.date).amount.number


def convert(book: Book, amount: Decimal, source: str, target: str) -> Decimal | None:
    """按报价折算；相同币种直接返回，支持反向与经记账币种中转。"""
    if source == target:
        return amount
    operating = book.options.operating_currency

    def rate(from_currency: str, to_currency: str) -> Decimal | None:
        direct = [
            item
            for item in price_directives(book)
            if item.commodity == from_currency and item.amount.currency == to_currency
        ]
        if direct:
            return max(direct, key=lambda item: item.date).amount.number
        reverse = [
            item
            for item in price_directives(book)
            if item.commodity == to_currency and item.amount.currency == from_currency
        ]
        if reverse:
            value = max(reverse, key=lambda item: item.date).amount.number
            return Decimal(1) / value if value else None
        return None

    direct_rate = rate(source, target)
    if direct_rate is not None:
        return amount * direct_rate
    first, second = rate(source, operating), rate(operating, target)
    if first is not None and second is not None:
        return amount * first * second
    return None


def build_positions(
    book: Book, method: str = METHOD_FIFO, as_of: date | None = None
) -> list[Position]:
    """按科目 + 商品归集持仓，成本基础支持 FIFO 与移动平均。"""
    positions: dict[tuple[str, str], Position] = {}
    transactions = sorted(book.transactions, key=lambda tx: tx.date)

    for tx in transactions:
        if as_of is not None and tx.date > as_of:
            continue
        for posting in tx.postings:
            if posting.units is None or posting.cost is None:
                continue
            commodity = posting.units.currency
            key = (posting.account, commodity)
            position = positions.setdefault(
                key,
                Position(
                    account=posting.account,
                    commodity=commodity,
                    cost_currency=posting.cost.currency,
                ),
            )
            units = posting.units.number
            if units > 0:
                total = cost_value(posting) or Decimal(0)
                unit_cost = total / units if units else Decimal(0)
                if method == METHOD_AVERAGE:
                    position.cost_total += total
                    position.units += units
                else:
                    position.lots.append(Lot(tx.date, units, unit_cost, posting.cost.currency))
                    position.cost_total += total
                    position.units += units
            else:
                proceeds = cost_value(posting) or Decimal(0)
                _dispose(position, abs(units), method, proceeds)

    for position in positions.values():
        position.market_price = latest_price(book, position.commodity, as_of)
        if position.units <= 0:
            position.units = Decimal(0)
            position.cost_total = Decimal(0)
    return [item for item in positions.values() if not is_zero(item.units)]


def _dispose(position: Position, units: Decimal, method: str, proceeds: Decimal) -> None:
    """按成本基础消耗持仓，并把差额计入已实现盈亏。"""
    if method == METHOD_AVERAGE or not position.lots:
        unit_cost = position.unit_cost
        consumed = unit_cost * units
        position.cost_total -= consumed
        position.units -= units
        position.realized += proceeds - consumed
        return

    remaining = units
    consumed = Decimal(0)
    while remaining > 0 and position.lots:
        lot = position.lots[0]
        take = min(lot.units, remaining)
        consumed += take * lot.unit_cost
        position.cost_total -= take * lot.unit_cost
        position.units -= take
        lot.units -= take
        remaining -= take
        if is_zero(lot.units):
            position.lots.pop(0)
    if remaining > 0:
        position.units -= remaining
    position.realized += proceeds - consumed


def holdings_value(book: Book, as_of: date | None = None) -> dict:
    """持仓市值汇总：按商品币种与记账币种分别给出。"""
    positions = build_positions(book, as_of=as_of)
    by_commodity: dict[str, Decimal] = {}
    total_cost: dict[str, Decimal] = {}
    missing_price: list[str] = []
    for position in positions:
        value = position.market_value
        if value is None:
            missing_price.append(position.commodity)
            value = position.cost_total
        by_commodity[position.commodity] = by_commodity.get(position.commodity, Decimal(0)) + value
        total_cost[position.commodity] = (
            total_cost.get(position.commodity, Decimal(0)) + position.cost_total
        )
    return {
        "持仓": positions,
        "市值": by_commodity,
        "成本": total_cost,
        "缺报价": sorted(set(missing_price)),
    }


def net_worth_in(book: Book, currency: str | None = None, as_of: date | None = None) -> dict:
    """净资产按报价折算到目标币种（商品持仓按最新报价折算，缺报价单独列出）。"""
    target = currency or book.options.operating_currency
    totals = book.net_worth(upto=as_of)
    converted = Decimal(0)
    missing: dict[str, Decimal] = {}
    for code, amount in totals.items():
        if is_zero(amount):
            continue
        value = convert(book, amount, code, target)
        if value is None:
            missing[code] = amount
        else:
            converted += value
    return {"币种": target, "折算后": converted, "缺报价": missing}
