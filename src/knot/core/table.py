from __future__ import annotations

from knot.core.width import pad, str_width, truncate


def render(
    headers: list[str],
    rows: list[list[str]],
    aligns: list[str] | None = None,
    indent: int = 0,
    max_width: int | None = None,
) -> str:
    aligns = aligns or ["left"] * len(headers)
    widths = [str_width(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], str_width(cell))

    if max_width:
        total = sum(widths) + 2 * (len(widths) - 1) + indent
        while total > max_width and max(widths) > 4:
            widest = widths.index(max(widths))
            widths[widest] -= 1
            total -= 1

    prefix = " " * indent

    def line(cells: list[str]) -> str:
        parts = []
        for i, cell in enumerate(cells):
            text = truncate(cell, widths[i]) if str_width(cell) > widths[i] else cell
            parts.append(pad(text, widths[i], aligns[i] if i < len(aligns) else "left"))
        return prefix + "  ".join(parts).rstrip()

    out = [line(headers), prefix + "  ".join("-" * w for w in widths)]
    out.extend(line(row) for row in rows)
    return "\n".join(out)
