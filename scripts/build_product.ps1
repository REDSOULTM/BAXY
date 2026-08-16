param(
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release',
    [string]$OutputRoot,
    [string]$MpvPath,
    [string]$VulkanLoaderPath,
    [string]$YtDlpPath,
    [ValidatePattern('^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-(0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)(\.(0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?\z')]
    [string]$Version = '1.0.8',
    [switch]$AllowDirtyDevelopmentBuild
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'path_safety.ps1')
. (Join-Path $PSScriptRoot 'product_build_common.ps1')
. (Join-Path $PSScriptRoot 'asset_resolver.ps1')

function Get-GitState {
    param([Parameter(Mandatory = $true)][string]$RepositoryRoot)

    $commit = [string](& git -C $RepositoryRoot rev-parse --verify HEAD)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve the source Git commit.' }
    $commit = $commit.Trim().ToLowerInvariant()
    if ($commit -notmatch '^[0-9a-f]{40}$') { throw "Unexpected Git commit identity: $commit" }
    $statusLines = @(& git -C $RepositoryRoot status --porcelain=v1 --untracked-files=all)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect the source Git worktree.' }
    return [pscustomobject][ordered]@{
        commit = $commit
        dirty = [bool]($statusLines.Count -gt 0)
        status = [string]($statusLines -join "`n")
    }
}

function Assert-DetachedSnapshotUnchanged {
    param(
        [Parameter(Mandatory = $true)][string]$SnapshotRoot,
        [Parameter(Mandatory = $true)][string]$Commit
    )

    $actualCommit = ([string](& git -C $SnapshotRoot rev-parse --verify HEAD)).Trim().ToLowerInvariant()
    if ($LASTEXITCODE -ne 0 -or -not [string]::Equals($actualCommit, $Commit, [StringComparison]::Ordinal)) {
        throw 'Detached source snapshot commit changed during the build.'
    }
    $status = @(& git -C $SnapshotRoot status --porcelain=v1 --untracked-files=all)
    if ($LASTEXITCODE -ne 0 -or $status.Count -ne 0) {
        throw 'Detached source snapshot changed during the build.'
    }
}

function Invoke-DotnetChecked {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    & dotnet @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$FailureMessage (exit code $LASTEXITCODE)." }
}

function Resolve-BaxyRuntimeTool {
    param(
        [string]$ConfiguredPath,
        [Parameter(Mandatory = $true)][string]$EnvironmentName,
        [AllowEmptyString()][string]$DefaultPath,
        [Parameter(Mandatory = $true)][string]$ExpectedFileName
    )

    $candidate = $ConfiguredPath
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $candidate = [Environment]::GetEnvironmentVariable($EnvironmentName, 'Process')
    }
    if ([string]::IsNullOrWhiteSpace($candidate)) { $candidate = $DefaultPath }
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        throw "Required runtime tool is missing: $ExpectedFileName"
    }
    $full = [IO.Path]::GetFullPath($candidate)
    if (-not [string]::Equals([IO.Path]::GetFileName($full), $ExpectedFileName, [StringComparison]::OrdinalIgnoreCase) -or
        -not (Test-Path -LiteralPath $full -PathType Leaf)) {
        throw "Required runtime tool is missing or has the wrong identity: $ExpectedFileName"
    }
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $full
    $length = [int64](Get-Item -LiteralPath $full -Force).Length
    if ($length -le 0 -or $length -gt 128MB) {
        throw "Required runtime tool has an invalid size: $ExpectedFileName"
    }
    return $full
}

