from __future__ import annotations

ROOT_NAMES = {
    "资产": "Assets",
    "负债": "Liabilities",
    "权益": "Equity",
    "收入": "Income",
    "费用": "Expenses",
}

ROOT_ALIASES = {
    "A": "资产",
    "Assets": "资产",
    "assets": "资产",
    "L": "负债",
    "Liabilities": "负债",
    "liabilities": "负债",
    "E": "权益",
    "Equity": "权益",
    "equity": "权益",
    "所有者权益": "权益",
    "净资产": "权益",
    "I": "收入",
    "Income": "收入",
    "income": "收入",
    "进账": "收入",
    "X": "费用",
    "Expenses": "费用",
    "expenses": "费用",
    "支出": "费用",
    "开销": "费用",
}

TERMS_ZH = {
    "balance_sheet": "资产负债表",
    "income_statement": "利润表",
    "cash_flow": "现金流量表",
    "trial_balance": "试算平衡表",
    "net_worth": "净资产",
    "debit": "借方",
    "credit": "贷方",
    "posting": "分录",
    "opening_balance": "期初余额",
    "closing_balance": "期末余额",
    "reconciliation": "对账",
}

TERMS_EN = {v: k for k, v in TERMS_ZH.items()}

FLAG_NAMES = {"*": "已确认", "!": "待确认", "?": "待分类", "P": "已对账"}


def translate_root(name: str, lang: str = "zh") -> str:
    if lang == "en":
        head, _, rest = name.partition(":")
        return ROOT_NAMES.get(head, head) + (":" + rest if rest else "")
    return name


def term(key: str, lang: str = "zh") -> str:
    if lang == "en":
        return TERMS_EN.get(key, key)
    return TERMS_ZH.get(key, key)
