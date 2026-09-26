"""图表：ChartSpec 中间结构 + 零依赖 SVG 渲染。

坐标计算允许使用 float（几何量），但金额本身全程保持 Decimal，
仅在生成坐标时一次性换算。
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from knot.core.amount import fmt_amount
from knot.core.book import Book
from knot.core.report import (
    expense_by_category,
    monthly_flow,
    net_worth_trend,
)
from knot.core.width import truncate

KIND_BAR = "bar"
KIND_LINE = "line"
KIND_PIE = "pie"
KIND_HEATMAP = "heatmap"
KIND_TREEMAP = "treemap"
KIND_GAUGE = "gauge"

KINDS = (KIND_BAR, KIND_LINE, KIND_PIE, KIND_HEATMAP, KIND_TREEMAP, KIND_GAUGE)

PALETTE = (
    "#4c78a8",
    "#f58518",
    "#54a24b",
    "#e45756",
    "#72b7b2",
    "#eeca3b",
    "#b279a2",
    "#ff9da6",
    "#9d755d",
    "#bab0ac",
)

MAX_POINTS = 300
WIDTH = 880
HEIGHT = 420


@dataclass
class ChartSeries:
    name: str
    values: list[Decimal] = field(default_factory=list)


@dataclass
class ChartSpec:
    kind: str
    title: str
    labels: list[str] = field(default_factory=list)
    series: list[ChartSeries] = field(default_factory=list)
    currency: str = "CNY"
    unit: str = ""

    def to_json(self) -> dict:
        return {
            "类型": self.kind,
            "标题": self.title,
            "币种": self.currency,
            "标签": list(self.labels),
            "系列": [
                {"名称": series.name, "数值": [str(value) for value in series.values]}
                for series in self.series
            ],
        }


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def downsample(labels: list[str], values: list[Decimal], limit: int = MAX_POINTS):
    if len(labels) <= limit:
        return labels, values
    bucket = (len(labels) + limit - 1) // limit
    new_labels: list[str] = []
    new_values: list[Decimal] = []
    for start in range(0, len(labels), bucket):
        chunk = values[start : start + bucket]
        new_labels.append(labels[start])
        new_values.append(sum(chunk, Decimal(0)) / Decimal(len(chunk)))
    return new_labels, new_values


def spec_monthly_flow(book: Book, start: date | None = None, end: date | None = None) -> ChartSpec:
    rows = monthly_flow(book, start, end)
    labels = [row["月份"] for row in rows]
    return ChartSpec(
        kind=KIND_BAR,
        title="月度收支",
        labels=labels,
        series=[
            ChartSeries("收入", [row["收入"] for row in rows]),
            ChartSeries("支出", [row["支出"] for row in rows]),
        ],
        currency=book.options.operating_currency,
    )


def spec_net_worth(book: Book, start: date | None = None, end: date | None = None) -> ChartSpec:
    rows = net_worth_trend(book, start, end)
    currency = book.options.operating_currency
    labels = [row["月份"] for row in rows]
    values = [_decimal(row.get(currency, Decimal(0))) for row in rows]
    return ChartSpec(
        kind=KIND_LINE,
        title="净资产趋势",
        labels=labels,
        series=[ChartSeries("净资产", values)],
        currency=currency,
    )


def spec_expense_pie(
    book: Book, start: date | None = None, end: date | None = None, top: int = 8
) -> ChartSpec:
    rows = expense_by_category(book, start, end, depth=2, top=top)
    return ChartSpec(
        kind=KIND_PIE,
        title="支出分类占比",
        labels=[name for name, _value in rows],
        series=[ChartSeries("支出", [value for _name, value in rows])],
        currency=book.options.operating_currency,
    )


def spec_category_treemap(
    book: Book, start: date | None = None, end: date | None = None, top: int = 12
) -> ChartSpec:
    rows = expense_by_category(book, start, end, depth=2, top=top)
    return ChartSpec(
        kind=KIND_TREEMAP,
        title="支出分类面积",
        labels=[name for name, _value in rows],
        series=[ChartSeries("支出", [value for _name, value in rows])],
        currency=book.options.operating_currency,
    )


def spec_calendar_heatmap(book: Book, year: int) -> ChartSpec:
    totals: dict[str, Decimal] = {}
    for tx in book.transactions:
        if tx.date.year != year:
            continue
        for posting in tx.postings:
            if posting.units is None or posting.account.split(":")[0] != "费用":
                continue
            key = tx.date.isoformat()
            totals[key] = totals.get(key, Decimal(0)) + posting.units.number
    labels = sorted(totals)
    return ChartSpec(
        kind=KIND_HEATMAP,
        title=f"{year} 年消费日历",
        labels=labels,
        series=[ChartSeries("支出", [totals[key] for key in labels])],
        currency=book.options.operating_currency,
    )


def _scale(values: list[Decimal], length: float) -> list[float]:
    if not values:
        return []
    top = max((value for value in values), default=Decimal(0))
    bottom = min((value for value in values), default=Decimal(0))
    span = top - bottom or Decimal(1)
    return [float((value - bottom) / span) * length for value in values]


def _text(
    x: float, y: float, content: str, size: int = 12, anchor: str = "middle", color: str = "#333333"
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
        f'fill="{color}" font-family="sans-serif">{html.escape(content)}</text>'
    )


def _wrap(title: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
    )


def spec_budget_gauge(book: Book, month: str | None = None, top: int = 8) -> ChartSpec:
    """预算进度：预算 vs 实际（三端消费同一 ChartSpec）。"""
    from knot.core.budget import rows as budget_rows

    items = budget_rows(book, month)[:top]
    return ChartSpec(
        kind=KIND_GAUGE,
        title="预算进度",
        labels=[item["科目"] for item in items],
        series=[
            ChartSeries("实际", [item["实际"] for item in items]),
            ChartSeries("预算", [item["预算"] for item in items]),
        ],
        currency=book.options.operating_currency,
    )


def _render_gauge(spec: ChartSpec, width: int, height: int) -> str:
    labels = spec.labels
    if not labels or len(spec.series) < 2:
        return _text(width / 2, height / 2, "暂无预算")
    actual, planned = spec.series[0].values, spec.series[1].values
    left, right = 150.0, width - 80.0
    row_height = min(28.0, (height - 90) / max(1, len(labels)))
    parts: list[str] = []
    for index, label in enumerate(labels):
        top = planned[index] if index < len(planned) else Decimal(0)
        used = actual[index] if index < len(actual) else Decimal(0)
        ratio = float(used / top) if top else 0.0
        y = 60 + index * row_height
        color = PALETTE[2] if ratio <= 1 else PALETTE[3]
        parts.append(_text(left - 10, y + 12, truncate(label, 16), size=12, anchor="end"))
        parts.append(
            f'<rect x="{left}" y="{y}" width="{right - left:.0f}" height="14" rx="7" '
            f'fill="#eef1f3"/>'
        )
        filled = max(2.0, min(1.0, ratio) * (right - left))
        parts.append(
            f'<rect x="{left}" y="{y}" width="{filled:.0f}" height="14" rx="7" fill="{color}">'
            f"<title>{html.escape(label)} 已用 {fmt_amount(used)} / 预算 {fmt_amount(top)}"
            f"（{ratio * 100:.0f}%）</title></rect>"
        )
        parts.append(
            _text(
                right + 8,
                y + 12,
                f"{ratio * 100:.0f}%  {fmt_amount(used)}/{fmt_amount(top)}",
                size=11,
                anchor="start",
                color="#555555",
            )
        )
    return "".join(parts)


def render_svg(spec: ChartSpec, width: int = WIDTH, height: int = HEIGHT) -> str:
    if spec.kind == KIND_BAR:
        body = _render_bar(spec, width, height)
    elif spec.kind == KIND_LINE:
        body = _render_line(spec, width, height)
    elif spec.kind == KIND_PIE:
        body = _render_pie(spec, width, height)
    elif spec.kind == KIND_HEATMAP:
        body = _render_heatmap(spec, width, height)
    elif spec.kind == KIND_TREEMAP:
        body = _render_treemap(spec, width, height)
    elif spec.kind == KIND_GAUGE:
        body = _render_gauge(spec, width, height)
    else:
        raise ValueError(f"未知图表类型：{spec.kind}")
    title = _text(width / 2, 28, spec.title, size=18)
    return "\n".join([_wrap(spec.title), title, body, "</svg>"])


def _render_bar(spec: ChartSpec, width: int, height: int) -> str:
    labels = spec.labels
    series_values: list[list[Decimal]] = []
    for item in spec.series:
        if len(item.values) == len(labels):
            series_values.append(list(item.values))
        else:
            _new_labels, values = downsample(labels, list(item.values))
            series_values.append(values)
    left, right, top, bottom = 60.0, width - 20.0, 60.0, height - 60.0
    plot_w, plot_h = right - left, bottom - top
    count = max(1, len(labels))
    group = plot_w / count
    bar_w = max(2.0, group / (len(spec.series) + 1))

    top_value = max(
        (abs(value) for values in series_values for value in values), default=Decimal(0)
    ) or Decimal(1)
    parts = [f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#999"/>']
    step = max(1, len(labels) // 12)
    for group_index, label in enumerate(labels):
        base_x = left + group_index * group
        for series_index, item in enumerate(spec.series):
            values = series_values[series_index]
            if group_index >= len(values):
                continue
            value = values[group_index]
            bar_h = float(abs(value) / top_value) * plot_h
            x = base_x + series_index * bar_w + group / 8
            y = bottom - bar_h
            color = PALETTE[series_index % len(PALETTE)]
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                f'fill="{color}"><title>{html.escape(label)} {item.name} '
                f"{fmt_amount(value)} {spec.currency}</title></rect>"
            )
        if group_index % step == 0:
            parts.append(_text(base_x + group / 2, bottom + 18, truncate(label, 12), size=11))
    legend = "  ".join(
        f'<rect x="{left + index * 110:.0f}" y="44" width="10" height="10" '
        f'fill="{PALETTE[index % len(PALETTE)]}"/>'
        + _text(left + index * 110 + 16, 53, item.name, size=12, anchor="start")
        for index, item in enumerate(spec.series)
    )
    axis = _text(left - 8, top + 12, fmt_amount(top_value), size=11, anchor="end") + _text(
        left - 8, bottom, "0", size=11, anchor="end"
    )
    return "".join(parts) + legend + axis


def _render_line(spec: ChartSpec, width: int, height: int) -> str:
    item = spec.series[0] if spec.series else ChartSeries("", [])
    labels, values = downsample(spec.labels, item.values)
    left, right, top, bottom = 60.0, width - 20.0, 60.0, height - 60.0
    plot_w, plot_h = right - left, bottom - top
    if not values:
        return _text(width / 2, height / 2, "暂无数据")
    ys = _scale(values, plot_h)
    step = plot_w / max(1, len(values) - 1)
    points = [(left + index * step, bottom - value) for index, value in enumerate(ys)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    parts = [
        f'<polyline points="{path}" fill="none" stroke="{PALETTE[0]}" stroke-width="2"/>',
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#999"/>',
    ]
    for index, (x, y) in enumerate(points):
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{PALETTE[0]}">'
            f"<title>{html.escape(labels[index])} {fmt_amount(values[index])} "
            f"{spec.currency}</title></circle>"
        )
    step_label = max(1, len(labels) // 12)
    for index, label in enumerate(labels):
        if index % step_label:
            continue
        parts.append(_text(points[index][0], bottom + 18, truncate(label, 12), size=11))
    parts.append(_text(left - 8, top + 12, fmt_amount(max(values)), size=11, anchor="end"))
    parts.append(_text(left - 8, bottom, fmt_amount(min(values)), size=11, anchor="end"))
    return "".join(parts)


def _render_pie(spec: ChartSpec, width: int, height: int) -> str:
    values = spec.series[0].values if spec.series else []
    total = sum(values, Decimal(0))
    center_x, center_y, radius = width * 0.34, height / 2 + 10, min(width, height) * 0.30
    if not values or total <= 0:
        return _text(width / 2, height / 2, "暂无数据")

    parts: list[str] = []
    angle = -90.0
    for index, (label, value) in enumerate(zip(spec.labels, values, strict=False)):
        share = float(value / total)
        sweep = share * 360.0
        start = math.radians(angle)
        end = math.radians(angle + sweep)
        x1 = center_x + radius * math.cos(start)
        y1 = center_y + radius * math.sin(start)
        x2 = center_x + radius * math.cos(end)
        y2 = center_y + radius * math.sin(end)
        large = 1 if sweep > 180 else 0
        color = PALETTE[index % len(PALETTE)]
        parts.append(
            f'<path d="M{center_x:.1f},{center_y:.1f} L{x1:.1f},{y1:.1f} '
            f'A{radius:.1f},{radius:.1f} 0 {large} 1 {x2:.1f},{y2:.1f} Z" fill="{color}" '
            f'stroke="#ffffff"><title>{html.escape(label)} {fmt_amount(value)} '
            f"{spec.currency}（{share * 100:.1f}%）</title></path>"
        )
        angle += sweep

    legend_x = width * 0.66
    legend_y = 80.0
    for index, (label, value) in enumerate(zip(spec.labels, values, strict=False)):
        color = PALETTE[index % len(PALETTE)]
        parts.append(
            f'<rect x="{legend_x:.0f}" y="{legend_y + index * 24 - 10:.0f}" width="10" '
            f'height="10" fill="{color}"/>'
        )
        share = float(value / total) * 100 if total else 0.0
        text = f"{truncate(label, 16)}  {fmt_amount(value)}（{share:.1f}%）"
        parts.append(_text(legend_x + 16, legend_y + index * 24, text, size=12, anchor="start"))
    return "".join(parts)


def _render_treemap(spec: ChartSpec, width: int, height: int) -> str:
    values = spec.series[0].values if spec.series else []
    total = sum((abs(value) for value in values), Decimal(0))
    if not values or total <= 0:
        return _text(width / 2, height / 2, "暂无数据")

    left, right, top, bottom = 20.0, width - 20.0, 60.0, height - 30.0
    parts: list[str] = []
    remaining = total
    y = top
    for index, (label, value) in enumerate(zip(spec.labels, values, strict=False)):
        share = float(abs(value) / remaining) if remaining else 0.0
        row_h = (bottom - y) * share if index < len(values) - 1 else bottom - y
        row_h = max(18.0, row_h)
        color = PALETTE[index % len(PALETTE)]
        parts.append(
            f'<rect x="{left}" y="{y:.1f}" width="{right - left:.1f}" height="{row_h - 2:.1f}" '
            f'fill="{color}"><title>{html.escape(label)} {fmt_amount(value)} '
            f"{spec.currency}</title></rect>"
        )
        if row_h >= 20:
            parts.append(
                _text(
                    left + 8,
                    y + row_h / 2 + 4,
                    f"{truncate(label, 18)}  {fmt_amount(value)}",
                    size=12,
                    anchor="start",
                    color="#ffffff",
                )
            )
        y += row_h
        remaining -= abs(value)
        if y >= bottom:
            break
    return "".join(parts)


def _render_heatmap(spec: ChartSpec, width: int, height: int) -> str:
    values = spec.series[0].values if spec.series else []
    if not values:
        return _text(width / 2, height / 2, "暂无数据")
    top = max(values)
    left, top_y = 40.0, 60.0
    cell = min((width - 80) / 31.0, (height - 110) / 12.0)
    parts: list[str] = []
    for index, label in enumerate(spec.labels):
        try:
            day = date.fromisoformat(label)
        except ValueError:
            continue
        intensity = float(values[index] / top) if top else 0.0
        shade = int(240 - intensity * 190)
        color = f"#{shade:02x}{int(shade * 0.85):02x}{int(shade * 0.5):02x}"
        x = left + (day.day - 1) * cell
        y = top_y + (day.month - 1) * cell
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell - 2:.1f}" height="{cell - 2:.1f}" '
            f'fill="{color}"><title>{label} {fmt_amount(values[index])} '
            f"{spec.currency}</title></rect>"
        )
    for month in range(1, 13):
        parts.append(
            _text(
                left + 8,
                top_y + (month - 1) * cell + cell * 0.7,
                f"{month}月",
                size=11,
                anchor="end",
            )
        )
    for day in (1, 10, 20, 31):
        parts.append(_text(left + (day - 1) * cell + cell / 2, top_y - 6, str(day), size=11))
    parts.append(
        _text(
            left,
            height - 18,
            f"最深色 = {fmt_amount(top)} {spec.currency}",
            size=11,
            anchor="start",
            color="#666666",
        )
    )
    return "".join(parts)
