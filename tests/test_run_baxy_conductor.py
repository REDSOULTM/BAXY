"""scripts/run_baxy_conductor.ps1 quotes the conductor's argv itself (Windows PowerShell 5.1 has no
ProcessStartInfo.ArgumentList): its Quote-ConductorArgument is taken out of the script by the PowerShell parser, nothing
else of the script runs, and the line it makes is read back by a process's own argv parsing (the C runtime's, the
rules Baxy.exe reads its arguments by)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_baxy_conductor.ps1"
EXTRACT = r"""
$values = Get-Content -LiteralPath $args[0] -Raw -Encoding UTF8 | ConvertFrom-Json
$ast = [System.Management.Automation.Language.Parser]::ParseFile($args[1], [ref]$null, [ref]$null)
$function = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -eq 'Quote-ConductorArgument' }, $true)
. ([scriptblock]::Create($function.Extent.Text))
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::Out.Write((@($values) | ForEach-Object { Quote-ConductorArgument $_ }) -join ' ')
"""


def _argv(tmp_path: Path, values: list[str]) -> list[str]:
    (tmp_path / "values.json").write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "extract.ps1").write_text("\ufeff" + EXTRACT, encoding="utf-8")
    line = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(tmp_path / "extract.ps1"),
         str(tmp_path / "values.json"), str(SCRIPT)],
        capture_output=True, text=True, encoding="utf-8", check=True, timeout=60).stdout
    echo = "import json, sys; sys.stdout.buffer.write(json.dumps(sys.argv[1:]).encode())"
    done = subprocess.run(f'"{sys.executable}" -c "{echo}" {line}', capture_output=True, check=True, timeout=60)
    return json.loads(done.stdout)


def test_a_turn_with_a_folder_reaches_the_app_as_it_was_written(tmp_path: Path) -> None:
    # Calidad PC 2026-10-25: every backslash was doubled, and only those before a quote are read as escapes: a turn
    # naming a folder reached the App with «C:\\Users\\...».
    values = [r"--text=abre la carpeta C:\Users\Public\Documents por favor", r"--capture=C:\una carpeta\captura"]
    assert _argv(tmp_path, values) == values


def test_quotes_and_a_trailing_backslash_survive(tmp_path: Path) -> None:
    values = ['--text=di "hola" y sal', "--text=termina en barra \\", '--text=barra antes de comilla \\"', "--plain"]
    assert _argv(tmp_path, values) == values
