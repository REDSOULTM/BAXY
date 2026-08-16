[CmdletBinding()]
param(
    [string]$Archive,
    [string]$FunctionGemmaRoot,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$manifestPath = Join-Path $repo 'bootstrap\agent-assets-v1.manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Agent asset manifest is missing: $manifestPath"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.schema -cne 'baxy-agent-assets-v1') {
    throw "Unsupported agent asset manifest schema: $($manifest.schema)"
}

if ([string]::IsNullOrWhiteSpace($Archive)) {
    $Archive = Join-Path $repo ([string]$manifest.archive.path)
}
$Archive = [IO.Path]::GetFullPath($Archive)
if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) {
    throw "Agent asset archive is missing: $Archive"
}

if ([string]::IsNullOrWhiteSpace($FunctionGemmaRoot)) {
    $FunctionGemmaRoot = Join-Path (Split-Path -Parent $repo) 'FunctionGemma'
}
$FunctionGemmaRoot = [IO.Path]::GetFullPath($FunctionGemmaRoot)

function Get-LowerSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-SafeRelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)
    if ([IO.Path]::IsPathRooted($Path)) { throw "Package path must be relative: $Path" }
    $parts = @($Path.Replace('\', '/').Split('/') | Where-Object { $_ -ne '' })
    if ($parts.Count -eq 0 -or $parts -contains '.' -or $parts -contains '..') {
        throw "Unsafe package path: $Path"
    }
}

$archiveInfo = Get-Item -LiteralPath $Archive
if ([int64]$archiveInfo.Length -ne [int64]$manifest.archive.bytes) {
    throw "Agent asset archive size mismatch: $($archiveInfo.Length)"
}
$archiveHash = Get-LowerSha256 -Path $Archive
if ($archiveHash -cne [string]$manifest.archive.sha256) {
    throw "Agent asset archive SHA-256 mismatch: $archiveHash"
}

$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ('baxy-agent-assets-' + [Guid]::NewGuid().ToString('N'))
$installed = New-Object 'Collections.Generic.List[object]'
try {
    $null = New-Item -ItemType Directory -Path $temporaryRoot
    Expand-Archive -LiteralPath $Archive -DestinationPath $temporaryRoot

    $expectedPackagePaths = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($record in @($manifest.files)) {
        $packagePath = ([string]$record.package_path).Replace('\', '/')
        Assert-SafeRelativePath -Path $packagePath
        if (-not $expectedPackagePaths.Add($packagePath)) {
            throw "Duplicate package path in manifest: $packagePath"
        }
    }

    $actualPackagePaths = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $temporaryPrefix = $temporaryRoot.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    foreach ($file in @(Get-ChildItem -LiteralPath $temporaryRoot -Recurse -Force -File)) {
        if (-not $file.FullName.StartsWith($temporaryPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Extracted file escaped the temporary root: $($file.FullName)"
        }
        $relative = $file.FullName.Substring($temporaryPrefix.Length).Replace('\', '/')
        if (-not $actualPackagePaths.Add($relative)) {
            throw "Duplicate extracted package path: $relative"
        }
    }
    if (-not $actualPackagePaths.SetEquals($expectedPackagePaths)) {
        throw 'Extracted agent asset file set does not match the manifest.'
    }

    foreach ($record in @($manifest.files)) {
        $packagePath = ([string]$record.package_path).Replace('/', [IO.Path]::DirectorySeparatorChar)
        $source = Join-Path $temporaryRoot $packagePath
        $sourceInfo = Get-Item -LiteralPath $source
        $sourceHash = Get-LowerSha256 -Path $source
        if ([int64]$sourceInfo.Length -ne [int64]$record.bytes -or
            $sourceHash -cne [string]$record.sha256) {
            throw "Agent asset payload mismatch: $($record.package_path)"
        }

        if ($null -ne $record.jsonl_rows) {
            $rowCount = 0
            foreach ($line in [IO.File]::ReadLines($source)) { $rowCount++ }
            if ($rowCount -ne [int]$record.jsonl_rows) {
                throw "JSONL row count mismatch for $($record.package_path): $rowCount"
            }
        }

        $destinationRoot = switch ([string]$record.destination_root) {
            'repository' { $repo; break }
            'function_gemma' { $FunctionGemmaRoot; break }
            default { throw "Unsupported destination root: $($record.destination_root)" }
        }
        $destinationPath = ([string]$record.destination_path).Replace('/', [IO.Path]::DirectorySeparatorChar)
        Assert-SafeRelativePath -Path $destinationPath
        $destination = [IO.Path]::GetFullPath((Join-Path $destinationRoot $destinationPath))
        $rootPrefix = $destinationRoot.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
        if (-not $destination.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Destination escaped its approved root: $destination"
        }

        $state = 'installed'
        if (Test-Path -LiteralPath $destination -PathType Leaf) {
            $existingHash = Get-LowerSha256 -Path $destination
            if ($existingHash -ceq [string]$record.sha256) {
                $state = 'already_present'
            } elseif (-not $Force.IsPresent) {
                throw "Destination exists with different bytes; rerun with -Force to replace it: $destination"
            }
        }

        if ($state -eq 'installed') {
            $parent = Split-Path -Parent $destination
            $null = New-Item -ItemType Directory -Path $parent -Force
            $incoming = Join-Path $parent ('.baxy-agent-asset-' + [Guid]::NewGuid().ToString('N') + '.tmp')
            try {
                Copy-Item -LiteralPath $source -Destination $incoming
                Move-Item -LiteralPath $incoming -Destination $destination -Force
            } finally {
                if (Test-Path -LiteralPath $incoming -PathType Leaf) {
                    Remove-Item -LiteralPath $incoming -Force
                }
            }
        }

        $installed.Add([pscustomobject][ordered]@{
            path = $destination
            state = $state
            bytes = [int64]$record.bytes
            sha256 = [string]$record.sha256
        })
    }
} finally {
    if (Test-Path -LiteralPath $temporaryRoot -PathType Container) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

[pscustomobject][ordered]@{
    restored = $true
    schema = [string]$manifest.schema
    archive = $Archive
    archive_sha256 = $archiveHash
    function_gemma_root = $FunctionGemmaRoot
    files = $installed.ToArray()
} | ConvertTo-Json -Depth 5
