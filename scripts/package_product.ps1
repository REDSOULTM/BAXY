param(
    [string]$BuildRoot,
    [string]$OutputRoot,
    [switch]$AllowDirtyDevelopmentBuild
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'path_safety.ps1')
. (Join-Path $PSScriptRoot 'product_build_common.ps1')

function Test-PathEqualOrDescendant {
    param(
        [Parameter(Mandatory = $true)][string]$Parent,
        [Parameter(Mandatory = $true)][string]$Candidate
    )

    $parentFull = [IO.Path]::GetFullPath($Parent).TrimEnd('\', '/')
    $candidateFull = [IO.Path]::GetFullPath($Candidate).TrimEnd('\', '/')
    return [string]::Equals($parentFull, $candidateFull, [StringComparison]::OrdinalIgnoreCase) -or
        $candidateFull.StartsWith($parentFull + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
}

function Get-StreamSha256 {
    param([Parameter(Mandatory = $true)][IO.Stream]$Stream)

    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($Stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        $algorithm.Dispose()
    }
}

function New-DeterministicProductZip {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object[]]$Entries,
        [Parameter(Mandatory = $true)][DateTimeOffset]$Timestamp
    )

    $ordered = @(Sort-BaxyFileRecordsOrdinal -Records $Entries)
    $sources = New-Object 'BaxyStoredZipSource[]' $ordered.Count
    for ($index = 0; $index -lt $ordered.Count; $index++) {
        $entry = $ordered[$index]
        Assert-BaxySafeRelativePath -Path ([string]$entry.path)
        $source = New-Object BaxyStoredZipSource
        $source.Name = [string]$entry.path
        if ($null -ne $entry.file_path) { $source.FilePath = [string]$entry.file_path }
        if ($null -ne $entry.content_bytes) { $source.ContentBytes = [byte[]]$entry.content_bytes }
        $sources[$index] = $source
    }
    [BaxyStoredZipWriter]::Write($Path, $sources, $Timestamp.UtcDateTime)
}

function Assert-DeterministicProductZip {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object[]]$ExpectedEntries,
        [Parameter(Mandatory = $true)][DateTimeOffset]$Timestamp
    )

    Add-Type -AssemblyName System.IO.Compression
    [BaxyZipStorageInspector]::AssertStored($Path)
    $orderedExpected = @(Sort-BaxyFileRecordsOrdinal -Records $ExpectedEntries)
    $lookup = New-Object 'Collections.Generic.Dictionary[string,object]' ([StringComparer]::Ordinal)
    foreach ($expected in $orderedExpected) { $lookup.Add([string]$expected.path, $expected) }

    $fileStream = New-Object IO.FileStream($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $archive = New-Object IO.Compression.ZipArchive($fileStream, [IO.Compression.ZipArchiveMode]::Read, $true)
        try {
            $entries = @($archive.Entries)
            if ($entries.Count -ne $orderedExpected.Count) { throw 'ZIP entry set does not match the expected package set.' }
            $caseInsensitivePaths = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
            for ($index = 0; $index -lt $entries.Count; $index++) {
                $entry = $entries[$index]
                $pathInZip = [string]$entry.FullName
                Assert-BaxySafeRelativePath -Path $pathInZip
                if (-not $caseInsensitivePaths.Add($pathInZip)) { throw "Duplicate ZIP path under Windows comparison rules: $pathInZip" }
                if (-not [string]::Equals($pathInZip, [string]$orderedExpected[$index].path, [StringComparison]::Ordinal)) {
                    throw 'ZIP entries are not in canonical ordinal order.'
                }
                if ($entry.ExternalAttributes -ne 0) { throw "ZIP entry has non-canonical attributes: $pathInZip" }
                $entryTime = $entry.LastWriteTime
                if ($entryTime.Year -ne $Timestamp.Year -or $entryTime.Month -ne $Timestamp.Month -or
                    $entryTime.Day -ne $Timestamp.Day -or $entryTime.Hour -ne $Timestamp.Hour -or
                    $entryTime.Minute -ne $Timestamp.Minute -or $entryTime.Second -ne $Timestamp.Second) {
                    throw "ZIP entry has a non-canonical timestamp: $pathInZip"
                }
                $expected = $lookup[$pathInZip]
                if ([int64]$entry.Length -ne [int64]$expected.bytes) { throw "ZIP entry length mismatch: $pathInZip" }
                $stream = $entry.Open()
                try { $actualHash = Get-StreamSha256 -Stream $stream } finally { $stream.Dispose() }
                if (-not [string]::Equals($actualHash, [string]$expected.sha256, [StringComparison]::Ordinal)) {
                    throw "ZIP entry SHA-256 mismatch: $pathInZip"
                }
            }
        } finally {
            $archive.Dispose()
        }
    } finally {
        $fileStream.Dispose()
    }
}

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$allowedBuildRoot = [IO.Path]::GetFullPath((Join-Path $root 'artifacts\product\build'))
if ([string]::IsNullOrWhiteSpace($BuildRoot)) {
    $BuildRoot = Join-Path $allowedBuildRoot (
        "local-$($script:BaxyRuntimeIdentifier)")
}
if ([string]::IsNullOrWhiteSpace($OutputRoot)) { $OutputRoot = Join-Path $allowedBuildRoot 'packages' }
$BuildRoot = [IO.Path]::GetFullPath($BuildRoot)
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
Assert-StrictDescendantPath -Parent $allowedBuildRoot -Child $BuildRoot
Assert-StrictDescendantPath -Parent $allowedBuildRoot -Child $OutputRoot
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $allowedBuildRoot
if ((Test-PathEqualOrDescendant -Parent $BuildRoot -Candidate $OutputRoot) -or
    (Test-PathEqualOrDescendant -Parent $OutputRoot -Candidate $BuildRoot)) {
    throw 'BuildRoot and OutputRoot must be separate sibling trees.'
}

