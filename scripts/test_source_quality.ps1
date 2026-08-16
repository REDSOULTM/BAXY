[CmdletBinding()]
param(
    [ValidateSet('Fast', 'Full')]
    [string]$Mode = 'Fast',

    [string]$QualityPython = $env:BAXY_QUALITY_PYTHON,

    [string]$RuntimeManifest,

    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Mode = if ($Mode -ieq 'Full') { 'Full' } else { 'Fast' }
$script:SourceQualityRoot = [IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..'))

function Test-StrictDescendant {
    param(
        [Parameter(Mandatory = $true)][string]$Parent,
        [Parameter(Mandatory = $true)][string]$Child
    )

    $parentFull = [IO.Path]::GetFullPath($Parent).TrimEnd('\', '/')
    $childFull = [IO.Path]::GetFullPath($Child)
    return $childFull.StartsWith(
        $parentFull + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase)
}

function Get-ProcessEnvironmentValue {
    param([Parameter(Mandatory = $true)][string]$Name)

    return [Environment]::GetEnvironmentVariable(
        $Name,
        [EnvironmentVariableTarget]::Process)
}

function Set-ProcessEnvironmentValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [AllowNull()][string]$Value
    )

    [Environment]::SetEnvironmentVariable(
        $Name,
        $Value,
        [EnvironmentVariableTarget]::Process)
}

function Invoke-WithDotnetEnvironment {
    param(
        [Parameter(Mandatory = $true)][string]$DotnetPath,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    $dotnetRoot = [IO.Path]::GetDirectoryName(
        [IO.Path]::GetFullPath($DotnetPath))
    $previousRoot = Get-ProcessEnvironmentValue -Name 'DOTNET_ROOT'
    $previousRootX64 = Get-ProcessEnvironmentValue -Name 'DOTNET_ROOT_X64'
    $previousPath = Get-ProcessEnvironmentValue -Name 'PATH'
    $scopedPath = if ([string]::IsNullOrWhiteSpace($previousPath)) {
        $dotnetRoot
    } else {
        $dotnetRoot + [IO.Path]::PathSeparator + $previousPath
    }

    try {
        Set-ProcessEnvironmentValue -Name 'DOTNET_ROOT' -Value $dotnetRoot
        Set-ProcessEnvironmentValue -Name 'DOTNET_ROOT_X64' -Value $dotnetRoot
        Set-ProcessEnvironmentValue -Name 'PATH' -Value $scopedPath
        & $Action
    } finally {
        Set-ProcessEnvironmentValue -Name 'DOTNET_ROOT' -Value $previousRoot
        Set-ProcessEnvironmentValue -Name 'DOTNET_ROOT_X64' -Value $previousRootX64
        Set-ProcessEnvironmentValue -Name 'PATH' -Value $previousPath
    }
}

function Invoke-NativeForOutput {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    Push-Location -LiteralPath $WorkingDirectory
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5 surfaces redirected native stderr as an
        # ErrorRecord. Capture it for a stable preflight diagnostic instead of
        # letting ErrorActionPreference=Stop bypass the resolver.
        $ErrorActionPreference = 'Continue'
        $output = @(& $Executable @Arguments 2>&1)
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

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Stage,
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    Write-Output "source_quality_stage_started: $Stage"
    Push-Location -LiteralPath $WorkingDirectory
    try {
        & $Executable @Arguments
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }

    if ($exitCode -ne 0) {
        throw "source_quality_check_failed: $Stage (exit $exitCode)"
    }
    Write-Output "source_quality_stage_passed: $Stage"
}

function Assert-PowerShellSourceHealth {
    param([Parameter(Mandatory = $true)][string]$ScriptsRoot)

    # A helper must have a literal call in its own file or in a script that
    # directly dot-sources that file. Dynamic callback/export patterns are not
    # silently accepted: introducing one requires an explicit quality policy.
    $scriptsFull = [IO.Path]::GetFullPath($ScriptsRoot)
    $sourceFiles = @(
        Get-ChildItem -LiteralPath $scriptsFull -Recurse -File |
            Where-Object { $_.Extension -in @('.ps1', '.psm1') })
    $definitions = New-Object 'Collections.Generic.List[object]'
    $sourcePaths = New-Object 'Collections.Generic.HashSet[string]' (
        [StringComparer]::OrdinalIgnoreCase)
    $commandsByFile = @{}
    $dotSourcesByFile = @{}
    $parseFailures = New-Object 'Collections.Generic.List[string]'
    foreach ($sourceFile in $sourceFiles) {
        $null = $sourcePaths.Add($sourceFile.FullName)
    }

    foreach ($sourceFile in $sourceFiles) {
        $commands = New-Object 'Collections.Generic.HashSet[string]' (
            [StringComparer]::OrdinalIgnoreCase)
        $dotSources = New-Object 'Collections.Generic.HashSet[string]' (
            [StringComparer]::OrdinalIgnoreCase)
        $tokens = $null
        $parseErrors = $null
        $ast = [Management.Automation.Language.Parser]::ParseFile(
            $sourceFile.FullName,
            [ref]$tokens,
            [ref]$parseErrors)
        foreach ($parseError in @($parseErrors)) {
            $parseFailures.Add(
                "$($sourceFile.FullName):" +
                "$($parseError.Extent.StartLineNumber):" +
                "$($parseError.Extent.StartColumnNumber):" +
                $parseError.Message)
        }
        foreach ($definition in @(
                $ast.FindAll(
                    {
                        param($node)
                        $node -is [Management.Automation.Language.FunctionDefinitionAst]
                    },
                    $true))) {
            $definitions.Add([pscustomobject]@{
                    Name = $definition.Name
                    Path = $sourceFile.FullName
                    Line = $definition.Extent.StartLineNumber
                })
        }
        foreach ($command in @(
                $ast.FindAll(
                    {
                        param($node)
                        $node -is [Management.Automation.Language.CommandAst]
                    },
                    $true))) {
            $commandName = $command.GetCommandName()
            if (-not [string]::IsNullOrWhiteSpace($commandName)) {
                $null = $commands.Add($commandName)
            }
            if ($command.InvocationOperator -eq
                [Management.Automation.Language.TokenKind]::Dot) {
                foreach ($literal in @(
                        $command.FindAll(
                            {
                                param($node)
                                $node -is [Management.Automation.Language.StringConstantExpressionAst]
                            },
                            $true))) {
                    if ($literal.Value -notmatch '\.psm?1$') {
                        continue
                    }
                    try {
                        $candidate = if (
                            [IO.Path]::IsPathRooted($literal.Value)) {
                            [IO.Path]::GetFullPath($literal.Value)
                        } else {
                            [IO.Path]::GetFullPath(
                                (Join-Path $sourceFile.DirectoryName $literal.Value))
                        }
                    } catch {
                        continue
                    }
                    if ($sourcePaths.Contains($candidate)) {
                        $null = $dotSources.Add($candidate)
                    }
                }
            }
        }
        $commandsByFile[$sourceFile.FullName] = $commands
        $dotSourcesByFile[$sourceFile.FullName] = $dotSources
    }

    if ($parseFailures.Count -gt 0) {
        throw (
            'source_quality_check_failed: powershell-parse ' +
            "($($parseFailures -join '; '))")
    }

    $unused = New-Object 'Collections.Generic.List[object]'
    foreach ($definition in $definitions) {
        $used = $commandsByFile[$definition.Path].Contains(
            $definition.Name)
        if (-not $used) {
            foreach ($consumer in $sourceFiles) {
                if (
                    $dotSourcesByFile[$consumer.FullName].Contains(
                        $definition.Path) -and
                    $commandsByFile[$consumer.FullName].Contains(
                        $definition.Name)) {
                    $used = $true
                    break
                }
            }
        }
        if (-not $used) {
            $unused.Add($definition)
        }
    }
    $unused = @($unused | Sort-Object Path, Line)
    if ($unused.Count -gt 0) {
        $details = @(
            $unused |
                ForEach-Object { "$($_.Path):$($_.Line):$($_.Name)" })
        throw (
            'source_quality_check_failed: powershell-unused-function ' +
            "($($details -join '; '))")
    }
}

function Get-ExpectedRuffVersion {
    $requirementsPath = Join-Path $script:SourceQualityRoot 'requirements-quality.txt'
    if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
        throw 'source_quality_preflight_failed: requirements_quality_missing'
    }

    $matches = @(
        Get-Content -LiteralPath $requirementsPath |
            ForEach-Object {
                $match = [regex]::Match(
                    [string]$_,
                    '^\s*ruff==(?<version>[0-9]+\.[0-9]+\.[0-9]+)\s*$')
                if ($match.Success) {
                    $match.Groups['version'].Value
                }
            })
    if ($matches.Count -ne 1) {
        throw 'source_quality_preflight_failed: ruff_pin_must_be_exactly_one'
    }
    return [string]$matches[0]
}

function Resolve-QualityPython {
    param([AllowEmptyString()][string]$Candidate)

    if ([string]::IsNullOrWhiteSpace($Candidate)) {
        $Candidate = Join-Path $env:LOCALAPPDATA (
            'BAXYQuality\source-quality-v1\Scripts\python.exe')
    }
    $candidateFull = [IO.Path]::GetFullPath($Candidate)
    if (-not (Test-Path -LiteralPath $candidateFull -PathType Leaf)) {
        throw "source_quality_preflight_failed: quality_python_missing ($candidateFull)"
    }

    $pythonVersion = Invoke-NativeForOutput `
        -Executable $candidateFull `
        -Arguments @(
            '-X',
            'utf8',
            '-c',
            'import sys; print(sys.version_info.major, sys.version_info.minor, sep=chr(46))'
        ) `
        -WorkingDirectory $script:SourceQualityRoot
    if ($pythonVersion.ExitCode -ne 0 -or
        $pythonVersion.Text -cne '3.12') {
        throw (
            'source_quality_preflight_failed: quality_python_must_be_3.12 ' +
            "($candidateFull reported '$($pythonVersion.Text)')")
    }

    $expectedRuff = Get-ExpectedRuffVersion
    $ruffVersion = Invoke-NativeForOutput `
        -Executable $candidateFull `
        -Arguments @('-X', 'utf8', '-m', 'ruff', '--version') `
        -WorkingDirectory $script:SourceQualityRoot
    if ($ruffVersion.ExitCode -ne 0 -or
        $ruffVersion.Text -cne "ruff $expectedRuff") {
        throw (
            'source_quality_preflight_failed: quality_ruff_version_mismatch ' +
            "(expected 'ruff $expectedRuff', reported '$($ruffVersion.Text)')")
    }

    return [pscustomobject]@{
        Path = $candidateFull
        PythonVersion = $pythonVersion.Text
        RuffVersion = $ruffVersion.Text
    }
}

function Resolve-Dotnet {
    $globalJsonPath = Join-Path $script:SourceQualityRoot 'global.json'
    if (-not (Test-Path -LiteralPath $globalJsonPath -PathType Leaf)) {
        throw 'source_quality_preflight_failed: global_json_missing'
    }
    $globalJson = Get-Content -Raw -LiteralPath $globalJsonPath |
        ConvertFrom-Json
    $expectedVersion = [string]$globalJson.sdk.version
    if ([string]::IsNullOrWhiteSpace($expectedVersion)) {
        throw 'source_quality_preflight_failed: global_json_sdk_missing'
    }

    $candidates = New-Object 'Collections.Generic.List[string]'
    if (-not [string]::IsNullOrWhiteSpace($env:BAXY_DOTNET)) {
        $candidates.Add([string]$env:BAXY_DOTNET)
    }
    $candidates.Add((Join-Path $env:USERPROFILE '.dotnet\dotnet.exe'))
    $pathDotnet = Get-Command dotnet -CommandType Application -ErrorAction SilentlyContinue
    if ($null -ne $pathDotnet) {
        $candidates.Add([string]$pathDotnet.Source)
    }

    $seen = New-Object 'Collections.Generic.HashSet[string]' (
        [StringComparer]::OrdinalIgnoreCase)
    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            continue
        }
        $candidateFull = [IO.Path]::GetFullPath($candidate)
        if (-not $seen.Add($candidateFull)) {
            continue
        }
        $version = Invoke-NativeForOutput `
            -Executable $candidateFull `
            -Arguments @('--version') `
            -WorkingDirectory $script:SourceQualityRoot
        if ($version.ExitCode -eq 0 -and
            $version.Text -ceq $expectedVersion) {
            return [pscustomobject]@{
                Path = $candidateFull
                Version = $version.Text
            }
        }
    }

    throw (
        'source_quality_preflight_failed: required_dotnet_sdk_not_found ' +
        "(expected $expectedVersion)")
}

function Resolve-FieldUiToolchain {
    $fieldUi = Join-Path $script:SourceQualityRoot 'src\Baxy.FieldUi'
    $packagePath = Join-Path $fieldUi 'package.json'
    $lockPath = Join-Path $fieldUi 'pnpm-lock.yaml'
    if (-not (Test-Path -LiteralPath $packagePath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $lockPath -PathType Leaf)) {
        throw 'source_quality_preflight_failed: field_ui_manifests_missing'
    }

    $eslint = Join-Path $fieldUi 'node_modules\.bin\eslint.cmd'
    $tsc = Join-Path $fieldUi 'node_modules\.bin\tsc.cmd'
    if (-not (Test-Path -LiteralPath $eslint -PathType Leaf) -or
        -not (Test-Path -LiteralPath $tsc -PathType Leaf)) {
        throw (
            'source_quality_preflight_failed: field_ui_dependencies_missing ' +
            '(provision them from pnpm-lock.yaml with --frozen-lockfile)')
    }

    $eslintVersion = Invoke-NativeForOutput `
        -Executable $eslint `
        -Arguments @('--version') `
        -WorkingDirectory $fieldUi
    if ($eslintVersion.ExitCode -ne 0) {
        throw 'source_quality_preflight_failed: field_ui_eslint_unavailable'
    }
    $tscVersion = Invoke-NativeForOutput `
        -Executable $tsc `
        -Arguments @('--version') `
        -WorkingDirectory $fieldUi
    if ($tscVersion.ExitCode -ne 0) {
        throw 'source_quality_preflight_failed: field_ui_typescript_unavailable'
    }

    return [pscustomobject]@{
        Root = [IO.Path]::GetFullPath($fieldUi)
        Eslint = [IO.Path]::GetFullPath($eslint)
        EslintVersion = $eslintVersion.Text
        TypeScript = [IO.Path]::GetFullPath($tsc)
        TypeScriptVersion = $tscVersion.Text
    }
}

function Assert-RuntimePythonLocks {
    param([Parameter(Mandatory = $true)][string]$Python)

    $verifier = Join-Path $script:SourceQualityRoot (
        'scripts\verify_python_runtime_lock.py')
    if (-not (Test-Path -LiteralPath $verifier -PathType Leaf)) {
        throw 'source_quality_preflight_failed: runtime_lock_verifier_missing'
    }
    foreach ($profile in @('runtime', 'test')) {
        $lock = Join-Path $script:SourceQualityRoot (
            "pylock.$profile-win-x64.toml")
        $constraints = Join-Path $script:SourceQualityRoot (
            "constraints-$profile-win-x64.txt")
        if (-not (Test-Path -LiteralPath $lock -PathType Leaf) -or
            -not (Test-Path -LiteralPath $constraints -PathType Leaf)) {
            throw (
                'source_quality_preflight_failed: ' +
                "$profile`_lock_source_missing")
        }
        $verification = Invoke-NativeForOutput `
            -Executable $Python `
            -Arguments @(
                '-X',
                'utf8',
                $verifier,
                '--lock',
                $lock,
                '--constraints',
                $constraints
            ) `
            -WorkingDirectory $script:SourceQualityRoot
        if ($verification.ExitCode -ne 0) {
            throw (
                'source_quality_preflight_failed: ' +
                "$profile`_lock_invalid")
        }
    }
}

