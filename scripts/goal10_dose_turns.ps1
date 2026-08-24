# Drive real turns through the launched BAXY window (WebView2 input).
# Inherited from scripts/probe_mvp_ui_smoke.ps1: UI Automation of the product,
# not a sidecar and not a corpus runner.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$TracePath,
    [Parameter(Mandatory = $true)][string]$JournalPath,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [Parameter(Mandatory = $true)][string]$SessionId,
    [string[]]$Turns,
    [int]$StartupTimeoutSeconds = 180,
    [int]$TurnTimeoutSeconds = 90
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
if (-not ('BaxyGoal10DoseWin' -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class BaxyGoal10DoseWin {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
}
'@
}

function Read-Trace {
    if (-not (Test-Path -LiteralPath $TracePath -PathType Leaf)) { return @() }
    $rows = [Collections.Generic.List[object]]::new()
    foreach ($line in Get-Content -LiteralPath $TracePath -ErrorAction SilentlyContinue) {
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

function Get-RepoAppProcess {
    $prefix = $repo.TrimEnd('\') + '\'
    foreach ($candidate in Get-Process -Name 'Baxy' -ErrorAction SilentlyContinue) {
        try {
            $path = [IO.Path]::GetFullPath($candidate.Path)
            if ($path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
                return $candidate
            }
        } catch {}
    }
    return $null
}

function Get-InputField([Diagnostics.Process]$Process) {
    $Process.Refresh()
    if ($Process.MainWindowHandle -eq [IntPtr]::Zero) { return $null }
    [void][BaxyGoal10DoseWin]::ShowWindow($Process.MainWindowHandle, 9)
    [void][BaxyGoal10DoseWin]::SetForegroundWindow($Process.MainWindowHandle)
    $root = [Windows.Automation.AutomationElement]::FromHandle($Process.MainWindowHandle)
    if ($null -eq $root) { return $null }
    $condition = New-Object Windows.Automation.PropertyCondition(
        [Windows.Automation.AutomationElement]::ControlTypeProperty,
        [Windows.Automation.ControlType]::Edit)
    $edits = $root.FindAll([Windows.Automation.TreeScope]::Descendants, $condition)
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
    Start-Sleep -Milliseconds 200
    $pattern = $Field.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern)
    $pattern.SetValue($Text)
    Start-Sleep -Milliseconds 150
    [Windows.Forms.SendKeys]::SendWait('{ENTER}')
}

function Find-Stage(
    [object[]]$Rows,
    [string]$Stage,
    [long]$AfterSequence,
    [string]$Id = '') {
    foreach ($row in $Rows) {
        if ([long]$row.seq -le $AfterSequence -or [string]$row.stage -ne $Stage) { continue }
        if (-not [string]::IsNullOrEmpty($Id) -and [string]$row.id -ne $Id) { continue }
        return $row
    }
    return $null
}

$app = Get-RepoAppProcess
if ($null -eq $app) { throw 'BAXY no está en marcha.' }
[void](Wait-Until -TimeoutSeconds $StartupTimeoutSeconds -Failure (
    'La ventana no expuso su entrada de texto.') -Condition {
        Get-InputField -Process $app
    })

$results = [Collections.Generic.List[object]]::new()
$index = 0
foreach ($text in $Turns) {
    $index += 1
    $beforeRows = Read-Trace
    $baseline = if ($beforeRows.Count) { [long]($beforeRows | Select-Object -Last 1).seq } else { 0 }
    $started = Get-Date
    $field = Wait-Until -TimeoutSeconds 30 -Failure 'Se perdió el campo de texto.' -Condition {
        Get-InputField -Process $app
    }
    $bridgeAttempts = 1
    Send-Text -Field $field -Text $text
    try {
        $submit = Wait-Until -TimeoutSeconds 3 -Failure 'bridge_retry' -Condition {
            Find-Stage -Rows (Read-Trace) -Stage 'submit.received' -AfterSequence $baseline
        }
    } catch {
        $submit = Find-Stage -Rows (Read-Trace) -Stage 'submit.received' -AfterSequence $baseline
    }
    if ($null -eq $submit) {
        # WebView2 can replace the textarea after rendering a response while the
        # old UIA element still reports enabled. submit.received is written at
        # the bridge boundary, before work starts, so its absence makes one
        # reacquire-and-resend safe without duplicating an accepted turn.
        $field = Wait-Until -TimeoutSeconds 30 -Failure 'Se perdió el campo de texto.' -Condition {
            Get-InputField -Process $app
        }
        $submit = Find-Stage -Rows (Read-Trace) -Stage 'submit.received' -AfterSequence $baseline
        if ($null -eq $submit) {
            $bridgeAttempts = 2
            Send-Text -Field $field -Text $text
            $submit = Wait-Until -TimeoutSeconds $TurnTimeoutSeconds -Failure (
                "Turno $index no cruzó el bridge: $text") -Condition {
                    Find-Stage -Rows (Read-Trace) -Stage 'submit.received' -AfterSequence $baseline
                }
        }
    }
    $turnId = [string]$submit.id
    $final = Wait-Until -TimeoutSeconds $TurnTimeoutSeconds -Failure (
        "Turno $index sin response.final: $text") -Condition {
            Find-Stage -Rows (Read-Trace) -Stage 'response.final' -AfterSequence $baseline -Id $turnId
        }
    $core = Find-Stage -Rows (Read-Trace) -Stage 'core.call.start' -AfterSequence $baseline -Id $turnId
    $visible = Find-Stage -Rows (Read-Trace) -Stage 'visible.text' -AfterSequence $baseline -Id $turnId
    $errorStage = Find-Stage -Rows (Read-Trace) -Stage 'turn.error' -AfterSequence $baseline -Id $turnId
    $results.Add([ordered]@{
        session = $SessionId
        index = $index
        text = $text
        turnId = $turnId
        submitted = $true
        coreOperation = if ($core) { [string]$core.detail } else { $null }
        visibleTextAccepted = $null -ne $visible
        finalMs = [double]$final.ms
        submitMs = [double]$submit.ms
        elapsedS = [Math]::Round(((Get-Date) - $started).TotalSeconds, 3)
        bridgeAttempts = $bridgeAttempts
        error = if ($errorStage) { [string]$errorStage.detail } else { $null }
    })
}

$payload = [ordered]@{
    session = $SessionId
    journalPath = $JournalPath
    tracePath = $TracePath
    turns = $results
    count = $results.Count
    finishedAt = (Get-Date).ToString('o')
}
$dir = Split-Path -Parent $OutputPath
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
($payload | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Host ("session={0} turns={1}" -f $SessionId, $results.Count)
