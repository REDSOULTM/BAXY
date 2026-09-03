Set-StrictMode -Version Latest

$script:BaxyAssetDescriptorSchema = 'baxy-assets-v1'
$script:BaxyAssetOverrideMaximumBytes = 64KB

function Read-BaxyAssetJsonObject {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$FailureCode
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$FailureCode`: missing: $Path"
    }
    $info = Get-Item -LiteralPath $Path -Force
    if ($info.Length -le 0 -or $info.Length -gt $script:BaxyAssetOverrideMaximumBytes) {
        throw "$FailureCode`: size_invalid: $Path"
    }
    try {
        $value = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 |
            ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "$FailureCode`: json_invalid: $Path"
    }
    if ($null -eq $value -or $value -is [Array]) {
        throw "$FailureCode`: object_required: $Path"
    }
    return $value
}

function Expand-BaxyAssetPath {
    param(
        [Parameter(Mandatory = $true)][string]$Template,
        [Parameter(Mandatory = $true)][string]$RepositoryRoot
    )

    $values = @{
        REPOSITORY_ROOT = $RepositoryRoot
        LOCALAPPDATA = [Environment]::GetFolderPath(
            [Environment+SpecialFolder]::LocalApplicationData)
        USERPROFILE = [Environment]::GetFolderPath(
            [Environment+SpecialFolder]::UserProfile)
        BAXY_ASSETS_ROOT = [Environment]::GetEnvironmentVariable(
            'BAXY_ASSETS_ROOT',
            [EnvironmentVariableTarget]::Process)
    }
    $script:__baxyAssetTokenMissing = $false
    $expanded = [regex]::Replace(
        $Template,
        '\$\{([A-Z_]+)\}',
        {
            param($match)
            $name = $match.Groups[1].Value
            if (-not $values.ContainsKey($name) -or
                [string]::IsNullOrWhiteSpace([string]$values[$name])) {
                $script:__baxyAssetTokenMissing = $true
                return ''
            }
            return [string]$values[$name]
        })
    $unresolved = $script:__baxyAssetTokenMissing -eq $true
    $script:__baxyAssetTokenMissing = $false
    if ($unresolved -or $expanded -match '\$\{') {
        return $null
    }
    try {
        return [IO.Path]::GetFullPath($expanded)
    } catch {
        return $null
    }
}

function Get-BaxyAssetDescriptor {
    param(
        [string]$DescriptorPath,
        [string]$RepositoryRoot
    )

    if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
        $RepositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
    } else {
        $RepositoryRoot = [IO.Path]::GetFullPath($RepositoryRoot)
    }
    if ([string]::IsNullOrWhiteSpace($DescriptorPath)) {
        $DescriptorPath = Join-Path $RepositoryRoot 'assets.manifest.json'
    }
    $DescriptorPath = [IO.Path]::GetFullPath($DescriptorPath)
    $descriptor = Read-BaxyAssetJsonObject `
        -Path $DescriptorPath `
        -FailureCode 'asset_descriptor_invalid'
    if ([string]$descriptor.schema -cne $script:BaxyAssetDescriptorSchema -or
        [int]$descriptor.version -ne 1 -or
        $null -eq $descriptor.assets -or
        $null -eq $descriptor.local_override) {
        throw 'asset_descriptor_invalid: schema'
    }

    $overridePath = [Environment]::GetEnvironmentVariable(
        [string]$descriptor.local_override.environment,
        [EnvironmentVariableTarget]::Process)
    if ([string]::IsNullOrWhiteSpace($overridePath)) {
        $overridePath = Expand-BaxyAssetPath `
            -Template ([string]$descriptor.local_override.default) `
            -RepositoryRoot $RepositoryRoot
    }
    $overrideAssets = $null
    if (-not [string]::IsNullOrWhiteSpace($overridePath) -and
        (Test-Path -LiteralPath $overridePath -PathType Leaf)) {
        $override = Read-BaxyAssetJsonObject `
            -Path $overridePath `
            -FailureCode 'asset_override_invalid'
        $properties = @($override.PSObject.Properties.Name)
        if ($properties.Count -ne 2 -or
            $properties -notcontains 'schema' -or
            $properties -notcontains 'assets' -or
            [string]$override.schema -cne [string]$descriptor.local_override.schema) {
            throw 'asset_override_invalid: schema'
        }
        $knownAssets = @($descriptor.assets.PSObject.Properties.Name)
        $unknownAssets = @($override.assets.PSObject.Properties.Name | Where-Object {
            $knownAssets -cnotcontains $_
        })
        if ($unknownAssets.Count -ne 0) {
            throw ('asset_override_invalid: unknown_assets: ' +
                ($unknownAssets -join ','))
        }
        $overrideAssets = $override.assets
    }

    return [pscustomobject]@{
        Path = $DescriptorPath
        RepositoryRoot = $RepositoryRoot
        Value = $descriptor
        OverrideAssets = $overrideAssets
    }
}

