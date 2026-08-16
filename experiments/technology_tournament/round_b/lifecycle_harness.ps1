param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('dotnet-wpf', 'dotnet-wpf-rust')]
    [string]$System,
    [string]$OutputPath,
    [int]$ColdRepetitions = 7
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Drawing

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$artifactRoot = Join-Path $root 'artifacts\technology_tournament'
$workRoot = Join-Path $artifactRoot 'work\round_b_lifecycle'
$harnessPath = Join-Path $PSScriptRoot 'lifecycle_harness.ps1'
$app = Join-Path $root 'experiments\technology_tournament\round_b\native_wpf\bin\Release\net10.0-windows\baxy-dotnet-wpf-slice.exe'
$appDirectory = Split-Path -Parent $app
$appBundleFiles = @(
    $app,
    (Join-Path $appDirectory 'baxy-dotnet-wpf-slice.dll'),
    (Join-Path $appDirectory 'baxy-dotnet-wpf-slice.deps.json'),
    (Join-Path $appDirectory 'baxy-dotnet-wpf-slice.runtimeconfig.json')
)
$protocolPath = Join-Path $artifactRoot 'protocol.json'
$casesPath = Join-Path $root 'experiments\technology_tournament\cases.json'
$core = if ($System -eq 'dotnet-wpf-rust') {
    Join-Path $root 'artifacts\technology_tournament\build\packaging\rust_native\baxy-rust-slice.exe'
} else {
    Join-Path $root 'artifacts\technology_tournament\build\packaging\dotnet_native_aot\baxy-dotnet-slice.exe'
}
$coreProcessName = if ($System -eq 'dotnet-wpf-rust') { 'baxy-rust-slice.exe' } else { 'baxy-dotnet-slice.exe' }
$utf8 = New-Object Text.UTF8Encoding($false)
$script:StartedProcesses = New-Object 'Collections.Generic.List[Diagnostics.Process]'
$previousEnvironment = [ordered]@{
    BAXY_ROUND_B_CORE = [Environment]::GetEnvironmentVariable('BAXY_ROUND_B_CORE', 'Process')
    BAXY_ROUND_B_DATA = [Environment]::GetEnvironmentVariable('BAXY_ROUND_B_DATA', 'Process')
    BAXY_ROUND_B_AUTOMATION = [Environment]::GetEnvironmentVariable('BAXY_ROUND_B_AUTOMATION', 'Process')
    BAXY_ROUND_B_SCALE = [Environment]::GetEnvironmentVariable('BAXY_ROUND_B_SCALE', 'Process')
}