function Resolve-RuntimePython {
    param([AllowEmptyString()][string]$ManifestPath)

    if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
        $ManifestPath = Join-Path $env:LOCALAPPDATA (
            'BAXYRuntime\mind-runtime-v1.json')
    }
    $manifestFull = [IO.Path]::GetFullPath($ManifestPath)
    if (-not (Test-Path -LiteralPath $manifestFull -PathType Leaf)) {
        throw (
            'source_quality_preflight_failed: runtime_manifest_missing ' +
            "($manifestFull)")
    }

    $manifest = Get-Content -Raw -LiteralPath $manifestFull | ConvertFrom-Json
    $pythonValue = [string]$manifest.python
    if ([string]::IsNullOrWhiteSpace($pythonValue)) {
        throw 'source_quality_preflight_failed: runtime_python_missing'
    }
    $pythonFull = [IO.Path]::GetFullPath($pythonValue)
    if (-not (Test-Path -LiteralPath $pythonFull -PathType Leaf) -or
        [IO.Path]::GetFileName($pythonFull) -ine 'python.exe') {
        throw (
            'source_quality_preflight_failed: runtime_python_invalid ' +
            "($pythonFull)")
    }

    $version = Invoke-NativeForOutput `
        -Executable $pythonFull `
        -Arguments @(
            '-X',
            'utf8',
            '-c',
            'import sys; print(sys.version_info.major, sys.version_info.minor, sep=chr(46))'
        ) `
        -WorkingDirectory $script:SourceQualityRoot
    if ($version.ExitCode -ne 0 -or $version.Text -cne '3.12') {
        throw (
            'source_quality_preflight_failed: runtime_python_must_be_3.12 ' +
            "($pythonFull reported '$($version.Text)')")
    }
    Assert-RuntimePythonLocks -Python $pythonFull

    return [pscustomobject]@{
        Path = $pythonFull
        Version = $version.Text
        Manifest = $manifestFull
    }
}

function Invoke-WithTemporaryPythonCache {
    param([Parameter(Mandatory = $true)][scriptblock]$Action)

    $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $cachePath = Join-Path $temporaryRoot (
        'baxy-source-quality-' + [Guid]::NewGuid().ToString('N'))
    $previousValue = Get-ProcessEnvironmentValue -Name 'PYTHONPYCACHEPREFIX'
    try {
        New-Item -ItemType Directory -Path $cachePath | Out-Null
        Set-ProcessEnvironmentValue `
            -Name 'PYTHONPYCACHEPREFIX' `
            -Value $cachePath
        & $Action
    } finally {
        Set-ProcessEnvironmentValue `
            -Name 'PYTHONPYCACHEPREFIX' `
            -Value $previousValue

        if (Test-Path -LiteralPath $cachePath) {
            $cacheFull = [IO.Path]::GetFullPath($cachePath)
            $cacheLeaf = [IO.Path]::GetFileName($cacheFull)
            $cacheItem = Get-Item -LiteralPath $cacheFull -Force
            if (-not (Test-StrictDescendant `
                    -Parent $temporaryRoot `
                    -Child $cacheFull) -or
                -not $cacheLeaf.StartsWith(
                    'baxy-source-quality-',
                    [StringComparison]::Ordinal) -or
                (($cacheItem.Attributes -band
                    [IO.FileAttributes]::ReparsePoint) -ne 0)) {
                throw (
                    'source_quality_cleanup_failed: unsafe_python_cache_path ' +
                    "($cacheFull)")
            }
            Remove-Item -LiteralPath $cacheFull -Recurse -Force
        }
    }
}

function Invoke-SourceQualityPreflight {
    $quality = Resolve-QualityPython -Candidate $QualityPython
    $dotnet = Resolve-Dotnet
    $fieldUi = Resolve-FieldUiToolchain
    $runtime = $null
    if ($Mode -ceq 'Full') {
        $runtime = Resolve-RuntimePython -ManifestPath $RuntimeManifest
    }

    return [pscustomobject]@{
        Quality = $quality
        Dotnet = $dotnet
        FieldUi = $fieldUi
        Runtime = $runtime
    }
}

function Invoke-SourceQualityGate {
    $tools = Invoke-SourceQualityPreflight
    Write-Output (
        'source_quality_toolchain: ' +
        "dotnet=$($tools.Dotnet.Version); " +
        "python=$($tools.Quality.PythonVersion); " +
        "$($tools.Quality.RuffVersion); " +
        "eslint=$($tools.FieldUi.EslintVersion); " +
        "typescript=$($tools.FieldUi.TypeScriptVersion); " +
        "runtime_locks=$(if ($null -eq $tools.Runtime) { 'not-required' } else { 'verified' })")

    if ($PreflightOnly) {
        Write-Output "source_quality_preflight_passed: mode=$Mode"
        return
    }

    $root = $script:SourceQualityRoot
    Write-Output 'source_quality_stage_started: powershell-source'
    Assert-PowerShellSourceHealth -ScriptsRoot (Join-Path $root 'scripts')
    Write-Output 'source_quality_stage_passed: powershell-source'

    Invoke-Checked `
        -Stage 'python-ruff' `
        -Executable $tools.Quality.Path `
        -Arguments @(
            '-X',
            'utf8',
            '-m',
            'ruff',
            'check',
            '--no-cache',
            '--config',
            (Join-Path $root 'ruff.toml'),
            (Join-Path $root 'main.py'),
            (Join-Path $root 'scripts'),
            (Join-Path $root 'src\baxy_mind'),
            (Join-Path $root 'tests'),
            (Join-Path $root 'experiments\mind_llm_tournament'),
            (Join-Path $root 'experiments\mind_router_spike')
        ) `
        -WorkingDirectory $root

    Invoke-WithTemporaryPythonCache -Action {
        Invoke-Checked `
            -Stage 'python-compileall' `
            -Executable $tools.Quality.Path `
            -Arguments @(
                '-X',
                'utf8',
                '-m',
                'compileall',
                '-q',
                (Join-Path $root 'main.py'),
                (Join-Path $root 'scripts'),
                (Join-Path $root 'src\baxy_mind'),
                (Join-Path $root 'tests')
            ) `
            -WorkingDirectory $root
    }

    Invoke-Checked `
        -Stage 'field-ui-eslint' `
        -Executable $tools.FieldUi.Eslint `
        -Arguments @('.', '--max-warnings', '0') `
        -WorkingDirectory $tools.FieldUi.Root
    Invoke-Checked `
        -Stage 'field-ui-tsc-app' `
        -Executable $tools.FieldUi.TypeScript `
        -Arguments @(
            '--noEmit',
            '--incremental',
            'false',
            '--pretty',
            'false',
            '-p',
            (Join-Path $tools.FieldUi.Root 'tsconfig.app.json')
        ) `
        -WorkingDirectory $tools.FieldUi.Root
    Invoke-Checked `
        -Stage 'field-ui-tsc-node' `
        -Executable $tools.FieldUi.TypeScript `
        -Arguments @(
            '--noEmit',
            '--incremental',
            'false',
            '--pretty',
            'false',
            '-p',
            (Join-Path $tools.FieldUi.Root 'tsconfig.node.json')
        ) `
        -WorkingDirectory $tools.FieldUi.Root

    Invoke-WithDotnetEnvironment -DotnetPath $tools.Dotnet.Path -Action {
        Invoke-Checked `
            -Stage 'dotnet-format' `
            -Executable $tools.Dotnet.Path `
            -Arguments @(
                'format',
                (Join-Path $root 'Baxy.slnx'),
                '--verify-no-changes',
                '--no-restore',
                '--verbosity',
                'minimal'
            ) `
            -WorkingDirectory $root

        Invoke-Checked `
            -Stage 'dotnet-build-release' `
            -Executable $tools.Dotnet.Path `
            -Arguments @(
                'build',
                (Join-Path $root 'Baxy.slnx'),
                '-c',
                'Release',
                '--no-restore',
                '--nologo'
            ) `
            -WorkingDirectory $root

        if ($Mode -ceq 'Full') {
            Invoke-Checked `
                -Stage 'dotnet-tests' `
                -Executable $tools.Dotnet.Path `
                -Arguments @(
                    'test',
                    (Join-Path $root 'Baxy.slnx'),
                    '-c',
                    'Release',
                    '--no-build',
                    # Integration and lifecycle suites intentionally share
                    # machine-level runtime resources.  Running test projects
                    # concurrently can make one suite tear down another
                    # suite's Core process and produce false startup failures.
                    # Serialize projects; each project still owns its normal
                    # in-process NUnit parallelism.
                    '-m:1',
                    '--nologo'
                ) `
                -WorkingDirectory $root
        }
    }

    if ($Mode -ceq 'Full') {
        $previousPythonPath = Get-ProcessEnvironmentValue -Name 'PYTHONPATH'
        $previousDontWrite = Get-ProcessEnvironmentValue `
            -Name 'PYTHONDONTWRITEBYTECODE'
        try {
            Set-ProcessEnvironmentValue `
                -Name 'PYTHONPATH' `
                -Value (Join-Path $root 'src')
            Set-ProcessEnvironmentValue `
                -Name 'PYTHONDONTWRITEBYTECODE' `
                -Value '1'
            Invoke-Checked `
                -Stage 'python-tests' `
                -Executable $tools.Runtime.Path `
                -Arguments @(
                    '-X',
                    'utf8',
                    '-m',
                    'pytest',
                    '-p',
                    'no:cacheprovider',
                    (Join-Path $root 'tests'),
                    '-q'
                ) `
                -WorkingDirectory $root
        } finally {
            Set-ProcessEnvironmentValue `
                -Name 'PYTHONPATH' `
                -Value $previousPythonPath
            Set-ProcessEnvironmentValue `
                -Name 'PYTHONDONTWRITEBYTECODE' `
                -Value $previousDontWrite
        }
    }

    Write-Output "source_quality_gate_passed: mode=$Mode"
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        Invoke-SourceQualityGate
    } catch {
        [Console]::Error.WriteLine([string]$_.Exception.Message)
        exit 1
    }
}
