param(
    [string]$PackageRoot,
    [string]$OutputRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'path_safety.ps1')
. (Join-Path $PSScriptRoot 'product_build_common.ps1')

$script:BaxySetupManifestSchema = 'baxy-setup-build-v2'
$script:BaxyEmbeddedAttestationSchema = 'baxy-setup-embedded-package-v2'
$script:BaxyEmbeddedEvidenceSchema = 'baxy-setup-embedded-verification-v2'
$script:BaxyDataSchema = 1
$script:BaxySetupFileName = 'Baxy.Setup.exe'
$script:BaxySetupManifestFileName = 'setup-manifest.json'
$script:BaxySetupChecksumsFileName = 'SHA256SUMS'
$script:BaxyMaximumPackageBytes = 256L * 1024L * 1024L
$script:BaxyMaximumPayloadFileBytes = 128L * 1024L * 1024L
$script:BaxyMaximumManifestBytes = 256 * 1024
$script:BaxyMaximumChecksumBytes = 64 * 1024
$script:BaxyMaximumVersionLength = 128
$script:BaxyPackagePayloadPaths = @(
    'Baxy.exe',
    'D3DCompiler_47_cor3.dll',
    'DesktopClickVisible.ps1',
    'DesktopKeyPress.ps1',
    'DesktopSelectAll.ps1',
    'FieldUi/assets/index-CjozYCnU.css',
    'FieldUi/assets/index-D3QuhrLm.js',
    'FieldUi/index.html',
    'FieldUiHost/field-native-bridge.js',
    'KnownFileOpen.ps1',
    'KnownFolderOpen.ps1',
    'Microsoft.Web.WebView2.Core.xml',
    'Microsoft.Web.WebView2.WinForms.xml',
    'Microsoft.Web.WebView2.Wpf.xml',
    'PenImc_cor3.dll',
    'PresentationNative_cor3.dll',
    'SpotifyDesktopAutomation.ps1',
    'SpotifyMediaControl.ps1',
    'WebView2Loader.dll',
    'WindowsScheduledNotification.ps1',
    'core/DesktopClickVisible.ps1',
    'core/DesktopKeyPress.ps1',
    'core/DesktopSelectAll.ps1',
    'core/KnownFileOpen.ps1',
    'core/KnownFolderOpen.ps1',
    'core/SpotifyDesktopAutomation.ps1',
    'core/SpotifyMediaControl.ps1',
    'core/WindowsScheduledNotification.ps1',
    'core/baxy-core.exe',
    'runtimes/win-x64/native/WebView2Loader.dll',
    'tools/mpv/mpv.exe',
    'tools/mpv/vulkan-1.dll',
    'tools/yt-dlp/yt-dlp.exe',
    'vcruntime140_cor3.dll',
    'wpfgfx_cor3.dll'
)
$script:BaxyPackageChecksumPaths = @(
    'Baxy.exe',
    'D3DCompiler_47_cor3.dll',
    'DesktopClickVisible.ps1',
    'DesktopKeyPress.ps1',
    'DesktopSelectAll.ps1',
    'FieldUi/assets/index-CjozYCnU.css',
    'FieldUi/assets/index-D3QuhrLm.js',
    'FieldUi/index.html',
    'FieldUiHost/field-native-bridge.js',
    'KnownFileOpen.ps1',
    'KnownFolderOpen.ps1',
    'Microsoft.Web.WebView2.Core.xml',
    'Microsoft.Web.WebView2.WinForms.xml',
    'Microsoft.Web.WebView2.Wpf.xml',
    'PenImc_cor3.dll',
    'PresentationNative_cor3.dll',
    'SpotifyDesktopAutomation.ps1',
    'SpotifyMediaControl.ps1',
    'WebView2Loader.dll',
    'WindowsScheduledNotification.ps1',
    'build-manifest.json',
    'core/DesktopClickVisible.ps1',
    'core/DesktopKeyPress.ps1',
    'core/DesktopSelectAll.ps1',
    'core/KnownFileOpen.ps1',
    'core/KnownFolderOpen.ps1',
    'core/SpotifyDesktopAutomation.ps1',
    'core/SpotifyMediaControl.ps1',
    'core/WindowsScheduledNotification.ps1',
    'core/baxy-core.exe',
    'runtimes/win-x64/native/WebView2Loader.dll',
    'tools/mpv/mpv.exe',
    'tools/mpv/vulkan-1.dll',
    'tools/yt-dlp/yt-dlp.exe',
    'vcruntime140_cor3.dll',
    'wpfgfx_cor3.dll'
)
$script:BaxyPackageZipPaths = @(
    'Baxy.exe',
    'D3DCompiler_47_cor3.dll',
    'DesktopClickVisible.ps1',
    'DesktopKeyPress.ps1',
    'DesktopSelectAll.ps1',
    'FieldUi/assets/index-CjozYCnU.css',
    'FieldUi/assets/index-D3QuhrLm.js',
    'FieldUi/index.html',
    'FieldUiHost/field-native-bridge.js',
    'KnownFileOpen.ps1',
    'KnownFolderOpen.ps1',
    'Microsoft.Web.WebView2.Core.xml',
    'Microsoft.Web.WebView2.WinForms.xml',
    'Microsoft.Web.WebView2.Wpf.xml',
    'PenImc_cor3.dll',
    'PresentationNative_cor3.dll',
    'SHA256SUMS',
    'SpotifyDesktopAutomation.ps1',
    'SpotifyMediaControl.ps1',
    'WebView2Loader.dll',
    'WindowsScheduledNotification.ps1',
    'build-manifest.json',
    'core/DesktopClickVisible.ps1',
    'core/DesktopKeyPress.ps1',
    'core/DesktopSelectAll.ps1',
    'core/KnownFileOpen.ps1',
    'core/KnownFolderOpen.ps1',
    'core/SpotifyDesktopAutomation.ps1',
    'core/SpotifyMediaControl.ps1',
    'core/WindowsScheduledNotification.ps1',
    'core/baxy-core.exe',
    'runtimes/win-x64/native/WebView2Loader.dll',
    'tools/mpv/mpv.exe',
    'tools/mpv/vulkan-1.dll',
    'tools/yt-dlp/yt-dlp.exe',
    'vcruntime140_cor3.dll',
    'wpfgfx_cor3.dll'
)

function Get-BaxySetupGitState {
    param([Parameter(Mandatory = $true)][string]$RepositoryRoot)

    $commit = [string](& git -C $RepositoryRoot rev-parse --verify HEAD)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve the Setup source Git commit.' }
    $commit = $commit.Trim().ToLowerInvariant()
    if ($commit -notmatch '^[0-9a-f]{40}$') { throw "Unexpected Git commit identity: $commit" }
    $statusLines = @(& git -C $RepositoryRoot status --porcelain=v1 --untracked-files=all)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect the Setup source Git worktree.' }
    return [pscustomobject][ordered]@{
        commit = $commit
        dirty = [bool]($statusLines.Count -gt 0)
        status = [string]($statusLines -join "`n")
    }
}

function Assert-BaxySetupSnapshotUnchanged {
    param(
        [Parameter(Mandatory = $true)][string]$SnapshotRoot,
        [Parameter(Mandatory = $true)][string]$Commit
    )

    $actualCommit = ([string](& git -C $SnapshotRoot rev-parse --verify HEAD)).Trim().ToLowerInvariant()
    if ($LASTEXITCODE -ne 0 -or -not [string]::Equals($actualCommit, $Commit, [StringComparison]::Ordinal)) {
        throw 'Detached Setup source snapshot commit changed during the build.'
    }
    $status = @(& git -C $SnapshotRoot status --porcelain=v1 --untracked-files=all)
    if ($LASTEXITCODE -ne 0 -or $status.Count -ne 0) {
        throw 'Detached Setup source snapshot changed during the build.'
    }
}

function Assert-BaxyMsBuildPathSafe {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Context
    )

    if ($Path.IndexOfAny(@([char]',', [char]';', [char]'%', [char]'=')) -ge 0) {
        throw "$Context contains a character that cannot be represented safely in the deterministic MSBuild command line: $Path"
    }
}

