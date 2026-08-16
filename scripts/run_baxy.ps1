# Lanza BAXY 1.0 con la mente activada (ADR-0005).
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\run_baxy.ps1
#       -SinMente  -> solo el cuerpo determinista
#       -Cpu       -> LLM en CPU puro (sin GPU)

param(
    [switch]$SinMente,
    [switch]$Cpu
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'build_layout.ps1')
$layout = Get-BaxyBuildLayout -RepositoryRoot $repo

$app = $layout.AppExecutable
$core = $layout.CorePublishExecutable
if (-not (Test-Path $app)) {
    throw "Falta Baxy.exe. Compila con: dotnet build src\Baxy.App -c $($layout.DevelopmentConfiguration)"
}
if (-not (Test-Path $core)) {
    throw "Falta baxy-core.exe. Publica con: dotnet publish src\Baxy.Core -c $($layout.DevelopmentConfiguration) -r $($layout.RuntimeIdentifier)"
}

# Raíz de datos AISLADA para la build de desarrollo (hija directa de
# %LOCALAPPDATA%\BAXY, como exige el core). Protege tus datos BAXY reales:
# la instalación previa creó llaves DPAPI/HMAC propias que esta build no
# debe (ni puede) tocar — sin esto el core se detiene fail-closed con
# ProtectedPayloadException. Es persistente entre lanzamientos.
$devRoot = Join-Path $env:LOCALAPPDATA "BAXY\dev-mente-v2"
if (-not (Test-Path $devRoot)) { New-Item -ItemType Directory -Path $devRoot -Force | Out-Null }
$env:BAXY_DATA_DIR = $devRoot
Write-Host "datos (aislados): $devRoot"

# El shell busca baxy-core.exe junto a la app; se copia solo si cambió.
$coreTarget = Join-Path (Split-Path $app) "baxy-core.exe"
if (-not (Test-Path $coreTarget) -or
    (Get-Item $core).LastWriteTimeUtc -gt (Get-Item $coreTarget).LastWriteTimeUtc) {
    Copy-Item $core $coreTarget -Force
    Write-Host "core actualizado junto a la app"
}

if ($SinMente) {
    $env:BAXY_MIND_DISABLED = "1"
    @(
        "BAXY_MIND_PYTHON",
        "BAXY_MIND_PYTHONPATH",
        "BAXY_MIND_LLM_GGUF",
        "BAXY_MIND_LLAMA_SERVER",
        "BAXY_MIND_STT_DIR",
        "BAXY_MIND_NGL",
        "BAXY_VOICE_WAKE_ON_START",
        "BAXY_ASSET_DESCRIPTOR"
    ) | ForEach-Object {
        Remove-Item "Env:$_" -ErrorAction SilentlyContinue
    }
    Write-Host "BAXY sin mente (cuerpo determinista puro)"
} else {
    $runtimeManifest = Join-Path $env:LOCALAPPDATA 'BAXYRuntime\mind-runtime-v1.json'
    Remove-Item Env:BAXY_MIND_DISABLED -ErrorAction SilentlyContinue
    $env:BAXY_ASSET_DESCRIPTOR = Join-Path $repo 'assets.manifest.json'
    if ($Cpu) {
        $env:BAXY_MIND_NGL = "0"
    }
    Write-Host ("BAXY comprobará la mente local en la app " +
        "$(if ($Cpu) {'(CPU puro)'} else {'(configuración local)'})")
    Write-Host "Runtime registrado pendiente de verificación SHA-256: $runtimeManifest"
}

Start-Process -FilePath $app -WorkingDirectory (Split-Path $app)
Write-Host "BAXY lanzada."
