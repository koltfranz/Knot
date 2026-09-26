"""关键字中英双写的单一事实源。

账本中的指令、选项键、选项值与周期同时接受中文与英文写法，
本模块是唯一维护点；其它模块 MUST NOT 自行硬编码关键字字面量。
"""

from __future__ import annotations

ZH = "zh"
EN = "en"

DIRECTIVES: dict[str, str] = {
    "option": "选项",
    "include": "引入",
    "open": "开立",
    "close": "关闭",
    "balance": "断言",
    "price": "报价",
    "commodity": "商品",
    "recur": "定期",
    "budget": "预算",
    "event": "事件",
    "from": "起",
    "to": "止",
}

OPTION_KEYS: dict[str, str] = {
    "operating_currency": "记账币种",
    "strict": "严格度",
    "default_asset": "默认资产",
    "default_income": "默认收入",
    "account_language": "科目语言",
    "sort_accounts": "科目排序",
    "pinyin": "拼音",
    "write_bom": "写入BOM",
    "keyword_language": "关键字语言",
}

OPTION_VALUES: dict[str, dict[str, str]] = {
    "strict": {
        "off": "off",
        "warn": "warn",
        "on": "on",
        "关闭": "off",
        "警告": "warn",
        "严格": "on",
    },
    "account_language": {"zh": "zh", "en": "en", "中文": "zh", "英文": "en"},
    "keyword_language": {
        "auto": "auto",
        "zh": "zh",
        "en": "en",
        "自动": "auto",
        "中文": "zh",
        "英文": "en",
    },
    "sort_accounts": {
        "unicode": "unicode",
        "pinyin": "pinyin",
        "按码位": "unicode",
        "拼音": "pinyin",
    },
    "pinyin": {"on": "on", "off": "off", "开": "on", "关": "off"},
    "write_bom": {"on": "on", "off": "off", "开": "on", "关": "off"},
}

PERIODS: dict[str, str] = {
    "daily": "每天",
    "weekly": "每周",
    "monthly": "每月",
    "quarterly": "每季度",
    "yearly": "每年",
}

DIRECTIVE_NOTES: dict[str, str] = {
    "option": "全局设置，同键后者覆盖前者",
    "include": "引入文件或通配符，解析期展开",
    "open": "开立科目，可带币种",
    "close": "关闭科目",
    "balance": "余额断言：该日期（含）前科目应有余额",
    "price": "报价 / 汇率",
    "commodity": "商品声明",
    "recur": "定期交易模板，仅内存展开不写回",
    "budget": "预算",
    "event": "备忘事件",
    "from": "定期交易的起始日期，与 recur 同用",
    "to": "定期交易的结束日期，与 recur 同用",
}

OPTION_KEY_NOTES: dict[str, str] = {
    "operating_currency": "记账币种，默认 CNY",
    "strict": "科目声明宽容度",
    "default_asset": "支出默认对手科目",
    "default_income": "收入默认对手科目",
    "account_language": "科目名显示语言",
    "sort_accounts": "科目排序方式",
    "pinyin": "拼音检索（M4）",
    "write_bom": "写入是否带 BOM",
    "keyword_language": "关键字写回语言：跟随文件 / 中文 / 英文",
}

VALUE_ORDER: dict[str, tuple[str, ...]] = {
    "strict": ("off", "warn", "on"),
    "account_language": ("zh", "en"),
    "keyword_language": ("auto", "zh", "en"),
    "sort_accounts": ("unicode", "pinyin"),
    "pinyin": ("on", "off"),
    "write_bom": ("on", "off"),
}

DIRECTIVE_LOOKUP: dict[str, str] = {
    **{name: name for name in DIRECTIVES},
    **{zh: name for name, zh in DIRECTIVES.items()},
}

_OPTION_KEY_LOOKUP: dict[str, str] = {
    **{name: name for name in OPTION_KEYS},
    **{zh: name for name, zh in OPTION_KEYS.items()},
}

_PERIOD_LOOKUP: dict[str, str] = {
    **{name: name for name in PERIODS},
    **{zh: name for name, zh in PERIODS.items()},
}


def canonical_directive(word: str) -> str | None:
    return DIRECTIVE_LOOKUP.get(word)


def directive_spelling(canonical: str, lang: str = ZH) -> str:
    if lang == EN:
        return canonical
    return DIRECTIVES.get(canonical, canonical)


def all_directive_spellings() -> list[str]:
    return sorted(DIRECTIVE_LOOKUP)


def canonical_option_key(key: str) -> str:
    return _OPTION_KEY_LOOKUP.get(key, key)


def option_key_spelling(canonical: str, lang: str = ZH) -> str:
    if lang == EN:
        return canonical
    return OPTION_KEYS.get(canonical, canonical)


def canonical_option_value(key: str, value: str) -> str:
    canonical_key = canonical_option_key(key)
    table = OPTION_VALUES.get(canonical_key, {})
    return table.get(value, value)


def canonical_period(period: str) -> str | None:
    return _PERIOD_LOOKUP.get(period)


def period_spelling(canonical: str, lang: str = ZH) -> str:
    if lang == EN:
        return canonical
    return PERIODS.get(canonical, canonical)


def detect_language(lines: list[str]) -> str:
    zh_hits = en_hits = 0
    for line in lines:
        if not line or line[0].isspace() or line.lstrip().startswith(";"):
            continue
        for token in line.split()[:2]:
            canonical = DIRECTIVE_LOOKUP.get(token)
            if canonical is None:
                continue
            if token == canonical:
                en_hits += 1
            else:
                zh_hits += 1
            break
    return EN if en_hits > zh_hits else ZH


def write_language(preference: str, file_language: str | None = None) -> str:
    """写回语言：显式设置优先，其次按文件跟随，最后默认中文。"""
    if preference in (ZH, EN):
        return preference
    if file_language in (ZH, EN):
        return file_language
    return ZH
