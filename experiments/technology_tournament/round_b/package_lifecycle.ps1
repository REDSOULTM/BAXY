param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('dotnet-wpf', 'dotnet-wpf-rust')]
    [string]$System,
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$artifactRoot = Join-Path $root 'artifacts\technology_tournament'
$rawRoot = Join-Path $artifactRoot 'raw'
$ownedRoot = Join-Path $artifactRoot "work\round_b_package\$System"
$shellRoot = Join-Path $artifactRoot 'build\round_b\wpf_sc_shell'
$shellName = 'baxy-dotnet-wpf-slice.exe'
$shell = Join-Path $shellRoot $shellName
$core = if ($System -eq 'dotnet-wpf-rust') {
    Join-Path $artifactRoot 'build\packaging\rust_native\baxy-rust-slice.exe'
} else {
    Join-Path $artifactRoot 'build\packaging\dotnet_native_aot\baxy-dotnet-slice.exe'
}
$packagesRoot = Join-Path $ownedRoot 'packages'
$installRoot = Join-Path $ownedRoot 'installed'
$dataRoot = Join-Path $ownedRoot 'user-data'
$casesPath = Join-Path $root 'experiments\technology_tournament\cases.json'
$protocolPath = Join-Path $artifactRoot 'protocol.json'
$buildRecipePath = Join-Path $PSScriptRoot 'build_round_b.ps1'
$utf8 = New-Object Text.UTF8Encoding($false)
$semverPattern = '^\d+\.\d+\.\d+$'

function Assert-Contained([string]$Path, [string]$AllowedRoot, [bool]$AllowRoot) {
    $resolved = [IO.Path]::GetFullPath($Path)
    $allowed = [IO.Path]::GetFullPath($AllowedRoot)
    $inside = $resolved.StartsWith($allowed + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
    if (-not $inside -and -not ($AllowRoot -and $resolved -eq $allowed)) {
        throw "Path is outside the allowed root: $resolved"
    }
    return $resolved
}

function Assert-Owned([string]$Path) {
    return Assert-Contained $Path $ownedRoot $true
}

function Assert-NoReparseTree([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $resolved)) { return }
    $pending = New-Object 'Collections.Generic.Queue[string]'
    $pending.Enqueue($resolved)
    while ($pending.Count -gt 0) {
        $current = $pending.Dequeue()
        $item = Get-Item -LiteralPath $current -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Reparse point is forbidden in package harness trees: $current"
        }
        if ($item.PSIsContainer) {
            foreach ($child in @(Get-ChildItem -LiteralPath $current -Force)) {
                if (($child.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                    throw "Reparse point is forbidden in package harness trees: $($child.FullName)"
                }
                if ($child.PSIsContainer) { $pending.Enqueue($child.FullName) }
            }
        }
    }
}

