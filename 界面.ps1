# 一键进入终端界面（TUI）：转发给 knot.ps1，只使用 ASCII 命令名。
& "$PSScriptRoot\knot.ps1" tui
exit $LASTEXITCODE
