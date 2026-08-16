param(
    [string]$RuntimeManifest,
    [string]$OutputPath,
    [switch]$Cpu
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$productArtifacts = [IO.Path]::GetFullPath((Join-Path $root 'artifacts\product'))
if ([string]::IsNullOrWhiteSpace($RuntimeManifest)) {
    $RuntimeManifest = Join-Path $env:LOCALAPPDATA 'BAXYRuntime\mind-runtime-v1.json'
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $productArtifacts 'mind_shell_e2e_gate.json'
}
$RuntimeManifest = [IO.Path]::GetFullPath($RuntimeManifest)
$OutputPath = [IO.Path]::GetFullPath($OutputPath)

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

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-MindPythonCandidate {
    param(
        [Parameter(Mandatory = $true)][string]$Candidate,
        [Parameter(Mandatory = $true)][string]$ImportPath
    )

    if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
        return $false
    }
    $probe = @'
import sys
import baxy_mind
import baxy_mind.voice
import numpy
import onnxruntime
import sherpa_onnx
raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 4)
'@
    $previousPythonPath = $env:PYTHONPATH
    $previousErrorAction = $ErrorActionPreference
    try {
        $env:PYTHONPATH = $ImportPath
        $ErrorActionPreference = 'Continue'
        & $Candidate -X utf8 -c $probe *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $previousErrorAction
        $env:PYTHONPATH = $previousPythonPath
    }
}

function Resolve-MindPython {
    param(
        [Parameter(Mandatory = $true)][string]$RegisteredPython,
        [Parameter(Mandatory = $true)][string]$ImportPath
    )

    $candidates = [Collections.Generic.List[string]]::new()
    $candidates.Add($RegisteredPython)
    $registeredVenv = Split-Path -Parent (Split-Path -Parent $RegisteredPython)
    $venvConfig = Join-Path $registeredVenv 'pyvenv.cfg'
    if (Test-Path -LiteralPath $venvConfig -PathType Leaf) {
        $configText = Get-Content -LiteralPath $venvConfig -Raw
        if ($configText -match '(?m)^home\s*=\s*(.+?)\s*$') {
            $candidates.Add((Join-Path $Matches[1].Trim() 'python.exe'))
        }
    }
    $localData = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::LocalApplicationData)
    $userProfile = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::UserProfile)
    $candidates.Add((Join-Path $localData 'Programs\Python\Python312\python.exe'))
    $candidates.Add((Join-Path $env:ProgramFiles 'Python312\python.exe'))
    $candidates.Add((Join-Path $userProfile (
        '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')))
    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (Test-MindPythonCandidate -Candidate $candidate -ImportPath $ImportPath) {
            return [IO.Path]::GetFullPath($candidate)
        }
    }
    throw 'No CPython 3.12 candidate can load the registered BAXY mind dependencies.'
}

