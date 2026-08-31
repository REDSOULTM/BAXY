[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CandidateSetup,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedCurrentVersion,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedInitialPreviousVersion,
    [Parameter(Mandatory = $true)]
    [string]$CandidateVersion,
    [Parameter(Mandatory = $true)]
    [string]$EvidencePath,
    [string]$ExpectedCandidateCommit,
    [string]$PriorFailureEvidencePath,
    [string]$ExpectedPriorFailureEvidenceSha256,
    [switch]$ContinueRecoveredCandidate,
    [ValidateRange(30, 600)]
    [int]$TimeoutSeconds = 180,
    [switch]$ConfirmInPlaceUpgrade
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'path_safety.ps1')

$script:DataSchema = 1
$script:ExpectedCapabilities = 168
$script:ExpectedApplicationCatalogVersion = 1
$script:MaximumApplicationCatalogNames = 2048
$script:MaximumApplicationCatalogNameUtf8Bytes = 512
$script:MaximumApplicationCatalogNamesUtf8Bytes = 262144
$script:MaximumApplicationCatalogEscapedNamesUtf8Bytes = 262144
$script:SemVerPattern =
    '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-(0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)(\.(0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?\z'
$script:StrictUtf8 = New-Object Text.UTF8Encoding($false, $true)
$script:PendingLifecycleNames = @(
    'current.next',
    'current.rollback',
    'transaction.v1.json',
    'transaction.next',
    'installation.next',
    'windows-integration.next',
    'windows-integration.previous',
    'windows-integration.transaction.v1.json',
    'windows-integration.transaction.next',
    'windows-integration.transaction.previous',
    'Baxy.Setup.next.exe',
    'Baxy.Setup.previous.exe'
)
$script:OwnedSetupProcessNames = @(
    'Baxy.Setup',
    'Baxy.Setup.next',
    'Baxy.Setup.previous'
)

function Assert-GateCondition {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )

    if (-not $Condition) { throw $Message }
}

function Test-LowerHex {
    param(
        [AllowNull()][string]$Value,
        [int]$Length = 64
    )

    return $null -ne $Value -and
        $Value.Length -eq $Length -and
        $Value -cmatch "^[0-9a-f]{$Length}$"
}

function Get-BytesSha256 {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)

    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $digest = $algorithm.ComputeHash($Bytes)
        return ([BitConverter]::ToString($digest)).Replace('-', '').ToLowerInvariant()
    } finally {
        $algorithm.Dispose()
    }
}

function Get-StringSha256 {
    param([Parameter(Mandatory = $true)][string]$Value)

    return Get-BytesSha256 -Bytes $script:StrictUtf8.GetBytes($Value)
}

function Get-FileSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    return Get-StreamedFileSha256 -Path $Path
}

function Get-StreamedFileSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = New-Object IO.FileStream(
        $Path,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        [IO.FileShare]::Read,
        1048576,
        [IO.FileOptions]::SequentialScan)
    try {
        $digest = $algorithm.ComputeHash($stream)
        return ([BitConverter]::ToString($digest)).Replace('-', '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}

function Assert-RegularFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    $full = [IO.Path]::GetFullPath($Path)
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $full
    Assert-GateCondition (Test-Path -LiteralPath $full -PathType Leaf) `
        'A required regular file is missing.'
    $attributes = [IO.File]::GetAttributes($full)
    Assert-GateCondition (
        ($attributes -band ([IO.FileAttributes]::Directory -bor
            [IO.FileAttributes]::ReparsePoint)) -eq 0) `
        'A required file is not a safe regular file.'
    return $full
}

function Assert-RegularDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $full
    Assert-GateCondition (Test-Path -LiteralPath $full -PathType Container) `
        'A required regular directory is missing.'
    $attributes = [IO.File]::GetAttributes($full)
    Assert-GateCondition (
        ($attributes -band [IO.FileAttributes]::Directory) -ne 0 -and
        ($attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) `
        'A required directory is unsafe.'
    return $full
}

function Get-OrdinalSortedStrings {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [object[]]$Values
    )

    $result = [string[]]@($Values | ForEach-Object { [string]$_ })
    [Array]::Sort($result, [StringComparer]::Ordinal)
    return $result
}

function Test-FullyQualifiedFileSystemPath {
    param([AllowNull()][string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or $Path.Contains([char]0)) {
        return $false
    }
    try {
        $root = [IO.Path]::GetPathRoot($Path)
        $null = [IO.Path]::GetFullPath($Path)
    } catch {
        return $false
    }
    if ([string]::IsNullOrWhiteSpace($root)) { return $false }
    if ($Path -cmatch '^[A-Za-z]:[\\/]') { return $true }
    if (-not $Path.StartsWith('\\', [StringComparison]::Ordinal)) {
        return $false
    }
    if (
        $Path.StartsWith('\\?\', [StringComparison]::Ordinal) -or
        $Path.StartsWith('\\.\', [StringComparison]::Ordinal)
    ) {
        return $false
    }
    $segments = @($root.Trim('\').Split(
        @([char]'\'),
        [StringSplitOptions]::RemoveEmptyEntries))
    return $segments.Count -eq 2
}

function Assert-ExactStringSequence {
    param(
        [Parameter(Mandatory = $true)][object[]]$Actual,
        [Parameter(Mandatory = $true)][string[]]$Expected,
        [Parameter(Mandatory = $true)][string]$Description
    )

    $actualStrings = [string[]]@($Actual | ForEach-Object { [string]$_ })
    Assert-GateCondition ($actualStrings.Count -eq $Expected.Count) `
        "$Description has an unexpected count."
    for ($index = 0; $index -lt $Expected.Count; $index++) {
        Assert-GateCondition (
            [string]::Equals(
                $actualStrings[$index],
                $Expected[$index],
                [StringComparison]::Ordinal)) `
            "$Description is not the exact canonical sequence."
    }
}

function Assert-ExactJsonProperties {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string[]]$Expected,
        [Parameter(Mandatory = $true)][string]$Description
    )

    Assert-GateCondition ($null -ne $Value) "$Description is null."
    Assert-ExactStringSequence `
        -Actual @($Value.PSObject.Properties.Name) `
        -Expected $Expected `
        -Description "$Description properties"
}

function Get-NormalizedApplicationCatalogName {
    param([Parameter(Mandatory = $true)][string]$Value)

    $folded = $Value.Replace(([char]0x00df).ToString(), 'ss')
    $folded = $folded.Replace(([char]0x1e9e).ToString(), 'ss')
    $folded = $folded.ToLowerInvariant()
    $folded = $folded.Normalize([Text.NormalizationForm]::FormKD)
    $builder = New-Object Text.StringBuilder
    $previousSeparator = $true
    foreach ($character in $folded.ToCharArray()) {
        if (
            [Globalization.CharUnicodeInfo]::GetUnicodeCategory($character) -eq
                [Globalization.UnicodeCategory]::NonSpacingMark
        ) {
            continue
        }

        if (
            ($character -ge [char]'a' -and $character -le [char]'z') -or
            ($character -ge [char]'0' -and $character -le [char]'9')
        ) {
            $null = $builder.Append($character)
            $previousSeparator = $false
        } elseif (-not $previousSeparator) {
            $null = $builder.Append(' ')
            $previousSeparator = $true
        }
    }
    return $builder.ToString().Trim()
}

function Assert-ApplicationCatalog {
    param([Parameter(Mandatory = $true)]$Value)

    Assert-ExactJsonProperties -Value $Value -Expected @(
        'version',
        'verified',
        'complete',
        'names'
    ) -Description 'installed core application catalog'
    Assert-GateCondition (
        $Value.version -is [int] -and
        [int]$Value.version -eq $script:ExpectedApplicationCatalogVersion) `
        'The installed core application catalog version is invalid.'
    Assert-GateCondition (
        $Value.verified -is [bool] -and $Value.verified -eq $true) `
        'The installed core application catalog is not verified.'
    Assert-GateCondition (
        $Value.complete -is [bool] -and $Value.complete -eq $true) `
        'The installed core application catalog is incomplete.'
    Assert-GateCondition ($Value.names -is [object[]]) `
        'The installed core application catalog names are not a JSON array.'

    $names = @($Value.names)
    Assert-GateCondition (
        $names.Count -le $script:MaximumApplicationCatalogNames) `
        'The installed core application catalog has too many names.'
    $normalizedNames = New-Object 'Collections.Generic.HashSet[string]' `
        ([StringComparer]::Ordinal)
    $totalUtf8Bytes = 0
    $totalEscapedUtf8Bytes = 0
    $previousName = $null
    foreach ($nameValue in $names) {
        Assert-GateCondition ($nameValue -is [string]) `
            'The installed core application catalog contains a non-text name.'
        $name = [string]$nameValue
        Assert-GateCondition (
            -not [string]::IsNullOrWhiteSpace($name) -and
            $name.Length -le $script:MaximumApplicationCatalogNameUtf8Bytes) `
            'The installed core application catalog contains an invalid name.'

        $escapedUtf8Bytes = 0
        for ($index = 0; $index -lt $name.Length; $index++) {
            $character = $name[$index]
            Assert-GateCondition (
                $character -ne [char]0xfffd -and
                -not [char]::IsControl($name, $index) -and
                (
                    -not [char]::IsWhiteSpace($name, $index) -or
                    $character -eq [char]' '
                )) `
                'The installed core application catalog contains an unsafe name.'
            $escapedUtf8Bytes += if (
                ($character -ge [char]'a' -and $character -le [char]'z') -or
                ($character -ge [char]'A' -and $character -le [char]'Z') -or
                ($character -ge [char]'0' -and $character -le [char]'9') -or
                $character -eq [char]' '
            ) { 1 } else { 6 }
        }

        try {
            $utf8Bytes = $script:StrictUtf8.GetByteCount($name)
        } catch [Text.EncoderFallbackException] {
            throw 'The installed core application catalog contains invalid Unicode.'
        }
        Assert-GateCondition (
            $utf8Bytes -le $script:MaximumApplicationCatalogNameUtf8Bytes) `
            'The installed core application catalog contains an oversized name.'
        Assert-GateCondition (
            $totalUtf8Bytes -le
                ($script:MaximumApplicationCatalogNamesUtf8Bytes - $utf8Bytes) -and
            $totalEscapedUtf8Bytes -le
                ($script:MaximumApplicationCatalogEscapedNamesUtf8Bytes -
                    $escapedUtf8Bytes)) `
            'The installed core application catalog exceeds its byte budget.'
        $totalUtf8Bytes += $utf8Bytes
        $totalEscapedUtf8Bytes += $escapedUtf8Bytes

        $normalizedName = Get-NormalizedApplicationCatalogName -Value $name
        Assert-GateCondition (
            $normalizedName.Length -gt 0 -and
            $normalizedNames.Add($normalizedName)) `
            'The installed core application catalog contains an ambiguous name.'
        if ($null -ne $previousName) {
            $caseInsensitiveComparison =
                [StringComparer]::OrdinalIgnoreCase.Compare($previousName, $name)
            $ordinalComparison =
                [StringComparer]::Ordinal.Compare($previousName, $name)
            Assert-GateCondition (
                $caseInsensitiveComparison -lt 0 -or
                (
                    $caseInsensitiveComparison -eq 0 -and
                    $ordinalComparison -lt 0
                )) `
                'The installed core application catalog is not canonically ordered.'
        }
        $previousName = $name
    }

    return [pscustomobject][ordered]@{
        present = $true
        version = [int]$Value.version
        verified = [bool]$Value.verified
        complete = [bool]$Value.complete
        name_count = [int]$names.Count
    }
}

function Read-StrictUtf8File {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [ValidateRange(1, 268435456)][int]$MaximumBytes
    )

    $full = Assert-RegularFile -Path $Path
    $item = Get-Item -LiteralPath $full -Force
    Assert-GateCondition ($item.Length -gt 0 -and $item.Length -le $MaximumBytes) `
        'A UTF-8 evidence file has an invalid byte length.'
    $bytes = [IO.File]::ReadAllBytes($full)
    Assert-GateCondition (
        $bytes.Length -lt 3 -or
        $bytes[0] -ne 0xef -or
        $bytes[1] -ne 0xbb -or
        $bytes[2] -ne 0xbf) `
        'A UTF-8 evidence file contains a forbidden BOM.'
    try {
        $text = $script:StrictUtf8.GetString($bytes)
    } catch [Text.DecoderFallbackException] {
        throw 'A UTF-8 evidence file contains malformed text.'
    }
    return [pscustomobject][ordered]@{
        path = $full
        bytes = [int64]$bytes.Length
        sha256 = Get-BytesSha256 -Bytes $bytes
        text = $text
    }
}

function Read-StrictJsonFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [ValidateRange(1, 268435456)][int]$MaximumBytes
    )

    $file = Read-StrictUtf8File -Path $Path -MaximumBytes $MaximumBytes
    try {
        $value = $file.text | ConvertFrom-Json
    } catch {
        throw 'A required JSON file is malformed.'
    }
    Assert-GateCondition ($null -ne $value) 'A required JSON file is null.'
    return [pscustomobject][ordered]@{
        path = $file.path
        bytes = $file.bytes
        sha256 = $file.sha256
        text = $file.text
        value = $value
    }
}

