param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-TextSha256Hex {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text)

    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
        return ([BitConverter]::ToString($algorithm.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    } finally {
        $algorithm.Dispose()
    }
}

function Get-RelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $base = [IO.Path]::GetFullPath($BasePath).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($base + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside the expected base: $full"
    }
    return $full.Substring($base.Length + 1).Replace([IO.Path]::DirectorySeparatorChar, '/')
}

function Assert-DescendantPath {
    param(
        [Parameter(Mandatory = $true)][string]$Parent,
        [Parameter(Mandatory = $true)][string]$Child
    )

    $parentFull = [IO.Path]::GetFullPath($Parent).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $childFull = [IO.Path]::GetFullPath($Child)
    if (-not $childFull.StartsWith($parentFull + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing path outside $parentFull`: $childFull"
    }
}

function Assert-ExistingPathChainHasNoReparsePoint {
    param([Parameter(Mandatory = $true)][string]$Path)

    $full = [IO.Path]::GetFullPath($Path)
    $volumeRoot = [IO.Path]::GetPathRoot($full)
    if ([string]::IsNullOrWhiteSpace($volumeRoot)) { throw "Path has no volume root: $full" }
    $current = New-Object IO.DirectoryInfo($volumeRoot)
    if (($current.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing path below a reparse point: $($current.FullName)"
    }

    $relative = $full.Substring($volumeRoot.Length)
    $segments = @($relative.Split(@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar), [StringSplitOptions]::RemoveEmptyEntries))
    for ($index = 0; $index -lt $segments.Count; $index++) {
        $segment = $segments[$index]
        try {
            $matches = @($current.EnumerateFileSystemInfos() | Where-Object {
                [string]::Equals($_.Name, $segment, [StringComparison]::OrdinalIgnoreCase)
            })
        } catch {
            throw "Unable to inspect path component without traversal: $($current.FullName) ($($_.Exception.GetType().Name))"
        }
        if ($matches.Count -eq 0) { return $false }
        if ($matches.Count -ne 1) { throw "Ambiguous path component below $($current.FullName): $segment" }
        $entry = $matches[0]
        if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Refusing reparse point in destructive path: $($entry.FullName)"
        }
        if ($index -lt ($segments.Count - 1)) {
            if (($entry.Attributes -band [IO.FileAttributes]::Directory) -eq 0) {
                throw "Non-directory path component blocks destructive path: $($entry.FullName)"
            }
            $current = New-Object IO.DirectoryInfo($entry.FullName)
        }
    }
    return $true
}

function Assert-TreeHasNoReparsePoint {
    param([Parameter(Mandatory = $true)][string]$Root)

    $pending = New-Object 'System.Collections.Generic.Stack[System.IO.DirectoryInfo]'
    $pending.Push((New-Object IO.DirectoryInfo([IO.Path]::GetFullPath($Root))))
    while ($pending.Count -gt 0) {
        $directory = $pending.Pop()
        if (($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Refusing reparse point in destructive tree: $($directory.FullName)"
        }
        try {
            $entries = @($directory.EnumerateFileSystemInfos())
        } catch {
            throw "Unable to inspect destructive tree without traversal: $($directory.FullName) ($($_.Exception.GetType().Name))"
        }
        foreach ($entry in $entries) {
            if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing reparse point in destructive tree: $($entry.FullName)"
            }
            if (($entry.Attributes -band [IO.FileAttributes]::Directory) -ne 0) {
                $pending.Push((New-Object IO.DirectoryInfo($entry.FullName)))
            }
        }
    }
}

function Remove-TreeFailClosed {
    param(
        [Parameter(Mandatory = $true)][string]$AllowedRoot,
        [Parameter(Mandatory = $true)][string]$Target
    )

    Assert-DescendantPath -Parent $AllowedRoot -Child $Target
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $AllowedRoot
    $targetExists = Assert-ExistingPathChainHasNoReparsePoint -Path $Target
    if (-not $targetExists) { return }
    $targetItem = Get-Item -LiteralPath $Target -Force -ErrorAction Stop
    if (-not $targetItem.PSIsContainer) { throw "Destructive target is not a directory: $Target" }
    Assert-TreeHasNoReparsePoint -Root $Target
    if (-not (Assert-ExistingPathChainHasNoReparsePoint -Path $Target)) {
        throw "Destructive target disappeared during validation: $Target"
    }
    Remove-Item -LiteralPath $Target -Recurse -Force -ErrorAction Stop
}

function Get-HostNativeToolchain {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere -PathType Leaf)) { throw "vswhere.exe is missing: $vswhere" }
    $installation = ((& $vswhere -latest -prerelease -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath) | Out-String).Trim()
    if (($LASTEXITCODE -ne 0) -or [string]::IsNullOrWhiteSpace($installation)) { throw 'A Visual Studio C++ toolchain was not discovered.' }
    $vcvars = Join-Path $installation 'VC\Auxiliary\Build\vcvarsall.bat'
    if (-not (Test-Path -LiteralPath $vcvars -PathType Leaf)) { throw "vcvarsall.bat is missing: $vcvars" }
    $vcArchitecture = $(if ($env:PROCESSOR_ARCHITECTURE -ceq 'ARM64') { 'arm64_amd64' } else { 'amd64' })
    $environmentLines = @(& $env:ComSpec /d /s /c "`"$vcvars`" $vcArchitecture >nul && set" 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "vcvarsall failed for $vcArchitecture" }
    $vcEnvironment = @{}
    foreach ($lineValue in $environmentLines) {
        $line = [string]$lineValue
        if (($line.Length -gt 0) -and ($line[0] -ne '=') -and ($line -match '^([^=]+)=(.*)$')) {
            $vcEnvironment[$matches[1]] = $matches[2]
        }
    }
    foreach ($requiredName in @('PATH', 'LIB', 'VCToolsInstallDir', 'VCToolsVersion')) {
        if (-not $vcEnvironment.ContainsKey($requiredName)) { throw "vcvarsall did not provide $requiredName" }
    }
    $linkCandidates = @(
        ([string]$vcEnvironment['PATH']).Split(';') |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            ForEach-Object { Join-Path $_ 'link.exe' } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
    )
    if ($linkCandidates.Count -eq 0) { throw 'vcvarsall did not expose link.exe on PATH.' }
    $linkPath = [IO.Path]::GetFullPath($linkCandidates[0])
    $linkInfo = Get-Item -LiteralPath $linkPath -Force
    $linkBanner = @(& $linkPath /? 2>&1 | Select-Object -First 1)
    $sdkVersion = $(if ($vcEnvironment.ContainsKey('WindowsSDKVersion')) { ([string]$vcEnvironment['WindowsSDKVersion']).TrimEnd('\', '/') } else { $null })
    $sdkDirectory = $(if ($vcEnvironment.ContainsKey('WindowsSdkDir')) { [IO.Path]::GetFullPath([string]$vcEnvironment['WindowsSdkDir']) } else { $null })
    $nativeLibraryPaths = @(
        ([string]$vcEnvironment['LIB']).Split(';') |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            ForEach-Object { [IO.Path]::GetFullPath($_) }
    )
    $libraryRecords = @(
        for ($index = 0; $index -lt $nativeLibraryPaths.Count; $index++) {
            [pscustomobject][ordered]@{
                ordinal = $index
                path = $nativeLibraryPaths[$index]
                path_sha256 = Get-TextSha256Hex -Text $nativeLibraryPaths[$index].ToLowerInvariant()
                exists = [bool](Test-Path -LiteralPath $nativeLibraryPaths[$index] -PathType Container)
            }
        }
    )
    $sdkDiscovered =
        (-not [string]::IsNullOrWhiteSpace($sdkVersion)) -and
        (-not [string]::IsNullOrWhiteSpace($sdkDirectory)) -and
        (Test-Path -LiteralPath $sdkDirectory -PathType Container)

    return [pscustomobject][ordered]@{
        classification = 'observed_same_host_native_toolchain'
        repository_pinned = $false
        discovery = 'vswhere latest Visual Studio C++ instance plus vcvarsall x64 environment'
        path_hash_scheme = 'sha256(utf8(lower-invariant(full-path)))'
        usage_binding = [ordered]@{
            dotnet_native_aot = 'NativeAOT Windows targets use the same latest-vswhere/vcvarsall selection recorded here.'
            rust = 'The build sets CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER to this exact link.exe path and LIB to the recorded vcvarsall native-library paths.'
        }
        visual_studio_installation = $installation
        vc_environment_architecture = $vcArchitecture
        msvc_tools_version = [string]$vcEnvironment['VCToolsVersion']
        linker = [ordered]@{
            path = $linkPath
            path_sha256 = Get-TextSha256Hex -Text $linkPath.ToLowerInvariant()
            file_sha256 = Get-Sha256Hex -Path $linkPath
            file_version = [string]$linkInfo.VersionInfo.FileVersion
            product_version = [string]$linkInfo.VersionInfo.ProductVersion
            banner = $(if ($linkBanner.Count -eq 1) { [string]$linkBanner[0] } else { $null })
        }
        windows_sdk = [ordered]@{
            discovered = [bool]$sdkDiscovered
            directory = $sdkDirectory
            directory_path_sha256 = $(if ($null -ne $sdkDirectory) { Get-TextSha256Hex -Text $sdkDirectory.ToLowerInvariant() } else { $null })
            version = $sdkVersion
            ucrt_version = $(if ($vcEnvironment.ContainsKey('UCRTVersion')) { [string]$vcEnvironment['UCRTVersion'] } else { $null })
            native_library_paths = @($libraryRecords)
            lib_environment_sha256 = Get-TextSha256Hex -Text ((@($nativeLibraryPaths | ForEach-Object { $_.ToLowerInvariant() })) -join ';')
        }
        passed = [bool]($sdkDiscovered -and ($libraryRecords.Count -gt 0) -and -not ($libraryRecords.exists -contains $false))
    }
}

function New-SnapshotFromFiles {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][IO.FileInfo[]]$Files
    )

    $records = @(
        $Files |
            Sort-Object -Property FullName -Unique |
            ForEach-Object {
                [pscustomobject][ordered]@{
                    relative_path = Get-RelativePath -BasePath $BasePath -Path $_.FullName
                    bytes = [long]$_.Length
                    sha256 = Get-Sha256Hex -Path $_.FullName
                }
            } |
            Sort-Object -Property relative_path
    )
    $treePayload = ($records | ForEach-Object {
        "{0}`0{1}`0{2}`n" -f $_.relative_path, $_.bytes, $_.sha256
    }) -join ''
    $totalBytes = [long]0
    foreach ($record in $records) { $totalBytes += [long]$record.bytes }

    return [pscustomobject][ordered]@{
        tree_sha256 = Get-TextSha256Hex -Text $treePayload
        file_count = [int]$records.Count
        total_bytes = $totalBytes
        files = @($records)
    }
}

function Get-TreeSnapshot {
    param([Parameter(Mandatory = $true)][string]$Root)

    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "Expected output directory is missing: $Root"
    }
    $files = @(Get-ChildItem -LiteralPath $Root -Recurse -Force -File)
    if ($files.Count -eq 0) { throw "Expected output directory is empty: $Root" }
    return New-SnapshotFromFiles -BasePath $Root -Files $files
}

function Get-InputSnapshot {
    param([Parameter(Mandatory = $true)][string]$RepositoryRoot)

    $files = New-Object 'System.Collections.Generic.List[System.IO.FileInfo]'
    $explicitFiles = @(
        (Join-Path $RepositoryRoot 'global.json'),
        (Join-Path $RepositoryRoot 'experiments\technology_tournament\round_b\build_round_b.ps1'),
        (Join-Path $RepositoryRoot 'experiments\technology_tournament\round_b\dotnet_webview\CoreBridge.cs'),
        (Join-Path $RepositoryRoot 'experiments\technology_tournament\round_b\tauri_rust\src-tauri\icons\icon.ico')
    )
    foreach ($path in $explicitFiles) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required build input is missing: $path" }
        $null = $files.Add((Get-Item -LiteralPath $path))
    }

    $inputDirectories = @(
        (Join-Path $RepositoryRoot 'experiments\technology_tournament\round_b\native_wpf'),
        (Join-Path $RepositoryRoot 'experiments\technology_tournament\dotnet_windows_core'),
        (Join-Path $RepositoryRoot 'experiments\technology_tournament\rust_core')
    )
    foreach ($directory in $inputDirectories) {
        foreach ($file in @(Get-ChildItem -LiteralPath $directory -Recurse -Force -File)) {
            if ($file.FullName -match '[\\/](bin|obj|target)[\\/]') { continue }
            $null = $files.Add($file)
        }
    }
    return New-SnapshotFromFiles -BasePath $RepositoryRoot -Files @($files)
}

function Copy-InputSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$DestinationRoot,
        [Parameter(Mandatory = $true)]$Snapshot
    )

    foreach ($record in @($Snapshot.files)) {
        $platformPath = ([string]$record.relative_path).Replace('/', [IO.Path]::DirectorySeparatorChar)
        $source = Join-Path $SourceRoot $platformPath
        $destination = Join-Path $DestinationRoot $platformPath
        Assert-DescendantPath -Parent $SourceRoot -Child $source
        Assert-DescendantPath -Parent $DestinationRoot -Child $destination
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }
}

