"""生成大规模测试账本（性能验收用）。

用法：python scripts/性能基准.py [交易数] [输出目录]
"""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path

ACCOUNTS = [
    "费用:餐饮:早餐",
    "费用:餐饮:午餐",
    "费用:餐饮:外卖",
    "费用:交通:打车",
    "费用:交通:公共交通",
    "费用:购物",
    "费用:居住:水电",
    "费用:娱乐",
]
ASSETS = ["资产:现金", "资产:银行:招行", "资产:银行:建行", "资产:第三方:微信"]
INCOME = ["收入:工资", "收入:投资收益"]
PAYEES = ["星巴克", "美团外卖", "滴滴出行", "永辉超市", "京东", "便利店", "地铁", "电影院"]


def generate(count: int, target: Path) -> Path:
    random.seed(20260926)
    lines = [
        'option "operating_currency" "CNY"',
        'option "strict" "off"',
        "",
        "2026-01-01 open 资产:现金 CNY",
        "2026-01-01 open 资产:银行:招行 CNY",
        "2026-01-01 open 资产:银行:建行 CNY",
        "2026-01-01 open 资产:第三方:微信 CNY",
        "2026-01-01 open 权益:期初",
        "2026-01-01 open 收入:工资 CNY",
        "2026-01-01 open 收入:投资收益 CNY",
        *[f"2026-01-01 open {name}" for name in ACCOUNTS],
        "",
        '2026-01-01 * "期初"',
        "  资产:银行:招行     200,000.00 CNY",
        "  权益:期初",
        "",
    ]
    day = 1
    month = 1
    for index in range(count):
        day += 1
        if day > 28:
            day = 1
            month = month % 12 + 1
        when = f"2026-{month:02d}-{day:02d}"
        payee = PAYEES[index % len(PAYEES)]
        if index % 40 == 0:
            lines.append(f'{when} * "{payee}"   收入:工资   -18,000.00 CNY  @ 资产:银行:招行')
        elif index % 17 == 0:
            gain = random.randint(50, 900)
            lines.append(f'{when} * "{payee}"   收入:投资收益   -{gain}.00 CNY  @ 资产:银行:招行')
        else:
            account = ACCOUNTS[index % len(ACCOUNTS)]
            amount = f"{random.randint(5, 480)}.{random.randint(0, 99):02d}"
            asset = ASSETS[index % len(ASSETS)]
            lines.append(f'{when} "{payee}"   {account}  {amount} CNY  @ {asset}')
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return target


def benchmark(ledger: Path) -> dict:
    from knot.core.budget import rows as budget_rows
    from knot.core.inventory import net_worth_in
    from knot.core.loader import load_book
    from knot.core.report import balance_sheet, expense_by_category, monthly_flow
    from knot.core.sql import execute

    started = time.perf_counter()
    _result, book, diags = load_book(ledger)
    parse_time = time.perf_counter() - started
    errors = [d for d in diags if d.level == "error"]

    started = time.perf_counter()
    monthly_flow(book)
    expense_by_category(book)
    balance_sheet(book)
    net_worth_in(book)
    budget_rows(book)
    execute(book, "SELECT 合计(金额) FROM 分录 GROUP BY 科目")
    report_time = time.perf_counter() - started

    return {
        "交易数": len(book.transactions),
        "科目数": len(book.used_accounts()),
        "解析与校验（秒）": round(parse_time, 3),
        "报表与查询（秒）": round(report_time, 3),
        "错误数": len(errors),
    }


def main(argv: list[str]) -> int:
    count = int(argv[0]) if argv else 30000
    directory = Path(argv[1]) if len(argv) > 1 else Path("dist") / "性能"
    directory.mkdir(parents=True, exist_ok=True)
    ledger = generate(count, directory / "main.knot")

    size_mb = ledger.stat().st_size / 1024 / 1024
    print(f"已生成 {ledger}（{count} 笔，{size_mb:.1f} MB）")
    outcome = benchmark(ledger)
    for key, value in outcome.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