function Copy-BaxyRuntimeToolBytes {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $input = New-Object IO.FileStream(
        $Source, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $output = New-Object IO.FileStream(
            $Destination, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $input.CopyTo($output) } finally { $output.Dispose() }
    } finally {
        $input.Dispose()
    }
}

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$mpvResolution = Resolve-BaxyAsset -Name 'mpv' -RepositoryRoot $root
$vulkanResolution = Resolve-BaxyAsset -Name 'mpv_vulkan' -RepositoryRoot $root
$ytDlpResolution = Resolve-BaxyAsset -Name 'yt_dlp' -RepositoryRoot $root
$MpvPath = Resolve-BaxyRuntimeTool `
    -ConfiguredPath $MpvPath `
    -EnvironmentName 'BAXY_MPV_PATH' `
    -DefaultPath ([string]$mpvResolution.Path) `
    -ExpectedFileName 'mpv.exe'
$VulkanLoaderPath = Resolve-BaxyRuntimeTool `
    -ConfiguredPath $VulkanLoaderPath `
    -EnvironmentName 'BAXY_MPV_VULKAN_PATH' `
    -DefaultPath ([string]$vulkanResolution.Path) `
    -ExpectedFileName 'vulkan-1.dll'
$YtDlpPath = Resolve-BaxyRuntimeTool `
    -ConfiguredPath $YtDlpPath `
    -EnvironmentName 'BAXY_YTDLP_PATH' `
    -DefaultPath ([string]$ytDlpResolution.Path) `
    -ExpectedFileName 'yt-dlp.exe'
$allowedBuildRoot = [IO.Path]::GetFullPath((Join-Path $root 'artifacts\product\build'))
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $allowedBuildRoot (
        "local-$($script:BaxyRuntimeIdentifier)")
}
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
Assert-StrictDescendantPath -Parent $allowedBuildRoot -Child $OutputRoot
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $allowedBuildRoot

$isDebug = [string]::Equals($Configuration, 'Debug', [StringComparison]::Ordinal)
$isRelease = [string]::Equals($Configuration, 'Release', [StringComparison]::Ordinal)
if (-not $isDebug -and -not $isRelease) { throw 'Configuration must use canonical casing: Debug or Release.' }

$initialGit = Get-GitState -RepositoryRoot $root
if ($initialGit.dirty -and -not $AllowDirtyDevelopmentBuild) {
    throw 'The Git worktree is dirty. Refusing to build until it is clean; use -AllowDirtyDevelopmentBuild only for an explicitly non-release development artifact.'
}

$epochText = [string](& git -C $root show -s --format=%ct $initialGit.commit)
if ($LASTEXITCODE -ne 0 -or $epochText.Trim() -notmatch '^[0-9]+$') { throw 'Unable to resolve source_date_epoch from Git.' }
$sourceDateEpoch = [int64]$epochText.Trim()
$shortCommit = $initialGit.commit.Substring(0, 12)
$informationalVersion = if ($Version.Contains('+')) { "$Version.sha.$shortCommit" } else { "$Version+$shortCommit" }
if ($initialGit.dirty) { $informationalVersion += '.dirty' }

$sourceRoot = $root
$sourceSnapshotRoot = $null
$sourceProvenance = if ($initialGit.dirty) { 'working_tree_development' } else { 'working_tree_clean' }
$stagingRoot = Join-Path $allowedBuildRoot ('.build-staging-' + [Guid]::NewGuid().ToString('N'))
$appOutput = Join-Path $stagingRoot 'app'
$coreOutput = Join-Path $appOutput 'core'
$previousSourceDateEpoch = [Environment]::GetEnvironmentVariable('SOURCE_DATE_EPOCH', 'Process')
$promoted = $false
$primaryFailure = $null
$result = $null