function Compare-Snapshots {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][string]$PrimaryArtifact,
        [Parameter(Mandatory = $true)]$Run01,
        [Parameter(Mandatory = $true)]$Run02
    )

    $leftFiles = @($Run01.files)
    $rightFiles = @($Run02.files)
    $leftPaths = @($leftFiles | ForEach-Object { [string]$_.relative_path })
    $rightPaths = @($rightFiles | ForEach-Object { [string]$_.relative_path })
    $sameFileSet = (@(Compare-Object -ReferenceObject $leftPaths -DifferenceObject $rightPaths -CaseSensitive)).Count -eq 0
    $artifactHashesEqual = $sameFileSet
    if ($artifactHashesEqual) {
        $rightByPath = @{}
        foreach ($file in $rightFiles) { $rightByPath[[string]$file.relative_path] = $file }
        foreach ($file in $leftFiles) {
            $other = $rightByPath[[string]$file.relative_path]
            if (($file.sha256 -ne $other.sha256) -or ([long]$file.bytes -ne [long]$other.bytes)) {
                $artifactHashesEqual = $false
                break
            }
        }
    }
    $leftPrimary = @($leftFiles | Where-Object { $_.relative_path -ceq $PrimaryArtifact })
    $rightPrimary = @($rightFiles | Where-Object { $_.relative_path -ceq $PrimaryArtifact })
    $primaryPresent = ($leftPrimary.Count -eq 1) -and ($rightPrimary.Count -eq 1)
    $primaryEqual = $primaryPresent -and ($leftPrimary[0].sha256 -eq $rightPrimary[0].sha256) -and ([long]$leftPrimary[0].bytes -eq [long]$rightPrimary[0].bytes)
    $treeHashEqual = $Run01.tree_sha256 -eq $Run02.tree_sha256
    $passed = $sameFileSet -and $artifactHashesEqual -and $primaryEqual -and $treeHashEqual

    return [pscustomobject][ordered]@{
        id = $Id
        primary_artifact = [ordered]@{
            relative_path = $PrimaryArtifact
            run_01_sha256 = $(if ($leftPrimary.Count -eq 1) { $leftPrimary[0].sha256 } else { $null })
            run_02_sha256 = $(if ($rightPrimary.Count -eq 1) { $rightPrimary[0].sha256 } else { $null })
            equal = [bool]$primaryEqual
        }
        run_01 = $Run01
        run_02 = $Run02
        same_file_set = [bool]$sameFileSet
        artifact_hashes_equal = [bool]$artifactHashesEqual
        tree_hash_equal = [bool]$treeHashEqual
        passed = [bool]$passed
    }
}

