param(
    [string]$BuildRoot,
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'path_safety.ps1')
. (Join-Path $PSScriptRoot 'build_layout.ps1')
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Drawing
if ($null -eq ('BaxyCaptureNative' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class BaxyCaptureNative
{
    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool PrintWindow(IntPtr window, IntPtr deviceContext, uint flags);
}
'@
}

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$buildLayout = Get-BaxyBuildLayout -RepositoryRoot $root
$artifactRoot = [IO.Path]::GetFullPath((Join-Path $root 'artifacts\product'))
$allowedBuildRoot = [IO.Path]::GetFullPath((Join-Path $artifactRoot 'build'))
$localApplicationData = [Environment]::GetFolderPath(
    [Environment+SpecialFolder]::LocalApplicationData,
    [Environment+SpecialFolderOption]::DoNotVerify)
if ([string]::IsNullOrWhiteSpace($localApplicationData)) {
    throw 'Windows did not expose the private local application-data directory.'
}
$localApplicationData = [IO.Path]::GetFullPath($localApplicationData)
$allowedRuntimeRoot = [IO.Path]::GetFullPath(
    (Join-Path $localApplicationData 'BAXY'))
Assert-StrictDescendantPath -Parent $localApplicationData -Child $allowedRuntimeRoot
if ([string]::IsNullOrWhiteSpace($BuildRoot)) {
    $BuildRoot = Join-Path $allowedBuildRoot (
        "local-$($buildLayout.RuntimeIdentifier)")
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $artifactRoot 'product_notes_slice.png'
}
$BuildRoot = [IO.Path]::GetFullPath($BuildRoot)
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
if (-not [string]::Equals(
        [IO.Path]::GetExtension($OutputPath),
        '.png',
        [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Product capture output must use a .png naming hint.'
}
$outputBaseName = [IO.Path]::GetFileNameWithoutExtension($OutputPath)
if ([string]::IsNullOrWhiteSpace($outputBaseName)) {
    throw 'Product capture output naming hint must include a file name.'
}
Assert-StrictDescendantPath -Parent $allowedBuildRoot -Child $BuildRoot
Assert-StrictDescendantPath -Parent $artifactRoot -Child $OutputPath
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $artifactRoot
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $allowedBuildRoot
if (-not (Assert-ExistingPathChainHasNoReparsePoint -Path $BuildRoot)) {
    throw 'Product build root does not exist.'
}

$app = Join-Path $BuildRoot 'app\Baxy.exe'
$core = Join-Path $BuildRoot 'app\core\baxy-core.exe'
foreach ($required in @($app, $core)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing product binary: $required" }
}
Assert-TreeHasNoReparsePoint $BuildRoot

$dataRoot = Join-Path $allowedRuntimeRoot 'capture-product-gate'
Assert-StrictDescendantPath -Parent $allowedRuntimeRoot -Child $dataRoot
if (-not (Assert-ExistingPathChainHasNoReparsePoint -Path $allowedRuntimeRoot)) {
    New-Item -ItemType Directory -Path $allowedRuntimeRoot -Force | Out-Null
}
if (-not (Assert-ExistingPathChainHasNoReparsePoint -Path $allowedRuntimeRoot)) {
    throw 'Could not create a safe private capture runtime root.'
}
Remove-TreeFailClosed -AllowedRoot $allowedRuntimeRoot -Target $dataRoot
New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $dataRoot

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

function Find-Control($Window, [string]$Name, $ControlType) {
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do {
        foreach ($node in $Window.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)) {
            if ($node.Current.Name -eq $Name -and $node.Current.ControlType -eq $ControlType) { return $node }
        }
        Start-Sleep -Milliseconds 100
    } until ([DateTime]::UtcNow -ge $deadline)
    return $null
}

function Find-NoteResponse($Window) {
    $expectedBody = 'Guard' + [char]0x00E9 + ' la nota ' +
        [char]0x00AB + 'Compras' + [char]0x00BB + '.'
    $expectedAccessibleText = "BAXY: $expectedBody"
    $accessibleRecordFragment = "AccessibleText = $expectedAccessibleText"
    foreach ($node in $Window.FindAll(
            [Windows.Automation.TreeScope]::Descendants,
            [Windows.Automation.Condition]::TrueCondition)) {
        $name = $node.Current.Name
        if ($name -eq $expectedBody -or
            $name -eq $expectedAccessibleText -or
            $name -like "*$accessibleRecordFragment*") {
            return $node
        }
    }
    return $null
}

function Get-OwnedCoreProcesses([int]$ParentProcessId, [string]$CorePath) {
    $expected = [IO.Path]::GetFullPath($CorePath)
    $instances = @(Get-CimInstance Win32_Process -Filter "Name = 'baxy-core.exe'" | Where-Object {
        $_.ParentProcessId -eq $ParentProcessId -and
        -not [string]::IsNullOrWhiteSpace($_.ExecutablePath) -and
        [string]::Equals(
            [IO.Path]::GetFullPath($_.ExecutablePath),
            $expected,
            [StringComparison]::OrdinalIgnoreCase)
    })
    return @($instances | ForEach-Object {
        $owned = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
        if ($null -eq $owned) { return }
        try {
            # Opening SafeHandle binds this object to the original process even
            # if Windows later reuses its numeric PID.
            $null = $owned.SafeHandle
            if ([string]::Equals(
                    [IO.Path]::GetFullPath($owned.Path),
                    $expected,
                    [StringComparison]::OrdinalIgnoreCase) -and
                [Math]::Abs(
                    ($owned.StartTime.ToUniversalTime() - $_.CreationDate.ToUniversalTime()).TotalSeconds) -lt 1) {
                $owned
            } else {
                $owned.Dispose()
            }
        } catch {
            $owned.Dispose()
        }
    })
}

$previousData = [Environment]::GetEnvironmentVariable('BAXY_DATA_DIR', 'Process')
$env:BAXY_DATA_DIR = $dataRoot
$ownedCoreProcesses = @()
$process = $null
$bitmap = $null
$temporary = $null
try {
    $process = Start-Process -FilePath $app -PassThru -WindowStyle Normal
    # Bind cleanup to this exact process object before its numeric PID can be reused.
    $null = $process.SafeHandle
    $window = Find-Window $process.Id
    if ($null -eq $window) { throw 'BAXY did not expose its product window.' }
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do {
        $editor = Find-Control $window 'Mensaje para BAXY' ([Windows.Automation.ControlType]::Edit)
        $send = Find-Control $window 'Enviar mensaje' ([Windows.Automation.ControlType]::Button)
        if ($null -ne $editor -and $null -ne $send -and $editor.Current.IsEnabled) { break }
        Start-Sleep -Milliseconds 100
    } until ([DateTime]::UtcNow -ge $deadline)
    if ($null -eq $editor -or $null -eq $send -or -not $editor.Current.IsEnabled) {
        throw 'The product core did not become ready.'
    }
    $ownedCoreProcesses = @(Get-OwnedCoreProcesses -ParentProcessId $process.Id -CorePath $core)
    if ($ownedCoreProcesses.Count -ne 1) {
        throw 'The capture could not bind exactly one owned core process to the product window.'
    }

    $requestText = 'Crea una nota llamada Compras con leche, pan y caf' + [char]0x00E9
    $editor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($requestText)
    $deadline = [DateTime]::UtcNow.AddSeconds(5)
    do {
        Start-Sleep -Milliseconds 50
        $send = Find-Control $window 'Enviar mensaje' ([Windows.Automation.ControlType]::Button)
    } until (($null -ne $send -and $send.Current.IsEnabled) -or [DateTime]::UtcNow -ge $deadline)
    if ($null -eq $send -or -not $send.Current.IsEnabled) { throw 'The composer did not accept the note request.' }
    $send.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
    $noteRoot = Join-Path $dataRoot 'notes-store\notes'
    $noteFiles = @()
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do {
        Start-Sleep -Milliseconds 100
        $editor = Find-Control $window 'Mensaje para BAXY' ([Windows.Automation.ControlType]::Edit)
        $noteFiles = @(
            if (Test-Path -LiteralPath $noteRoot) {
                Get-ChildItem -LiteralPath $noteRoot -Filter '*.json' -File
            })
    } until ((
            $null -ne $editor -and
            $editor.Current.IsEnabled -and
            $noteFiles.Count -eq 1) -or
        [DateTime]::UtcNow -ge $deadline)
    if ($null -eq $editor -or
        -not $editor.Current.IsEnabled -or
        $noteFiles.Count -ne 1) {
        throw "The note mission did not converge: editor_found=$($null -ne $editor), editor_enabled=$($null -ne $editor -and $editor.Current.IsEnabled), note_files=$($noteFiles.Count)."
    }
    Start-Sleep -Milliseconds 500
    $answer = Find-NoteResponse $window

    $window.SetFocus()
    Start-Sleep -Milliseconds 500
    $rect = $window.Current.BoundingRectangle
    $width = [Math]::Max(1, [int][Math]::Round($rect.Width))
    $height = [Math]::Max(1, [int][Math]::Round($rect.Height))
    $bitmap = New-Object Drawing.Bitmap($width, $height, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    $graphics.Clear([Drawing.Color]::FromArgb(10, 14, 20))
    $deviceContext = $graphics.GetHdc()
    try {
        $appHandle = [IntPtr]$window.Current.NativeWindowHandle
        if ($appHandle -eq [IntPtr]::Zero -or
            -not [BaxyCaptureNative]::PrintWindow($appHandle, $deviceContext, 2)) {
            throw 'Windows could not render the BAXY product window for evidence.'
        }
    } finally {
        $graphics.ReleaseHdc($deviceContext)
        $graphics.Dispose()
    }
    $outputDirectory = [IO.Path]::GetFullPath((Split-Path -Parent $OutputPath))
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $outputDirectory
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $outputDirectory
    $temporary = Join-Path $outputDirectory ".$outputBaseName.$PID.$([Guid]::NewGuid().ToString('N')).tmp"
    $temporary = [IO.Path]::GetFullPath($temporary)
    Assert-StrictDescendantPath -Parent $artifactRoot -Child $temporary
    $bitmap.Save($temporary, [Drawing.Imaging.ImageFormat]::Png)
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $temporary
    $captureSha256 = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
    $contentAddressedName = "$outputBaseName-$captureSha256.png"
    $contentAddressedOutputPath = [IO.Path]::GetFullPath(
        (Join-Path $outputDirectory $contentAddressedName))
    Assert-StrictDescendantPath -Parent $artifactRoot -Child $contentAddressedOutputPath
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $contentAddressedOutputPath
    if (Test-Path -LiteralPath $contentAddressedOutputPath) {
        if (-not (Test-Path -LiteralPath $contentAddressedOutputPath -PathType Leaf)) {
            throw 'Content-addressed capture path is not a regular file.'
        }
        $existingSha256 = (Get-FileHash -LiteralPath $contentAddressedOutputPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if (-not [string]::Equals(
                $existingSha256,
                $captureSha256,
                [StringComparison]::Ordinal)) {
            throw 'Existing content-addressed capture does not match its SHA-256 name.'
        }
        Remove-Item -LiteralPath $temporary -Force
        $temporary = $null
    } else {
        Move-Item -LiteralPath $temporary -Destination $contentAddressedOutputPath
        $temporary = $null
    }
    $OutputPath = $contentAddressedOutputPath

    [ordered]@{
        output = $OutputPath
        sha256 = $captureSha256
        width = $width
        height = $height
        native_width = $width
        native_height = $height
        content_addressed = $true
        resampled = $false
        core_ready = $true
        mission_completed = $true
        response_observed_by_uia = $null -ne $answer
        note_files = $noteFiles.Count
    } | ConvertTo-Json -Compress
} finally {
    $orphanDetected = $false
    $dataCleanupFailure = $null
    try {
        if ($null -ne $bitmap) { $bitmap.Dispose() }
        if ($null -ne $temporary -and (Test-Path -LiteralPath $temporary -PathType Leaf)) {
            Assert-StrictDescendantPath -Parent $artifactRoot -Child $temporary
            $null = Assert-ExistingPathChainHasNoReparsePoint -Path $temporary
            Remove-Item -LiteralPath $temporary -Force
        }
        if ($null -ne $process -and $ownedCoreProcesses.Count -eq 0) {
            $ownedCoreProcesses = @(Get-OwnedCoreProcesses -ParentProcessId $process.Id -CorePath $core)
        }
        if ($null -ne $process -and -not $process.HasExited) {
            $null = $process.CloseMainWindow()
            if (-not $process.WaitForExit(5000)) {
                $process.Kill()
                $null = $process.WaitForExit(5000)
            }
        }
        $orphanDeadline = [DateTime]::UtcNow.AddSeconds(5)
        do {
            $liveOwnedCoreProcesses = @($ownedCoreProcesses | Where-Object { -not $_.HasExited })
            if ($liveOwnedCoreProcesses.Count -eq 0) { break }
            Start-Sleep -Milliseconds 100
        } until ([DateTime]::UtcNow -ge $orphanDeadline)
        if ($liveOwnedCoreProcesses.Count -gt 0) {
            $orphanDetected = $true
            foreach ($ownedCore in $liveOwnedCoreProcesses) {
                try {
                    $ownedCore.Kill()
                    $null = $ownedCore.WaitForExit(5000)
                } catch {
                    # The process may have exited between HasExited and Kill.
                }
            }
        }
    } finally {
        foreach ($ownedCore in $ownedCoreProcesses) { $ownedCore.Dispose() }
        if ($null -eq $previousData) {
            [Environment]::SetEnvironmentVariable('BAXY_DATA_DIR', $null, 'Process')
        } else {
            [Environment]::SetEnvironmentVariable('BAXY_DATA_DIR', $previousData, 'Process')
        }
    }
    try {
        Remove-TreeFailClosed -AllowedRoot $allowedRuntimeRoot -Target $dataRoot
    } catch {
        $dataCleanupFailure = $_.Exception.Message
    }
    if ($orphanDetected -and $null -ne $dataCleanupFailure) {
        throw "The capture detected and stopped an orphaned baxy-core process. Runtime cleanup also failed closed: $dataCleanupFailure"
    }
    if ($orphanDetected) {
        throw 'The capture detected and stopped an orphaned baxy-core process.'
    }
    if ($null -ne $dataCleanupFailure) {
        throw "The capture completed, but runtime cleanup failed closed: $dataCleanupFailure"
    }
}
