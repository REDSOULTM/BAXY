# BAXY Renew: corre los bancos y mide VRAM, RAM y latencia en un solo paso.
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\renew_check.ps1 -Label r5                   # bancos de práctica
#   powershell -ExecutionPolicy Bypass -File scripts\renew_check.ps1 -Label r5 -Only decision,escenas
#   powershell -ExecutionPolicy Bypass -File scripts\renew_check.ps1 -Label final -Holdout       # los sellados, una vez
# Los bancos viven fuera del repo (llevan pedidos reales del dueño): $env:BAXY_RENEW_BANKS, por defecto
# F:\BAXYeval\renew_v1. Con -Holdout se comprueba antes el sha256 de cada sellado contra artifacts\renew\metas.json.
# Cada banco deja <bancos>\runs\<Label>-<banco>… con su resumen en la primera línea; al final se imprime el resumen
# conjunto (y, con -Holdout, el acierto del holdout final: decisión + extremo a extremo + latido).
param(
    [Parameter(Mandatory = $true)][string]$Label,
    [switch]$Holdout,
    [string[]]$Only = @()
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
if (-not $env:BAXY_RENEW_BANKS) { $env:BAXY_RENEW_BANKS = "F:\BAXYeval\renew_v1" }
$banks = $env:BAXY_RENEW_BANKS
$runs = Join-Path $banks "runs"
New-Item -ItemType Directory -Force -Path $runs | Out-Null
$scripts = Join-Path $repo "scripts\renew"

function Want([string]$name) { return $Only.Count -eq 0 -or $Only -contains $name }

if ($Holdout) {
    $metas = Get-Content (Join-Path $repo "artifacts\renew\metas.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($entry in $metas.bancos.sellados.PSObject.Properties) {
        $file = $entry.Value.archivo -replace '/', '\'
        $actual = (Get-FileHash -Algorithm SHA256 $file).Hash.ToLowerInvariant()
        if ($actual -ne $entry.Value.sha256) { throw "sello roto: $($entry.Name) ($file)" }
    }
    Write-Host "sellos intactos"
    $sets = @{
        decision   = Join-Path $banks "holdout\decision.json"
        e2e        = Join-Path $banks "e2e\sealed.json"
        escenas    = Join-Path $banks "escenas\sealed.json"
        latido     = Join-Path $banks "escenas\holdout_latido.json"
        falsedades = Join-Path $banks "falsedades\sealed.json"
    }
} else {
    $sets = @{
        decision   = Join-Path $banks "practica\decision2.json"
        e2e        = Join-Path $banks "e2e\practice.json"
        escenas    = Join-Path $banks "escenas\practice.json"
        falsedades = Join-Path $banks "falsedades\practice.json"
    }
}

function Run([string]$script, [string[]]$arguments) {
    & py -3.12 -X utf8 (Join-Path $scripts $script) @arguments | Select-Object -Last 1
    if ($LASTEXITCODE -ne 0) { throw "$script falló ($LASTEXITCODE)" }
}

# The decision and scene benches start their own llama-server; the product benches start Baxy.exe with its own. They
# run one after the other: the product's resources are measured alone.
if (Want "decision") { Run "bench_decision.py" @("$Label-decision", "--cases", $sets.decision) }
if (Want "escenas") { Run "bench_escenas.py" @("$Label", "--scenes", $sets.escenas) }
if ($Holdout -and (Want "latido")) { Run "bench_escenas.py" @("$Label-latido", "--scenes", $sets.latido) }
if (Want "e2e") { Run "bench_e2e.py" @("$Label", "--cases", $sets.e2e) }
if (Want "falsedades") { Run "bench_falsedades.py" @("$Label", "--cases", $sets.falsedades) }
if (Want "recursos") { Run "measure_resources.py" @("$Label") }

& py -3.12 -X utf8 (Join-Path $scripts "summarize.py") $Label $(if ($Holdout) { "--holdout" })
Write-Host "resúmenes en $runs"
