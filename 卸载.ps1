<#
结绳 Knot 一键卸载（Windows / PowerShell）

只清理安装目录（含独立虚拟环境与命令垫片）和用户 PATH 条目，不依赖 Python，
也不会删除任何账本文件。

用法：
  powershell -ExecutionPolicy Bypass -File .\卸载.ps1
  pwsh -File .\卸载.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\Knot"),
    [switch]$DryRun,
    [switch]$Yes
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$binDir = Join-Path $InstallDir "bin"
$infoPath = Join-Path $InstallDir "install.json"

if (Test-Path -LiteralPath $infoPath) {
    try {
        $info = Get-Content -LiteralPath $infoPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($info.命令目录) { $binDir = $info.命令目录 }
        Write-Host "找到安装记录：$($info.版本)（来源：$($info.来源)）"
    } catch {
        Write-Host "安装记录读取失败，按默认路径清理。"
    }
} else {
    Write-Host "未找到安装记录（install.json），按默认路径清理：$InstallDir"
}

$ledgers = @(Get-ChildItem -LiteralPath $InstallDir -Recurse -Filter *.knot -ErrorAction SilentlyContinue)

Write-Host "将清理："
Write-Host "  命令目录：$binDir"
Write-Host "  安装目录：$InstallDir"
Write-Host "  用户 PATH 中的相关条目"
Write-Host "账本数据通常不在这里；如安装在别处的账本不会被删除。"
if ($ledgers.Count -gt 0) {
    Write-Host "注意：安装目录内发现 $($ledgers.Count) 个 .knot 账本文件，卸载会一并删除："
    $ledgers | Select-Object -First 5 | ForEach-Object { Write-Host "  $($_.FullName)" }
    Write-Host "如需保留，请先移动到其它目录再卸载。"
}
if (-not $Yes) {
    $answer = Read-Host "确认卸载？(y/N)"
    if ($answer -notmatch '^(y|yes|是)$') {
        Write-Host "已取消。"
        exit 0
    }
}

if ($DryRun) {
    Write-Host "（试运行）未做任何修改。"
    exit 0
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -and (@($userPath -split ";") -contains $binDir)) {
    $segments = @($userPath -split ";" | Where-Object { $_ -ne "" -and $_ -ne $binDir })
    [Environment]::SetEnvironmentVariable("Path", ($segments -join ";"), "User")
    Write-Host "已从用户 PATH 移除：$binDir"
} else {
    Write-Host "用户 PATH 中没有该条目，跳过"
}

if (Test-Path -LiteralPath $InstallDir) {
    try {
        Remove-Item -LiteralPath $InstallDir -Recurse -Force
        Write-Host "已删除安装目录：$InstallDir"
    } catch {
        Write-Host "直接删除失败（可能有终端正在使用该解释器），已安排后台清理 ..."
        $cleanup = Join-Path $env:TEMP ("knot-uninstall-" + [guid]::NewGuid().ToString("N") + ".cmd")
        $script = @(
            "@echo off",
            "timeout /t 2 /nobreak >nul",
            "rmdir /s /q `"$InstallDir`"",
            "del `"%~f0`"",
            ""
        ) -join "`r`n"
        [System.IO.File]::WriteAllText($cleanup, $script, (New-Object System.Text.ASCIIEncoding))
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$cleanup`"" -WindowStyle Hidden
        Write-Host "请稍候几秒，目录会在后台被删除。"
    }
} else {
    Write-Host "安装目录不存在，跳过：$InstallDir"
}

Write-Host "卸载完成。账本文件未受影响。"
