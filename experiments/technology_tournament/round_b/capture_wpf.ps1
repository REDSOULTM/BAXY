param(
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Drawing

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$artifactRoot = Join-Path $root 'artifacts\technology_tournament'
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $artifactRoot 'round_b_wpf.png'
}
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
$allowedOutputRoot = [IO.Path]::GetFullPath($artifactRoot)
if (-not $OutputPath.StartsWith($allowedOutputRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Capture output must stay below $allowedOutputRoot"
}

$app = Join-Path $root 'experiments\technology_tournament\round_b\native_wpf\bin\Release\net10.0-windows\baxy-dotnet-wpf-slice.exe'
$core = Join-Path $artifactRoot 'build\packaging\dotnet_native_aot\baxy-dotnet-slice.exe'
$dataRoot = Join-Path $artifactRoot 'work\round_b_capture\data'
foreach ($required in @($app, $core)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Required binary is missing: $required" }
}
if (Test-Path -LiteralPath $dataRoot) {
    $resolvedData = [IO.Path]::GetFullPath($dataRoot)
    $allowedWork = [IO.Path]::GetFullPath((Join-Path $artifactRoot 'work'))
    if (-not $resolvedData.StartsWith($allowedWork + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to reset capture data outside $allowedWork"
    }
    Remove-Item -LiteralPath $resolvedData -Recurse -Force
}
New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null

function Find-Window([int]$ProcessId) {
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do {
        foreach ($candidate in [Windows.Automation.AutomationElement]::RootElement.FindAll(
            [Windows.Automation.TreeScope]::Children,
            [Windows.Automation.Condition]::TrueCondition)) {
            if ($candidate.Current.ProcessId -eq $ProcessId -and $candidate.Current.Name -like 'BAXY*') { return $candidate }
        }
        Start-Sleep -Milliseconds 100
    } until ([DateTime]::UtcNow -ge $deadline)
    return $null
}

function Find-Control($Window, [string]$NamePattern, $ControlType) {
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do {
        foreach ($node in $Window.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)) {
            if ($node.Current.Name -like $NamePattern -and $node.Current.ControlType -eq $ControlType) { return $node }
        }
        Start-Sleep -Milliseconds 50
    } until ([DateTime]::UtcNow -ge $deadline)
    return $null
}

function Count-NamedNodes($Window) {
    return @($Window.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition) |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_.Current.Name) }).Count
}

$previousCore = [Environment]::GetEnvironmentVariable('BAXY_ROUND_B_CORE', 'Process')
$previousData = [Environment]::GetEnvironmentVariable('BAXY_ROUND_B_DATA', 'Process')
$previousAutomation = [Environment]::GetEnvironmentVariable('BAXY_ROUND_B_AUTOMATION', 'Process')
$env:BAXY_ROUND_B_CORE = $core
$env:BAXY_ROUND_B_DATA = $dataRoot
[Environment]::SetEnvironmentVariable('BAXY_ROUND_B_AUTOMATION', $null, 'Process')
$process = $null
$bitmap = $null
try {
    $process = Start-Process -FilePath $app -PassThru
    $window = Find-Window $process.Id
    if ($null -eq $window) { throw 'BAXY did not expose its main window.' }
    $ready = Find-Control $window 'CORE LISTO' ([Windows.Automation.ControlType]::Text)
    $editor = Find-Control $window 'Mensaje para BAXY' ([Windows.Automation.ControlType]::Edit)
    $send = Find-Control $window 'Enviar mensaje' ([Windows.Automation.ControlType]::Button)
    if ($null -eq $ready -or $null -eq $editor -or $null -eq $send -or -not $send.Current.IsEnabled) {
        throw 'BAXY core readiness attestation failed before capture.'
    }

    $before = Count-NamedNodes $window
    $editor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue('Crea la nota ideas.txt con el texto: comprar te')
    $send.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    do {
        Start-Sleep -Milliseconds 100
        $after = Count-NamedNodes $window
    } until (($after -gt $before -and $send.Current.IsEnabled) -or [DateTime]::UtcNow -ge $deadline)
    if ($after -le $before -or -not $send.Current.IsEnabled) { throw 'The captured mission did not finish.' }

    $window.SetFocus()
    Start-Sleep -Milliseconds 500
    $rect = $window.Current.BoundingRectangle
    $width = [Math]::Max(1, [int][Math]::Round($rect.Width))
    $height = [Math]::Max(1, [int][Math]::Round($rect.Height))
    $bitmap = New-Object Drawing.Bitmap($width, $height, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen([int][Math]::Round($rect.Left), [int][Math]::Round($rect.Top), 0, 0, $bitmap.Size)
    } finally {
        $graphics.Dispose()
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $OutputPath) -Force | Out-Null
    $temporary = "$OutputPath.$PID.tmp"
    $bitmap.Save($temporary, [Drawing.Imaging.ImageFormat]::Png)
    Move-Item -LiteralPath $temporary -Destination $OutputPath -Force
    [ordered]@{
        output = $OutputPath
        width = $width
        height = $height
        mission_completed = $true
        core_ready = $true
    } | ConvertTo-Json -Compress
} finally {
    if ($null -ne $bitmap) { $bitmap.Dispose() }
    if ($null -ne $process -and -not $process.HasExited) {
        $null = $process.CloseMainWindow()
        if (-not $process.WaitForExit(5000)) { Stop-Process -Id $process.Id -Force }
    }
    foreach ($entry in @(
        @('BAXY_ROUND_B_CORE', $previousCore),
        @('BAXY_ROUND_B_DATA', $previousData),
        @('BAXY_ROUND_B_AUTOMATION', $previousAutomation))) {
        if ($null -eq $entry[1]) {
            [Environment]::SetEnvironmentVariable($entry[0], $null, 'Process')
        } else {
            [Environment]::SetEnvironmentVariable($entry[0], [string]$entry[1], 'Process')
        }
    }
}