function Move-AtomicGateFile {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $sourceFull = [IO.Path]::GetFullPath($Source)
    $destinationFull = [IO.Path]::GetFullPath($Destination)
    if (-not (Test-Path -LiteralPath $sourceFull -PathType Leaf)) {
        throw "Atomic publication source is missing: $sourceFull"
    }
    if (-not [string]::Equals(
            [IO.Path]::GetPathRoot($sourceFull),
            [IO.Path]::GetPathRoot($destinationFull),
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Atomic publication source and destination must use the same volume.'
    }

    if (-not (Test-Path -LiteralPath $destinationFull -PathType Leaf)) {
        [IO.File]::Move($sourceFull, $destinationFull)
        return
    }

    $destinationDirectory = Split-Path -Parent $destinationFull
    $backupPath = Join-Path $destinationDirectory (
        '.' + [IO.Path]::GetFileName($destinationFull) + '.' +
        [Guid]::NewGuid().ToString('N') + '.bak')
    try {
        # Windows PowerShell 5 can bind a null backup path as an invalid empty
        # path. A real, gate-owned backup preserves atomic replacement while
        # keeping the prior canonical artifact recoverable until success.
        [IO.File]::Replace($sourceFull, $destinationFull, $backupPath, $true)
    } finally {
        if (Test-Path -LiteralPath $backupPath -PathType Leaf) {
            Remove-Item -LiteralPath $backupPath -Force
        }
    }
}

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value
    )

    $directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
        New-Item -ItemType Directory -Path $directory | Out-Null
    }
    $temporary = Join-Path $directory (
        '.' + [IO.Path]::GetFileName($Path) + '.' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $text = ($Value | ConvertTo-Json -Depth 10) + "`n"
        [IO.File]::WriteAllText(
            $temporary,
            $text,
            [Text.UTF8Encoding]::new($false))
        Move-AtomicGateFile -Source $temporary -Destination $Path
    } finally {
        if (Test-Path -LiteralPath $temporary -PathType Leaf) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Get-TrxTestRecords {
    param([Parameter(Mandatory = $true)][xml]$Trx)

    $definitions = @($Trx.TestRun.TestDefinitions.UnitTest)
    $results = @($Trx.TestRun.Results.UnitTestResult)
    if ($definitions.Count -eq 0) {
        return @()
    }
    if ($results.Count -ne $definitions.Count) {
        throw 'The TRX does not contain exactly one result for every test definition.'
    }

    $definitionsById = @{}
    foreach ($definition in $definitions) {
        $testId = [string]$definition.id
        if ([string]::IsNullOrWhiteSpace($testId) -or
            $definitionsById.ContainsKey($testId)) {
            throw 'The TRX contains an empty or duplicate test definition identity.'
        }
        $definitionsById[$testId] = $definition
    }

    $resultsById = @{}
    foreach ($result in $results) {
        $testId = [string]$result.testId
        if ([string]::IsNullOrWhiteSpace($testId) -or
            $resultsById.ContainsKey($testId)) {
            throw 'The TRX contains an empty or duplicate result identity.'
        }
        if (-not $definitionsById.ContainsKey($testId)) {
            throw 'The TRX contains a result without a matching test definition.'
        }
        $resultsById[$testId] = $result
    }

    foreach ($definition in $definitions) {
        $testId = [string]$definition.id
        if ([string]::IsNullOrWhiteSpace($testId) -or
            -not $resultsById.ContainsKey($testId)) {
            throw 'The TRX contains an unmatched test definition identity.'
        }
        [pscustomobject]@{
            fully_qualified_name = '{0}.{1}' -f (
                [string]$definition.TestMethod.className),
                ([string]$definition.TestMethod.name)
            class_name = [string]$definition.TestMethod.className
            storage = [IO.Path]::GetFullPath([string]$definition.storage)
            outcome = [string]$resultsById[$testId].outcome
        }
    }
}

if (-not (Test-StrictDescendant -Parent $productArtifacts -Child $OutputPath)) {
    throw 'OutputPath must be a strict descendant of artifacts\product.'
}
$outputDirectory = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}
if (-not (Test-Path -LiteralPath $RuntimeManifest -PathType Leaf)) {
    throw "Mind runtime manifest is missing: $RuntimeManifest"
}
if ((Get-Item -LiteralPath $RuntimeManifest -Force).Length -gt 16KB) {
    throw 'Mind runtime manifest exceeds its reviewed size bound.'
}

try {
    $runtime = Get-Content -LiteralPath $RuntimeManifest -Raw -Encoding UTF8 |
        ConvertFrom-Json -ErrorAction Stop
} catch {
    throw "Mind runtime manifest is not valid JSON: $($_.Exception.Message)"
}
if (-not [string]::Equals(
        [string]$runtime.schema,
        'baxy-mind-runtime-v1',
        [StringComparison]::Ordinal)) {
    throw 'Mind runtime manifest has an unsupported schema.'
}

$registeredPython = [IO.Path]::GetFullPath([string]$runtime.python)
$pythonPath = [IO.Path]::GetFullPath([string]$runtime.python_path)
$gguf = [IO.Path]::GetFullPath([string]$runtime.gguf)
$llamaServer = [IO.Path]::GetFullPath([string]$runtime.llama_server)
foreach ($requiredFile in @($registeredPython, $gguf, $llamaServer)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "A required mind runtime file is missing: $requiredFile"
    }
}
if (-not (Test-Path -LiteralPath $pythonPath -PathType Container)) {
    throw "The mind Python source directory is missing: $pythonPath"
}
if (-not (Test-Path -LiteralPath (Join-Path $pythonPath 'baxy_mind\__main__.py') -PathType Leaf)) {
    throw 'The configured Python path is not the BAXY mind source tree.'
}
$registeredVenv = Split-Path -Parent (Split-Path -Parent $registeredPython)
$registeredSitePackages = Join-Path $registeredVenv 'Lib\site-packages'
if (-not (Test-Path -LiteralPath $registeredSitePackages -PathType Container)) {
    throw "The registered BAXY Python dependencies are missing: $registeredSitePackages"
}
$mindPythonPath = $pythonPath + [IO.Path]::PathSeparator + $registeredSitePackages
$python = Resolve-MindPython `
    -RegisteredPython $registeredPython `
    -ImportPath $mindPythonPath

