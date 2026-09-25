from __future__ import annotations

import difflib
import re
from datetime import date

from knot.core.amount import parse_decimal
from knot.core.diagnostic import Diagnostic
from knot.core.lexer import (
    DATE_LINE_RE,
    KEYWORDS,
    Token,
    is_account,
    is_currency,
    is_date,
    is_flag,
    is_number,
    lex_line,
)
from knot.core.model import (
    Amount,
    Balance,
    Budget,
    Close,
    Commodity,
    Cost,
    Directive,
    Event,
    Flag,
    Include,
    Open,
    Option,
    Posting,
    Price,
    Recur,
    Transaction,
)

META_RE = re.compile(r";\s*([^:：]+)[:：]\s*(.*)$")

PERIODS = {"daily", "weekly", "monthly", "quarterly", "yearly"}


def _to_date(text: str, token: Token) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ParseError(f"非法日期：{text}", token.line, token.col, caret=text) from exc


class ParseError(Exception):
    def __init__(
        self, message: str, line: int, col: int, caret: str = "", suggestion: str | None = None
    ):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        self.caret = caret
        self.suggestion = suggestion


class Parser:
    def __init__(self, text: str, filename: str = "") -> None:
        self.lines = text.splitlines()
        self.filename = filename
        self.diags: list[Diagnostic] = []

    def _diag(
        self,
        level: str,
        line: int,
        col: int,
        message: str,
        caret: str = "",
        suggestion: str | None = None,
    ) -> None:
        snippet = self.lines[line - 1] if 0 < line <= len(self.lines) else None
        self.diags.append(
            Diagnostic(
                level=level,
                file=self.filename,
                line=line,
                col=col,
                message=message,
                suggestion=suggestion,
                snippet=snippet,
                caret=caret or None,
            )
        )

    def parse(self) -> tuple[list[Directive], list[Diagnostic]]:
        directives: list[Directive] = []
        i, n = 0, len(self.lines)
        while i < n:
            raw = self.lines[i]
            if not raw.strip():
                i += 1
                continue
            if raw[0].isspace():
                self._diag("error", i + 1, 1, "意外的缩进行：缺少指令头", caret=raw.strip()[:1])
                i = self._panic(i + 1)
                continue
            if raw.lstrip().startswith(";"):
                i += 1
                continue
            try:
                directive, i = self._parse_toplevel(i)
                if directive is not None:
                    directives.append(directive)
            except ParseError as exc:
                self._diag(
                    "error",
                    exc.line,
                    exc.col,
                    exc.message,
                    caret=exc.caret or "",
                    suggestion=exc.suggestion,
                )
                i = self._panic(i + 1)
        return directives, self.diags

    def _panic(self, i: int) -> int:
        while i < len(self.lines):
            line = self.lines[i]
            if line and not line[0].isspace() and DATE_LINE_RE.match(line):
                return i
            stripped = line.strip()
            if stripped.startswith("option ") or stripped.startswith("include "):
                return i
            i += 1
        return i

    def _lex(self, i: int) -> list[Token]:
        tokens, lex_diags = lex_line(self.lines[i], i + 1)
        for d in lex_diags:
            d.file = self.filename
            self.diags.append(d)
        return tokens

    def _consume_block(self, i: int) -> tuple[list[tuple[int, str]], int]:
        block: list[tuple[int, str]] = []
        j = i + 1
        while j < len(self.lines):
            line = self.lines[j]
            if not line.strip() or not line[0].isspace():
                break
            block.append((j, line))
            j += 1
        return block, j

    def _parse_toplevel(self, i: int) -> tuple[Directive | None, int]:
        tokens = self._lex(i)
        if not tokens:
            return None, i + 1
        first = tokens[0]
        if first.kind == "word":
            if first.text == "option":
                return self._parse_option(tokens, i)
            if first.text == "include":
                return self._parse_include(tokens, i)
            if first.text in KEYWORDS:
                raise ParseError(
                    f"指令缺少日期：{first.text}", first.line, first.col, caret=first.text
                )
        if first.kind == "word" and is_date(first.text):
            if len(tokens) >= 2 and tokens[1].kind == "word" and tokens[1].text in KEYWORDS:
                return self._parse_dated(tokens, i)
            if (
                len(tokens) >= 2
                and tokens[1].kind == "word"
                and not is_flag(tokens[1].text)
                and not is_number(tokens[1].text)
            ):
                close = difflib.get_close_matches(tokens[1].text, KEYWORDS, n=1, cutoff=0.8)
                if close:
                    raise ParseError(
                        f"未知指令：{tokens[1].text}",
                        tokens[1].line,
                        tokens[1].col,
                        caret=tokens[1].text,
                        suggestion=f'是否意为 "{close[0]}"？',
                    )
            return self._parse_transaction(tokens, i)
        close = difflib.get_close_matches(first.text, KEYWORDS, n=1)
        suggestion = f'是否意为 "{close[0]}"？' if close else None
        raise ParseError(
            f"无法识别的指令：{first.text}",
            first.line,
            first.col,
            caret=first.text,
            suggestion=suggestion,
        )

    def _expect_end(self, tokens: list[Token], idx: int) -> None:
        if idx < len(tokens):
            t = tokens[idx]
            raise ParseError(f"多余的记号：{t.text}", t.line, t.col, caret=t.text)

    def _parse_option(self, tokens: list[Token], i: int) -> tuple[Directive, int]:
        key = tokens[1] if len(tokens) > 1 else None
        value = tokens[2] if len(tokens) > 2 else None
        if key is None or key.kind != "string" or value is None or value.kind != "string":
            t = tokens[0]
            raise ParseError(
                'option 需要两个字符串：option "键" "值"', t.line, t.col, caret="option"
            )
        self._expect_end(tokens, 3)
        return Option(key.text, value.text, self.filename, i + 1, i + 1), i + 1

    def _parse_include(self, tokens: list[Token], i: int) -> tuple[Directive, int]:
        target = tokens[1] if len(tokens) > 1 else None
        if target is None or target.kind != "string":
            t = tokens[0]
            raise ParseError("include 需要一个字符串路径", t.line, t.col, caret="include")
        self._expect_end(tokens, 2)
        return Include(target.text, self.filename, i + 1, i + 1), i + 1

    def _parse_dated(self, tokens: list[Token], i: int) -> tuple[Directive, int]:
        d = _to_date(tokens[0].text, tokens[0])
        keyword = tokens[1].text
        rest = tokens[2:]
        handler = {
            "open": self._parse_open,
            "close": self._parse_close,
            "balance": self._parse_balance,
            "price": self._parse_price,
            "commodity": self._parse_commodity,
            "recur": self._parse_recur,
            "budget": self._parse_budget,
            "event": self._parse_event,
        }[keyword]
        return handler(d, rest, i)

    def _amount_from(self, tokens: list[Token], idx: int, required: bool = True):
        if idx >= len(tokens) or tokens[idx].kind != "word" or not is_number(tokens[idx].text):
            if required:
                t = tokens[idx - 1] if idx else tokens[0]
                raise ParseError("缺少金额", t.line, t.col, caret=t.text)
            return None, idx
        number = parse_decimal(tokens[idx].text)
        idx += 1
        currency = ""
        if idx < len(tokens) and tokens[idx].kind == "word" and is_currency(tokens[idx].text):
            currency = tokens[idx].text
            idx += 1
        return Amount(number, currency), idx

    def _account_from(self, tokens: list[Token], idx: int, what: str = "科目"):
        if (
            idx >= len(tokens)
            or tokens[idx].kind != "word"
            or not is_account(tokens[idx].text)
            or is_number(tokens[idx].text)
            or is_flag(tokens[idx].text)
        ):
            t = tokens[idx] if idx < len(tokens) else tokens[idx - 1]
            raise ParseError(f"{what}名非法：{t.text}", t.line, t.col, caret=t.text)
        return tokens[idx].text, idx + 1

    def _parse_open(self, d: date, tokens: list[Token], i: int) -> tuple[Directive, int]:
        account, idx = self._account_from(tokens, 0)
        currencies: list[str] = []
        while idx < len(tokens) and tokens[idx].kind == "word" and is_currency(tokens[idx].text):
            currencies.append(tokens[idx].text)
            idx += 1
        self._expect_end(tokens, idx)
        return Open(d, account, tuple(currencies), {}, self.filename, i + 1, i + 1), i + 1

    def _parse_close(self, d: date, tokens: list[Token], i: int) -> tuple[Directive, int]:
        account, idx = self._account_from(tokens, 0)
        self._expect_end(tokens, idx)
        return Close(d, account, self.filename, i + 1, i + 1), i + 1

    def _parse_balance(self, d: date, tokens: list[Token], i: int) -> tuple[Directive, int]:
        account, idx = self._account_from(tokens, 0)
        amount, idx = self._amount_from(tokens, idx)
        self._expect_end(tokens, idx)
        return Balance(d, account, amount, self.filename, i + 1, i + 1), i + 1

    def _parse_price(self, d: date, tokens: list[Token], i: int) -> tuple[Directive, int]:
        if not tokens or tokens[0].kind != "word":
            t = tokens[0] if tokens else Token("word", "price", 0, 0)
            raise ParseError("price 缺少商品代码", t.line, t.col, caret=t.text)
        commodity = tokens[0].text
        amount, idx = self._amount_from(tokens, 1)
        self._expect_end(tokens, idx)
        return Price(d, commodity, amount, self.filename, i + 1, i + 1), i + 1

    def _parse_commodity(self, d: date, tokens: list[Token], i: int) -> tuple[Directive, int]:
        if not tokens or tokens[0].kind != "word":
            t = tokens[0] if tokens else Token("word", "commodity", 0, 0)
            raise ParseError("commodity 缺少代码", t.line, t.col, caret=t.text)
        self._expect_end(tokens, 1)
        return Commodity(d, tokens[0].text, self.filename, i + 1, i + 1), i + 1

    def _parse_recur(self, d: date, tokens: list[Token], i: int) -> tuple[Directive, int]:
        if len(tokens) < 2 or tokens[0].kind != "string" or tokens[1].kind != "string":
            t = tokens[0] if tokens else Token("word", "recur", 0, 0)
            raise ParseError('recur 需要："周期" "说明" from 起 to 止', t.line, t.col, caret=t.text)
        period, description = tokens[0].text, tokens[1].text
        if period.lower() not in PERIODS and period not in (
            "每天",
            "每周",
            "每月",
            "每季度",
            "每年",
        ):
            raise ParseError(f"未知周期：{period}", tokens[0].line, tokens[0].col, caret=period)
        idx = 2
        date_from = date_to = None
        while idx < len(tokens):
            t = tokens[idx]
            if t.kind == "word" and t.text == "from" and idx + 1 < len(tokens):
                date_from = _to_date(tokens[idx + 1].text, tokens[idx + 1])
                idx += 2
            elif t.kind == "word" and t.text == "to" and idx + 1 < len(tokens):
                date_to = _to_date(tokens[idx + 1].text, tokens[idx + 1])
                idx += 2
            else:
                raise ParseError(f"recur 出现意外记号：{t.text}", t.line, t.col, caret=t.text)
        if date_from is None:
            raise ParseError(
                "recur 缺少 from 起始日期", tokens[0].line, tokens[0].col, caret="recur"
            )
        postings, next_i = self._parse_postings_block(i)
        return Recur(
            d, period, description, date_from, date_to, postings, self.filename, i + 1, next_i
        ), next_i

    def _parse_budget(self, d: date, tokens: list[Token], i: int) -> tuple[Directive, int]:
        if not tokens or tokens[0].kind != "word":
            t = tokens[0] if tokens else Token("word", "budget", 0, 0)
            raise ParseError("budget 缺少周期", t.line, t.col, caret=t.text)
        period = tokens[0].text
        account, idx = self._account_from(tokens, 1)
        amount, idx = self._amount_from(tokens, idx)
        self._expect_end(tokens, idx)
        return Budget(d, period, account, amount, self.filename, i + 1, i + 1), i + 1

    def _parse_event(self, d: date, tokens: list[Token], i: int) -> tuple[Directive, int]:
        if len(tokens) < 2 or tokens[0].kind != "string" or tokens[1].kind != "string":
            t = tokens[0] if tokens else Token("word", "event", 0, 0)
            raise ParseError('event 需要两个字符串："名称" "值"', t.line, t.col, caret=t.text)
        self._expect_end(tokens, 2)
        return Event(d, tokens[0].text, tokens[1].text, self.filename, i + 1, i + 1), i + 1

    def _parse_posting(self, tokens: list[Token], idx: int, lineno: int) -> tuple[Posting, int]:
        account, idx = self._account_from(tokens, idx)
        posting = Posting(account)
        if idx < len(tokens) and tokens[idx].kind == "word" and is_number(tokens[idx].text):
            amount, idx = self._amount_from(tokens, idx)
            posting.units = amount
        while idx < len(tokens):
            t = tokens[idx]
            if t.kind == "lbrace":
                amount, idx = self._amount_from(tokens, idx + 1)
                if idx >= len(tokens) or tokens[idx].kind != "rbrace":
                    raise ParseError("成本表达式缺少 }", t.line, t.col, caret=t.text)
                idx += 1
                posting.cost = Cost(amount.number, amount.currency, kind="unit")
            elif t.kind == "atat":
                amount, idx = self._amount_from(tokens, idx + 1)
                posting.cost = Cost(amount.number, amount.currency, kind="total")
            elif t.kind == "at":
                nxt = tokens[idx + 1] if idx + 1 < len(tokens) else None
                if nxt is not None and nxt.kind == "word" and is_number(nxt.text):
                    amount, idx = self._amount_from(tokens, idx + 1)
                    posting.cost = Cost(amount.number, amount.currency, kind="price")
                elif nxt is not None and nxt.kind == "word" and is_account(nxt.text):
                    posting.counterparty = nxt.text
                    idx += 2
                else:
                    raise ParseError(" @ 之后应为单价或对手科目", t.line, t.col, caret=t.text)
            elif t.kind == "word" and is_account(t.text):
                break
            else:
                raise ParseError(f"分录中出现意外记号：{t.text}", t.line, t.col, caret=t.text)
        return posting, idx

    def _parse_postings_block(self, i: int) -> tuple[list[Posting], int]:
        postings: list[Posting] = []
        block, next_i = self._consume_block(i)
        for lineno, _line in block:
            tokens = self._lex(lineno)
            if not tokens:
                continue
            if tokens[0].kind == "comment":
                continue
            idx = 0
            while idx < len(tokens):
                posting, idx = self._parse_posting(tokens, idx, lineno)
                postings.append(posting)
        return postings, next_i

    def _parse_transaction(self, tokens: list[Token], i: int) -> tuple[Directive, int]:
        when = _to_date(tokens[0].text, tokens[0])
        idx = 1
        flag = Flag.OK
        if idx < len(tokens) and tokens[idx].kind == "word" and is_flag(tokens[idx].text):
            flag = Flag(tokens[idx].text)
            idx += 1

        strings: list[str] = []
        tags: set[str] = set()
        links: set[str] = set()
        while idx < len(tokens):
            t = tokens[idx]
            if t.kind == "string":
                strings.append(t.text)
                idx += 1
            elif t.kind == "tag":
                tags.add(t.text)
                idx += 1
            elif t.kind == "link":
                links.add(t.text)
                idx += 1
            elif t.kind == "word" and is_account(t.text):
                break
            else:
                raise ParseError(f"交易头部出现意外记号：{t.text}", t.line, t.col, caret=t.text)
        if len(strings) > 2:
            t = tokens[0]
            raise ParseError(
                "交易头部最多两个字符串（收款方、摘要）", t.line, t.col, caret=strings[2]
            )

        postings: list[Posting] = []
        while idx < len(tokens):
            posting, idx = self._parse_posting(tokens, idx, i + 1)
            postings.append(posting)

        meta: dict[str, str] = {}
        block, next_i = self._consume_block(i)
        for lineno, _line in block:
            tokens_b = self._lex(lineno)
            if not tokens_b:
                continue
            if tokens_b[0].kind == "comment":
                m = META_RE.match(tokens_b[0].text)
                if m:
                    key, value = m.group(1).strip(), m.group(2).strip()
                    if postings:
                        postings[-1].meta[key] = value
                    else:
                        meta[key] = value
                continue
            pos = 0
            while pos < len(tokens_b):
                posting, pos = self._parse_posting(tokens_b, pos, lineno)
                postings.append(posting)

        if not postings:
            t = tokens[0]
            raise ParseError("交易没有任何分录", t.line, t.col, caret=t.text)

        payee = strings[0] if len(strings) >= 2 else None
        narration = strings[1] if len(strings) >= 2 else (strings[0] if strings else "")
        tx = Transaction(
            date=when,
            flag=flag,
            payee=payee,
            narration=narration,
            postings=postings,
            tags=frozenset(tags),
            links=frozenset(links),
            meta=meta,
            src_file=self.filename,
            src_line_start=i + 1,
            src_line_end=next_i,
        )
        return tx, next_i