function Invoke-RoundBBuild {
    param(
        [Parameter(Mandatory = $true)][string]$PowerShellPath,
        [Parameter(Mandatory = $true)][string]$BuildScript,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$OutputRoot,
        [Parameter(Mandatory = $true)][string]$LogRoot,
        [Parameter(Mandatory = $true)][string]$RunId,
        [Parameter(Mandatory = $true)][string]$RepositoryRoot
    )

    $stdout = Join-Path $LogRoot ($RunId + '.stdout.log')
    $stderr = Join-Path $LogRoot ($RunId + '.stderr.log')
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $process = New-Object Diagnostics.Process
    $process.StartInfo = New-Object Diagnostics.ProcessStartInfo
    $process.StartInfo.FileName = $PowerShellPath
    $process.StartInfo.Arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -OutputRoot "{1}"' -f $BuildScript, $OutputRoot
    $process.StartInfo.WorkingDirectory = $WorkingDirectory
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.CreateNoWindow = $true
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    try {
        if (-not $process.Start()) { throw "Failed to start isolated build $RunId" }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $stdoutText = $stdoutTask.Result
        $stderrText = $stderrTask.Result
        $childExitCode = $process.ExitCode
    } finally {
        $timer.Stop()
        $process.Dispose()
    }
    $utf8 = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($stdout, $stdoutText, $utf8)
    [IO.File]::WriteAllText($stderr, $stderrText, $utf8)

    $metadataPrefix = 'BAXY_ROUND_B_BUILD_METADATA='
    $metadataLines = @(
        ($stdoutText -split "`r?`n") |
            Where-Object { $_.StartsWith($metadataPrefix, [StringComparison]::Ordinal) }
    )
    $buildMetadata = $null
    $metadataError = $null
    if ($metadataLines.Count -eq 1) {
        try {
            $buildMetadata = $metadataLines[0].Substring($metadataPrefix.Length) | ConvertFrom-Json
            if (($buildMetadata.schema_version -ne 1) -or ($null -eq $buildMetadata.native_link_toolchain)) {
                throw 'Build metadata is missing its native toolchain identity.'
            }
            $reportedScope = $buildMetadata.reproduction_classification
            if (
                ([string]$buildMetadata.dotnet_sdk -cne '10.0.100') -or
                ([string]$buildMetadata.rustc -notmatch '^rustc 1\.97\.0 \(') -or
                ($null -eq $reportedScope) -or
                ([string]$reportedScope.host_scope -cne 'single_host') -or
                ([string]$reportedScope.global_package_caches -cne 'shared_host_caches') -or
                ($reportedScope.clean_environment -ne $false) -or
                ($reportedScope.cross_host -ne $false)
            ) {
                throw 'Build metadata has an unexpected toolchain or environment classification.'
            }
        } catch {
            $metadataError = $_.Exception.GetType().Name + ': ' + $_.Exception.Message
            $buildMetadata = $null
        }
    } else {
        $metadataError = "Expected exactly one build metadata marker, found $($metadataLines.Count)."
    }
    $nativeIdentity = $(if ($null -ne $buildMetadata) { $buildMetadata.native_link_toolchain } else { $null })
    $nativeIdentitySha256 = $(if ($null -ne $nativeIdentity) { Get-TextSha256Hex -Text ($nativeIdentity | ConvertTo-Json -Depth 20 -Compress) } else { $null })
    $metadataPassed = $null -ne $buildMetadata

    return [pscustomobject][ordered]@{
        run_id = $RunId
        source_isolation = 'separate_exact_source_replica'
        host_scope = 'same_host_as_other_run'
        global_package_caches = 'shared_between_runs'
        clean_environment = $false
        cross_host = $false
        output_root = Get-RelativePath -BasePath $RepositoryRoot -Path $OutputRoot
        stdout_log = Get-RelativePath -BasePath $RepositoryRoot -Path $stdout
        stdout_sha256 = $(if (Test-Path -LiteralPath $stdout) { Get-Sha256Hex -Path $stdout } else { $null })
        stderr_log = Get-RelativePath -BasePath $RepositoryRoot -Path $stderr
        stderr_sha256 = $(if (Test-Path -LiteralPath $stderr) { Get-Sha256Hex -Path $stderr } else { $null })
        stderr_tail = $(if ($stderrText.Length -gt 4000) { $stderrText.Substring($stderrText.Length - 4000) } else { $stderrText })
        build_metadata_captured = [bool]$metadataPassed
        build_metadata_error = $metadataError
        build_reported_dotnet_sdk = $(if ($null -ne $buildMetadata) { [string]$buildMetadata.dotnet_sdk } else { $null })
        build_reported_rustc = $(if ($null -ne $buildMetadata) { [string]$buildMetadata.rustc } else { $null })
        build_reported_reproduction_classification = $(if ($null -ne $buildMetadata) { $buildMetadata.reproduction_classification } else { $null })
        native_link_toolchain = $nativeIdentity
        native_link_toolchain_sha256 = $nativeIdentitySha256
        exit_code = [int]$childExitCode
        duration_ms = [math]::Round($timer.Elapsed.TotalMilliseconds, 3)
        passed = ($childExitCode -eq 0) -and $metadataPassed
    }
}

