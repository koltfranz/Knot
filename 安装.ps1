<#
结绳 Knot 正式安装（Windows / PowerShell）

用法：
  powershell -ExecutionPolicy Bypass -File .\安装.ps1
  pwsh -File .\安装.ps1 -InstallDir "$env:LOCALAPPDATA\Programs\Knot" -Yes
  pwsh -File .\安装.ps1 -From knot-ledger      # 从 PyPI 安装（发布后可用）

参数：
  -InstallDir  安装目录（默认 %LOCALAPPDATA%\Programs\Knot）
  -From        pip 安装目标（默认脚本所在目录；可传包名、wheel 或源码路径）
  -NoPath      不修改用户 PATH（CI 或自定义环境用）
  -Yes         不提问，直接安装

安装后：新开终端即可使用全局命令 knot（knot --version / knot create / knot open）。
卸载：powershell -ExecutionPolicy Bypass -File .\卸载.ps1（不会删除账本文件）。
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\Knot"),
    [string]$From = "",
    [switch]$NoPath,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"

if (-not $From) { $From = $PSScriptRoot }
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$venvDir = Join-Path $InstallDir "venv"
$binDir = Join-Path $InstallDir "bin"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$entry = Join-Path $venvDir "Scripts\knot.exe"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$utf8Bom = New-Object System.Text.UTF8Encoding($true)

Write-Host "结绳 Knot 安装程序"
Write-Host "  安装目录：$InstallDir"
Write-Host "  安装来源：$From"
if (-not $Yes) {
    $answer = Read-Host "继续安装？(y/N)"
    if ($answer -notmatch '^(y|yes|是)$') {
        Write-Host "已取消。"
        exit 0
    }
}

$pyExe = $null
$pyArgs = @()
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyExe = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pyExe = "py"
    $pyArgs = @("-3")
}
if (-not $pyExe) {
    Write-Host "错误：未找到 Python，请先安装 3.11 或更高版本：https://www.python.org/downloads/"
    exit 2
}
$version = & $pyExe @pyArgs -c "import sys; print('%d.%d' % sys.version_info[:2])"
if (-not $version -or [version]$version -lt [version]"3.11") {
    Write-Host "错误：Python 版本过低（$version），需要 3.11 或更高。"
    exit 2
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
if (Test-Path -LiteralPath $venvPython) {
    Write-Host "复用已存在的虚拟环境（重复执行安装即升级）"
} else {
    Write-Host "创建虚拟环境：$venvDir"
    & $pyExe @pyArgs -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "错误：创建虚拟环境失败。"
        exit 2
    }
}

Write-Host "安装 knot-ledger ..."
& $venvPython -m pip install --quiet --upgrade pip
& $venvPython -m pip install --quiet --upgrade $From
if ($LASTEXITCODE -ne 0) {
    Write-Host "错误：安装失败，请检查网络或安装来源。"
    exit 2
}

New-Item -ItemType Directory -Force -Path $binDir | Out-Null
if (Test-Path -LiteralPath $entry) {
    $call = "`"$entry`""
} else {
    $call = "`"$venvPython`" -m knot"
}
$cmdShim = @(
    "@echo off",
    "rem 由 安装.ps1 生成：结绳 Knot 全局命令（cmd）",
    "$call %*",
    ""
) -join "`r`n"
$psShim = @(
    "# 由 安装.ps1 生成：结绳 Knot 全局命令（PowerShell）",
    "& $call @args",
    "exit `$LASTEXITCODE",
    ""
) -join "`r`n"
[System.IO.File]::WriteAllText((Join-Path $binDir "knot.cmd"), $cmdShim, $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $binDir "knot.ps1"), $psShim, $utf8Bom)

# 入口：桌面 + 开始菜单快捷方式（双击弹出选择窗口）
$windowless = Join-Path $venvDir "Scripts\pythonw.exe"
$entryTarget = if (Test-Path -LiteralPath $windowless) { $windowless } else { $venvPython }
$entryPaths = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "结绳 Knot.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "结绳 Knot.lnk")
)
$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in $entryPaths) {
    try {
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $entryTarget
        $shortcut.Arguments = "-m knot 入口"
        $shortcut.WorkingDirectory = $env:USERPROFILE
        $shortcut.Description = "结绳 Knot：纯文本复式记账（选择浏览器界面或终端界面）"
        $shortcut.Save()
        Write-Host "已创建入口：$shortcutPath"
    } catch {
        Write-Host "警告：创建入口失败（$shortcutPath）：$($_.Exception.Message)"
    }
}

if ($NoPath) {
    Write-Host "按 -NoPath 跳过 PATH 修改；可直接调用 $binDir\knot.cmd"
} else {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not $userPath) { $userPath = "" }
    $segments = @($userPath -split ";" | Where-Object { $_ -ne "" })
    if ($segments -contains $binDir) {
        Write-Host "用户 PATH 已包含：$binDir"
    } else {
        $trimmed = $userPath.TrimEnd(";")
        $newPath = if ($trimmed) { "$trimmed;$binDir" } else { $binDir }
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Host "已把 $binDir 加入用户 PATH（新开终端生效）"
    }
}

$versionText = ((& $venvPython -m knot --version) -join "").Trim()
$info = [ordered]@{
    版本     = $versionText
    来源     = $From
    安装目录 = $InstallDir
    命令目录 = $binDir
    解释器   = $venvPython
    入口     = $entryPaths
    安装时间 = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
}
[System.IO.File]::WriteAllText(
    (Join-Path $InstallDir "install.json"),
    ($info | ConvertTo-Json),
    $utf8NoBom
)

Write-Host "运行自检 ..."
& $venvPython -m knot 自检
if ($LASTEXITCODE -ne 0) {
    Write-Host "警告：自检未全部通过，请按上方提示处理。"
}

Write-Host ""
Write-Host "安装完成：$versionText"
Write-Host "  双击桌面或开始菜单的「结绳 Knot」入口即可使用（弹选择窗口）"
Write-Host "  新开终端后也可直接用命令："
Write-Host "    knot --version"
Write-Host "    knot create 我的账本      # 新建账本（默认内容可直接改）"
Write-Host "    knot open 我的账本        # 打开终端界面（鼠标可点选 / Ctrl+单击多选）"
Write-Host "    knot 示例                 # 复制示例账本（演示全部功能与 7 种图表）"
Write-Host "    knot --补全 powershell    # 输出 PowerShell 补全脚本"
Write-Host "  在 Python 中使用：& '$venvPython' -c `"import knot; print(knot.__version__)`""
Write-Host "  卸载：powershell -ExecutionPolicy Bypass -File `"$PSScriptRoot\卸载.ps1`""
Write-Host "  卸载只清理安装目录与 PATH，不会删除账本文件。"