function Resolve-BaxyAsset {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$ExplicitPath,
        [string]$DescriptorPath,
        [string]$RepositoryRoot
    )

    $source = Get-BaxyAssetDescriptor `
        -DescriptorPath $DescriptorPath `
        -RepositoryRoot $RepositoryRoot
    $property = $source.Value.assets.PSObject.Properties[$Name]
    if ($null -eq $property) {
        throw "asset_unknown: $Name"
    }
    $definition = $property.Value
    $kind = [string]$definition.kind
    if ($kind -cnotin @('file', 'directory')) {
        throw "asset_definition_invalid: $Name"
    }

    $raw = [Collections.Generic.List[string]]::new()
    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        $raw.Add($ExplicitPath)
    }
    $environmentValue = [Environment]::GetEnvironmentVariable(
        [string]$definition.environment,
        [EnvironmentVariableTarget]::Process)
    if (-not [string]::IsNullOrWhiteSpace($environmentValue)) {
        $raw.Add($environmentValue)
    }
    if ($null -ne $source.OverrideAssets) {
        $overrideProperty = $source.OverrideAssets.PSObject.Properties[$Name]
        if ($null -ne $overrideProperty) {
            foreach ($item in @($overrideProperty.Value)) {
                if (-not [string]::IsNullOrWhiteSpace([string]$item)) {
                    $raw.Add([string]$item)
                }
            }
        }
    }
    foreach ($item in @($definition.candidates)) {
        $raw.Add([string]$item)
    }

    $candidates = [Collections.Generic.List[string]]::new()
    $seen = [Collections.Generic.HashSet[string]]::new(
        [StringComparer]::OrdinalIgnoreCase)
    foreach ($item in $raw) {
        $candidate = Expand-BaxyAssetPath `
            -Template $item `
            -RepositoryRoot $source.RepositoryRoot
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and $seen.Add($candidate)) {
            $candidates.Add($candidate)
        }
    }

    $selected = $null
    foreach ($candidate in $candidates) {
        $valid = if ($kind -ceq 'file') {
            Test-Path -LiteralPath $candidate -PathType Leaf
        } else {
            Test-Path -LiteralPath $candidate -PathType Container
        }
        if ($valid -and $kind -ceq 'directory') {
            $requiredProperty = $definition.PSObject.Properties['required_files']
            $requiredFiles = @()
            if ($null -ne $requiredProperty -and $null -ne $requiredProperty.Value) {
                $requiredFiles = @($requiredProperty.Value)
            }
            foreach ($requiredFile in $requiredFiles) {
                if (-not (Test-Path -LiteralPath (Join-Path $candidate $requiredFile) -PathType Leaf)) {
                    $valid = $false
                    break
                }
            }
        }
        if ($valid) {
            $selected = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $candidate).Path)
            break
        }
    }

    return [pscustomobject]@{
        Name = $Name
        Found = -not [string]::IsNullOrWhiteSpace($selected)
        Path = $selected
        Candidates = @($candidates)
        Required = [bool]$definition.required
        Repair = [string]$definition.repair
        Descriptor = $source.Path
    }
}