function Get-SemVerParts {
    param([Parameter(Mandatory = $true)][string]$Version)

    Assert-GateCondition (
        $Version.Length -ge 1 -and
        $Version.Length -le 128 -and
        $Version -cmatch $script:SemVerPattern) `
        'A supplied version is not canonical SemVer.'
    $withoutBuild = $Version.Split('+')[0]
    $mainAndPre = $withoutBuild.Split('-', 2)
    $numbers = $mainAndPre[0].Split('.')
    $prerelease = [string[]]@()
    if ($mainAndPre.Count -eq 2) {
        $prerelease = [string[]]$mainAndPre[1].Split('.')
    }
    return [pscustomobject]@{
        major = [int64]$numbers[0]
        minor = [int64]$numbers[1]
        patch = [int64]$numbers[2]
        prerelease = $prerelease
    }
}

function Compare-SemVerPrecedence {
    param(
        [Parameter(Mandatory = $true)][string]$Left,
        [Parameter(Mandatory = $true)][string]$Right
    )

    $leftParts = Get-SemVerParts -Version $Left
    $rightParts = Get-SemVerParts -Version $Right
    foreach ($name in @('major', 'minor', 'patch')) {
        if ($leftParts.$name -lt $rightParts.$name) { return -1 }
        if ($leftParts.$name -gt $rightParts.$name) { return 1 }
    }
    if ($leftParts.prerelease.Count -eq 0 -and $rightParts.prerelease.Count -eq 0) {
        return 0
    }
    if ($leftParts.prerelease.Count -eq 0) { return 1 }
    if ($rightParts.prerelease.Count -eq 0) { return -1 }
    $count = [Math]::Min($leftParts.prerelease.Count, $rightParts.prerelease.Count)
    for ($index = 0; $index -lt $count; $index++) {
        $leftIdentifier = $leftParts.prerelease[$index]
        $rightIdentifier = $rightParts.prerelease[$index]
        $leftNumeric = $leftIdentifier -cmatch '^(0|[1-9][0-9]*)$'
        $rightNumeric = $rightIdentifier -cmatch '^(0|[1-9][0-9]*)$'
        if ($leftNumeric -and $rightNumeric) {
            if ($leftIdentifier.Length -ne $rightIdentifier.Length) {
                $comparison = $leftIdentifier.Length.CompareTo(
                    $rightIdentifier.Length)
            } else {
                $comparison = [StringComparer]::Ordinal.Compare(
                    $leftIdentifier,
                    $rightIdentifier)
            }
        } elseif ($leftNumeric) {
            $comparison = -1
        } elseif ($rightNumeric) {
            $comparison = 1
        } else {
            $comparison = [StringComparer]::Ordinal.Compare(
                $leftIdentifier,
                $rightIdentifier)
        }
        if ($comparison -lt 0) { return -1 }
        if ($comparison -gt 0) { return 1 }
    }
    return $leftParts.prerelease.Count.CompareTo($rightParts.prerelease.Count)
}

function Get-CanonicalProductPaths {
    $localData = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::LocalApplicationData)
    $programs = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::Programs)
    Assert-GateCondition (
        -not [string]::IsNullOrWhiteSpace($localData) -and
        -not [string]::IsNullOrWhiteSpace($programs)) `
        'Windows did not expose the required per-user known folders.'
    $localData = [IO.Path]::GetFullPath($localData).TrimEnd('\', '/')
    $programs = [IO.Path]::GetFullPath($programs).TrimEnd('\', '/')
    $root = [IO.Path]::GetFullPath((Join-Path $localData 'Programs\BAXY'))
    $startMenuDirectory = [IO.Path]::GetFullPath((Join-Path $programs 'BAXY'))
    $paths = [pscustomobject]@{
        root = $root
        data = [IO.Path]::GetFullPath((Join-Path $localData 'BAXY'))
        versions = Join-Path $root 'versions'
        staging = Join-Path $root 'staging'
        stable_setup = Join-Path $root 'Baxy.Setup.exe'
        current = Join-Path $root 'current'
        previous = Join-Path $root 'current.previous'
        installation = Join-Path $root 'installation.v1.json'
        integration = Join-Path $root 'windows-integration.v1.json'
        start_menu_directory = $startMenuDirectory
        shortcut = Join-Path $startMenuDirectory 'BAXY.lnk'
    }
    foreach ($candidate in @(
        $paths.root,
        $paths.data,
        $paths.versions,
        $paths.staging,
        $paths.stable_setup,
        $paths.current,
        $paths.previous,
        $paths.installation,
        $paths.integration,
        $paths.start_menu_directory,
        $paths.shortcut
    )) {
        $null = Assert-ExistingPathChainHasNoReparsePoint -Path $candidate
    }
    return $paths
}

function Get-RepositorySourceState {
    $root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\', '/')
    $root = Assert-RegularDirectory -Path $root
    $head = [string](& git -C $root rev-parse --verify HEAD)
    Assert-GateCondition ($LASTEXITCODE -eq 0) 'Unable to resolve the source Git HEAD.'
    $head = $head.Trim().ToLowerInvariant()
    Assert-GateCondition (Test-LowerHex -Value $head -Length 40) `
        'The source Git HEAD is invalid.'
    $status = @(& git -C $root status --porcelain=v1 --untracked-files=all)
    Assert-GateCondition ($LASTEXITCODE -eq 0) 'Unable to inspect the source worktree.'
    Assert-GateCondition ($status.Count -eq 0) `
        'The in-place upgrade gate requires a clean source worktree.'
    return [pscustomobject]@{
        root = $root
        head = $head
    }
}

function Assert-NewEvidencePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-GateCondition (
        -not [string]::IsNullOrWhiteSpace($Path) -and
        (Test-FullyQualifiedFileSystemPath -Path $Path)) `
        'EvidencePath must be an absolute new file path.'
    $full = [IO.Path]::GetFullPath($Path)
    Assert-GateCondition (
        -not (Test-Path -LiteralPath $full) -and
        -not [IO.Path]::GetFileName($full).Contains(':')) `
        'EvidencePath must be new and cannot address an alternate data stream.'
    $parent = [IO.Path]::GetDirectoryName($full)
    Assert-GateCondition (-not [string]::IsNullOrWhiteSpace($parent)) `
        'EvidencePath has no parent.'
    $parent = Assert-RegularDirectory -Path $parent
    Assert-GateCondition (
        [string]::Equals(
            [IO.Path]::GetDirectoryName($full),
            $parent,
            [StringComparison]::OrdinalIgnoreCase)) `
        'EvidencePath did not canonicalize to its verified parent.'
    return $full
}

function Assert-EvidencePathOutsideProtectedRoots {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$ProtectedRoots
    )

    $full = [IO.Path]::GetFullPath($Path)
    foreach ($rootValue in @($ProtectedRoots | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_)
    })) {
        $root = [IO.Path]::GetFullPath($rootValue).TrimEnd('\', '/')
        Assert-GateCondition (
            -not [string]::Equals(
                $full,
                $root,
                [StringComparison]::OrdinalIgnoreCase) -and
            -not $full.StartsWith(
                $root + [IO.Path]::DirectorySeparatorChar,
                [StringComparison]::OrdinalIgnoreCase)) `
            'EvidencePath must remain outside source, build, installation, data, and Windows-integration roots.'
    }
    return $full
}

function ConvertTo-SafeEvidenceJson {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string[]]$ForbiddenPaths
    )

    $json = [string]($Value | ConvertTo-Json -Depth 20 -Compress)
    foreach ($forbidden in @($ForbiddenPaths | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_)
    } | Select-Object -Unique)) {
        Assert-GateCondition (
            $json.IndexOf($forbidden, [StringComparison]::OrdinalIgnoreCase) -lt 0) `
            'The evidence attempted to disclose a private local path.'
    }
    Assert-GateCondition (-not $json.Contains(':\')) `
        'The evidence attempted to disclose an absolute drive path.'
    return $json + "`n"
}

function Write-AtomicEvidence {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string[]]$ForbiddenPaths
    )

    $full = Assert-NewEvidencePath -Path $Path
    $parent = [IO.Path]::GetDirectoryName($full)
    $leaf = [IO.Path]::GetFileName($full)
    $temporary = Join-Path $parent (".$leaf.$([Guid]::NewGuid().ToString('N')).tmp")
    $text = ConvertTo-SafeEvidenceJson -Value $Value -ForbiddenPaths $ForbiddenPaths
    $bytes = $script:StrictUtf8.GetBytes($text)
    $created = $false
    try {
        $stream = New-Object IO.FileStream(
            $temporary,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write,
            [IO.FileShare]::None,
            4096,
            [IO.FileOptions]::WriteThrough)
        $created = $true
        try {
            $stream.Write($bytes, 0, $bytes.Length)
            $stream.Flush($true)
        } finally {
            $stream.Dispose()
        }
        Assert-RegularFile -Path $temporary | Out-Null
        [IO.File]::Move($temporary, $full)
        $created = $false
        $written = Read-StrictUtf8File -Path $full -MaximumBytes 1048576
        Assert-GateCondition (
            [string]::Equals($written.text, $text, [StringComparison]::Ordinal)) `
            'The atomically promoted evidence changed after publication.'
    } finally {
        if ($created -and (Test-Path -LiteralPath $temporary -PathType Leaf)) {
            Assert-RegularFile -Path $temporary | Out-Null
            [IO.File]::Delete($temporary)
        }
    }
}

function Assert-SafeRelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-GateCondition (
        -not [string]::IsNullOrWhiteSpace($Path) -and
        $Path.Length -le 240 -and
        -not $Path.Contains('\') -and
        -not $Path.Contains(':') -and
        -not $Path.StartsWith('/') -and
        -not $Path.EndsWith('/') -and
        -not $Path.Contains('//') -and
        -not $Path.Contains([char]0)) `
        'An installed manifest contains an unsafe relative path.'
    foreach ($segment in $Path.Split('/')) {
        Assert-GateCondition (
            $segment.Length -gt 0 -and
            $segment -cne '.' -and
            $segment -cne '..') `
            'An installed manifest contains an unsafe path segment.'
    }
}

function Get-SafeDescendantFile {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Relative
    )

    Assert-SafeRelativePath -Path $Relative
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $candidate = [IO.Path]::GetFullPath(
        (Join-Path $rootFull $Relative.Replace('/', '\')))
    Assert-GateCondition (
        $candidate.StartsWith(
            $rootFull + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) `
        'An installed manifest path escaped its immutable version root.'
    return Assert-RegularFile -Path $candidate
}

function Get-ContentIdentity {
    param([Parameter(Mandatory = $true)][object[]]$Records)

    $lookup = @{}
    foreach ($record in $Records) {
        Assert-GateCondition (-not $lookup.ContainsKey([string]$record.path)) `
            'A content identity contains a duplicate path.'
        $lookup.Add([string]$record.path, $record)
    }
    $paths = @(Get-OrdinalSortedStrings -Values @($lookup.Keys))
    $builder = New-Object Text.StringBuilder
    foreach ($path in $paths) {
        $record = $lookup[$path]
        $null = $builder.Append($path).Append([char]0)
        $null = $builder.Append(
            ([int64]$record.bytes).ToString(
                [Globalization.CultureInfo]::InvariantCulture)).Append([char]0)
        $null = $builder.Append([string]$record.sha256).Append("`n")
    }
    return Get-StringSha256 -Value $builder.ToString()
}

function Assert-IdentityEqual {
    param(
        [Parameter(Mandatory = $true)]$Actual,
        [Parameter(Mandatory = $true)]$Expected,
        [Parameter(Mandatory = $true)][string]$Description
    )

    foreach ($name in @(
        'version',
        'data_schema',
        'package_sha256',
        'manifest_sha256',
        'content_id'
    )) {
        Assert-GateCondition (
            [string]::Equals(
                [string]$Actual.$name,
                [string]$Expected.$name,
                [StringComparison]::Ordinal)) `
            "$Description changed its $name identity."
    }
}

function Read-InstallationPointer {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedVersion
    )

    $json = Read-StrictJsonFile -Path $Path -MaximumBytes 2048
    $value = $json.value
    Assert-ExactJsonProperties -Value $value -Expected @(
        'schema',
        'version',
        'data_schema',
        'package_sha256',
        'manifest_sha256',
        'content_id'
    ) -Description 'installation pointer'
    Assert-GateCondition (
        $value.schema -ceq 'baxy-current-v2' -and
        $value.version -ceq $ExpectedVersion -and
        [int]$value.data_schema -eq $script:DataSchema -and
        (Test-LowerHex -Value $value.package_sha256) -and
        (Test-LowerHex -Value $value.manifest_sha256) -and
        (Test-LowerHex -Value $value.content_id)) `
        'An installation pointer has an invalid identity.'
    return $value
}

function Get-InstalledVersionRecord {
    param(
        [Parameter(Mandatory = $true)]$Paths,
        [Parameter(Mandatory = $true)]$Pointer
    )

    $versionRoot = Join-Path $Paths.versions ([string]$Pointer.version)
    $versionRoot = Assert-RegularDirectory -Path $versionRoot
    Assert-TreeHasNoReparsePoint -Root $versionRoot

    $manifestFile = Read-StrictJsonFile `
        -Path (Join-Path $versionRoot 'build-manifest.json') `
        -MaximumBytes 262144
    $manifest = $manifestFile.value
    Assert-ExactJsonProperties -Value $manifest -Expected @(
        'schema',
        'product',
        'version',
        'data_schema',
        'configuration',
        'runtime',
        'target_framework',
        'authenticity',
        'source',
        'toolchain',
        'deployment',
        'file_count',
        'total_bytes',
        'files'
    ) -Description 'installed build manifest'
    Assert-GateCondition (
        $manifest.schema -ceq 'baxy-product-build-v4' -and
        $manifest.product -ceq 'BAXY' -and
        $manifest.version -ceq $Pointer.version -and
        [int]$manifest.data_schema -eq $script:DataSchema -and
        $manifest.configuration -ceq 'Release' -and
        $manifest.runtime -ceq 'win-x64' -and
        $manifest.target_framework -ceq 'net10.0-windows10.0.19041.0' -and
        $manifest.authenticity -ceq 'not_provided') `
        'An installed build manifest is outside the release contract.'
    Assert-ExactJsonProperties -Value $manifest.source -Expected @(
        'commit',
        'dirty',
        'provenance',
        'source_date_epoch'
    ) -Description 'installed build source'
    Assert-GateCondition (
        (Test-LowerHex -Value $manifest.source.commit -Length 40) -and
        $manifest.source.dirty -eq $false -and
        $manifest.source.provenance -ceq 'git_head_snapshot' -and
        [int64]$manifest.source.source_date_epoch -ge 0) `
        'An installed build source identity is invalid.'

    $records = @($manifest.files)
    Assert-GateCondition (
        $records.Count -ge 1 -and
        $records.Count -le 64 -and
        [int]$manifest.file_count -eq $records.Count) `
        'An installed build manifest has an invalid file count.'
    $caseInsensitive = New-Object 'Collections.Generic.HashSet[string]' `
        ([StringComparer]::OrdinalIgnoreCase)
    $recordPaths = New-Object 'Collections.Generic.List[string]'
    $verifiedRecords = New-Object 'Collections.Generic.List[object]'
    $totalBytes = [int64]0
    $previousPath = $null
    foreach ($record in $records) {
        Assert-ExactJsonProperties -Value $record -Expected @(
            'path',
            'bytes',
            'sha256'
        ) -Description 'installed build file record'
        $relative = [string]$record.path
        Assert-SafeRelativePath -Path $relative
        Assert-GateCondition ($caseInsensitive.Add($relative)) `
            'An installed build manifest contains a duplicate Windows path.'
        if ($null -ne $previousPath) {
            Assert-GateCondition (
                [StringComparer]::Ordinal.Compare($previousPath, $relative) -lt 0) `
                'Installed build file records are not in strict ordinal order.'
        }
        $previousPath = $relative
        $filePath = Get-SafeDescendantFile -Root $versionRoot -Relative $relative
        $item = Get-Item -LiteralPath $filePath -Force
        $actualSha256 = Get-FileSha256 -Path $filePath
        Assert-GateCondition (
            [int64]$record.bytes -eq [int64]$item.Length -and
            (Test-LowerHex -Value $record.sha256) -and
            $actualSha256 -ceq [string]$record.sha256) `
            'An installed file does not match its build manifest.'
        $totalBytes += [int64]$item.Length
        $recordPaths.Add($relative)
        $verifiedRecords.Add([pscustomobject]@{
            path = $relative
            bytes = [int64]$item.Length
            sha256 = $actualSha256
        })
    }
    Assert-GateCondition ($totalBytes -eq [int64]$manifest.total_bytes) `
        'The installed build total byte count is invalid.'
    Assert-GateCondition ($manifestFile.sha256 -ceq $Pointer.manifest_sha256) `
        'The installed build manifest hash differs from its pointer.'

    $checksumFile = Read-StrictUtf8File `
        -Path (Join-Path $versionRoot 'SHA256SUMS') `
        -MaximumBytes 65536
    $checksumRecords = @($verifiedRecords.ToArray())
    $checksumRecords += [pscustomobject]@{
        path = 'build-manifest.json'
        bytes = [int64]$manifestFile.bytes
        sha256 = [string]$manifestFile.sha256
    }
    $checksumLookup = @{}
    foreach ($record in $checksumRecords) {
        $checksumLookup.Add([string]$record.path, $record)
    }
    $checksumPaths = @(Get-OrdinalSortedStrings -Values @($checksumLookup.Keys))
    $expectedChecksumText = [string](($checksumPaths | ForEach-Object {
        "$($checksumLookup[$_].sha256)  $_"
    }) -join "`n") + "`n"
    Assert-GateCondition (
        [string]::Equals(
            $checksumFile.text,
            $expectedChecksumText,
            [StringComparison]::Ordinal)) `
        'The installed SHA256SUMS file is not exact.'

    $contentRecords = @($checksumRecords)
    $contentRecords += [pscustomobject]@{
        path = 'SHA256SUMS'
        bytes = [int64]$checksumFile.bytes
        sha256 = [string]$checksumFile.sha256
    }
    $contentId = Get-ContentIdentity -Records $contentRecords

    $attestationFile = Read-StrictJsonFile `
        -Path (Join-Path $versionRoot '.baxy-version.json') `
        -MaximumBytes 4096
    $attestation = $attestationFile.value
    Assert-ExactJsonProperties -Value $attestation -Expected @(
        'schema',
        'version',
        'data_schema',
        'package_sha256',
        'manifest_sha256',
        'content_id'
    ) -Description 'installed version attestation'
    Assert-GateCondition (
        $attestation.schema -ceq 'baxy-installed-version-v2' -and
        $attestation.version -ceq $Pointer.version -and
        [int]$attestation.data_schema -eq $script:DataSchema -and
        $attestation.package_sha256 -ceq $Pointer.package_sha256 -and
        $attestation.manifest_sha256 -ceq $manifestFile.sha256 -and
        $attestation.content_id -ceq $contentId) `
        'The installed version attestation does not match installed bytes.'
    Assert-IdentityEqual `
        -Actual $attestation `
        -Expected $Pointer `
        -Description 'installed version'

    $expectedFiles = @($recordPaths.ToArray())
    $expectedFiles += @(
        'build-manifest.json',
        'SHA256SUMS',
        '.baxy-version.json'
    )
    $expectedFiles = @(Get-OrdinalSortedStrings -Values $expectedFiles)
    $prefix = $versionRoot.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    $actualFiles = @(Get-ChildItem -LiteralPath $versionRoot -File -Recurse -Force |
        ForEach-Object {
            Assert-RegularFile -Path $_.FullName | Out-Null
            $_.FullName.Substring($prefix.Length).Replace('\', '/')
        })
    $actualFiles = @(Get-OrdinalSortedStrings -Values $actualFiles)
    Assert-ExactStringSequence `
        -Actual $actualFiles `
        -Expected $expectedFiles `
        -Description 'installed version file set'

    $corePath = Get-SafeDescendantFile `
        -Root $versionRoot `
        -Relative 'core/baxy-core.exe'
    return [pscustomobject]@{
        identity = $attestation
        source_commit = [string]$manifest.source.commit
        core_path = $corePath
        core_sha256 = Get-FileSha256 -Path $corePath
    }
}

function Get-PendingLifecycleArtifacts {
    param([Parameter(Mandatory = $true)]$Paths)

    $pending = New-Object 'Collections.Generic.List[string]'
    foreach ($name in $script:PendingLifecycleNames) {
        if (Test-Path -LiteralPath (Join-Path $Paths.root $name)) {
            $pending.Add($name)
        }
    }
    foreach ($evidence in @(Get-ChildItem `
        -LiteralPath $Paths.root `
        -Filter '.baxy-setup-verify-*.json' `
        -File `
        -Force `
        -ErrorAction SilentlyContinue)) {
        $pending.Add($evidence.Name)
    }
    if (Test-Path -LiteralPath $Paths.staging -PathType Container) {
        foreach ($entry in @(Get-ChildItem -LiteralPath $Paths.staging -Force)) {
            $pending.Add("staging/$($entry.Name)")
        }
    }
    if (Test-Path -LiteralPath $Paths.start_menu_directory -PathType Container) {
        foreach ($entry in @(Get-ChildItem `
            -LiteralPath $Paths.start_menu_directory `
            -Filter '.baxy-*.lnk' `
            -Force `
            -ErrorAction SilentlyContinue)) {
            $pending.Add("start-menu/$($entry.Name)")
        }
    }
    return [string[]]$pending.ToArray()
}

function Get-ImmutableVersionInventory {
    param([Parameter(Mandatory = $true)]$Paths)

    $versionsRoot = Assert-RegularDirectory -Path $Paths.versions
    Assert-TreeHasNoReparsePoint -Root $versionsRoot
    $entries = @(Get-ChildItem -LiteralPath $versionsRoot -Force)
    $names = New-Object 'Collections.Generic.List[string]'
    $caseInsensitive = New-Object 'Collections.Generic.HashSet[string]' `
        ([StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in $entries) {
        Assert-GateCondition (
            $entry.PSIsContainer -and
            ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) `
            'The immutable versions root contains a non-directory entry.'
        $null = Get-SemVerParts -Version $entry.Name
        Assert-GateCondition ($caseInsensitive.Add($entry.Name)) `
            'The immutable versions root contains an ambiguous version name.'
        $names.Add($entry.Name)
    }
    $orderedNames = @(Get-OrdinalSortedStrings -Values $names.ToArray())
    $snapshots = New-Object 'Collections.Generic.List[object]'
    foreach ($name in $orderedNames) {
        $versionRoot = Assert-RegularDirectory -Path (Join-Path $versionsRoot $name)
        Assert-TreeHasNoReparsePoint -Root $versionRoot
        $prefix =
            $versionRoot.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
        $directories = @(Get-ChildItem `
            -LiteralPath $versionRoot `
            -Directory `
            -Recurse `
            -Force |
            ForEach-Object {
                Assert-RegularDirectory -Path $_.FullName | Out-Null
                $_.FullName.Substring($prefix.Length).Replace('\', '/')
            })
        $directories = @(Get-OrdinalSortedStrings -Values $directories)
        $files = @(Get-ChildItem `
            -LiteralPath $versionRoot `
            -File `
            -Recurse `
            -Force |
            ForEach-Object {
                $path = Assert-RegularFile -Path $_.FullName
                [pscustomobject]@{
                    path = $path.Substring($prefix.Length).Replace('\', '/')
                    bytes = [int64]$_.Length
                    sha256 = Get-FileSha256 -Path $path
                }
            })
        $filePaths = @(Get-OrdinalSortedStrings -Values @($files.path))
        $fileLookup = @{}
        foreach ($file in $files) {
            Assert-GateCondition (-not $fileLookup.ContainsKey($file.path)) `
                'An immutable version tree contains an ambiguous file path.'
            $fileLookup.Add($file.path, $file)
        }
        $builder = New-Object Text.StringBuilder
        $null = $builder.Append("baxy-immutable-version-tree-v1`n")
        foreach ($directory in $directories) {
            $null = $builder.Append('D').Append([char]0)
            $null = $builder.Append($directory).Append("`n")
        }
        foreach ($path in $filePaths) {
            $file = $fileLookup[$path]
            $null = $builder.Append('F').Append([char]0)
            $null = $builder.Append($path).Append([char]0)
            $null = $builder.Append(
                ([int64]$file.bytes).ToString(
                    [Globalization.CultureInfo]::InvariantCulture)).Append([char]0)
            $null = $builder.Append($file.sha256).Append("`n")
        }
        $snapshots.Add([pscustomobject]@{
            version = $name
            tree_sha256 = Get-StringSha256 -Value $builder.ToString()
            files = [int]$filePaths.Count
            directories = [int]$directories.Count
        })
    }
    return [pscustomobject]@{
        names = [string[]]$orderedNames
        snapshots = [object[]]$snapshots.ToArray()
    }
}

