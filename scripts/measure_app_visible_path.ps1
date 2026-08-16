# Versioned, reproducible harness for BAXY's visible response path.
#
# What it is for: measuring what a person actually waits for, from the keystroke
# that submits a question to the moment the answer is painted, with every stage
# in between attributed separately. The earlier measurements of this path were
# driven from ad-hoc scratch scripts, so they could not be repeated or audited.
# This script is the versioned replacement.
#
# What it guarantees:
#   * Stable scenario identifiers and a SHA-256 over the frozen scenario set, so
#     two runs are comparable only when they asked the same questions.
#   * A cold arm (a freshly launched app, an unwarmed model) and a warm arm (the
#     same instance, already warmed), alternated in ABBA order across rounds so
#     drift and thermal state cannot favour one arm.
#   * The hardware and runtime state at measurement time: GPU clocks, thermal
#     slowdown, temperature, plus the SHA-256 of every asset that decides speed.
#   * Raw per-sample traces kept next to the summary; nothing is averaged away.
#
# What it never does: it only asks conversational and read-only questions. No
# scenario opens an application, sends a message, changes a device or writes
# anything outside the trace directory.
#
#   powershell -File scripts/measure_app_visible_path.ps1 -Rounds 2

[CmdletBinding()]
param(
    [int]$Rounds = 2,
    [string]$OutputDirectory = '',
    [int]$WarmupSeconds = 90,
    [int]$PerScenarioSeconds = 30
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# $PSScriptRoot is not bound while parameter defaults are evaluated, so the
# repository and the output directory are resolved here instead.
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $scriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $repo 'artifacts\fixes\app_visible_path_v3'
}
$harnessVersion = 'baxy.app-visible-path-harness.v3'

# Frozen scenario set. The identifiers are stable across runs; changing any text
# changes the fixture hash and therefore marks the results as a different
# experiment rather than a continuation of the old one.
$scenarios = @(
    [pscustomobject]@{ Id = 'conv-greeting';   Route = 'conversation'; Text = 'hola, todo bien' }
    [pscustomobject]@{ Id = 'conv-explain';    Route = 'conversation'; Text = 'explicame en dos oraciones que hace un ssd' }
    [pscustomobject]@{ Id = 'status-time';     Route = 'status';       Text = 'que hora es' }
    [pscustomobject]@{ Id = 'status-battery';  Route = 'status';       Text = 'cuanta bateria queda' }
    [pscustomobject]@{ Id = 'status-memory';   Route = 'status';       Text = 'cuanta ram tengo' }
)

function Get-Sha256Text([string]$text) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($text)
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-', '').ToLowerInvariant()
    }
    finally { $sha.Dispose() }
}

function Get-Sha256File([string]$path) {
    if (-not (Test-Path $path)) { return $null }
    return (Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()
}

# The canonical scenario text is what the hash covers: identifier, route and the
# exact question, in declaration order.
$canonicalScenarios = ($scenarios | ForEach-Object { "$($_.Id)`t$($_.Route)`t$($_.Text)" }) -join "`n"
$fixtureSha256 = Get-Sha256Text $canonicalScenarios

# The root is chosen by what it actually contains, not by what the machine
# exports: this machine exports DOTNET_ROOT and DOTNET_ROOT_X64 pointing at a
# system-wide install whose newest desktop runtime is 9.0, which cannot run the
# app. Preferring the ambient value silently launches the apphost's error dialog.
function Select-DesktopRuntimeRoot {
    param([string[]]$Candidates)
    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        $desktop = Join-Path $candidate 'shared\Microsoft.WindowsDesktop.App'
        if (-not (Test-Path $desktop)) { continue }
        $hasTen = Get-ChildItem $desktop -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like '10.*' }
        if ($hasTen) { return $candidate }
    }
    return $null
}

$script:DotnetRoot = Select-DesktopRuntimeRoot @(
    $env:BAXY_DOTNET_ROOT,
    'D:\BAXYRuntime\tools\dotnet-10.0.100',
    $env:DOTNET_ROOT_X64,
    $env:DOTNET_ROOT)

$app = Join-Path $repo 'src\Baxy.App\bin\Release\net10.0-windows10.0.19041.0\Baxy.exe'
if (-not (Test-Path $app)) {
    throw "No existe la app compilada en $app. Compila Release antes de medir."
}
if ($null -eq $script:DotnetRoot) {
    throw 'No se encontró ninguna raíz .NET con un runtime de escritorio 10.x; la app no puede arrancar.'
}
Write-Output "dotnet root: $script:DotnetRoot"
$appDirectory = Split-Path $app
$core = Join-Path $repo 'src\Baxy.Core\bin\Release\net10.0-windows10.0.19041.0\win-x64\publish\baxy-core.exe'
$coreBesideApp = Join-Path $appDirectory 'baxy-core.exe'
if ((Test-Path $core) -and (Test-Path $coreBesideApp) -and
    ((Get-Item $core).LastWriteTimeUtc -gt (Get-Item $coreBesideApp).LastWriteTimeUtc)) {
    Copy-Item $core $coreBesideApp -Force
}

