"""黄金测试驱动器：输入账本 + 期望输出 JSON。"""

from __future__ import annotations

import json
import pathlib

from knot.core.diagnostic import count
from knot.core.loader import load_book

DATA_DIR = pathlib.Path(__file__).resolve().parents[1] / "schema" / "测试数据"

CASES = sorted(p for p in DATA_DIR.glob("*.knot") if p.name != "别名.knot")


def load_case(ledger_path: pathlib.Path) -> dict:
    expected_path = ledger_path.with_suffix(".expected.json")
    if not expected_path.exists():
        raise AssertionError(f"缺少期望文件：{expected_path.name}")
    return json.loads(expected_path.read_text(encoding="utf-8"))


def run_case(ledger_path: pathlib.Path) -> tuple[dict, object, list]:
    expected = load_case(ledger_path)
    _result, book, diags = load_book(ledger_path)
    return expected, book, diags


def error_lines(diags: list) -> list[int]:
    return sorted(d.line for d in diags if d.level == "error")


def error_count(diags: list) -> int:
    return count(diags, "error")