try {
    if ($isRelease -and -not $initialGit.dirty) {
        $sourceSnapshotRoot = Join-Path $allowedBuildRoot ('.source-snapshot-' + [Guid]::NewGuid().ToString('N'))
        $sourceRoot = New-BaxyHeadWorktreeSnapshot `
            -RepositoryRoot $root `
            -AllowedRoot $allowedBuildRoot `
            -SnapshotRoot $sourceSnapshotRoot `
            -Commit $initialGit.commit
        $sourceProvenance = 'git_head_snapshot'
    }

    $appProject = Join-Path $sourceRoot 'src\Baxy.App\Baxy.App.csproj'
    $coreProject = Join-Path $sourceRoot 'src\Baxy.Core\Baxy.Core.csproj'
    if (Test-Path -LiteralPath $stagingRoot) { throw "Build staging path unexpectedly exists: $stagingRoot" }
    New-Item -ItemType Directory -Path $coreOutput | Out-Null
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $stagingRoot
    [Environment]::SetEnvironmentVariable('SOURCE_DATE_EPOCH', [string]$sourceDateEpoch, 'Process')

    Push-Location $sourceRoot
    try {
        $dotnetSdk = [string](& dotnet --version)
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($dotnetSdk)) { throw 'Unable to resolve the .NET SDK version.' }
        $dotnetSdk = $dotnetSdk.Trim()

        Invoke-DotnetChecked -FailureMessage 'Core restore failed' -Arguments @(
            'restore', $coreProject, '-r', $script:BaxyRuntimeIdentifier,
            '--ignore-failed-sources', '-p:NuGetAudit=false', '--nologo'
        )
        Invoke-DotnetChecked -FailureMessage 'Core NativeAOT publish failed' -Arguments @(
            'publish', $coreProject, '-c', $Configuration, '-r', $script:BaxyRuntimeIdentifier,
            '--self-contained', 'true', '--no-restore', '-o', $coreOutput, '--nologo',
            '-p:PublishAot=true', '-p:StripSymbols=true', '-p:DebugType=none',
            '-p:DebugSymbols=false', '-p:NativeDebugSymbols=false',
            '-p:CopyOutputSymbolsToPublishDirectory=false',
            '-p:ContinuousIntegrationBuild=true', '-p:Deterministic=true',
            "-p:PathMap=$sourceRoot=/_/baxy", "-p:Version=$Version",
            "-p:InformationalVersion=$informationalVersion", "-p:SourceRevisionId=$($initialGit.commit)"
        )

        Invoke-DotnetChecked -FailureMessage 'App restore failed' -Arguments @(
            'restore', $appProject, '-r', $script:BaxyRuntimeIdentifier,
            '--ignore-failed-sources', '-p:NuGetAudit=false', '--nologo'
        )
        Invoke-DotnetChecked -FailureMessage 'WPF self-contained single-file publish failed' -Arguments @(
            'publish', $appProject, '-c', $Configuration, '-r', $script:BaxyRuntimeIdentifier,
            '--self-contained', 'true', '--no-restore', '-o', $appOutput, '--nologo',
            '-p:PublishSingleFile=true', '-p:EnableCompressionInSingleFile=true',
            '-p:IncludeNativeLibrariesForSelfExtract=false', '-p:DebugType=none',
            '-p:DebugSymbols=false', '-p:CopyOutputSymbolsToPublishDirectory=false',
            '-p:ContinuousIntegrationBuild=true', '-p:Deterministic=true',
            "-p:PathMap=$sourceRoot=/_/baxy", "-p:Version=$Version",
            "-p:InformationalVersion=$informationalVersion", "-p:SourceRevisionId=$($initialGit.commit)"
        )
    } finally {
        Pop-Location
    }

    $mpvOutput = Join-Path $appOutput 'tools\mpv'
    $ytDlpOutput = Join-Path $appOutput 'tools\yt-dlp'
    New-Item -ItemType Directory -Path $mpvOutput -Force | Out-Null
    New-Item -ItemType Directory -Path $ytDlpOutput -Force | Out-Null
    Copy-BaxyRuntimeToolBytes -Source $MpvPath -Destination (Join-Path $mpvOutput 'mpv.exe')
    Copy-BaxyRuntimeToolBytes -Source $VulkanLoaderPath -Destination (Join-Path $mpvOutput 'vulkan-1.dll')
    Copy-BaxyRuntimeToolBytes -Source $YtDlpPath -Destination (Join-Path $ytDlpOutput 'yt-dlp.exe')

    $files = @(Get-BaxyPayloadFileRecords -PayloadRoot $appOutput)
    Assert-BaxyExactProductPayloadFileSet -Files $files

    if ($null -ne $sourceSnapshotRoot) {
        Assert-DetachedSnapshotUnchanged -SnapshotRoot $sourceSnapshotRoot -Commit $initialGit.commit
    } else {
        $finalGit = Get-GitState -RepositoryRoot $root
        if (-not [string]::Equals($initialGit.commit, $finalGit.commit, [StringComparison]::Ordinal) -or
            -not [string]::Equals($initialGit.status, $finalGit.status, [StringComparison]::Ordinal)) {
            throw 'The live source Git state changed while the development product was being built.'
        }
    }

    $manifest = New-BaxyBuildManifest `
        -Version $Version `
        -Configuration $Configuration `
        -Commit $initialGit.commit `
        -Dirty ([bool]$initialGit.dirty) `
        -SourceProvenance $sourceProvenance `
        -SourceDateEpoch $sourceDateEpoch `
        -DotnetSdk $dotnetSdk `
        -PowerShellVersion ($PSVersionTable.PSVersion.ToString()) `
        -Files $files
    Write-BaxyUtf8NoBom -Path (Join-Path $stagingRoot 'build-manifest.json') -Text (ConvertTo-BaxyCanonicalJson -Value $manifest)
    $null = Get-BaxyValidatedBuildManifest -BuildRoot $stagingRoot

    Move-BaxyDirectoryAtomically -AllowedRoot $allowedBuildRoot -Source $stagingRoot -Destination $OutputRoot
    $promoted = $true
    $validated = Get-BaxyValidatedBuildManifest -BuildRoot $OutputRoot

    $result = [ordered]@{
        app = Join-Path $OutputRoot 'app\Baxy.exe'
        core = Join-Path $OutputRoot 'app\core\baxy-core.exe'
        manifest = Join-Path $OutputRoot 'build-manifest.json'
        files = [int]$validated.manifest.file_count
        bytes = [int64]$validated.manifest.total_bytes
        output = $OutputRoot
        commit = $initialGit.commit
        dirty = [bool]$initialGit.dirty
        source_provenance = $sourceProvenance
    }
} catch {
    $primaryFailure = $_
}

$cleanupFailures = New-Object 'System.Collections.Generic.List[string]'
[Environment]::SetEnvironmentVariable('SOURCE_DATE_EPOCH', $previousSourceDateEpoch, 'Process')
if (Test-Path -LiteralPath $stagingRoot) {
    try { Remove-TreeFailClosed -AllowedRoot $allowedBuildRoot -Target $stagingRoot } catch { $cleanupFailures.Add($_.Exception.Message) }
}
if ($null -ne $primaryFailure -and $promoted -and (Test-Path -LiteralPath $OutputRoot)) {
    try { Remove-TreeFailClosed -AllowedRoot $allowedBuildRoot -Target $OutputRoot } catch { $cleanupFailures.Add($_.Exception.Message) }
}
if ($null -ne $sourceSnapshotRoot) {
    try {
        Remove-BaxyHeadWorktreeSnapshot -RepositoryRoot $root -AllowedRoot $allowedBuildRoot -SnapshotRoot $sourceSnapshotRoot
    } catch {
        $cleanupFailures.Add($_.Exception.Message)
    }
}

if ($null -ne $primaryFailure) {
    if ($cleanupFailures.Count -gt 0) {
        throw "Build failed: $($primaryFailure.Exception.Message) Cleanup also failed closed: $($cleanupFailures -join '; ')"
    }
    throw $primaryFailure
}
if ($cleanupFailures.Count -gt 0) { throw "Build completed, but cleanup failed closed: $($cleanupFailures -join '; ')" }
$result | ConvertTo-Json -Compress
