param(
    [switch]$Cpu,
    [switch]$NoWake,
    [switch]$ValidateOnly,
    [string]$WakeCandidateManifest
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = $PSScriptRoot
foreach ($required in @('AGENTS.md', 'Baxy.slnx', 'main.py')) {
    if (-not (Test-Path -LiteralPath (Join-Path $repo $required) -PathType Leaf)) {
        throw "Este no es el checkout canonico de BAXY: falta $required en $repo"
    }
}

$runtimeManifest = Join-Path $env:LOCALAPPDATA 'BAXYRuntime\mind-runtime-v1.json'
if (-not (Test-Path -LiteralPath $runtimeManifest -PathType Leaf)) {
    throw "Falta el runtime local de BAXY. Ejecuta .\scripts\bootstrap.ps1 primero."
}

$runtime = Get-Content -LiteralPath $runtimeManifest -Raw | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace([string]$runtime.python)) {
    throw "El runtime registrado no declara el Python aislado de BAXY."
}
$registeredPython = [IO.Path]::GetFullPath([string]$runtime.python)
if (-not (Test-Path -LiteralPath $registeredPython -PathType Leaf)) {
    throw "Falta el Python aislado registrado de BAXY: $registeredPython"
}
if ([string]$runtime.python_sha256 -cnotmatch '^[0-9a-f]{64}$') {
    throw "El runtime registrado no declara un SHA-256 valido para Python."
}
$registeredPythonHash = (
    Get-FileHash -Algorithm SHA256 -LiteralPath $registeredPython
).Hash.ToLowerInvariant()
if ($registeredPythonHash -cne [string]$runtime.python_sha256) {
    throw (
        'El Python aislado registrado de BAXY cambio: SHA-256 inesperado ' +
        $registeredPythonHash)
}
if ([string]::IsNullOrWhiteSpace([string]$runtime.stt_dir)) {
    throw "El runtime registrado no declara el modelo final de transcripcion."
}

$registeredVenv = Split-Path -Parent (Split-Path -Parent $registeredPython)
$registeredSitePackages = Join-Path $registeredVenv 'Lib\site-packages'
if (-not (Test-Path -LiteralPath $registeredSitePackages -PathType Container)) {
    throw "Faltan las dependencias Python registradas de BAXY: $registeredSitePackages"
}
$mvpPythonPath = (Join-Path $repo 'src') + [IO.Path]::PathSeparator + $registeredSitePackages

function Test-BaxyMvpPython {
    param([Parameter(Mandatory = $true)][string]$Candidate)

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
        $env:PYTHONPATH = $mvpPythonPath
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

function Resolve-BaxyMvpPython {
    $candidates = [Collections.Generic.List[string]]::new()
    $candidates.Add($registeredPython)

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
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        $candidates.Add((Join-Path $env:USERPROFILE (
            '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')))
    }
    $candidates.Add((Join-Path $userProfile (
        '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')))

    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (Test-BaxyMvpPython -Candidate $candidate) {
            return [IO.Path]::GetFullPath($candidate)
        }
    }
    throw (
        'No encontre un CPython 3.12 capaz de cargar la mente y la voz de BAXY. ' +
        'Ejecuta .\scripts\bootstrap.ps1 para reparar el runtime aislado.')
}

$python = Resolve-BaxyMvpPython
$pythonHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $python).Hash.ToLowerInvariant()

$runtimeRoot = Split-Path -Parent (
    Split-Path -Parent (
        Split-Path -Parent ([string]$runtime.stt_dir)))
$defaultCandidate = Join-Path $runtimeRoot (
    'experiments\wakeword\baxy_wake_routed_cascade_v25a_endpoint_development\' +
    'baxy-wake-cascade-v2.json')
if ([string]::IsNullOrWhiteSpace($WakeCandidateManifest)) {
    $WakeCandidateManifest = $defaultCandidate
}

$candidateExpectedSha256 = 'a9a3a9fb2a98eee6d903df6afbc59bfa02d0111e9e7bd6de626ade441585001d'
$verdictExpectedSha256 = 'f93d363bca35fc84fee31c08aa5a2a8e31fc7cb5c578cd923747fc61562eff88'
$verdictPath = Join-Path $repo 'artifacts\development\baxy_endpoint_candidate_v25a_opened_verdict_v1.json'