function Get-PrivateDataInventory {
    param([Parameter(Mandatory = $true)][string]$Root)

    $root = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $exists = Assert-ExistingPathChainHasNoReparsePoint -Path $root
    if (-not $exists) {
        return [pscustomobject][ordered]@{
            schema = 'baxy-private-data-tree-v1'
            exists = $false
            tree_sha256 = Get-StringSha256 -Value (
                "baxy-private-data-tree-v1`nABSENT`n")
            files = 0
            directories = 0
            total_bytes = [int64]0
        }
    }

    $root = Assert-RegularDirectory -Path $root
    Assert-TreeHasNoReparsePoint -Root $root
    $prefix = $root + [IO.Path]::DirectorySeparatorChar
    $directoryRecords = @(Get-ChildItem `
        -LiteralPath $root `
        -Directory `
        -Recurse `
        -Force |
        ForEach-Object {
            $path = Assert-RegularDirectory -Path $_.FullName
            [pscustomobject]@{
                path = $path.Substring($prefix.Length).Replace('\', '/')
                attributes = [int]$_.Attributes
                last_write_utc_ticks = [int64]$_.LastWriteTimeUtc.Ticks
            }
        })
    $fileRecords = @(Get-ChildItem `
        -LiteralPath $root `
        -File `
        -Recurse `
        -Force |
        ForEach-Object {
            $path = Assert-RegularFile -Path $_.FullName
            $before = Get-Item -LiteralPath $path -Force
            $sha256 = Get-StreamedFileSha256 -Path $path
            $after = Get-Item -LiteralPath $path -Force
            Assert-GateCondition (
                [int64]$before.Length -eq [int64]$after.Length -and
                [int64]$before.LastWriteTimeUtc.Ticks -eq
                    [int64]$after.LastWriteTimeUtc.Ticks -and
                [int]$before.Attributes -eq [int]$after.Attributes) `
                'A private data file changed while its integrity snapshot was being read.'
            [pscustomobject]@{
                path = $path.Substring($prefix.Length).Replace('\', '/')
                bytes = [int64]$after.Length
                sha256 = $sha256
                attributes = [int]$after.Attributes
                last_write_utc_ticks = [int64]$after.LastWriteTimeUtc.Ticks
            }
        })

    $directoryPaths = @(Get-OrdinalSortedStrings -Values @(
        $directoryRecords | ForEach-Object { $_.path }
    ))
    $filePaths = @(Get-OrdinalSortedStrings -Values @(
        $fileRecords | ForEach-Object { $_.path }
    ))
    $directoryLookup = @{}
    foreach ($record in $directoryRecords) {
        Assert-GateCondition (-not $directoryLookup.ContainsKey($record.path)) `
            'The private data tree contains an ambiguous directory path.'
        $directoryLookup.Add($record.path, $record)
    }
    $fileLookup = @{}
    $totalBytes = [int64]0
    foreach ($record in $fileRecords) {
        Assert-GateCondition (
            -not $fileLookup.ContainsKey($record.path) -and
            -not $directoryLookup.ContainsKey($record.path)) `
            'The private data tree contains an ambiguous file path.'
        $fileLookup.Add($record.path, $record)
        Assert-GateCondition (
            [int64]$record.bytes -ge 0 -and
            $totalBytes -le ([int64]::MaxValue - [int64]$record.bytes)) `
            'The private data tree byte count overflowed.'
        $totalBytes += [int64]$record.bytes
    }

    $builder = New-Object Text.StringBuilder
    $null = $builder.Append("baxy-private-data-tree-v1`nPRESENT`n")
    foreach ($path in $directoryPaths) {
        $record = $directoryLookup[$path]
        $null = $builder.Append('D').Append([char]0)
        $null = $builder.Append($path).Append([char]0)
        $null = $builder.Append(
            ([int]$record.attributes).ToString(
                [Globalization.CultureInfo]::InvariantCulture)).Append([char]0)
        $null = $builder.Append(
            ([int64]$record.last_write_utc_ticks).ToString(
                [Globalization.CultureInfo]::InvariantCulture)).Append("`n")
    }
    foreach ($path in $filePaths) {
        $record = $fileLookup[$path]
        $null = $builder.Append('F').Append([char]0)
        $null = $builder.Append($path).Append([char]0)
        $null = $builder.Append(
            ([int64]$record.bytes).ToString(
                [Globalization.CultureInfo]::InvariantCulture)).Append([char]0)
        $null = $builder.Append($record.sha256).Append([char]0)
        $null = $builder.Append(
            ([int]$record.attributes).ToString(
                [Globalization.CultureInfo]::InvariantCulture)).Append([char]0)
        $null = $builder.Append(
            ([int64]$record.last_write_utc_ticks).ToString(
                [Globalization.CultureInfo]::InvariantCulture)).Append("`n")
    }
    return [pscustomobject][ordered]@{
        schema = 'baxy-private-data-tree-v1'
        exists = $true
        tree_sha256 = Get-StringSha256 -Value $builder.ToString()
        files = [int]$filePaths.Count
        directories = [int]$directoryPaths.Count
        total_bytes = $totalBytes
    }
}

function Assert-PrivateDataInventoryEqual {
    param(
        [Parameter(Mandatory = $true)]$Actual,
        [Parameter(Mandatory = $true)]$Expected
    )

    foreach ($name in @(
        'schema',
        'exists',
        'tree_sha256',
        'files',
        'directories',
        'total_bytes'
    )) {
        Assert-GateCondition (
            [string]::Equals(
                [string]$Actual.$name,
                [string]$Expected.$name,
                [StringComparison]::Ordinal)) `
            'The private BAXY data tree changed during the lifecycle.'
    }
}

function Assert-VersionInventoryTransition {
    param(
        [Parameter(Mandatory = $true)]$Baseline,
        [Parameter(Mandatory = $true)]$Observed,
        [Parameter(Mandatory = $true)][string]$AddedVersion
    )

    Assert-GateCondition (-not ($Baseline.names -ccontains $AddedVersion)) `
        'The candidate was already present in the baseline version inventory.'
    $expectedNames = @($Baseline.names)
    $expectedNames += $AddedVersion
    $expectedNames = @(Get-OrdinalSortedStrings -Values $expectedNames)
    Assert-ExactStringSequence `
        -Actual $Observed.names `
        -Expected $expectedNames `
        -Description 'immutable version directory inventory'
    foreach ($before in $Baseline.snapshots) {
        $matches = @($Observed.snapshots | Where-Object {
            $_.version -ceq $before.version
        })
        Assert-GateCondition (
            $matches.Count -eq 1 -and
            $matches[0].tree_sha256 -ceq $before.tree_sha256 -and
            [int]$matches[0].files -eq [int]$before.files -and
            [int]$matches[0].directories -eq [int]$before.directories) `
            'A pre-existing immutable version tree changed during the lifecycle.'
    }
}

function Assert-VersionInventoryEqual {
    param(
        [Parameter(Mandatory = $true)]$Actual,
        [Parameter(Mandatory = $true)]$Expected
    )

    Assert-ExactStringSequence `
        -Actual $Actual.names `
        -Expected $Expected.names `
        -Description 'immutable version directory inventory'
    foreach ($before in $Expected.snapshots) {
        $matches = @($Actual.snapshots | Where-Object {
            $_.version -ceq $before.version
        })
        Assert-GateCondition (
            $matches.Count -eq 1 -and
            $matches[0].tree_sha256 -ceq $before.tree_sha256 -and
            [int]$matches[0].files -eq [int]$before.files -and
            [int]$matches[0].directories -eq [int]$before.directories) `
            'An immutable version tree changed during the lifecycle.'
    }
}

function Get-OwnedSetupProcesses {
    return @(Get-Process `
        -Name $script:OwnedSetupProcessNames `
        -ErrorAction SilentlyContinue)
}

function Get-SetupProcessSnapshot {
    $records = New-Object 'Collections.Generic.List[object]'
    foreach ($imageName in @(
        'Baxy.Setup.exe',
        'Baxy.Setup.next.exe',
        'Baxy.Setup.previous.exe'
    )) {
        foreach ($process in @(Get-CimInstance `
            -ClassName Win32_Process `
            -Filter "Name = '$imageName'" `
            -ErrorAction Stop)) {
            $records.Add([pscustomobject]@{
                process_id = [int]$process.ProcessId
                parent_process_id = [int]$process.ParentProcessId
                name = [string]$process.Name
                executable_path = [string]$process.ExecutablePath
                creation_utc = $process.CreationDate.ToUniversalTime()
            })
        }
    }
    return [object[]]$records.ToArray()
}

function Get-OwnedSetupDescendants {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [object[]]$Snapshot,
        [Parameter(Mandatory = $true)][int]$RootProcessId
    )

    $pending = New-Object 'Collections.Generic.Queue[object]'
    $pending.Enqueue([pscustomobject]@{
        process_id = $RootProcessId
        depth = 0
    })
    $seen = New-Object 'Collections.Generic.HashSet[int]'
    $null = $seen.Add($RootProcessId)
    $descendants = New-Object 'Collections.Generic.List[object]'
    while ($pending.Count -gt 0) {
        $parent = $pending.Dequeue()
        foreach ($record in @($Snapshot | Where-Object {
            [int]$_.parent_process_id -eq [int]$parent.process_id
        })) {
            if (-not $seen.Add([int]$record.process_id)) { continue }
            $ownedName = @(
                'Baxy.Setup.exe',
                'Baxy.Setup.next.exe',
                'Baxy.Setup.previous.exe'
            ) -ccontains $record.name
            if (-not $ownedName) { continue }
            $withDepth = [pscustomobject]@{
                process_id = [int]$record.process_id
                parent_process_id = [int]$record.parent_process_id
                name = [string]$record.name
                executable_path = [string]$record.executable_path
                creation_utc = [DateTime]$record.creation_utc
                depth = [int]$parent.depth + 1
            }
            $descendants.Add($withDepth)
            $pending.Enqueue($withDepth)
        }
    }
    return [object[]]$descendants.ToArray()
}

function Test-AllowedSetupExecutablePath {
    param(
        [AllowNull()][string]$Path,
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [string[]]$AllowedPaths
    )

    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    try {
        $full = [IO.Path]::GetFullPath($Path)
    } catch {
        return $false
    }
    foreach ($allowedValue in $AllowedPaths) {
        if ([string]::IsNullOrWhiteSpace($allowedValue)) { continue }
        if ([string]::Equals(
            $full,
            [IO.Path]::GetFullPath($allowedValue),
            [StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Stop-VerifiedSetupProcessRecord {
    param(
        [Parameter(Mandatory = $true)]$Record,
        [Parameter(Mandatory = $true)][string[]]$AllowedPaths,
        [Parameter(Mandatory = $true)][DateTime]$NotBeforeUtc
    )

    Assert-GateCondition (
        [DateTime]$Record.creation_utc -ge $NotBeforeUtc.AddSeconds(-2) -and
        (Test-AllowedSetupExecutablePath `
            -Path ([string]$Record.executable_path) `
            -AllowedPaths $AllowedPaths)) `
        'Refusing to terminate a Setup process outside the gate-owned identity.'
    $process = Get-Process `
        -Id ([int]$Record.process_id) `
        -ErrorAction SilentlyContinue
    if ($null -eq $process) { return }
    try {
        $null = $process.SafeHandle
        $actualPath = [IO.Path]::GetFullPath($process.Path)
        $actualStart = $process.StartTime.ToUniversalTime()
        Assert-GateCondition (
            (Test-AllowedSetupExecutablePath `
                -Path $actualPath `
                -AllowedPaths $AllowedPaths) -and
            [Math]::Abs(
                ($actualStart - [DateTime]$Record.creation_utc).TotalSeconds) -lt 1) `
            'Refusing to terminate a Setup PID whose bound identity changed.'
        $process.Kill()
        Assert-GateCondition ($process.WaitForExit(5000)) `
            'A gate-owned Setup process did not terminate.'
    } finally {
        $process.Dispose()
    }
}

function Stop-GateOwnedSetupProcesses {
    param(
        [Parameter(Mandatory = $true)][DateTime]$NotBeforeUtc,
        [Parameter(Mandatory = $true)][string[]]$AllowedPaths
    )

    $snapshot = @(Get-SetupProcessSnapshot)
    foreach ($record in @($snapshot | Sort-Object creation_utc -Descending)) {
        if ([DateTime]$record.creation_utc -lt $NotBeforeUtc.AddSeconds(-2)) {
            continue
        }
        Stop-VerifiedSetupProcessRecord `
            -Record $record `
            -AllowedPaths $AllowedPaths `
            -NotBeforeUtc $NotBeforeUtc
    }
    Assert-GateCondition (@(Get-OwnedSetupProcesses).Count -eq 0) `
        'A gate-owned Setup process survived termination.'
}

function Stop-OwnedSetupProcessTree {
    param(
        [Parameter(Mandatory = $true)]$RootProcess,
        [Parameter(Mandatory = $true)][DateTime]$NotBeforeUtc,
        [Parameter(Mandatory = $true)][string[]]$AllowedPaths
    )

    $terminationFailure = $null
    try {
        $snapshot = @(Get-SetupProcessSnapshot)
        $descendants = @(Get-OwnedSetupDescendants `
            -Snapshot $snapshot `
            -RootProcessId ([int]$RootProcess.Id))
        foreach ($record in @($descendants | Sort-Object depth -Descending)) {
            Stop-VerifiedSetupProcessRecord `
                -Record $record `
                -AllowedPaths $AllowedPaths `
                -NotBeforeUtc $NotBeforeUtc
        }
    } catch {
        $terminationFailure = $_
    } finally {
        try {
            if (-not $RootProcess.HasExited) {
                $RootProcess.Kill()
                Assert-GateCondition ($RootProcess.WaitForExit(5000)) `
                    'The gate-owned Setup root process did not terminate.'
            }
        } catch {
            if ($null -eq $terminationFailure) { $terminationFailure = $_ }
        }
    }
    try {
        Stop-GateOwnedSetupProcesses `
            -NotBeforeUtc $NotBeforeUtc `
            -AllowedPaths $AllowedPaths
    } catch {
        if ($null -eq $terminationFailure) { $terminationFailure = $_ }
    }
    if ($null -ne $terminationFailure) { throw $terminationFailure }
}

function Get-OwnedProductProcesses {
    $result = New-Object 'Collections.Generic.List[object]'
    foreach ($process in @(Get-Process `
        -Name 'Baxy', 'baxy-core' `
        -ErrorAction SilentlyContinue)) {
        $result.Add($process)
    }
    foreach ($process in @(Get-OwnedSetupProcesses)) {
        $result.Add($process)
    }
    return [object[]]$result.ToArray()
}

function Assert-NoOwnedProductProcesses {
    Assert-GateCondition (@(Get-OwnedProductProcesses).Count -eq 0) `
        'A BAXY product or Setup process is still running.'
}

function Read-InstallationIdentity {
    param([Parameter(Mandatory = $true)]$Paths)

    $json = Read-StrictJsonFile -Path $Paths.installation -MaximumBytes 4096
    $value = $json.value
    Assert-ExactJsonProperties -Value $value -Expected @(
        'schema',
        'install_id',
        'data_schema',
        'installation_root'
    ) -Description 'installation identity'
    $parsedId = [Guid]::Empty
    Assert-GateCondition (
        $value.schema -ceq 'baxy-installation-v1' -and
        [Guid]::TryParseExact([string]$value.install_id, 'N', [ref]$parsedId) -and
        $parsedId -ne [Guid]::Empty -and
        $value.install_id -ceq $parsedId.ToString('N') -and
        [int]$value.data_schema -eq $script:DataSchema -and
        $value.installation_root -ceq $Paths.root) `
        'The immutable installation identity is invalid.'
    return $value
}

function Assert-ShortcutExact {
    param(
        [Parameter(Mandatory = $true)]$Paths,
        [Parameter(Mandatory = $true)]$Expected
    )

    $shortcutPath = Assert-RegularFile -Path $Paths.shortcut
    $item = Get-Item -LiteralPath $shortcutPath -Force
    $sha256 = Get-FileSha256 -Path $shortcutPath
    Assert-GateCondition (
        [int64]$Expected.bytes -eq [int64]$item.Length -and
        (Test-LowerHex -Value $Expected.sha256) -and
        $Expected.sha256 -ceq $sha256) `
        'The Start Menu shortcut differs from committed integration state.'

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $null
    try {
        $shortcut = $shell.CreateShortcut($shortcutPath)
        Assert-GateCondition (
            $shortcut.TargetPath -ceq $Paths.stable_setup -and
            $shortcut.Arguments -ceq '--launch' -and
            $shortcut.WorkingDirectory -ceq $Paths.root -and
            $shortcut.IconLocation -ceq "$($Paths.stable_setup),0" -and
            [int]$shortcut.WindowStyle -eq 1 -and
            $shortcut.Description -ceq 'BAXY') `
            'The Start Menu shortcut semantic target is invalid.'
    } finally {
        if ($null -ne $shortcut -and [Runtime.InteropServices.Marshal]::IsComObject($shortcut)) {
            [Runtime.InteropServices.Marshal]::FinalReleaseComObject($shortcut) | Out-Null
        }
        if ([Runtime.InteropServices.Marshal]::IsComObject($shell)) {
            [Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell) | Out-Null
        }
    }
    return [pscustomobject]@{
        sha256 = $sha256
        bytes = [int64]$item.Length
    }
}

function Assert-UninstallRegistryExact {
    param(
        [Parameter(Mandatory = $true)]$Paths,
        [Parameter(Mandatory = $true)]$Installation,
        [Parameter(Mandatory = $true)]$Integration
    )

    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::CurrentUser,
        [Microsoft.Win32.RegistryView]::Registry64)
    $key = $null
    try {
        $key = $base.OpenSubKey(
            'Software\Microsoft\Windows\CurrentVersion\Uninstall\BAXY',
            $false)
        Assert-GateCondition ($null -ne $key) `
            'The exact per-user BAXY uninstall registry key is missing.'
        Assert-GateCondition (@($key.GetSubKeyNames()).Count -eq 0) `
            'The BAXY uninstall registry key contains unexpected subkeys.'
        $quotedSetup = '"' + $Paths.stable_setup + '"'
        $expected = [ordered]@{
            DisplayName = [pscustomobject]@{ value = 'BAXY'; kind = 'String' }
            DisplayVersion = [pscustomobject]@{
                value = [string]$Integration.active.version
                kind = 'String'
            }
            Publisher = [pscustomobject]@{ value = 'BAXY'; kind = 'String' }
            InstallLocation = [pscustomobject]@{ value = $Paths.root; kind = 'String' }
            UninstallString = [pscustomobject]@{
                value = "$quotedSetup --uninstall"
                kind = 'String'
            }
            QuietUninstallString = [pscustomobject]@{
                value = "$quotedSetup --uninstall --keep-data --quiet"
                kind = 'String'
            }
            DisplayIcon = [pscustomobject]@{
                value = "$quotedSetup,0"
                kind = 'String'
            }
            NoModify = [pscustomobject]@{ value = 1; kind = 'DWord' }
            NoRepair = [pscustomobject]@{ value = 1; kind = 'DWord' }
            EstimatedSize = [pscustomobject]@{
                value = [int]$Integration.estimated_size_kilobytes
                kind = 'DWord'
            }
            BaxyInstallId = [pscustomobject]@{
                value = [string]$Installation.install_id
                kind = 'String'
            }
            BaxyDataSchema = [pscustomobject]@{
                value = $script:DataSchema
                kind = 'DWord'
            }
            BaxyStableSetupSha256 = [pscustomobject]@{
                value = [string]$Integration.stable_setup.host_sha256
                kind = 'String'
            }
        }
        $actualNames = @(Get-OrdinalSortedStrings -Values @($key.GetValueNames()))
        $expectedNames = @(Get-OrdinalSortedStrings -Values @($expected.Keys))
        Assert-ExactStringSequence `
            -Actual $actualNames `
            -Expected $expectedNames `
            -Description 'uninstall registry value set'
        foreach ($name in $expectedNames) {
            $actualKind = $key.GetValueKind($name).ToString()
            $actualValue = $key.GetValue(
                $name,
                $null,
                [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
            Assert-GateCondition (
                $actualKind -ceq $expected[$name].kind -and
                $actualValue -ceq $expected[$name].value) `
                'The BAXY uninstall registry snapshot is not exact.'
        }
        return [pscustomobject]@{
            display_version = [string]$Integration.active.version
            stable_setup_sha256 = [string]$Integration.stable_setup.host_sha256
            estimated_size_kilobytes = [int]$Integration.estimated_size_kilobytes
        }
    } finally {
        if ($null -ne $key) { $key.Dispose() }
        $base.Dispose()
    }
}

function Get-InstalledState {
    param(
        [Parameter(Mandatory = $true)]$Paths,
        [Parameter(Mandatory = $true)][string]$ExpectedCurrent,
        [Parameter(Mandatory = $true)][string]$ExpectedPrevious,
        [Parameter(Mandatory = $true)][string]$ExpectedStableVersion,
        [Parameter(Mandatory = $true)][string]$ExpectedStableSetupSha256,
        [Parameter(Mandatory = $true)][string]$ExpectedStablePackageSha256,
        [AllowNull()]$ExpectedCurrentIdentity = $null
    )

    Assert-NoOwnedProductProcesses
    Assert-RegularDirectory -Path $Paths.root | Out-Null
    Assert-RegularDirectory -Path $Paths.versions | Out-Null
    Assert-RegularDirectory -Path $Paths.staging | Out-Null
    Assert-GateCondition (@(Get-PendingLifecycleArtifacts -Paths $Paths).Count -eq 0) `
        'The BAXY lifecycle has pending transaction artifacts.'

    $installation = Read-InstallationIdentity -Paths $Paths
    $current = Read-InstallationPointer `
        -Path $Paths.current `
        -ExpectedVersion $ExpectedCurrent
    $previous = Read-InstallationPointer `
        -Path $Paths.previous `
        -ExpectedVersion $ExpectedPrevious
    Assert-GateCondition ($current.version -cne $previous.version) `
        'current and current.previous identify the same version.'
    $currentVersion = Get-InstalledVersionRecord -Paths $Paths -Pointer $current
    $previousVersion = Get-InstalledVersionRecord -Paths $Paths -Pointer $previous
    if ($null -ne $ExpectedCurrentIdentity) {
        Assert-IdentityEqual `
            -Actual $current `
            -Expected $ExpectedCurrentIdentity `
            -Description 'expected active candidate'
        Assert-GateCondition (
            $currentVersion.source_commit -ceq
                [string]$ExpectedCurrentIdentity.source_commit) `
            'The installed candidate came from an unexpected source commit.'
    }

    $integrationJson = Read-StrictJsonFile `
        -Path $Paths.integration `
        -MaximumBytes 16384
    $integration = $integrationJson.value
    Assert-ExactJsonProperties -Value $integration -Expected @(
        'schema',
        'install_id',
        'data_schema',
        'installation_root',
        'active',
        'stable_setup',
        'shortcut',
        'estimated_size_kilobytes'
    ) -Description 'Windows integration state'
    Assert-ExactJsonProperties -Value $integration.active -Expected @(
        'schema',
        'version',
        'data_schema',
        'package_sha256',
        'manifest_sha256',
        'content_id'
    ) -Description 'Windows integration active identity'
    Assert-ExactJsonProperties -Value $integration.stable_setup -Expected @(
        'version',
        'embedded_package_sha256',
        'host_sha256',
        'host_bytes'
    ) -Description 'Windows integration stable Setup identity'
    Assert-ExactJsonProperties -Value $integration.shortcut -Expected @(
        'sha256',
        'bytes'
    ) -Description 'Windows integration shortcut identity'
    Assert-GateCondition (
        $integration.schema -ceq 'baxy-windows-integration-v1' -and
        $integration.install_id -ceq $installation.install_id -and
        [int]$integration.data_schema -eq $script:DataSchema -and
        $integration.installation_root -ceq $Paths.root -and
        $integration.stable_setup.version -ceq $ExpectedStableVersion -and
        $integration.stable_setup.embedded_package_sha256 -ceq
            $ExpectedStablePackageSha256 -and
        $integration.stable_setup.host_sha256 -ceq
            $ExpectedStableSetupSha256 -and
        [int64]$integration.stable_setup.host_bytes -gt 0 -and
        [int]$integration.estimated_size_kilobytes -gt 0) `
        'The committed Windows integration state is invalid.'
    Assert-IdentityEqual `
        -Actual $integration.active `
        -Expected $current `
        -Description 'Windows integration active product'

    $stableSetup = Assert-RegularFile -Path $Paths.stable_setup
    $stableItem = Get-Item -LiteralPath $stableSetup -Force
    $stableSha256 = Get-FileSha256 -Path $stableSetup
    Assert-GateCondition (
        $stableSha256 -ceq $ExpectedStableSetupSha256 -and
        $stableSha256 -ceq $integration.stable_setup.host_sha256 -and
        [int64]$stableItem.Length -eq
            [int64]$integration.stable_setup.host_bytes) `
        'The stable Setup host differs from committed integration state.'
    $stableVersionParts = Get-SemVerParts -Version $ExpectedStableVersion
    $expectedFileVersion =
        "$($stableVersionParts.major).$($stableVersionParts.minor).$($stableVersionParts.patch).0"
    Assert-GateCondition (
        $stableItem.VersionInfo.FileVersion -ceq $expectedFileVersion) `
        'The stable Setup host has the wrong file version.'

    $shortcut = Assert-ShortcutExact `
        -Paths $Paths `
        -Expected $integration.shortcut
    $registry = Assert-UninstallRegistryExact `
        -Paths $Paths `
        -Installation $installation `
        -Integration $integration

    $summary = [ordered]@{
        current = [string]$current.version
        previous = [string]$previous.version
        active_package_sha256 = [string]$current.package_sha256
        active_manifest_sha256 = [string]$current.manifest_sha256
        active_content_id = [string]$current.content_id
        stable_setup_version = [string]$integration.stable_setup.version
        stable_setup_sha256 = $stableSha256
        stable_embedded_package_sha256 =
            [string]$integration.stable_setup.embedded_package_sha256
        shortcut_sha256 = [string]$shortcut.sha256
        registry_display_version = [string]$registry.display_version
        install_id_sha256 = Get-StringSha256 -Value ([string]$installation.install_id)
        data_schema = [int]$installation.data_schema
        pending_artifacts = 0
        owned_processes = 0
    }
    return [pscustomobject]@{
        installation = $installation
        current = $current
        previous = $previous
        integration = $integration
        current_version = $currentVersion
        previous_version = $previousVersion
        summary = $summary
    }
}

function Get-CandidateSetupArtifact {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedVersion,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit
    )

    Assert-GateCondition (Test-FullyQualifiedFileSystemPath -Path $Path) `
        'CandidateSetup must be an absolute path.'
    $setupPath = Assert-RegularFile -Path ([IO.Path]::GetFullPath($Path))
    Assert-GateCondition (
        [IO.Path]::GetFileName($setupPath) -ceq 'Baxy.Setup.exe') `
        'CandidateSetup must be named exactly Baxy.Setup.exe.'
    $root = Assert-RegularDirectory -Path ([IO.Path]::GetDirectoryName($setupPath))
    Assert-TreeHasNoReparsePoint -Root $root
    $entries = @(Get-ChildItem -LiteralPath $root -Force)
    $entryNames = @(Get-OrdinalSortedStrings -Values @($entries.Name))
    $expectedNames = @(Get-OrdinalSortedStrings -Values @(
        'Baxy.Setup.exe',
        'SHA256SUMS',
        'setup-manifest.json'
    ))
    Assert-ExactStringSequence `
        -Actual $entryNames `
        -Expected $expectedNames `
        -Description 'candidate Setup output'
    Assert-GateCondition (@($entries | Where-Object { $_.PSIsContainer }).Count -eq 0) `
        'The candidate Setup output contains a directory.'

    $manifestFile = Read-StrictJsonFile `
        -Path (Join-Path $root 'setup-manifest.json') `
        -MaximumBytes 262144
    $manifest = $manifestFile.value
    Assert-ExactJsonProperties -Value $manifest -Expected @(
        'schema',
        'product',
        'version',
        'data_schema',
        'configuration',
        'runtime',
        'target_framework',
        'authenticity',
        'authenticode',
        'source',
        'embedded_package',
        'deployment',
        'toolchain',
        'file'
    ) -Description 'candidate Setup manifest'
    Assert-ExactJsonProperties -Value $manifest.source -Expected @(
        'commit',
        'provenance',
        'source_date_epoch'
    ) -Description 'candidate Setup source'
    Assert-ExactJsonProperties -Value $manifest.embedded_package -Expected @(
        'name',
        'sha256',
        'bytes',
        'manifest_sha256',
        'content_id',
        'attestation_sha256'
    ) -Description 'candidate embedded package'
    Assert-ExactJsonProperties -Value $manifest.file -Expected @(
        'path',
        'bytes',
        'sha256'
    ) -Description 'candidate Setup file'

    $setupItem = Get-Item -LiteralPath $setupPath -Force
    $setupSha256 = Get-FileSha256 -Path $setupPath
    $expectedPackageName =
        "BAXY-$ExpectedVersion-$($ExpectedCommit.Substring(0, 12))-win-x64.zip"
    Assert-GateCondition (
        $manifest.schema -ceq 'baxy-setup-build-v2' -and
        $manifest.product -ceq 'BAXY' -and
        $manifest.version -ceq $ExpectedVersion -and
        [int]$manifest.data_schema -eq $script:DataSchema -and
        $manifest.configuration -ceq 'Release' -and
        $manifest.runtime -ceq 'win-x64' -and
        $manifest.target_framework -ceq 'net10.0-windows10.0.19041.0' -and
        $manifest.authenticity -ceq 'not_provided' -and
        $manifest.authenticode -ceq 'NotSigned' -and
        $manifest.source.commit -ceq $ExpectedCommit -and
        $manifest.source.provenance -ceq 'git_head_snapshot' -and
        [int64]$manifest.source.source_date_epoch -ge 0 -and
        $manifest.embedded_package.name -ceq $expectedPackageName -and
        (Test-LowerHex -Value $manifest.embedded_package.sha256) -and
        [int64]$manifest.embedded_package.bytes -gt 0 -and
        (Test-LowerHex -Value $manifest.embedded_package.manifest_sha256) -and
        (Test-LowerHex -Value $manifest.embedded_package.content_id) -and
        (Test-LowerHex -Value $manifest.embedded_package.attestation_sha256) -and
        $manifest.file.path -ceq 'Baxy.Setup.exe' -and
        [int64]$manifest.file.bytes -eq [int64]$setupItem.Length -and
        $manifest.file.sha256 -ceq $setupSha256) `
        'The candidate Setup manifest does not match its exact release artifact.'

    $versionParts = Get-SemVerParts -Version $ExpectedVersion
    $expectedFileVersion =
        "$($versionParts.major).$($versionParts.minor).$($versionParts.patch).0"
    Assert-GateCondition ($setupItem.VersionInfo.FileVersion -ceq $expectedFileVersion) `
        'The candidate Setup has the wrong PE file version.'
    $signature = Get-AuthenticodeSignature -LiteralPath $setupPath
    Assert-GateCondition ($signature.Status.ToString() -ceq 'NotSigned') `
        'The candidate Setup Authenticode state differs from its manifest.'

    $checksums = Read-StrictUtf8File `
        -Path (Join-Path $root 'SHA256SUMS') `
        -MaximumBytes 65536
    $expectedChecksums =
        "$setupSha256  Baxy.Setup.exe`n$($manifestFile.sha256)  setup-manifest.json`n"
    Assert-GateCondition (
        [string]::Equals(
            $checksums.text,
            $expectedChecksums,
            [StringComparison]::Ordinal)) `
        'The candidate Setup SHA256SUMS file is not exact.'

    return [pscustomobject]@{
        path = $setupPath
        root = $root
        sha256 = $setupSha256
        bytes = [int64]$setupItem.Length
        manifest_sha256 = [string]$manifestFile.sha256
        version = [string]$manifest.version
        source_commit = [string]$manifest.source.commit
        source_date_epoch = [int64]$manifest.source.source_date_epoch
        package_sha256 = [string]$manifest.embedded_package.sha256
        package_bytes = [int64]$manifest.embedded_package.bytes
        package_manifest_sha256 =
            [string]$manifest.embedded_package.manifest_sha256
        content_id = [string]$manifest.embedded_package.content_id
        expected_identity = [pscustomobject]@{
            version = [string]$manifest.version
            data_schema = [int]$manifest.data_schema
            package_sha256 = [string]$manifest.embedded_package.sha256
            manifest_sha256 =
                [string]$manifest.embedded_package.manifest_sha256
            content_id = [string]$manifest.embedded_package.content_id
            source_commit = [string]$manifest.source.commit
        }
    }
}

function Read-RecoveredCandidateEvidence {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Candidate,
        [Parameter(Mandatory = $true)][string]$ExpectedCurrent,
        [Parameter(Mandatory = $true)][string]$ExpectedInitialPrevious,
        [Parameter(Mandatory = $true)][string]$ExpectedCandidate,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )

    Assert-GateCondition (
        (Test-FullyQualifiedFileSystemPath -Path $Path) -and
        -not [IO.Path]::GetFileName($Path).Contains(':')) `
        'PriorFailureEvidencePath must be an absolute regular file without an alternate data stream.'
    $file = Read-StrictJsonFile `
        -Path ([IO.Path]::GetFullPath($Path)) `
        -MaximumBytes 65536
    Assert-GateCondition ($file.sha256 -ceq $ExpectedSha256) `
        'The prior failed lifecycle evidence hash is not the pinned identity.'
    $value = $file.value
    Assert-ExactJsonProperties -Value $value -Expected @(
        'schema',
        'status',
        'operation',
        'started_utc',
        'completed_utc',
        'phase',
        'failure_code',
        'exception_type',
        'versions',
        'candidate_setup_sha256',
        'recovery',
        'privacy'
    ) -Description 'prior failed lifecycle evidence'
    Assert-ExactJsonProperties -Value $value.versions -Expected @(
        'initial_current',
        'initial_previous',
        'candidate'
    ) -Description 'prior failed lifecycle versions'
    Assert-ExactJsonProperties -Value $value.recovery -Expected @(
        'attempted',
        'status',
        'final_candidate_attested',
        'exception_type',
        'cleanup_exception_type',
        'observation_exception_type',
        'current',
        'previous',
        'setup_exit_code',
        'setup_duration_ms',
        'settle_duration_ms',
        'residual_setup_processes'
    ) -Description 'prior failed lifecycle recovery'
    Assert-ExactJsonProperties -Value $value.privacy -Expected @(
        'local_paths_included',
        'exception_messages_included'
    ) -Description 'prior failed lifecycle privacy'
    Assert-GateCondition (
        $value.schema -ceq 'baxy-in-place-upgrade-attestation-v1' -and
        $value.status -ceq 'failed' -and
        $value.operation -ceq 'upgrade_rollback_reactivation' -and
        $value.phase -ceq 'install_candidate' -and
        $value.failure_code -ceq 'in_place_upgrade_gate_failed' -and
        $value.exception_type -is [string] -and
        -not [string]::IsNullOrWhiteSpace($value.exception_type) -and
        $value.versions.initial_current -ceq $ExpectedCurrent -and
        $value.versions.initial_previous -ceq $ExpectedInitialPrevious -and
        $value.versions.candidate -ceq $ExpectedCandidate -and
        $value.candidate_setup_sha256 -ceq $Candidate.sha256 -and
        $value.recovery.attempted -is [bool] -and
        [bool]$value.recovery.attempted -and
        $value.recovery.status -ceq 'passed' -and
        $value.recovery.final_candidate_attested -is [bool] -and
        [bool]$value.recovery.final_candidate_attested -and
        $null -eq $value.recovery.exception_type -and
        $null -eq $value.recovery.cleanup_exception_type -and
        $null -eq $value.recovery.observation_exception_type -and
        $value.recovery.current -ceq $ExpectedCandidate -and
        $value.recovery.previous -ceq $ExpectedCurrent -and
        $value.recovery.setup_exit_code -is [int] -and
        [int]$value.recovery.setup_exit_code -eq 0 -and
        ($value.recovery.setup_duration_ms -is [int] -or
            $value.recovery.setup_duration_ms -is [long]) -and
        [int64]$value.recovery.setup_duration_ms -ge 0 -and
        ($value.recovery.settle_duration_ms -is [int] -or
            $value.recovery.settle_duration_ms -is [long]) -and
        [int64]$value.recovery.settle_duration_ms -ge 0 -and
        $value.recovery.residual_setup_processes -is [int] -and
        [int]$value.recovery.residual_setup_processes -eq 0 -and
        $value.privacy.local_paths_included -is [bool] -and
        $value.privacy.exception_messages_included -is [bool] -and
        -not [bool]$value.privacy.local_paths_included -and
        -not [bool]$value.privacy.exception_messages_included) `
        'The prior failed lifecycle evidence does not prove an exact recovered candidate state.'
    return [pscustomobject]@{
        path = [IO.Path]::GetFullPath($Path)
        sha256 = [string]$file.sha256
        value = $value
    }
}

function Invoke-HiddenSetupProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)][int]$MaximumSeconds,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256,
        [string[]]$AdditionalAllowedSetupPaths = @()
    )

    $setupPath = Assert-RegularFile -Path $Path
    Assert-GateCondition ((Get-FileSha256 -Path $setupPath) -ceq $ExpectedSha256) `
        'A Setup executable changed before invocation.'
    $start = @{
        FilePath = $setupPath
        WorkingDirectory = [IO.Path]::GetDirectoryName($setupPath)
        PassThru = $true
        WindowStyle = 'Hidden'
    }
    if ($Arguments.Count -gt 0) { $start.ArgumentList = $Arguments }
    $allowedSetupPaths = [string[]]@($setupPath)
    $allowedSetupPaths += [string[]]$AdditionalAllowedSetupPaths
    $processStartedUtc = [DateTime]::UtcNow
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $process = Start-Process @start
    try {
        if (-not $process.WaitForExit($MaximumSeconds * 1000)) {
            Stop-OwnedSetupProcessTree `
                -RootProcess $process `
                -NotBeforeUtc $processStartedUtc `
                -AllowedPaths $allowedSetupPaths
            throw 'A hidden Setup process exceeded its reviewed timeout.'
        }
        $exitCode = $process.ExitCode
    } finally {
        $watch.Stop()
        $process.Dispose()
    }
    Assert-GateCondition ($exitCode -eq 0) `
        "A hidden Setup process failed with exit code $exitCode."
    Assert-GateCondition ((Get-FileSha256 -Path $setupPath) -ceq $ExpectedSha256) `
        'A Setup executable changed during invocation.'
    return [pscustomobject]@{
        exit_code = $exitCode
        duration_ms = [int64]$watch.ElapsedMilliseconds
    }
}