$dotnetCandidates = [Collections.Generic.List[string]]::new()
$dotnetCandidates.Add((Join-Path $env:USERPROFILE '.dotnet\dotnet.exe'))
$dotnetFromPath = Get-Command dotnet -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Source -First 1
if (-not [string]::IsNullOrWhiteSpace($dotnetFromPath)) {
    $dotnetCandidates.Add($dotnetFromPath)
}
$dotnet = $null
foreach ($candidate in $dotnetCandidates) {
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        continue
    }
    $sdk = [string](& $candidate --version)
    if ($LASTEXITCODE -eq 0 -and $sdk.Trim() -ceq '10.0.100') {
        $dotnet = [IO.Path]::GetFullPath($candidate)
        break
    }
}
if ([string]::IsNullOrWhiteSpace($dotnet)) {
    throw ("BAXY requires the exact .NET SDK 10.0.100. Checked: " +
        ($dotnetCandidates -join '; '))
}
$dotnetRoot = [IO.Path]::GetDirectoryName($dotnet)
if ([string]::IsNullOrWhiteSpace($dotnetRoot) -or
    -not (Test-Path -LiteralPath $dotnetRoot -PathType Container)) {
    throw 'The selected .NET SDK executable has no valid runtime root.'
}

$testProject = Join-Path $root 'tests\Baxy.Integration.Tests\Baxy.Integration.Tests.csproj'
$corpus = Join-Path $root 'tests\data\turn_evidence_runtime.v1.jsonl'
if (-not (Test-Path -LiteralPath $testProject -PathType Leaf)) {
    throw 'The integration test project is missing.'
}
if (-not (Test-Path -LiteralPath $corpus -PathType Leaf)) {
    throw 'The promoted turn-evidence corpus is missing.'
}

$gateWorkParent = Join-Path $productArtifacts 'gate-work'
if (-not (Test-Path -LiteralPath $gateWorkParent -PathType Container)) {
    New-Item -ItemType Directory -Path $gateWorkParent | Out-Null
}
$runRoot = Join-Path $gateWorkParent ('mind-shell-' + [Guid]::NewGuid().ToString('N'))
if (-not (Test-StrictDescendant -Parent $gateWorkParent -Child $runRoot)) {
    throw 'The generated gate work path escaped its owned root.'
}
New-Item -ItemType Directory -Path $runRoot | Out-Null
$testClassName = 'Baxy.Integration.Tests.MindShellEndToEndTests'
$testClassFilter = "FullyQualifiedName~$testClassName"
$physicalTestName =
    "$testClassName.OptInRealRuntimeTraversesShellMindAndCoreUsingReadOnlyOperations"
$selectionTrxName = 'mind-shell-selection.trx'
$selectionTrxPath = Join-Path $runRoot $selectionTrxName
$selectionConsoleLog = Join-Path $runRoot 'dotnet-selection.log'
$trxName = 'mind-shell-e2e.trx'
$trxWorkPath = Join-Path $runRoot $trxName
$trxOutputPath = [IO.Path]::ChangeExtension($OutputPath, '.trx')
$attestationWorkPath = Join-Path $runRoot 'mind-shell-e2e-attestation.json'
$attestationOutputPath = [IO.Path]::ChangeExtension($OutputPath, '.attestation.json')
$consoleLog = Join-Path $runRoot 'dotnet-test.log'

