from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from knot.core.normalize import normalize_text

WEEKDAYS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}

_RELATIVE = {
    "今天": 0,
    "今日": 0,
    "today": 0,
    "昨天": -1,
    "昨日": -1,
    "yesterday": -1,
    "前天": -2,
    "明天": 1,
    "明日": 1,
    "tomorrow": 1,
    "后天": 2,
}

_ISO_RE = re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$")
_MD_RE = re.compile(r"(\d{1,2})[-/](\d{1,2})$")
_CN_FULL_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})[日号]?$")
_CN_MD_RE = re.compile(r"(\d{1,2})月(\d{1,2})[日号]?$")
_MONTH_RE = re.compile(r"(\d{4})[-/年](\d{1,2})月?$")
_LAST_WEEK_RE = re.compile(r"上周([一二三四五六日天])$")


def _last_day_of_month(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def parse_date(text: str, today: date | None = None) -> date:
    today = today or date.today()
    s = normalize_text(text).strip()
    if not s:
        raise ValueError("日期不能为空")

    if s in _RELATIVE:
        return today + timedelta(days=_RELATIVE[s])

    if m := _CN_FULL_RE.match(s):
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if m := _ISO_RE.match(s):
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if m := _CN_MD_RE.match(s):
        return date(today.year, int(m.group(1)), int(m.group(2)))
    if m := _MD_RE.match(s):
        return date(today.year, int(m.group(1)), int(m.group(2)))
    if m := _LAST_WEEK_RE.match(s):
        monday = today - timedelta(days=today.isoweekday() - 1) - timedelta(days=7)
        return monday + timedelta(days=WEEKDAYS[m.group(1)] - 1)

    raise ValueError(f"无法识别的日期：{text}")


def parse_month(text: str, today: date | None = None) -> tuple[date, date]:
    """解析月份或区间：`2026-09`、`2026年9月`、`9月`、`本月`、`上月`，返回闭区间。"""
    today = today or date.today()
    s = normalize_text(text).strip()

    if s in ("本月", "这个月"):
        first = today.replace(day=1)
        return first, _last_day_of_month(first.year, first.month)
    if s in ("上月", "上个月"):
        first_last = today.replace(day=1) - timedelta(days=1)
        return first_last.replace(day=1), first_last
    if s in ("今年", "本年"):
        return date(today.year, 1, 1), date(today.year, 12, 31)
    if s in ("去年", "上一年"):
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)

    if m := _MONTH_RE.match(s):
        first = date(int(m.group(1)), int(m.group(2)), 1)
        return first, _last_day_of_month(first.year, first.month)

    raise ValueError(f"无法识别的月份：{text}")