$validated = Get-BaxyValidatedBuildManifest -BuildRoot $BuildRoot
$manifest = $validated.manifest
$isRelease = [string]::Equals([string]$manifest.configuration, 'Release', [StringComparison]::Ordinal)
$isHeadSnapshot = [string]::Equals([string]$manifest.source.provenance, 'git_head_snapshot', [StringComparison]::Ordinal)
$developmentArtifact = [bool]$manifest.source.dirty -or -not $isRelease -or -not $isHeadSnapshot
if ($developmentArtifact -and -not $AllowDirtyDevelopmentBuild) {
    throw 'Refusing to package a dirty or non-Release build without -AllowDirtyDevelopmentBuild.'
}

$shortCommit = ([string]$manifest.source.commit).Substring(0, 12)
$qualifiers = ''
if (-not $isRelease) { $qualifiers += '-debug' }
if ([bool]$manifest.source.dirty) { $qualifiers += '-dirty' }
$packageFileName = (
    "BAXY-$($manifest.version)-$shortCommit$qualifiers-$($manifest.runtime).zip")
Assert-BaxySafeRelativePath -Path $packageFileName

$checksumRecords = @()
foreach ($record in @($validated.files)) {
    $checksumRecords += [pscustomobject][ordered]@{
        path = [string]$record.path
        bytes = [int64]$record.bytes
        sha256 = [string]$record.sha256
        file_path = Join-Path $validated.payload_root ([string]$record.path).Replace('/', '\')
        content_bytes = $null
    }
}
$manifestBytes = [byte[]]$validated.manifest_bytes
$checksumRecords += [pscustomobject][ordered]@{
    path = 'build-manifest.json'
    bytes = [int64]$manifestBytes.Length
    sha256 = [string]$validated.manifest_sha256
    file_path = $null
    content_bytes = [byte[]]$manifestBytes
}
$checksumRecords = @(Sort-BaxyFileRecordsOrdinal -Records $checksumRecords)
$checksumText = [string](($checksumRecords | ForEach-Object { "$($_.sha256)  $($_.path)" }) -join "`n") + "`n"
$checksumBytes = $script:BaxyUtf8NoBom.GetBytes($checksumText)
$checksumHash = Get-BaxyBytesSha256 -Bytes $checksumBytes

$zipEntries = @($checksumRecords)
$zipEntries += [pscustomobject][ordered]@{
    path = 'SHA256SUMS'
    bytes = [int64]$checksumBytes.Length
    sha256 = $checksumHash
    file_path = $null
    content_bytes = [byte[]]$checksumBytes
}
$zipEntries = @(Sort-BaxyFileRecordsOrdinal -Records $zipEntries)
$timestamp = Get-BaxyFixedZipTimestamp -SourceDateEpoch ([int64]$manifest.source.source_date_epoch)

$stagingRoot = Join-Path $allowedBuildRoot ('.package-staging-' + [Guid]::NewGuid().ToString('N'))
$stagingPackagePath = Join-Path $stagingRoot $packageFileName
$stagingDigestPath = $stagingPackagePath + '.sha256'
$promoted = $false
$primaryFailure = $null
$result = $null
try {
    if (Test-Path -LiteralPath $stagingRoot) { throw "Package staging path unexpectedly exists: $stagingRoot" }
    New-Item -ItemType Directory -Path $stagingRoot | Out-Null
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $stagingRoot
    New-DeterministicProductZip -Path $stagingPackagePath -Entries $zipEntries -Timestamp $timestamp
    Assert-DeterministicProductZip -Path $stagingPackagePath -ExpectedEntries $zipEntries -Timestamp $timestamp
    $stagingSha256 = Get-BaxySha256 -Path $stagingPackagePath
    $digestText = "$stagingSha256  $packageFileName`n"
    Write-BaxyUtf8NoBom -Path $stagingDigestPath -Text $digestText
    Assert-DeterministicProductZip -Path $stagingPackagePath -ExpectedEntries $zipEntries -Timestamp $timestamp
    if (-not [string]::Equals((Read-BaxyUtf8NoBom -Path $stagingDigestPath), $digestText, [StringComparison]::Ordinal)) {
        throw 'Staged package digest sidecar failed verification.'
    }
    Assert-TreeHasNoReparsePoint -Root $stagingRoot
    Assert-BaxyNoAlternateDataStreams -Root $stagingRoot
    if (@(Get-ChildItem -LiteralPath $stagingRoot -File -Recurse -Force).Count -ne 2) {
        throw 'Staged package output contains unexpected files.'
    }

    Move-BaxyDirectoryAtomically -AllowedRoot $allowedBuildRoot -Source $stagingRoot -Destination $OutputRoot
    $promoted = $true
    $packagePath = Join-Path $OutputRoot $packageFileName
    $digestPath = $packagePath + '.sha256'

    Assert-DeterministicProductZip -Path $packagePath -ExpectedEntries $zipEntries -Timestamp $timestamp
    $packageSha256 = Get-BaxySha256 -Path $packagePath
    $expectedDigestText = "$packageSha256  $packageFileName`n"
    if (-not [string]::Equals((Read-BaxyUtf8NoBom -Path $digestPath), $expectedDigestText, [StringComparison]::Ordinal)) {
        throw 'Promoted package digest sidecar failed verification.'
    }
    Assert-TreeHasNoReparsePoint -Root $OutputRoot
    Assert-BaxyNoAlternateDataStreams -Root $OutputRoot
    if (@(Get-ChildItem -LiteralPath $OutputRoot -File -Recurse -Force).Count -ne 2) {
        throw 'Promoted package output contains unexpected files.'
    }
    Assert-DeterministicProductZip -Path $packagePath -ExpectedEntries $zipEntries -Timestamp $timestamp
    $secondPackageSha256 = Get-BaxySha256 -Path $packagePath
    if (-not [string]::Equals($packageSha256, $secondPackageSha256, [StringComparison]::Ordinal) -or
        -not [string]::Equals((Read-BaxyUtf8NoBom -Path $digestPath), $expectedDigestText, [StringComparison]::Ordinal)) {
        throw 'Package bytes or digest changed during final verification.'
    }

    $result = [ordered]@{
        package = $packagePath
        package_sha256 = $packageSha256
        package_bytes = [int64](Get-Item -LiteralPath $packagePath).Length
        digest = $digestPath
        commit = [string]$manifest.source.commit
        dirty = [bool]$manifest.source.dirty
        source_provenance = [string]$manifest.source.provenance
    }
} catch {
    $primaryFailure = $_
}

$cleanupFailures = New-Object 'System.Collections.Generic.List[string]'
if (Test-Path -LiteralPath $stagingRoot) {
    try { Remove-TreeFailClosed -AllowedRoot $allowedBuildRoot -Target $stagingRoot } catch { $cleanupFailures.Add($_.Exception.Message) }
}
if ($null -ne $primaryFailure -and $promoted -and (Test-Path -LiteralPath $OutputRoot)) {
    try { Remove-TreeFailClosed -AllowedRoot $allowedBuildRoot -Target $OutputRoot } catch { $cleanupFailures.Add($_.Exception.Message) }
}
if ($null -ne $primaryFailure) {
    if ($cleanupFailures.Count -gt 0) {
        throw "Packaging failed: $($primaryFailure.Exception.Message) Cleanup also failed closed: $($cleanupFailures -join '; ')"
    }
    throw $primaryFailure
}
if ($cleanupFailures.Count -gt 0) { throw "Packaging completed, but cleanup failed closed: $($cleanupFailures -join '; ')" }
$result | ConvertTo-Json -Compress