if (-not (Test-Path $OutputDirectory)) {
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
}
$OutputDirectory = (Resolve-Path $OutputDirectory).Path

function Get-EnvironmentState {
    $gpu = $null
    try {
        $query = 'name,clocks.current.sm,clocks.max.sm,temperature.gpu,power.draw,clocks_throttle_reasons.active,memory.used,memory.total'
        $raw = & nvidia-smi --query-gpu=$query --format=csv,noheader 2>$null
        if ($LASTEXITCODE -eq 0 -and $raw) { $gpu = ($raw | Select-Object -First 1).Trim() }
    }
    catch { $gpu = $null }

    $manifestPath = Join-Path $env:LOCALAPPDATA 'BAXYRuntime\mind-runtime-v1.json'
    $runtime = $null
    if (Test-Path $manifestPath) {
        $manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json
        $runtime = [pscustomobject]@{
            llama_server        = [string]$manifest.llama_server
            llama_server_sha256 = Get-Sha256File ([string]$manifest.llama_server)
            gguf                = [string]$manifest.gguf
            gguf_sha256         = if ($manifest.PSObject.Properties.Name -contains 'gguf_sha256') { [string]$manifest.gguf_sha256 } else { $null }
            ngl                 = [string]$manifest.ngl
        }
    }

    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    # A machine measured on battery throttles differently, so the arm is only
    # comparable when this is recorded. A machine with no battery reports none.
    $battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
    $onAcPower = if ($null -eq $battery) { $true } else { $battery.BatteryStatus -ne 1 }
    return [pscustomobject]@{
        captured_at_utc = (Get-Date).ToUniversalTime().ToString('o')
        gpu             = $gpu
        gpu_query       = 'name,clocks.current.sm,clocks.max.sm,temperature.gpu,power.draw,clocks_throttle_reasons.active,memory.used,memory.total'
        cpu             = $cpu.Name
        cpu_max_mhz     = $cpu.MaxClockSpeed
        on_ac_power     = $onAcPower
        app_sha256      = Get-Sha256File $app
        core_sha256     = Get-Sha256File $coreBesideApp
        runtime         = $runtime
    }
}

function Stop-BaxyTree([int]$processId) {
    try { Stop-Process -Id $processId -Force -ErrorAction Stop } catch {}
    Start-Sleep -Seconds 3
    Get-Process -Name 'baxy-core', 'llama-server' -ErrorAction SilentlyContinue |
        ForEach-Object {
            Write-Output ("residual: {0} {1}" -f $_.Name, $_.Id)
            try { Stop-Process -Id $_.Id -Force -ErrorAction Stop } catch {}
        }
    Start-Sleep -Seconds 2
}

