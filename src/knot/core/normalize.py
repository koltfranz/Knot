from __future__ import annotations

import unicodedata
from pathlib import Path

FULLWIDTH_MAP = str.maketrans(
    {
        "：": ":",
        "，": ",",
        "。": ".",
        "（": "(",
        "）": ")",
        "！": "!",
        "？": "?",
        "；": ";",
        "％": "%",
        "／": "/",
        "＼": "\\",
        "－": "-",
        "＿": "_",
        "　": " ",
        "￥": "¥",
        "＄": "$",
        "０": "0",
        "１": "1",
        "２": "2",
        "３": "3",
        "４": "4",
        "５": "5",
        "６": "6",
        "７": "7",
        "８": "8",
        "９": "9",
        "．": ".",
        "＋": "+",
        "＝": "=",
        "＊": "*",
    }
)

CURRENCY_MAP = {
    "¥": "CNY",
    "￥": "CNY",
    "CNY": "CNY",
    "RMB": "CNY",
    "rmb": "CNY",
    "元": "CNY",
    "块": "CNY",
    "人民币": "CNY",
    "$": "USD",
    "USD": "USD",
    "usd": "USD",
    "美元": "USD",
    "HKD": "HKD",
    "港币": "HKD",
    "港元": "HKD",
    "EUR": "EUR",
    "欧元": "EUR",
    "JPY": "JPY",
    "日元": "JPY",
}


class KnotError(Exception):
    """面向用户的错误，携带中文消息。"""


def normalize_text(s: str) -> str:
    s = s.translate(FULLWIDTH_MAP)
    return unicodedata.normalize("NFKC", s)


def normalize_currency(s: str) -> str:
    s = normalize_text(s).strip()
    return CURRENCY_MAP.get(s, s.upper())


def sniff_and_read(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise KnotError(f"无法识别编码：{path}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def read_text_raw(path: Path) -> str:
    """保留原始行尾（不启用通用换行），用于增量写回与格式化。"""
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return fh.read()