function Invoke-BaxySetupDotnetChecked {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    & dotnet @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$FailureMessage (exit code $LASTEXITCODE)." }
}

function Get-BaxyStreamSha256 {
    param([Parameter(Mandatory = $true)][IO.Stream]$Stream)

    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($Stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        $algorithm.Dispose()
    }
}

function Get-BaxyZipEntryBytes {
    param(
        [Parameter(Mandatory = $true)]$Entry,
        [Parameter(Mandatory = $true)][int64]$MaximumBytes
    )

    if ([int64]$Entry.Length -gt $MaximumBytes) { throw "ZIP metadata entry exceeds its reviewed limit: $($Entry.FullName)" }
    $stream = $Entry.Open()
    try {
        $memory = New-Object IO.MemoryStream
        try {
            $stream.CopyTo($memory)
            return ,([byte[]]$memory.ToArray())
        } finally {
            $memory.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
}

function Get-BaxyPackageContentId {
    param([Parameter(Mandatory = $true)][object[]]$Entries)

    $canonical = New-Object Text.StringBuilder
    foreach ($entry in @(Sort-BaxyFileRecordsOrdinal -Records $Entries)) {
        $null = $canonical.Append([string]$entry.path)
        $null = $canonical.Append([char]0)
        $null = $canonical.Append(([int64]$entry.bytes).ToString([Globalization.CultureInfo]::InvariantCulture))
        $null = $canonical.Append([char]0)
        $null = $canonical.Append([string]$entry.sha256)
        $null = $canonical.Append("`n")
    }
    return Get-BaxyBytesSha256 -Bytes $script:BaxyUtf8NoBom.GetBytes($canonical.ToString())
}

function Get-BaxyValidatedPackageManifest {
    param(
        [Parameter(Mandatory = $true)][byte[]]$ManifestBytes,
        [Parameter(Mandatory = $true)][object[]]$ZipRecords,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit,
        [Parameter(Mandatory = $true)][int64]$ExpectedSourceDateEpoch
    )

    $raw = ConvertFrom-BaxyUtf8NoBomBytes -Bytes $ManifestBytes -Context 'embedded product build-manifest.json'
    try { $manifest = $raw | ConvertFrom-Json -ErrorAction Stop } catch {
        throw "Invalid embedded product build manifest JSON: $($_.Exception.Message)"
    }
    Assert-BaxyPropertySet -Object $manifest -Expected @(
        'schema', 'product', 'version', 'data_schema', 'configuration', 'runtime', 'target_framework',
        'authenticity', 'source', 'toolchain', 'deployment', 'file_count', 'total_bytes', 'files'
    ) -Context 'embedded product build manifest'
    Assert-BaxyPropertySet -Object $manifest.source -Expected @(
        'commit', 'dirty', 'provenance', 'source_date_epoch'
    ) -Context 'embedded product build manifest source'
    Assert-BaxyPropertySet -Object $manifest.toolchain -Expected @('dotnet_sdk', 'powershell') `
        -Context 'embedded product build manifest toolchain'
    Assert-BaxyPropertySet -Object $manifest.deployment -Expected @(
        'app', 'native_libraries', 'core', 'symbols'
    ) -Context 'embedded product build manifest deployment'

    if (-not [string]::Equals([string]$manifest.schema, 'baxy-product-build-v4', [StringComparison]::Ordinal) -or
        -not [string]::Equals([string]$manifest.product, 'BAXY', [StringComparison]::Ordinal) -or
        -not [string]::Equals([string]$manifest.configuration, 'Release', [StringComparison]::Ordinal) -or
        -not [string]::Equals([string]$manifest.runtime, 'win-x64', [StringComparison]::Ordinal) -or
        -not [string]::Equals([string]$manifest.target_framework, 'net10.0-windows10.0.19041.0', [StringComparison]::Ordinal) -or
        -not [string]::Equals([string]$manifest.authenticity, 'not_provided', [StringComparison]::Ordinal)) {
        throw 'Embedded package manifest is not the exact BAXY Release win-x64 v4 contract.'
    }
    $version = [string]$manifest.version
    if ($version.Length -lt 1 -or $version.Length -gt $script:BaxyMaximumVersionLength -or
        $version -notmatch $script:BaxySemVerPattern) {
        throw 'Embedded package manifest has an invalid semantic version.'
    }
    if ($manifest.data_schema -isnot [int] -or [int]$manifest.data_schema -ne $script:BaxyDataSchema) {
        throw 'Embedded package manifest has an unsupported data schema.'
    }
    if ($manifest.source.dirty -isnot [bool] -or [bool]$manifest.source.dirty -or
        -not [string]::Equals([string]$manifest.source.provenance, 'git_head_snapshot', [StringComparison]::Ordinal)) {
        throw 'Embedded package manifest is not a clean Git HEAD snapshot.'
    }
    if (-not [string]::Equals([string]$manifest.source.commit, $ExpectedCommit, [StringComparison]::Ordinal)) {
        throw 'Embedded package commit does not match the clean Setup Git HEAD.'
    }
    if ([int64]$manifest.source.source_date_epoch -ne $ExpectedSourceDateEpoch) {
        throw 'Embedded package source_date_epoch does not match the Setup Git HEAD commit time.'
    }
    if ([string]::IsNullOrWhiteSpace([string]$manifest.toolchain.dotnet_sdk) -or
        [string]::IsNullOrWhiteSpace([string]$manifest.toolchain.powershell)) {
        throw 'Embedded package manifest toolchain is incomplete.'
    }
    if (-not [string]::Equals([string]$manifest.deployment.app, 'self_contained_single_file', [StringComparison]::Ordinal) -or
        -not [string]::Equals([string]$manifest.deployment.native_libraries, 'adjacent_no_self_extraction', [StringComparison]::Ordinal) -or
        -not [string]::Equals([string]$manifest.deployment.core, 'native_aot_self_contained', [StringComparison]::Ordinal) -or
        -not [string]::Equals([string]$manifest.deployment.symbols, 'excluded_from_user_payload', [StringComparison]::Ordinal)) {
        throw 'Embedded package manifest deployment contract is invalid.'
    }

    $records = @()
    $manifestFiles = @($manifest.files)
    if ($manifestFiles.Count -ne $script:BaxyPackagePayloadPaths.Count -or
        [int]$manifest.file_count -ne $script:BaxyPackagePayloadPaths.Count) {
        throw "Embedded package manifest must contain exactly $($script:BaxyPackagePayloadPaths.Count) reviewed payload records."
    }
    foreach ($record in $manifestFiles) {
        Assert-BaxyPropertySet -Object $record -Expected @('path', 'bytes', 'sha256') `
            -Context 'embedded product build manifest file record'
        Assert-BaxySafeRelativePath -Path ([string]$record.path)
        if ([int64]$record.bytes -lt 0 -or [int64]$record.bytes -gt $script:BaxyMaximumPayloadFileBytes -or
            [string]$record.sha256 -notmatch '^[0-9a-f]{64}$') {
            throw "Embedded package manifest file record is invalid: $($record.path)"
        }
        $records += [pscustomobject][ordered]@{
            path = [string]$record.path
            bytes = [int64]$record.bytes
            sha256 = [string]$record.sha256
        }
    }
    Assert-BaxyExactProductPayloadFileSet -Files $records

    $zipByPath = New-Object 'Collections.Generic.Dictionary[string,object]' ([StringComparer]::Ordinal)
    foreach ($entry in $ZipRecords) { $zipByPath.Add([string]$entry.path, $entry) }
    [int64]$totalBytes = 0
    foreach ($record in $records) {
        $actual = $zipByPath[[string]$record.path]
        if ([int64]$record.bytes -ne [int64]$actual.bytes -or
            -not [string]::Equals([string]$record.sha256, [string]$actual.sha256, [StringComparison]::Ordinal)) {
            throw "Embedded package manifest record does not match ZIP bytes: $($record.path)"
        }
        $totalBytes += [int64]$record.bytes
    }
    if ([int64]$manifest.total_bytes -ne $totalBytes) { throw 'Embedded package manifest total_bytes is invalid.' }

    $canonical = New-BaxyBuildManifest `
        -Version ([string]$manifest.version) `
        -Configuration 'Release' `
        -Commit ([string]$manifest.source.commit) `
        -Dirty $false `
        -SourceProvenance 'git_head_snapshot' `
        -SourceDateEpoch ([int64]$manifest.source.source_date_epoch) `
        -DotnetSdk ([string]$manifest.toolchain.dotnet_sdk) `
        -PowerShellVersion ([string]$manifest.toolchain.powershell) `
        -Files $records
    $canonicalText = ConvertTo-BaxyCanonicalJson -Value $canonical
    if (-not [string]::Equals($raw, $canonicalText, [StringComparison]::Ordinal)) {
        throw 'Embedded package build-manifest.json is not canonical v3 JSON.'
    }

    return [pscustomobject][ordered]@{
        manifest = $canonical
        bytes = [byte[]]$ManifestBytes
        sha256 = Get-BaxyBytesSha256 -Bytes $ManifestBytes
        records = @($records)
    }
}

function Get-BaxyValidatedProductPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit,
        [Parameter(Mandatory = $true)][int64]$ExpectedSourceDateEpoch
    )

    $packageRootFull = [IO.Path]::GetFullPath($Root)
    if (-not (Test-Path -LiteralPath $packageRootFull -PathType Container)) {
        throw "Product package root is missing: $packageRootFull"
    }
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $packageRootFull
    Assert-TreeHasNoReparsePoint -Root $packageRootFull
    Assert-BaxyNoAlternateDataStreams -Root $packageRootFull
    Assert-BaxyTreeHasNoHardLinks -Root $packageRootFull
    $rootEntries = @(Get-ChildItem -LiteralPath $packageRootFull -Force -ErrorAction Stop)
    if ($rootEntries.Count -ne 2 -or @($rootEntries | Where-Object { $_.PSIsContainer }).Count -ne 0) {
        throw 'Product package root must contain exactly one ZIP and its sidecar, with no directories.'
    }
    $zipFiles = @($rootEntries | Where-Object { $_.Name.EndsWith('.zip', [StringComparison]::Ordinal) })
    if ($zipFiles.Count -ne 1) { throw 'Product package root must contain exactly one lowercase .zip file.' }
    $packagePath = [IO.Path]::GetFullPath($zipFiles[0].FullName)
    $packageName = [string]$zipFiles[0].Name
    Assert-BaxySafeRelativePath -Path $packageName
    $expectedSidecarName = $packageName + '.sha256'
    $sidecarFiles = @($rootEntries | Where-Object {
        -not $_.PSIsContainer -and
        [string]::Equals([string]$_.Name, $expectedSidecarName, [StringComparison]::Ordinal)
    })
    if ($sidecarFiles.Count -ne 1) {
        throw 'Product package root is missing the exact ZIP .sha256 sidecar.'
    }
    $sidecarPath = [IO.Path]::GetFullPath($sidecarFiles[0].FullName)
    $packageLength = [int64](Get-Item -LiteralPath $packagePath -Force).Length
    if ($packageLength -le 0 -or $packageLength -gt $script:BaxyMaximumPackageBytes) {
        throw 'Product ZIP length is outside the reviewed Setup bounds.'
    }
    $packageSha256 = Get-BaxySha256 -Path $packagePath
    $expectedSidecar = "$packageSha256  $packageName`n"
    Assert-BaxyExactUtf8TextFile `
        -Path $sidecarPath `
        -ExpectedText $expectedSidecar `
        -Context 'Product package sidecar'

    [BaxyZipStorageInspector]::AssertStored($packagePath)
    [BaxySetupStoredCrcInspector]::AssertCrcs($packagePath)
    Add-Type -AssemblyName System.IO.Compression
    $zipRecords = @()
    $manifestBytes = $null
    $checksumBytes = $null
    $fileStream = New-Object IO.FileStream($packagePath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $archive = New-Object IO.Compression.ZipArchive($fileStream, [IO.Compression.ZipArchiveMode]::Read, $true)
        try {
            $entries = @($archive.Entries)
            if ($entries.Count -ne $script:BaxyPackageZipPaths.Count) {
                throw "Product ZIP must contain exactly $($script:BaxyPackageZipPaths.Count) reviewed files."
            }
            for ($index = 0; $index -lt $entries.Count; $index++) {
                $entry = $entries[$index]
                $path = [string]$entry.FullName
                if (-not [string]::Equals($path, $script:BaxyPackageZipPaths[$index], [StringComparison]::Ordinal)) {
                    throw "Product ZIP entry set or order is non-canonical: $path"
                }
                Assert-BaxySafeRelativePath -Path $path
                if ($entry.ExternalAttributes -ne 0 -or [int64]$entry.Length -gt $script:BaxyMaximumPayloadFileBytes) {
                    throw "Product ZIP entry has non-canonical attributes or size: $path"
                }
                $captured = $null
                if ([string]::Equals($path, 'build-manifest.json', [StringComparison]::Ordinal)) {
                    $captured = Get-BaxyZipEntryBytes -Entry $entry -MaximumBytes $script:BaxyMaximumManifestBytes
                    $manifestBytes = [byte[]]$captured
                } elseif ([string]::Equals($path, 'SHA256SUMS', [StringComparison]::Ordinal)) {
                    $captured = Get-BaxyZipEntryBytes -Entry $entry -MaximumBytes $script:BaxyMaximumChecksumBytes
                    $checksumBytes = [byte[]]$captured
                }
                if ($null -ne $captured) {
                    $entrySha256 = Get-BaxyBytesSha256 -Bytes ([byte[]]$captured)
                } else {
                    $entryStream = $entry.Open()
                    try { $entrySha256 = Get-BaxyStreamSha256 -Stream $entryStream } finally { $entryStream.Dispose() }
                }
                $zipRecords += [pscustomobject][ordered]@{
                    path = $path
                    bytes = [int64]$entry.Length
                    sha256 = $entrySha256
                    timestamp = $entry.LastWriteTime
                }
            }
        } finally {
            $archive.Dispose()
        }
    } finally {
        $fileStream.Dispose()
    }
    if ($null -eq $manifestBytes -or $null -eq $checksumBytes) {
        throw 'Product ZIP canonical metadata entries are missing.'
    }

    $validatedManifest = Get-BaxyValidatedPackageManifest `
        -ManifestBytes $manifestBytes `
        -ZipRecords $zipRecords `
        -ExpectedCommit $ExpectedCommit `
        -ExpectedSourceDateEpoch $ExpectedSourceDateEpoch
    $manifest = $validatedManifest.manifest
    $expectedPackageName = "BAXY-$($manifest.version)-$($ExpectedCommit.Substring(0, 12))-win-x64.zip"
    if (-not [string]::Equals($packageName, $expectedPackageName, [StringComparison]::Ordinal)) {
        throw 'Product package filename does not match its version and clean Git HEAD commit.'
    }

    $expectedTimestamp = Get-BaxyFixedZipTimestamp -SourceDateEpoch $ExpectedSourceDateEpoch
    foreach ($record in $zipRecords) {
        $actualTimestamp = [DateTimeOffset]$record.timestamp
        if ($actualTimestamp.Year -ne $expectedTimestamp.Year -or $actualTimestamp.Month -ne $expectedTimestamp.Month -or
            $actualTimestamp.Day -ne $expectedTimestamp.Day -or $actualTimestamp.Hour -ne $expectedTimestamp.Hour -or
            $actualTimestamp.Minute -ne $expectedTimestamp.Minute -or $actualTimestamp.Second -ne $expectedTimestamp.Second) {
            throw "Product ZIP entry timestamp is not derived from source_date_epoch: $($record.path)"
        }
    }

    $zipByPath = New-Object 'Collections.Generic.Dictionary[string,object]' ([StringComparer]::Ordinal)
    foreach ($record in $zipRecords) { $zipByPath.Add([string]$record.path, $record) }
    $checksumText = [string](($script:BaxyPackageChecksumPaths | ForEach-Object {
        $record = $zipByPath[$_]
        "$($record.sha256)  $_"
    }) -join "`n") + "`n"
    $actualChecksumText = ConvertFrom-BaxyUtf8NoBomBytes -Bytes $checksumBytes -Context 'embedded product SHA256SUMS'
    if (-not [string]::Equals($actualChecksumText, $checksumText, [StringComparison]::Ordinal)) {
        throw 'Product ZIP SHA256SUMS is not the exact canonical checksum set.'
    }

    $secondPackageSha256 = Get-BaxySha256 -Path $packagePath
    Assert-BaxyExactUtf8TextFile `
        -Path $sidecarPath `
        -ExpectedText $expectedSidecar `
        -Context 'Product package sidecar during final validation'
    if (-not [string]::Equals($packageSha256, $secondPackageSha256, [StringComparison]::Ordinal)) {
        throw 'Product package bytes or sidecar changed during independent validation.'
    }

    return [pscustomobject][ordered]@{
        root = $packageRootFull
        path = $packagePath
        name = $packageName
        sidecar_path = $sidecarPath
        sha256 = $packageSha256
        bytes = $packageLength
        manifest = $manifest
        manifest_sha256 = [string]$validatedManifest.sha256
        content_id = Get-BaxyPackageContentId -Entries $zipRecords
        zip_records = @($zipRecords)
    }
}

function Write-BaxyDurableBytes {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][byte[]]$Bytes
    )

    $stream = New-Object IO.FileStream(
        $Path,
        [IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,
        [IO.FileShare]::None,
        4096,
        [IO.FileOptions]::WriteThrough)
    try {
        $stream.Write($Bytes, 0, $Bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
}

function Copy-BaxyFileDurably {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $input = New-Object IO.FileStream(
        $Source,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        [IO.FileShare]::Read,
        1048576,
        [IO.FileOptions]::SequentialScan)
    try {
        $output = New-Object IO.FileStream(
            $Destination,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write,
            [IO.FileShare]::None,
            1048576,
            ([IO.FileOptions]::SequentialScan -bor [IO.FileOptions]::WriteThrough))
        try {
            $input.CopyTo($output)
            $output.Flush($true)
        } finally {
            $output.Dispose()
        }
    } finally {
        $input.Dispose()
    }
}

function Assert-BaxyFileHasSingleHardLink {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Hardlink attestation requires an existing file: $Path"
    }
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $Path
    [BaxySetupHardLinkInspector]::AssertSingleLink([IO.Path]::GetFullPath($Path))
}

function Assert-BaxyTreeHasNoHardLinks {
    param([Parameter(Mandatory = $true)][string]$Root)

    $rootFull = [IO.Path]::GetFullPath($Root)
    if (-not (Test-Path -LiteralPath $rootFull -PathType Container)) {
        throw "Hardlink tree attestation requires an existing directory: $rootFull"
    }
    foreach ($file in @(Get-ChildItem -LiteralPath $rootFull -File -Recurse -Force -ErrorAction Stop)) {
        Assert-BaxyFileHasSingleHardLink -Path $file.FullName
    }
}

function Assert-BaxyExactUtf8TextFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$ExpectedText,
        [Parameter(Mandatory = $true)][string]$Context
    )

    Assert-BaxyFileHasSingleHardLink -Path $Path
    $expectedLength = [int64]$script:BaxyUtf8NoBom.GetByteCount($ExpectedText)
    $actualLength = [int64](Get-Item -LiteralPath $Path -Force -ErrorAction Stop).Length
    if ($actualLength -ne $expectedLength) {
        throw "$Context byte length is not the exact reviewed length."
    }
    if (-not [string]::Equals((Read-BaxyUtf8NoBom -Path $Path), $ExpectedText, [StringComparison]::Ordinal)) {
        throw "$Context is not the exact canonical UTF-8 record."
    }
}

