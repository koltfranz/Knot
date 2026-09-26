"""记账表单：字段导航 + cooked 模式文本输入。"""

from __future__ import annotations

from dataclasses import dataclass, field

FIELDS = (
    ("金额", "金额", True),
    ("科目", "科目", True),
    ("来自", "来源科目", False),
    ("去向", "目标科目", False),
    ("日期", "日期", False),
    ("摘要", "摘要", False),
    ("收款方", "收款方", False),
    ("标签", "标签（逗号分隔）", False),
)


@dataclass
class Form:
    values: dict[str, str] = field(default_factory=dict)
    index: int = 0

    def labels(self) -> list[tuple[str, str]]:
        return [(name, label) for name, label, _required in FIELDS]

    def current(self) -> str:
        return FIELDS[self.index][0]

    def move(self, delta: int) -> None:
        self.index = (self.index + delta) % len(FIELDS)

    def set(self, value: str) -> None:
        self.values[self.current()] = value

    def missing(self) -> list[str]:
        return [label for name, label, required in FIELDS if required and not self.values.get(name)]

    def as_payload(self) -> dict:
        payload = {}
        for name, value in self.values.items():
            if name == "标签" and value:
                payload[name] = [
                    item.strip() for item in value.replace("，", ",").split(",") if item.strip()
                ]
            elif value:
                payload[name] = value
        return payload

    def render_lines(self, width: int) -> list[str]:
        lines = []
        for index, (name, label, required) in enumerate(FIELDS):
            value = self.values.get(name, "")
            marker = "▸" if index == self.index else " "
            hint = "（必填）" if required and not value else ""
            lines.append(f"{marker} {label:<12}{value or '…'}{hint}")
        return lines
