"""盲文迷你图：把 ChartSpec 的数值序列渲染为 8 级点阵。"""

from __future__ import annotations

from decimal import Decimal

BRAILLE_BASE = 0x2800
DOT_MAP = ((0x01, 0x02, 0x04, 0x40), (0x08, 0x10, 0x20, 0x80))


def levels(values: list[Decimal | float], height: int = 1) -> list[list[int]]:
    if not values:
        return []
    numbers = [float(value) for value in values]
    top, bottom = max(numbers) or 1.0, min(0.0, min(numbers))
    span = (top - bottom) or 1.0
    steps = 4 * height
    return [[round((value - bottom) / span * steps) for value in numbers]]


def render(values: list[Decimal | float], width: int | None = None, height: int = 1) -> str:
    if not values:
        return ""
    series = levels(values, height)[0]
    if width is not None and len(series) > width:
        bucket = (len(series) + width - 1) // width
        series = [max(series[i : i + bucket]) for i in range(0, len(series), bucket)][:width]
    cells = []
    for index in range(0, len(series), 2):
        code = 0
        for column, value in (
            (0, series[index]),
            (1, series[index + 1] if index + 1 < len(series) else 0),
        ):
            for row in range(4):
                if value > row:
                    code |= DOT_MAP[column][row]
        cells.append(chr(BRAILLE_BASE + code))
    return "".join(cells)


sparkline = render
