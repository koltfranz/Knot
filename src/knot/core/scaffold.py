"""账本骨架生成器：`knot 初始化` 的模板与落盘逻辑。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from knot.core.keywords import EN, ZH, directive_spelling, option_key_spelling
from knot.core.width import pad

ALIAS_FILENAME = "别名.knot"
RULE_DIR = Path("规则")
RULE_FILENAME = "分类规则.knot"

ROOTS_TO_OPEN = (
    "资产:现金",
    "资产:银行:招行",
    "负债:信用卡",
    "权益:期初",
    "收入:工资",
    "费用:餐饮",
    "费用:待分类",
)


@dataclass
class ScaffoldOptions:
    directory: Path
    year: int
    currency: str = "CNY"
    default_asset: str = "资产:现金"
    default_income: str = "收入:其他"
    language: str = ZH
    overwrite: bool = False
    opened_accounts: tuple[str, ...] = ROOTS_TO_OPEN


@dataclass
class ScaffoldResult:
    created: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)


def _spelling(options: ScaffoldOptions):
    lang = options.language
    return lambda canonical: directive_spelling(canonical, lang)


def render_files(options: ScaffoldOptions) -> dict[Path, str]:
    kw = _spelling(options)

    def key(canonical: str) -> str:
        return option_key_spelling(canonical, options.language)

    directory = options.directory

    main = "\n".join(
        [
            "; 结绳 Knot 账本 · 由 `knot 初始化` 生成",
            f"; 版本 {_version()} · 文档见仓库 docs/用户手册.md",
            "",
            f'{kw("option")} "{key("operating_currency")}" "{options.currency}"',
            f'{kw("option")} "{key("default_asset")}" "{options.default_asset}"',
            f'{kw("option")} "{key("default_income")}" "{options.default_income}"',
            f'{kw("option")} "{key("strict")}" "警告"',
            "",
            f'{kw("include")} "{ALIAS_FILENAME}"',
            f'{kw("include")} "{RULE_DIR.as_posix()}/{RULE_FILENAME}"',
            f'{kw("include")} "20*.knot"',
            "",
        ]
    )

    opens = [
        f"{options.year}-01-01 {kw('open')} {pad(account, 18)} {options.currency}"
        for account in options.opened_accounts
    ]
    year_file = "\n".join(
        [
            "; 当年账务 · `记` 会按日期把新交易插入本文件",
            "",
            *opens,
            "",
            "; 期初余额：把 0.00 改为实际数字，或删除整段示例",
            f'{options.year}-01-01 * "期初"',
            f"  {pad('资产:现金', 18)}  0.00 {options.currency}",
            "  权益:期初",
            "",
        ]
    )

    aliases = "\n".join(
        [
            "; 别名 · 格式：别名 = 目标（目标可为完整科目名或命令关键字）",
            "招行 = 资产:银行:招行",
            "微信 = 资产:第三方:微信",
            "咖啡 = 费用:餐饮:咖啡",
            "",
        ]
    )

    rules = "\n".join(
        [
            "; 分类规则 · 格式：收款方 = 科目",
            "; 记账时带 --收款方 会自动追加；导入账单时按此匹配",
            "",
        ]
    )

    gitignore = "\n".join([".venv/", "*.pyz", "*.tmp", "__pycache__/", ""])

    return {
        directory / "main.knot": main,
        directory / f"{options.year}.knot": year_file,
        directory / ALIAS_FILENAME: aliases,
        directory / RULE_DIR / RULE_FILENAME: rules,
        directory / ".gitignore": gitignore,
    }


def _version() -> str:
    from knot.version import __version__

    return __version__


def create_ledger(options: ScaffoldOptions) -> ScaffoldResult:
    result = ScaffoldResult()
    for path, content in render_files(options).items():
        if path.exists() and not options.overwrite:
            result.skipped.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")
        result.created.append(path)
    return result


def language_choices() -> tuple[str, str]:
    return ZH, EN
