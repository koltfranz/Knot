# 结绳 Knot 一键启动器（PowerShell）：准备环境后运行 CLI。
# 无参数 -> 交互菜单（双击友好）；其余参数原样转给 knot。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
Set-Location -LiteralPath $PSScriptRoot

$pyExe = $null
$pyArgs = @()
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyExe = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pyExe = "py"
    $pyArgs = @("-3")
}
if (-not $pyExe) {
    Write-Host "[Knot] 未找到 Python 3.11+，请先安装：https://www.python.org/downloads/"
    exit 2
}

$version = & $pyExe @pyArgs -c "import sys; print('%d.%d' % sys.version_info[:2])"
if (-not $version -or [version]$version -lt [version]"3.11") {
    Write-Host "[Knot] Python 版本过低（当前 $version），需要 3.11 或更高。"
    exit 2
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "[Knot] 首次运行：创建虚拟环境并安装（需要联网一次）..."
    & $pyExe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[Knot] 创建虚拟环境失败。"
        exit 2
    }
    & $venvPython -m pip install --quiet --upgrade pip
    & $venvPython -m pip install --quiet -e .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[Knot] 安装失败，请检查网络或 Python 版本。"
        exit 2
    }
}

if ($args.Count -eq 0) {
    & $venvPython -m knot menu
    $code = $LASTEXITCODE
    Write-Host ""
    if (-not [Console]::IsInputRedirected) {
        Read-Host "按回车关闭窗口"
    }
    exit $code
}

& $venvPython -m knot @args
exit $LASTEXITCODE