function Get-TreeHash([string[]]$Paths) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $files = @()
        foreach ($path in $Paths) {
            if (Test-Path -LiteralPath $path -PathType Leaf) { $files += Get-Item -LiteralPath $path }
            else { $files += Get-ChildItem -LiteralPath $path -File -Recurse }
        }
        foreach ($file in @($files | Sort-Object FullName -Unique)) {
            $relative = $file.FullName.Substring($root.Length).TrimStart('\').Replace('\', '/')
            $nameBytes = [Text.Encoding]::UTF8.GetBytes($relative)
            $null = $sha.TransformBlock($nameBytes, 0, $nameBytes.Length, $nameBytes, 0)
            $bytes = [IO.File]::ReadAllBytes($file.FullName)
            $null = $sha.TransformBlock($bytes, 0, $bytes.Length, $bytes, 0)
        }
        $null = $sha.TransformFinalBlock(@(), 0, 0)
        return ([BitConverter]::ToString($sha.Hash)).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Get-ProvenanceRecord([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to record provenance outside the repository: $resolved"
    }
    return [ordered]@{
        path = $resolved.Substring($root.Length).TrimStart('\').Replace('\', '/')
        sha256 = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

function Assert-NoReparseTree([string]$Path) {
    $pending = New-Object 'Collections.Generic.Queue[string]'
    $pending.Enqueue([IO.Path]::GetFullPath($Path))
    while ($pending.Count -gt 0) {
        $current = $pending.Dequeue()
        $item = Get-Item -LiteralPath $current -Force -ErrorAction Stop
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Refusing to traverse a reparse point while resetting lifecycle work: $current"
        }
        if (-not $item.PSIsContainer) { continue }
        foreach ($child in @(Get-ChildItem -LiteralPath $current -Force -ErrorAction Stop)) {
            if (($child.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing to traverse a reparse point while resetting lifecycle work: $($child.FullName)"
            }
            if ($child.PSIsContainer) { $pending.Enqueue($child.FullName) }
        }
    }
}

function Reset-OwnedDirectory([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    $allowed = [IO.Path]::GetFullPath($workRoot)
    if (-not $resolved.StartsWith($allowed + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to reset path outside lifecycle work root: $resolved"
    }
    if (Test-Path -LiteralPath $resolved) {
        Assert-NoReparseTree $resolved
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
    New-Item -ItemType Directory -Path $resolved -Force | Out-Null
}

function Start-Baxy([string]$DataRoot, [bool]$Automation, [bool]$Scale200) {
    $env:BAXY_ROUND_B_CORE = $core
    $env:BAXY_ROUND_B_DATA = $DataRoot
    if ($Automation) { $env:BAXY_ROUND_B_AUTOMATION = '1' } else { Remove-Item Env:BAXY_ROUND_B_AUTOMATION -ErrorAction SilentlyContinue }
    if ($Scale200) { $env:BAXY_ROUND_B_SCALE = '200' } else { Remove-Item Env:BAXY_ROUND_B_SCALE -ErrorAction SilentlyContinue }
    $started = Start-Process -FilePath $app -PassThru
    $script:StartedProcesses.Add($started)
    return $started
}

function Wait-BaxyWindow([Diagnostics.Process]$Process, [int]$Seconds = 15) {
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        $Process.Refresh()
        if ($Process.HasExited) { return $null }
        $windows = [Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children, [Windows.Automation.Condition]::TrueCondition)
        foreach ($candidate in $windows) {
            if ($candidate.Current.ProcessId -ne $Process.Id -or $candidate.Current.Name -notlike 'BAXY*') { continue }
            $composer = $candidate.FindFirst(
                [Windows.Automation.TreeScope]::Descendants,
                ([Windows.Automation.PropertyCondition]::new(
                    [Windows.Automation.AutomationElement]::AutomationIdProperty,
                    'MessageInput')))
            if ($null -ne $composer) { return $candidate }
        }
        Start-Sleep -Milliseconds 50
    } until ([DateTime]::UtcNow -ge $deadline)
    return $null
}

function Find-Control($Window, [string]$NamePattern, $ControlType, [int]$Seconds = 15) {
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        foreach ($node in $Window.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)) {
            if ($node.Current.Name -like $NamePattern -and $node.Current.ControlType -eq $ControlType) { return $node }
        }
        Start-Sleep -Milliseconds 50
    } until ([DateTime]::UtcNow -ge $deadline)
    return $null
}

function Assert-CoreReady($Window, [string]$Context = 'unspecified') {
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    $observedStatus = '<missing>'
    $observedEditor = $false
    $observedButton = $false
    do {
        $ready = $null
        $editor = $null
        $button = $null
        foreach ($node in $Window.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)) {
            switch ([string]$node.Current.AutomationId) {
                'CoreStatusText' { $ready = $node }
                'MessageInput' { $editor = $node }
                'SendButton' { $button = $node }
            }
        }
        $observedStatus = if ($null -eq $ready) { '<missing>' } else { [string]$ready.Current.Name }
        $observedEditor = $null -ne $editor
        $observedButton = $null -ne $button
        if (
            $null -ne $ready -and $ready.Current.Name -eq 'CORE LISTO' -and
            $null -ne $editor -and $editor.Current.IsEnabled -and
            $null -ne $button -and $button.Current.IsEnabled
        ) {
            return $editor
        }
        Start-Sleep -Milliseconds 50
    } until ([DateTime]::UtcNow -ge $deadline)
    $windowName = [string]$Window.Current.Name
    throw "The core did not complete startup attestation (context=$Context; window=$windowName; status=$observedStatus; editor=$observedEditor; button=$observedButton)."
}

function Get-WindowBitmap($Window) {
    $rect = $Window.Current.BoundingRectangle
    $width = [Math]::Max(1, [int][Math]::Round($rect.Width))
    $height = [Math]::Max(1, [int][Math]::Round($rect.Height))
    $bitmap = New-Object Drawing.Bitmap($width, $height, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen([int][Math]::Round($rect.Left), [int][Math]::Round($rect.Top), 0, 0, $bitmap.Size)
    } finally {
        $graphics.Dispose()
    }
    return $bitmap
}

function Get-SampledPixelChange([Drawing.Bitmap]$Before, [Drawing.Bitmap]$After) {
    $changed = 0
    $total = 0
    for ($y = 4; $y -lt [Math]::Min($Before.Height, $After.Height); $y += 12) {
        for ($x = 4; $x -lt [Math]::Min($Before.Width, $After.Width); $x += 12) {
            $left = $Before.GetPixel($x, $y)
            $right = $After.GetPixel($x, $y)
            $distance = [Math]::Abs([int]$left.R - [int]$right.R) + [Math]::Abs([int]$left.G - [int]$right.G) + [Math]::Abs([int]$left.B - [int]$right.B)
            if ($distance -ge 24) { $changed++ }
            $total++
        }
    }
    if ($total -eq 0) { return 0.0 }
    return $changed / [double]$total
}

function Get-Names($Window) {
    $names = @()
    foreach ($node in $Window.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)) {
        if (-not [string]::IsNullOrWhiteSpace($node.Current.Name)) { $names += $node.Current.Name }
    }
    return @($names)
}

function Submit-Mission($Window, [string]$Message, [string]$InvocationId) {
    $editor = Find-Control $Window 'Mensaje para BAXY' ([Windows.Automation.ControlType]::Edit)
    $idEditor = Find-Control $Window 'ID de invoc*' ([Windows.Automation.ControlType]::Edit)
    $button = Find-Control $Window 'Enviar mensaje' ([Windows.Automation.ControlType]::Button)
    if ($null -eq $editor -or $null -eq $idEditor -or $null -eq $button) { throw 'Accessible mission controls are missing.' }
    $beforeNames = @(Get-Names $Window).Count
    $idEditor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($InvocationId)
    $editor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($Message)
    $button.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    do {
        Start-Sleep -Milliseconds 50
        $names = @(Get-Names $Window)
    } until (($names.Count -gt $beforeNames -and $button.Current.IsEnabled) -or [DateTime]::UtcNow -ge $deadline)
    return @($names)
}

function Measure-WarmMissions($Window, [int]$Count) {
    $editor = Find-Control $Window 'Mensaje para BAXY' ([Windows.Automation.ControlType]::Edit)
    $idEditor = Find-Control $Window 'ID de invoc*' ([Windows.Automation.ControlType]::Edit)
    $button = Find-Control $Window 'Enviar mensaje' ([Windows.Automation.ControlType]::Button)
    if ($null -eq $editor -or $null -eq $idEditor -or $null -eq $button) { throw 'Warm latency controls are missing.' }
    $samples = @()
    for ($index = 0; $index -lt $Count; $index++) {
        $message = 'Hola BAXY'
        $beforeNames = @(Get-Names $Window).Count
        $idEditor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue("warm-$System-$index")
        $editor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($message)
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $button.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
        $deadline = [DateTime]::UtcNow.AddSeconds(10)
        do {
            Start-Sleep -Milliseconds 10
            $afterNames = @(Get-Names $Window).Count
        } until (($afterNames -gt $beforeNames -and $button.Current.IsEnabled) -or [DateTime]::UtcNow -ge $deadline)
        $timer.Stop()
        $samples += [pscustomobject][ordered]@{ index = $index; elapsed_ms = $timer.Elapsed.TotalMilliseconds; valid = ($afterNames -gt $beforeNames -and $button.Current.IsEnabled) }
    }
    return @($samples)
}

function Get-TreeIds([int]$RootProcessId) {
    $rootProcess = Get-Process -Id $RootProcessId -ErrorAction Stop
    $rootStarted = $rootProcess.StartTime.AddSeconds(-1)
    $processes = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, Name)
    $seen = New-Object 'Collections.Generic.HashSet[int]'
    $queue = New-Object 'Collections.Generic.Queue[int]'
    $queue.Enqueue($RootProcessId)
    $result = @()
    while ($queue.Count -gt 0) {
        $currentId = $queue.Dequeue()
        if (-not $seen.Add($currentId)) { continue }
        $result += $currentId
        foreach ($child in @($processes | Where-Object { $_.ParentProcessId -eq $currentId })) {
            $live = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
            if ($null -ne $live -and $live.StartTime -ge $rootStarted) { $queue.Enqueue([int]$child.ProcessId) }
        }
    }
    return @($result)
}

function Find-CorePid([int]$ParentProcessId, [int]$Seconds = 10) {
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        $match = @(Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $ParentProcessId -and $_.Name -eq $coreProcessName } | Select-Object -First 1)
        if ($match) { return [int]$match.ProcessId }
        Start-Sleep -Milliseconds 50
    } until ([DateTime]::UtcNow -ge $deadline)
    return 0
}

