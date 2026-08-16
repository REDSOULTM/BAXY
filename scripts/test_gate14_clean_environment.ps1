param(
    [Parameter(Mandatory = $true)][string]$PredecessorSetup,
    [Parameter(Mandatory = $true)][string]$CandidateSetup,
    [string]$EvidencePath,
    [switch]$ConfirmDisposableProfile
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'path_safety.ps1')

function Assert-Condition {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )

    if (-not $Condition) { throw $Message }
}

function Wait-Condition {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Condition,
        [Parameter(Mandatory = $true)][string]$Failure,
        [int]$Seconds = 30
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        if (& $Condition) { return }
        Start-Sleep -Milliseconds 100
    } until ([DateTime]::UtcNow -ge $deadline)
    throw $Failure
}

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-SetupIdentity {
    param([Parameter(Mandatory = $true)][string]$Path)

    $full = [IO.Path]::GetFullPath($Path)
    Assert-Condition (Test-Path -LiteralPath $full -PathType Leaf) "Missing Setup: $full"
    Assert-Condition (Assert-ExistingPathChainHasNoReparsePoint -Path $full) `
        'A Setup input is not a regular path.'
    $directory = [IO.Path]::GetDirectoryName($full)
    $manifestPath = Join-Path $directory 'setup-manifest.json'
    $sumsPath = Join-Path $directory 'SHA256SUMS'
    Assert-Condition (Test-Path -LiteralPath $manifestPath -PathType Leaf) `
        'A Setup input has no adjacent setup-manifest.json.'
    Assert-Condition (Test-Path -LiteralPath $sumsPath -PathType Leaf) `
        'A Setup input has no adjacent SHA256SUMS.'

    $manifest = Read-JsonFile $manifestPath
    $sha256 = (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()
    $manifestSha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $sumLines = @(Get-Content -LiteralPath $sumsPath -Encoding UTF8)
    Assert-Condition ($manifest.schema -ceq 'baxy-setup-build-v2') `
        'The Setup manifest schema is not baxy-setup-build-v2.'
    Assert-Condition (
        $manifest.version -is [string] -and
        $manifest.version -cmatch '^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$') `
        'The Setup manifest has an invalid semantic version.'
    Assert-Condition ($manifest.file.path -ceq 'Baxy.Setup.exe') `
        'The Setup manifest identifies an unexpected file.'
    Assert-Condition ($manifest.file.sha256 -ceq $sha256) `
        'The Setup executable does not match its manifest.'
    Assert-Condition ($sumLines -ccontains "$sha256  Baxy.Setup.exe") `
        'SHA256SUMS does not attest the Setup executable.'
    Assert-Condition ($sumLines -ccontains "$manifestSha256  setup-manifest.json") `
        'SHA256SUMS does not attest setup-manifest.json.'

    return [pscustomobject]@{
        path = $full
        version = $manifest.version
        sha256 = $sha256
        bytes = [long](Get-Item -LiteralPath $full).Length
        package_sha256 = $manifest.embedded_package.sha256
        source_commit = $manifest.source.commit
        authenticode = $manifest.authenticode
    }
}

function Invoke-Setup {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string[]]$Arguments = @()
    )

    $start = @{
        FilePath = $Path
        PassThru = $true
        Wait = $true
        WindowStyle = 'Hidden'
    }
    if ($Arguments.Count -gt 0) { $start['ArgumentList'] = $Arguments }
    $process = Start-Process @start
    try {
        Assert-Condition ($process.ExitCode -eq 0) `
            "Setup exited with code $($process.ExitCode): $Path $($Arguments -join ' ')"
    } finally {
        $process.Dispose()
    }
}

function Get-RegistryDisplayVersion {
    $view = [Microsoft.Win32.RegistryView]::Registry64
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::CurrentUser,
        $view)
    try {
        $key = $base.OpenSubKey('Software\Microsoft\Windows\CurrentVersion\Uninstall\BAXY')
        if ($null -eq $key) { return $null }
        try { return [string]$key.GetValue('DisplayVersion', $null) }
        finally { $key.Dispose() }
    } finally {
        $base.Dispose()
    }
}

