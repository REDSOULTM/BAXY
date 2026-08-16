param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('dotnet-webview', 'tauri-rust', 'dotnet-wpf', 'dotnet-wpf-rust')]
    [string]$Shell,
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type -ReferencedAssemblies UIAutomationClient,UIAutomationTypes @'
using System.Threading;
using System.Windows.Automation;
public static class BaxyRoundBLiveCounter {
    public static int Count;
    public static string LastName = "";
    public static readonly AutomationEventHandler Handler = new AutomationEventHandler(OnEvent);
    private static void OnEvent(object sender, AutomationEventArgs args) {
        Interlocked.Increment(ref Count);
        AutomationElement element = sender as AutomationElement;
        if (element != null) LastName = element.Current.Name;
    }
}
'@

$script:Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$script:ArtifactRoot = Join-Path $script:Root 'artifacts\technology_tournament'
$script:WorkRoot = Join-Path $script:ArtifactRoot 'work\round_b'
$script:HarnessPath = Join-Path $PSScriptRoot 'harness.ps1'
$script:CasesPath = Join-Path $script:Root 'experiments\technology_tournament\cases.json'
$script:ProtocolPath = Join-Path $script:ArtifactRoot 'protocol.json'
$utf8 = New-Object Text.UTF8Encoding($false)

$definitions = @{
    'dotnet-webview' = @{
        DisplayName = '.NET + WebView2'
        App = Join-Path $script:Root 'experiments\technology_tournament\round_b\dotnet_webview\bin\Release\net10.0-windows\baxy-dotnet-webview-slice.exe'
        Core = Join-Path $script:Root 'artifacts\technology_tournament\build\packaging\dotnet_native_aot\baxy-dotnet-slice.exe'
        Bundle = Join-Path $script:Root 'experiments\technology_tournament\round_b\dotnet_webview\bin\Release\net10.0-windows'
        Source = @(
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\dotnet_webview'),
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\shared_ui')
        )
    }
    'tauri-rust' = @{
        DisplayName = 'Tauri + Rust'
        App = Join-Path $script:Root 'experiments\technology_tournament\round_b\tauri_rust\src-tauri\target\release\baxy-tauri-rust-slice.exe'
        Core = Join-Path $script:Root 'artifacts\technology_tournament\build\packaging\rust_native\baxy-rust-slice.exe'
        Bundle = Join-Path $script:Root 'experiments\technology_tournament\round_b\tauri_rust\src-tauri\target\release\baxy-tauri-rust-slice.exe'
        Source = @(
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\tauri_rust'),
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\shared_ui')
        )
    }
    'dotnet-wpf' = @{
        DisplayName = '.NET WPF nativo'
        App = Join-Path $script:Root 'experiments\technology_tournament\round_b\native_wpf\bin\Release\net10.0-windows\baxy-dotnet-wpf-slice.exe'
        Core = Join-Path $script:Root 'artifacts\technology_tournament\build\packaging\dotnet_native_aot\baxy-dotnet-slice.exe'
        Bundle = @(
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\native_wpf\bin\Release\net10.0-windows\baxy-dotnet-wpf-slice.exe'),
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\native_wpf\bin\Release\net10.0-windows\baxy-dotnet-wpf-slice.dll'),
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\native_wpf\bin\Release\net10.0-windows\baxy-dotnet-wpf-slice.deps.json'),
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\native_wpf\bin\Release\net10.0-windows\baxy-dotnet-wpf-slice.runtimeconfig.json')
        )
        Source = @(
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\native_wpf'),
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\dotnet_webview\CoreBridge.cs'),
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\tauri_rust\src-tauri\icons\icon.ico'),
            (Join-Path $script:Root 'experiments\technology_tournament\dotnet_windows_core')
        )
    }
    'dotnet-wpf-rust' = @{
        DisplayName = '.NET WPF nativo'
        App = Join-Path $script:Root 'experiments\technology_tournament\round_b\native_wpf\bin\Release\net10.0-windows\baxy-dotnet-wpf-slice.exe'
        Core = Join-Path $script:Root 'artifacts\technology_tournament\build\packaging\rust_native\baxy-rust-slice.exe'
        Bundle = @(
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\native_wpf\bin\Release\net10.0-windows\baxy-dotnet-wpf-slice.exe'),
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\native_wpf\bin\Release\net10.0-windows\baxy-dotnet-wpf-slice.dll'),
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\native_wpf\bin\Release\net10.0-windows\baxy-dotnet-wpf-slice.deps.json'),
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\native_wpf\bin\Release\net10.0-windows\baxy-dotnet-wpf-slice.runtimeconfig.json')
        )
        Source = @(
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\native_wpf'),
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\dotnet_webview\CoreBridge.cs'),
            (Join-Path $script:Root 'experiments\technology_tournament\round_b\tauri_rust\src-tauri\icons\icon.ico'),
            (Join-Path $script:Root 'experiments\technology_tournament\rust_core')
        )
    }
}
$definition = $definitions[$Shell]

