"""流水批量操作：汇总、打标签、导出、删除（带备份）。

供 TUI 的鼠标多选使用；核心逻辑放在 core，便于单测与后续被 CLI / Web 复用。
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from knot.core.amount import fmt_amount
from knot.core.normalize import KnotError
from knot.core.recur import is_generated
from knot.core.writer import Edit, apply_edits, detect_style, render_transaction

INCOME_ROOT = "收入"
EXPENSE_ROOT = "费用"
EXPORT_FIELDS = ("日期", "标志", "收款方", "摘要", "科目", "金额", "币种", "标签", "来源")


@dataclass
class BulkResult:
    changed: int = 0
    skipped: int = 0
    files: list[Path] = field(default_factory=list)
    backups: list[Path] = field(default_factory=list)


def selection_key(transaction) -> tuple[str, int]:
    """多选标记的键：文件 + 起始行（同一块不会重复）。"""
    return (str(transaction.src_file or ""), int(transaction.src_line_start or 0))


def selectable(transactions) -> tuple[list, int]:
    """可写回的交易：跳过定期展开、去重、要求有效行区间。"""
    seen: set[tuple[str, int, int]] = set()
    picked = []
    skipped = 0
    for transaction in transactions:
        block = (
            str(transaction.src_file or ""),
            int(transaction.src_line_start or 0),
            int(transaction.src_line_end or 0),
        )
        if is_generated(transaction) or not transaction.src_file or transaction.src_line_start <= 0:
            skipped += 1
            continue
        if transaction.src_line_end < transaction.src_line_start:
            skipped += 1
            continue
        if block in seen:
            skipped += 1
            continue
        seen.add(block)
        picked.append(transaction)
    return picked, skipped


def summarize(transactions) -> dict:
    """选中交易的笔数与收支合计（只看收入/费用类非自动分录，转账不虚增）。"""
    items = list(transactions)
    totals: dict[str, Decimal] = {}
    for transaction in items:
        for posting in transaction.postings:
            if posting.generated or posting.units is None:
                continue
            if posting.account.split(":")[0] not in (INCOME_ROOT, EXPENSE_ROOT):
                continue
            currency = posting.units.currency or ""
            totals[currency] = totals.get(currency, Decimal(0)) + abs(posting.units.number)
    return {"笔数": len(items), "收支合计": totals}


def format_totals(totals: dict[str, Decimal]) -> str:
    if not totals:
        return "0.00"
    return " · ".join(
        f"{fmt_amount(value)} {currency}".strip() for currency, value in sorted(totals.items())
    )


def _group(transactions) -> dict[Path, list]:
    groups: dict[Path, list] = {}
    for transaction in transactions:
        groups.setdefault(Path(transaction.src_file), []).append(transaction)
    for items in groups.values():
        items.sort(key=lambda tx: tx.src_line_start)
    return groups


def tag_transactions(transactions, tags) -> BulkResult:
    """给交易追加标签（合并去重），整块重写，未编辑行字节不变。"""
    cleaned = [str(tag).strip().lstrip("#") for tag in tags]
    cleaned = [tag for tag in cleaned if tag]
    if not cleaned:
        raise KnotError("标签不能为空")

    picked, skipped = selectable(transactions)
    result = BulkResult(skipped=skipped)
    for path, items in _group(picked).items():
        indent, newline = detect_style(path)
        edits = []
        for transaction in items:
            transaction.tags = frozenset({*transaction.tags, *cleaned})
            edits.append(
                Edit(
                    transaction.src_line_start,
                    transaction.src_line_end,
                    render_transaction(transaction, indent, newline),
                )
            )
            result.changed += 1
        apply_edits(path, edits)
        result.files.append(path)
    return result


def backup_path(path: Path, stamp: str | None = None) -> Path:
    stamp = stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.name}.{stamp}.bak")


def _is_blank(lines: list[str], index: int) -> bool:
    return 0 <= index < len(lines) and not lines[index].strip()


def delete_transactions(transactions, *, backup: bool = True) -> BulkResult:
    """删除交易块；删除前默认生成时间戳备份。"""
    picked, skipped = selectable(transactions)
    result = BulkResult(skipped=skipped)
    for path, items in _group(picked).items():
        lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
        edits = []
        for transaction in items:
            extra = 1 if _is_blank(lines, transaction.src_line_end) else 0
            edits.append(Edit(transaction.src_line_start, transaction.src_line_end + extra, []))
            result.changed += 1
        if backup:
            target = backup_path(path)
            target.write_bytes(path.read_bytes())
            result.backups.append(target)
        apply_edits(path, edits)
        result.files.append(path)
    return result


def export_transactions(transactions, target: Path, fmt: str = "csv") -> tuple[int, Path]:
    """导出选中交易为 CSV（utf-8-sig，Excel 友好）或 JSON；逐条分录展开。"""
    picked, _skipped = selectable(transactions)
    rows = []
    for transaction in picked:
        for posting in transaction.postings:
            if posting.generated:
                continue
            rows.append(
                {
                    "日期": transaction.date.isoformat(),
                    "标志": transaction.flag.value,
                    "收款方": transaction.payee or "",
                    "摘要": transaction.narration or "",
                    "科目": posting.account,
                    "金额": fmt_amount(posting.units.number) if posting.units else "",
                    "币种": (
                        posting.units.currency if posting.units and posting.units.currency else ""
                    ),
                    "标签": " ".join(f"#{tag}" for tag in sorted(transaction.tags)),
                    "来源": f"{Path(transaction.src_file).name}:{transaction.src_line_start}",
                }
            )
    target.parent.mkdir(parents=True, exist_ok=True)
    if fmt.lower() == "json":
        target.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline=""
        )
    else:
        with target.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(EXPORT_FIELDS))
            writer.writeheader()
            writer.writerows(rows)
    return len(rows), target