function Wait-AllGone([int[]]$ProcessIds, [int]$Seconds = 5) {
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        $alive = @($ProcessIds | Where-Object { $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue) })
        if ($alive.Count -eq 0) { return @() }
        Start-Sleep -Milliseconds 50
    } until ([DateTime]::UtcNow -ge $deadline)
    return @($alive)
}

function Close-Baxy([Diagnostics.Process]$Process, [int[]]$OwnedIds) {
    if (-not $Process.HasExited) {
        $null = $Process.CloseMainWindow()
        if (-not $Process.WaitForExit(5000)) { Stop-Process -Id $Process.Id -Force }
    }
    return @(Wait-AllGone $OwnedIds)
}

function Percentile([double[]]$Values, [double]$Value) {
    $ordered = @($Values | Sort-Object)
    if ($ordered.Count -eq 0) { return [double]::NaN }
    $rank = ($ordered.Count - 1) * $Value
    $low = [Math]::Floor($rank)
    $high = [Math]::Ceiling($rank)
    if ($low -eq $high) { return [double]$ordered[$low] }
    return [double]$ordered[$low] * ($high - $rank) + [double]$ordered[$high] * ($rank - $low)
}

try {
if (-not (Test-Path -LiteralPath $app) -or -not (Test-Path -LiteralPath $core)) { throw 'Required lifecycle binaries are missing.' }
$systemRoot = Join-Path $workRoot $System
Reset-OwnedDirectory $systemRoot
$startedUtc = [DateTime]::UtcNow
$coldSamples = @()

for ($index = 0; $index -lt $ColdRepetitions; $index++) {
    $data = Join-Path $systemRoot ("cold_{0:D2}" -f $index)
    New-Item -ItemType Directory -Path $data -Force | Out-Null
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $cold = Start-Baxy $data $true $false
    $coldWindow = $null
    $coldOwned = @()
    $coldValid = $false
    $coldReadyMs = [double]::NaN
    $coldOrphans = @()
    $coldRootExitedPrematurely = $false
    try {
        $coldWindow = Wait-BaxyWindow $cold
        $editor = if ($null -ne $coldWindow) { Assert-CoreReady $coldWindow "cold_$index" } else { $null }
        $timer.Stop()
        $coldRootExitedPrematurely = $cold.HasExited
        $coldOwned = if ($coldRootExitedPrematurely) { @() } else { @(Get-TreeIds $cold.Id) }
        $coldReadyMs = $timer.Elapsed.TotalMilliseconds
        $coldValid = ($null -ne $editor -and -not $coldRootExitedPrematurely)
    } finally {
        if (-not $cold.HasExited) { $coldOrphans = @(Close-Baxy $cold $coldOwned) }
        else { $coldOrphans = @(Wait-AllGone $coldOwned) }
    }
    $coldSamples += [pscustomobject][ordered]@{ index = $index; ready_ms = $coldReadyMs; valid = $coldValid; root_exited_prematurely = $coldRootExitedPrematurely; orphan_process_ids = @($coldOrphans) }
}

$warmData = Join-Path $systemRoot 'warm_ui'
New-Item -ItemType Directory -Path $warmData -Force | Out-Null
$warm = Start-Baxy $warmData $true $false
$warmWindow = Wait-BaxyWindow $warm
if ($null -eq $warmWindow) { throw 'Warm latency window did not start.' }
$null = Assert-CoreReady $warmWindow 'warm_ui'
$warmSamples = @(Measure-WarmMissions $warmWindow 31)
$warmOwned = @(Get-TreeIds $warm.Id)
$warmOrphans = @(Close-Baxy $warm $warmOwned)

$lifecycleData = Join-Path $systemRoot 'lifecycle_data'
New-Item -ItemType Directory -Path $lifecycleData -Force | Out-Null
$primary = Start-Baxy $lifecycleData $true $false
$primaryWindow = Wait-BaxyWindow $primary
if ($null -eq $primaryWindow) { throw 'Primary lifecycle window did not start.' }
$null = Assert-CoreReady $primaryWindow 'primary_lifecycle'
$primaryOwned = @(Get-TreeIds $primary.Id)
$primaryCorePid = Find-CorePid $primary.Id

$secondary = Start-Baxy $lifecycleData $true $false
$secondaryExited = $secondary.WaitForExit(3000)
if (-not $secondaryExited) { Stop-Process -Id $secondary.Id -Force }
$secondaryExitCode = if ($secondaryExited) { $secondary.ExitCode } else { $null }
$singleInstancePassed = $secondaryExited -and $secondaryExitCode -eq 0 -and $primaryCorePid -gt 0

$createNames = @(Submit-Mission $primaryWindow 'Crea la nota recovery.txt con el texto: vive' "lifecycle-$System-create")
$recoveryFile = Join-Path $lifecycleData 'workspace\notes\recovery.txt'
$createPassed = (Test-Path -LiteralPath $recoveryFile) -and ([IO.File]::ReadAllText($recoveryFile, [Text.Encoding]::UTF8) -eq 'vive') -and ($createNames -contains 'VERIFICADO')
$primaryOwned = @(Get-TreeIds $primary.Id)
Stop-Process -Id $primary.Id -Force
$null = $primary.WaitForExit(3000)
$crashOrphans = @(Wait-AllGone $primaryOwned)

$restart = Start-Baxy $lifecycleData $true $false
$restartWindow = Wait-BaxyWindow $restart
if ($null -eq $restartWindow) { throw 'Restart window did not start.' }
$null = Assert-CoreReady $restartWindow 'restart_after_crash'
$restartNames = @(Submit-Mission $restartWindow 'Lee la nota recovery.txt' "lifecycle-$System-read")
$restartPassed = ($restartNames -contains 'VERIFICADO') -and @($restartNames | Where-Object { $_ -like '*vive*' }).Count -gt 0
$restartOwned = @(Get-TreeIds $restart.Id)
$restartOrphans = @(Close-Baxy $restart $restartOwned)

$scaleData = Join-Path $systemRoot 'scale_200'
New-Item -ItemType Directory -Path $scaleData -Force | Out-Null
$scale = Start-Baxy $scaleData $true $true
$scaleWindow = Wait-BaxyWindow $scale
if ($null -eq $scaleWindow) { throw 'Scale test window did not start.' }
$null = Assert-CoreReady $scaleWindow 'scale_200'
$scaleEditor = Find-Control $scaleWindow 'Mensaje para BAXY' ([Windows.Automation.ControlType]::Edit)
$scaleSend = Find-Control $scaleWindow 'Enviar mensaje' ([Windows.Automation.ControlType]::Button)
$contrast = Find-Control $scaleWindow 'Alternar contraste alto' ([Windows.Automation.ControlType]::Button)
$beforeContrast = Get-WindowBitmap $scaleWindow
$contrast.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
Start-Sleep -Milliseconds 300
$afterContrast = Get-WindowBitmap $scaleWindow
$contrastPixelChange = Get-SampledPixelChange $beforeContrast $afterContrast
$beforeContrast.Dispose()
$afterContrast.Dispose()
$windowRect = $scaleWindow.Current.BoundingRectangle
$editorRect = $scaleEditor.Current.BoundingRectangle
$sendRect = $scaleSend.Current.BoundingRectangle
$scaleNodes = $scaleWindow.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)
$scaleContained = -not $scaleEditor.Current.IsOffscreen -and -not $scaleSend.Current.IsOffscreen -and $editorRect.Left -ge $windowRect.Left -and $editorRect.Right -le $windowRect.Right -and $sendRect.Right -le $windowRect.Right
$scaleResponsive = @($scaleNodes | Where-Object { $_.Current.AutomationId -eq 'ActivityRail' }).Count -eq 0
$editorOffscreen = $scaleEditor.Current.IsOffscreen
$sendOffscreen = $scaleSend.Current.IsOffscreen
$contrastHelp = $contrast.Current.HelpText
$scaleOwned = @(Get-TreeIds $scale.Id)
$scaleOrphans = @(Close-Baxy $scale $scaleOwned)

