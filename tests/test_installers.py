from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PS1_FILES = ("安装.ps1", "卸载.ps1")
SH_FILES = ("安装.sh", "卸载.sh")


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8-sig")


class InstallerFileTest(unittest.TestCase):
    def test_files_exist(self) -> None:
        for name in (*PS1_FILES, *SH_FILES):
            self.assertTrue((ROOT / name).exists(), f"缺少安装脚本：{name}")

    def test_install_ps1_contract(self) -> None:
        text = read("安装.ps1")
        self.assertIn("param(", text)
        self.assertIn("InstallDir", text)
        self.assertIn("NoPath", text)
        self.assertIn("SetEnvironmentVariable", text)
        self.assertIn("install.json", text)
        self.assertIn("venv", text)
        self.assertIn("自检", text)
        self.assertIn("knot.cmd", text)

    def test_uninstall_ps1_contract(self) -> None:
        text = read("卸载.ps1")
        self.assertIn("DryRun", text)
        self.assertIn("install.json", text)
        self.assertIn("SetEnvironmentVariable", text)
        self.assertIn("账本", text)

    def test_ps1_files_have_bom_and_crlf(self) -> None:
        for name in PS1_FILES:
            raw = (ROOT / name).read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), f"{name} 需要 UTF-8 BOM")
            self.assertIn(b"\r\n", raw, name)
            self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), f"{name} 必须使用 CRLF")

    def test_install_sh_contract(self) -> None:
        text = read("安装.sh")
        self.assertIn("set -eu", text)
        self.assertIn(".local/share/knot", text)
        self.assertIn(".local/bin", text)
        self.assertIn("install.json", text)
        self.assertIn("knot installer", text)
        self.assertIn("venv", text)

    def test_uninstall_sh_contract(self) -> None:
        text = read("卸载.sh")
        self.assertIn("--dry-run", text)
        self.assertIn("install.json", text)
        self.assertIn("knot installer", text)
        self.assertIn("账本", text)

    def test_sh_files_use_lf(self) -> None:
        for name in SH_FILES:
            raw = (ROOT / name).read_bytes()
            self.assertNotIn(b"\r\n", raw, f"{name} 必须使用 LF")

    def test_gitattributes_declares_ps1_crlf(self) -> None:
        text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.ps1 text eol=crlf", text)


class InstallerSyntaxTest(unittest.TestCase):
    def test_powershell_scripts_parse(self) -> None:
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if not shell:
            self.skipTest("本机没有 PowerShell")
        template = (
            "$tokens = $null; $errors = $null; "
            "[void][System.Management.Automation.Language.Parser]::ParseFile("
            "'{path}', [ref]$tokens, [ref]$errors); "
            "if ($errors.Count -gt 0) {{ $errors | ForEach-Object {{ $_.Message }}; exit 1 }}"
        )
        for name in PS1_FILES:
            result = subprocess.run(
                [
                    shell,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    template.format(path=(ROOT / name).as_posix()),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(
                result.returncode, 0, f"{name} 语法检查失败：{result.stdout}{result.stderr}"
            )

    def test_shell_scripts_parse(self) -> None:
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("本机没有 sh")
        for name in SH_FILES:
            result = subprocess.run(
                [shell, "-n", str(ROOT / name)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(result.returncode, 0, f"{name} 语法检查失败：{result.stderr}")


if __name__ == "__main__":
    unittest.main()
