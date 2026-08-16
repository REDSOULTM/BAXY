param(
    [string]$Python
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
. (Join-Path $PSScriptRoot 'python_runtime_common.ps1')

$pythonFull = Resolve-BaxyRuntimePython `
    -Candidate $Python `
    -ManifestPath '' `
    -FailurePrefix 'mind_runtime_setup_failed'
Assert-BaxyPythonLockToolchain `
    -Python $pythonFull `
    -WorkingDirectory $repo `
    -FailurePrefix 'mind_runtime_setup_failed'

$lock = Join-Path $repo 'pylock.runtime-win-x64.toml'
$null = Assert-BaxyRuntimeLock `
    -Python $pythonFull `
    -Repository $repo `
    -Profile Runtime `
    -FailurePrefix 'mind_runtime_setup_failed' `
    -StructureOnly
$installation = Invoke-BaxyPythonForOutput `
    -Python $pythonFull `
    -Arguments @(
        '-X',
        'utf8',
        '-m',
        'pip',
        'install',
        '--disable-pip-version-check',
        '--only-binary=:all:',
        '--require-hashes',
        '--no-deps',
        '-r',
        $lock
    ) `
    -WorkingDirectory $repo
if ($installation.ExitCode -ne 0) {
    throw 'mind_runtime_setup_failed: dependency_install'
}
if (-not [string]::IsNullOrWhiteSpace($installation.Text)) {
    Write-Output $installation.Text
}
$null = Assert-BaxyRuntimeLock `
    -Python $pythonFull `
    -Repository $repo `
    -Profile Runtime `
    -FailurePrefix 'mind_runtime_setup_failed'

$probeCode = @'
from baxy_mind.voice import VoiceEngine
import json

probe = VoiceEngine.probe()
print(json.dumps(probe, ensure_ascii=False))
raise SystemExit(0 if probe.get('stt') and probe.get('vad') else 2)
'@
$previousPythonPath = [Environment]::GetEnvironmentVariable(
    'PYTHONPATH',
    [EnvironmentVariableTarget]::Process)
try {
    [Environment]::SetEnvironmentVariable(
        'PYTHONPATH',
        (Join-Path $repo 'src'),
        [EnvironmentVariableTarget]::Process)
    $probe = Invoke-BaxyPythonForOutput `
        -Python $pythonFull `
        -Arguments @('-X', 'utf8', '-c', $probeCode) `
        -WorkingDirectory $repo
} finally {
    [Environment]::SetEnvironmentVariable(
        'PYTHONPATH',
        $previousPythonPath,
        [EnvironmentVariableTarget]::Process)
}
if ($probe.ExitCode -ne 0) {
    throw 'mind_runtime_setup_failed: voice_probe'
}
Write-Output $probe.Text
