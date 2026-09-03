# Conductor sin ventana: misma admisión/turno/publicación que la UI.
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\run_baxy_conductor.ps1 `
#     -Text "Hola, ¿qué puedes hacer?" `
#     -Capture artifacts\comprobaciones\C01\launch-1
#   powershell -ExecutionPolicy Bypass -File scripts\run_baxy_conductor.ps1 `
#     -TurnsFile artifacts\comprobaciones\C01\r01-r06.turns.jsonl `
#     -Capture artifacts\comprobaciones\C01\r01-r06
#
# El perfil de datos se configura al arrancar y persiste entre turnos.
# No hay flag de modo agente: misma política, composición y verificación.

param(
    [switch]$Cpu,
    [string]$Profile,
    [string]$Capture,
    [string]$TurnsFile,
    [string]$Text,
    [int]$TimeoutMs = 120000
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'build_layout.ps1')
$layout = Get-BaxyBuildLayout -RepositoryRoot $repo

$app = $layout.AppExecutable
$core = $layout.CorePublishExecutable
if (-not (Test-Path $app)) {
    throw "Falta Baxy.exe. Compila con: dotnet build src\Baxy.App -c $($layout.DevelopmentConfiguration)"
}
if (-not (Test-Path $core)) {
    throw "Falta baxy-core.exe. Publica con: dotnet publish src\Baxy.Core -c $($layout.DevelopmentConfiguration) -r $($layout.RuntimeIdentifier)"
}

if ([string]::IsNullOrWhiteSpace($Profile)) {
    $Profile = Join-Path $env:LOCALAPPDATA "BAXY\comprobaciones-c01"
}
if (-not (Test-Path $Profile)) {
    New-Item -ItemType Directory -Path $Profile -Force | Out-Null
}
$env:BAXY_DATA_DIR = $Profile
Write-Host "perfil persistente: $Profile"

$coreTarget = Join-Path (Split-Path $app) "baxy-core.exe"
if (-not (Test-Path $coreTarget) -or
    (Get-Item $core).LastWriteTimeUtc -gt (Get-Item $coreTarget).LastWriteTimeUtc) {
    Copy-Item $core $coreTarget -Force
    Write-Host "core actualizado junto a la app"
}

$runtimeManifest = Join-Path $env:LOCALAPPDATA 'BAXYRuntime\mind-runtime-v1.json'
Remove-Item Env:BAXY_MIND_DISABLED -ErrorAction SilentlyContinue
$env:BAXY_ASSET_DESCRIPTOR = Join-Path $repo 'assets.manifest.json'
$env:BAXY_VOICE_WAKE_ON_START = "0"
if ($Cpu) {
    $env:BAXY_MIND_NGL = "0"
}
$env:BAXY_CONDUCTOR_COMMIT = (git -C $repo rev-parse HEAD)
Write-Host "Runtime registrado: $runtimeManifest"
Write-Host "commit: $($env:BAXY_CONDUCTOR_COMMIT)"

$argumentList = [System.Collections.Generic.List[string]]::new()
$argumentList.Add("--conductor")
$argumentList.Add("--profile=$Profile")
$argumentList.Add("--timeout-ms=$TimeoutMs")
$argumentList.Add("--commit=$($env:BAXY_CONDUCTOR_COMMIT)")
if (-not [string]::IsNullOrWhiteSpace($Capture)) {
    if (-not (Test-Path $Capture)) {
        New-Item -ItemType Directory -Path $Capture -Force | Out-Null
    }
    $argumentList.Add("--capture=$((Resolve-Path $Capture).Path)")
}
if (-not [string]::IsNullOrWhiteSpace($TurnsFile)) {
    $argumentList.Add("--turns-file=$((Resolve-Path $TurnsFile).Path)")
}
if (-not [string]::IsNullOrWhiteSpace($Text)) {
    $argumentList.Add("--text=$Text")
}

$workDir = Split-Path $app
Write-Host "conductor: $app $($argumentList -join ' ')"
# WinExe returns immediately under `&`; the documented command must wait
# for admission, public events and the honest terminal. Quote argv here
# because Windows PowerShell 5.1 has no ProcessStartInfo.ArgumentList.
function Quote-ConductorArgument([string]$value) {
    if ($value -notmatch '[\s"]') {
        return $value
    }
    return '"' + ($value -replace '\\','\\' -replace '"','\"') + '"'
}
$argumentLine = ($argumentList | ForEach-Object { Quote-ConductorArgument $_ }) -join ' '
$process = New-Object System.Diagnostics.Process
$process.StartInfo.FileName = $app
$process.StartInfo.WorkingDirectory = $workDir
$process.StartInfo.Arguments = $argumentLine
$process.StartInfo.UseShellExecute = $false
if (-not $process.Start()) {
    throw "conductor_process_missing"
}
$process.WaitForExit()
exit $process.ExitCode
