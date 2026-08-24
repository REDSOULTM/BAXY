# Lanza Baxy.exe directo y observa si baxy-core.exe se queda vivo.
param(
    [int]$Seconds = 20,
    [string]$Tag = "probe",
    [string]$Scratch = (Join-Path $env:TEMP "baxy-goal10")
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$scratch = $Scratch
if (-not (Test-Path $scratch)) { New-Item -ItemType Directory -Path $scratch -Force | Out-Null }
$app = Join-Path $repo "src\Baxy.App\bin\Release\net10.0-windows10.0.19041.0\Baxy.exe"
$presence = Join-Path $env:LOCALAPPDATA "BAXY\presence"

# 0. Nada vivo de antes.
Get-Process -Name "Baxy", "baxy-core" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

# 1. Borrar rastros previos para que lo que salga sea de esta corrida.
foreach ($f in @("last-core-exit.txt", "last-crash.txt")) {
    $p = Join-Path $presence $f
    if (Test-Path $p) { Remove-Item $p -Force }
}
$trace = Join-Path $scratch ("trace-{0}.jsonl" -f $Tag)
if (Test-Path $trace) { Remove-Item $trace -Force }

# 2. Entorno igual que run_baxy.ps1 (mente activada).
$env:BAXY_DATA_DIR = Join-Path $env:LOCALAPPDATA "BAXY\dev-mente-v2"
$env:BAXY_APP_TRACE = $trace
$env:BAXY_ASSET_DESCRIPTOR = Join-Path $repo "assets.manifest.json"
Remove-Item Env:BAXY_MIND_DISABLED -ErrorAction SilentlyContinue

$proc = Start-Process -FilePath $app -WorkingDirectory (Split-Path $app) -PassThru
("app pid={0}" -f $proc.Id)

# 3. Muestreo cada 200 ms: quien esta vivo.
$log = New-Object System.Collections.Generic.List[string]
$deadline = (Get-Date).AddSeconds($Seconds)
$coreEverSeen = $false
$sw = [System.Diagnostics.Stopwatch]::StartNew()
while ((Get-Date) -lt $deadline) {
    $names = @()
    foreach ($p in (Get-CimInstance Win32_Process -Filter "Name='baxy-core.exe' OR Name='Baxy.exe' OR Name='python.exe' OR Name='llama-server.exe'" -ErrorAction SilentlyContinue)) {
        $names += ("{0}#{1}(ppid={2})" -f $p.Name, $p.ProcessId, $p.ParentProcessId)
        if ($p.Name -eq "baxy-core.exe") { $coreEverSeen = $true }
    }
    $log.Add(("{0,7:F0}ms {1}" -f $sw.Elapsed.TotalMilliseconds, ($names -join " ")))
    Start-Sleep -Milliseconds 200
}

$log | Set-Content -Path (Join-Path $scratch ("procs-{0}.txt" -f $Tag)) -Encoding utf8
("core visto alguna vez: {0}" -f $coreEverSeen)
("app sigue viva: {0}" -f (-not $proc.HasExited))

foreach ($f in @("last-core-exit.txt", "last-crash.txt")) {
    $p = Join-Path $presence $f
    if (Test-Path $p) {
        ("--- {0} ---" -f $f)
        Get-Content $p
    } else {
        ("--- {0}: no existe ---" -f $f)
    }
}

("--- trace ({0}) ---" -f $trace)
if (Test-Path $trace) { Get-Content $trace -TotalCount 60 } else { "sin trace" }
