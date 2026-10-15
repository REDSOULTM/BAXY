# BAXY Renew: corre los bancos y mide VRAM, RAM y latencia en un solo paso.
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\renew_check.ps1 -Label r2            # bancos de práctica
#   powershell -ExecutionPolicy Bypass -File scripts\renew_check.ps1 -Label final -Holdout # los sellados, una vez, al final
# Los bancos viven fuera del repo (llevan pedidos reales del dueño): $env:BAXY_RENEW_BANKS, por defecto F:\BAXYeval\renew_v1.
# Cada banco escribe <bancos>\runs\<Label>-<banco>.jsonl con su resumen en la primera línea.
param(
    [Parameter(Mandatory = $true)][string]$Label,
    [switch]$Holdout,
    [string[]]$Only = @()
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
if (-not $env:BAXY_RENEW_BANKS) { $env:BAXY_RENEW_BANKS = "F:\BAXYeval\renew_v1" }
$banks = $env:BAXY_RENEW_BANKS
$py = "py"
$runs = Join-Path $banks "runs"
New-Item -ItemType Directory -Force -Path $runs | Out-Null

$decisionCases = if ($Holdout) { Join-Path $banks "holdout\decision.json" } else { "F:\BAXYeval\renew_bench\cases.json" }

function Want([string]$name) { return $Only.Count -eq 0 -or $Only -contains $name }

if (Want "decision") {
    & $py -3.12 -X utf8 (Join-Path $repo "scripts\renew\bench_decision.py") "$Label-decision" --cases $decisionCases |
        Select-Object -Last 1
    if ($LASTEXITCODE -ne 0) { throw "bench_decision falló ($LASTEXITCODE)" }
}

Write-Host "resúmenes en $runs"