$environmentNames = @(
    'PATH',
    'DOTNET_ROOT',
    'DOTNET_ROOT_X64',
    'BAXY_MIND_PYTHON',
    'BAXY_MIND_PYTHONPATH',
    'BAXY_MIND_LLM_GGUF',
    'BAXY_MIND_LLAMA_SERVER',
    'BAXY_MIND_NGL',
    'BAXY_MIND_STT_DIR',
    'BAXY_MIND_CTX',
    'BAXY_MIND_LLM_REQUEST_TIMEOUT',
    'BAXY_MIND_ROUTER_START_DELAY',
    'BAXY_MIND_TURN_CORPUS',
    'BAXY_MIND_SHELL_E2E_ATTESTATION',
    'BAXY_VOICE_WAKE_ON_START',
    'HF_HUB_OFFLINE'
)
$before = @{}
foreach ($name in $environmentNames) {
    $before[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$startedUtc = [DateTimeOffset]::UtcNow
$stopwatch = [Diagnostics.Stopwatch]::StartNew()
$selectionExitCode = -1
$selectionCounters = $null
$selectionRecords = @()
$selectionPassedTests = @()
$selectionNotExecutedTests = @()
$selectionUnexpectedOutcomes = @()
$expectedTests = @()
$executionExpectedTests = @($physicalTestName)
$actualRecords = @()
$actualTests = @()
$exactTestFilter = $null
$testAssembly = $null
$testAssemblySha256 = $null
$testAssemblyUnchanged = $false
$exitCode = -1
$testOutput = @()
$counters = $null
$failure = $null
try {
    $env:DOTNET_ROOT = $dotnetRoot
    # Generated x64 apphosts consult DOTNET_ROOT_X64 before DOTNET_ROOT.
    # Keep both pinned so baxy-core.exe uses the same reviewed runtime as
    # dotnet test even when the machine has a conflicting system-wide value.
    $env:DOTNET_ROOT_X64 = $dotnetRoot
    $env:PATH = "$dotnetRoot;$env:PATH"
    $env:BAXY_MIND_PYTHON = $python
    $env:BAXY_MIND_PYTHONPATH = $mindPythonPath
    $env:BAXY_MIND_LLM_GGUF = $gguf
    $env:BAXY_MIND_LLAMA_SERVER = $llamaServer
    $env:BAXY_MIND_NGL = if ($Cpu) { '0' } else { [string][int]$runtime.ngl }
    if ($null -ne $runtime.stt_dir -and
        -not [string]::IsNullOrWhiteSpace([string]$runtime.stt_dir)) {
        $sttDirectory = [IO.Path]::GetFullPath([string]$runtime.stt_dir)
        if (Test-Path -LiteralPath $sttDirectory -PathType Container) {
            $env:BAXY_MIND_STT_DIR = $sttDirectory
        }
    }
    $env:BAXY_MIND_CTX = '4096'
    $env:BAXY_MIND_LLM_REQUEST_TIMEOUT = if ($Cpu) { '120' } else { '55' }
    # La certificación ejerce el default productivo del retraso E5 (3 s);
    # el estrés delay=0 es un escenario separado y explícito.
    Remove-Item Env:BAXY_MIND_ROUTER_START_DELAY -ErrorAction SilentlyContinue
    $env:BAXY_MIND_TURN_CORPUS = $corpus
    $env:BAXY_MIND_SHELL_E2E_ATTESTATION = $attestationWorkPath
    $env:BAXY_VOICE_WAKE_ON_START = '0'
    $env:HF_HUB_OFFLINE = '1'

    # Run the reviewed class filter once to prove every ordinary contract case
    # against the compiled assembly. NUnit's Strict ExplicitMode cannot mix an
    # Explicit case with ordinary cases, so the exact-name run below reuses the
    # unchanged assembly and selects only the reviewed physical identity.
    $selectionArguments = @(
        'test',
        $testProject,
        '-c', 'Release',
        '--nologo',
        '-p:NuGetAudit=false',
        '--filter', $testClassFilter,
        '--logger', "trx;LogFileName=$selectionTrxName",
        '--results-directory', $runRoot
    )
    $selectionOutput = @(
        & $dotnet @selectionArguments 2>&1 |
            ForEach-Object { [string]$_ }
    )
    $selectionExitCode = $LASTEXITCODE
    [IO.File]::WriteAllLines(
        $selectionConsoleLog,
        $selectionOutput,
        [Text.UTF8Encoding]::new($false))
    if ($selectionExitCode -ne 0) {
        throw "The selected-test discovery run failed with exit code $selectionExitCode."
    }
    if (-not (Test-Path -LiteralPath $selectionTrxPath -PathType Leaf)) {
        throw 'The selected-test discovery run did not publish a TRX file.'
    }

    [xml]$selectionTrx = Get-Content -LiteralPath $selectionTrxPath -Raw -Encoding UTF8
    $selectionSummary = $selectionTrx.TestRun.ResultSummary
    if ($null -ne $selectionSummary -and $null -ne $selectionSummary.Counters) {
        $selectionCounters = [ordered]@{
            total = [int]$selectionSummary.Counters.total
            executed = [int]$selectionSummary.Counters.executed
            passed = [int]$selectionSummary.Counters.passed
            failed = [int]$selectionSummary.Counters.failed
            error = [int]$selectionSummary.Counters.error
            timeout = [int]$selectionSummary.Counters.timeout
            aborted = [int]$selectionSummary.Counters.aborted
            inconclusive = [int]$selectionSummary.Counters.inconclusive
            not_executed = [int]$selectionSummary.Counters.notExecuted
        }
    }
    $selectionRecords = @(Get-TrxTestRecords -Trx $selectionTrx)
    if ($selectionRecords.Count -eq 0) {
        throw 'The reviewed class filter discovered no tests.'
    }
    if (@(
            $selectionRecords | Where-Object {
                -not [string]::Equals(
                    [string]$_.class_name,
                    $testClassName,
                    [StringComparison]::Ordinal)
            }
        ).Count -ne 0) {
        throw 'The reviewed class filter selected a test outside its exact class.'
    }
    $expectedTests = @(
        $selectionRecords |
            ForEach-Object { [string]$_.fully_qualified_name } |
            Sort-Object -Unique
    )
    if ($expectedTests.Count -ne $selectionRecords.Count) {
        throw 'The reviewed class filter discovered duplicate test identities.'
    }
    if (@(
            $expectedTests | Where-Object {
                $_ -notmatch (
                    '^' + [regex]::Escape($testClassName) +
                    '\.[A-Za-z_][A-Za-z0-9_]*$')
            }
        ).Count -ne 0) {
        throw 'The reviewed class contains a test identity that needs explicit filter review.'
    }
    $physicalSelectionRecords = @(
        $selectionRecords | Where-Object {
            [string]::Equals(
                [string]$_.fully_qualified_name,
                $physicalTestName,
                [StringComparison]::Ordinal)
        }
    )
    if ($physicalSelectionRecords.Count -gt 1 -or
        ($physicalSelectionRecords.Count -eq 1 -and
            -not [string]::Equals(
                [string]$physicalSelectionRecords[0].outcome,
                'NotExecuted',
                [StringComparison]::Ordinal))) {
        throw 'The discovery probe unexpectedly executed or duplicated the Explicit physical test.'
    }
    if ($physicalSelectionRecords.Count -eq 0) {
        # NUnit adapters differ here: some publish an Explicit case as
        # NotExecuted while others omit it from an ordinary class-filter run.
        # The reviewed exact identity is appended in the latter case; the
        # exact-name execution below still has to discover, execute and pass it.
        $expectedTests = @(
            $expectedTests + $physicalTestName | Sort-Object -Unique
        )
    }
    $testAssemblies = @(
        $selectionRecords |
            ForEach-Object { [string]$_.storage } |
            Sort-Object -Unique
    )
    if ($testAssemblies.Count -ne 1 -or
        -not (Test-Path -LiteralPath $testAssemblies[0] -PathType Leaf)) {
        throw 'The selected tests did not resolve to one compiled test assembly.'
    }
    $testAssembly = $testAssemblies[0]
    $testAssemblySha256 = Get-Sha256 -Path $testAssembly
    $exactTestFilter = (
        $executionExpectedTests |
            ForEach-Object { "FullyQualifiedName=$_" }
    ) -join '|'

    $arguments = @(
        'test',
        $testProject,
        '-c', 'Release',
        '--nologo',
        '-p:NuGetAudit=false',
        '--no-build',
        '--filter', $exactTestFilter,
        '--logger', "trx;LogFileName=$trxName",
        '--results-directory', $runRoot
    )
    $testOutput = @(& $dotnet @arguments 2>&1 | ForEach-Object { [string]$_ })
    $exitCode = $LASTEXITCODE
    [IO.File]::WriteAllLines(
        $consoleLog,
        $testOutput,
        [Text.UTF8Encoding]::new($false))

    if (Test-Path -LiteralPath $trxWorkPath -PathType Leaf) {
        [xml]$trx = Get-Content -LiteralPath $trxWorkPath -Raw -Encoding UTF8
        $summary = $trx.TestRun.ResultSummary
        if ($null -ne $summary -and $null -ne $summary.Counters) {
            $counters = [ordered]@{
                total = [int]$summary.Counters.total
                executed = [int]$summary.Counters.executed
                passed = [int]$summary.Counters.passed
                failed = [int]$summary.Counters.failed
                error = [int]$summary.Counters.error
                timeout = [int]$summary.Counters.timeout
                aborted = [int]$summary.Counters.aborted
                inconclusive = [int]$summary.Counters.inconclusive
                not_executed = [int]$summary.Counters.notExecuted
            }
        }
        $actualRecords = @(Get-TrxTestRecords -Trx $trx)
        $actualTests = @(
            $actualRecords |
                ForEach-Object { [string]$_.fully_qualified_name } |
                Sort-Object -Unique
        )
    }
    $testAssemblyUnchanged =
        (Test-Path -LiteralPath $testAssembly -PathType Leaf) -and
        [string]::Equals(
            (Get-Sha256 -Path $testAssembly),
            $testAssemblySha256,
            [StringComparison]::Ordinal)
} catch {
    $failure = $_.Exception.Message
} finally {
    $stopwatch.Stop()
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $before[$name], 'Process')
    }
}

