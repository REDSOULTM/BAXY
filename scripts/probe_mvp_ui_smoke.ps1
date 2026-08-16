# Safe end-to-end smoke for the source MVP launcher and visible desktop path.
# It starts .\run_mvp.ps1 -NoWake, submits one read-only time query through the
# real WebView2 UI, waits for the typed Core route and painted final response,
# then closes the window normally and proves the process tree was reaped.

[CmdletBinding()]
param(
    [string]$OutputDirectory = '',
    [int]$StartupTimeoutSeconds = 180,
    [int]$TurnTimeoutSeconds = 60,
    [int]$ShutdownTimeoutSeconds = 30
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $scriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $repo 'artifacts\mvp\ui_smoke_v1'
}
$output = [IO.Path]::GetFullPath($OutputDirectory)
$reportPath = Join-Path $output 'report.json'
$tracePath = Join-Path $output 'shell-trace.jsonl'
if ((Test-Path -LiteralPath $reportPath) -or (Test-Path -LiteralPath $tracePath)) {
    throw "Me niego a mezclar o sobrescribir evidencia existente en: $output"
}
New-Item -ItemType Directory -Path $output -Force | Out-Null

function Get-Sha256([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Read-Trace {
    if (-not (Test-Path -LiteralPath $tracePath -PathType Leaf)) { return @() }
    $rows = [Collections.Generic.List[object]]::new()
    foreach ($line in Get-Content -LiteralPath $tracePath -ErrorAction SilentlyContinue) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try { $rows.Add(($line | ConvertFrom-Json)) } catch {}
    }
    return @($rows)
}

function Wait-Until {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Condition,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds,
        [string]$Failure = 'Se agotó el tiempo de espera.'
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $value = & $Condition
        if ($null -ne $value -and $value -ne $false) { return $value }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    throw $Failure
}

function Get-RepoAppProcess([datetime]$NotBefore) {
    $prefix = $repo.TrimEnd('\') + '\'
    foreach ($candidate in Get-Process -Name 'Baxy' -ErrorAction SilentlyContinue) {
        try {
            $path = [IO.Path]::GetFullPath($candidate.Path)
            if ($candidate.StartTime -ge $NotBefore -and
                $path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
                return $candidate
            }
        } catch {}
    }
    return $null
}

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
if (-not ('BaxyMvpSmokeWin' -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class BaxyMvpSmokeWin {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
}
'@
}

function Get-InputField([Diagnostics.Process]$Process) {
    $Process.Refresh()
    if ($Process.MainWindowHandle -eq [IntPtr]::Zero) { return $null }
    [void][BaxyMvpSmokeWin]::ShowWindow($Process.MainWindowHandle, 9)
    [void][BaxyMvpSmokeWin]::SetForegroundWindow($Process.MainWindowHandle)
    $root = [Windows.Automation.AutomationElement]::FromHandle(
        $Process.MainWindowHandle)
    if ($null -eq $root) { return $null }
    $condition = New-Object Windows.Automation.PropertyCondition(
        [Windows.Automation.AutomationElement]::ControlTypeProperty,
        [Windows.Automation.ControlType]::Edit)
    $edits = $root.FindAll(
        [Windows.Automation.TreeScope]::Descendants,
        $condition)
    for ($index = 0; $index -lt $edits.Count; $index++) {
        $candidate = $edits.Item($index)
        if ($candidate.Current.IsEnabled -and -not $candidate.Current.IsOffscreen) {
            return $candidate
        }
    }
    return $null
}

function Send-Text([Windows.Automation.AutomationElement]$Field, [string]$Text) {
    $Field.SetFocus()
    Start-Sleep -Milliseconds 250
    $pattern = $Field.GetCurrentPattern(
        [Windows.Automation.ValuePattern]::Pattern)
    $pattern.SetValue($Text)
    Start-Sleep -Milliseconds 200
    [Windows.Forms.SendKeys]::SendWait('{ENTER}')
}

function Find-Stage(
    [object[]]$Rows,
    [string]$Stage,
    [long]$AfterSequence,
    [string]$Id = '',
    [string]$Detail = '') {
    foreach ($row in $Rows) {
        if ([long]$row.seq -le $AfterSequence -or [string]$row.stage -ne $Stage) {
            continue
        }
        if (-not [string]::IsNullOrEmpty($Id) -and [string]$row.id -ne $Id) {
            continue
        }
        if (-not [string]::IsNullOrEmpty($Detail) -and
            [string]$row.detail -ne $Detail) {
            continue
        }
        return $row
    }
    return $null
}

$launchStarted = Get-Date
$launcher = $null
$app = $null
$appPath = $null
$forcedCleanup = $false
$exceptionText = $null
$evidence = $null
try {
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = 'powershell.exe'
    $psi.Arguments = (
        '-NoProfile -ExecutionPolicy Bypass -File "' +
        (Join-Path $repo 'run_mvp.ps1') + '" -NoWake')
    $psi.WorkingDirectory = $repo
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.EnvironmentVariables['BAXY_APP_TRACE'] = $tracePath
    $launcher = [Diagnostics.Process]::Start($psi)

    $app = Wait-Until -TimeoutSeconds $StartupTimeoutSeconds -Failure (
        'El launcher no abrió la ventana real de BAXY.') -Condition {
            if ($launcher.HasExited) {
                throw "run_mvp.ps1 terminó durante el arranque con código $($launcher.ExitCode)."
            }
            Get-RepoAppProcess -NotBefore $launchStarted.AddSeconds(-1)
        }
    $appPath = $app.Path

    $field = Wait-Until -TimeoutSeconds $StartupTimeoutSeconds -Failure (
        'La ventana no expuso su entrada de texto accesible.') -Condition {
            $app.Refresh()
            if ($app.HasExited) { throw 'BAXY terminó antes de quedar utilizable.' }
            Get-InputField -Process $app
        }

    $startupReady = Wait-Until -TimeoutSeconds $StartupTimeoutSeconds -Failure (
        'La UI abrió, pero Core/Mind no alcanzaron startup.ready.') -Condition {
            Find-Stage -Rows (Read-Trace) -Stage 'startup.ready' -AfterSequence 0
        }

    $app.Refresh()
    $root = [Windows.Automation.AutomationElement]::FromHandle($app.MainWindowHandle)
    $bounds = $root.Current.BoundingRectangle
    $desktop = [Windows.Forms.SystemInformation]::VirtualScreen
    $insideDesktop = $bounds.Width -gt 0 -and $bounds.Height -gt 0 -and
        $bounds.Left -ge ($desktop.Left - 2) -and
        $bounds.Top -ge ($desktop.Top - 2) -and
        $bounds.Right -le ($desktop.Right + 2) -and
        $bounds.Bottom -le ($desktop.Bottom + 2)

    $beforeRows = Read-Trace
    $baselineSequence = if ($beforeRows.Count) {
        [long]($beforeRows | Select-Object -Last 1).seq
    } else { 0 }
    # Windows PowerShell 5.1 treats BOM-less UTF-8 source as the active ANSI
    # codepage. Build the two non-ASCII characters explicitly so the real UI
    # receives exactly "¿Qué hora es?" on every machine.
    $query = ('{0}Qu{1} hora es?' -f [char]0x00bf, [char]0x00e9)
    Send-Text -Field $field -Text $query

    $submit = Wait-Until -TimeoutSeconds $TurnTimeoutSeconds -Failure (
        'La UI no entregó el texto al bridge.') -Condition {
            Find-Stage -Rows (Read-Trace) -Stage 'submit.received' `
                -AfterSequence $baselineSequence
        }
    $turnId = [string]$submit.id
    $coreCall = Wait-Until -TimeoutSeconds $TurnTimeoutSeconds -Failure (
        'El turno no alcanzó system.time en Core.') -Condition {
            Find-Stage -Rows (Read-Trace) -Stage 'core.call.start' `
                -AfterSequence $baselineSequence -Id $turnId -Detail 'system.time'
        }
    $final = Wait-Until -TimeoutSeconds $TurnTimeoutSeconds -Failure (
        'El turno no produjo una respuesta final visible.') -Condition {
            Find-Stage -Rows (Read-Trace) -Stage 'response.final' `
                -AfterSequence $baselineSequence -Id $turnId
        }
    $visibleText = Find-Stage -Rows (Read-Trace) -Stage 'visible.text' `
        -AfterSequence $baselineSequence -Id $turnId
    if ($null -eq $visibleText) {
        throw 'La política visible no aceptó texto natural para el resultado.'
    }
    $paint = Wait-Until -TimeoutSeconds $TurnTimeoutSeconds -Failure (
        'La respuesta final no llegó a un cuadro pintado.') -Condition {
            Find-Stage -Rows (Read-Trace) -Stage 'paint.observed' `
                -AfterSequence ([long]$final.seq)
        }

    $app.Refresh()
    $evidence = [ordered]@{
        startupReady = $null -ne $startupReady
        mainWindowResponding = [bool]$app.Responding
        windowInsideVirtualDesktop = [bool]$insideDesktop
        inputAccessible = $null -ne $field
        submittedThroughRealUi = $null -ne $submit
        coreOperation = [string]$coreCall.detail
        naturalVisibleTextAccepted = $null -ne $visibleText
        finalResponsePainted = $null -ne $paint
        startupMilliseconds = [double]$startupReady.ms
        turnMilliseconds = [Math]::Round(
            [double]$paint.ms - [double]$submit.ms,
            3)
        bounds = [ordered]@{
            left = [Math]::Round($bounds.Left, 2)
            top = [Math]::Round($bounds.Top, 2)
            width = [Math]::Round($bounds.Width, 2)
            height = [Math]::Round($bounds.Height, 2)
        }
    }
}
catch {
    $exceptionText = $_.Exception.Message
}
finally {
    $closedNormally = $false
    if ($null -ne $app) {
        try {
            $app.Refresh()
            if (-not $app.HasExited) {
                $requested = $app.CloseMainWindow()
                if ($requested) {
                    try { Wait-Process -Id $app.Id -Timeout $ShutdownTimeoutSeconds -ErrorAction Stop } catch {}
                }
                $app.Refresh()
            }
            $closedNormally = $app.HasExited
            if (-not $closedNormally) {
                $forcedCleanup = $true
                $app.Kill()
                $app.WaitForExit(10000)
            }
        } catch {
            $forcedCleanup = $true
        }
    }
    if ($null -ne $launcher) {
        try {
            if (-not $launcher.HasExited) {
                $launcher.WaitForExit($ShutdownTimeoutSeconds * 1000)
            }
            if (-not $launcher.HasExited) {
                $forcedCleanup = $true
                $launcher.Kill()
                $launcher.WaitForExit(10000)
            }
        } catch { $forcedCleanup = $true }
    }

    Start-Sleep -Seconds 2
    $residual = @(
        Get-Process -Name 'Baxy', 'baxy-core', 'llama-server' -ErrorAction SilentlyContinue |
            Where-Object {
                try { $_.StartTime -ge $launchStarted.AddSeconds(-1) } catch { $false }
            } |
            Select-Object Name, Id, StartTime
    )
    if ($residual.Count -gt 0) {
        $forcedCleanup = $true
        foreach ($process in $residual) {
            try { Stop-Process -Id $process.Id -Force -ErrorAction Stop } catch {}
        }
    }

    $trace = Read-Trace
    $checksPassed = $null -eq $exceptionText -and
        $null -ne $evidence -and
        $evidence.startupReady -and
        $evidence.mainWindowResponding -and
        $evidence.windowInsideVirtualDesktop -and
        $evidence.inputAccessible -and
        $evidence.submittedThroughRealUi -and
        $evidence.coreOperation -eq 'system.time' -and
        $evidence.naturalVisibleTextAccepted -and
        $evidence.finalResponsePainted -and
        $closedNormally -and
        -not $forcedCleanup -and
        $residual.Count -eq 0
    $report = [ordered]@{
        schema = 'baxy.mvp-ui-smoke.v1'
        measuredAtUtc = (Get-Date).ToUniversalTime().ToString('o')
        scope = 'run_mvp_no_wake_real_ui_read_only_time_query_and_graceful_shutdown'
        programSha256 = Get-Sha256 $MyInvocation.MyCommand.Path
        launcherSha256 = Get-Sha256 (Join-Path $repo 'run_mvp.ps1')
        appSha256 = Get-Sha256 $appPath
        effectsExecuted = 0
        audioCapturedOrPlayed = 0
        query = if (Get-Variable query -ErrorAction SilentlyContinue) { $query } else { $null }
        evidence = $evidence
        shutdown = [ordered]@{
            closeMainWindowSucceeded = [bool]$closedNormally
            launcherExited = if ($null -ne $launcher) { [bool]$launcher.HasExited } else { $false }
            forcedCleanup = [bool]$forcedCleanup
            residualProcesses = @($residual)
        }
        trace = [ordered]@{
            path = $tracePath
            sha256 = Get-Sha256 $tracePath
            records = $trace.Count
            truncated = @($trace | Where-Object { $_.stage -eq 'trace.truncated' }).Count
        }
        error = $exceptionText
        gatePassed = [bool]$checksPassed
    }
    $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $reportPath -Encoding utf8
}

$finalReport = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
$finalReport | Select-Object schema, gatePassed, effectsExecuted, error | Format-List
if (-not $finalReport.gatePassed) { exit 1 }
