from __future__ import annotations

import argparse

BASH_TEMPLATE = """# knot bash 补全：source 本文件或置于 /etc/bash_completion.d/
_knot_complete() {{
    local cur prev commands opts
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    commands="{commands}"
    opts="{opts}"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$commands $opts" -- "$cur") )
        return 0
    fi
    COMPREPLY=( $(compgen -f -- "$cur") )
    return 0
}}
complete -o default -F _knot_complete knot
"""

ZSH_TEMPLATE = """#compdef knot
_knot() {{
    local -a commands
    commands=({commands})
    _arguments '*: :->args'
    if (( CURRENT == 2 )); then
        _describe 'command' commands
    else
        _files
    fi
}}
_knot "$@"
"""

FISH_TEMPLATE = """# knot fish 补全：置于 ~/.config/fish/completions/knot.fish
complete -c knot -f
{lines}
"""

POWERSHELL_TEMPLATE = """# 结绳 Knot PowerShell 补全
# 生成：knot --补全 powershell > knot-completion.ps1
# 启用：在 $PROFILE 里加一行  . "$HOME\\knot-completion.ps1"
$__knotCommands = @(__COMMANDS__)
$__knotOptions = @('--账本', '--ledger', '--补全', '--completion', '--version', '-h', '--help')
Register-ArgumentCompleter -Native -CommandName knot -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $elements = @($commandAst.CommandElements | Select-Object -Skip 1)
    if ($elements.Count -le 1) {
        @($__knotCommands + $__knotOptions) |
            Where-Object { $_ -like "$wordToComplete*" } |
            ForEach-Object {
                [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
            }
        return
    }
    Get-ChildItem -Path "$wordToComplete*" -ErrorAction SilentlyContinue | ForEach-Object {
        [System.Management.Automation.CompletionResult]::new(
            $_.Name, $_.Name, 'ProviderItem', $_.FullName
        )
    }
}
"""


def _commands(parser: argparse.ArgumentParser) -> list[str]:
    names: list[str] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                names.append(name)
                names.extend(getattr(sub, "_aliases", []) or [])
    return sorted(set(names))


def _options(parser: argparse.ArgumentParser) -> list[str]:
    opts = []
    for action in parser._actions:
        opts.extend(action.option_strings)
    return sorted(set(opts))


def generate(shell: str, parser: argparse.ArgumentParser) -> str:
    commands = _commands(parser)
    if shell == "bash":
        return BASH_TEMPLATE.format(commands=" ".join(commands), opts=" ".join(_options(parser)))
    if shell == "zsh":
        return ZSH_TEMPLATE.format(commands=" ".join(f"'{name}'" for name in commands))
    if shell == "fish":
        lines = "\n".join(
            f"complete -c knot -n '__fish_use_subcommand' -a '{name}'" for name in commands
        )
        return FISH_TEMPLATE.format(lines=lines)
    if shell in ("powershell", "pwsh"):
        return POWERSHELL_TEMPLATE.replace(
            "__COMMANDS__", ", ".join(f"'{name}'" for name in commands)
        )
    raise ValueError(f"不支持的 shell：{shell}")
