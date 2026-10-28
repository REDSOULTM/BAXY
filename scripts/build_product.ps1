param(
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release',
    [string]$OutputRoot,
    [ValidatePattern('^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-(0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)(\.(0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?\z')]
    [string]$Version = '1.1.0',
    [switch]$AllowDirtyDevelopmentBuild
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

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

# A dirty worktree is refused before anything else runs: the helpers below compile C# types
# (Add-Type spawns csc.exe and cvtres.exe) and resolve runtime assets, which the refusal never needs.
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$initialGit = Get-GitState -RepositoryRoot $root
if ($initialGit.dirty -and -not $AllowDirtyDevelopmentBuild) {
    throw 'The Git worktree is dirty. Refusing to build until it is clean; use -AllowDirtyDevelopmentBuild only for an explicitly non-release development artifact.'
}

. (Join-Path $PSScriptRoot 'path_safety.ps1')
. (Join-Path $PSScriptRoot 'product_build_common.ps1')

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
    Use-BaxyVisualStudioInstallerPath

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