$attestation = $null
$attestationFailure = $null
$journalIntegrityValidated = $false
$journalAttestationValid = $false
$exactReadOnlyCoreOperations = $false
$allCoreResultsCompletedAndVerified = $false
$noCoreEffectMayHaveOccurred = $false
$observedOperations = @()
$operationCounts = [ordered]@{
    'memory.status' = 0
    'system.time' = 0
    'system.status' = 0
    'system.process.list' = 0
    'task.list' = 0
    'note.list' = 0
}
try {
    if (-not (Test-Path -LiteralPath $attestationWorkPath -PathType Leaf)) {
        throw 'The physical test did not publish its authenticated core attestation.'
    }
    if ((Get-Item -LiteralPath $attestationWorkPath -Force).Length -gt 64KB) {
        throw 'The authenticated core attestation exceeds its reviewed size bound.'
    }
    $attestation = Get-Content -LiteralPath $attestationWorkPath -Raw -Encoding UTF8 |
        ConvertFrom-Json -ErrorAction Stop
    $completions = @($attestation.completions)
    $observedOperations = @(
        $completions | ForEach-Object { [string]$_.operation }
    )
    $operationCounts = [ordered]@{
        'memory.status' = @(
            $observedOperations | Where-Object {
                [string]::Equals($_, 'memory.status', [StringComparison]::Ordinal)
            }
        ).Count
        'system.time' = @(
            $observedOperations | Where-Object {
                [string]::Equals($_, 'system.time', [StringComparison]::Ordinal)
            }
        ).Count
        'system.status' = @(
            $observedOperations | Where-Object {
                [string]::Equals($_, 'system.status', [StringComparison]::Ordinal)
            }
        ).Count
        'system.process.list' = @(
            $observedOperations | Where-Object {
                [string]::Equals($_, 'system.process.list', [StringComparison]::Ordinal)
            }
        ).Count
        'task.list' = @(
            $observedOperations | Where-Object {
                [string]::Equals($_, 'task.list', [StringComparison]::Ordinal)
            }
        ).Count
        'note.list' = @(
            $observedOperations | Where-Object {
                [string]::Equals($_, 'note.list', [StringComparison]::Ordinal)
            }
        ).Count
    }
    $exactReadOnlyCoreOperations =
        $completions.Count -eq 15 -and
        $operationCounts['memory.status'] -eq 1 -and
        $operationCounts['system.time'] -eq 5 -and
        $operationCounts['system.status'] -eq 2 -and
        $operationCounts['system.process.list'] -eq 3 -and
        $operationCounts['task.list'] -eq 2 -and
        $operationCounts['note.list'] -eq 2 -and
        @(
            $observedOperations | Where-Object {
                $_ -notin @(
                    'memory.status',
                    'system.time',
                    'system.status',
                    'system.process.list',
                    'task.list',
                    'note.list'
                )
            }
        ).Count -eq 0
    $allCoreResultsCompletedAndVerified =
        $completions.Count -gt 0 -and
        @(
            $completions | Where-Object {
                -not [string]::Equals(
                    [string]$_.status,
                    'completed',
                    [StringComparison]::Ordinal) -or
                $_.verified -ne $true -or
                $_.replayed -ne $false
            }
        ).Count -eq 0
    $noCoreEffectMayHaveOccurred =
        $completions.Count -gt 0 -and
        @(
            $completions | Where-Object {
                $_.effect_may_have_occurred -ne $false
            }
        ).Count -eq 0
    $hashPattern = '^[0-9a-f]{64}$'
    $journalIntegrityValidated =
        [string]::Equals(
            [string]$attestation.schema,
            'baxy-mind-shell-core-attestation-v1',
            [StringComparison]::Ordinal) -and
        $attestation.journal_integrity_validated -eq $true -and
        [string]::Equals(
            [string]$attestation.journal_authentication,
            'hmac-sha256',
            [StringComparison]::Ordinal) -and
        [string]$attestation.journal_sha256 -match $hashPattern -and
        [string]$attestation.anchor_sha256 -match $hashPattern -and
        $attestation.journal_structure_valid -eq $true
    $journalAttestationValid =
        $journalIntegrityValidated -and
        [int]$attestation.journal_records -eq 30 -and
        [int]$attestation.started_records -eq 15 -and
        [int]$attestation.completed_records -eq 15 -and
        $attestation.expected_read_only_operations_observed -eq $true -and
        [int]$attestation.operation_counts.memory_status -eq 1 -and
        [int]$attestation.operation_counts.system_time -eq 5 -and
        [int]$attestation.operation_counts.system_status -eq 2 -and
        [int]$attestation.operation_counts.system_process_list -eq 3 -and
        [int]$attestation.operation_counts.task_list -eq 2 -and
        [int]$attestation.operation_counts.note_list -eq 2 -and
        $exactReadOnlyCoreOperations -and
        $allCoreResultsCompletedAndVerified -and
        $noCoreEffectMayHaveOccurred
} catch {
    $attestationFailure = $_.Exception.Message
    $attestation = $null
    $journalIntegrityValidated = $false
    $journalAttestationValid = $false
    $exactReadOnlyCoreOperations = $false
    $allCoreResultsCompletedAndVerified = $false
    $noCoreEffectMayHaveOccurred = $false
}

