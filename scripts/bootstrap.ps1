[CmdletBinding()]
param(
    [string]$AssetDescriptor,
    [string]$PythonLauncher = 'py',
    [string]$VenvDirectory,
    [switch]$CheckOnly,
    [switch]$Cpu
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Text.UTF8Encoding]::new($false)

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
. (Join-Path $PSScriptRoot 'asset_resolver.ps1')
. (Join-Path $PSScriptRoot 'mind_runtime_manifest.ps1')

if ([string]::IsNullOrWhiteSpace($AssetDescriptor)) {
    $AssetDescriptor = Join-Path $repo 'assets.manifest.json'
}
if ([string]::IsNullOrWhiteSpace($VenvDirectory)) {
    $localData = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::LocalApplicationData)
    if ([string]::IsNullOrWhiteSpace($localData)) {
        throw 'bootstrap_failed: Windows no expuso LocalApplicationData.'
    }
    $VenvDirectory = Join-Path $localData 'BAXYRuntime\python\mind-runtime-v1'
}
$VenvDirectory = [IO.Path]::GetFullPath($VenvDirectory)
$runtimeManifest = Join-Path (
    [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::LocalApplicationData)
    ) 'BAXYRuntime\mind-runtime-v1.json'

function Resolve-BaxyDotnet {
    $candidates = [Collections.Generic.List[string]]::new()
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        $candidates.Add((Join-Path $env:USERPROFILE '.dotnet\dotnet.exe'))
    }
    $candidates.Add((Join-Path (
        [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
        ) '.dotnet\dotnet.exe'))
    $fromPath = Get-Command dotnet -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty Source -First 1
    if (-not [string]::IsNullOrWhiteSpace($fromPath)) {
        $candidates.Add($fromPath)
    }
    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            continue
        }
        $version = [string](& $candidate --version)
        if ($LASTEXITCODE -eq 0 -and $version.Trim() -ceq '10.0.100') {
            return [IO.Path]::GetFullPath($candidate)
        }
    }
    throw ('bootstrap_failed: falta .NET SDK 10.0.100. Se revisaron: ' +
        ($candidates -join '; ') + '. Instalalo desde https://dotnet.microsoft.com/download.')
}

function Show-BaxyAssetResolution {
    param([Parameter(Mandatory = $true)]$Resolution)

    if ($Resolution.Found) {
        Write-Host "  [OK] $($Resolution.Name): $($Resolution.Path)"
        return
    }
    $importance = if ($Resolution.Required) { 'FALTA' } else { 'OPCIONAL' }
    Write-Host "  [$importance] $($Resolution.Name)"
    foreach ($candidate in $Resolution.Candidates) {
        Write-Host "    - $candidate"
    }
    Write-Host "    Como corregirlo: $($Resolution.Repair)"
}

$null = Resolve-BaxyDotnet
$assetNames = @(
    'conversation_model',
    'llama_server',
    'stt_parakeet',
    'stt_nemotron_streaming',
    'wake_manifest',
    'neural_tts_voice',
    'vision_model',
    'mpv',
    'mpv_vulkan',
    'yt_dlp'
)
$resolutions = @{}
Write-Host "Inventario declarativo de activos: $AssetDescriptor"
foreach ($name in $assetNames) {
    $resolution = Resolve-BaxyAsset `
        -Name $name `
        -DescriptorPath $AssetDescriptor `
        -RepositoryRoot $repo
    $resolutions[$name] = $resolution
    Show-BaxyAssetResolution -Resolution $resolution
}
$missingRequired = @($resolutions.Values | Where-Object {
    $_.Required -and -not $_.Found
})

if ($CheckOnly) {
    $runtimeStatus = Get-BaxyMindRuntimeStatus -ManifestPath $runtimeManifest
    if ($missingRequired.Count -eq 0 -and $runtimeStatus.Valid) {
        Write-Host 'BAXY arranca: los activos obligatorios y el runtime registrado son validos.'
        exit 0
    }
    if (-not $runtimeStatus.Valid) {
        Write-Host "Runtime registrado: $($runtimeStatus.Detail)"
    }
    Write-Host 'BAXY no arranca con mente local; corrige los elementos detallados arriba y ejecuta .\scripts\bootstrap.ps1.'
    exit 2
}

$python = Join-Path $VenvDirectory 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    Write-Host "Creando Python 3.12 aislado en: $VenvDirectory"
    & $PythonLauncher -3.12 -m venv $VenvDirectory
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw ('bootstrap_failed: no se pudo crear CPython 3.12 x64. ' +
            'Instalalo desde https://www.python.org/downloads/windows/.')
    }
}

Write-Host 'Fijando pip 26.1.2 e instalando dependencias verificadas por hash...'
& $python -X utf8 -m pip install --disable-pip-version-check `
    --only-binary=:all: 'pip==26.1.2'
if ($LASTEXITCODE -ne 0) {
    throw 'bootstrap_failed: no se pudo fijar pip 26.1.2.'
}
& (Join-Path $PSScriptRoot 'setup_mind_voice.ps1') -Python $python
if ($LASTEXITCODE -ne 0) {
    throw 'bootstrap_failed: no se pudo instalar o verificar el runtime Python.'
}

if ($missingRequired.Count -ne 0) {
    Write-Host 'BAXY no arranca con mente local: faltan activos obligatorios. No se descargo ningun modelo.'
    Write-Host 'Despues de restaurarlos o declararlos en el override local, vuelve a ejecutar .\scripts\bootstrap.ps1.'
    exit 2
}

$registrationArguments = @{
    Python = $python
    PythonPath = (Join-Path $repo 'src')
    Gguf = $resolutions['conversation_model'].Path
    LlamaServer = $resolutions['llama_server'].Path
    SttDirectory = $resolutions['stt_parakeet'].Path
    GpuLayers = if ($Cpu) { 0 } else { 99 }
}
if (-not $resolutions['wake_manifest'].Found) {
    $registrationArguments.NoWake = $true
}
& (Join-Path $PSScriptRoot 'register_mind_runtime.ps1') @registrationArguments
if ($LASTEXITCODE -ne 0) {
    throw 'bootstrap_failed: no se pudo registrar el runtime local.'
}

$status = Get-BaxyMindRuntimeStatus -ManifestPath $runtimeManifest
if (-not $status.Valid) {
    throw "bootstrap_failed: $($status.Code): $($status.Detail)"
}
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $repo 'src'
    & $python -X utf8 -c "import baxy_mind, baxy_mind.voice; print('mind_import_ok')"
    if ($LASTEXITCODE -ne 0) {
        throw 'bootstrap_failed: la mente Python no se pudo importar.'
    }
} finally {
    $env:PYTHONPATH = $previousPythonPath
}

Write-Host 'BAXY arranca: runtime Python, manifiesto y activos obligatorios quedaron verificados.'
Write-Host 'Inicia el producto con: python main.py'
