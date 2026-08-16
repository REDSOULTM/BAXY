function Get-BaxyRequiredBuildLayoutProperty {
    param(
        [Parameter(Mandatory = $true)][Xml.XmlDocument]$Document,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $nodes = @($Document.SelectNodes("/Project/PropertyGroup/$Name"))
    if ($nodes.Count -ne 1) {
        throw "Directory.Build.props must define $Name exactly once."
    }
    $value = [string]$nodes[0].InnerText
    $value = $value.Trim()
    $baseName = @($value.Split('.'))[0]
    $reservedName = $baseName -match (
        '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$')
    if ($value -cnotmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$' -or
        $value.EndsWith('.', [StringComparison]::Ordinal) -or
        $reservedName) {
        throw "Directory.Build.props contains an unsafe $Name value."
    }
    return $value
}

function Read-BaxyBuildLayoutDocument {
    param([Parameter(Mandatory = $true)][string]$Path)

    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($item.PSIsContainer -or $item.Length -le 0 -or
        $item.Length -gt (1024 * 1024)) {
        throw 'Directory.Build.props has an invalid or excessive size.'
    }
    $settings = New-Object Xml.XmlReaderSettings
    $settings.DtdProcessing = [Xml.DtdProcessing]::Prohibit
    $settings.XmlResolver = $null
    $reader = [Xml.XmlReader]::Create($Path, $settings)
    try {
        $document = New-Object Xml.XmlDocument
        $document.XmlResolver = $null
        $document.Load($reader)
        return $document
    } finally {
        $reader.Dispose()
    }
}

function Get-BaxyBuildLayout {
    param([Parameter(Mandatory = $true)][string]$RepositoryRoot)

    $repository = [IO.Path]::GetFullPath($RepositoryRoot)
    $props = Join-Path $repository 'Directory.Build.props'
    $document = Read-BaxyBuildLayoutDocument -Path $props
    if ($document.DocumentElement.Name -cne 'Project') {
        throw 'Directory.Build.props must have a Project root.'
    }

    $defaultTargetFramework = Get-BaxyRequiredBuildLayoutProperty `
        -Document $document `
        -Name 'BaxyDefaultTargetFramework'
    $targetFramework = Get-BaxyRequiredBuildLayoutProperty `
        -Document $document `
        -Name 'BaxyWindowsTargetFramework'
    $runtimeIdentifier = Get-BaxyRequiredBuildLayoutProperty `
        -Document $document `
        -Name 'BaxyRuntimeIdentifier'
    $configuration = Get-BaxyRequiredBuildLayoutProperty `
        -Document $document `
        -Name 'BaxyDevelopmentConfiguration'
    $appOutput = Join-Path $repository (
        "src\Baxy.App\bin\$configuration\$targetFramework")
    $coreOutput = Join-Path $repository (
        "src\Baxy.Core\bin\$configuration\$targetFramework")

    return [pscustomobject][ordered]@{
        DefaultTargetFramework = $defaultTargetFramework
        WindowsTargetFramework = $targetFramework
        RuntimeIdentifier = $runtimeIdentifier
        DevelopmentConfiguration = $configuration
        AppExecutable = [IO.Path]::GetFullPath((Join-Path $appOutput 'Baxy.exe'))
        CoreExecutable = [IO.Path]::GetFullPath(
            (Join-Path $coreOutput 'baxy-core.exe'))
        CorePublishExecutable = [IO.Path]::GetFullPath(
            (Join-Path $coreOutput (
                "$runtimeIdentifier\publish\baxy-core.exe")))
    }
}
