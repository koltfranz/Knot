from __future__ import annotations

from pathlib import Path


def load_rule_file(path: Path) -> dict[str, str]:
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


class RuleTable:
    def __init__(self, mapping: dict[str, str] | None = None, path: Path | None = None) -> None:
        self.rules = dict(mapping or {})
        self.path = path

    def update(self, mapping: dict[str, str]) -> None:
        self.rules.update(mapping)

    def match(self, payee: str) -> str | None:
        if not payee:
            return None
        for key, account in self.rules.items():
            if key in payee:
                return account
        return None

    def learn(self, payee: str, account: str) -> bool:
        if not payee or self.rules.get(payee) == account:
            return False
        self.rules[payee] = account
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self.path.write_text(
                    "; 规则/分类规则.knot\n; 收款方 = 科目\n", encoding="utf-8", newline=""
                )
            with self.path.open("a", encoding="utf-8", newline="") as fh:
                fh.write(f"{payee} = {account}\n")
        return True
