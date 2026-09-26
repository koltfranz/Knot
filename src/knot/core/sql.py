"""SQL 子集：面向账本的结构化查询。

支持：
    SELECT 字段[, …] FROM 流水|分录
      [WHERE 条件 [AND|OR …]] [GROUP BY 字段] [ORDER BY 字段 [DESC]] [LIMIT n]

条件运算符：= != > < >= <= 包含 开头于（字段与值均可中英混写）。
聚合函数：合计/求和(字段)、计数(*)、平均(字段)、最大(字段)、最小(字段)。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from knot.core.amount import fmt_amount
from knot.core.book import Book
from knot.core.normalize import KnotError, normalize_text

STATEMENT_RE = re.compile(
    r"^\s*SELECT\s+(?P<fields>.+?)\s+FROM\s+(?P<source>\S+)"
    r"(?:\s+WHERE\s+(?P<where>.+?))?"
    r"(?:\s+GROUP\s+BY\s+(?P<group>\S+))?"
    r"(?:\s+ORDER\s+BY\s+(?P<order>\S+(?:\s+(?:ASC|DESC|升序|降序))?))?"
    r"(?:\s+LIMIT\s+(?P<limit>\d+))?\s*$",
    re.IGNORECASE | re.DOTALL,
)
BOOLEAN_SPLIT = re.compile(r"\s+(?:AND|OR|并且|或者)\s+", re.IGNORECASE)
CONDITION_RE = re.compile(
    r"^\s*(?P<field>[\w\u4e00-\u9fff]+)\s*(?P<op>>=|<=|!=|<>|=|>|<|包含|开头于|结尾于)\s*"
    r"(?P<value>.+?)\s*$"
)
ORDER_RE = re.compile(
    r"^(?P<field>[\w\u4e00-\u9fff]+)(?:\s+(?P<direction>ASC|DESC|升序|降序))?$", re.IGNORECASE
)
FUNCTIONS = ("合计", "求和", "计数", "平均", "最大", "最小")

FLOW_FIELDS = ("日期", "标志", "收款方", "摘要", "标签")
POSTING_FIELDS = ("日期", "标志", "收款方", "摘要", "科目", "金额", "币种", "标签")


@dataclass
class Query:
    source: str = "分录"
    fields: list[str] = field(default_factory=list)
    conditions: list[tuple[str, str, str, str]] = field(
        default_factory=list
    )  # (joiner, field, op, value)
    group_by: str | None = None
    order_by: str | None = None
    descending: bool = False
    limit: int | None = None


def _tokens(statement: str) -> list[str]:  # 保留给聚合表达式使用
    return normalize_text(statement).replace(",", " , ").split()


def parse(statement: str) -> Query:
    match = STATEMENT_RE.match(normalize_text(statement))
    if match is None:
        raise KnotError(
            "SQL 子集语法：SELECT 字段 FROM 流水|分录 [WHERE …] [GROUP BY …] [ORDER BY …] [LIMIT n]"
        )
    query = Query()
    fields = match.group("fields")
    query.fields = [name.strip() for name in fields.split(",") if name.strip()] or ["*"]

    source = match.group("source")
    if source in ("postings", "transactions"):
        source = "分录" if source == "postings" else "流水"
    if source not in ("流水", "分录"):
        raise KnotError(f"未知数据源：{source}（可选 流水 / 分录）")
    query.source = source

    where = match.group("where")
    if where:
        joiner = "AND"
        for part in BOOLEAN_SPLIT.split(where):
            if part.strip().upper() in ("AND", "OR", "并且", "或者"):
                joiner = "OR" if part.strip().upper() in ("OR", "或者") else "AND"
                continue
            condition = CONDITION_RE.match(part)
            if condition is None:
                raise KnotError(f"无法解析条件：{part.strip()}")
            query.conditions.append(
                (
                    joiner,
                    condition.group("field"),
                    condition.group("op"),
                    condition.group("value").strip().strip("'\""),
                )
            )

    if match.group("group"):
        query.group_by = match.group("group")
    if match.group("order"):
        order = ORDER_RE.match(match.group("order").strip())
        if order is None:
            raise KnotError(f"无法解析 ORDER BY：{match.group('order')}")
        query.order_by = order.group("field")
        query.descending = (order.group("direction") or "").upper() in ("DESC", "降序")
    if match.group("limit"):
        query.limit = int(match.group("limit"))
    return query


def _rows(book: Book, source: str) -> list[dict]:
    rows: list[dict] = []
    for tx in book.transactions:
        if source == "流水":
            rows.append(
                {
                    "日期": tx.date.isoformat(),
                    "标志": tx.flag.value,
                    "收款方": tx.payee or "",
                    "摘要": tx.narration,
                    "标签": ",".join(sorted(tx.tags)),
                    "_金额": sum((p.units.number for p in tx.postings if p.units), Decimal(0)),
                    "_币种": book.options.operating_currency,
                }
            )
            continue
        for posting in tx.postings:
            rows.append(
                {
                    "日期": tx.date.isoformat(),
                    "标志": tx.flag.value,
                    "收款方": tx.payee or "",
                    "摘要": tx.narration,
                    "科目": posting.account,
                    "金额": posting.units.number if posting.units else Decimal(0),
                    "币种": (posting.units.currency if posting.units else "")
                    or book.default_currency(posting.account),
                    "标签": ",".join(sorted(tx.tags)),
                    "_金额": posting.units.number if posting.units else Decimal(0),
                }
            )
    return rows


def _compare(value, op: str, target: str) -> bool:
    left = value if isinstance(value, str) else str(value)
    if op in ("包含", "开头于", "结尾于"):
        if op == "包含":
            return target in left
        if op == "开头于":
            return left.startswith(target)
        return left.endswith(target)
    numeric = None
    try:
        numeric = Decimal(str(value).replace(",", ""))
        right = Decimal(target.replace(",", ""))
    except (InvalidOperation, ValueError):
        right = None
    if numeric is not None and right is not None:
        return {
            "=": numeric == right,
            "!=": numeric != right,
            "<>": numeric != right,
            ">": numeric > right,
            "<": numeric < right,
            ">=": numeric >= right,
            "<=": numeric <= right,
        }[op]
    return {
        "=": left == target,
        "!=": left != target,
        "<>": left != target,
        ">": left > target,
        "<": left < target,
        ">=": left >= target,
        "<=": left <= target,
    }[op]


def _filter(rows: list[dict], conditions) -> list[dict]:
    if not conditions:
        return rows
    result = []
    for row in rows:
        keep = True
        for index, (joiner, name, op, value) in enumerate(conditions):
            hit = name in row and _compare(row[name], op, value)
            if index == 0:
                keep = hit
            elif joiner == "OR":
                keep = keep or hit
            else:
                keep = keep and hit
        if keep:
            result.append(row)
    return result


def _aggregate(rows: list[dict], expression: str, group: str | None):
    if expression in FUNCTIONS or "(" in expression:
        name = expression.split("(")[0]
        inner = expression[expression.find("(") + 1 : -1] if "(" in expression else "*"
        if name not in FUNCTIONS:
            raise KnotError(f"未知聚合函数：{name}")
        buckets: dict[str, list[dict]] = {}
        for row in rows:
            buckets.setdefault(str(row.get(group, "")) if group else "", []).append(row)
        output = []
        for key, items in buckets.items():
            values = [item.get(inner, Decimal(0)) for item in items]
            numbers = [value for value in values if isinstance(value, Decimal)]
            if name in ("计数",):
                result = Decimal(len(items))
            elif name in ("合计", "求和"):
                result = sum(numbers, Decimal(0))
            elif name == "平均":
                result = sum(numbers, Decimal(0)) / len(numbers) if numbers else Decimal(0)
            elif name == "最大":
                result = max(numbers) if numbers else Decimal(0)
            else:
                result = min(numbers) if numbers else Decimal(0)
            output.append({group or "分组": key, expression: result})
        return output, True
    return rows, False


def execute(book: Book, statement: str) -> dict:
    query = parse(statement)
    rows = _rows(book, query.source)
    rows = _filter(rows, query.conditions)
    aggregated = False
    fields = list(query.fields)
    if len(query.fields) == 1 and (query.fields[0] in FUNCTIONS or "(" in query.fields[0]):
        rows, aggregated = _aggregate(rows, query.fields[0], query.group_by)
        if query.group_by:
            fields = [query.group_by, *query.fields]
    if query.order_by:
        rows.sort(key=lambda row: row.get(query.order_by, ""), reverse=query.descending)
    if query.limit is not None:
        rows = rows[: query.limit]

    if not aggregated:
        available = POSTING_FIELDS if query.source == "分录" else FLOW_FIELDS
        if fields == ["*"]:
            fields = list(available)
        else:
            for name in fields:
                if name not in available:
                    raise KnotError(f"未知字段：{name}（可用 {'、'.join(available)}）")
    display = [[_format(row.get(name)) for name in fields] for row in rows]
    return {"字段": fields, "行": display, "原始": rows, "条数": len(rows)}


def _format(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return fmt_amount(value)
    return str(value)
