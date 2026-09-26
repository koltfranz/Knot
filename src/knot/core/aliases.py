from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from knot.core.i18n import ROOT_ALIASES
from knot.core.lexer import is_account

BUILTIN_ACCOUNTS: dict[str, str] = {
    "现金": "资产:现金",
    "银行": "资产:银行",
    "招行": "资产:银行:招行",
    "cmb": "资产:银行:招行",
    "建行": "资产:银行:建行",
    "工行": "资产:银行:工行",
    "支付宝": "资产:第三方:支付宝",
    "alipay": "资产:第三方:支付宝",
    "微信": "资产:第三方:微信",
    "wechat": "资产:第三方:微信",
    "余额宝": "资产:投资:余额宝",
    "证券": "资产:投资:证券",
    "信用卡": "负债:信用卡",
    "花呗": "负债:信用卡:花呗",
    "房贷": "负债:贷款:房贷",
    "车贷": "负债:贷款:车贷",
    "工资": "收入:工资",
    "salary": "收入:工资",
    "奖金": "收入:工资:奖金",
    "理财": "收入:投资收益",
    "餐饮": "费用:餐饮",
    "吃饭": "费用:餐饮",
    "早餐": "费用:餐饮:早餐",
    "午餐": "费用:餐饮:午餐",
    "外卖": "费用:餐饮:外卖",
    "交通": "费用:交通",
    "打车": "费用:交通:打车",
    "地铁": "费用:交通:公共交通",
    "房租": "费用:居住:房租",
    "水电": "费用:居住:水电",
    "购物": "费用:购物",
    "医疗": "费用:医疗",
    "娱乐": "费用:娱乐",
    "教育": "费用:教育",
    "人情": "费用:人情往来",
    "待分类": "费用:待分类",
}

COMMAND_ALIASES: dict[str, str] = {
    "记": "add",
    "查": "show",
    "余": "bal",
    "图": "chart",
    "报": "report",
    "检查": "check",
    "整理": "fmt",
    "导入": "import",
    "对账": "reconcile",
    "服务": "serve",
}


@dataclass(slots=True)
class Resolution:
    target: str | None = None
    candidates: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.target is not None


def load_alias_file(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    text = path.read_text(encoding="utf-8-sig")
    for raw in text.splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and value:
            mapping[key] = value
    return mapping


def _canonicalize_roots(text: str) -> str:
    if ":" not in text:
        return ROOT_ALIASES.get(text, text)
    head, _, rest = text.partition(":")
    if head in ROOT_ALIASES:
        return f"{ROOT_ALIASES[head]}:{rest}"
    return text


def is_complete_account(text: str) -> bool:
    return bool(is_account(text)) and (":" in text or text in ROOT_ALIASES.values())


class AliasTable:
    def __init__(self, user: dict[str, str] | None = None) -> None:
        self.user = dict(user or {})

    def update(self, mapping: dict[str, str]) -> None:
        self.user.update(mapping)

    def all(self) -> dict[str, str]:
        return {
            **BUILTIN_ACCOUNTS,
            **{k: v for k, v in self.user.items() if v not in COMMAND_ALIASES},
        }

    def resolve(self, text: str) -> Resolution:
        text = text.strip()
        if not text:
            return Resolution()

        if text in self.user:
            return Resolution(self.user[text])
        if text in BUILTIN_ACCOUNTS:
            return Resolution(BUILTIN_ACCOUNTS[text])

        canonical = _canonicalize_roots(text)
        if canonical != text:
            return self.resolve(canonical)
        if is_complete_account(text):
            return Resolution(text)

        table = {**BUILTIN_ACCOUNTS, **self.user}
        matches = sorted({value for key, value in table.items() if text in key or key in text})
        if len(matches) == 1:
            return Resolution(matches[0])
        return Resolution(None, matches)