if ($null -eq ('BaxySetupPeInspector' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class BaxySetupHardLinkInspector
{
    private const uint FileShareRead = 0x00000001;
    private const uint OpenExisting = 3;
    private const uint FileAttributeNormal = 0x00000080;
    private const uint FileFlagOpenReparsePoint = 0x00200000;

    [StructLayout(LayoutKind.Sequential)]
    private struct ByHandleFileInformation
    {
        internal uint FileAttributes;
        internal System.Runtime.InteropServices.ComTypes.FILETIME CreationTime;
        internal System.Runtime.InteropServices.ComTypes.FILETIME LastAccessTime;
        internal System.Runtime.InteropServices.ComTypes.FILETIME LastWriteTime;
        internal uint VolumeSerialNumber;
        internal uint FileSizeHigh;
        internal uint FileSizeLow;
        internal uint NumberOfLinks;
        internal uint FileIndexHigh;
        internal uint FileIndexLow;
    }

    public static void AssertSingleLink(string path)
    {
        using (SafeFileHandle handle = CreateFile(
            path,
            0,
            FileShareRead,
            IntPtr.Zero,
            OpenExisting,
            FileAttributeNormal | FileFlagOpenReparsePoint,
            IntPtr.Zero))
        {
            if (handle.IsInvalid)
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Unable to open file for hardlink attestation: " + path);
            ByHandleFileInformation information;
            if (!GetFileInformationByHandle(handle, out information))
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Unable to read hardlink identity: " + path);
            if (information.NumberOfLinks != 1)
                throw new InvalidDataException("A hard-linked Setup delivery file is forbidden: " + path);
        }
    }

    [DllImport("kernel32.dll", EntryPoint = "CreateFileW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFile(
        string fileName,
        uint desiredAccess,
        uint shareMode,
        IntPtr securityAttributes,
        uint creationDisposition,
        uint flagsAndAttributes,
        IntPtr templateFile);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetFileInformationByHandle(
        SafeFileHandle handle,
        out ByHandleFileInformation information);
}

public static class BaxySetupStoredCrcInspector
{
    private const uint EndOfCentralDirectorySignature = 0x06054b50;
    private const uint CentralDirectoryHeaderSignature = 0x02014b50;
    private const uint LocalFileHeaderSignature = 0x04034b50;
    private static readonly uint[] Table = CreateTable();

    public static void AssertCrcs(string path)
    {
        using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
        using (BinaryReader reader = new BinaryReader(stream))
        {
            stream.Position = stream.Length - 22;
            if (reader.ReadUInt32() != EndOfCentralDirectorySignature)
                throw new InvalidDataException("Stored ZIP EOCD is missing during CRC verification.");
            reader.ReadUInt16();
            reader.ReadUInt16();
            reader.ReadUInt16();
            ushort totalEntries = reader.ReadUInt16();
            reader.ReadUInt32();
            uint centralOffset = reader.ReadUInt32();
            reader.ReadUInt16();
            stream.Position = centralOffset;
            byte[] buffer = new byte[1024 * 1024];
            for (int index = 0; index < totalEntries; index++)
            {
                if (reader.ReadUInt32() != CentralDirectoryHeaderSignature)
                    throw new InvalidDataException("Stored ZIP central entry is missing during CRC verification.");
                reader.ReadBytes(12);
                uint expectedCrc = reader.ReadUInt32();
                uint storedSize = reader.ReadUInt32();
                reader.ReadUInt32();
                ushort nameLength = reader.ReadUInt16();
                ushort extraLength = reader.ReadUInt16();
                ushort commentLength = reader.ReadUInt16();
                reader.ReadUInt16();
                reader.ReadUInt16();
                reader.ReadUInt32();
                uint localOffset = reader.ReadUInt32();
                long nextCentral = stream.Position + nameLength + extraLength + commentLength;

                stream.Position = localOffset;
                if (reader.ReadUInt32() != LocalFileHeaderSignature)
                    throw new InvalidDataException("Stored ZIP local entry is missing during CRC verification.");
                reader.ReadBytes(22);
                ushort localNameLength = reader.ReadUInt16();
                ushort localExtraLength = reader.ReadUInt16();
                stream.Position += localNameLength + localExtraLength;
                uint crc = 0xffffffffU;
                uint remaining = storedSize;
                while (remaining > 0)
                {
                    int requested = (int)Math.Min((uint)buffer.Length, remaining);
                    int read = stream.Read(buffer, 0, requested);
                    if (read != requested)
                        throw new EndOfStreamException("Stored ZIP entry is truncated during CRC verification.");
                    for (int offset = 0; offset < read; offset++)
                        crc = Table[(crc ^ buffer[offset]) & 0xff] ^ (crc >> 8);
                    remaining -= (uint)read;
                }
                crc = ~crc;
                if (crc != expectedCrc)
                    throw new InvalidDataException("Stored ZIP CRC32 does not match entry bytes.");
                stream.Position = nextCentral;
            }
        }
    }

    private static uint[] CreateTable()
    {
        uint[] table = new uint[256];
        for (uint index = 0; index < table.Length; index++)
        {
            uint value = index;
            for (int bit = 0; bit < 8; bit++)
                value = (value & 1) != 0 ? 0xedb88320U ^ (value >> 1) : value >> 1;
            table[index] = value;
        }
        return table;
    }
}

public static class BaxySetupPeInspector
{
    private const ushort MachineAmd64 = 0x8664;
    private const ushort Pe32Plus = 0x020b;
    private const ushort WindowsGuiSubsystem = 2;
    private const uint PeSignature = 0x00004550;
    private const int ResourceDirectoryIndex = 2;
    private const int SecurityDirectoryIndex = 4;
    private const int DebugDirectoryIndex = 6;
    private const int ClrDirectoryIndex = 14;

    private sealed class Section
    {
        public uint VirtualAddress;
        public uint VirtualSize;
        public uint RawSize;
        public uint RawOffset;
    }

    public static void AssertDelivery(string path)
    {
        using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
        using (BinaryReader reader = new BinaryReader(stream))
        {
            if (stream.Length < 512 || reader.ReadUInt16() != 0x5a4d)
                throw new InvalidDataException("Setup is not a complete DOS/PE executable.");
            stream.Position = 0x3c;
            int peOffset = reader.ReadInt32();
            if (peOffset < 0x40 || (long)peOffset + 24 > stream.Length)
                throw new InvalidDataException("Setup PE header offset is invalid.");
            stream.Position = peOffset;
            if (reader.ReadUInt32() != PeSignature)
                throw new InvalidDataException("Setup PE signature is invalid.");
            ushort machine = reader.ReadUInt16();
            ushort sectionCount = reader.ReadUInt16();
            reader.ReadUInt32();
            uint pointerToSymbolTable = reader.ReadUInt32();
            uint numberOfSymbols = reader.ReadUInt32();
            ushort optionalSize = reader.ReadUInt16();
            ushort characteristics = reader.ReadUInt16();
            long optionalOffset = stream.Position;
            if (machine != MachineAmd64 || sectionCount == 0 || optionalSize < 240 ||
                (characteristics & 0x0002) == 0 || (characteristics & 0x2000) != 0)
                throw new InvalidDataException("Setup must be an AMD64 executable with a PE32+ optional header.");
            if (pointerToSymbolTable != 0 || numberOfSymbols != 0)
                throw new InvalidDataException("Setup contains a forbidden COFF symbol table.");
            if (optionalOffset + optionalSize > stream.Length || reader.ReadUInt16() != Pe32Plus)
                throw new InvalidDataException("Setup is not PE32+.");

            stream.Position = optionalOffset + 68;
            if (reader.ReadUInt16() != WindowsGuiSubsystem)
                throw new InvalidDataException("Setup must use the Windows GUI subsystem.");
            stream.Position = optionalOffset + 108;
            uint directoryCount = reader.ReadUInt32();
            if (directoryCount <= ClrDirectoryIndex)
                throw new InvalidDataException("Setup PE data-directory table is incomplete.");
            long directoryOffset = optionalOffset + 112;
            uint resourceSize;
            uint securitySize;
            uint debugSize;
            uint clrSize;
            uint resourceRva = ReadDirectory(reader, stream, directoryOffset, ResourceDirectoryIndex, out resourceSize);
            uint securityOffset = ReadDirectory(reader, stream, directoryOffset, SecurityDirectoryIndex, out securitySize);
            uint debugRva = ReadDirectory(reader, stream, directoryOffset, DebugDirectoryIndex, out debugSize);
            uint clrRva = ReadDirectory(reader, stream, directoryOffset, ClrDirectoryIndex, out clrSize);
            if (resourceRva == 0 || resourceSize == 0)
                throw new InvalidDataException("Setup has no embedded resource directory.");
            if (securityOffset != 0 || securitySize != 0)
                throw new InvalidDataException("Unsigned Setup must not contain an Authenticode certificate table.");
            if (clrRva != 0 || clrSize != 0)
                throw new InvalidDataException("Setup contains a CLR descriptor and is not a NativeAOT executable.");

            long sectionOffset = optionalOffset + optionalSize;
            if (sectionOffset + (long)sectionCount * 40 > stream.Length)
                throw new InvalidDataException("Setup PE section table is truncated.");
            List<Section> sections = new List<Section>(sectionCount);
            stream.Position = sectionOffset;
            for (int index = 0; index < sectionCount; index++)
            {
                reader.ReadBytes(8);
                uint virtualSize = reader.ReadUInt32();
                uint virtualAddress = reader.ReadUInt32();
                uint rawSize = reader.ReadUInt32();
                uint rawOffset = reader.ReadUInt32();
                reader.ReadBytes(16);
                if ((ulong)rawOffset + rawSize > (ulong)stream.Length)
                    throw new InvalidDataException("Setup PE section raw data is outside the file.");
                sections.Add(new Section { VirtualAddress = virtualAddress, VirtualSize = virtualSize, RawSize = rawSize, RawOffset = rawOffset });
            }

            RvaToOffset(resourceRva, resourceSize, sections, stream.Length);
            if (debugRva == 0 || debugSize == 0 || debugSize % 28 != 0)
                throw new InvalidDataException("Setup PE debug directory is missing or malformed.");
            long debugOffset = RvaToOffset(debugRva, debugSize, sections, stream.Length);
            if (debugOffset + debugSize > stream.Length)
                throw new InvalidDataException("Setup PE debug directory is outside the file.");
            bool hasRepro = false;
            for (int index = 0; index < debugSize / 28; index++)
            {
                stream.Position = debugOffset + index * 28;
                reader.ReadUInt32();
                reader.ReadUInt32();
                reader.ReadUInt16();
                reader.ReadUInt16();
                uint type = reader.ReadUInt32();
                uint size = reader.ReadUInt32();
                reader.ReadUInt32();
                uint pointer = reader.ReadUInt32();
                if (type == 2)
                    throw new InvalidDataException("Setup contains forbidden CodeView/PDB metadata.");
                if (type == 16)
                    hasRepro = true;
                if (size != 0 && ((long)pointer + size > stream.Length))
                    throw new InvalidDataException("Setup PE debug payload is outside the file.");
            }
            if (!hasRepro)
                throw new InvalidDataException("Setup PE lacks the deterministic REPRO debug record.");
        }
    }

    private static uint ReadDirectory(BinaryReader reader, Stream stream, long directoryOffset, int index, out uint size)
    {
        stream.Position = directoryOffset + index * 8;
        uint address = reader.ReadUInt32();
        size = reader.ReadUInt32();
        return address;
    }

    private static long RvaToOffset(uint rva, uint size, List<Section> sections, long fileLength)
    {
        foreach (Section section in sections)
        {
            ulong delta = rva >= section.VirtualAddress ? (ulong)rva - section.VirtualAddress : ulong.MaxValue;
            if (delta <= section.RawSize && (ulong)size <= section.RawSize - delta)
            {
                long offset = (long)((ulong)section.RawOffset + delta);
                if (offset < 0 || (ulong)offset + size > (ulong)fileLength)
                    break;
                return offset;
            }
        }
        throw new InvalidDataException("Setup PE directory RVA does not map to a reviewed section.");
    }
}
'@
}

function Assert-BaxySetupExecutable {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Setup executable is missing: $Path" }
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $Path
    Assert-BaxyFileHasSingleHardLink -Path $Path
    [BaxySetupPeInspector]::AssertDelivery($Path)
    $signature = Get-AuthenticodeSignature -FilePath $Path -ErrorAction Stop
    if (-not [string]::Equals([string]$signature.Status, 'NotSigned', [StringComparison]::Ordinal)) {
        throw "Setup Authenticode status must be honestly NotSigned, observed: $($signature.Status)"
    }
}

function Get-BaxyExactPublishedSetup {
    param([Parameter(Mandatory = $true)][string]$PublishRoot)

    if (-not (Test-Path -LiteralPath $PublishRoot -PathType Container)) {
        throw 'Setup publish output directory is missing.'
    }
    Assert-TreeHasNoReparsePoint -Root $PublishRoot
    Assert-BaxyNoAlternateDataStreams -Root $PublishRoot
    Assert-BaxyTreeHasNoHardLinks -Root $PublishRoot
    $entries = @(Get-ChildItem -LiteralPath $PublishRoot -Force -ErrorAction Stop)
    if ($entries.Count -ne 1 -or $entries[0].PSIsContainer -or
        -not [string]::Equals([string]$entries[0].Name, $script:BaxySetupFileName, [StringComparison]::Ordinal)) {
        throw 'Setup publish output must contain exactly Baxy.Setup.exe and no other file or directory.'
    }
    $path = [IO.Path]::GetFullPath($entries[0].FullName)
    Assert-BaxySetupExecutable -Path $path
    return $path
}

function New-BaxyEmbeddedAttestationBytes {
    param([Parameter(Mandatory = $true)]$Package)

    $attestation = [ordered]@{
        schema = $script:BaxyEmbeddedAttestationSchema
        version = [string]$Package.manifest.version
        data_schema = [int]$Package.manifest.data_schema
        package_sha256 = [string]$Package.sha256
        package_bytes = [int64]$Package.bytes
        manifest_sha256 = [string]$Package.manifest_sha256
        content_id = [string]$Package.content_id
        source_date_epoch = [int64]$Package.manifest.source.source_date_epoch
        commit = [string]$Package.manifest.source.commit
    }
    return ,([byte[]]$script:BaxyUtf8NoBom.GetBytes((ConvertTo-BaxyCanonicalJson -Value $attestation) + "`n"))
}

function Assert-BaxyEmbeddedEvidence {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Package
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw 'Setup did not create embedded verification evidence.' }
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $Path
    $expected = [ordered]@{
        schema = $script:BaxyEmbeddedEvidenceSchema
        status = 'passed'
        version = [string]$Package.manifest.version
        data_schema = [int]$Package.manifest.data_schema
        package_sha256 = [string]$Package.sha256
        package_bytes = [int64]$Package.bytes
        manifest_sha256 = [string]$Package.manifest_sha256
        content_id = [string]$Package.content_id
        source_date_epoch = [int64]$Package.manifest.source.source_date_epoch
        commit = [string]$Package.manifest.source.commit
    }
    $expectedText = (ConvertTo-BaxyCanonicalJson -Value $expected) + "`n"
    Assert-BaxyExactUtf8TextFile `
        -Path $Path `
        -ExpectedText $expectedText `
        -Context 'Setup embedded verification evidence'
}

function Invoke-BaxyEmbeddedVerification {
    param(
        [Parameter(Mandatory = $true)][string]$SetupPath,
        [Parameter(Mandatory = $true)][string]$EvidencePath
    )

    if (Test-Path -LiteralPath $EvidencePath) { throw 'Embedded verification evidence path must be new.' }
    $quotedEvidence = '"' + $EvidencePath.Replace('"', '""') + '"'
    $process = Start-Process `
        -FilePath $SetupPath `
        -ArgumentList @('--verify-embedded', '--evidence', $quotedEvidence) `
        -PassThru `
        -WindowStyle Hidden
    try {
        if (-not $process.WaitForExit(60000)) {
            try { $process.Kill() } catch { }
            throw 'Setup embedded verification timed out.'
        }
        if ($process.ExitCode -ne 0) { throw "Setup embedded verification failed with exit code $($process.ExitCode)." }
    } finally {
        $process.Dispose()
    }
}

function New-BaxySetupManifest {
    param(
        [Parameter(Mandatory = $true)]$Package,
        [Parameter(Mandatory = $true)][string]$SetupSha256,
        [Parameter(Mandatory = $true)][int64]$SetupBytes,
        [Parameter(Mandatory = $true)][string]$AttestationSha256,
        [Parameter(Mandatory = $true)][string]$DotnetSdk,
        [Parameter(Mandatory = $true)][string]$PowerShellVersion
    )

    return [ordered]@{
        schema = $script:BaxySetupManifestSchema
        product = 'BAXY'
        version = [string]$Package.manifest.version
        data_schema = [int]$Package.manifest.data_schema
        configuration = 'Release'
        runtime = 'win-x64'
        target_framework = 'net10.0-windows10.0.19041.0'
        authenticity = 'not_provided'
        authenticode = 'NotSigned'
        source = [ordered]@{
            commit = [string]$Package.manifest.source.commit
            provenance = 'git_head_snapshot'
            source_date_epoch = [int64]$Package.manifest.source.source_date_epoch
        }
        embedded_package = [ordered]@{
            name = [string]$Package.name
            sha256 = [string]$Package.sha256
            bytes = [int64]$Package.bytes
            manifest_sha256 = [string]$Package.manifest_sha256
            content_id = [string]$Package.content_id
            attestation_sha256 = $AttestationSha256
        }
        deployment = [ordered]@{
            setup = 'native_aot_self_contained'
            subsystem = 'windows_gui'
            symbols = 'excluded_from_user_payload'
        }
        toolchain = [ordered]@{
            dotnet_sdk = $DotnetSdk
            powershell = $PowerShellVersion
        }
        file = [ordered]@{
            path = $script:BaxySetupFileName
            bytes = $SetupBytes
            sha256 = $SetupSha256
        }
    }
}

function Assert-BaxySetupOutput {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$ExpectedManifestText
    )

    $rootFull = [IO.Path]::GetFullPath($Root)
    if (-not (Test-Path -LiteralPath $rootFull -PathType Container)) { throw "Setup output root is missing: $rootFull" }
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $rootFull
    Assert-TreeHasNoReparsePoint -Root $rootFull
    Assert-BaxyNoAlternateDataStreams -Root $rootFull
    Assert-BaxyTreeHasNoHardLinks -Root $rootFull
    $entries = @(Get-ChildItem -LiteralPath $rootFull -Force -ErrorAction Stop | Sort-Object -Property Name)
    $expectedNames = @($script:BaxySetupFileName, $script:BaxySetupChecksumsFileName, $script:BaxySetupManifestFileName) | Sort-Object
    if ($entries.Count -ne $expectedNames.Count -or @($entries | Where-Object { $_.PSIsContainer }).Count -ne 0) {
        throw 'Setup output must contain exactly three reviewed files and no directories.'
    }
    for ($index = 0; $index -lt $expectedNames.Count; $index++) {
        if (-not [string]::Equals([string]$entries[$index].Name, [string]$expectedNames[$index], [StringComparison]::Ordinal)) {
            throw "Setup output contains an unexpected file: $($entries[$index].Name)"
        }
    }

    $setupPath = Join-Path $rootFull $script:BaxySetupFileName
    $manifestPath = Join-Path $rootFull $script:BaxySetupManifestFileName
    $checksumsPath = Join-Path $rootFull $script:BaxySetupChecksumsFileName
    Assert-BaxySetupExecutable -Path $setupPath
    Assert-BaxyExactUtf8TextFile `
        -Path $manifestPath `
        -ExpectedText $ExpectedManifestText `
        -Context 'setup-manifest.json'
    $setupSha256 = Get-BaxySha256 -Path $setupPath
    $manifestSha256 = Get-BaxySha256 -Path $manifestPath
    $expectedChecksums = "$setupSha256  $($script:BaxySetupFileName)`n$manifestSha256  $($script:BaxySetupManifestFileName)`n"
    Assert-BaxyExactUtf8TextFile `
        -Path $checksumsPath `
        -ExpectedText $expectedChecksums `
        -Context 'Setup SHA256SUMS'
    return [pscustomobject][ordered]@{
        setup_path = $setupPath
        setup_sha256 = $setupSha256
        setup_bytes = [int64](Get-Item -LiteralPath $setupPath -Force).Length
        manifest_path = $manifestPath
        manifest_sha256 = $manifestSha256
        checksums_path = $checksumsPath
    }
}

function Move-BaxyNewDirectoryAtomically {
    param(
        [Parameter(Mandatory = $true)][string]$AllowedRoot,
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $allowedFull = [IO.Path]::GetFullPath($AllowedRoot)
    $sourceFull = [IO.Path]::GetFullPath($Source)
    $destinationFull = [IO.Path]::GetFullPath($Destination)
    Assert-StrictDescendantPath -Parent $allowedFull -Child $sourceFull
    Assert-StrictDescendantPath -Parent $allowedFull -Child $destinationFull
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $allowedFull
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $sourceFull
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $destinationFull
    Assert-TreeHasNoReparsePoint -Root $sourceFull
    Assert-BaxyNoAlternateDataStreams -Root $sourceFull
    Assert-BaxyTreeHasNoHardLinks -Root $sourceFull
    if (Test-Path -LiteralPath $destinationFull) {
        throw "Setup OutputRoot must remain new; refusing to replace or delete existing output: $destinationFull"
    }

    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    foreach ($file in @(Get-ChildItem -LiteralPath $sourceFull -File -Recurse -Force -ErrorAction Stop)) {
        $probe = New-Object IO.FileStream($file.FullName, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
        $probe.Dispose()
    }
    if (Test-Path -LiteralPath $destinationFull) {
        throw "Setup OutputRoot appeared during promotion; refusing to mutate it: $destinationFull"
    }
    [IO.Directory]::Move($sourceFull, $destinationFull)
}

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$allowedProductBuildRoot = [IO.Path]::GetFullPath((Join-Path $root 'artifacts\product\build'))
$setupArtifactsRoot = [IO.Path]::GetFullPath((Join-Path $root 'artifacts\setup'))
$allowedSetupBuildRoot = [IO.Path]::GetFullPath((Join-Path $setupArtifactsRoot 'build'))
if ([string]::IsNullOrWhiteSpace($PackageRoot)) { $PackageRoot = Join-Path $allowedProductBuildRoot 'packages' }
if ([string]::IsNullOrWhiteSpace($OutputRoot)) { $OutputRoot = Join-Path $allowedSetupBuildRoot 'local-win-x64' }
$PackageRoot = [IO.Path]::GetFullPath($PackageRoot)
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
Assert-StrictDescendantPath -Parent $allowedProductBuildRoot -Child $PackageRoot
Assert-StrictDescendantPath -Parent $allowedSetupBuildRoot -Child $OutputRoot
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $OutputRoot

$initialGit = Get-BaxySetupGitState -RepositoryRoot $root
if ($initialGit.dirty) {
    throw 'The Git worktree is dirty. Refusing to build delivery Setup outside a clean Git HEAD.'
}
$epochText = [string](& git -C $root show -s --format=%ct $initialGit.commit)
if ($LASTEXITCODE -ne 0 -or $epochText.Trim() -notmatch '^[0-9]+$') {
    throw 'Unable to resolve Setup source_date_epoch from Git HEAD.'
}
$sourceDateEpoch = [int64]$epochText.Trim()

$null = Assert-ExistingPathChainHasNoReparsePoint -Path $allowedProductBuildRoot
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $setupArtifactsRoot
if (-not (Test-Path -LiteralPath $setupArtifactsRoot)) { New-Item -ItemType Directory -Path $setupArtifactsRoot | Out-Null }
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $setupArtifactsRoot
if (-not (Test-Path -LiteralPath $allowedSetupBuildRoot)) { New-Item -ItemType Directory -Path $allowedSetupBuildRoot | Out-Null }
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $allowedSetupBuildRoot
if (Test-Path -LiteralPath $OutputRoot) {
    throw "Setup OutputRoot must be new; refusing to replace or delete existing output: $OutputRoot"
}

$sourceSnapshotRoot = Join-Path $allowedSetupBuildRoot ('.setup-source-snapshot-' + [Guid]::NewGuid().ToString('N'))
$workRoot = Join-Path $allowedSetupBuildRoot ('.setup-work-' + [Guid]::NewGuid().ToString('N'))
$outputStagingRoot = Join-Path $allowedSetupBuildRoot ('.setup-output-staging-' + [Guid]::NewGuid().ToString('N'))
$inputRoot = Join-Path $workRoot 'input'
$dotnetArtifactsRoot = Join-Path $workRoot 'dotnet-artifacts'
$publishRoot = Join-Path $workRoot 'publish'
$attestationPath = Join-Path $workRoot 'embedded-package-attestation.json'
$evidencePath = Join-Path $workRoot 'embedded-verification-evidence.json'
$previousSourceDateEpoch = [Environment]::GetEnvironmentVariable('SOURCE_DATE_EPOCH', 'Process')
$promoted = $false
$primaryFailure = $null
$result = $null

try {
    $validatedOriginalPackage = Get-BaxyValidatedProductPackage `
        -Root $PackageRoot `
        -ExpectedCommit $initialGit.commit `
        -ExpectedSourceDateEpoch $sourceDateEpoch

    New-Item -ItemType Directory -Path $inputRoot | Out-Null
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $workRoot
    $snapshotPackagePath = Join-Path $inputRoot $validatedOriginalPackage.name
    $snapshotSidecarPath = $snapshotPackagePath + '.sha256'
    Copy-BaxyFileDurably -Source $validatedOriginalPackage.path -Destination $snapshotPackagePath
    Copy-BaxyFileDurably -Source $validatedOriginalPackage.sidecar_path -Destination $snapshotSidecarPath
    $validatedPackage = Get-BaxyValidatedProductPackage `
        -Root $inputRoot `
        -ExpectedCommit $initialGit.commit `
        -ExpectedSourceDateEpoch $sourceDateEpoch
    if (-not [string]::Equals($validatedOriginalPackage.sha256, $validatedPackage.sha256, [StringComparison]::Ordinal) -or
        -not [string]::Equals($validatedOriginalPackage.content_id, $validatedPackage.content_id, [StringComparison]::Ordinal)) {
        throw 'Durable embedded package snapshot does not match the independently validated input.'
    }

    $attestationBytes = New-BaxyEmbeddedAttestationBytes -Package $validatedPackage
    Write-BaxyDurableBytes -Path $attestationPath -Bytes $attestationBytes
    $attestationSha256 = Get-BaxySha256 -Path $attestationPath

    $sourceRoot = New-BaxyHeadWorktreeSnapshot `
        -RepositoryRoot $root `
        -AllowedRoot $allowedSetupBuildRoot `
        -SnapshotRoot $sourceSnapshotRoot `
        -Commit $initialGit.commit
    $setupProject = Join-Path $sourceRoot 'src\Baxy.Setup\Baxy.Setup.csproj'
    if (-not (Test-Path -LiteralPath $setupProject -PathType Leaf)) {
        throw 'Clean Git HEAD does not contain src\Baxy.Setup\Baxy.Setup.csproj.'
    }
    Assert-BaxyMsBuildPathSafe -Path $sourceRoot -Context 'Setup source snapshot path'
    Assert-BaxyMsBuildPathSafe -Path $workRoot -Context 'Setup isolated work path'
    [Environment]::SetEnvironmentVariable('SOURCE_DATE_EPOCH', [string]$sourceDateEpoch, 'Process')

    $informationalVersion = if (([string]$validatedPackage.manifest.version).Contains('+')) {
        "$($validatedPackage.manifest.version).sha.$($initialGit.commit.Substring(0, 12))"
    } else {
        "$($validatedPackage.manifest.version)+$($initialGit.commit.Substring(0, 12))"
    }
    # MSBuild treats a literal comma in -p as another property delimiter. %2C is
    # decoded into the comma that the compiler's PathMap value requires.
    $pathMap = "$sourceRoot=/_/baxy%2C$workRoot=/_/baxy-setup-work"
    Push-Location $sourceRoot
    try {
        $dotnetSdk = [string](& dotnet --version)
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($dotnetSdk)) {
            throw 'Unable to resolve the .NET SDK version for Setup.'
        }
        $dotnetSdk = $dotnetSdk.Trim()
        Invoke-BaxySetupDotnetChecked -FailureMessage 'Setup restore failed' -Arguments @(
            'restore', $setupProject, '-r', 'win-x64', '--artifacts-path', $dotnetArtifactsRoot,
            '--ignore-failed-sources', '-p:NuGetAudit=false', '--nologo'
        )
        Invoke-BaxySetupDotnetChecked -FailureMessage 'Setup NativeAOT publish failed' -Arguments @(
            'publish', $setupProject, '-c', 'Release', '-r', 'win-x64',
            '--self-contained', 'true', '--no-restore', '--artifacts-path', $dotnetArtifactsRoot,
            '-o', $publishRoot, '--nologo',
            '-p:PublishAot=true', '-p:StripSymbols=true', '-p:DebugType=none',
            '-p:DebugSymbols=false', '-p:NativeDebugSymbols=false',
            '-p:CopyOutputSymbolsToPublishDirectory=false',
            '-p:ContinuousIntegrationBuild=true', '-p:Deterministic=true',
            '-p:IlcGenerateCompleteTypeMetadata=false', '-p:IlcGenerateStackTraceData=false',
            "-p:PathMap=$pathMap", "-p:Version=$($validatedPackage.manifest.version)",
            "-p:InformationalVersion=$informationalVersion", "-p:SourceRevisionId=$($initialGit.commit)",
            "-p:BaxyEmbeddedPackage=$snapshotPackagePath",
            "-p:BaxyEmbeddedPackageAttestation=$attestationPath"
        )
    } finally {
        Pop-Location
    }

    $publishedSetupPath = Get-BaxyExactPublishedSetup -PublishRoot $publishRoot
    Invoke-BaxyEmbeddedVerification -SetupPath $publishedSetupPath -EvidencePath $evidencePath
    Assert-BaxyEmbeddedEvidence -Path $evidencePath -Package $validatedPackage
    Assert-BaxySetupExecutable -Path $publishedSetupPath

    $revalidatedSnapshotPackage = Get-BaxyValidatedProductPackage `
        -Root $inputRoot `
        -ExpectedCommit $initialGit.commit `
        -ExpectedSourceDateEpoch $sourceDateEpoch
    $revalidatedOriginalPackage = Get-BaxyValidatedProductPackage `
        -Root $PackageRoot `
        -ExpectedCommit $initialGit.commit `
        -ExpectedSourceDateEpoch $sourceDateEpoch
    if (-not [string]::Equals($validatedPackage.sha256, $revalidatedSnapshotPackage.sha256, [StringComparison]::Ordinal) -or
        -not [string]::Equals($validatedPackage.sha256, $revalidatedOriginalPackage.sha256, [StringComparison]::Ordinal)) {
        throw 'Embedded package input changed while Setup was being published and physically verified.'
    }

    Assert-BaxySetupSnapshotUnchanged -SnapshotRoot $sourceSnapshotRoot -Commit $initialGit.commit
    $finalGit = Get-BaxySetupGitState -RepositoryRoot $root
    if ($finalGit.dirty -or -not [string]::Equals($finalGit.commit, $initialGit.commit, [StringComparison]::Ordinal)) {
        throw 'Live clean Git HEAD changed while Setup was being built.'
    }

    New-Item -ItemType Directory -Path $outputStagingRoot | Out-Null
    $stagedSetupPath = Join-Path $outputStagingRoot $script:BaxySetupFileName
    Copy-BaxyFileDurably -Source $publishedSetupPath -Destination $stagedSetupPath
    Assert-BaxySetupExecutable -Path $stagedSetupPath
    $setupSha256 = Get-BaxySha256 -Path $stagedSetupPath
    $setupBytes = [int64](Get-Item -LiteralPath $stagedSetupPath -Force).Length
    $setupManifest = New-BaxySetupManifest `
        -Package $validatedPackage `
        -SetupSha256 $setupSha256 `
        -SetupBytes $setupBytes `
        -AttestationSha256 $attestationSha256 `
        -DotnetSdk $dotnetSdk `
        -PowerShellVersion ($PSVersionTable.PSVersion.ToString())
    $setupManifestText = ConvertTo-BaxyCanonicalJson -Value $setupManifest
    Write-BaxyDurableBytes `
        -Path (Join-Path $outputStagingRoot $script:BaxySetupManifestFileName) `
        -Bytes $script:BaxyUtf8NoBom.GetBytes($setupManifestText)
    $setupManifestSha256 = Get-BaxySha256 -Path (Join-Path $outputStagingRoot $script:BaxySetupManifestFileName)
    $checksumsText = "$setupSha256  $($script:BaxySetupFileName)`n$setupManifestSha256  $($script:BaxySetupManifestFileName)`n"
    Write-BaxyDurableBytes `
        -Path (Join-Path $outputStagingRoot $script:BaxySetupChecksumsFileName) `
        -Bytes $script:BaxyUtf8NoBom.GetBytes($checksumsText)
    $staged = Assert-BaxySetupOutput -Root $outputStagingRoot -ExpectedManifestText $setupManifestText

    Move-BaxyNewDirectoryAtomically `
        -AllowedRoot $allowedSetupBuildRoot `
        -Source $outputStagingRoot `
        -Destination $OutputRoot
    $promoted = $true
    $final = Assert-BaxySetupOutput -Root $OutputRoot -ExpectedManifestText $setupManifestText
    $secondFinal = Assert-BaxySetupOutput -Root $OutputRoot -ExpectedManifestText $setupManifestText
    if (-not [string]::Equals($final.setup_sha256, $secondFinal.setup_sha256, [StringComparison]::Ordinal) -or
        -not [string]::Equals($final.manifest_sha256, $secondFinal.manifest_sha256, [StringComparison]::Ordinal)) {
        throw 'Promoted Setup bytes changed during final double verification.'
    }

    $result = [ordered]@{
        setup = $final.setup_path
        setup_sha256 = $final.setup_sha256
        setup_bytes = $final.setup_bytes
        manifest = $final.manifest_path
        manifest_sha256 = $final.manifest_sha256
        checksums = $final.checksums_path
        embedded_package_sha256 = [string]$validatedPackage.sha256
        content_id = [string]$validatedPackage.content_id
        commit = $initialGit.commit
        source_date_epoch = $sourceDateEpoch
        authenticode = 'NotSigned'
        output = $OutputRoot
    }
} catch {
    $primaryFailure = $_
}

$cleanupFailures = New-Object 'System.Collections.Generic.List[string]'
[Environment]::SetEnvironmentVariable('SOURCE_DATE_EPOCH', $previousSourceDateEpoch, 'Process')
foreach ($temporaryRoot in @($outputStagingRoot, $workRoot)) {
    if (Test-Path -LiteralPath $temporaryRoot) {
        try { Remove-TreeFailClosed -AllowedRoot $allowedSetupBuildRoot -Target $temporaryRoot } catch {
            $cleanupFailures.Add($_.Exception.Message)
        }
    }
}
if ($null -ne $primaryFailure -and $promoted -and (Test-Path -LiteralPath $OutputRoot)) {
    try { Remove-TreeFailClosed -AllowedRoot $allowedSetupBuildRoot -Target $OutputRoot } catch {
        $cleanupFailures.Add($_.Exception.Message)
    }
}
if (Test-Path -LiteralPath $sourceSnapshotRoot) {
    try {
        Remove-BaxyHeadWorktreeSnapshot `
            -RepositoryRoot $root `
            -AllowedRoot $allowedSetupBuildRoot `
            -SnapshotRoot $sourceSnapshotRoot
    } catch {
        $cleanupFailures.Add($_.Exception.Message)
    }
}

if ($null -ne $primaryFailure) {
    if ($cleanupFailures.Count -gt 0) {
        throw "Setup build failed: $($primaryFailure.Exception.Message) Cleanup also failed closed: $($cleanupFailures -join '; ')"
    }
    throw $primaryFailure
}
if ($cleanupFailures.Count -gt 0) {
    throw "Setup build completed, but cleanup failed closed: $($cleanupFailures -join '; ')"
}
$result | ConvertTo-Json -Compress