function Test-NoPendingLifecycleArtifacts {
    $names = @(
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
    foreach ($name in $names) {
        if (Test-Path -LiteralPath (Join-Path $script:InstallationRoot $name)) {
            return $false
        }
    }
    return $true
}

function Assert-InstalledState {
    param(
        [Parameter(Mandatory = $true)][string]$Current,
        [AllowNull()][string]$Previous,
        [Parameter(Mandatory = $true)][string]$StableVersion
    )

    Wait-Condition {
        (Test-Path -LiteralPath $script:CurrentPointer -PathType Leaf) -and
        (Test-Path -LiteralPath $script:IntegrationStatePath -PathType Leaf) -and
        (Test-Path -LiteralPath $script:StableSetupHost -PathType Leaf) -and
        (Test-NoPendingLifecycleArtifacts) -and
        @(Get-Process -Name 'Baxy.Setup' -ErrorAction SilentlyContinue).Count -eq 0
    } 'The lifecycle did not reach a stable committed state.'

    $currentState = Read-JsonFile $script:CurrentPointer
    $integration = Read-JsonFile $script:IntegrationStatePath
    Assert-Condition ($currentState.version -ceq $Current) 'current has the wrong version.'
    Assert-Condition ($integration.active.version -ceq $Current) `
        'windows integration has the wrong active version.'
    Assert-Condition ($integration.stable_setup.version -ceq $StableVersion) `
        'windows integration has the wrong stable Setup version.'
    Assert-Condition ((Get-RegistryDisplayVersion) -ceq $Current) `
        'The uninstall registry has the wrong active version.'
    Assert-Condition (Test-Path -LiteralPath $script:StartMenuShortcut -PathType Leaf) `
        'The exact Start Menu shortcut is missing.'

    $previousPath = Join-Path $script:InstallationRoot 'current.previous'
    if ($null -eq $Previous) {
        Assert-Condition (-not (Test-Path -LiteralPath $previousPath)) `
            'A first install unexpectedly has current.previous.'
    } else {
        Assert-Condition (Test-Path -LiteralPath $previousPath -PathType Leaf) `
            'current.previous is missing.'
        $previousState = Read-JsonFile $previousPath
        Assert-Condition ($previousState.version -ceq $Previous) `
            'current.previous has the wrong version.'
    }
}

function Get-UninstallTombstones {
    if (-not (Test-Path -LiteralPath $script:InstallParent -PathType Container)) { return @() }
    return @(Get-ChildItem -LiteralPath $script:InstallParent -Force |
        Where-Object { $_.Name -clike '.BAXY-uninstall-*' })
}

function Test-NoBaxyProcesses {
    return @(Get-Process -Name 'Baxy', 'baxy-core', 'Baxy.Setup' -ErrorAction SilentlyContinue).Count -eq 0
}

function Assert-Uninstalled {
    param([Parameter(Mandatory = $true)][bool]$KeepData)

    Wait-Condition {
        -not (Test-Path -LiteralPath $script:InstallationRoot) -and
        -not (Test-Path -LiteralPath $script:StartMenuDirectory) -and
        $null -eq (Get-RegistryDisplayVersion) -and
        (Get-UninstallTombstones).Count -eq 0 -and
        (Test-NoBaxyProcesses)
    } 'Uninstall did not remove its exact installation and integration paths.' 45

    if ($KeepData) {
        Assert-Condition (Test-Path -LiteralPath $script:DataRoot -PathType Container) `
            'keep-data removed the BAXY data root.'
    } else {
        Assert-Condition (-not (Test-Path -LiteralPath $script:DataRoot)) `
            'purge-data left the BAXY data root.'
    }
}

function Invoke-FirstInstalledLaunch {
    Assert-Condition (Test-NoBaxyProcesses) 'The launch preflight found a BAXY process.'
    Invoke-Setup -Path $script:StableSetupHost -Arguments @('--launch')

    $app = $null
    try {
        Wait-Condition {
            $running = @(Get-Process -Name 'Baxy' -ErrorAction SilentlyContinue)
            if ($running.Count -ne 1) { return $false }
            $script:LaunchedApp = $running[0]
            $script:LaunchedApp.Refresh()
            return $script:LaunchedApp.MainWindowHandle -ne [IntPtr]::Zero
        } 'The first installed BAXY launch did not expose one visible app process.' 20
        $app = $script:LaunchedApp
        $app.Refresh()
        $path = [IO.Path]::GetFullPath($app.MainModule.FileName)
        Assert-StrictDescendantPath -Parent $script:InstallationRoot -Child $path
        Assert-Condition ($app.CloseMainWindow()) `
            'The gate-owned BAXY window did not accept a normal close.'
        Assert-Condition ($app.WaitForExit(15000)) `
            'The gate-owned BAXY app did not exit after its normal close.'
        Wait-Condition { Test-NoBaxyProcesses } `
            'The first launch left a BAXY/core process.' 15
        Assert-Condition (Test-Path -LiteralPath $script:DataRoot -PathType Container) `
            'The first installed launch did not initialize the data root.'
        return [ordered]@{
            process_id = $app.Id
            executable = $path
            visible_window = $true
            normal_close = $true
            residual_processes = 0
        }
    } finally {
        if ($null -ne $app) { $app.Dispose() }
    }
}

function Publish-Evidence {
    param([Parameter(Mandatory = $true)]$Value)

    $json = $Value | ConvertTo-Json -Depth 10
    $next = $script:EvidencePath + '.next'
    [IO.File]::WriteAllText($next, $json + [Environment]::NewLine, $script:Utf8NoBom)
    Move-Item -LiteralPath $next -Destination $script:EvidencePath -Force
}

if (-not $ConfirmDisposableProfile) {
    throw 'Refusing destructive Gate 14. Re-run once in a disposable clean profile with -ConfirmDisposableProfile.'
}

$RepositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$ArtifactRoot = [IO.Path]::GetFullPath((Join-Path $RepositoryRoot 'artifacts\setup'))
$Utf8NoBom = New-Object Text.UTF8Encoding($false)
if ([string]::IsNullOrWhiteSpace($EvidencePath)) {
    $EvidencePath = Join-Path $ArtifactRoot 'gate14_clean_environment_gate.json'
}
$EvidencePath = [IO.Path]::GetFullPath($EvidencePath)
Assert-StrictDescendantPath -Parent $ArtifactRoot -Child $EvidencePath
Assert-Condition ([IO.Path]::GetExtension($EvidencePath) -ceq '.json') `
    'Evidence must be a JSON file under artifacts\setup.'

$localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
$programs = [Environment]::GetFolderPath([Environment+SpecialFolder]::Programs)
$InstallationRoot = [IO.Path]::GetFullPath((Join-Path $localAppData 'Programs\BAXY'))
$InstallParent = [IO.Path]::GetDirectoryName($InstallationRoot)
$StableSetupHost = Join-Path $InstallationRoot 'Baxy.Setup.exe'
$CurrentPointer = Join-Path $InstallationRoot 'current'
$IntegrationStatePath = Join-Path $InstallationRoot 'windows-integration.v1.json'
$DataRoot = [IO.Path]::GetFullPath((Join-Path $localAppData 'BAXY'))
$StartMenuDirectory = [IO.Path]::GetFullPath((Join-Path $programs 'BAXY'))
$StartMenuShortcut = Join-Path $StartMenuDirectory 'BAXY.lnk'

$predecessor = Get-SetupIdentity -Path $PredecessorSetup
$candidate = Get-SetupIdentity -Path $CandidateSetup
$predecessorVersion = [string]$predecessor.version
$candidateVersion = [string]$candidate.version
Assert-Condition ($predecessor.sha256 -cne $candidate.sha256) `
    'Predecessor and candidate Setup executables must be distinct.'
Assert-Condition ($predecessorVersion -cne $candidateVersion) `
    'Predecessor and candidate Setup versions must be distinct.'
Assert-Condition (Test-NoBaxyProcesses) 'The clean-profile preflight found a BAXY process.'
Assert-Condition (-not (Test-Path -LiteralPath $InstallationRoot)) `
    'The clean-profile preflight found an installation root.'
Assert-Condition (-not (Test-Path -LiteralPath $DataRoot)) `
    'The clean-profile preflight found a BAXY data root.'
Assert-Condition (-not (Test-Path -LiteralPath $StartMenuDirectory)) `
    'The clean-profile preflight found BAXY Start Menu integration.'
Assert-Condition ($null -eq (Get-RegistryDisplayVersion)) `
    'The clean-profile preflight found the BAXY uninstall registry key.'
Assert-Condition ((Get-UninstallTombstones).Count -eq 0) `
    'The clean-profile preflight found an uninstall tombstone.'

$steps = New-Object 'System.Collections.Generic.List[object]'
$evidence = [ordered]@{
    schema = 'baxy-gate14-clean-environment-v1'
    status = 'running'
    observed_utc = [DateTime]::UtcNow.ToString('o')
    profile_preflight = 'pristine'
    predecessor = $predecessor
    candidate = $candidate
    steps = $steps
}

try {
    Invoke-Setup -Path $predecessor.path
    Assert-InstalledState -Current $predecessorVersion -Previous $null `
        -StableVersion $predecessorVersion
    $steps.Add([ordered]@{ name = 'install_1.0.0'; status = 'passed' })

    $launch = Invoke-FirstInstalledLaunch
    $steps.Add([ordered]@{ name = 'first_installed_launch'; status = 'passed'; evidence = $launch })

    $canaryPath = Join-Path $DataRoot 'gate14-clean-canary.txt'
    $canaryText = 'BAXY-GATE14-' + [Guid]::NewGuid().ToString('N')
    [IO.File]::WriteAllText($canaryPath, $canaryText, $Utf8NoBom)
    $canarySha256 = (Get-FileHash -LiteralPath $canaryPath -Algorithm SHA256).Hash.ToLowerInvariant()

    Invoke-Setup -Path $candidate.path
    Assert-InstalledState -Current $candidateVersion -Previous $predecessorVersion `
        -StableVersion $candidateVersion
    $steps.Add([ordered]@{ name = 'update_1.0.1'; status = 'passed' })

    Invoke-Setup -Path $StableSetupHost -Arguments @('--rollback')
    Assert-InstalledState -Current $predecessorVersion -Previous $candidateVersion `
        -StableVersion $candidateVersion
    $steps.Add([ordered]@{ name = 'rollback_1.0.0'; status = 'passed' })

    Invoke-Setup -Path $StableSetupHost -Arguments @('--uninstall', '--keep-data', '--quiet')
    Assert-Uninstalled -KeepData $true
    Assert-Condition ((Get-FileHash -LiteralPath $canaryPath -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $canarySha256) `
        'keep-data changed the gate canary.'
    $steps.Add([ordered]@{ name = 'uninstall_keep_data'; status = 'passed'; canary_sha256 = $canarySha256 })

    Invoke-Setup -Path $candidate.path
    Assert-InstalledState -Current $candidateVersion -Previous $null `
        -StableVersion $candidateVersion
    Assert-Condition ((Get-FileHash -LiteralPath $canaryPath -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $canarySha256) `
        'Reinstall changed the preserved gate canary.'
    $steps.Add([ordered]@{ name = 'reinstall_1.0.1'; status = 'passed' })

    Invoke-Setup -Path $StableSetupHost -Arguments @(
        '--uninstall', '--purge-data', '--confirm-purge-data', '--quiet')
    Assert-Uninstalled -KeepData $false
    $steps.Add([ordered]@{ name = 'uninstall_purge_data'; status = 'passed' })

    $evidence.status = 'passed'
    $evidence.completed_utc = [DateTime]::UtcNow.ToString('o')
    $evidence.final = [ordered]@{
        installation_root_absent = -not (Test-Path -LiteralPath $InstallationRoot)
        data_root_absent = -not (Test-Path -LiteralPath $DataRoot)
        shortcut_absent = -not (Test-Path -LiteralPath $StartMenuDirectory)
        registry_absent = $null -eq (Get-RegistryDisplayVersion)
        tombstones = (Get-UninstallTombstones).Count
        baxy_processes = 0
    }
    Publish-Evidence $evidence
} catch {
    $evidence.status = 'failed'
    $evidence.failed_utc = [DateTime]::UtcNow.ToString('o')
    $evidence.error = $_.Exception.Message
    Publish-Evidence $evidence
    throw
}
