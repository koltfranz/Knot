from __future__ import annotations

import copy
import glob
from dataclasses import dataclass, field
from pathlib import Path

from knot.core.aliases import AliasTable, load_alias_file
from knot.core.diagnostic import Diagnostic
from knot.core.model import Directive, Include, Option, Options
from knot.core.normalize import read_text
from knot.core.parser import Parser
from knot.core.rules import RuleTable, load_rule_file

ALIAS_FILENAME = "别名.knot"
RULE_FILENAME = "分类规则.knot"


@dataclass(slots=True)
class LoadResult:
    directives: list[Directive] = field(default_factory=list)
    options: Options = field(default_factory=Options)
    aliases: AliasTable = field(default_factory=AliasTable)
    rules: RuleTable = field(default_factory=RuleTable)
    sources: dict[str, list[str]] = field(default_factory=dict)
    files: list[Path] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)


class Loader:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, int, int], tuple[list[Directive], list[Diagnostic], str]] = {}

    def _parse_file(self, path: Path) -> tuple[list[Directive], list[Diagnostic], str]:
        stat = path.stat()
        key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
        if key in self._cache:
            directives, diags, text = self._cache[key]
            return copy.deepcopy(directives), copy.deepcopy(diags), text
        text = read_text(path)
        parser = Parser(text, filename=str(path))
        directives, diags = parser.parse()
        self._cache[key] = (directives, diags, text)
        return copy.deepcopy(directives), copy.deepcopy(diags), text

    def load(self, path: Path, missing_ok: bool = False) -> LoadResult:
        result = LoadResult()
        options_pairs: dict[str, str] = {}
        visited: set[Path] = set()

        def process(file: Path, active: frozenset[Path], is_root: bool = False) -> None:
            try:
                resolved = file.resolve()
            except OSError:
                resolved = file
            if resolved in active:
                result.diagnostics.append(
                    Diagnostic(
                        level="error",
                        file=str(file),
                        line=0,
                        col=0,
                        message=f"include 循环：{file}",
                    )
                )
                return
            if resolved in visited:
                return
            visited.add(resolved)

            if not file.exists():
                if missing_ok and is_root:
                    return
                result.diagnostics.append(
                    Diagnostic(
                        level="error",
                        file=str(file),
                        line=0,
                        col=0,
                        message=f"文件不存在：{file}",
                    )
                )
                return

            if file.name == ALIAS_FILENAME:
                result.aliases.update(load_alias_file(file))
                return
            if file.name == RULE_FILENAME:
                table = load_rule_file(file)
                result.rules.update(table)
                if result.rules.path is None:
                    result.rules.path = file
                result.files.append(file)
                return

            directives, diags, text = self._parse_file(file)
            result.diagnostics.extend(diags)
            result.sources[str(file)] = text.splitlines()
            result.files.append(file)

            for directive in directives:
                if isinstance(directive, Include):
                    matches = sorted(glob.glob(str(file.parent / directive.pattern)))
                    if not matches:
                        result.diagnostics.append(
                            Diagnostic(
                                level="warning",
                                file=directive.src_file,
                                line=directive.src_line_start,
                                col=1,
                                message=f"include 未匹配到文件：{directive.pattern}",
                            )
                        )
                        continue
                    for match in matches:
                        process(Path(match), active | {resolved})
                elif isinstance(directive, Option):
                    options_pairs[directive.key] = directive.value
                else:
                    result.directives.append(directive)

        process(path, frozenset(), is_root=True)
        result.options = Options.from_pairs(options_pairs)
        return result


def load_book(path: str | Path, missing_ok: bool = False):
    from knot.core.book import Book, build

    result = Loader().load(Path(path), missing_ok=missing_ok)
    book: Book
    book, diags = build(result.directives, result.options, result.sources, result.aliases)
    return result, book, result.diagnostics + diags