function Remove-Owned([string]$Path) {
    $resolved = Assert-Owned $Path
    if (Test-Path -LiteralPath $resolved) {
        Assert-NoReparseTree $resolved
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

function Get-TreeHash([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        foreach ($file in @(Get-ChildItem -LiteralPath $resolved -File -Recurse -Force | Sort-Object FullName)) {
            $relative = $file.FullName.Substring($resolved.Length).TrimStart('\').Replace('\', '/')
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
    $resolved = Assert-Contained $Path $root $false
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) { throw "Provenance input is missing: $resolved" }
    $relative = $resolved.Substring($root.Length).TrimStart('\').Replace('\', '/')
    $item = Get-Item -LiteralPath $resolved -Force
    return [ordered]@{
        path = $relative
        bytes = [int64]$item.Length
        sha256 = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

function New-Package([string]$Version) {
    if ($Version -notmatch $semverPattern) { throw "Invalid package version: $Version" }
    $package = Join-Path $packagesRoot $Version
    Remove-Owned $package
    New-Item -ItemType Directory -Path (Join-Path $package 'core') -Force | Out-Null
    foreach ($entry in @(Get-ChildItem -LiteralPath $shellRoot -Force)) {
        if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Shell bundle contains a reparse point: $($entry.FullName)" }
        Copy-Item -LiteralPath $entry.FullName -Destination $package -Recurse
    }
    Copy-Item -LiteralPath $core -Destination (Join-Path $package 'core\baxy-core.exe')
    $runtimeKind = if ($System -eq 'dotnet-wpf-rust') { 'rust' } else { 'dotnet' }
    [IO.File]::WriteAllText((Join-Path $package 'core\runtime.txt'), $runtimeKind, $utf8)
    [IO.File]::WriteAllText((Join-Path $package 'version.txt'), $Version, $utf8)
    [IO.File]::WriteAllText((Join-Path $package 'release-marker.txt'), "BAXY tournament payload $Version", $utf8)
    $files = @()
    foreach ($file in @(Get-ChildItem -LiteralPath $package -File -Recurse -Force | Sort-Object FullName)) {
        $relative = $file.FullName.Substring($package.Length).TrimStart('\').Replace('\', '/')
        $files += [ordered]@{
            path = $relative
            bytes = [int64]$file.Length
            sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $manifest = [ordered]@{
        schema_version = 1
        product = 'BAXY'
        version = $Version
        system = $System
        authenticity = 'not_provided'
        files = $files
    }
    [IO.File]::WriteAllText((Join-Path $package 'manifest.json'), ($manifest | ConvertTo-Json -Depth 6), $utf8)
    return $package
}

function Get-PackageValidation([string]$Package) {
    $failures = @()
    try {
        $resolved = Assert-Owned $Package
        if (-not (Test-Path -LiteralPath $resolved -PathType Container)) { throw 'package directory is missing' }
        Assert-NoReparseTree $resolved
        $manifestPath = Join-Path $resolved 'manifest.json'
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'root manifest.json is missing' }
        foreach ($packageFile in @(Get-ChildItem -LiteralPath $resolved -File -Recurse -Force)) {
            $relativeStreamPath = $packageFile.FullName.Substring($resolved.Length).TrimStart('\')
            $streams = @(Get-Item -LiteralPath $packageFile.FullName -Stream * -ErrorAction Stop)
            if (@($streams | Where-Object { $_.Stream -eq ':$DATA' }).Count -ne 1) {
                $failures += "default data stream could not be attested: $relativeStreamPath"
            }
            foreach ($alternateStream in @($streams | Where-Object { $_.Stream -ne ':$DATA' })) {
                $failures += "alternate data stream forbidden: $relativeStreamPath [$($alternateStream.Stream)]"
            }
        }
        $manifest = [IO.File]::ReadAllText($manifestPath, [Text.Encoding]::UTF8) | ConvertFrom-Json
        if ($manifest.schema_version -ne 1) { $failures += 'unsupported schema_version' }
        if ($manifest.product -ne 'BAXY') { $failures += 'unexpected product' }
        if ($manifest.system -ne $System) { $failures += 'unexpected system' }
        if (([string]$manifest.version) -notmatch $semverPattern) { $failures += 'invalid semantic version' }
        if ($manifest.authenticity -ne 'not_provided') { $failures += 'unexpected authenticity claim' }
        $expected = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        foreach ($record in @($manifest.files)) {
            $relativeSlash = [string]$record.path
            $unsafePath = [string]::IsNullOrWhiteSpace($relativeSlash) -or $relativeSlash.StartsWith('/') -or $relativeSlash.Contains('\') -or $relativeSlash.Contains(':') -or @($relativeSlash.Split('/') | Where-Object { $_ -eq '.' -or $_ -eq '..' }).Count -gt 0
            if ($unsafePath) {
                $failures += "unsafe manifest path: $relativeSlash"
                continue
            }
            if (([string]$record.sha256) -notmatch '^[0-9a-f]{64}$') { $failures += "invalid hash: $relativeSlash"; continue }
            if ([int64]$record.bytes -lt 0) { $failures += "invalid size: $relativeSlash"; continue }
            $relative = $relativeSlash.Replace('/', '\')
            if (-not $expected.Add($relative)) { $failures += "duplicate path: $relativeSlash"; continue }
            $path = [IO.Path]::GetFullPath((Join-Path $resolved $relative))
            if (-not $path.StartsWith($resolved + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { $failures += "escaped path: $relativeSlash"; continue }
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { $failures += "missing file: $relativeSlash"; continue }
            $item = Get-Item -LiteralPath $path -Force
            if ($item.Length -ne [int64]$record.bytes) { $failures += "size mismatch: $relativeSlash"; continue }
            if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne [string]$record.sha256) { $failures += "hash mismatch: $relativeSlash" }
        }
        $actual = @(Get-ChildItem -LiteralPath $resolved -File -Recurse -Force | Where-Object { $_.FullName -ne $manifestPath })
        foreach ($file in $actual) {
            $relative = $file.FullName.Substring($resolved.Length).TrimStart('\')
            if (-not $expected.Contains($relative)) { $failures += "unexpected file: $relative" }
        }
        if ($actual.Count -ne $expected.Count) { $failures += 'manifest file count mismatch' }
    } catch {
        $failures += $_.Exception.Message
    }
    return [pscustomobject][ordered]@{ passed = ($failures.Count -eq 0); failures = @($failures) }
}

function Test-Package([string]$Package) {
    return [bool](Get-PackageValidation $Package).passed
}

function Write-DurableText([string]$Path, [string]$Text) {
    $stream = New-Object IO.FileStream($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = $utf8.GetBytes($Text)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
}

function Set-Current([string]$Version) {
    if ($Version -notmatch $semverPattern) { throw "Invalid current version: $Version" }
    $versionRoot = Assert-Owned (Join-Path $installRoot "versions\$Version")
    if (-not (Test-Package $versionRoot)) { throw "Installed version failed verification: $Version" }
    $current = Assert-Owned (Join-Path $installRoot 'current.txt')
    $temporary = Assert-Owned (Join-Path $installRoot ("current.{0}.tmp" -f [Guid]::NewGuid().ToString('N')))
    Write-DurableText $temporary $Version
    if (Test-Path -LiteralPath $current) {
        $backup = Assert-Owned (Join-Path $installRoot 'current.previous')
        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
        [IO.File]::Replace($temporary, $current, $backup, $true)
    } else {
        [IO.File]::Move($temporary, $current)
    }
}

function Install-Version([string]$Package) {
    $validation = Get-PackageValidation $Package
    if (-not $validation.passed) { throw "Package verification failed before install: $($validation.failures -join '; ')" }
    $manifest = [IO.File]::ReadAllText((Join-Path $Package 'manifest.json'), [Text.Encoding]::UTF8) | ConvertFrom-Json
    $version = [string]$manifest.version
    if ($version -notmatch $semverPattern) { throw "Invalid package version: $version" }
    $versionsRoot = Assert-Owned (Join-Path $installRoot 'versions')
    New-Item -ItemType Directory -Path $versionsRoot -Force | Out-Null
    $destination = Assert-Owned (Join-Path $versionsRoot $version)
    if (Test-Path -LiteralPath $destination) { throw "Installed versions are immutable: $version" }
    $stagingRoot = Assert-Owned (Join-Path $installRoot 'staging')
    New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null
    $staging = Assert-Owned (Join-Path $stagingRoot ([Guid]::NewGuid().ToString('N')))
    New-Item -ItemType Directory -Path $staging -Force | Out-Null
    try {
        Copy-Item -Path (Join-Path $Package '*') -Destination $staging -Recurse -Force
        $postCopy = Get-PackageValidation $staging
        if (-not $postCopy.passed) { throw "Installed package failed staged verification: $($postCopy.failures -join '; ')" }
        [IO.Directory]::Move($staging, $destination)
        Set-Current $version
    } finally {
        if (Test-Path -LiteralPath $staging) { Remove-Owned $staging }
    }
}

function Get-CurrentVersion {
    $current = Assert-Owned (Join-Path $installRoot 'current.txt')
    if (-not (Test-Path -LiteralPath $current -PathType Leaf)) { return $null }
    $version = [IO.File]::ReadAllText($current, [Text.Encoding]::UTF8).Trim()
    if ($version -notmatch $semverPattern) { throw "Invalid current pointer: $version" }
    return $version
}

function Restore-Previous {
    $previousPath = Assert-Owned (Join-Path $installRoot 'current.previous')
    if (-not (Test-Path -LiteralPath $previousPath -PathType Leaf)) { throw 'No previous version pointer is available.' }
    $previous = [IO.File]::ReadAllText($previousPath, [Text.Encoding]::UTF8).Trim()
    if ($previous -notmatch $semverPattern) { throw "Invalid previous pointer: $previous" }
    Set-Current $previous
    return $previous
}

function Find-Control($Window, [string]$NamePattern, $ControlType, [DateTime]$Deadline) {
    do {
        foreach ($node in $Window.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)) {
            if ($node.Current.Name -like $NamePattern -and $node.Current.ControlType -eq $ControlType) { return $node }
        }
        Start-Sleep -Milliseconds 50
    } until ([DateTime]::UtcNow -ge $Deadline)
    return $null
}

function Get-Names($Window) {
    $names = @()
    foreach ($node in $Window.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)) {
        if (-not [string]::IsNullOrWhiteSpace($node.Current.Name)) { $names += $node.Current.Name }
    }
    return @($names)
}

function Get-TreeIds([int]$RootProcessId) {
    $rootProcess = Get-Process -Id $RootProcessId -ErrorAction Stop
    $rootStarted = $rootProcess.StartTime.AddSeconds(-1)
    $processes = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId)
    $seen = New-Object 'Collections.Generic.HashSet[int]'
    $pending = New-Object 'Collections.Generic.Queue[int]'
    $pending.Enqueue($RootProcessId)
    $result = @()
    while ($pending.Count -gt 0) {
        $current = $pending.Dequeue()
        if (-not $seen.Add($current)) { continue }
        $result += $current
        foreach ($child in @($processes | Where-Object { $_.ParentProcessId -eq $current })) {
            $live = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
            if ($null -ne $live -and $live.StartTime -ge $rootStarted) { $pending.Enqueue([int]$child.ProcessId) }
        }
    }
    return @($result)
}

function Get-NetworkSnapshot([int]$RootProcessId) {
    $ids = @(Get-TreeIds $RootProcessId)
    $tcp = @(Get-NetTCPConnection -ErrorAction Stop)
    $udp = @(Get-NetUDPEndpoint -ErrorAction Stop)
    return [ordered]@{
        observer = 'Get-NetTCPConnection+Get-NetUDPEndpoint'
        observer_ok = $true
        tcp = @($tcp | Where-Object { $ids -contains $_.OwningProcess } | Select-Object State, LocalAddress, LocalPort, RemoteAddress, RemotePort, OwningProcess)
        udp = @($udp | Where-Object { $ids -contains $_.OwningProcess } | Select-Object LocalAddress, LocalPort, OwningProcess)
    }
}

function Count-Completed([string]$JournalPath, [string]$InvocationId) {
    if (-not (Test-Path -LiteralPath $JournalPath -PathType Leaf)) { return 0 }
    $count = 0
    foreach ($line in [IO.File]::ReadAllLines($JournalPath, [Text.Encoding]::UTF8)) {
        try {
            $record = $line | ConvertFrom-Json
            if ($record.status -eq 'completed' -and $record.invocation_id -eq $InvocationId) { $count++ }
        } catch { }
    }
    return $count
}

function Start-Current {
    $evidence = [ordered]@{
        passed = $false
        version = $null
        core_attested = $false
        mission_verified = $false
        effect_verified = $false
        journal_completed_records = 0
        replay_visible = $false
        replay_single_effect = $false
        network_snapshots = @()
        network_observer_ok = $false
        graceful_shutdown = $false
        orphan_process_ids = @()
        bundle_cache_bytes = 0
        errors = @()
    }
    $process = $null
    $ownedIds = @()
    try {
        $version = Get-CurrentVersion
        if ([string]::IsNullOrWhiteSpace($version)) { throw 'No current version is installed.' }
        $versionRoot = Assert-Owned (Join-Path $installRoot "versions\$version")
        $validation = Get-PackageValidation $versionRoot
        if (-not $validation.passed) { throw "Current version failed launch verification: $($validation.failures -join '; ')" }
        $executable = Assert-Owned (Join-Path $versionRoot $shellName)
        if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) { throw 'Packaged shell entrypoint is missing.' }
        $cacheRoot = Assert-Owned (Join-Path $installRoot 'bundle-cache')
        $start = New-Object Diagnostics.ProcessStartInfo
        $start.FileName = $executable
        $start.WorkingDirectory = $versionRoot
        $start.UseShellExecute = $false
        $start.EnvironmentVariables.Remove('BAXY_ROUND_B_CORE')
        $start.EnvironmentVariables['BAXY_ROUND_B_AUTOMATION'] = '1'
        $start.EnvironmentVariables['BAXY_ROUND_B_DATA'] = $dataRoot
        $start.EnvironmentVariables['DOTNET_ROOT'] = 'C:\baxy-runtime-intentionally-absent'
        $start.EnvironmentVariables['DOTNET_MULTILEVEL_LOOKUP'] = '0'
        $start.EnvironmentVariables['DOTNET_BUNDLE_EXTRACT_BASE_DIR'] = $cacheRoot
        $process = [Diagnostics.Process]::Start($start)
        if ($null -eq $process) { throw 'Packaged shell process did not start.' }
        $evidence.version = $version
        $deadline = [DateTime]::UtcNow.AddSeconds(25)
        $window = $null
        do {
            $process.Refresh()
            if ($process.HasExited) { throw "Packaged shell exited early with code $($process.ExitCode)." }
            foreach ($candidate in [Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children, [Windows.Automation.Condition]::TrueCondition)) {
                if ($candidate.Current.ProcessId -ne $process.Id -or $candidate.Current.Name -notlike 'BAXY*') { continue }
                $composer = $candidate.FindFirst(
                    [Windows.Automation.TreeScope]::Descendants,
                    ([Windows.Automation.PropertyCondition]::new(
                        [Windows.Automation.AutomationElement]::AutomationIdProperty,
                        'MessageInput')))
                if ($null -ne $composer) { $window = $candidate; break }
            }
            if ($null -eq $window) { Start-Sleep -Milliseconds 50 }
        } until ($null -ne $window -or [DateTime]::UtcNow -ge $deadline)
        if ($null -eq $window) { throw 'Packaged shell did not expose a BAXY window.' }
        $coreReady = Find-Control $window 'CORE LISTO' ([Windows.Automation.ControlType]::Text) $deadline
        $idEditor = Find-Control $window 'ID de invoc*' ([Windows.Automation.ControlType]::Edit) $deadline
        $editor = Find-Control $window 'Mensaje para BAXY' ([Windows.Automation.ControlType]::Edit) $deadline
        $button = Find-Control $window 'Enviar mensaje' ([Windows.Automation.ControlType]::Button) $deadline
        if ($null -eq $coreReady -or $null -eq $idEditor -or $null -eq $editor -or $null -eq $button) { throw 'Packaged shell did not expose attested mission controls.' }
        $evidence.core_attested = $true
        $token = [Guid]::NewGuid().ToString('N')
        $invocationId = "package-health-$token"
        $noteName = "health-$token.txt"
        $noteText = "alive-$token"
        $message = "Crea la nota $noteName con el texto: $noteText"
        $notePath = Join-Path $dataRoot "workspace\notes\$noteName"
        $journalPath = Join-Path $dataRoot 'workspace\journal.jsonl'
        $idEditor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($invocationId)
        $editor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($message)
        $button.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
        do {
            Start-Sleep -Milliseconds 50
            $names = @(Get-Names $window)
        } until ((($names -contains 'VERIFICADO') -and $button.Current.IsEnabled -and (Test-Path -LiteralPath $notePath -PathType Leaf)) -or [DateTime]::UtcNow -ge $deadline)
        $evidence.mission_verified = ($names -contains 'VERIFICADO') -and $button.Current.IsEnabled
        $evidence.effect_verified = (Test-Path -LiteralPath $notePath -PathType Leaf) -and ([IO.File]::ReadAllText($notePath, [Text.Encoding]::UTF8) -eq $noteText)
        $evidence.journal_completed_records = Count-Completed $journalPath $invocationId
        $evidence.network_snapshots += Get-NetworkSnapshot $process.Id
        $beforeReplayHash = if (Test-Path -LiteralPath $notePath -PathType Leaf) { (Get-FileHash -LiteralPath $notePath -Algorithm SHA256).Hash } else { $null }
        $beforeReplayNames = @(Get-Names $window).Count
        $idEditor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($invocationId)
        $editor.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern).SetValue($message)
        $button.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
        do {
            Start-Sleep -Milliseconds 50
            $replayNames = @(Get-Names $window)
        } until ((($replayNames.Count -gt $beforeReplayNames) -and $button.Current.IsEnabled) -or [DateTime]::UtcNow -ge $deadline)
        $evidence.replay_visible = $replayNames -contains 'Resultado recuperado sin repetir el efecto.'
        $afterReplayHash = if (Test-Path -LiteralPath $notePath -PathType Leaf) { (Get-FileHash -LiteralPath $notePath -Algorithm SHA256).Hash } else { $null }
        $evidence.journal_completed_records = Count-Completed $journalPath $invocationId
        $evidence.replay_single_effect = $beforeReplayHash -eq $afterReplayHash -and $evidence.journal_completed_records -eq 1
        $evidence.network_snapshots += Get-NetworkSnapshot $process.Id
        $ownedIds = @(Get-TreeIds $process.Id)
        if (Test-Path -LiteralPath $cacheRoot) {
            $evidence.bundle_cache_bytes = [int64](Get-ChildItem -LiteralPath $cacheRoot -File -Recurse -Force | Measure-Object Length -Sum).Sum
        }
    } catch {
        $evidence.errors += $_.Exception.Message
    } finally {
        if ($null -ne $process) {
            try {
                if (-not $process.HasExited) {
                    $closed = $process.CloseMainWindow()
                    if ($closed -and $process.WaitForExit(7000)) {
                        $evidence.graceful_shutdown = $true
                    } else {
                        if (-not $process.HasExited) { $process.Kill() }
                        $process.WaitForExit(7000)
                    }
                } else {
                    $evidence.graceful_shutdown = $true
                }
            } catch {
                $evidence.errors += "cleanup: $($_.Exception.Message)"
            }
            $process.Dispose()
        }
        Start-Sleep -Milliseconds 250
        $evidence.orphan_process_ids = @($ownedIds | Where-Object { $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue) })
    }
    $evidence.network_observer_ok = $evidence.network_snapshots.Count -eq 2 -and @($evidence.network_snapshots | Where-Object { $_.observer_ok -ne $true }).Count -eq 0
    $networkEmpty = @($evidence.network_snapshots | ForEach-Object { @($_.tcp) + @($_.udp) }).Count -eq 0
    $evidence.passed = $evidence.core_attested -and $evidence.mission_verified -and $evidence.effect_verified -and $evidence.journal_completed_records -eq 1 -and $evidence.replay_visible -and $evidence.replay_single_effect -and $evidence.network_observer_ok -and $networkEmpty -and $evidence.graceful_shutdown -and $evidence.orphan_process_ids.Count -eq 0 -and $evidence.errors.Count -eq 0
    return [pscustomobject]$evidence
}

if (-not (Test-Path -LiteralPath $shell -PathType Leaf) -or -not (Test-Path -LiteralPath $core -PathType Leaf)) { throw 'Self-contained shell or core is missing.' }

New-Item -ItemType Directory -Path $ownedRoot -Force | Out-Null
Remove-Owned $ownedRoot
New-Item -ItemType Directory -Path $packagesRoot -Force | Out-Null
New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null

$sentinelRoot = Join-Path $artifactRoot ("work\round_b_package_sentinel\{0}\{1}" -f $System, [Guid]::NewGuid().ToString('N'))
$sentinelRoot = Assert-Contained $sentinelRoot (Join-Path $artifactRoot 'work\round_b_package_sentinel') $false
New-Item -ItemType Directory -Path $sentinelRoot -Force | Out-Null
$sentinel = Join-Path $sentinelRoot 'sentinel.txt'
[IO.File]::WriteAllText($sentinel, 'do-not-delete', $utf8)
$sentinelHash = (Get-FileHash -LiteralPath $sentinel -Algorithm SHA256).Hash
$hostileRoot = Join-Path $ownedRoot 'reparse-probe'
New-Item -ItemType Directory -Path $hostileRoot -Force | Out-Null
$junction = Join-Path $hostileRoot 'outside'
New-Item -ItemType Junction -Path $junction -Target $sentinelRoot | Out-Null
$reparseRejected = $false
try { Remove-Owned $hostileRoot } catch { $reparseRejected = $true }
$sentinelPreserved = (Test-Path -LiteralPath $sentinel -PathType Leaf) -and (Get-FileHash -LiteralPath $sentinel -Algorithm SHA256).Hash -eq $sentinelHash
if (Test-Path -LiteralPath $junction) { [IO.Directory]::Delete($junction, $false) }
Remove-Owned $hostileRoot
Remove-Item -LiteralPath $sentinelRoot -Recurse -Force

$package100 = New-Package '1.0.0'
$package101 = New-Package '1.0.1'
$package102 = New-Package '1.0.2'
$package103 = New-Package '1.0.3'
[IO.File]::AppendAllText((Join-Path $package102 'version.txt'), '-tampered', $utf8)
$adsStreamName = 'baxy-package-hostile'
$adsTarget = Join-Path $package103 'version.txt'
Set-Content -LiteralPath $adsTarget -Stream $adsStreamName -Value 'tampered-outside-the-default-stream' -Encoding UTF8 -ErrorAction Stop
$adsStreamObserved = @(
    Get-Item -LiteralPath $adsTarget -Stream * -ErrorAction Stop |
        Where-Object { $_.Stream -eq $adsStreamName }
).Count -eq 1

Install-Version $package100
$installLaunch = Start-Current
$installedVersion = Get-CurrentVersion
$installedMarker = [IO.File]::ReadAllText((Join-Path $installRoot 'versions\1.0.0\release-marker.txt'), [Text.Encoding]::UTF8)

Install-Version $package101
$updateLaunch = Start-Current
$updatedVersion = Get-CurrentVersion
$updatedMarker = [IO.File]::ReadAllText((Join-Path $installRoot 'versions\1.0.1\release-marker.txt'), [Text.Encoding]::UTF8)

$contentTamperedRejected = $false
$contentTamperFailure = $null
try { Install-Version $package102 } catch { $contentTamperedRejected = $true; $contentTamperFailure = $_.Exception.Message }
$pointerAfterContentTamper = Get-CurrentVersion

$adsInstallRejected = $false
$adsTamperFailure = $null
try { Install-Version $package103 } catch {
    $adsTamperFailure = $_.Exception.Message
    $adsInstallRejected = $adsTamperFailure -like '*alternate data stream forbidden*'
}
$pointerAfterAdsTamper = Get-CurrentVersion
$adsTamperedRejected = $adsStreamObserved -and $adsInstallRejected
$tamperedRejected = $contentTamperedRejected -and $adsTamperedRejected
$pointerAfterTamper = $pointerAfterContentTamper -eq '1.0.1' -and $pointerAfterAdsTamper -eq '1.0.1'

$rollbackSource = [IO.File]::ReadAllText((Join-Path $installRoot 'current.previous'), [Text.Encoding]::UTF8).Trim()
$restoredVersion = Restore-Previous
$rollbackLaunch = Start-Current
$rollbackVersion = Get-CurrentVersion

[IO.File]::WriteAllText((Join-Path $dataRoot 'keep-me.txt'), 'private-data', $utf8)
Remove-Owned $installRoot
$keepDataPassed = (Test-Path -LiteralPath (Join-Path $dataRoot 'keep-me.txt')) -and -not (Test-Path -LiteralPath $installRoot)

New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
Install-Version $package101
$reinstallLaunch = Start-Current
Remove-Owned $installRoot
Remove-Owned $dataRoot
$purgePassed = -not (Test-Path -LiteralPath $installRoot) -and -not (Test-Path -LiteralPath $dataRoot)

$packageBytes = [int64](Get-ChildItem -LiteralPath $package100 -File -Recurse -Force | Measure-Object Length -Sum).Sum
$result = [ordered]@{
    schema_version = 2
    protocol_id = 'baxy-technology-tournament-v1'
    round = 'b_package_lifecycle'
    scope = 'internal offline package mechanism; not a Windows installer certification'
    system_id = $System
    provenance = [ordered]@{
        harness = Get-ProvenanceRecord $PSCommandPath
        cases = Get-ProvenanceRecord $casesPath
        protocol = Get-ProvenanceRecord $protocolPath
        build_recipe = Get-ProvenanceRecord $buildRecipePath
    }
    hashes = [ordered]@{
        shell_bundle_sha256 = Get-TreeHash $shellRoot
        shell_entrypoint_sha256 = (Get-FileHash -LiteralPath $shell -Algorithm SHA256).Hash.ToLowerInvariant()
        core_sha256 = (Get-FileHash -LiteralPath $core -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    signatures = [ordered]@{
        shell = [string](Get-AuthenticodeSignature -LiteralPath $shell).Status
        core = [string](Get-AuthenticodeSignature -LiteralPath $core).Status
    }
    package_bytes = $packageBytes
    package_integrity = [ordered]@{
        authenticity = 'not_provided'
        unsigned_payload_consistency = $true
        threat_model = 'Detects payload changes only while the colocated manifest is trusted and unchanged.'
        tampered_payload_rejected = $tamperedRejected
        content_tampered_payload_rejected = $contentTamperedRejected
        content_tamper_failure = $contentTamperFailure
        alternate_data_stream_observed = $adsStreamObserved
        alternate_data_stream_payload_rejected = $adsTamperedRejected
        alternate_data_stream_name = $adsStreamName
        alternate_data_stream_failure = $adsTamperFailure
    }
    reparse_defense = [ordered]@{ rejected = $reparseRejected; external_sentinel_preserved = $sentinelPreserved }
    runtime_resolution_probe = [ordered]@{
        clean_machine_claimed = $false
        dotnet_root = 'C:\baxy-runtime-intentionally-absent'
        multilevel_lookup = '0'
        shared_with_install_launch = $true
        first_launch = $installLaunch
    }
    install = [ordered]@{
        version = $installedVersion
        release_marker = $installedMarker
        launch = $installLaunch
        passed = ($installedVersion -eq '1.0.0' -and $installedMarker -eq 'BAXY tournament payload 1.0.0' -and $installLaunch.passed)
    }
    update = [ordered]@{
        version = $updatedVersion
        release_marker = $updatedMarker
        payload_changed = $installedMarker -ne $updatedMarker
        launch = $updateLaunch
        passed = ($updatedVersion -eq '1.0.1' -and $updatedMarker -eq 'BAXY tournament payload 1.0.1' -and $installedMarker -ne $updatedMarker -and $updateLaunch.passed)
    }
    tampered_update = [ordered]@{
        rejected = $tamperedRejected
        content_tamper_rejected = $contentTamperedRejected
        alternate_data_stream_rejected = $adsTamperedRejected
        current_after_content_tamper = $pointerAfterContentTamper
        current_after_alternate_data_stream_tamper = $pointerAfterAdsTamper
        current_unchanged = $pointerAfterTamper
    }
    rollback = [ordered]@{
        source = 'current.previous'
        previous_pointer = $rollbackSource
        restored_version = $restoredVersion
        current_version = $rollbackVersion
        launch = $rollbackLaunch
        passed = ($rollbackSource -eq '1.0.0' -and $restoredVersion -eq '1.0.0' -and $rollbackVersion -eq '1.0.0' -and $rollbackLaunch.passed)
    }
    uninstall_keep_data = [ordered]@{ passed = $keepDataPassed }
    reinstall = [ordered]@{ launch = $reinstallLaunch; passed = $reinstallLaunch.passed }
    uninstall_purge_data = [ordered]@{ passed = $purgePassed }
}

$gates = [ordered]@{
    reparse_defense = $reparseRejected -and $sentinelPreserved
    install = $result.install.passed
    update = $result.update.passed
    tampered_payload_rejected = $tamperedRejected -and $pointerAfterTamper
    rollback = $result.rollback.passed
    uninstall_keep_data = $keepDataPassed
    reinstall = $result.reinstall.passed
    uninstall_purge_data = $purgePassed
}
$failedGates = @($gates.Keys | Where-Object { -not $gates[$_] })
$result.gates = $gates
$result.failed_gates = $failedGates
$result.overall_passed = $failedGates.Count -eq 0

if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path $rawRoot "round_b_package_$($System.Replace('-', '_')).json" }
$resolvedOutput = Assert-Contained $OutputPath $rawRoot $false
New-Item -ItemType Directory -Path (Split-Path -Parent $resolvedOutput) -Force | Out-Null
$temporaryOutput = "$resolvedOutput.$([Guid]::NewGuid().ToString('N')).tmp"
[IO.File]::WriteAllText($temporaryOutput, ($result | ConvertTo-Json -Depth 12), $utf8)
if (Test-Path -LiteralPath $resolvedOutput) {
    $outputBackup = "$resolvedOutput.previous"
    if (Test-Path -LiteralPath $outputBackup) { Remove-Item -LiteralPath $outputBackup -Force }
    [IO.File]::Replace($temporaryOutput, $resolvedOutput, $outputBackup, $true)
    Remove-Item -LiteralPath $outputBackup -Force
} else {
    [IO.File]::Move($temporaryOutput, $resolvedOutput)
}

[ordered]@{
    system = $System
    package_mib = $result.package_bytes / 1MB
    overall_passed = $result.overall_passed
    failed_gates = $result.failed_gates
    output = $resolvedOutput
} | ConvertTo-Json -Compress

if (-not $result.overall_passed) { throw "Round B package lifecycle gates failed: $($failedGates -join ', ')" }
