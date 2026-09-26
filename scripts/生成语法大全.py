"""从 core/keywords.py 生成 docs/语法大全.md 中的对照表。

用法：
    python scripts/生成语法大全.py            # 写入文档
    python scripts/生成语法大全.py --检查      # 只校验文档与代码是否一致（退出码 1 表示不一致）
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "语法大全.md"
START = "<!-- keywords:start -->"
END = "<!-- keywords:end -->"

sys.path.insert(0, str(ROOT / "src"))

from knot.core.keywords import (  # noqa: E402
    DIRECTIVE_NOTES,
    DIRECTIVES,
    OPTION_KEY_NOTES,
    OPTION_KEYS,
    OPTION_VALUES,
    PERIODS,
    VALUE_ORDER,
)


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _option_value_cell(key: str) -> str:
    table = OPTION_VALUES.get(key, {})
    order = VALUE_ORDER.get(key, ())
    parts: list[str] = []
    for canonical in order:
        zh = next(
            (name for name, target in table.items() if target == canonical and name != canonical),
            None,
        )
        parts.append(f"`{canonical}` / `{zh}`" if zh else f"`{canonical}`")
    return "、".join(parts) if parts else "—"


def render_tables() -> str:
    blocks: list[str] = []

    blocks.append("**账本指令**\n")
    blocks.append(
        _table(
            ["英文", "中文", "说明"],
            [[f"`{en}`", f"`{zh}`", DIRECTIVE_NOTES.get(en, "")] for en, zh in DIRECTIVES.items()],
        )
    )

    blocks.append("\n**选项键**\n")
    blocks.append(
        _table(
            ["英文", "中文", "取值", "说明"],
            [
                [f"`{en}`", f"`{zh}`", _option_value_cell(en), OPTION_KEY_NOTES.get(en, "")]
                for en, zh in OPTION_KEYS.items()
            ],
        )
    )

    blocks.append("\n**周期**\n")
    blocks.append(
        _table(
            ["英文", "中文"],
            [[f"`{en}`", f"`{zh}`"] for en, zh in PERIODS.items()],
        )
    )

    blocks.append("\n**标志（符号固定，中文仅用于展示）**\n")
    blocks.append(
        _table(
            ["符号", "中文名", "含义"],
            [
                ["`*`", "已确认", "默认，可省略"],
                ["`!`", "待确认", "需复核"],
                ["`?`", "待分类", "导入与快速记账的收件箱，默认落 `费用:待分类`"],
                ["`P`", "已对账", "已与账单核对"],
            ],
        )
    )

    return "\n".join(blocks)


def apply_to_document(text: str, generated: str) -> str:
    if START not in text or END not in text:
        raise SystemExit(f"文档缺少标记 {START} / {END}")
    head, _, rest = text.partition(START)
    _, _, tail = rest.partition(END)
    return f"{head}{START}\n\n{generated}\n\n{END}{tail}"


def main(argv: list[str]) -> int:
    generated = render_tables()
    current = DOC.read_text(encoding="utf-8")
    expected = apply_to_document(current, generated)

    if "--检查" in argv or "--check" in argv:
        if current == expected:
            print("语法大全与关键字表一致")
            return 0
        print("语法大全与关键字表不一致，请运行：python scripts/生成语法大全.py", file=sys.stderr)
        return 1

    if current == expected:
        print(f"无需更新：{DOC}")
        return 0
    DOC.write_text(expected, encoding="utf-8", newline="")
    print(f"已更新：{DOC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
