[CmdletBinding()]
param(
    [string]$Python,
    [ValidateSet('Runtime', 'Test')]
    [string]$Profile = 'Runtime',
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
. (Join-Path $PSScriptRoot 'path_safety.ps1')
. (Join-Path $PSScriptRoot 'python_runtime_common.ps1')
$profileName = $Profile.ToLowerInvariant()
$requirements = Join-Path $repo "requirements-$profileName-win-x64.in"
$constraints = Join-Path $repo "constraints-$profileName-win-x64.txt"
$destination = Join-Path $repo "pylock.$profileName-win-x64.toml"
$verifier = Join-Path $repo 'scripts\verify_python_runtime_lock.py'

$pythonFull = Resolve-BaxyRuntimePython `
    -Candidate $Python `
    -ManifestPath '' `
    -FailurePrefix 'python_dependency_lock_failed'
foreach ($requiredFile in @($requirements, $constraints, $verifier)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw 'python_dependency_lock_failed: source_missing'
    }
}

Assert-BaxyPythonLockToolchain `
    -Python $pythonFull `
    -WorkingDirectory $repo `
    -FailurePrefix 'python_dependency_lock_failed'

$temporaryRoot = [IO.Path]::GetFullPath(
    (Join-Path $repo ('.runtime-lock-' + [Guid]::NewGuid().ToString('N'))))
$expectedPrefix = $repo.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
if (-not $temporaryRoot.StartsWith(
        $expectedPrefix,
        [StringComparison]::OrdinalIgnoreCase) -or
    -not [IO.Path]::GetFileName($temporaryRoot).StartsWith(
        '.runtime-lock-',
        [StringComparison]::Ordinal)) {
    throw 'python_dependency_lock_failed: unsafe_temporary_root'
}

$generated = Join-Path $temporaryRoot "pylock.$profileName-win-x64.toml"
try {
    $null = New-Item -ItemType Directory -Path $temporaryRoot
    Push-Location -LiteralPath $repo
    try {
        try {
            $ErrorActionPreference = 'Continue'
            & $pythonFull -X utf8 -m pip lock `
                --disable-pip-version-check `
                --only-binary=:all: `
                --find-links (Join-Path $repo 'runtime_wheels') `
                --requirement $requirements `
                --constraint $constraints `
                --output $generated
            $lockExitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = 'Stop'
        }
        if ($lockExitCode -ne 0) {
            throw 'python_dependency_lock_failed: resolver'
        }
    } finally {
        Pop-Location
    }

    $content = [IO.File]::ReadAllText($generated).Replace("`r`n", "`n")
    # pip currently emits absolute file URLs for --find-links. Keep only wheels
    # from the owned bundle directory and express them portably under PEP 751.
    $wheelRoot = [IO.Path]::GetFullPath((Join-Path $repo 'runtime_wheels'))
    foreach ($match in [regex]::Matches($content, '(?m)^url = "(file:[^"]+)"$')) {
        $wheelUri = [Uri]$match.Groups[1].Value
        $wheelPath = [IO.Path]::GetFullPath($wheelUri.LocalPath)
        if (-not $wheelUri.IsFile -or
            -not [IO.Path]::GetDirectoryName($wheelPath).Equals(
                $wheelRoot, [StringComparison]::OrdinalIgnoreCase) -or
            [IO.Path]::GetExtension($wheelPath) -cne '.whl') {
            throw 'python_dependency_lock_failed: local_wheel_outside_bundle'
        }
        $content = $content.Replace(
            $match.Value,
            ('path = "runtime_wheels/' + [IO.Path]::GetFileName($wheelPath) + '"'))
    }
    $header = "lock-version = `"1.0`"`ncreated-by = `"pip`"`n"
    if (-not $content.StartsWith($header, [StringComparison]::Ordinal)) {
        throw 'python_dependency_lock_failed: unexpected_header'
    }
    $platformHeader = @(
        'lock-version = "1.0"'
        "environments = [`"implementation_name == 'cpython' and sys_platform == 'win32' and platform_machine == 'AMD64'`"]"
        'requires-python = "==3.12.*"'
        'created-by = "pip"'
        ''
    ) -join "`n"
    $content = $platformHeader + $content.Substring($header.Length)
    [IO.File]::WriteAllText(
        $generated,
        $content,
        [Text.UTF8Encoding]::new($false))

    $null = Assert-BaxyRuntimeLock `
        -Python $pythonFull `
        -Repository $repo `
        -Profile $Profile `
        -FailurePrefix 'python_dependency_lock_failed' `
        -LockPath $generated `
        -ConstraintsPath $constraints `
        -StructureOnly

    if ($Check.IsPresent) {
        $lockMatches = (Test-Path -LiteralPath $destination -PathType Leaf) -and
            ((Get-FileHash -Algorithm SHA256 -LiteralPath $generated).Hash -ceq
                (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash)
        if (-not $lockMatches) {
            throw 'python_dependency_lock_failed: committed_lock_is_stale'
        }
        Write-Output "python_dependency_lock_current: profile=$Profile"
    } else {
        $staged = Join-Path $repo (
            ".pylock-$profileName-" + [Guid]::NewGuid().ToString('N') + '.tmp')
        try {
            [IO.File]::WriteAllBytes(
                $staged,
                [IO.File]::ReadAllBytes($generated))
            Move-Item -LiteralPath $staged -Destination $destination -Force
        } finally {
            if (Test-Path -LiteralPath $staged -PathType Leaf) {
                Remove-Item -LiteralPath $staged -Force
            }
        }
        Write-Output "python_dependency_lock_written: profile=$Profile"
    }
} finally {
    if (Test-Path -LiteralPath $temporaryRoot -PathType Container) {
        Remove-TreeFailClosed `
            -AllowedRoot $repo `
            -Target $temporaryRoot
    }
}
