Set-StrictMode -Version Latest

function Invoke-BaxyPythonForOutput {
    param(
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    Push-Location -LiteralPath $WorkingDirectory
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5 wraps redirected native stderr in ErrorRecord.
        # Capture it explicitly so callers always receive a stable result.
        $ErrorActionPreference = 'Continue'
        $output = @(& $Python @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Pop-Location
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Text = (@($output | ForEach-Object { [string]$_ }) -join "`n").Trim()
    }
}

function Resolve-BaxyRuntimePython {
    param(
        [AllowEmptyString()][string]$Candidate,
        [AllowEmptyString()][string]$ManifestPath,
        [Parameter(Mandatory = $true)][string]$FailurePrefix
    )

    if ([string]::IsNullOrWhiteSpace($Candidate)) {
        if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
            $localData = [Environment]::GetFolderPath(
                [Environment+SpecialFolder]::LocalApplicationData)
            if ([string]::IsNullOrWhiteSpace($localData)) {
                throw "$FailurePrefix`: local_app_data_missing"
            }
            $ManifestPath = Join-Path $localData (
                'BAXYRuntime\mind-runtime-v1.json')
        }

        $manifestFull = [IO.Path]::GetFullPath($ManifestPath)
        if (-not (Test-Path -LiteralPath $manifestFull -PathType Leaf)) {
            throw "$FailurePrefix`: runtime_manifest_missing"
        }
        try {
            $manifest = Get-Content -Raw -LiteralPath $manifestFull |
                ConvertFrom-Json -ErrorAction Stop
        } catch {
            throw "$FailurePrefix`: runtime_manifest_invalid"
        }
        if ([string]$manifest.schema -cne 'baxy-mind-runtime-v1') {
            throw "$FailurePrefix`: runtime_manifest_schema"
        }
        $Candidate = [string]$manifest.python
        if ([string]::IsNullOrWhiteSpace($Candidate)) {
            throw "$FailurePrefix`: runtime_manifest_python_missing"
        }
    }

    try {
        $pythonFull = [IO.Path]::GetFullPath($Candidate)
    } catch {
        throw "$FailurePrefix`: python_path_invalid"
    }
    if (-not (Test-Path -LiteralPath $pythonFull -PathType Leaf) -or
        [IO.Path]::GetFileName($pythonFull) -ine 'python.exe') {
        throw "$FailurePrefix`: python_missing"
    }
    return $pythonFull
}

function Assert-BaxyPythonLockToolchain {
    param(
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$FailurePrefix
    )

    $identity = Invoke-BaxyPythonForOutput `
        -Python $Python `
        -Arguments @(
            '-X',
            'utf8',
            '-c',
            ('import platform, sys; print(' +
                'sys.implementation.name, ' +
                'str(sys.version_info.major) + chr(46) + ' +
                'str(sys.version_info.minor), sys.platform, ' +
                'platform.machine().upper(), sep=chr(124))')
        ) `
        -WorkingDirectory $WorkingDirectory
    if ($identity.ExitCode -ne 0 -or
        $identity.Text -cne 'cpython|3.12|win32|AMD64') {
        throw "$FailurePrefix`: python_must_be_cpython_3_12_win_x64"
    }

    $pip = Invoke-BaxyPythonForOutput `
        -Python $Python `
        -Arguments @('-X', 'utf8', '-m', 'pip', '--version') `
        -WorkingDirectory $WorkingDirectory
    if ($pip.ExitCode -ne 0 -or
        -not $pip.Text.StartsWith(
            'pip 26.1.2 ',
            [StringComparison]::Ordinal)) {
        throw "$FailurePrefix`: pip_must_be_26_1_2"
    }
}

function Assert-BaxyRuntimeLock {
    param(
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string]$Repository,
        [ValidateSet('Runtime', 'Test')][string]$Profile = 'Runtime',
        [Parameter(Mandatory = $true)][string]$FailurePrefix,
        [AllowEmptyString()][string]$LockPath,
        [AllowEmptyString()][string]$ConstraintsPath,
        [switch]$StructureOnly
    )

    $profileName = $Profile.ToLowerInvariant()
    $verifier = Join-Path $Repository (
        'scripts\verify_python_runtime_lock.py')
    $lock = if ([string]::IsNullOrWhiteSpace($LockPath)) {
        Join-Path $Repository "pylock.$profileName-win-x64.toml"
    } else {
        [IO.Path]::GetFullPath($LockPath)
    }
    $constraints = if ([string]::IsNullOrWhiteSpace($ConstraintsPath)) {
        Join-Path $Repository "constraints-$profileName-win-x64.txt"
    } else {
        [IO.Path]::GetFullPath($ConstraintsPath)
    }
    foreach ($requiredFile in @($verifier, $lock, $constraints)) {
        if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
            throw "$FailurePrefix`: lock_source_missing"
        }
    }

    $arguments = @(
        '-X',
        'utf8',
        $verifier,
        '--lock',
        $lock,
        '--constraints',
        $constraints
    )
    if ($StructureOnly.IsPresent) {
        $arguments += '--structure-only'
    }
    $verification = Invoke-BaxyPythonForOutput `
        -Python $Python `
        -Arguments $arguments `
        -WorkingDirectory $Repository
    if ($verification.ExitCode -ne 0) {
        throw "$FailurePrefix`: $profileName`_lock_invalid"
    }
    Write-Output $verification.Text
}