function Find-Dumpbin {
    $command = Get-Command dumpbin.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) { return $command.Source }

    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere -PathType Leaf)) { return $null }
    $installation = ((& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath) | Out-String).Trim()
    if ([string]::IsNullOrWhiteSpace($installation)) { return $null }
    $toolsRoot = Join-Path $installation 'VC\Tools\MSVC'
    foreach ($version in @(Get-ChildItem -LiteralPath $toolsRoot -Directory | Sort-Object -Property Name -Descending)) {
        $candidate = Join-Path $version.FullName 'bin\Hostx64\x64\dumpbin.exe'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}

function Get-RustRuntimeImports {
    param(
        [Parameter(Mandatory = $true)][string]$Dumpbin,
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string]$RunId
    )

    $output = @(& $Dumpbin /nologo /imports $Executable 2>&1)
    $exitCode = $LASTEXITCODE
    $imports = @(
        $output |
            ForEach-Object { ([string]$_).Trim() } |
            Where-Object { $_ -match '^[A-Za-z0-9._-]+\.dll$' } |
            ForEach-Object { $_.ToLowerInvariant() } |
            Sort-Object -Unique
    )
    $forbidden = @($imports | Where-Object {
        ($_ -match '^vcruntime.*\.dll$') -or
        ($_ -match '^msvcp.*\.dll$') -or
        ($_ -eq 'msvcrt.dll') -or
        ($_ -eq 'ucrtbase.dll') -or
        ($_ -match '^api-ms-win-crt-.*\.dll$')
    })

    return [pscustomobject][ordered]@{
        run_id = $RunId
        executable_sha256 = Get-Sha256Hex -Path $Executable
        imports = @($imports)
        forbidden_imports = @($forbidden)
        dumpbin_exit_code = [int]$exitCode
        passed = ($exitCode -eq 0) -and ($imports.Count -gt 0) -and ($forbidden.Count -eq 0)
    }
}