function Start-Baxy([string]$tracePath) {
    if (Test-Path $tracePath) { Remove-Item $tracePath -Force }
    $devRoot = Join-Path $env:LOCALAPPDATA 'BAXY\dev-mente-v2'
    if (-not (Test-Path $devRoot)) { New-Item -ItemType Directory -Path $devRoot -Force | Out-Null }

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $app
    $psi.WorkingDirectory = $appDirectory
    # ShellExecute would not carry these, so the process is started directly.
    $psi.UseShellExecute = $false
    $psi.EnvironmentVariables['BAXY_APP_TRACE'] = $tracePath
    $psi.EnvironmentVariables['BAXY_DATA_DIR'] = $devRoot
    $psi.EnvironmentVariables['BAXY_ASSET_DESCRIPTOR'] = (Join-Path $repo 'assets.manifest.json')
    # The development build is framework-dependent and this machine's shared
    # runtimes stop at 9.0, so without these the apphost only shows its own
    # error dialog and the harness would measure a window that is not BAXY.
    # DOTNET_ROOT_X64 must be set as well, and is what actually decides here:
    # the architecture-specific form outranks DOTNET_ROOT, and this machine
    # already exports it pointing at the system-wide install.
    $psi.EnvironmentVariables['DOTNET_ROOT'] = $script:DotnetRoot
    $psi.EnvironmentVariables['DOTNET_ROOT_X64'] = $script:DotnetRoot
    $psi.EnvironmentVariables['DOTNET_ROOT(x64)'] = $script:DotnetRoot
    if ($psi.EnvironmentVariables.ContainsKey('BAXY_MIND_DISABLED')) {
        [void]$psi.EnvironmentVariables.Remove('BAXY_MIND_DISABLED')
    }
    $started = [System.Diagnostics.Process]::Start($psi)
    # The trace file is opened by BAXY itself as it boots, so its appearance is
    # the proof that what started is BAXY and not the apphost's error dialog.
    $deadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $deadline -and -not (Test-Path $tracePath)) {
        if ($started.HasExited) {
            throw "BAXY terminó durante el arranque con código $($started.ExitCode)."
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-Path $tracePath)) {
        try { $started.Kill() } catch {}
        throw "BAXY no abrió su traza en $tracePath; lo que arrancó no es la app instrumentada."
    }
    return $started
}

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
if (-not ('BaxyHarnessWin' -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class BaxyHarnessWin {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
}
'@
}

function Get-BaxyInputField([System.Diagnostics.Process]$process) {
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        $process.Refresh()
        if ($process.MainWindowHandle -ne [IntPtr]::Zero) {
            [void][BaxyHarnessWin]::ShowWindow($process.MainWindowHandle, 9)
            [void][BaxyHarnessWin]::SetForegroundWindow($process.MainWindowHandle)
            $root = [System.Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
            $condition = New-Object System.Windows.Automation.PropertyCondition(
                [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
                [System.Windows.Automation.ControlType]::Edit)
            $edits = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
            for ($i = 0; $i -lt $edits.Count; $i++) {
                $candidate = $edits.Item($i)
                if ($candidate.Current.IsEnabled -and -not $candidate.Current.IsOffscreen) {
                    return $candidate
                }
            }
        }
        Start-Sleep -Milliseconds 800
    }
    throw 'La ventana de BAXY no expuso un campo de entrada utilizable.'
}

function Send-Scenario($field, [string]$text) {
    $field.SetFocus()
    Start-Sleep -Milliseconds 400
    $pattern = $field.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    $pattern.SetValue($text)
    Start-Sleep -Milliseconds 300
    [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
}

$runId = [Guid]::NewGuid().ToString('N')
$before = Get-EnvironmentState
$arms = @()

for ($round = 0; $round -lt $Rounds; $round++) {
    # ABBA: cold, warm, warm, cold, mirrored on odd rounds. A cold arm is a new
    # process; a warm arm reuses the process the previous block already warmed.
    $order = if ($round % 2 -eq 0) { @('cold', 'warm', 'warm', 'cold') } else { @('warm', 'cold', 'cold', 'warm') }
    $process = $null
    $field = $null
    try {
        for ($block = 0; $block -lt $order.Count; $block++) {
            $arm = $order[$block]
            $blockId = "r${round}b${block}"
            $tracePath = Join-Path $OutputDirectory "trace-$runId-$blockId-$arm.jsonl"

            # A warm arm that has to start its own process must warm it first,
            # otherwise it would silently be a cold measurement. That warmup is a
            # real turn and the trace records it, so its count is declared here:
            # attribution is by position, and a warmup turn the summary did not
            # know about would shift every scenario in the block by one.
            $warmupTurns = 0
            if ($arm -eq 'cold' -or $null -eq $process) {
                if ($null -ne $process) { Stop-BaxyTree $process.Id; $process = $null }
                $process = Start-Baxy $tracePath
                $field = Get-BaxyInputField $process
                if ($arm -eq 'warm') {
                    Send-Scenario $field 'hola'
                    $warmupTurns = 1
                    Start-Sleep -Seconds $WarmupSeconds
                }
            }
            else {
                # Warm reuse: point the running app at a new trace file by
                # restarting only when the trace must be separated. The app
                # writes one trace per process, so a warm block keeps writing to
                # the cold block's file and is separated by turn identifiers.
                $tracePath = $arms[-1].trace_path
            }

            $armStart = (Get-Date).ToUniversalTime().ToString('o')
            $sent = @()
            foreach ($scenario in $scenarios) {
                Send-Scenario $field $scenario.Text
                $sent += [pscustomobject]@{
                    scenario_id = $scenario.Id
                    route       = $scenario.Route
                    sent_at_utc = (Get-Date).ToUniversalTime().ToString('o')
                }
                Start-Sleep -Seconds $PerScenarioSeconds
            }

            $arms += [pscustomobject]@{
                block_id     = $blockId
                round        = $round
                arm          = $arm
                trace_path   = $tracePath
                warmup_turns = $warmupTurns
                started_utc  = $armStart
                ended_utc    = (Get-Date).ToUniversalTime().ToString('o')
                scenarios    = $sent
            }
            Write-Output "block $blockId arm=$arm done"
        }
    }
    finally {
        if ($null -ne $process) { Stop-BaxyTree $process.Id }
    }
}

$after = Get-EnvironmentState
$index = [pscustomobject]@{
    schema             = $harnessVersion
    run_id             = $runId
    measured_at_utc    = (Get-Date).ToUniversalTime().ToString('o')
    effects_executed   = 0
    rounds             = $Rounds
    scenario_fixture   = [pscustomobject]@{
        sha256    = $fixtureSha256
        canonical = $canonicalScenarios
        scenarios = $scenarios
    }
    design             = 'cold and warm arms alternated in ABBA order (cold,warm,warm,cold and the mirrored order); one process per cold block; identical scenario set and order in every block'
    environment_before = $before
    environment_after  = $after
    blocks             = $arms
}
$indexPath = Join-Path $OutputDirectory "index-$runId.json"
$index | ConvertTo-Json -Depth 12 | Out-File -FilePath $indexPath -Encoding utf8
Write-Output "INDEX=$indexPath"
Write-Output 'HARNESS-DONE'
