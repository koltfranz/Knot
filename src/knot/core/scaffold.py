"""账本骨架生成器：`knot 初始化` / `knot 新建` 的模板与落盘逻辑。"""

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
    "资产:投资:沪深300",
    "负债:信用卡",
    "权益:期初",
    "收入:工资",
    "费用:餐饮",
    "费用:居住:房租",
    "费用:日用品",
    "费用:待分类",
)

SAMPLE_HEADER = "; ── 示例：把下面每行行首的「; 」删掉即可使用（「;;」开头的只是说明）──"

GITIGNORE = ".venv/\n*.pyz\n*.tmp\n*.bak\n__pycache__/\n"


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


def render_sample(lines: list[str]) -> list[str]:
    """示例段落盘：内容行加「; 」前缀；「;;」开头的说明行原样保留。"""
    out = []
    for line in lines:
        if line.startswith(";;") or line == ";":
            out.append(line)
        elif line:
            out.append(f"; {line}")
        else:
            out.append(";")
    return out


def _period(options: ScaffoldOptions) -> str:
    return "monthly" if options.language == EN else "每月"


def sample_lines(options: ScaffoldOptions, kw) -> list[str]:
    """示例账务（注释形式写入年份文件；解注释后必须是合法的）。"""
    year = options.year
    asset = options.default_asset
    return [
        ";; 极简支出：一句话，自动从默认资产出账",
        f'{year}-01-06 "早餐 豆浆油条"  费用:餐饮:早餐  8.50 CNY  @ {asset}',
        ";",
        ";; 收款方 + 摘要 + 标签 + 链接，以及分录元数据（凭证路径等）",
        f'{year}-01-07 * "腾讯" "1月工资" #工资 ^主业',
        "  ; 凭证: ./凭证/2026-01-07-工资.pdf",
        "  收入:工资        -18,000.00 CNY",
        "  资产:银行:招行",
        ";",
        ";; 待分类（?）：落到「费用:待分类」，之后用 `knot 归类` 批量归类",
        f'{year}-01-09 ? "便利店"  费用:待分类  25.00 CNY  @ {asset}',
        ";",
        ";; 多分录：最后一腿不写金额，系统自动配平",
        f'{year}-01-11 * "超市"',
        "  费用:餐饮:食材     128.00 CNY",
        "  费用:日用品         45.00 CNY",
        "  资产:现金",
        ";",
        ";; 定期交易：模板按月展开（只在内存里），改这一处即可改房租",
        f'{year}-01-01 {kw("recur")} "monthly" "房租" from {year}-01-01 to {year}-12-01',
        "  费用:居住:房租   3,500.00 CNY  @ 资产:银行:招行",
        ";",
        f";; 预算：{_period(options)}频率 + 科目 + 金额，`knot 预算` 看进度",
        f"{year}-01-01 {kw('budget')} {_period(options)} 费用:餐饮  2,000.00 CNY",
        ";",
        ";; 投资与成本：{单价 币种} 记成本，price 记报价，`knot 持仓` 看盈亏",
        f'{year}-03-01 * "买入沪深300"',
        "  资产:投资:沪深300     1000 FUND {3.8500 CNY}",
        "  资产:银行:招行      -3,850.00 CNY",
        f"{year}-06-01 {kw('price')} FUND 4.1200 CNY",
        ";",
        ";; 余额断言（金额必须与账实一致，对不上会报错）：",
        f";;   {year}-12-31 {kw('balance')} 资产:银行:招行  12,345.00 CNY",
        ";; 结账：科目不再使用时可标记关闭",
        f"{year}-12-31 {kw('close')} 权益:期初",
        ";",
        ";; 事件：只记录，不参与金额",
        f'{year}-01-01 {kw("event")} "生日" "妈妈"',
    ]


def render_files(options: ScaffoldOptions) -> dict[Path, str]:
    kw = _spelling(options)

    def key(canonical: str) -> str:
        return option_key_spelling(canonical, options.language)

    directory = options.directory

    main = "\n".join(
        [
            "; 结绳 Knot 账本 · 由 `knot 初始化` / `knot 新建` 生成",
            f"; 版本 {_version()} · 文档见仓库 docs/用户手册.md",
            ";",
            "; 本文件是账本入口：写选项、引入其它文件；路径都相对本文件所在目录。",
            "",
            "; 记账币种：报表、自动配平都用它",
            f'{kw("option")} "{key("operating_currency")}" "{options.currency}"',
            "; 默认支出对手科目：`knot 记 38 餐饮` 这类极简写法从这里出账",
            f'{kw("option")} "{key("default_asset")}" "{options.default_asset}"',
            "; 默认收入对手科目：收入类极简写法用它",
            f'{kw("option")} "{key("default_income")}" "{options.default_income}"',
            "; 科目声明宽容度：关闭 / 警告 / 严格（也可写 off / warn / on）",
            f'{kw("option")} "{key("strict")}" "警告"',
            "",
            "; 引入同目录文件，支持通配符",
            f'{kw("include")} "{ALIAS_FILENAME}"',
            f'{kw("include")} "{RULE_DIR.as_posix()}/{RULE_FILENAME}"',
            f'{kw("include")} "20*.knot"',
            "",
        ]
    )

    opens = [
        f"{options.year}-01-01 {kw('open')} {pad(account, 20)} {options.currency}"
        for account in options.opened_accounts
    ]
    year_file = "\n".join(
        [
            "; 当年账务 · `knot 记` 会按日期把新交易插入本文件",
            "",
            "; 开立科目（不写也能记账；这里显式列出，便于按需增删）",
            *opens,
            "",
            "; 期初余额：把 0.00 改成你的实际数字，或删掉这一段",
            f'{options.year}-01-01 * "期初"',
            f"  {pad('资产:现金', 20)}  0.00 {options.currency}",
            "  权益:期初",
            "",
            SAMPLE_HEADER,
            *render_sample(sample_lines(options, kw)),
            "",
        ]
    )

    aliases = "\n".join(
        [
            "; 别名 · 每行「别名 = 目标」，目标可以是完整科目名或命令关键字",
            "; 记账时可直接用在科目位置：`knot 记 38 咖啡 -f 现金`",
            "招行 = 资产:银行:招行",
            "微信 = 资产:第三方:微信",
            "咖啡 = 费用:餐饮:咖啡",
            "",
        ]
    )

    rules = "\n".join(
        [
            "; 分类规则 · 每行「收款方 = 科目」",
            "; 记账时带 --收款方 会自动套用并追加；导入账单时按此匹配",
            "; 例：星巴克 = 费用:餐饮:咖啡",
            "",
        ]
    )

    return {
        directory / "main.knot": main,
        directory / f"{options.year}.knot": year_file,
        directory / ALIAS_FILENAME: aliases,
        directory / RULE_DIR / RULE_FILENAME: rules,
        directory / ".gitignore": GITIGNORE,
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