function Reset-OwnedDirectory([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    $allowed = [IO.Path]::GetFullPath($script:WorkRoot)
    if (-not $resolved.StartsWith($allowed + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to reset a path outside the Round B work root: $resolved"
    }
    if (Test-Path -LiteralPath $resolved) {
        Assert-NoReparseTree $resolved
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
    New-Item -ItemType Directory -Path $resolved -Force | Out-Null
}

function Assert-NoReparseTree([string]$Path) {
    $pending = New-Object 'Collections.Generic.Queue[string]'
    $pending.Enqueue([IO.Path]::GetFullPath($Path))
    while ($pending.Count -gt 0) {
        $current = $pending.Dequeue()
        $item = Get-Item -LiteralPath $current -Force -ErrorAction Stop
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Refusing to traverse a reparse point while resetting Round B work: $current"
        }
        if (-not $item.PSIsContainer) { continue }
        foreach ($child in @(Get-ChildItem -LiteralPath $current -Force -ErrorAction Stop)) {
            if (($child.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing to traverse a reparse point while resetting Round B work: $($child.FullName)"
            }
            if ($child.PSIsContainer) { $pending.Enqueue($child.FullName) }
        }
    }
}

function Get-ProvenanceRecord([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($script:Root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to record provenance outside the repository: $resolved"
    }
    return [ordered]@{
        path = $resolved.Substring($script:Root.Length).TrimStart('\').Replace('\', '/')
        sha256 = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

function Get-TreeIds([int]$RootProcessId) {
    $processes = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, Name)
    $rootProcess = Get-Process -Id $RootProcessId -ErrorAction Stop
    $rootStarted = $rootProcess.StartTime.AddSeconds(-1)
    $seen = New-Object 'Collections.Generic.HashSet[int]'
    $pending = New-Object 'Collections.Generic.Queue[int]'
    $pending.Enqueue($RootProcessId)
    $result = @()
    while ($pending.Count -gt 0) {
        $currentId = $pending.Dequeue()
        if (-not $seen.Add($currentId)) { continue }
        $result += $currentId
        foreach ($child in @($processes | Where-Object { $_.ParentProcessId -eq $currentId })) {
            $liveChild = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
            if ($null -ne $liveChild -and $liveChild.StartTime -ge $rootStarted) {
                $pending.Enqueue([int]$child.ProcessId)
            }
        }
    }
    return @($result)
}

function Get-TreeMemory([int]$RootProcessId) {
    $ids = @(Get-TreeIds $RootProcessId)
    $samples = @()
    foreach ($processId in $ids) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($null -ne $process) {
            $samples += [pscustomobject][ordered]@{
                pid = $processId
                name = $process.ProcessName
                private_bytes = [int64]$process.PrivateMemorySize64
                working_set_bytes = [int64]$process.WorkingSet64
                peak_working_set_bytes = [int64]$process.PeakWorkingSet64
            }
        }
    }
    return [pscustomobject][ordered]@{
        private_bytes = [int64](($samples | Measure-Object private_bytes -Sum).Sum)
        working_set_bytes = [int64](($samples | Measure-Object working_set_bytes -Sum).Sum)
        peak_working_set_bytes = [int64](($samples | Measure-Object peak_working_set_bytes -Sum).Sum)
        processes = @($samples)
    }
}

function Get-TreeGpuMemory([int]$RootProcessId) {
    $ids = @(Get-TreeIds $RootProcessId)
    $counters = @(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory -ErrorAction SilentlyContinue)
    $samples = @()
    foreach ($processId in $ids) {
        $matching = @($counters | Where-Object { $_.Name -like "pid_$($processId)_*" })
        $dedicated = if ($matching.Count -gt 0) { [int64](($matching | Measure-Object DedicatedUsage -Sum).Sum) } else { [int64]0 }
        $shared = if ($matching.Count -gt 0) { [int64](($matching | Measure-Object SharedUsage -Sum).Sum) } else { [int64]0 }
        $samples += [pscustomobject][ordered]@{
            pid = $processId
            dedicated_bytes = $dedicated
            shared_bytes = $shared
        }
    }
    return [pscustomobject][ordered]@{
        dedicated_bytes = [int64](($samples | Measure-Object dedicated_bytes -Sum).Sum)
        shared_bytes = [int64](($samples | Measure-Object shared_bytes -Sum).Sum)
        source = 'Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory'
        processes = @($samples)
    }
}

function Get-NetworkSnapshot([int]$RootProcessId) {
    $ids = @(Get-TreeIds $RootProcessId)
    try {
        $allTcp = @(Get-NetTCPConnection -ErrorAction Stop)
        $allUdp = @(Get-NetUDPEndpoint -ErrorAction Stop)
    } catch {
        throw "Network observer failed closed: $($_.Exception.GetType().FullName)"
    }
    $tcp = @($allTcp | Where-Object { $ids -contains $_.OwningProcess } | Select-Object State, LocalAddress, LocalPort, RemoteAddress, RemotePort, OwningProcess)
    $udp = @($allUdp | Where-Object { $ids -contains $_.OwningProcess } | Select-Object LocalAddress, LocalPort, OwningProcess)
    return [ordered]@{
        observer = 'Get-NetTCPConnection+Get-NetUDPEndpoint'
        observer_ok = $true
        process_ids = @($ids)
        tcp = $tcp
        udp = $udp
    }
}

function Get-BundleBytes([string[]]$Paths) {
    $total = [int64]0
    foreach ($path in $Paths) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $total += [int64](Get-Item -LiteralPath $path).Length
        } else {
            $total += [int64](Get-ChildItem -LiteralPath $path -File -Recurse | Measure-Object Length -Sum).Sum
        }
    }
    return $total
}

function Get-PathSetHash([string[]]$Paths, [bool]$ExcludeBuildOutputs) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $files = @()
        foreach ($path in $Paths) {
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                $files += Get-Item -LiteralPath $path
            } else {
                $files += Get-ChildItem -LiteralPath $path -File -Recurse
            }
        }
        if ($ExcludeBuildOutputs) {
            $files = @($files | Where-Object {
                $_.FullName -notlike '*\node_modules\*' -and
                $_.FullName -notlike '*\target\*' -and
                $_.FullName -notlike '*\bin\*' -and
                $_.FullName -notlike '*\obj\*'
            })
        }
        $files = @($files | Sort-Object FullName -Unique)
        foreach ($file in $files) {
            $relative = $file.FullName.Substring($script:Root.Length).TrimStart('\').Replace('\', '/')
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

function Get-SourceHash([string[]]$Paths) {
    return Get-PathSetHash $Paths $true
}

function Get-BundleHash([string[]]$Paths) {
    return Get-PathSetHash @($Paths) $false
}

function Find-BaxyWindow([int]$ProcessId, [DateTime]$Deadline) {
    do {
        $windows = [Windows.Automation.AutomationElement]::RootElement.FindAll(
            [Windows.Automation.TreeScope]::Children,
            [Windows.Automation.Condition]::TrueCondition)
        foreach ($candidate in $windows) {
            if ($candidate.Current.ProcessId -ne $ProcessId -or $candidate.Current.Name -notlike 'BAXY*') { continue }
            $composer = $candidate.FindFirst(
                [Windows.Automation.TreeScope]::Descendants,
                ([Windows.Automation.PropertyCondition]::new(
                    [Windows.Automation.AutomationElement]::AutomationIdProperty,
                    'MessageInput')))
            if ($null -ne $composer) { return $candidate }
        }
        Start-Sleep -Milliseconds 50
    } until ([DateTime]::UtcNow -ge $Deadline)
    return $null
}

function Find-Control($Window, [string]$NamePattern, $ControlType, [DateTime]$Deadline) {
    do {
        $nodes = $Window.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)
        foreach ($node in $nodes) {
            if ($node.Current.Name -like $NamePattern -and $node.Current.ControlType -eq $ControlType) {
                return $node
            }
        }
        Start-Sleep -Milliseconds 50
    } until ([DateTime]::UtcNow -ge $Deadline)
    return $null
}

function Get-Names($Window) {
    $names = @()
    $nodes = $Window.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)
    foreach ($node in $nodes) {
        if (-not [string]::IsNullOrWhiteSpace($node.Current.Name)) { $names += $node.Current.Name }
    }
    return @($names)
}

function Get-FocusKey($Element) {
    $runtimeId = @($Element.GetRuntimeId()) -join '.'
    $automationId = [string]$Element.Current.AutomationId
    $name = [string]$Element.Current.Name
    $controlType = [string]$Element.Current.ControlType.ProgrammaticName
    return "$runtimeId|$automationId|$name|$controlType"
}

function Test-SameStringSet([string[]]$Left, [string[]]$Right) {
    if ($Left.Count -ne $Right.Count) { return $false }
    return (@(Compare-Object -ReferenceObject @($Left | Sort-Object) -DifferenceObject @($Right | Sort-Object)).Count -eq 0)
}

function Get-KeyboardFocusEvidence($Window, $Editor) {
    $uiaFocusable = @()
    foreach ($node in $Window.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)) {
        try {
            if ($node.Current.IsKeyboardFocusable -and $node.Current.IsEnabled -and -not $node.Current.IsOffscreen) {
                $uiaFocusable += [pscustomobject][ordered]@{
                    key = Get-FocusKey $node
                    automation_id = [string]$node.Current.AutomationId
                    name = [string]$node.Current.Name
                    control_type = [string]$node.Current.ControlType.ProgrammaticName
                }
            }
        } catch { }
    }
    $uiaFocusable = @($uiaFocusable | Sort-Object key -Unique)
    $expectedAutomationIds = @('InvocationInput', 'MessageInput', 'SendButton', 'ContrastButton')
    $expectedNamedButtons = @('Crear una nota', 'Leer una nota', 'Mover a papelera')
    $focusable = @($uiaFocusable | Where-Object {
        $_.automation_id -in $expectedAutomationIds -or $_.name -in $expectedNamedButtons
    } | Sort-Object key -Unique)
    if ($focusable.Count -eq 0) { throw 'No keyboard-focusable controls were exposed.' }
    $catalog = @($focusable | ForEach-Object { $_.key })
    $startKey = Get-FocusKey $Editor
    if ($catalog -notcontains $startKey) { throw 'The visible composer was absent from the keyboard focus catalog.' }

    $Editor.SetFocus()
    Start-Sleep -Milliseconds 100
    $forward = @((Get-FocusKey ([Windows.Automation.AutomationElement]::FocusedElement)))
    for ($index = 0; $index -lt $focusable.Count; $index++) {
        [Windows.Forms.SendKeys]::SendWait('{TAB}')
        Start-Sleep -Milliseconds 80
        $forward += Get-FocusKey ([Windows.Automation.AutomationElement]::FocusedElement)
    }

    $Editor.SetFocus()
    Start-Sleep -Milliseconds 100
    $reverse = @((Get-FocusKey ([Windows.Automation.AutomationElement]::FocusedElement)))
    for ($index = 0; $index -lt $focusable.Count; $index++) {
        [Windows.Forms.SendKeys]::SendWait('+{TAB}')
        Start-Sleep -Milliseconds 80
        $reverse += Get-FocusKey ([Windows.Automation.AutomationElement]::FocusedElement)
    }

    $forwardBody = @($forward | Select-Object -First $focusable.Count)
    $reverseBody = @($reverse | Select-Object -First $focusable.Count)
    $expectedReverseBody = @($startKey) + @($forwardBody | Select-Object -Skip 1 | Sort-Object { -[array]::IndexOf($forwardBody, $_) })
    $forwardComplete = (
        $forward.Count -eq ($focusable.Count + 1) -and
        $forward[0] -eq $startKey -and
        $forward[-1] -eq $startKey -and
        (@($forwardBody | Sort-Object -Unique).Count -eq $focusable.Count) -and
        (Test-SameStringSet $forwardBody $catalog))
    $reverseComplete = (
        $reverse.Count -eq ($focusable.Count + 1) -and
        $reverse[0] -eq $startKey -and
        $reverse[-1] -eq $startKey -and
        (@($reverseBody | Sort-Object -Unique).Count -eq $focusable.Count) -and
        (Test-SameStringSet $reverseBody $catalog) -and
        ((@($reverseBody) -join "`n") -eq (@($expectedReverseBody) -join "`n")))

    return [pscustomobject][ordered]@{
        controls = @($focusable)
        uia_keyboard_focusable_controls = @($uiaFocusable)
        start_key = $startKey
        forward_order = @($forward)
        reverse_order = @($reverse)
        forward_cycle_complete = $forwardComplete
        reverse_cycle_complete = $reverseComplete
    }
}

function Count-Name($Window, [string]$Name) {
    return @((Get-Names $Window) | Where-Object { $_ -eq $Name }).Count
}

function Get-EffectSnapshot([string]$Workspace) {
    $result = [ordered]@{}
    foreach ($directoryName in @('notes', 'trash')) {
        $directory = Join-Path $Workspace $directoryName
        if (-not (Test-Path -LiteralPath $directory)) { continue }
        foreach ($file in @(Get-ChildItem -LiteralPath $directory -File -Recurse | Sort-Object FullName)) {
            $relative = $file.FullName.Substring($Workspace.Length).TrimStart('\').Replace('\', '/')
            $result[$relative] = [ordered]@{ bytes = [int64]$file.Length; sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
        }
    }
    return $result
}

function Get-WorkspaceSnapshot([string]$Workspace) {
    if (-not (Test-Path -LiteralPath $Workspace)) {
        return [pscustomobject][ordered]@{ root_exists = $false; entries = @() }
    }
    $resolved = [IO.Path]::GetFullPath($Workspace)
    $entries = @()
    $pending = New-Object 'Collections.Generic.Queue[string]'
    $pending.Enqueue($resolved)
    while ($pending.Count -gt 0) {
        $directory = $pending.Dequeue()
        foreach ($item in @(Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop)) {
            $relative = $item.FullName.Substring($resolved.Length).TrimStart('\').Replace('\', '/')
            $isReparse = (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
            if ($isReparse) {
                $entries += [pscustomobject][ordered]@{ path = $relative; kind = 'reparse_point' }
            } elseif ($item.PSIsContainer) {
                $entries += [pscustomobject][ordered]@{ path = $relative; kind = 'directory' }
                $pending.Enqueue($item.FullName)
            } else {
                $entries += [pscustomobject][ordered]@{
                    path = $relative
                    kind = 'file'
                    bytes = [int64]$item.Length
                    sha256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
                }
            }
        }
    }
    return [pscustomobject][ordered]@{ root_exists = $true; entries = @($entries | Sort-Object path) }
}

function Invoke-MalformedCoreProbe([string]$CorePath, [string]$ProbeRoot, $Case) {
    New-Item -ItemType Directory -Path $ProbeRoot -Force | Out-Null
    $probeWorkspace = Join-Path $ProbeRoot 'workspace'
    $beforeMalformed = Get-WorkspaceSnapshot $probeWorkspace
    $recoveryInvocationId = "raw-$Shell-t16-recovery"
    $recoveryRequest = [ordered]@{
        invocation_id = $recoveryInvocationId
        message = 'Hola BAXY'
        workspace = $probeWorkspace
    } | ConvertTo-Json -Compress
    $processInfo = New-Object Diagnostics.ProcessStartInfo
    $processInfo.FileName = $CorePath
    $processInfo.WorkingDirectory = $ProbeRoot
    $processInfo.UseShellExecute = $false
    $processInfo.CreateNoWindow = $true
    $processInfo.RedirectStandardInput = $true
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    if ($processInfo.PSObject.Properties.Name -contains 'StandardInputEncoding') { $processInfo.StandardInputEncoding = $utf8 }
    if ($processInfo.PSObject.Properties.Name -contains 'StandardOutputEncoding') { $processInfo.StandardOutputEncoding = $utf8 }
    if ($processInfo.PSObject.Properties.Name -contains 'StandardErrorEncoding') { $processInfo.StandardErrorEncoding = $utf8 }
    $processInfo.EnvironmentVariables['BAXY_TOURNAMENT_ROOT'] = $ProbeRoot
    $processInfo.EnvironmentVariables['BAXY_FIXED_WORKSPACE'] = $probeWorkspace

    $probe = New-Object Diagnostics.Process
    $probe.StartInfo = $processInfo
    $timedOut = $false
    $recoveryLine = $null
    $remainingStdout = ''
    $remainingStderr = ''
    $malformedStderrLine = $null
    $malformedStdoutLines = @()
    $afterMalformed = $null
    $network = $null
    try {
        if (-not $probe.Start()) { throw 'The malformed-input core probe did not start.' }
        $stderrLineTask = $probe.StandardError.ReadLineAsync()
        $firstStdoutTask = $probe.StandardOutput.ReadLineAsync()
        $probe.StandardInput.WriteLine([string]$Case.raw_input)
        $probe.StandardInput.Flush()
        if (-not $stderrLineTask.Wait(10000)) {
            $timedOut = $true
            throw 'The malformed-input core probe emitted no redacted error before timeout.'
        }
        $malformedStderrLine = $stderrLineTask.Result
        Start-Sleep -Milliseconds 100
        $afterMalformed = Get-WorkspaceSnapshot $probeWorkspace
        if ($firstStdoutTask.IsCompleted) {
            if (-not [string]::IsNullOrWhiteSpace($firstStdoutTask.Result)) { $malformedStdoutLines += $firstStdoutTask.Result }
            $recoveryTask = $probe.StandardOutput.ReadLineAsync()
        } else {
            $recoveryTask = $firstStdoutTask
        }
        $remainingStderrTask = $probe.StandardError.ReadToEndAsync()
        $probe.StandardInput.WriteLine($recoveryRequest)
        $probe.StandardInput.Flush()
        if (-not $recoveryTask.Wait(10000)) {
            $timedOut = $true
            throw 'The malformed-input core probe did not recover before timeout.'
        }
        $recoveryLine = $recoveryTask.Result
        $network = Get-NetworkSnapshot $probe.Id
        $probe.StandardInput.Close()
        $remainingTask = $probe.StandardOutput.ReadToEndAsync()
        if (-not $probe.WaitForExit(10000)) {
            $timedOut = $true
            $probe.Kill()
            $null = $probe.WaitForExit(5000)
        }
        $remainingStdout = $remainingTask.GetAwaiter().GetResult()
        $remainingStderr = $remainingStderrTask.GetAwaiter().GetResult()
    } catch {
        if (-not $probe.HasExited) {
            try { $probe.Kill() } catch { }
            try { $null = $probe.WaitForExit(5000) } catch { }
        }
        throw
    } finally {
        try { $probe.StandardInput.Dispose() } catch { }
    }

    $failures = @()
    $response = $null
    try { $response = $recoveryLine | ConvertFrom-Json } catch { $failures += 'the recovery response was not valid JSON' }
    $recoveryValid = (
        $null -ne $response -and
        $response.invocation_id -eq $recoveryInvocationId -and
        $response.state -eq 'done')
    if (-not $recoveryValid) { $failures += 'the core did not answer a valid request after malformed input' }
    $remainingStderrLines = @($remainingStderr -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $stderrRedacted = (
        $malformedStderrLine -eq 'BAXY_PROTOCOL_ERROR malformed_json' -and
        $remainingStderrLines.Count -eq 0 -and
        $malformedStderrLine -notmatch '(?i)stack|traceback| at |:\\Users\\|workspace')
    if (-not $stderrRedacted) { $failures += 'malformed-input stderr was not the exact redacted protocol error' }
    $extraStdoutLines = @($remainingStdout -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $malformedStdoutCount = $malformedStdoutLines.Count
    if ($extraStdoutLines.Count -ne 0) { $failures += 'the recovery request produced extra stdout protocol records' }
    if ($malformedStdoutCount -ne 0) { $failures += 'malformed input produced a stdout protocol record' }
    $filesystemUnchanged = (($beforeMalformed | ConvertTo-Json -Compress -Depth 8) -eq ($afterMalformed | ConvertTo-Json -Compress -Depth 8))
    if (-not $filesystemUnchanged) { $failures += 'malformed input changed the workspace before recovery was sent' }
    $networkEmpty = ($network.observer_ok -eq $true -and $network.tcp.Count -eq 0 -and $network.udp.Count -eq 0)
    if (-not $networkEmpty) { $failures += 'malformed-input core probe exposed network activity' }
    if ($timedOut -or $probe.ExitCode -ne 0) { $failures += 'malformed-input core probe did not exit cleanly' }

    $exitCode = $probe.ExitCode
    $probe.Dispose()
    return [pscustomobject][ordered]@{
        passed = ($failures.Count -eq 0)
        failures = @($failures)
        process_survived = $recoveryValid
        recovery_response_valid = $recoveryValid
        recovery_response_state = if ($null -ne $response) { [string]$response.state } else { $null }
        stderr_redacted = $stderrRedacted
        stderr_record = $malformedStderrLine
        malformed_stdout_protocol_records = $malformedStdoutCount
        filesystem_unchanged = $filesystemUnchanged
        filesystem_snapshot_scope = 'complete_workspace_before_recovery'
        workspace_before_malformed = $beforeMalformed
        workspace_after_malformed_before_recovery = $afterMalformed
        exit_code = $exitCode
        timed_out = $timedOut
        network_snapshot = $network
    }
}

function Count-Completed([string]$JournalPath, [string]$InvocationId) {
    if (-not (Test-Path -LiteralPath $JournalPath)) { return 0 }
    $count = 0
    foreach ($line in [IO.File]::ReadAllLines($JournalPath, [Text.Encoding]::UTF8)) {
        try {
            $record = $line | ConvertFrom-Json
            if ($record.invocation_id -eq $InvocationId -and $record.status -eq 'completed') { $count++ }
        } catch { }
    }
    return $count
}

function Invoke-Mission($Window, $Editor, $InvocationEditor, $SendButton, [string]$Message, [string]$InvocationId, [bool]$UseKeyboard) {
    $beforeCount = Count-Name $Window $Message
    $beforeNamedCount = @(Get-Names $Window).Count
    $InvocationEditor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($InvocationId)
    $Editor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($Message)
    if ($UseKeyboard) {
        $Editor.SetFocus()
        [Windows.Forms.SendKeys]::SendWait('{ENTER}')
    } else {
        $SendButton.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do {
        Start-Sleep -Milliseconds 50
        $afterCount = Count-Name $Window $Message
        $afterNamedCount = @(Get-Names $Window).Count
        $enabled = $SendButton.Current.IsEnabled
    } until ((($afterCount -gt $beforeCount -or $afterNamedCount -gt $beforeNamedCount) -and $enabled) -or [DateTime]::UtcNow -ge $deadline)
    Start-Sleep -Milliseconds 100
    return [pscustomobject][ordered]@{
        completed = (($afterCount -gt $beforeCount -or $afterNamedCount -gt $beforeNamedCount) -and $enabled)
        names = @(Get-Names $Window)
    }
}

function Test-CaseResult($Case, [string[]]$Names, [string]$Workspace, $BeforeEffects, $ExternalBefore, $ExternalAfter) {
    $failures = @()
    $expected = $Case.expected
    $stateName = if ($expected.state -eq 'done') { 'VERIFICADO' } elseif ($expected.state -eq 'blocked') { 'BLOQUEADO' } else { 'FALLO' }
    if ($Names -notcontains $stateName) { $failures += "visible state was not $stateName" }
    if ($Names -contains 'schema_version' -or $Names -contains '{') { $failures += 'raw protocol became visible' }
    if ($expected.PSObject.Properties.Name -contains 'response_contains') {
        $found = @($Names | Where-Object { $_.IndexOf([string]$expected.response_contains, [StringComparison]::OrdinalIgnoreCase) -ge 0 }).Count -gt 0
        if (-not $found) { $failures += 'expected natural response fragment was not visible' }
    }
    if ($expected.PSObject.Properties.Name -contains 'file') {
        $path = Join-Path $Workspace ([string]$expected.file).Replace('/', '\')
        if (-not (Test-Path -LiteralPath $path)) { $failures += "expected file is missing: $($expected.file)" }
        elseif ([IO.File]::ReadAllText($path, [Text.Encoding]::UTF8) -ne [string]$expected.content) { $failures += "content mismatch: $($expected.file)" }
    }
    if ($expected.PSObject.Properties.Name -contains 'present') {
        $path = Join-Path $Workspace ([string]$expected.present).Replace('/', '\')
        if (-not (Test-Path -LiteralPath $path)) { $failures += "expected path is missing: $($expected.present)" }
    }
    if ($expected.PSObject.Properties.Name -contains 'absent') {
        $path = Join-Path $Workspace ([string]$expected.absent).Replace('/', '\')
        if (Test-Path -LiteralPath $path) { $failures += "path should be absent: $($expected.absent)" }
    }
    if ($expected.PSObject.Properties.Name -contains 'filesystem_changes' -and [int]$expected.filesystem_changes -eq 0) {
        $afterEffects = Get-EffectSnapshot $Workspace
        if (($BeforeEffects | ConvertTo-Json -Compress -Depth 5) -ne ($afterEffects | ConvertTo-Json -Compress -Depth 5)) { $failures += 'unexpected note or trash change' }
    }
    if ($null -ne $ExternalBefore -and (($ExternalBefore | ConvertTo-Json -Compress) -ne ($ExternalAfter | ConvertTo-Json -Compress))) {
        $failures += 'external target changed'
    }
    return @($failures)
}

if (-not (Test-Path -LiteralPath $definition.App)) { throw "Shell binary is missing: $($definition.App)" }
if (-not (Test-Path -LiteralPath $definition.Core)) { throw "Core binary is missing: $($definition.Core)" }

$cases = ([IO.File]::ReadAllText($script:CasesPath, [Text.Encoding]::UTF8) | ConvertFrom-Json).cases
$runRoot = Join-Path $script:WorkRoot $Shell
Reset-OwnedDirectory $runRoot
$dataRoot = Join-Path $runRoot 'data'
New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
$workspace = Join-Path $dataRoot 'workspace'

$env:BAXY_ROUND_B_CORE = $definition.Core
$env:BAXY_ROUND_B_DATA = $dataRoot
$env:BAXY_ROUND_B_AUTOMATION = '1'

$startedUtc = [DateTime]::UtcNow
$startedTicks = [Diagnostics.Stopwatch]::GetTimestamp()
[BaxyRoundBLiveCounter]::Count = 0
[BaxyRoundBLiveCounter]::LastName = ''
$process = Start-Process -FilePath $definition.App -PassThru
$ownedPids = @()
$result = $null
$window = $null
$liveHandler = [BaxyRoundBLiveCounter]::Handler
try {
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    $window = Find-BaxyWindow $process.Id $deadline
    if ($null -eq $window) { throw 'The shell did not expose a BAXY window.' }
    $editor = Find-Control $window 'Mensaje para BAXY' ([Windows.Automation.ControlType]::Edit) $deadline
    $invocationEditor = Find-Control $window 'ID de invoc*' ([Windows.Automation.ControlType]::Edit) $deadline
    $sendButton = Find-Control $window 'Enviar mensaje' ([Windows.Automation.ControlType]::Button) $deadline
    if ($null -eq $editor -or $null -eq $invocationEditor -or $null -eq $sendButton) { throw 'Required accessible controls were not exposed.' }
    $coreReady = Find-Control $window 'CORE LISTO' ([Windows.Automation.ControlType]::Text) $deadline
    if ($null -eq $coreReady -or -not $editor.Current.IsEnabled -or -not $sendButton.Current.IsEnabled) { throw 'The local core did not complete its startup attestation.' }
    $readyTicks = [Diagnostics.Stopwatch]::GetTimestamp()
    [Windows.Automation.Automation]::AddAutomationEventHandler(
        [Windows.Automation.AutomationElementIdentifiers]::LiveRegionChangedEvent,
        $window,
        [Windows.Automation.TreeScope]::Subtree,
        $liveHandler)

    $initialNames = @(Get-Names $window)
    $liveRegions = @()
    foreach ($node in $window.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)) {
        try {
            $live = $node.GetCurrentPropertyValue([Windows.Automation.AutomationElementIdentifiers]::LiveSettingProperty)
            if ([int]$live -ne 0) { $liveRegions += [ordered]@{ name = $node.Current.Name; setting = [string]$live } }
        } catch { }
    }
    $keyboardFocus = Get-KeyboardFocusEvidence $window $editor
    $tabTarget = ($keyboardFocus.controls | Where-Object { $_.key -eq $keyboardFocus.forward_order[1] } | Select-Object -First 1).name
    $shiftTabTarget = ($keyboardFocus.controls | Where-Object { $_.key -eq $keyboardFocus.reverse_order[1] } | Select-Object -First 1).name
    if (-not $keyboardFocus.forward_cycle_complete -or -not $keyboardFocus.reverse_cycle_complete) {
        $keyboardFocus | ConvertTo-Json -Depth 6 -Compress | Write-Output
        throw 'The complete forward/reverse keyboard focus cycle was not deterministic.'
    }

    $idleMemory = Get-TreeMemory $process.Id
    $memorySamples = @($idleMemory)
    $idleGpuMemory = Get-TreeGpuMemory $process.Id
    $gpuMemorySamples = @($idleGpuMemory)
    $networkSamples = @(Get-NetworkSnapshot $process.Id)
    $caseResults = @()
    foreach ($case in $cases) {
        if ($case.id -eq 'T16_MALFORMED_REQUEST') {
            $transportProbe = Invoke-MalformedCoreProbe $definition.Core (Join-Path $runRoot 'malformed_probe') $case
            $caseResults += [pscustomobject][ordered]@{
                case_id = $case.id
                weight = $case.weight
                passed = $transportProbe.passed
                route = 'raw_core_transport_probe'
                failures = @($transportProbe.failures)
                visible_state = @()
                transport_evidence = $transportProbe
            }
            $networkSamples += Get-NetworkSnapshot $process.Id
            continue
        }

        $beforeEffects = Get-EffectSnapshot $workspace
        $externalPath = $null
        if ($case.id -eq 'T09_BLOCK_TRAVERSAL') { $externalPath = Join-Path $dataRoot 'escape.txt' }
        if ($case.id -eq 'T10_BLOCK_ABSOLUTE_PATH') { $externalPath = 'C:\Windows\Temp\baxy-escape.txt' }
        $externalBefore = if ($null -ne $externalPath) { [ordered]@{ exists = [bool](Test-Path -LiteralPath $externalPath); hash = if (Test-Path -LiteralPath $externalPath -PathType Leaf) { (Get-FileHash -LiteralPath $externalPath -Algorithm SHA256).Hash } else { $null } } } else { $null }

        if (($case.PSObject.Properties.Name -contains 'setup') -and $case.setup -eq 'append_partial_json_to_journal_after_T14') {
            $journal = Join-Path $workspace 'journal.jsonl'
            $stream = New-Object IO.FileStream($journal, [IO.FileMode]::Append, [IO.FileAccess]::Write, [IO.FileShare]::Read)
            try { $bytes = [Text.Encoding]::UTF8.GetBytes('{"partial":'); $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
        }

        $invocationId = "ui-$Shell-$($case.id.ToLowerInvariant())"
        $invocation = $null
        $failures = @()
        $route = 'visible_composer'
        if ($case.id -eq 'T11_BLOCK_NUL' -and $Shell -notlike 'dotnet-wpf*') {
            $invocationEditor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($invocationId)
            $editor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue([string]$case.message)
            $accepted = $editor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).Current.Value
            $afterEffects = Get-EffectSnapshot $workspace
            $prevented = [string]::IsNullOrEmpty($accepted) -and (($beforeEffects | ConvertTo-Json -Compress -Depth 5) -eq ($afterEffects | ConvertTo-Json -Compress -Depth 5))
            if (-not $prevented) { $failures += 'the HTML input did not prevent a NUL mission' }
            $route = 'prevented_by_html_text_control_and_covered_by_round_a_transport'
            $invocation = [ordered]@{ completed = $prevented; names = @(Get-Names $window) }
        } else {
            $invocation = Invoke-Mission $window $editor $invocationEditor $sendButton ([string]$case.message) $invocationId ($case.id -eq 'T01_CONVERSATION')
            if (-not $invocation.completed) { $failures += 'UI mission did not complete before timeout' }
            $externalAfter = if ($null -ne $externalPath) { [ordered]@{ exists = [bool](Test-Path -LiteralPath $externalPath); hash = if (Test-Path -LiteralPath $externalPath -PathType Leaf) { (Get-FileHash -LiteralPath $externalPath -Algorithm SHA256).Hash } else { $null } } } else { $null }
            $failures += @(Test-CaseResult $case @($invocation.names) $workspace $beforeEffects $externalBefore $externalAfter)
            if (($case.PSObject.Properties.Name -contains 'repeat_same_invocation_id') -and $case.repeat_same_invocation_id -eq $true) {
                $replay = Invoke-Mission $window $editor $invocationEditor $sendButton ([string]$case.message) $invocationId $false
                if (-not $replay.completed) { $failures += 'replay did not complete before timeout' }
                if (@($replay.names | Where-Object { $_ -eq 'Resultado recuperado sin repetir el efecto.' }).Count -eq 0) { $failures += 'replay detail was not visible' }
                if ((Count-Completed (Join-Path $workspace 'journal.jsonl') $invocationId) -ne 1) { $failures += 'replay created more than one completed journal record' }
            }
            if ($case.id -eq 'T15_TRUNCATED_JOURNAL_RECOVERY' -and @(Get-ChildItem -LiteralPath $workspace -Filter 'journal.corrupt.*.jsonl' -File).Count -eq 0) {
                $failures += 'truncated journal tail was not quarantined'
            }
        }
        $memorySamples += Get-TreeMemory $process.Id
        $gpuMemorySamples += Get-TreeGpuMemory $process.Id
        $networkSamples += Get-NetworkSnapshot $process.Id
        $caseResults += [pscustomobject][ordered]@{
            case_id = $case.id
            weight = $case.weight
            passed = ($failures.Count -eq 0)
            route = $route
            failures = @($failures)
            visible_state = @($invocation.names | Where-Object { $_ -in @('VERIFICADO', 'BLOQUEADO', 'FALLO') } | Select-Object -Last 1)
        }
    }

    $networkSamples += Get-NetworkSnapshot $process.Id
    $network = [ordered]@{
        observer = 'Get-NetTCPConnection+Get-NetUDPEndpoint'
        observer_ok = (@($networkSamples | Where-Object { $_.observer_ok -ne $true }).Count -eq 0)
        tcp = @($networkSamples | ForEach-Object { @($_.tcp) })
        udp = @($networkSamples | ForEach-Object { @($_.udp) })
        samples = @($networkSamples)
        sampling_note = 'Discrete snapshots at idle, after every UI case, and before shutdown; not a continuous ETW trace.'
    }
    $ownedPids = @(Get-TreeIds $process.Id)
    $maxPrivate = [int64](($memorySamples | Measure-Object private_bytes -Maximum).Maximum)
    $maxWorking = [int64](($memorySamples | Measure-Object working_set_bytes -Maximum).Maximum)
    $maxDedicatedGpu = [int64](($gpuMemorySamples | Measure-Object dedicated_bytes -Maximum).Maximum)
    $maxSharedGpu = [int64](($gpuMemorySamples | Measure-Object shared_bytes -Maximum).Maximum)
    $passedWeight = [double](($caseResults | Where-Object passed | Measure-Object weight -Sum).Sum)
    $totalWeight = [double](($caseResults | Measure-Object weight -Sum).Sum)
    $result = [ordered]@{
        schema_version = 1
        protocol_id = 'baxy-technology-tournament-v1'
        round = 'b_integrated_system'
        shell_id = $Shell
        display_name = $definition.DisplayName
        started_utc = $startedUtc.ToString('o')
        finished_utc = [DateTime]::UtcNow.ToString('o')
        ready_ms = (($readyTicks - $startedTicks) * 1000.0 / [Diagnostics.Stopwatch]::Frequency)
        command = @($definition.App)
        environment = [ordered]@{ BAXY_ROUND_B_CORE = $definition.Core; BAXY_ROUND_B_DATA = $dataRoot; BAXY_ROUND_B_AUTOMATION = '1' }
        provenance = [ordered]@{
            harness = Get-ProvenanceRecord $script:HarnessPath
            protocol = Get-ProvenanceRecord $script:ProtocolPath
            cases = Get-ProvenanceRecord $script:CasesPath
        }
        hashes = [ordered]@{
            shell_bundle_sha256 = Get-BundleHash $definition.Bundle
            shell_entrypoint_sha256 = (Get-FileHash -LiteralPath $definition.App -Algorithm SHA256).Hash.ToLowerInvariant()
            core_sha256 = (Get-FileHash -LiteralPath $definition.Core -Algorithm SHA256).Hash.ToLowerInvariant()
            source_tree_sha256 = Get-SourceHash $definition.Source
        }
        shell_bundle_scope = [ordered]@{
            kind = if ($Shell -like 'dotnet-wpf*') { 'explicit_fdd_runtime_files_loaded_by_the_measured_shell' } else { 'candidate_runtime_bundle' }
            files = if ($Shell -like 'dotnet-wpf*') { @($definition.Bundle | ForEach-Object { Get-ProvenanceRecord $_ }) } elseif (Test-Path -LiteralPath $definition.Bundle -PathType Leaf) { @(Get-ProvenanceRecord $definition.Bundle) } else { @() }
        }
        shell_bundle_bytes = Get-BundleBytes $definition.Bundle
        core_bytes = [int64](Get-Item -LiteralPath $definition.Core).Length
        bundle_bytes = (Get-BundleBytes $definition.Bundle) + [int64](Get-Item -LiteralPath $definition.Core).Length
        accessibility = [ordered]@{
            named_nodes = $initialNames.Count
            core_ready_visible = ($initialNames -contains 'CORE LISTO')
            technical_runtime_hidden = ($initialNames -notcontains '.NET WPF nativo' -and $initialNames -notcontains '.NET NativeAOT' -and $initialNames -notcontains 'Rust nativo')
            composer_named = ($null -ne $editor)
            send_named = ($null -ne $sendButton)
            live_regions = @($liveRegions)
            live_region_events = [BaxyRoundBLiveCounter]::Count
            last_live_region_name = [BaxyRoundBLiveCounter]::LastName
            tab_target = $tabTarget
            shift_tab_target = $shiftTabTarget
            focusable_controls = @($keyboardFocus.controls)
            focus_start_key = $keyboardFocus.start_key
            forward_focus_order = @($keyboardFocus.forward_order)
            reverse_focus_order = @($keyboardFocus.reverse_order)
            forward_focus_cycle_complete = $keyboardFocus.forward_cycle_complete
            reverse_focus_cycle_complete = $keyboardFocus.reverse_cycle_complete
            keyboard_submit_case = 'T01_CONVERSATION'
            raw_protocol_hidden = (@(Get-Names $window) -notcontains 'schema_version')
        }
        resources = [ordered]@{
            idle = $idleMemory
            max_sampled_private_bytes = $maxPrivate
            max_sampled_working_set_bytes = $maxWorking
            gpu = [ordered]@{
                idle = $idleGpuMemory
                max_sampled_dedicated_bytes = $maxDedicatedGpu
                max_sampled_shared_bytes = $maxSharedGpu
            }
            network_snapshot = $network
        }
        functional = [ordered]@{
            passed_weight = $passedWeight
            total_weight = $totalWeight
            pass_ratio = if ($totalWeight -gt 0) { $passedWeight / $totalWeight } else { 0 }
            cases = @($caseResults)
        }
        owned_process_ids_before_close = @($ownedPids)
    }
} finally {
    if ($null -ne $window) {
        try {
            [Windows.Automation.Automation]::RemoveAutomationEventHandler(
                [Windows.Automation.AutomationElementIdentifiers]::LiveRegionChangedEvent,
                $window,
                $liveHandler)
        } catch { }
    }
    if ($null -ne $process -and -not $process.HasExited) {
        $null = $process.CloseMainWindow()
        if (-not $process.WaitForExit(5000)) { Stop-Process -Id $process.Id -Force }
    }
    Start-Sleep -Milliseconds 500
    $orphans = @($ownedPids | Where-Object { $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue) })
    if ($null -ne $result) {
        $result['cleanup'] = [ordered]@{ orphan_process_ids = $orphans; passed = ($orphans.Count -eq 0) }
    }
    Remove-Item Env:BAXY_ROUND_B_AUTOMATION -ErrorAction SilentlyContinue
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $script:ArtifactRoot "raw\round_b_$($Shell.Replace('-', '_')).json"
}
$outputDirectory = Split-Path -Parent ([IO.Path]::GetFullPath($OutputPath))
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
$resolvedOutput = [IO.Path]::GetFullPath($OutputPath)
$temporaryOutput = "$resolvedOutput.$PID.tmp"
$json = $result | ConvertTo-Json -Depth 14
[IO.File]::WriteAllText($temporaryOutput, $json, $utf8)
Move-Item -LiteralPath $temporaryOutput -Destination $resolvedOutput -Force
$summary = [ordered]@{
    shell = $Shell
    passed_weight = $result.functional.passed_weight
    total_weight = $result.functional.total_weight
    pass_ratio = $result.functional.pass_ratio
    no_network = ($result.resources.network_snapshot.observer_ok -eq $true -and $result.resources.network_snapshot.tcp.Count -eq 0 -and $result.resources.network_snapshot.udp.Count -eq 0)
    cleanup = $result.cleanup.passed
    output = [IO.Path]::GetFullPath($OutputPath)
}
$summary | ConvertTo-Json -Compress
if ($summary.passed_weight -ne $summary.total_weight -or -not $summary.no_network -or -not $summary.cleanup) {
    throw "Round B functional hard gate failed for $Shell"
}