$selectionIsComplete = $false
if ($null -ne $selectionCounters -and $expectedTests.Count -gt 0) {
    $selectionPassedTests = @(
        $selectionRecords | Where-Object {
            [string]::Equals(
                [string]$_.outcome,
                'Passed',
                [StringComparison]::Ordinal)
        }
    )
    $selectionNotExecutedTests = @(
        $selectionRecords | Where-Object {
            [string]::Equals(
                [string]$_.outcome,
                'NotExecuted',
                [StringComparison]::Ordinal)
        }
    )
    $selectionUnexpectedOutcomes = @(
        $selectionRecords | Where-Object {
            [string]$_.outcome -notin @('Passed', 'NotExecuted')
        }
    )
    $physicalWasOmitted = @(
        $selectionRecords | Where-Object {
            [string]::Equals(
                [string]$_.fully_qualified_name,
                $physicalTestName,
                [StringComparison]::Ordinal)
        }
    ).Count -eq 0
    $expectedSelectionRecordCount = if ($physicalWasOmitted) {
        $expectedTests.Count - 1
    } else {
        $expectedTests.Count
    }
    $expectedNotExecutedCount = if ($physicalWasOmitted) { 0 } else { 1 }
    $selectionIsComplete =
        $selectionExitCode -eq 0 -and
        $selectionCounters.total -eq $expectedSelectionRecordCount -and
        $selectionRecords.Count -eq $expectedSelectionRecordCount -and
        $selectionPassedTests.Count -eq $selectionCounters.executed -and
        $selectionPassedTests.Count -eq $selectionCounters.passed -and
        $selectionNotExecutedTests.Count -eq $expectedNotExecutedCount -and
        ($physicalWasOmitted -or
            [string]::Equals(
                [string]$selectionNotExecutedTests[0].fully_qualified_name,
                $physicalTestName,
                [StringComparison]::Ordinal)) -and
        $selectionUnexpectedOutcomes.Count -eq 0 -and
        $selectionCounters.failed -eq 0 -and
        $selectionCounters.error -eq 0 -and
        $selectionCounters.timeout -eq 0 -and
        $selectionCounters.aborted -eq 0 -and
        $selectionCounters.inconclusive -eq 0
}
$selectedTestSetMatches = $false
if ($executionExpectedTests.Count -gt 0 -and
    $actualTests.Count -eq $executionExpectedTests.Count) {
    $selectedTestSetMatches =
        @(
            Compare-Object `
                -ReferenceObject $executionExpectedTests `
                -DifferenceObject $actualTests `
                -CaseSensitive
        ).Count -eq 0
}
$allSelectedTestsExecuted = $false
$allSelectedTestsPassed = $false
$noTestFailedOrSkipped = $false
if ($null -ne $counters -and $executionExpectedTests.Count -gt 0) {
    $actualUnexpectedOutcomes = @(
        $actualRecords | Where-Object {
            -not [string]::Equals(
                [string]$_.outcome,
                'Passed',
                [StringComparison]::Ordinal)
        }
    )
    $allSelectedTestsExecuted =
        $counters.total -eq $executionExpectedTests.Count -and
        $counters.executed -eq $executionExpectedTests.Count -and
        $actualRecords.Count -eq $executionExpectedTests.Count
    $allSelectedTestsPassed =
        $counters.passed -eq $executionExpectedTests.Count -and
        $actualUnexpectedOutcomes.Count -eq 0
    $noTestFailedOrSkipped =
        $counters.failed -eq 0 -and
        $counters.error -eq 0 -and
        $counters.timeout -eq 0 -and
        $counters.aborted -eq 0 -and
        $counters.inconclusive -eq 0 -and
        $actualUnexpectedOutcomes.Count -eq 0
}
$checks = [ordered]@{
    selection_probe_exit_zero = $selectionExitCode -eq 0
    selection_probe_complete = $selectionIsComplete
    selected_test_set_matches_execution = $selectedTestSetMatches
    test_assembly_unchanged = $testAssemblyUnchanged
    dotnet_exit_zero = $exitCode -eq 0
    trx_exists = Test-Path -LiteralPath $trxWorkPath -PathType Leaf
    all_selected_tests_executed = $allSelectedTestsExecuted
    all_selected_tests_passed = $allSelectedTestsPassed
    no_test_failed_or_skipped = $noTestFailedOrSkipped
    authenticated_journal_attestation_valid = $journalAttestationValid
    exact_read_only_core_operations = $exactReadOnlyCoreOperations
    all_core_results_completed_and_verified = $allCoreResultsCompletedAndVerified
    no_core_effect_may_have_occurred = $noCoreEffectMayHaveOccurred
}
$passed = @($checks.Values | Where-Object { $_ -ne $true }).Count -eq 0
$gitCommit = ([string](& git -C $root rev-parse HEAD)).Trim().ToLowerInvariant()
$gitDirty = @(& git -C $root status --porcelain=v1 --untracked-files=all).Count -gt 0
$report = [ordered]@{
    schema = 'baxy-mind-shell-e2e-gate-v1'
    status = if ($passed) { 'passed' } else { 'failed' }
    started_utc = $startedUtc.ToString('O')
    completed_utc = [DateTimeOffset]::UtcNow.ToString('O')
    duration_seconds = [math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
    source = [ordered]@{
        commit = $gitCommit
        dirty = $gitDirty
    }
    runtime = [ordered]@{
        manifest_sha256 = Get-Sha256 -Path $RuntimeManifest
        python_sha256 = Get-Sha256 -Path $python
        gguf_name = [IO.Path]::GetFileName($gguf)
        gguf_sha256 = Get-Sha256 -Path $gguf
        llama_server_sha256 = Get-Sha256 -Path $llamaServer
        dotnet_sdk = $sdk.Trim()
        gpu_layers = if ($Cpu) { 0 } else { [int]$runtime.ngl }
        corpus_sha256 = Get-Sha256 -Path $corpus
    }
    boundary = [ordered]@{
        path = 'MainWindowViewModel -> MindSidecarClient -> baxy_mind turn.decide/plan -> CoreProcessClient -> core'
        observed_operations = $observedOperations
        operation_counts = $operationCounts
        external_effects = if ($journalIntegrityValidated) {
            -not $noCoreEffectMayHaveOccurred
        } else {
            $null
        }
        installed_application_launched = if ($journalIntegrityValidated) {
            @(
                $observedOperations | Where-Object {
                    [string]::Equals($_, 'app.open', [StringComparison]::Ordinal)
                }
            ).Count -gt 0
        } else {
            $null
        }
    }
    evidence = [ordered]@{
        attestation_schema = if ($null -ne $attestation) {
            [string]$attestation.schema
        } else {
            $null
        }
        journal_integrity_validated = if ($null -ne $attestation) {
            $journalIntegrityValidated
        } else {
            $false
        }
        journal_authentication = if ($null -ne $attestation) {
            [string]$attestation.journal_authentication
        } else {
            $null
        }
        journal_sha256 = if ($null -ne $attestation) {
            [string]$attestation.journal_sha256
        } else {
            $null
        }
        anchor_sha256 = if ($null -ne $attestation) {
            [string]$attestation.anchor_sha256
        } else {
            $null
        }
        attestation_sha256 = if (
            Test-Path -LiteralPath $attestationWorkPath -PathType Leaf) {
            Get-Sha256 -Path $attestationWorkPath
        } else {
            $null
        }
        failure = $attestationFailure
    }
    test = [ordered]@{
        selection_filter = $testClassFilter
        exact_execution_filter = if ($expectedTests.Count -gt 0) {
            $exactTestFilter
        } else {
            $null
        }
        discovery_expected_tests = $expectedTests
        selected_tests = $executionExpectedTests
        executed_tests = $actualTests
        test_assembly = if ($null -ne $testAssembly) {
            [IO.Path]::GetFileName($testAssembly)
        } else {
            $null
        }
        test_assembly_sha256 = $testAssemblySha256
        selection_exit_code = $selectionExitCode
        selection_counters = $selectionCounters
        selection_result_outcomes = [ordered]@{
            passed = $selectionPassedTests.Count
            not_executed = $selectionNotExecutedTests.Count
            unexpected = $selectionUnexpectedOutcomes.Count
        }
        selection_not_executed_tests = @(
            $selectionNotExecutedTests |
                ForEach-Object { [string]$_.fully_qualified_name }
        )
        exit_code = $exitCode
        counters = $counters
        failure = $failure
    }
    checks = $checks
}

try {
    if (Test-Path -LiteralPath $trxWorkPath -PathType Leaf) {
        $trxTemporary = Join-Path (Split-Path -Parent $trxOutputPath) (
            '.' + [IO.Path]::GetFileName($trxOutputPath) + '.' +
            [Guid]::NewGuid().ToString('N') + '.tmp')
        Copy-Item -LiteralPath $trxWorkPath -Destination $trxTemporary
        Move-AtomicGateFile -Source $trxTemporary -Destination $trxOutputPath
    } elseif (Test-Path -LiteralPath $trxOutputPath -PathType Leaf) {
        Remove-Item -LiteralPath $trxOutputPath -Force
    }
    if (Test-Path -LiteralPath $attestationWorkPath -PathType Leaf) {
        $attestationTemporary = Join-Path (Split-Path -Parent $attestationOutputPath) (
            '.' + [IO.Path]::GetFileName($attestationOutputPath) + '.' +
            [Guid]::NewGuid().ToString('N') + '.tmp')
        Copy-Item -LiteralPath $attestationWorkPath -Destination $attestationTemporary
        Move-AtomicGateFile -Source $attestationTemporary -Destination $attestationOutputPath
    } elseif (Test-Path -LiteralPath $attestationOutputPath -PathType Leaf) {
        Remove-Item -LiteralPath $attestationOutputPath -Force
    }
    Write-JsonAtomic -Path $OutputPath -Value $report
} finally {
    $resolvedRunRoot = [IO.Path]::GetFullPath($runRoot)
    if (-not (Test-StrictDescendant -Parent $gateWorkParent -Child $resolvedRunRoot)) {
        throw 'Refusing to remove an unowned gate work path.'
    }
    if (Test-Path -LiteralPath $resolvedRunRoot -PathType Container) {
        Remove-Item -LiteralPath $resolvedRunRoot -Recurse -Force
    }
}

$report | ConvertTo-Json -Depth 10
if (-not $passed) {
    throw "The real shell/mind/core E2E gate failed. See $OutputPath"
}
