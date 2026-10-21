# BAXY Renew: the Field view's acceptance tests (design v4, «Baxy pruebas.html» ported to Playwright) against the real
# app. It starts BAXY through the usual launcher (scripts\run_renew.cmd closes this worktree's window, compiles if needed
# and launches) with WebView2's remote debugging port, waits for the view and runs src\Baxy.FieldUi\e2e.
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\test_field_ui.ps1            # lanza BAXY y prueba
#   powershell -ExecutionPolicy Bypass -File scripts\test_field_ui.ps1 -NoLaunch  # BAXY ya corre con el puerto
param(
    [int]$Port = 9333,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$field = Join-Path $repo "src\Baxy.FieldUi"
$endpoint = "http://127.0.0.1:$Port"

if (-not $NoLaunch) {
    # The port reaches the WebView2 runtime through the environment the app inherits.
    $env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = "--remote-debugging-port=$Port"
    & cmd.exe /c (Join-Path $repo "scripts\run_renew.cmd")
    if ($LASTEXITCODE -ne 0) { throw "BAXY no arrancó (run_renew.cmd salió con $LASTEXITCODE)." }
}

$deadline = (Get-Date).AddMinutes(2)
do {
    try {
        $pages = Invoke-RestMethod -Uri "$endpoint/json/list" -TimeoutSec 3
        if ($pages | Where-Object { $_.url -like "https://baxy.local/*" }) { break }
    } catch { }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)
if ((Get-Date) -ge $deadline) { throw "La vista de BAXY no apareció en $endpoint." }

$env:BAXY_CDP_URL = $endpoint
# What the speakers really play, for e2e/lipsync.spec.ts (WASAPI loopback; built here, nothing is downloaded).
$loopcap = Join-Path $repo "scripts\tools\loopcap"
& dotnet build (Join-Path $loopcap "loopcap.csproj") -c Release -v q --nologo | Out-Null
$loopcapExe = Join-Path $loopcap "bin\Release\net10.0-windows\loopcap.exe"
if (Test-Path $loopcapExe) { $env:BAXY_LOOPCAP = $loopcapExe } else { Write-Warning "loopcap no compiló: lipsync.spec.ts se salta." }
Push-Location $field
try {
    & (Join-Path $field "node_modules\.bin\playwright.cmd") test
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