if (-not (Test-Path -LiteralPath $WakeCandidateManifest -PathType Leaf)) {
    throw "Falta la mejor wake word ya medida: $WakeCandidateManifest"
}
if (-not (Test-Path -LiteralPath $verdictPath -PathType Leaf)) {
    throw "Falta la evidencia de la wake word v25a: $verdictPath"
}

$candidateHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $WakeCandidateManifest).Hash.ToLowerInvariant()
$verdictHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $verdictPath).Hash.ToLowerInvariant()
if ($candidateHash -ne $candidateExpectedSha256) {
    throw "La wake word v25a cambio: SHA-256 inesperado $candidateHash"
}
if ($verdictHash -ne $verdictExpectedSha256) {
    throw "La evidencia v25a cambio: SHA-256 inesperado $verdictHash"
}

$verdict = Get-Content -LiteralPath $verdictPath -Raw | ConvertFrom-Json
if (-not $verdict.openedDevelopmentPassed -or
    -not $verdict.developmentOnly -or
    $verdict.promotable -or
    [int]$verdict.metrics.runtimeFalseActivations -ne 0 -or
    [int]$verdict.effectsExecuted -ne 0) {
    throw 'La evidencia v25a no cumple el contrato seguro del MVP.'
}

if ($ValidateOnly) {
    Write-Host (
        'Wake del MVP: identidad v25a verificada como candidata de desarrollo. ' +
        'La prueba fisica v17 fue rechazada (46/48); no esta promovida. El ' +
        'wake_manifest opcional del inventario corresponde al detector historico.')
    Write-Host "Python funcional del MVP: $python (SHA-256 $pythonHash)"
    & (Join-Path $repo 'scripts\bootstrap.ps1') -CheckOnly
    Write-Host (
        'MVP validado: UI/Core, mente, Parakeet y Nemotron disponibles; ' +
        'wake v25a disponible solo como candidata de desarrollo.')
    Write-Host 'No se inicio la aplicacion ni se ejecuto ningun efecto.'
    return
}

$mvpEnvironment = @{
    BAXY_MIND_PYTHON = $python
    BAXY_MIND_PYTHONPATH = $mvpPythonPath
    BAXY_MVP_DEVELOPMENT = '1'
    BAXY_VOICE_LEXICAL_WAKE_FALLBACK = 'off'
    BAXY_VOICE_STREAMING_LANGUAGE = 'auto'
    BAXY_VOICE_STREAMING_STT = 'on'
    BAXY_VOICE_WAKE_CASCADE_ALLOW_UNCALIBRATED = '1'
    BAXY_VOICE_WAKE_CASCADE_MANIFEST = $WakeCandidateManifest
    BAXY_VOICE_WAKE_ON_START = $(if ($NoWake) { '0' } else { '1' })
}
$previousEnvironment = @{}
foreach ($name in $mvpEnvironment.Keys) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    [Environment]::SetEnvironmentVariable($name, [string]$mvpEnvironment[$name], 'Process')
}

$launchExitCode = 0
try {
    Write-Host 'BAXY MVP: UI y mente reales, sin instalar ni tocar la aplicacion instalada.'
    Write-Host 'Voz: wake word v25a + Nemotron parcial + Parakeet final.'
    Write-Warning (
        'La wake word v25a sigue en desarrollo: la prueba fisica v17 fue ' +
        'rechazada con 46/48 positivos y el corpus confusable expuso falsas ' +
        'activaciones. No esta promovida.')
    if ($NoWake) {
        Write-Host 'Microfono automatico desactivado para esta ejecucion.'
    }

    $mainArguments = @()
    if ($Cpu) {
        $mainArguments += '--cpu'
    }
    Push-Location $repo
    try {
        & $python (Join-Path $repo 'main.py') @mainArguments
        $launchExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
finally {
    foreach ($name in $previousEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable(
            $name,
            $previousEnvironment[$name],
            'Process')
    }
}

if ($launchExitCode -ne 0) {
    exit $launchExitCode
}
