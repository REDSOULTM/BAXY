param(
    [string]$OutputRoot
)

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

function Assert-StrictDescendantPath {
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

    Assert-StrictDescendantPath -Parent $AllowedRoot -Child $Target
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $AllowedRoot
    $targetExists = Assert-ExistingPathChainHasNoReparsePoint -Path $Target
    if (-not $targetExists) { return }
    $targetItem = Get-Item -LiteralPath $Target -Force -ErrorAction Stop
    if (-not $targetItem.PSIsContainer) { throw "Destructive target is not a directory: $Target" }
    Assert-TreeHasNoReparsePoint -Root $Target
    # Recheck the full existing chain immediately before deletion to reduce the
    # window in which a path could be exchanged for a junction.
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
        identity = [pscustomobject][ordered]@{
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
        cargo_linker = $linkPath
        cargo_native_library_path = [string]$vcEnvironment['LIB']
    }
}

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$artifactRoot = Join-Path $root 'artifacts\technology_tournament'
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $artifactRoot 'build\round_b_reproducible'
}
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
$allowed = [IO.Path]::GetFullPath((Join-Path $artifactRoot 'build'))
Assert-StrictDescendantPath -Parent $allowed -Child $OutputRoot
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $allowed
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $OutputRoot

$dotnetVersion = $null
Push-Location $root
try {
    $dotnetVersion = (& dotnet --version).Trim()
} finally {
    Pop-Location
}
if ($dotnetVersion -ne '10.0.100') { throw "Expected .NET SDK 10.0.100, found $dotnetVersion" }
$cargo = Join-Path $env:USERPROFILE '.cargo\bin\cargo.exe'
$rustc = Join-Path $env:USERPROFILE '.cargo\bin\rustc.exe'
if (-not (Test-Path -LiteralPath $cargo) -or -not (Test-Path -LiteralPath $rustc)) { throw 'Pinned Rust toolchain launchers are missing.' }
$rustToolchain = '1.97.0-x86_64-pc-windows-msvc'
$rustVersion = (& $rustc "+$rustToolchain" --version).Trim()
if ($rustVersion -notlike 'rustc 1.97.0 *') { throw "Expected rustc 1.97.0, found $rustVersion" }
$nativeToolchain = Get-HostNativeToolchain
if (-not $nativeToolchain.identity.passed) { throw 'The host native linker/Windows SDK identity is incomplete.' }

$shellProject = Join-Path $root 'experiments\technology_tournament\round_b\native_wpf\BaxyNativeWpf.csproj'
$dotnetCoreProject = Join-Path $root 'experiments\technology_tournament\dotnet_windows_core\BaxySlice.csproj'
$rustManifest = Join-Path $root 'experiments\technology_tournament\rust_core\Cargo.toml'
$fdd = Join-Path $OutputRoot 'wpf_fdd'
$shell = Join-Path $OutputRoot 'wpf_self_contained'
$dotnetCore = Join-Path $OutputRoot 'dotnet_native_aot'
$rustTarget = Join-Path $OutputRoot 'rust_target'
$rustCore = Join-Path $OutputRoot 'rust_static'
Remove-TreeFailClosed -AllowedRoot $allowed -Target $OutputRoot
foreach ($directory in @($fdd, $shell, $dotnetCore, $rustTarget, $rustCore)) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $OutputRoot

Push-Location $root
try {
    & dotnet publish $shellProject -c Release --no-self-contained -p:DebugType=None -p:DebugSymbols=false -p:ContinuousIntegrationBuild=true -o $fdd --nologo
    if ($LASTEXITCODE -ne 0) { throw "WPF framework-dependent publish failed with exit code $LASTEXITCODE" }
    & dotnet publish $shellProject -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=false -p:DebugType=None -p:DebugSymbols=false -p:ContinuousIntegrationBuild=true -o $shell --nologo
    if ($LASTEXITCODE -ne 0) { throw "WPF self-contained publish failed with exit code $LASTEXITCODE" }
    & dotnet publish $dotnetCoreProject -c Release -r win-x64 --self-contained -p:PublishAot=true -p:StripSymbols=true -p:DebugType=None -p:DebugSymbols=false -p:ContinuousIntegrationBuild=true -o $dotnetCore --nologo
    if ($LASTEXITCODE -ne 0) { throw ".NET NativeAOT publish failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

$previousTarget = $env:CARGO_TARGET_DIR
$cargoLinkerVariable = 'CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER'
$previousCargoLinker = [Environment]::GetEnvironmentVariable($cargoLinkerVariable, 'Process')
$previousNativeLibraryPath = [Environment]::GetEnvironmentVariable('LIB', 'Process')
Push-Location (Split-Path -Parent $rustManifest)
try {
    $env:CARGO_TARGET_DIR = $rustTarget
    [Environment]::SetEnvironmentVariable($cargoLinkerVariable, $nativeToolchain.cargo_linker, 'Process')
    [Environment]::SetEnvironmentVariable('LIB', $nativeToolchain.cargo_native_library_path, 'Process')
    & $cargo "+$rustToolchain" build --release --frozen
    if ($LASTEXITCODE -ne 0) { throw "Rust static build failed with exit code $LASTEXITCODE" }
} finally {
    if ($null -eq $previousTarget) { Remove-Item Env:CARGO_TARGET_DIR -ErrorAction SilentlyContinue } else { $env:CARGO_TARGET_DIR = $previousTarget }
    [Environment]::SetEnvironmentVariable($cargoLinkerVariable, $previousCargoLinker, 'Process')
    [Environment]::SetEnvironmentVariable('LIB', $previousNativeLibraryPath, 'Process')
    Pop-Location
}
Copy-Item -LiteralPath (Join-Path $rustTarget 'release\baxy-rust-slice.exe') -Destination (Join-Path $rustCore 'baxy-rust-slice.exe') -Force

$buildSummary = [ordered]@{
    schema_version = 1
    dotnet_sdk = $dotnetVersion
    rustc = $rustVersion
    native_link_toolchain = $nativeToolchain.identity
    reproduction_classification = [ordered]@{
        host_scope = 'single_host'
        output_root_isolated = $true
        source_replica_isolation = 'provided_by_reproducibility_harness'
        global_package_caches = 'shared_host_caches'
        clean_environment = $false
        cross_host = $false
    }
    output_root = $OutputRoot
    outputs = [ordered]@{
        wpf_fdd = $fdd
        wpf_self_contained = $shell
        dotnet_native_aot = $dotnetCore
        rust_static = $rustCore
    }
}
$buildSummary | ConvertTo-Json -Depth 10
Write-Output ('BAXY_ROUND_B_BUILD_METADATA=' + ($buildSummary | ConvertTo-Json -Depth 10 -Compress))