$validCold = @($coldSamples | Where-Object valid | ForEach-Object { [double]$_.ready_ms })
$validWarm = @($warmSamples | Select-Object -Skip 1 | Where-Object valid | ForEach-Object { [double]$_.elapsed_ms })
$result = [ordered]@{
    schema_version = 1
    protocol_id = 'baxy-technology-tournament-v1'
    round = 'b_lifecycle'
    system_id = $System
    started_utc = $startedUtc.ToString('o')
    finished_utc = [DateTime]::UtcNow.ToString('o')
    provenance = [ordered]@{
        harness = Get-ProvenanceRecord $harnessPath
        protocol = Get-ProvenanceRecord $protocolPath
        cases = Get-ProvenanceRecord $casesPath
    }
    hashes = [ordered]@{
        shell_bundle_sha256 = Get-TreeHash $appBundleFiles
        shell_entrypoint_sha256 = (Get-FileHash -LiteralPath $app -Algorithm SHA256).Hash.ToLowerInvariant()
        core_sha256 = (Get-FileHash -LiteralPath $core -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    cold_start = [ordered]@{
        repetitions = $ColdRepetitions
        valid = $validCold.Count
        p50_ms = Percentile $validCold 0.50
        p95_ms = Percentile $validCold 0.95
        samples = @($coldSamples)
    }
    warm_ui = [ordered]@{
        warmup_discarded = $warmSamples[0]
        valid = $validWarm.Count
        p50_ms = Percentile $validWarm 0.50
        p95_ms = Percentile $validWarm 0.95
        throughput_per_second = if (($validWarm | Measure-Object -Sum).Sum -gt 0) { $validWarm.Count / (($validWarm | Measure-Object -Sum).Sum / 1000.0) } else { 0 }
        samples = @($warmSamples | Select-Object -Skip 1)
        orphan_process_ids = @($warmOrphans)
    }
    single_instance = [ordered]@{
        passed = $singleInstancePassed
        second_exited_within_ms = if ($secondaryExited) { 3000 } else { $null }
        second_exit_code = $secondaryExitCode
        primary_core_pid = $primaryCorePid
    }
    crash_and_restart = [ordered]@{
        create_verified = $createPassed
        crash_orphan_process_ids = @($crashOrphans)
        job_cleanup_passed = ($crashOrphans.Count -eq 0)
        restart_read_verified = $restartPassed
        graceful_restart_orphan_process_ids = @($restartOrphans)
    }
    scale_and_contrast = [ordered]@{
        equivalent_work_area = '900x520 DIPs; physical 200 percent monitor not available on this host'
        controls_contained = $scaleContained
        responsive_activity_hidden = $scaleResponsive
        editor_offscreen = $editorOffscreen
        send_offscreen = $sendOffscreen
        contrast_help_text = $contrastHelp
        sampled_pixel_change_ratio = $contrastPixelChange
        contrast_toggled = ($contrastHelp -eq 'Contraste alto activado' -and $contrastPixelChange -ge 0.05)
        orphan_process_ids = @($scaleOrphans)
    }
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path $artifactRoot "raw\round_b_lifecycle_$($System.Replace('-', '_')).json" }
New-Item -ItemType Directory -Path (Split-Path -Parent ([IO.Path]::GetFullPath($OutputPath))) -Force | Out-Null
$resolvedOutput = [IO.Path]::GetFullPath($OutputPath)
$temporaryOutput = "$resolvedOutput.$PID.tmp"
[IO.File]::WriteAllText($temporaryOutput, ($result | ConvertTo-Json -Depth 10), $utf8)
Move-Item -LiteralPath $temporaryOutput -Destination $resolvedOutput -Force
$summary = [ordered]@{
    system = $System
    cold_p95_ms = $result.cold_start.p95_ms
    warm_p95_ms = $result.warm_ui.p95_ms
    single_instance = $result.single_instance.passed
    job_cleanup = $result.crash_and_restart.job_cleanup_passed
    restart = $result.crash_and_restart.restart_read_verified
    scale = $result.scale_and_contrast.controls_contained
    contrast = $result.scale_and_contrast.contrast_toggled
    output = $resolvedOutput
}
$summary | ConvertTo-Json -Compress
$lifecyclePassed = (
    $result.cold_start.valid -eq $ColdRepetitions -and
    @($result.cold_start.samples | Where-Object { $_.orphan_process_ids.Count -ne 0 }).Count -eq 0 -and
    $result.warm_ui.valid -eq 30 -and
    $result.warm_ui.orphan_process_ids.Count -eq 0 -and
    $result.single_instance.passed -and
    $result.crash_and_restart.create_verified -and
    $result.crash_and_restart.job_cleanup_passed -and
    $result.crash_and_restart.restart_read_verified -and
    $result.crash_and_restart.graceful_restart_orphan_process_ids.Count -eq 0 -and
    $result.scale_and_contrast.controls_contained -and
    $result.scale_and_contrast.responsive_activity_hidden -and
    $result.scale_and_contrast.contrast_toggled -and
    $result.scale_and_contrast.orphan_process_ids.Count -eq 0)
if (-not $lifecyclePassed) { throw "Round B lifecycle hard gate failed for $System" }
} finally {
    foreach ($started in @($script:StartedProcesses)) {
        try {
            $started.Refresh()
            if (-not $started.HasExited) { Stop-Process -Id $started.Id -Force -ErrorAction SilentlyContinue }
        } catch { }
    }
    Start-Sleep -Milliseconds 200
    foreach ($entry in $previousEnvironment.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
    }
}