function Invoke-EmbeddedCandidateVerification {
    param(
        [Parameter(Mandatory = $true)]$Candidate,
        [Parameter(Mandatory = $true)][int]$MaximumSeconds
    )

    $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/')
    $null = Assert-ExistingPathChainHasNoReparsePoint -Path $temporaryRoot
    $evidencePath = Join-Path $temporaryRoot (
        "baxy-upgrade-verify-$([Guid]::NewGuid().ToString('N')).json")
    Assert-GateCondition (-not (Test-Path -LiteralPath $evidencePath)) `
        'A unique embedded verification path is unexpectedly occupied.'
    try {
        $quotedEvidence = '"' + $evidencePath.Replace('"', '""') + '"'
        $execution = Invoke-HiddenSetupProcess `
            -Path $Candidate.path `
            -Arguments @('--verify-embedded', '--evidence', $quotedEvidence) `
            -MaximumSeconds $MaximumSeconds `
            -ExpectedSha256 $Candidate.sha256
        $evidenceFile = Read-StrictJsonFile `
            -Path $evidencePath `
            -MaximumBytes 4096
        $evidence = $evidenceFile.value
        Assert-ExactJsonProperties -Value $evidence -Expected @(
            'schema',
            'status',
            'version',
            'data_schema',
            'package_sha256',
            'package_bytes',
            'manifest_sha256',
            'content_id',
            'source_date_epoch',
            'commit'
        ) -Description 'candidate embedded verification evidence'
        Assert-GateCondition (
            $evidence.schema -ceq 'baxy-setup-embedded-verification-v2' -and
            $evidence.status -ceq 'passed' -and
            $evidence.version -ceq $Candidate.version -and
            [int]$evidence.data_schema -eq $script:DataSchema -and
            $evidence.package_sha256 -ceq $Candidate.package_sha256 -and
            [int64]$evidence.package_bytes -eq $Candidate.package_bytes -and
            $evidence.manifest_sha256 -ceq
                $Candidate.package_manifest_sha256 -and
            $evidence.content_id -ceq $Candidate.content_id -and
            [int64]$evidence.source_date_epoch -eq
                $Candidate.source_date_epoch -and
            $evidence.commit -ceq $Candidate.source_commit) `
            'The candidate failed its physical embedded-package verification.'
        return [pscustomobject]@{
            status = 'passed'
            exit_code = [int]$execution.exit_code
            duration_ms = [int64]$execution.duration_ms
            evidence_sha256 = [string]$evidenceFile.sha256
        }
    } finally {
        if (Test-Path -LiteralPath $evidencePath -PathType Leaf) {
            Assert-GateCondition (
                [string]::Equals(
                    [IO.Path]::GetDirectoryName($evidencePath),
                    $temporaryRoot,
                    [StringComparison]::OrdinalIgnoreCase) -and
                [IO.Path]::GetFileName($evidencePath) -cmatch
                    '^baxy-upgrade-verify-[0-9a-f]{32}\.json$') `
                'Refusing to remove a non-owned verification temporary.'
            Assert-RegularFile -Path $evidencePath | Out-Null
            [IO.File]::Delete($evidencePath)
        }
    }
}

function Wait-ForInstalledState {
    param(
        [Parameter(Mandatory = $true)]$Paths,
        [Parameter(Mandatory = $true)][hashtable]$Expected,
        [Parameter(Mandatory = $true)][int]$MaximumSeconds
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($MaximumSeconds)
    $watch = [Diagnostics.Stopwatch]::StartNew()
    do {
        $setupProcesses = @(Get-OwnedSetupProcesses)
        $pending = @(Get-PendingLifecycleArtifacts -Paths $Paths)
        if ($setupProcesses.Count -eq 0 -and $pending.Count -eq 0) {
            try {
                $state = Get-InstalledState `
                    -Paths $Paths `
                    -ExpectedCurrent $Expected.current `
                    -ExpectedPrevious $Expected.previous `
                    -ExpectedStableVersion $Expected.stable_version `
                    -ExpectedStableSetupSha256 $Expected.stable_setup_sha256 `
                    -ExpectedStablePackageSha256 $Expected.stable_package_sha256 `
                    -ExpectedCurrentIdentity $Expected.current_identity
                Start-Sleep -Milliseconds 250
                Assert-GateCondition (
                    @(Get-OwnedSetupProcesses).Count -eq 0 -and
                    @(Get-PendingLifecycleArtifacts -Paths $Paths).Count -eq 0) `
                    'The lifecycle changed while its committed state was being attested.'
                $watch.Stop()
                return [pscustomobject]@{
                    state = $state
                    settle_duration_ms = [int64]$watch.ElapsedMilliseconds
                }
            } catch {
                # A Setup host can exit immediately before its hidden resume child
                # appears. Keep polling until the complete committed state exists.
            }
        }
        Start-Sleep -Milliseconds 250
    } until ([DateTime]::UtcNow -ge $deadline)
    $watch.Stop()
    throw 'The BAXY lifecycle did not settle within the reviewed timeout.'
}

function Remove-OwnedCoreSmokeRoot {
    param(
        [Parameter(Mandatory = $true)][string]$TemporaryParent,
        [Parameter(Mandatory = $true)][string]$SmokeRoot
    )

    $parent = [IO.Path]::GetFullPath($TemporaryParent).TrimEnd('\', '/')
    $root = [IO.Path]::GetFullPath($SmokeRoot).TrimEnd('\', '/')
    Assert-StrictDescendantPath -Parent $parent -Child $root
    Assert-GateCondition (
        [IO.Path]::GetDirectoryName($root) -ceq $parent -and
        [IO.Path]::GetFileName($root) -cmatch
            '^baxy-upgrade-core-smoke-[0-9a-f]{32}$') `
        'Refusing to remove a non-owned core smoke profile.'
    if (Test-Path -LiteralPath $root) {
        Assert-TreeHasNoReparsePoint -Root $root
        Remove-TreeFailClosed -AllowedRoot $parent -Target $root
    }
}

function Invoke-InstalledCoreSmoke {
    param(
        [Parameter(Mandatory = $true)][string]$CorePath,
        [Parameter(Mandatory = $true)][string]$ExpectedVersion,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256,
        [Parameter(Mandatory = $true)][string]$PrivateDataParent,
        [Parameter(Mandatory = $true)][int]$MaximumSeconds,
        [switch]$RequireApplicationCatalog
    )

    Assert-NoOwnedProductProcesses
    $core = Assert-RegularFile -Path $CorePath
    Assert-GateCondition ((Get-FileSha256 -Path $core) -ceq $ExpectedSha256) `
        'The installed core changed before its smoke.'
    $localData = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::LocalApplicationData,
        [Environment+SpecialFolderOption]::DoNotVerify)
    Assert-GateCondition (-not [string]::IsNullOrWhiteSpace($localData)) `
        'Windows did not expose private local application storage.'
    $expectedPrivateParent = [IO.Path]::GetFullPath(
        (Join-Path $localData 'BAXY')).TrimEnd('\', '/')
    $temporaryParent = Assert-RegularDirectory -Path $PrivateDataParent
    Assert-GateCondition (
        [string]::Equals(
            $temporaryParent,
            $expectedPrivateParent,
            [StringComparison]::OrdinalIgnoreCase)) `
        'The isolated core smoke parent is not BAXY private local storage.'
    $smokeRoot = Join-Path $temporaryParent (
        "baxy-upgrade-core-smoke-$([Guid]::NewGuid().ToString('N'))")
    Assert-GateCondition (-not (Test-Path -LiteralPath $smokeRoot)) `
        'A unique core smoke profile is unexpectedly occupied.'

    $process = $null
    $standardInput = $null
    $stderrTask = $null
    $previousInputEncoding = [Console]::InputEncoding
    $inputEncodingChanged = $false
    try {
        $startInfo = New-Object Diagnostics.ProcessStartInfo
        $startInfo.FileName = $core
        $startInfo.WorkingDirectory = [IO.Path]::GetDirectoryName($core)
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
        $startInfo.RedirectStandardInput = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $startInfo.EnvironmentVariables['BAXY_DATA_DIR'] = $smokeRoot

        $process = New-Object Diagnostics.Process
        $process.StartInfo = $startInfo
        [Console]::InputEncoding = $script:StrictUtf8
        $inputEncodingChanged = $true
        Assert-GateCondition ($process.Start()) 'The installed core did not start.'
        $standardInput = $process.StandardInput
        [Console]::InputEncoding = $previousInputEncoding
        $inputEncodingChanged = $false
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $helloTask = $process.StandardOutput.ReadLineAsync()
        if (-not $helloTask.Wait([Math]::Min($MaximumSeconds, 30) * 1000)) {
            try { $process.Kill() } catch { }
            throw 'The installed core did not emit its JSONL hello in time.'
        }
        $helloLine = $helloTask.GetAwaiter().GetResult()
        Assert-GateCondition (-not [string]::IsNullOrWhiteSpace($helloLine)) `
            'The installed core emitted no JSONL hello.'
        try {
            $hello = $helloLine | ConvertFrom-Json
        } catch {
            throw 'The installed core hello is not valid JSONL.'
        }
        $expectedHelloProperties = @(
            'type',
            'protocol',
            'coreVersion',
            'pid',
            'capabilities'
        )
        if ($RequireApplicationCatalog) {
            $expectedHelloProperties += 'applicationCatalog'
        }
        Assert-ExactJsonProperties `
            -Value $hello `
            -Expected $expectedHelloProperties `
            -Description 'installed core hello'
        $capabilities = @($hello.capabilities)
        $applicationCatalog = if ($RequireApplicationCatalog) {
            Assert-ApplicationCatalog -Value $hello.applicationCatalog
        } else {
            [pscustomobject][ordered]@{
                present = $false
                version = $null
                verified = $null
                complete = $null
                name_count = 0
            }
        }
        Assert-GateCondition (
            $hello.type -ceq 'hello' -and
            $hello.protocol -ceq 'baxy.local.v1' -and
            $hello.coreVersion -ceq $ExpectedVersion -and
            [int]$hello.pid -eq $process.Id -and
            $capabilities.Count -eq $script:ExpectedCapabilities) `
            'The installed core hello differs from the release protocol contract.'
        $names = New-Object 'Collections.Generic.HashSet[string]' `
            ([StringComparer]::Ordinal)
        foreach ($capability in $capabilities) {
            Assert-GateCondition (
                $capability.name -is [string] -and
                -not [string]::IsNullOrWhiteSpace($capability.name) -and
                $names.Add([string]$capability.name)) `
                'The installed core exposes an invalid or duplicate capability.'
        }

        foreach ($privateState in @(
            (Join-Path $smokeRoot 'journal\missions.jsonl'),
            (Join-Path $smokeRoot 'journal\missions.jsonl.anchor'),
            (Join-Path $smokeRoot 'security\journal-hmac.v2.key')
        )) {
            Assert-RegularFile -Path $privateState | Out-Null
        }

        $standardInput.Close()
        if (-not $process.WaitForExit($MaximumSeconds * 1000)) {
            try { $process.Kill() } catch { }
            try { $null = $process.WaitForExit(5000) } catch { }
            throw 'The installed core did not exit after JSONL stdin closed.'
        }
        Assert-GateCondition ($stderrTask.Wait(5000)) `
            'The installed core stderr did not drain.'
        $stderr = $stderrTask.GetAwaiter().GetResult()
        $remainingStdout = $process.StandardOutput.ReadToEnd()
        Assert-GateCondition (
            $process.ExitCode -eq 0 -and
            [string]::IsNullOrEmpty($stderr) -and
            [string]::IsNullOrEmpty($remainingStdout)) `
            'The installed core smoke did not close cleanly.'
        Assert-GateCondition ((Get-FileSha256 -Path $core) -ceq $ExpectedSha256) `
            'The installed core changed during its smoke.'

        return [ordered]@{
            status = 'passed'
            protocol = [string]$hello.protocol
            core_version = [string]$hello.coreVersion
            capabilities = [int]$capabilities.Count
            exit_code = [int]$process.ExitCode
            stderr_bytes = 0
            trailing_stdout_bytes = 0
            isolated_private_profile = $true
            profile_removed = $true
            core_sha256 = $ExpectedSha256
            application_catalog = $applicationCatalog
        }
    } finally {
        if ($inputEncodingChanged) {
            [Console]::InputEncoding = $previousInputEncoding
        }
        if ($null -ne $process) {
            if (-not $process.HasExited) {
                try { $process.Kill() } catch { }
                try { $null = $process.WaitForExit(5000) } catch { }
            }
            $process.Dispose()
        }
        Remove-OwnedCoreSmokeRoot `
            -TemporaryParent $temporaryParent `
            -SmokeRoot $smokeRoot
    }
}

function Get-LifecycleAllowedSetupPaths {
    param(
        [Parameter(Mandatory = $true)]$Candidate,
        [Parameter(Mandatory = $true)]$Paths
    )

    return [string[]]@(
        $Candidate.path,
        $Paths.stable_setup,
        (Join-Path $Paths.root 'Baxy.Setup.next.exe'),
        (Join-Path $Paths.root 'Baxy.Setup.previous.exe')
    )
}

function Invoke-BestEffortCandidateReactivation {
    param(
        [Parameter(Mandatory = $true)]$Candidate,
        [Parameter(Mandatory = $true)]$Paths,
        [Parameter(Mandatory = $true)][string]$ExpectedPreviousVersion,
        [Parameter(Mandatory = $true)]$BaselineInventory,
        [Parameter(Mandatory = $true)]$BaselinePrivateData,
        [Parameter(Mandatory = $true)][DateTime]$MutationStartedUtc,
        [switch]$CandidateAlreadyInBaseline,
        [Parameter(Mandatory = $true)][int]$MaximumSeconds
    )

    $allowedSetupPaths = Get-LifecycleAllowedSetupPaths `
        -Candidate $Candidate `
        -Paths $Paths
    Stop-GateOwnedSetupProcesses `
        -NotBeforeUtc $MutationStartedUtc `
        -AllowedPaths $allowedSetupPaths
    $execution = Invoke-HiddenSetupProcess `
        -Path $Candidate.path `
        -MaximumSeconds $MaximumSeconds `
        -ExpectedSha256 $Candidate.sha256 `
        -AdditionalAllowedSetupPaths $allowedSetupPaths
    $wait = Wait-ForInstalledState `
        -Paths $Paths `
        -Expected @{
            current = $Candidate.version
            previous = $ExpectedPreviousVersion
            stable_version = $Candidate.version
            stable_setup_sha256 = $Candidate.sha256
            stable_package_sha256 = $Candidate.package_sha256
            current_identity = $Candidate.expected_identity
        } `
        -MaximumSeconds $MaximumSeconds
    $inventory = Get-ImmutableVersionInventory -Paths $Paths
    if ($CandidateAlreadyInBaseline.IsPresent) {
        Assert-VersionInventoryEqual `
            -Actual $inventory `
            -Expected $BaselineInventory
    } else {
        Assert-VersionInventoryTransition `
            -Baseline $BaselineInventory `
            -Observed $inventory `
            -AddedVersion $Candidate.version
    }
    $privateData = Get-PrivateDataInventory -Root $Paths.data
    Assert-PrivateDataInventoryEqual `
        -Actual $privateData `
        -Expected $BaselinePrivateData
    Assert-NoOwnedProductProcesses
    return [pscustomobject]@{
        state = $wait.state
        inventory = $inventory
        private_data = $privateData
        setup_exit_code = [int]$execution.exit_code
        setup_duration_ms = [int64]$execution.duration_ms
        settle_duration_ms = [int64]$wait.settle_duration_ms
    }
}

function Invoke-RecoveredCandidateValidationPhase {
    param(
        [Parameter(Mandatory = $true)]$Paths,
        [Parameter(Mandatory = $true)]$Baseline,
        [Parameter(Mandatory = $true)]$PriorEvidence,
        [Parameter(Mandatory = $true)][string]$CandidateVersion,
        [Parameter(Mandatory = $true)][int]$MaximumSeconds
    )

    $candidateSmoke = Invoke-InstalledCoreSmoke `
        -CorePath $Baseline.current_version.core_path `
        -ExpectedVersion $CandidateVersion `
        -ExpectedSha256 $Baseline.current_version.core_sha256 `
        -PrivateDataParent $Paths.data `
        -MaximumSeconds $MaximumSeconds `
        -RequireApplicationCatalog
    $step = [ordered]@{
        name = 'validate_recovered_candidate'
        status = 'passed'
        prior_failure_evidence_sha256 = $PriorEvidence.sha256
        recovered_setup_exit_code =
            [int]$PriorEvidence.value.recovery.setup_exit_code
        recovered_setup_duration_ms =
            [int64]$PriorEvidence.value.recovery.setup_duration_ms
        recovered_settle_duration_ms =
            [int64]$PriorEvidence.value.recovery.settle_duration_ms
        state = $Baseline.summary
        core_smoke = $candidateSmoke
    }
    return [pscustomobject][ordered]@{
        PSTypeName = 'Baxy.InPlaceUpgrade.CandidatePhase'
        state = $Baseline
        step = $step
    }
}

function Invoke-CandidateInstallPhase {
    param(
        [Parameter(Mandatory = $true)]$Candidate,
        [Parameter(Mandatory = $true)]$Paths,
        [Parameter(Mandatory = $true)]$Baseline,
        [Parameter(Mandatory = $true)]$BaselineInventory,
        [Parameter(Mandatory = $true)][string]$BaselineInstallId,
        [Parameter(Mandatory = $true)][string]$BaselineShortcutSha256,
        [Parameter(Mandatory = $true)][string[]]$AllowedSetupPaths,
        [Parameter(Mandatory = $true)][string]$CandidateVersion,
        [Parameter(Mandatory = $true)][string]$ExpectedCurrentVersion,
        [Parameter(Mandatory = $true)][int]$MaximumSeconds
    )

    $installExecution = Invoke-HiddenSetupProcess `
        -Path $Candidate.path `
        -MaximumSeconds $MaximumSeconds `
        -ExpectedSha256 $Candidate.sha256 `
        -AdditionalAllowedSetupPaths $AllowedSetupPaths
    $installWait = Wait-ForInstalledState `
        -Paths $Paths `
        -Expected @{
            current = $CandidateVersion
            previous = $ExpectedCurrentVersion
            stable_version = $CandidateVersion
            stable_setup_sha256 = $Candidate.sha256
            stable_package_sha256 = $Candidate.package_sha256
            current_identity = $Candidate.expected_identity
        } `
        -MaximumSeconds $MaximumSeconds
    $installedCandidate = $installWait.state
    $candidateInventory = Get-ImmutableVersionInventory -Paths $Paths
    Assert-VersionInventoryTransition `
        -Baseline $BaselineInventory `
        -Observed $candidateInventory `
        -AddedVersion $CandidateVersion
    Assert-IdentityEqual `
        -Actual $installedCandidate.previous `
        -Expected $Baseline.current `
        -Description 'candidate update previous pointer'
    Assert-GateCondition (
        $installedCandidate.installation.install_id -ceq $BaselineInstallId -and
        $installedCandidate.integration.shortcut.sha256 -ceq
            $BaselineShortcutSha256) `
        'The candidate update changed immutable installation ownership or shortcut identity.'
    $candidateSmoke = Invoke-InstalledCoreSmoke `
        -CorePath $installedCandidate.current_version.core_path `
        -ExpectedVersion $CandidateVersion `
        -ExpectedSha256 $installedCandidate.current_version.core_sha256 `
        -PrivateDataParent $Paths.data `
        -MaximumSeconds $MaximumSeconds `
        -RequireApplicationCatalog
    $step = [ordered]@{
        name = 'install_candidate'
        status = 'passed'
        setup_exit_code = [int]$installExecution.exit_code
        setup_duration_ms = [int64]$installExecution.duration_ms
        settle_duration_ms = [int64]$installWait.settle_duration_ms
        state = $installedCandidate.summary
        core_smoke = $candidateSmoke
    }
    return [pscustomobject][ordered]@{
        PSTypeName = 'Baxy.InPlaceUpgrade.CandidatePhase'
        state = $installedCandidate
        step = $step
    }
}

function Invoke-CandidateRollbackPhase {
    param(
        [Parameter(Mandatory = $true)]$Candidate,
        [Parameter(Mandatory = $true)]$Paths,
        [Parameter(Mandatory = $true)]$Baseline,
        [Parameter(Mandatory = $true)]$BaselineInventory,
        [Parameter(Mandatory = $true)]$InstalledCandidate,
        [Parameter(Mandatory = $true)][string]$BaselineInstallId,
        [Parameter(Mandatory = $true)][string]$BaselineShortcutSha256,
        [Parameter(Mandatory = $true)][string[]]$AllowedSetupPaths,
        [Parameter(Mandatory = $true)][string]$CandidateVersion,
        [Parameter(Mandatory = $true)][string]$ExpectedCurrentVersion,
        [switch]$Continuation,
        [Parameter(Mandatory = $true)][int]$MaximumSeconds
    )

    $rollbackExecution = Invoke-HiddenSetupProcess `
        -Path $Paths.stable_setup `
        -Arguments @('--rollback') `
        -MaximumSeconds $MaximumSeconds `
        -ExpectedSha256 $Candidate.sha256 `
        -AdditionalAllowedSetupPaths $AllowedSetupPaths
    $rollbackWait = Wait-ForInstalledState `
        -Paths $Paths `
        -Expected @{
            current = $ExpectedCurrentVersion
            previous = $CandidateVersion
            stable_version = $CandidateVersion
            stable_setup_sha256 = $Candidate.sha256
            stable_package_sha256 = $Candidate.package_sha256
            current_identity = $null
        } `
        -MaximumSeconds $MaximumSeconds
    $rolledBack = $rollbackWait.state
    $rollbackInventory = Get-ImmutableVersionInventory -Paths $Paths
    if ($Continuation.IsPresent) {
        Assert-VersionInventoryEqual `
            -Actual $rollbackInventory `
            -Expected $BaselineInventory
    } else {
        Assert-VersionInventoryTransition `
            -Baseline $BaselineInventory `
            -Observed $rollbackInventory `
            -AddedVersion $CandidateVersion
    }
    $expectedRollbackIdentity = if ($Continuation.IsPresent) {
        $Baseline.previous
    } else {
        $Baseline.current
    }
    Assert-IdentityEqual `
        -Actual $rolledBack.current `
        -Expected $expectedRollbackIdentity `
        -Description 'rollback active pointer'
    Assert-IdentityEqual `
        -Actual $rolledBack.previous `
        -Expected $InstalledCandidate.current `
        -Description 'rollback previous pointer'
    Assert-GateCondition (
        $rolledBack.installation.install_id -ceq $BaselineInstallId -and
        $rolledBack.integration.shortcut.sha256 -ceq
            $BaselineShortcutSha256) `
        'Rollback changed immutable installation ownership or shortcut identity.'
    $rollbackSmoke = Invoke-InstalledCoreSmoke `
        -CorePath $rolledBack.current_version.core_path `
        -ExpectedVersion $ExpectedCurrentVersion `
        -ExpectedSha256 $rolledBack.current_version.core_sha256 `
        -PrivateDataParent $Paths.data `
        -MaximumSeconds $MaximumSeconds
    $step = [ordered]@{
        name = 'rollback'
        status = 'passed'
        setup_exit_code = [int]$rollbackExecution.exit_code
        setup_duration_ms = [int64]$rollbackExecution.duration_ms
        settle_duration_ms = [int64]$rollbackWait.settle_duration_ms
        state = $rolledBack.summary
        core_smoke = $rollbackSmoke
    }
    return [pscustomobject][ordered]@{
        PSTypeName = 'Baxy.InPlaceUpgrade.RollbackPhase'
        step = $step
        expected_rollback_identity = $expectedRollbackIdentity
    }
}

function Invoke-CandidateReactivationPhase {
    param(
        [Parameter(Mandatory = $true)]$Candidate,
        [Parameter(Mandatory = $true)]$Paths,
        [Parameter(Mandatory = $true)]$Baseline,
        [Parameter(Mandatory = $true)]$BaselineInventory,
        [Parameter(Mandatory = $true)]$InstalledCandidate,
        [Parameter(Mandatory = $true)]$ExpectedRollbackIdentity,
        [Parameter(Mandatory = $true)][string]$BaselineInstallId,
        [Parameter(Mandatory = $true)][string]$BaselineShortcutSha256,
        [Parameter(Mandatory = $true)][string[]]$AllowedSetupPaths,
        [Parameter(Mandatory = $true)][string]$CandidateVersion,
        [Parameter(Mandatory = $true)][string]$ExpectedCurrentVersion,
        [switch]$Continuation,
        [Parameter(Mandatory = $true)][int]$MaximumSeconds
    )

    $reactivateExecution = Invoke-HiddenSetupProcess `
        -Path $Paths.stable_setup `
        -MaximumSeconds $MaximumSeconds `
        -ExpectedSha256 $Candidate.sha256 `
        -AdditionalAllowedSetupPaths $AllowedSetupPaths
    $reactivateWait = Wait-ForInstalledState `
        -Paths $Paths `
        -Expected @{
            current = $CandidateVersion
            previous = $ExpectedCurrentVersion
            stable_version = $CandidateVersion
            stable_setup_sha256 = $Candidate.sha256
            stable_package_sha256 = $Candidate.package_sha256
            current_identity = $Candidate.expected_identity
        } `
        -MaximumSeconds $MaximumSeconds
    $final = $reactivateWait.state
    $finalInventory = Get-ImmutableVersionInventory -Paths $Paths
    if ($Continuation.IsPresent) {
        Assert-VersionInventoryEqual `
            -Actual $finalInventory `
            -Expected $BaselineInventory
    } else {
        Assert-VersionInventoryTransition `
            -Baseline $BaselineInventory `
            -Observed $finalInventory `
            -AddedVersion $CandidateVersion
    }
    Assert-IdentityEqual `
        -Actual $final.current `
        -Expected $InstalledCandidate.current `
        -Description 'reactivated candidate pointer'
    Assert-IdentityEqual `
        -Actual $final.previous `
        -Expected $ExpectedRollbackIdentity `
        -Description 'reactivated previous pointer'
    Assert-GateCondition (
        $final.installation.install_id -ceq $BaselineInstallId -and
        $final.integration.shortcut.sha256 -ceq
            $BaselineShortcutSha256) `
        'Reactivation changed immutable installation ownership or shortcut identity.'
    if (-not $Continuation.IsPresent) {
        $retainedInitialPrevious = Get-InstalledVersionRecord `
            -Paths $Paths `
            -Pointer $Baseline.previous
        Assert-GateCondition (
            $retainedInitialPrevious.source_commit -ceq
                $Baseline.previous_version.source_commit -and
            $retainedInitialPrevious.core_sha256 -ceq
                $Baseline.previous_version.core_sha256) `
            'The initial previous immutable version changed during the lifecycle.'
    }
    $finalSmoke = Invoke-InstalledCoreSmoke `
        -CorePath $final.current_version.core_path `
        -ExpectedVersion $CandidateVersion `
        -ExpectedSha256 $final.current_version.core_sha256 `
        -PrivateDataParent $Paths.data `
        -MaximumSeconds $MaximumSeconds `
        -RequireApplicationCatalog
    $step = [ordered]@{
        name = 'reactivate_candidate'
        status = 'passed'
        setup_exit_code = [int]$reactivateExecution.exit_code
        setup_duration_ms = [int64]$reactivateExecution.duration_ms
        settle_duration_ms = [int64]$reactivateWait.settle_duration_ms
        state = $final.summary
        core_smoke = $finalSmoke
    }
    return [pscustomobject][ordered]@{
        PSTypeName = 'Baxy.InPlaceUpgrade.ReactivationPhase'
        step = $step
        inventory = $finalInventory
    }
}

function New-InPlaceUpgradeRecoveryResult {
    return [ordered]@{
        attempted = $false
        status = 'not_required'
        final_candidate_attested = $false
        exception_type = $null
        cleanup_exception_type = $null
        observation_exception_type = $null
        current = $null
        previous = $null
        setup_exit_code = $null
        setup_duration_ms = $null
        settle_duration_ms = $null
        residual_setup_processes = $null
    }
}

function Invoke-InPlaceUpgradeRecovery {
    param(
        [Parameter(Mandatory = $true)]$Candidate,
        [Parameter(Mandatory = $true)]$Paths,
        [Parameter(Mandatory = $true)]$BaselineInventory,
        [Parameter(Mandatory = $true)]$BaselinePrivateData,
        [Parameter(Mandatory = $true)][DateTime]$MutationStartedUtc,
        [Parameter(Mandatory = $true)][string]$ExpectedCurrentVersion,
        [Parameter(Mandatory = $true)][string]$CandidateVersion,
        [switch]$Continuation,
        [Parameter(Mandatory = $true)][int]$MaximumSeconds
    )

    $recovery = New-InPlaceUpgradeRecoveryResult
    $recovery.attempted = $true
    $recovery.status = 'running'
    try {
        $recovered = Invoke-BestEffortCandidateReactivation `
            -Candidate $Candidate `
            -Paths $Paths `
            -ExpectedPreviousVersion $ExpectedCurrentVersion `
            -BaselineInventory $BaselineInventory `
            -BaselinePrivateData $BaselinePrivateData `
            -MutationStartedUtc $MutationStartedUtc `
            -CandidateAlreadyInBaseline:$Continuation `
            -MaximumSeconds $MaximumSeconds
        $recovery.status = 'passed'
        $recovery.final_candidate_attested = $true
        $recovery.current = [string]$recovered.state.summary.current
        $recovery.previous = [string]$recovered.state.summary.previous
        $recovery.setup_exit_code = [int]$recovered.setup_exit_code
        $recovery.setup_duration_ms = [int64]$recovered.setup_duration_ms
        $recovery.settle_duration_ms = [int64]$recovered.settle_duration_ms
        $recovery.residual_setup_processes = 0
    } catch {
        $recovery.status = 'failed'
        $recovery.exception_type = $_.Exception.GetType().FullName
        try {
            Stop-GateOwnedSetupProcesses `
                -NotBeforeUtc $MutationStartedUtc `
                -AllowedPaths (Get-LifecycleAllowedSetupPaths `
                    -Candidate $Candidate `
                    -Paths $Paths)
            $recovery.residual_setup_processes = 0
        } catch {
            $recovery.cleanup_exception_type =
                $_.Exception.GetType().FullName
            try {
                $recovery.residual_setup_processes =
                    @(Get-OwnedSetupProcesses).Count
            } catch {
                # Cleanup already failed. Preserve that stable failure type and
                # mark the residual count unknown so evidence publication can
                # still report the original lifecycle fault.
                $recovery.residual_setup_processes = $null
            }
        }
        try {
            $observedFinal = Get-InstalledState `
                -Paths $Paths `
                -ExpectedCurrent $CandidateVersion `
                -ExpectedPrevious $ExpectedCurrentVersion `
                -ExpectedStableVersion $CandidateVersion `
                -ExpectedStableSetupSha256 $Candidate.sha256 `
                -ExpectedStablePackageSha256 $Candidate.package_sha256 `
                -ExpectedCurrentIdentity $Candidate.expected_identity
            $recovery.final_candidate_attested = $true
            $recovery.current = [string]$observedFinal.summary.current
            $recovery.previous = [string]$observedFinal.summary.previous
        } catch {
            $recovery.observation_exception_type =
                $_.Exception.GetType().FullName
        }
    }
    return $recovery
}

function New-InPlaceUpgradeSuccessEvidence {
    param(
        [switch]$Continuation,
        [Parameter(Mandatory = $true)][string]$StartedUtc,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds,
        [Parameter(Mandatory = $true)]$Source,
        [Parameter(Mandatory = $true)]$Candidate,
        [Parameter(Mandatory = $true)]$EmbeddedVerification,
        [Parameter(Mandatory = $true)]$Baseline,
        [Parameter(Mandatory = $true)][object[]]$Steps,
        [Parameter(Mandatory = $true)][string]$ExpectedCurrentVersion,
        [Parameter(Mandatory = $true)][string]$ExpectedInitialPreviousVersion,
        [Parameter(Mandatory = $true)][string]$CandidateVersion,
        [Parameter(Mandatory = $true)][string]$BaselineInstallId,
        [Parameter(Mandatory = $true)]$BaselineInventory,
        [Parameter(Mandatory = $true)]$FinalInventory,
        [Parameter(Mandatory = $true)]$BaselinePrivateData,
        [Parameter(Mandatory = $true)]$FinalPrivateData,
        [AllowNull()]$PriorEvidence = $null
    )

    $resultSchema = if ($Continuation.IsPresent) {
        'baxy-in-place-upgrade-continuation-attestation-v1'
    } else {
        'baxy-in-place-upgrade-attestation-v1'
    }
    $resultOperation = if ($Continuation.IsPresent) {
        'recovered_install_rollback_reactivation'
    } else {
        'upgrade_rollback_reactivation'
    }
    $limitations = New-Object 'Collections.Generic.List[string]'
    foreach ($limitation in @(
        'same_host_current_user_profile',
        'authenticode_not_signed',
        'gui_not_launched',
        'isolated_core_protocol_smoke_only',
        'private_data_alternate_streams_not_inventoried'
    )) {
        $limitations.Add($limitation)
    }
    if ($Continuation.IsPresent) {
        $limitations.Add('continued_from_recovered_candidate')
    }
    $result = [ordered]@{
        schema = $resultSchema
        status = 'passed'
        operation = $resultOperation
        started_utc = $StartedUtc
        completed_utc = [DateTime]::UtcNow.ToString('o')
        timeout_seconds = $TimeoutSeconds
        source = [ordered]@{
            commit = $Source.head
            clean_before = $true
            clean_after = $true
        }
        versions = [ordered]@{
            initial_current = $ExpectedCurrentVersion
            initial_previous = $ExpectedInitialPreviousVersion
            candidate = $CandidateVersion
            final_current = $CandidateVersion
            final_previous = $ExpectedCurrentVersion
        }
        candidate = [ordered]@{
            setup_sha256 = $Candidate.sha256
            setup_bytes = $Candidate.bytes
            setup_manifest_sha256 = $Candidate.manifest_sha256
            package_sha256 = $Candidate.package_sha256
            package_bytes = $Candidate.package_bytes
            package_manifest_sha256 = $Candidate.package_manifest_sha256
            content_id = $Candidate.content_id
            authenticode = 'NotSigned'
            embedded_verification = $EmbeddedVerification
        }
        baseline = $Baseline.summary
        steps = $Steps
        preservation = [ordered]@{
            install_id_preserved = $true
            install_id_sha256 = Get-StringSha256 -Value $BaselineInstallId
            data_schema_preserved = $true
            data_schema = $script:DataSchema
            shortcut_identity_preserved = $true
            versions_deleted = 0
            initial_version_directories = [int]$BaselineInventory.names.Count
            final_version_directories = [int]$FinalInventory.names.Count
            preexisting_version_trees_unchanged = $true
            private_data = [ordered]@{
                snapshot_schema = [string]$BaselinePrivateData.schema
                content_and_metadata_read_for_integrity = $true
                relative_paths_or_content_published = $false
                baseline_tree_sha256 =
                    [string]$BaselinePrivateData.tree_sha256
                final_tree_sha256 =
                    [string]$FinalPrivateData.tree_sha256
                existed = [bool]$BaselinePrivateData.exists
                files = [int]$BaselinePrivateData.files
                directories = [int]$BaselinePrivateData.directories
                total_bytes = [int64]$BaselinePrivateData.total_bytes
                unchanged = $true
                deleted = $false
            }
            gui_launched = $false
            residual_owned_processes = 0
            residual_transaction_artifacts = 0
        }
        privacy = [ordered]@{
            local_paths_included = $false
            user_profile_included = $false
            install_id_included = $false
            exception_messages_included = $false
        }
        limitations = [string[]]$limitations.ToArray()
    }
    if ($Continuation.IsPresent) {
        $result['aggregate_status'] = 'passed_with_recovery_continuation'
        $result['continuation'] = [ordered]@{
            prior_failure_evidence_sha256 = $PriorEvidence.sha256
            prior_status = 'failed'
            prior_recovery_status = 'passed'
            start_current = $CandidateVersion
            start_previous = $ExpectedCurrentVersion
        }
        $result.candidate['source_commit'] = $Candidate.source_commit
    }
    return $result
}

function New-InPlaceUpgradeFailureEvidence {
    param(
        [switch]$Continuation,
        [Parameter(Mandatory = $true)][string]$StartedUtc,
        [Parameter(Mandatory = $true)][string]$FailedPhase,
        [Parameter(Mandatory = $true)]$Caught,
        [Parameter(Mandatory = $true)][string]$ExpectedCurrentVersion,
        [Parameter(Mandatory = $true)][string]$ExpectedInitialPreviousVersion,
        [Parameter(Mandatory = $true)][string]$CandidateVersion,
        [AllowNull()]$Candidate = $null,
        [Parameter(Mandatory = $true)]$Recovery,
        [AllowNull()]$PriorEvidence = $null,
        [AllowNull()][string]$ExpectedCandidateCommit = $null
    )

    $failure = [ordered]@{
        schema = if ($Continuation.IsPresent) {
            'baxy-in-place-upgrade-continuation-attestation-v1'
        } else {
            'baxy-in-place-upgrade-attestation-v1'
        }
        status = 'failed'
        operation = if ($Continuation.IsPresent) {
            'recovered_install_rollback_reactivation'
        } else {
            'upgrade_rollback_reactivation'
        }
        started_utc = $StartedUtc
        completed_utc = [DateTime]::UtcNow.ToString('o')
        phase = $FailedPhase
        failure_code = 'in_place_upgrade_gate_failed'
        exception_type = $Caught.Exception.GetType().FullName
        versions = [ordered]@{
            initial_current = $ExpectedCurrentVersion
            initial_previous = $ExpectedInitialPreviousVersion
            candidate = $CandidateVersion
        }
        candidate_setup_sha256 = if ($null -ne $Candidate) {
            $Candidate.sha256
        } else {
            $null
        }
        recovery = $Recovery
        privacy = [ordered]@{
            local_paths_included = $false
            exception_messages_included = $false
        }
    }
    if ($Continuation.IsPresent) {
        $failure['continuation'] = [ordered]@{
            prior_failure_evidence_sha256 = if ($null -ne $PriorEvidence) {
                $PriorEvidence.sha256
            } else {
                $null
            }
            candidate_source_commit = if ($null -ne $Candidate) {
                $Candidate.source_commit
            } else {
                $ExpectedCandidateCommit
            }
        }
    }
    return $failure
}

function Invoke-InPlaceUpgradeAttestation {
    Assert-GateCondition $ConfirmInPlaceUpgrade.IsPresent `
        'Refusing an in-place lifecycle without -ConfirmInPlaceUpgrade.'
    $continuation = $ContinueRecoveredCandidate.IsPresent
    if ($continuation) {
        Assert-GateCondition (
            (Test-LowerHex -Value $ExpectedCandidateCommit -Length 40) -and
            -not [string]::IsNullOrWhiteSpace($PriorFailureEvidencePath) -and
            (Test-LowerHex -Value $ExpectedPriorFailureEvidenceSha256)) `
            'Continuation requires exact candidate commit and prior evidence identities.'
    } else {
        Assert-GateCondition (
            [string]::IsNullOrWhiteSpace($ExpectedCandidateCommit) -and
            [string]::IsNullOrWhiteSpace($PriorFailureEvidencePath) -and
            [string]::IsNullOrWhiteSpace(
                $ExpectedPriorFailureEvidenceSha256)) `
            'Candidate commit and prior evidence identities are valid only with -ContinueRecoveredCandidate.'
    }
    $null = Get-SemVerParts -Version $ExpectedCurrentVersion
    $null = Get-SemVerParts -Version $ExpectedInitialPreviousVersion
    $null = Get-SemVerParts -Version $CandidateVersion
    Assert-GateCondition (
        (Compare-SemVerPrecedence `
            -Left $ExpectedCurrentVersion `
            -Right $ExpectedInitialPreviousVersion) -gt 0) `
        'The expected baseline current version must advance its initial previous version.'
    Assert-GateCondition (
        (Compare-SemVerPrecedence `
            -Left $CandidateVersion `
            -Right $ExpectedCurrentVersion) -gt 0) `
        'The candidate must advance the expected baseline version.'

    $evidenceFull = Assert-NewEvidencePath -Path $EvidencePath
    $startedUtc = [DateTime]::UtcNow.ToString('o')
    $phase = 'source_preflight'
    $source = $null
    $candidate = $null
    $priorEvidence = $null
    $paths = $null
    $baselineInventory = $null
    $baselinePrivateData = $null
    $mutationStarted = $false
    $mutationStartedUtc = $null
    $forbiddenPaths = New-Object 'Collections.Generic.List[string]'
    foreach ($path in @(
        [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile),
        [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData),
        [IO.Path]::GetTempPath(),
        $CandidateSetup,
        $EvidencePath,
        $PriorFailureEvidencePath
    )) {
        if (-not [string]::IsNullOrWhiteSpace($path)) {
            $forbiddenPaths.Add([IO.Path]::GetFullPath($path))
        }
    }

    try {
        $source = Get-RepositorySourceState
        $forbiddenPaths.Add($source.root)
        $phase = 'candidate_validation'
        $candidateCommit = if ($continuation) {
            $ExpectedCandidateCommit
        } else {
            $source.head
        }
        $candidate = Get-CandidateSetupArtifact `
            -Path $CandidateSetup `
            -ExpectedVersion $CandidateVersion `
            -ExpectedCommit $candidateCommit
        if ($continuation) {
            & git -C $source.root merge-base --is-ancestor `
                $candidate.source_commit $source.head
            Assert-GateCondition ($LASTEXITCODE -eq 0) `
                'The recovered candidate commit is not an ancestor of the clean gate source.'
        }
        $forbiddenPaths.Add($candidate.path)
        $forbiddenPaths.Add($candidate.root)
        $embeddedVerification = Invoke-EmbeddedCandidateVerification `
            -Candidate $candidate `
            -MaximumSeconds $TimeoutSeconds

        $phase = 'installed_preflight'
        $paths = Get-CanonicalProductPaths
        $forbiddenPaths.Add($paths.root)
        $forbiddenPaths.Add($paths.data)
        $forbiddenPaths.Add($paths.shortcut)
        $evidenceFull = Assert-EvidencePathOutsideProtectedRoots `
            -Path $evidenceFull `
            -ProtectedRoots @(
                $source.root,
                $candidate.root,
                $paths.root,
                $paths.data,
                $paths.start_menu_directory
            )
        if ($continuation) {
            $priorFull = [IO.Path]::GetFullPath($PriorFailureEvidencePath)
            Assert-GateCondition (
                -not [string]::Equals(
                    $priorFull,
                    $evidenceFull,
                    [StringComparison]::OrdinalIgnoreCase)) `
                'Prior and final evidence must be different files.'
            $null = Assert-EvidencePathOutsideProtectedRoots `
                -Path $priorFull `
                -ProtectedRoots @(
                    $source.root,
                    $candidate.root,
                    $paths.root,
                    $paths.data,
                    $paths.start_menu_directory
                )
            $priorEvidence = Read-RecoveredCandidateEvidence `
                -Path $priorFull `
                -Candidate $candidate `
                -ExpectedCurrent $ExpectedCurrentVersion `
                -ExpectedInitialPrevious $ExpectedInitialPreviousVersion `
                -ExpectedCandidate $CandidateVersion `
                -ExpectedSha256 $ExpectedPriorFailureEvidenceSha256
            $forbiddenPaths.Add($priorEvidence.path)
        }
        Assert-NoOwnedProductProcesses
        if ($continuation) {
            Assert-GateCondition (
                Test-Path -LiteralPath (
                    Join-Path $paths.versions $CandidateVersion) -PathType Container) `
                'The recovered candidate immutable version is missing.'
            $baseline = Get-InstalledState `
                -Paths $paths `
                -ExpectedCurrent $CandidateVersion `
                -ExpectedPrevious $ExpectedCurrentVersion `
                -ExpectedStableVersion $CandidateVersion `
                -ExpectedStableSetupSha256 $candidate.sha256 `
                -ExpectedStablePackageSha256 $candidate.package_sha256 `
                -ExpectedCurrentIdentity $candidate.expected_identity
        } else {
            Assert-GateCondition (
                -not (Test-Path -LiteralPath (
                    Join-Path $paths.versions $CandidateVersion))) `
                'The candidate immutable version already exists before this gate.'
            $baselineStableSha256 = Get-FileSha256 -Path $paths.stable_setup
            $baseline = Get-InstalledState `
                -Paths $paths `
                -ExpectedCurrent $ExpectedCurrentVersion `
                -ExpectedPrevious $ExpectedInitialPreviousVersion `
                -ExpectedStableVersion $ExpectedCurrentVersion `
                -ExpectedStableSetupSha256 $baselineStableSha256 `
                -ExpectedStablePackageSha256 (
                    (Read-InstallationPointer `
                     -Path $paths.current `
                     -ExpectedVersion $ExpectedCurrentVersion).package_sha256)
        }
        $baselineInventory = Get-ImmutableVersionInventory -Paths $paths
        Assert-GateCondition (
            $baselineInventory.names -ccontains $ExpectedInitialPreviousVersion) `
            'The original previous immutable version is not retained.'
        $baselinePrivateData = Get-PrivateDataInventory -Root $paths.data
        $baselineInstallId = [string]$baseline.installation.install_id
        $baselineShortcutSha256 = [string]$baseline.integration.shortcut.sha256
        $allowedSetupPaths = Get-LifecycleAllowedSetupPaths `
            -Candidate $candidate `
            -Paths $paths

        $steps = New-Object 'Collections.Generic.List[object]'

        if ($continuation) {
            $phase = 'validate_recovered_candidate'
            $candidatePhase = Invoke-RecoveredCandidateValidationPhase `
                -Paths $paths `
                -Baseline $baseline `
                -PriorEvidence $priorEvidence `
                -CandidateVersion $CandidateVersion `
                -MaximumSeconds $TimeoutSeconds
            $steps.Add($candidatePhase.step)
            $mutationStarted = $true
            $mutationStartedUtc = [DateTime]::UtcNow
        } else {
            $phase = 'install_candidate'
            $mutationStarted = $true
            $mutationStartedUtc = [DateTime]::UtcNow
            $candidatePhase = Invoke-CandidateInstallPhase `
                -Candidate $candidate `
                -Paths $paths `
                -Baseline $baseline `
                -BaselineInventory $baselineInventory `
                -BaselineInstallId $baselineInstallId `
                -BaselineShortcutSha256 $baselineShortcutSha256 `
                -AllowedSetupPaths $allowedSetupPaths `
                -CandidateVersion $CandidateVersion `
                -ExpectedCurrentVersion $ExpectedCurrentVersion `
                -MaximumSeconds $TimeoutSeconds
            $steps.Add($candidatePhase.step)
        }
        $installedCandidate = $candidatePhase.state

        $phase = 'rollback'
        $rollbackPhase = Invoke-CandidateRollbackPhase `
            -Candidate $candidate `
            -Paths $paths `
            -Baseline $baseline `
            -BaselineInventory $baselineInventory `
            -InstalledCandidate $installedCandidate `
            -BaselineInstallId $baselineInstallId `
            -BaselineShortcutSha256 $baselineShortcutSha256 `
            -AllowedSetupPaths $allowedSetupPaths `
            -CandidateVersion $CandidateVersion `
            -ExpectedCurrentVersion $ExpectedCurrentVersion `
            -Continuation:$continuation `
            -MaximumSeconds $TimeoutSeconds
        $steps.Add($rollbackPhase.step)
        $expectedRollbackIdentity =
            $rollbackPhase.expected_rollback_identity

        $phase = 'reactivate_candidate'
        $reactivationPhase = Invoke-CandidateReactivationPhase `
            -Candidate $candidate `
            -Paths $paths `
            -Baseline $baseline `
            -BaselineInventory $baselineInventory `
            -InstalledCandidate $installedCandidate `
            -ExpectedRollbackIdentity $expectedRollbackIdentity `
            -BaselineInstallId $baselineInstallId `
            -BaselineShortcutSha256 $baselineShortcutSha256 `
            -AllowedSetupPaths $allowedSetupPaths `
            -CandidateVersion $CandidateVersion `
            -ExpectedCurrentVersion $ExpectedCurrentVersion `
            -Continuation:$continuation `
            -MaximumSeconds $TimeoutSeconds
        $steps.Add($reactivationPhase.step)
        $finalInventory = $reactivationPhase.inventory

        $phase = 'private_data_preservation'
        $finalPrivateData = Get-PrivateDataInventory -Root $paths.data
        Assert-PrivateDataInventoryEqual `
            -Actual $finalPrivateData `
            -Expected $baselinePrivateData

        $phase = 'final_source_and_process_check'
        Assert-NoOwnedProductProcesses
        Assert-GateCondition (@(Get-PendingLifecycleArtifacts -Paths $paths).Count -eq 0) `
            'The final lifecycle retained pending artifacts.'
        $finalSource = Get-RepositorySourceState
        Assert-GateCondition ($finalSource.head -ceq $source.head) `
            'The source HEAD changed during the in-place lifecycle.'
        Assert-GateCondition ((Get-FileSha256 -Path $candidate.path) -ceq $candidate.sha256) `
            'The candidate delivery artifact changed during the lifecycle.'
        if ($continuation) {
            Assert-GateCondition (
                (Get-FileSha256 -Path $priorEvidence.path) -ceq
                    $priorEvidence.sha256) `
                'The prior failed lifecycle evidence changed during continuation.'
        }

        $result = New-InPlaceUpgradeSuccessEvidence `
            -Continuation:$continuation `
            -StartedUtc $startedUtc `
            -TimeoutSeconds $TimeoutSeconds `
            -Source $source `
            -Candidate $candidate `
            -EmbeddedVerification $embeddedVerification `
            -Baseline $baseline `
            -Steps $steps.ToArray() `
            -ExpectedCurrentVersion $ExpectedCurrentVersion `
            -ExpectedInitialPreviousVersion $ExpectedInitialPreviousVersion `
            -CandidateVersion $CandidateVersion `
            -BaselineInstallId $baselineInstallId `
            -BaselineInventory $baselineInventory `
            -FinalInventory $finalInventory `
            -BaselinePrivateData $baselinePrivateData `
            -FinalPrivateData $finalPrivateData `
            -PriorEvidence $priorEvidence
        $phase = 'publish_evidence'
        Write-AtomicEvidence `
            -Path $evidenceFull `
            -Value $result `
            -ForbiddenPaths $forbiddenPaths.ToArray()
        return $result
    } catch {
        $caught = $_
        $failedPhase = $phase
        $recovery = New-InPlaceUpgradeRecoveryResult
        if (
            $mutationStarted -and
            $null -ne $candidate -and
            $null -ne $paths -and
            $null -ne $baselineInventory -and
            $null -ne $baselinePrivateData
        ) {
            $recovery = Invoke-InPlaceUpgradeRecovery `
                -Candidate $candidate `
                -Paths $paths `
                -BaselineInventory $baselineInventory `
                -BaselinePrivateData $baselinePrivateData `
                -MutationStartedUtc $mutationStartedUtc `
                -ExpectedCurrentVersion $ExpectedCurrentVersion `
                -CandidateVersion $CandidateVersion `
                -Continuation:$continuation `
                -MaximumSeconds $TimeoutSeconds
        }
        if (-not (Test-Path -LiteralPath $evidenceFull)) {
            $failure = New-InPlaceUpgradeFailureEvidence `
                -Continuation:$continuation `
                -StartedUtc $startedUtc `
                -FailedPhase $failedPhase `
                -Caught $caught `
                -ExpectedCurrentVersion $ExpectedCurrentVersion `
                -ExpectedInitialPreviousVersion $ExpectedInitialPreviousVersion `
                -CandidateVersion $CandidateVersion `
                -Candidate $candidate `
                -Recovery $recovery `
                -PriorEvidence $priorEvidence `
                -ExpectedCandidateCommit $ExpectedCandidateCommit
            Write-AtomicEvidence `
                -Path $evidenceFull `
                -Value $failure `
                -ForbiddenPaths $forbiddenPaths.ToArray()
        }
        throw $caught
    }
}

if ($MyInvocation.InvocationName -cne '.') {
    $output = Invoke-InPlaceUpgradeAttestation
    $output | ConvertTo-Json -Depth 20 -Compress
}