function Write-AtomicJson {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value
    )

    $directory = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $temporary = Join-Path $directory ((Split-Path -Leaf $Path) + '.tmp.' + $PID + '.' + [Guid]::NewGuid().ToString('N'))
    $backup = Join-Path $directory ((Split-Path -Leaf $Path) + '.bak.' + $PID + '.' + [Guid]::NewGuid().ToString('N'))
    $json = $Value | ConvertTo-Json -Depth 30
    [IO.File]::WriteAllText($temporary, $json + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        [IO.File]::Replace($temporary, $Path, $backup, $true)
        Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
    } else {
        [IO.File]::Move($temporary, $Path)
    }
}

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$artifactRoot = Join-Path $root 'artifacts\technology_tournament'
$buildParent = Join-Path $artifactRoot 'build'
$sessionRoot = Join-Path $buildParent 'rb'
$run01Root = Join-Path $sessionRoot 'a'
$run02Root = Join-Path $sessionRoot 'b'
$run01Output = Join-Path $run01Root 'artifacts\technology_tournament\build\o'
$run02Output = Join-Path $run02Root 'artifacts\technology_tournament\build\o'
$logRoot = Join-Path $sessionRoot 'l'
$evidencePath = Join-Path $artifactRoot 'raw\round_b_reproducibility.json'
$buildScript = Join-Path $PSScriptRoot 'build_round_b.ps1'
$harnessPath = Join-Path $PSScriptRoot 'reproducibility_harness.ps1'
$rustRoot = Join-Path $root 'experiments\technology_tournament\rust_core'
$globalJsonPath = Join-Path $root 'global.json'
$rustToolchainPath = Join-Path $rustRoot 'rust-toolchain.toml'
$cargoConfigPath = Join-Path $rustRoot '.cargo\config.toml'
$powerShellPath = Join-Path $PSHOME 'powershell.exe'
$evidence = $null
$exitCode = 1

