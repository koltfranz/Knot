"""账本服务：Web 与 TUI 共用的数据层（按 mtime 缓存，写操作走 core.actions）。"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from knot.core.actions import EntryRequest, reclassify, resolve_account, write_entry
from knot.core.amount import fmt_amount, is_zero
from knot.core.book import Book
from knot.core.chart import (
    spec_budget_gauge,
    spec_calendar_heatmap,
    spec_cash_flow_waterfall,
    spec_category_treemap,
    spec_expense_pie,
    spec_monthly_flow,
    spec_net_worth,
)
from knot.core.date_cn import parse_date, parse_month
from knot.core.diagnostic import Diagnostic
from knot.core.importer import SOURCES
from knot.core.importer.base import (
    build_transaction,
    existing_keys,
    split_duplicates,
)
from knot.core.loader import LoadResult, load_book
from knot.core.normalize import KnotError
from knot.core.query import Filter, select
from knot.core.report import (
    balance_over_time,
    balance_sheet,
    cash_flow_statement,
    expense_by_category,
    income_statement,
    monthly_flow,
    net_worth_trend,
)
from knot.core.writer import insert_transaction, target_year_file


def _money(value: Decimal) -> str:
    return fmt_amount(value)


@dataclass
class Snapshot:
    book: Book
    diagnostics: list[Diagnostic]
    loaded: LoadResult
    stamp: float


class LedgerService:
    def __init__(self, ledger: Path, token: str | None = None) -> None:
        self.ledger = Path(ledger)
        self.token = token
        self._cache: Snapshot | None = None

    # ---------- 读取 ----------

    def _files_stamp(self, files: list[Path]) -> float:
        stamps = [self.ledger.stat().st_mtime] if self.ledger.exists() else [0.0]
        for path in files:
            try:
                stamps.append(path.stat().st_mtime)
            except OSError:
                continue
        parent = self.ledger.parent
        if parent.exists():
            stamps.append(parent.stat().st_mtime)
        return max(stamps)

    def snapshot(self) -> Snapshot:
        files = self._cache.loaded.files if self._cache else []
        stamp = self._files_stamp(files)
        if self._cache is not None and self._cache.stamp == stamp:
            return self._cache
        loaded, book, diagnostics = load_book(self.ledger, missing_ok=True)
        snapshot = Snapshot(book=book, diagnostics=diagnostics, loaded=loaded, stamp=stamp)
        self._cache = snapshot
        return snapshot

    def invalidate(self) -> None:
        self._cache = None

    def index(self) -> dict:
        snapshot = self.snapshot()
        errors = [d for d in snapshot.diagnostics if d.level == "error"]
        return {
            "账本": str(self.ledger),
            "交易数": len(snapshot.book.transactions),
            "科目数": len(snapshot.book.used_accounts()),
            "错误": len(errors),
            "警告": sum(1 for d in snapshot.diagnostics if d.level == "warning"),
            "待分类": self._uncategorized_rows(snapshot.book)["合计笔数"],
            "币种": snapshot.book.options.operating_currency,
            "诊断": [
                {"级别": d.level, "文件": d.file, "行": d.line, "信息": d.message}
                for d in snapshot.diagnostics[:50]
            ],
        }

    def transactions(self, params: dict) -> dict:
        book = self.snapshot().book
        filters = Filter(
            account=params.get("科目"),
            date_from=self._date(params.get("从")),
            date_to=self._date(params.get("到")),
            tags=frozenset(self._list(params.get("标签"))),
            payee=params.get("收款方"),
            keywords=list(self._list(params.get("关键词"))),
            limit=self._int(params.get("条数")),
        )
        if params.get("月"):
            start, end = parse_month(params["月"])
            filters.date_from, filters.date_to = start, end
        rows = select(book.transactions, filters)
        return {
            "流水": [
                {
                    "日期": tx.date.isoformat(),
                    "标志": tx.flag.value,
                    "收款方": tx.payee,
                    "摘要": tx.narration,
                    "标签": sorted(tx.tags),
                    "分录": [
                        {
                            "科目": posting.account,
                            "金额": _money(posting.units.number) if posting.units else "",
                            "币种": posting.units.currency if posting.units else "",
                            "自动配平": posting.generated,
                        }
                        for posting in tx.postings
                    ],
                    "来源": f"{tx.src_file}:{tx.src_line_start}",
                }
                for tx in reversed(rows)
            ],
            "共": len(rows),
        }

    def balances(self, params: dict) -> dict:
        book = self.snapshot().book
        account = params.get("科目")
        tree = self._tree(book, account)
        flat = {
            name: {
                currency: _money(value)
                for currency, value in book.balance_of(name).items()
                if not is_zero(value)
            }
            for name in book.used_accounts()
            if (account is None or name == account or name.startswith(account + ":"))
        }
        return {
            "币种": book.options.operating_currency,
            "树": tree,
            "科目": {name: values for name, values in flat.items() if values},
        }

    def _tree(self, book: Book, account: str | None) -> list[dict]:
        names = [
            n
            for n in book.used_accounts()
            if account is None or n == account or n.startswith(account + ":")
        ]
        prefixes: set[str] = set()
        for name in names:
            parts = name.split(":")
            for index in range(1, len(parts) + 1):
                prefixes.add(":".join(parts[:index]))
        rows = []
        for node in sorted(prefixes):
            totals = book.balance_of(node)
            values = {
                currency: _money(value) for currency, value in totals.items() if not is_zero(value)
            }
            if not values:
                continue
            rows.append(
                {
                    "科目": node,
                    "层级": node.count(":"),
                    "名称": node.split(":")[-1],
                    "余额": values,
                }
            )
        return rows

    def accounts(self, params: dict) -> dict:
        book = self.snapshot().book
        rows = []
        for name in book.used_accounts():
            totals = book.balance_of(name, include_children=False)
            if all(is_zero(value) for value in totals.values()) and params.get("全部") != "1":
                continue
            trend = balance_over_time(book, name)
            rows.append(
                {
                    "科目": name,
                    "余额": {currency: _money(value) for currency, value in totals.items()},
                    "趋势": [_money(row["余额"]) for row in trend],
                }
            )
        return {"科目": rows, "共": len(rows)}

    def report(self, kind: str, params: dict) -> dict:
        book = self.snapshot().book
        start, end = self._range(params)
        if kind in ("资产负债表", "balance"):
            return {"类型": "资产负债表", "数据": balance_sheet(book, end or self._today(book))}
        if kind in ("利润表", "income"):
            return {"类型": "利润表", "数据": income_statement(book, start, end)}
        if kind in ("现金流量表", "cash"):
            return {"类型": "现金流量表", "数据": cash_flow_statement(book, start, end)}
        if kind in ("收支", "monthly"):
            return {"类型": "收支", "数据": monthly_flow(book, start, end)}
        if kind in ("净资产", "networth"):
            return {"类型": "净资产", "数据": net_worth_trend(book, start, end)}
        if kind in ("分类", "category"):
            return {
                "类型": "分类",
                "数据": [
                    {"科目": name, "金额": _money(value)}
                    for name, value in expense_by_category(book, start, end)
                ],
            }
        if kind in ("概况", "summary"):
            return {"类型": "概况", "数据": book.summary()}
        raise KnotError(f"未知报表：{kind}")

    def holdings(self, params: dict) -> dict:
        from knot.core.inventory import build_positions, net_worth_in

        book = self.snapshot().book
        method = "average" if params.get("方法") in ("average", "平均") else "fifo"
        positions = build_positions(book, method=method)
        operated = net_worth_in(book, params.get("币种") or None)
        return {
            "方法": method,
            "持仓": [
                {
                    "科目": item.account,
                    "商品": item.commodity,
                    "数量": str(item.units),
                    "成本": _money(item.cost_total),
                    "单位成本": str(item.unit_cost),
                    "最新价": str(item.market_price) if item.market_price is not None else None,
                    "市值": _money(item.market_value) if item.market_value is not None else None,
                    "未实现盈亏": _money(item.unrealized) if item.unrealized is not None else None,
                    "已实现盈亏": _money(item.realized),
                }
                for item in positions
            ],
            "净资产": {
                "币种": operated["币种"],
                "折算后": _money(operated["折算后"]),
                "缺报价": {key: _money(value) for key, value in operated["缺报价"].items()},
            },
        }

    def budgets(self, params: dict) -> dict:
        from knot.core.budget import rows as budget_rows
        from knot.core.budget import summary as budget_summary

        book = self.snapshot().book
        month = params.get("月")
        items = [
            {
                **item,
                "预算": _money(item["预算"]),
                "实际": _money(item["实际"]),
                "剩余": _money(item["剩余"]),
                "进度": f"{item['进度'] * 100:.1f}%",
            }
            for item in budget_rows(book, month)
        ]
        total = budget_summary(book, month)
        return {
            "进度": items,
            "合计": {
                "月份": total["月份"],
                "预算合计": _money(total["预算合计"]),
                "实际合计": _money(total["实际合计"]),
                "剩余合计": _money(total["剩余合计"]),
                "超支科目": total["超支科目"],
            },
        }

    def chart(self, kind: str, params: dict) -> dict:
        book = self.snapshot().book
        start, end = self._range(params)
        if kind in ("净资产", "networth"):
            spec = spec_net_worth(book, start, end)
        elif kind in ("收支", "monthly"):
            spec = spec_monthly_flow(book, start, end)
        elif kind in ("分类", "category"):
            spec = spec_expense_pie(book, start, end)
        elif kind in ("树", "treemap"):
            spec = spec_category_treemap(book, start, end)
        elif kind in ("日历", "heatmap"):
            year = self._int(params.get("年"))
            if year is None:
                years = sorted({tx.date.year for tx in book.transactions})
                year = years[-1] if years else date.today().year
            spec = spec_calendar_heatmap(book, year)
        elif kind in ("预算", "budget"):
            spec = spec_budget_gauge(book, params.get("月"))
        elif kind in ("现金流", "瀑布", "waterfall"):
            spec = spec_cash_flow_waterfall(book, start, end)
        else:
            raise KnotError(f"未知图表：{kind}")
        return spec.to_json()

    def aliases(self, params: dict) -> dict:
        snapshot = self.snapshot()
        mapping = snapshot.loaded.aliases.all()
        rows = [
            {
                "别名": key,
                "目标": value,
                "来源": "用户" if key in snapshot.loaded.aliases.user else "内置",
            }
            for key, value in sorted(mapping.items())
        ]
        return {"别名": rows, "共": len(rows)}

    # ---------- 写入 ----------

    def add_entry(self, payload: dict) -> dict:
        snapshot = self.snapshot()
        request = EntryRequest(
            amount=str(payload.get("金额", "")),
            account=str(payload.get("科目", "")),
            from_account=payload.get("来自") or None,
            to_account=payload.get("去向") or None,
            when=payload.get("日期") or None,
            note=str(payload.get("摘要", "")),
            payee=payload.get("收款方") or None,
            tags=tuple(payload.get("标签") or ()),
        )
        entry = write_entry(
            request,
            ledger=self.ledger,
            aliases=snapshot.loaded.aliases,
            options=snapshot.book.options,
            rules=snapshot.loaded.rules,
            files=snapshot.loaded.files,
        )
        self.invalidate()
        return {
            "已记入": str(entry.target),
            "交易": {
                "日期": entry.transaction.date.isoformat(),
                "摘要": entry.transaction.narration,
                "收款方": entry.transaction.payee,
                "分录": [
                    {
                        "科目": posting.account,
                        "金额": _money(posting.units.number) if posting.units else "",
                    }
                    for posting in entry.transaction.postings
                    if not posting.generated
                ],
            },
            "已学习规则": entry.learned,
        }

    def uncategorized(self, params: dict) -> dict:
        snapshot = self.snapshot()
        return self._uncategorized_rows(snapshot.book)

    def _uncategorized_rows(self, book: Book) -> dict:
        counter: Counter = Counter()
        totals: dict[tuple[str, str], Decimal] = {}
        for tx in book.transactions:
            for posting in tx.postings:
                if posting.account != "费用:待分类" or posting.units is None:
                    continue
                payee = tx.payee or tx.narration or "未知"
                currency = posting.units.currency or book.options.operating_currency
                counter[payee] += 1
                totals[(payee, currency)] = (
                    totals.get((payee, currency), Decimal(0)) + posting.units.number
                )
        rows = []
        for payee, count in counter.most_common():
            amounts = {
                currency: _money(value)
                for (name, currency), value in totals.items()
                if name == payee
            }
            rows.append({"收款方": payee, "笔数": count, "金额": amounts})
        return {"待分类": rows, "合计笔数": sum(counter.values())}

    def classify(self, payload: dict) -> dict:
        snapshot = self.snapshot()
        payee = str(payload.get("收款方", ""))
        account = str(payload.get("科目", ""))
        if not payee or not account:
            raise KnotError("归类需要 收款方 与 科目")
        count, files = reclassify(
            self.ledger,
            aliases=snapshot.loaded.aliases,
            payee=payee,
            account=account,
            rules=snapshot.loaded.rules,
        )
        self.invalidate()
        return {"已归类": count, "文件": [str(path) for path in files]}

    def import_preview(self, payload: dict) -> dict:
        return self._import(payload, write=False)

    def import_apply(self, payload: dict) -> dict:
        return self._import(payload, write=True)

    def _import(self, payload: dict, write: bool) -> dict:
        snapshot = self.snapshot()
        source = str(payload.get("来源", ""))
        module = SOURCES.get(source) or SOURCES.get(source.lower())
        if module is None:
            raise KnotError(f"未知账单来源：{source}")
        raw_files = payload.get("文件") or []
        source_account = payload.get("账户") or snapshot.book.options.default_asset
        source_account = resolve_account(snapshot.loaded.aliases, source_account, "账户")

        known = existing_keys(snapshot.book)
        written: Counter = Counter()
        results = []
        for raw_path in raw_files:
            path = Path(str(raw_path))
            if not path.exists():
                raise KnotError(f"文件不存在：{path}")
            parsed = module.parse(path)
            kept, duplicates = split_duplicates(parsed.rows, known + written)
            transactions = [
                build_transaction(
                    row,
                    source_account=source_account,
                    rules=snapshot.loaded.rules,
                    default_target=snapshot.book.options.default_income,
                    currency=snapshot.book.options.operating_currency,
                )
                for row in kept
            ]
            if write:
                for transaction in transactions:
                    target = target_year_file(
                        self.ledger, transaction.date.year, snapshot.loaded.files
                    )
                    insert_transaction(target, transaction)
                written.update(row.key() for row in kept)
            results.append(
                {
                    "文件": str(path),
                    "总行数": parsed.stats.total,
                    "可导入": len(transactions),
                    "重复": len(duplicates),
                    "待分类": sum(1 for tx in transactions if tx.flag.value == "?"),
                    "解析失败": parsed.stats.failed,
                    "预览": [
                        {
                            "日期": tx.date.isoformat(),
                            "金额": _money(tx.postings[0].units.number),
                            "科目": tx.postings[0].account,
                            "收款方": tx.payee,
                        }
                        for tx in transactions[:20]
                    ],
                }
            )
        if write:
            self.invalidate()
        return {"已写入": write, "结果": results}

    # ---------- 变更监听 ----------

    def watch(self, interval: float = 0.5, heartbeat: float = 10.0) -> Iterator[dict]:
        snapshot = self.snapshot()
        last = snapshot.stamp
        last_beat = time.time()
        while True:
            time.sleep(interval)
            current = self._files_stamp(snapshot.loaded.files)
            now = time.time()
            if current != last:
                last = current
                self.invalidate()
                snapshot = self.snapshot()
                yield {"事件": "变更", "时间": now, "交易数": len(snapshot.book.transactions)}
                last_beat = now
            elif now - last_beat >= heartbeat:
                last_beat = now
                yield {"事件": "心跳", "时间": now}

    # ---------- 工具 ----------

    def _today(self, book: Book) -> date:
        dates = [tx.date for tx in book.transactions]
        return max(dates) if dates else date.today()

    def _date(self, text: str | None) -> date | None:
        if not text:
            return None
        return parse_date(text)

    def _int(self, text) -> int | None:
        if text in (None, ""):
            return None
        return int(text)

    def _list(self, text) -> list[str]:
        if not text:
            return []
        if isinstance(text, list):
            return [str(item) for item in text]
        return [item for item in str(text).split(",") if item]

    def _range(self, params: dict) -> tuple[date | None, date | None]:
        if params.get("月"):
            return parse_month(params["月"])
        if params.get("年"):
            year = int(params["年"])
            return parse_month(f"{year}-1")[0], parse_month(f"{year}-12")[1]
        return self._date(params.get("从")), self._date(params.get("到"))