try {
    Assert-DescendantPath -Parent $buildParent -Child $sessionRoot
    Assert-DescendantPath -Parent $sessionRoot -Child $run01Root
    Assert-DescendantPath -Parent $sessionRoot -Child $run02Root
    if ([String]::Equals([IO.Path]::GetFullPath($run01Root), [IO.Path]::GetFullPath($run02Root), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Reproducibility builds must use distinct output directories.'
    }
    Remove-TreeFailClosed -AllowedRoot $buildParent -Target $sessionRoot
    New-Item -ItemType Directory -Path $sessionRoot, $logRoot -Force | Out-Null
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $sessionRoot

    & git -C $root check-ignore -q -- (Get-RelativePath -BasePath $root -Path $run01Root)
    $run01Ignored = $LASTEXITCODE -eq 0
    & git -C $root check-ignore -q -- (Get-RelativePath -BasePath $root -Path $run02Root)
    $run02Ignored = $LASTEXITCODE -eq 0

    $globalPin = Get-Content -LiteralPath $globalJsonPath -Raw | ConvertFrom-Json
    $globalPinValid =
        ([string]$globalPin.sdk.version -ceq '10.0.100') -and
        ([string]$globalPin.sdk.rollForward -ceq 'disable') -and
        ($globalPin.sdk.allowPrerelease -eq $false)
    $dotnetActual = ((& dotnet --version 2>&1) | Out-String).Trim()
    $dotnetExit = $LASTEXITCODE

    $rustToolchainText = Get-Content -LiteralPath $rustToolchainPath -Raw
    $cargoConfigText = Get-Content -LiteralPath $cargoConfigPath -Raw
    $rustPinValid =
        ($rustToolchainText -match '(?m)^\s*channel\s*=\s*"1\.97\.0"\s*$') -and
        ($rustToolchainText -match '(?m)^\s*profile\s*=\s*"minimal"\s*$') -and
        ($rustToolchainText -match '(?m)^\s*targets\s*=\s*\[\s*"x86_64-pc-windows-msvc"\s*\]\s*$')
    $staticCrtConfigured =
        ($cargoConfigText -match '(?m)^\s*\[target\.x86_64-pc-windows-msvc\]\s*$') -and
        ($cargoConfigText -match '(?s)rustflags\s*=\s*\[[^\]]*"target-feature=\+crt-static"[^\]]*\]')
    $deterministicRustLinkConfigured =
        ($cargoConfigText -match '(?s)rustflags\s*=\s*\[[^\]]*"link-arg=/Brepro"[^\]]*\]')

    $cargo = Join-Path $env:USERPROFILE '.cargo\bin\cargo.exe'
    $rustc = Join-Path $env:USERPROFILE '.cargo\bin\rustc.exe'
    $rustup = Join-Path $env:USERPROFILE '.cargo\bin\rustup.exe'
    foreach ($launcher in @($cargo, $rustc, $rustup)) {
        if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "Rust launcher is missing: $launcher" }
    }
    Push-Location $rustRoot
    try {
        $rustcActual = ((& $rustc --version 2>&1) | Out-String).Trim()
        $rustcExit = $LASTEXITCODE
        $cargoActual = ((& $cargo --version 2>&1) | Out-String).Trim()
        $cargoExit = $LASTEXITCODE
        $activeToolchain = ((& $rustup show active-toolchain 2>&1) | Out-String).Trim()
        $activeToolchainExit = $LASTEXITCODE
        $installedTargets = @(& $rustup target list --installed 2>$null | ForEach-Object { ([string]$_).Trim() })
        $installedTargetsExit = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    $dotnetToolchainPassed = $globalPinValid -and ($dotnetExit -eq 0) -and ($dotnetActual -ceq '10.0.100')
    $rustToolchainPassed =
        $rustPinValid -and
        $staticCrtConfigured -and
        $deterministicRustLinkConfigured -and
        ($rustcExit -eq 0) -and ($rustcActual -match '^rustc 1\.97\.0 \(') -and
        ($cargoExit -eq 0) -and ($cargoActual -match '^cargo 1\.97\.0 \(') -and
        ($activeToolchainExit -eq 0) -and ($activeToolchain -match '^1\.97\.0-x86_64-pc-windows-msvc\b') -and
        ($installedTargetsExit -eq 0) -and ($installedTargets -contains 'x86_64-pc-windows-msvc')
    $nativeToolchain = Get-HostNativeToolchain

    $inputBefore = Get-InputSnapshot -RepositoryRoot $root
    Copy-InputSnapshot -SourceRoot $root -DestinationRoot $run01Root -Snapshot $inputBefore
    $replica01 = Get-InputSnapshot -RepositoryRoot $run01Root
    $replica01Exact = $inputBefore.tree_sha256 -eq $replica01.tree_sha256
    $replica01BuildScript = Join-Path $run01Root 'experiments\technology_tournament\round_b\build_round_b.ps1'
    $replica01RustRoot = Join-Path $run01Root 'experiments\technology_tournament\rust_core'
    $build01 = Invoke-RoundBBuild -PowerShellPath $powerShellPath -BuildScript $replica01BuildScript -WorkingDirectory $replica01RustRoot -OutputRoot $run01Output -LogRoot $logRoot -RunId 'run_01' -RepositoryRoot $root
    $inputBetween = Get-InputSnapshot -RepositoryRoot $root
    Copy-InputSnapshot -SourceRoot $root -DestinationRoot $run02Root -Snapshot $inputBetween
    $replica02 = Get-InputSnapshot -RepositoryRoot $run02Root
    $replica02Exact = $inputBetween.tree_sha256 -eq $replica02.tree_sha256
    $replica02BuildScript = Join-Path $run02Root 'experiments\technology_tournament\round_b\build_round_b.ps1'
    $replica02RustRoot = Join-Path $run02Root 'experiments\technology_tournament\rust_core'
    $build02 = Invoke-RoundBBuild -PowerShellPath $powerShellPath -BuildScript $replica02BuildScript -WorkingDirectory $replica02RustRoot -OutputRoot $run02Output -LogRoot $logRoot -RunId 'run_02' -RepositoryRoot $root
    $inputAfter = Get-InputSnapshot -RepositoryRoot $root
    $inputsUnchanged =
        ($inputBefore.tree_sha256 -eq $inputBetween.tree_sha256) -and
        ($inputBetween.tree_sha256 -eq $inputAfter.tree_sha256)

    $comparisons = [ordered]@{}
    if ($build01.passed -and $build02.passed) {
        $comparisons.wpf_self_contained = Compare-Snapshots -Id 'wpf_self_contained' -PrimaryArtifact 'baxy-dotnet-wpf-slice.exe' -Run01 (Get-TreeSnapshot -Root (Join-Path $run01Output 'wpf_self_contained')) -Run02 (Get-TreeSnapshot -Root (Join-Path $run02Output 'wpf_self_contained'))
        $comparisons.dotnet_native_aot = Compare-Snapshots -Id 'dotnet_native_aot' -PrimaryArtifact 'baxy-dotnet-slice.exe' -Run01 (Get-TreeSnapshot -Root (Join-Path $run01Output 'dotnet_native_aot')) -Run02 (Get-TreeSnapshot -Root (Join-Path $run02Output 'dotnet_native_aot'))
        $comparisons.rust_static = Compare-Snapshots -Id 'rust_static' -PrimaryArtifact 'baxy-rust-slice.exe' -Run01 (Get-TreeSnapshot -Root (Join-Path $run01Output 'rust_static')) -Run02 (Get-TreeSnapshot -Root (Join-Path $run02Output 'rust_static'))
    }

    $dumpbin = Find-Dumpbin
    $runtimeRuns = @()
    if (($null -ne $dumpbin) -and $build01.passed -and $build02.passed) {
        $runtimeRuns = @(
            (Get-RustRuntimeImports -Dumpbin $dumpbin -Executable (Join-Path $run01Output 'rust_static\baxy-rust-slice.exe') -RunId 'run_01'),
            (Get-RustRuntimeImports -Dumpbin $dumpbin -Executable (Join-Path $run02Output 'rust_static\baxy-rust-slice.exe') -RunId 'run_02')
        )
    }
    $runtimeImportsEqual =
        ($runtimeRuns.Count -eq 2) -and
        ((@($runtimeRuns[0].imports) -join "`n") -ceq (@($runtimeRuns[1].imports) -join "`n"))
    $rustStaticCrtPassed =
        $staticCrtConfigured -and
        ($runtimeRuns.Count -eq 2) -and
        $runtimeRuns[0].passed -and
        $runtimeRuns[1].passed -and
        $runtimeImportsEqual

    $buildsPassed = $build01.passed -and $build02.passed
    $wpfPassed = $comparisons.Contains('wpf_self_contained') -and $comparisons.wpf_self_contained.passed
    $dotnetCorePassed = $comparisons.Contains('dotnet_native_aot') -and $comparisons.dotnet_native_aot.passed
    $rustCorePassed = $comparisons.Contains('rust_static') -and $comparisons.rust_static.passed
    $nativeToolchainSha256 = Get-TextSha256Hex -Text ($nativeToolchain | ConvertTo-Json -Depth 20 -Compress)
    $buildNativeIdentitiesMatch =
        $build01.build_metadata_captured -and
        $build02.build_metadata_captured -and
        ($build01.native_link_toolchain_sha256 -ceq $nativeToolchainSha256) -and
        ($build02.native_link_toolchain_sha256 -ceq $nativeToolchainSha256)
    $nativeToolchainObserved = $nativeToolchain.passed -and $buildNativeIdentitiesMatch
    $repositorySdkToolchainsPinned = $dotnetToolchainPassed -and $rustToolchainPassed
    $gates = [ordered]@{
        toolchains_pinned = [bool]$repositorySdkToolchainsPinned
        repository_sdk_toolchains_pinned = [bool]$repositorySdkToolchainsPinned
        host_native_toolchain_observed = [bool]$nativeToolchainObserved
        build_directories_ignored = [bool]($run01Ignored -and $run02Ignored)
        inputs_unchanged = [bool]$inputsUnchanged
        input_replicas_exact = [bool]($replica01Exact -and $replica02Exact)
        independent_builds_succeeded = [bool]$buildsPassed
        wpf_self_contained_reproducible = [bool]$wpfPassed
        dotnet_native_aot_reproducible = [bool]$dotnetCorePassed
        rust_static_reproducible = [bool]$rustCorePassed
        rust_static_crt = [bool]$rustStaticCrtPassed
    }
    $gates.all_passed = -not ($gates.Values -contains $false)

    $evidence = [pscustomobject][ordered]@{
        schema_version = 1
        generated_utc = [DateTime]::UtcNow.ToString('o')
        evidence_id = 'round_b_reproducibility'
        provenance = [ordered]@{
            harness = [ordered]@{
                path = Get-RelativePath -BasePath $root -Path $harnessPath
                bytes = [int64](Get-Item -LiteralPath $harnessPath -Force).Length
                sha256 = Get-Sha256Hex -Path $harnessPath
            }
        }
        scope = [ordered]@{
            statement = 'Two exact source replicas execute the Round B recipe in separate processes and output roots on one host with shared global caches; complete output trees and per-file SHA-256 values are compared.'
            classification = 'same_host_isolated_source_replicas_shared_caches'
            source_replicas_isolated = $true
            output_roots_isolated = $true
            process_runs_separate = $true
            host_shared = $true
            global_caches_shared = $true
            clean_environment = $false
            cross_host = $false
            cache_state_reset_between_runs = $false
            limitation = 'This is not clean-environment or cross-host reproduction. NuGet, Cargo, rustup, SDK, MSVC, and Windows SDK state are shared host state.'
            official_packaging_artifacts_modified = $false
            build_root = Get-RelativePath -BasePath $root -Path $sessionRoot
            evidence_path = Get-RelativePath -BasePath $root -Path $evidencePath
        }
        gate_semantics = [ordered]@{
            toolchains_pinned = 'Compatibility alias for repository_sdk_toolchains_pinned. Repository pins cover the .NET SDK and Rust compiler/toolchain target only; this gate explicitly excludes host MSVC link.exe and the Windows SDK.'
            repository_sdk_toolchains_pinned = 'The repository pins the .NET SDK and Rust compiler/toolchain target used by both runs.'
            host_native_toolchain_observed = 'The actual same-host MSVC linker identity and vcvarsall-selected Windows SDK were discovered and recorded, but are not repository-pinned.'
            independent_builds_succeeded = 'Compatibility name retained: the runs are separate processes with separate exact source replicas and output roots on the same host; they share global caches and are neither clean-host nor cross-host builds.'
        }
        recipe = [ordered]@{
            path = Get-RelativePath -BasePath $root -Path $buildScript
            sha256 = Get-Sha256Hex -Path $buildScript
        }
        toolchains = [ordered]@{
            pinning_scope = [ordered]@{
                repository_pinned = @('.NET SDK', 'Rust compiler channel', 'Rust target', 'Rust linker flags')
                host_observed_not_pinned = @('MSVC link.exe', 'MSVC tools', 'Windows SDK', 'native library search paths')
            }
            dotnet = [ordered]@{
                pin_file = Get-RelativePath -BasePath $root -Path $globalJsonPath
                pin_sha256 = Get-Sha256Hex -Path $globalJsonPath
                expected_sdk = '10.0.100'
                expected_roll_forward = 'disable'
                actual_sdk = $dotnetActual
                pin_valid = [bool]$globalPinValid
                passed = [bool]$dotnetToolchainPassed
            }
            rust = [ordered]@{
                pin_file = Get-RelativePath -BasePath $root -Path $rustToolchainPath
                pin_sha256 = Get-Sha256Hex -Path $rustToolchainPath
                expected_channel = '1.97.0'
                expected_target = 'x86_64-pc-windows-msvc'
                rustc_actual = $rustcActual
                cargo_actual = $cargoActual
                active_toolchain = $activeToolchain
                target_installed = [bool]($installedTargets -contains 'x86_64-pc-windows-msvc')
                pin_valid = [bool]$rustPinValid
                passed = [bool]$rustToolchainPassed
            }
            rust_static_crt_configuration = [ordered]@{
                path = Get-RelativePath -BasePath $root -Path $cargoConfigPath
                sha256 = Get-Sha256Hex -Path $cargoConfigPath
                configured = [bool]$staticCrtConfigured
                deterministic_link_configured = [bool]$deterministicRustLinkConfigured
            }
            host_native = $nativeToolchain
            host_native_build_binding = [ordered]@{
                identity_sha256 = $nativeToolchainSha256
                both_builds_captured_identity = [bool]($build01.build_metadata_captured -and $build02.build_metadata_captured)
                run_01_identity_sha256 = $build01.native_link_toolchain_sha256
                run_02_identity_sha256 = $build02.native_link_toolchain_sha256
                both_runs_match_observed_identity = [bool]$buildNativeIdentitiesMatch
                passed = [bool]$nativeToolchainObserved
            }
        }
        input_snapshots = [ordered]@{
            before_run_01 = $inputBefore
            between_runs = $inputBetween
            after_run_02 = $inputAfter
            run_01_replica = $replica01
            run_02_replica = $replica02
            unchanged = [bool]$inputsUnchanged
            replicas_exact = [bool]($replica01Exact -and $replica02Exact)
        }
        builds = @($build01, $build02)
        comparisons = $comparisons
        rust_static_runtime = [ordered]@{
            analyzer = $dumpbin
            imports_equal = [bool]$runtimeImportsEqual
            runs = @($runtimeRuns)
            passed = [bool]$rustStaticCrtPassed
        }
        gates = $gates
        passed = [bool]$gates.all_passed
    }
    if ($evidence.passed) { $exitCode = 0 }
} catch {
    $evidence = [pscustomobject][ordered]@{
        schema_version = 1
        generated_utc = [DateTime]::UtcNow.ToString('o')
        evidence_id = 'round_b_reproducibility'
        fatal_error = [ordered]@{
            type = $_.Exception.GetType().FullName
            message = $_.Exception.Message
            script_stack_trace = $_.ScriptStackTrace
        }
        gates = [ordered]@{ all_passed = $false }
        passed = $false
    }
}

Write-AtomicJson -Path $evidencePath -Value $evidence
Write-Output ([ordered]@{
    evidence_id = $evidence.evidence_id
    evidence_path = Get-RelativePath -BasePath $root -Path $evidencePath
    gates = $evidence.gates
    passed = [bool]$evidence.passed
} | ConvertTo-Json -Depth 5)
exit $exitCode
