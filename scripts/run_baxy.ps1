# Lanza BAXY 1.0 con la mente activada (ADR-0005).
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\run_baxy.ps1
#       -SinMente  -> solo el cuerpo determinista
#       -Cpu       -> LLM en CPU puro (sin GPU)
#       -Profile <nombre|ruta> -> raíz de datos (por defecto dev-mente-v2)
#       -UiProbe <turnos.jsonl> -UiCapture <ui-probe.jsonl> -> sonda de la
#           ventana: teclea los turnos en el compositor real y escribe lo que
#           muestra; las auditorías van a la carpeta de la captura.
#           Salidas: 0 cierre done, 3 BAXY ya abierta, 5 sin cierre en la
#           captura, 6 cierre que no es done, 7 tope superado (cerrada por PID).

param(
    [switch]$SinMente,
    [switch]$Cpu,
    # Arranque de comprobación: la ventana teclea estos turnos en su propio
    # compositor y escribe lo que muestra. Sin estos parámetros no cambia nada.
    [string]$UiProbe,
    [string]$UiCapture,
    # Nombre (hija de %LOCALAPPDATA%\BAXY) o ruta de la raíz de datos. Vacío
    # deja la de siempre. Las tandas usan uno propio: dev-mente-v2 es el del dueño.
    [string]$Profile,
    # Tope por turno y ventana de estabilidad de la sonda (0 = los de la sonda).
    [int]$TurnTimeoutMs = 0,
    [int]$StableMs = 0
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

# La instancia única cede en silencio (sale con 0 sin escribir nada): con
# BAXY abierta la sonda daría un falso éxito.
if (-not [string]::IsNullOrWhiteSpace($UiProbe) -and
    @(Get-Process Baxy, baxy-core -ErrorAction SilentlyContinue).Count -gt 0) {
    Write-Host "BAXY ya esta abierta: la sonda no puede arrancar su propia ventana."
    exit 3
}

# Raíz de datos AISLADA para la build de desarrollo (hija directa de
# %LOCALAPPDATA%\BAXY, como exige el core). Protege tus datos BAXY reales:
# la instalación previa creó llaves DPAPI/HMAC propias que esta build no
# debe (ni puede) tocar — sin esto el core se detiene fail-closed con
# ProtectedPayloadException. Es persistente entre lanzamientos.
$devRoot = Join-Path $env:LOCALAPPDATA "BAXY\dev-mente-v2"
if (-not [string]::IsNullOrWhiteSpace($Profile)) {
    $devRoot = if ($Profile -match '[\\/:]') {
        $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Profile)
    } else {
        Join-Path $env:LOCALAPPDATA "BAXY\$Profile"
    }
    $devRoot = $devRoot.TrimEnd('\')
    $baxyRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'BAXY')).TrimEnd('\')
    if ([IO.Path]::GetDirectoryName($devRoot) -ne $baxyRoot) {
        throw "El perfil debe ser hijo directo de $baxyRoot (lo exige el core): $devRoot"
    }
}
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

# Las rutas llevan espacios: sin comillas, -ArgumentList las parte en dos.
$appArguments = @()
if (-not [string]::IsNullOrWhiteSpace($UiProbe)) {
    # La app arranca en su carpeta bin: toda ruta que reciba va absoluta.
    $turnsPath = (Resolve-Path $UiProbe).Path
    if ([string]::IsNullOrWhiteSpace($UiCapture)) {
        $UiCapture = Join-Path (Split-Path $turnsPath) 'ui-probe.jsonl'
    }
    $UiCapture = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($UiCapture)
    $evidence = Split-Path $UiCapture
    if (-not (Test-Path $evidence)) { New-Item -ItemType Directory -Path $evidence -Force | Out-Null }
    Remove-Item $UiCapture -ErrorAction SilentlyContinue

    # Misma instrumentación que scripts/cu_live/cu_live.sh, en la carpeta de la
    # captura; sin palabra de activación para que el micrófono no meta turnos.
    $env:BAXY_VOICE_WAKE_ON_START = "0"
    $env:BAXY_APP_TRACE = Join-Path $evidence 'trace.jsonl'
    $env:BAXY_MIND_MODEL_CALL_AUDIT_PATH = Join-Path $evidence 'model_calls.jsonl'
    $env:BAXY_MIND_LLM_INVALID_JSON_DIR = Join-Path $evidence 'invalid_json'
    $env:BAXY_MIND_RAW_REPLY_AUDIT_PATH = Join-Path $evidence 'raw_replies.jsonl'
    $env:BAXY_MIND_TURN_AUDIT_PATH = Join-Path $evidence 'turn_audit.jsonl'
    $env:BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH = Join-Path $evidence 'compose_audit.jsonl'
    $env:BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT = "1"
    if ([string]::IsNullOrWhiteSpace($env:BAXY_MIND_PYTHONPATH)) {
        # La mente de este checkout, no la que tenga registrada el runtime.
        $env:BAXY_MIND_PYTHONPATH = Join-Path $repo 'src'
    }
    Write-Host "captura: $UiCapture"

    $appArguments += ('"--ui-probe=' + $turnsPath + '"')
    $appArguments += ('"--ui-capture=' + $UiCapture + '"')
    if ($TurnTimeoutMs -gt 0) { $appArguments += "--ui-turn-timeout-ms=$TurnTimeoutMs" }
    if ($StableMs -gt 0) { $appArguments += "--ui-stable-ms=$StableMs" }
}
if ($appArguments.Count -gt 0) {
    # Tope de la sonda entera: arranque (la sonda espera el input hasta 3 min)
    # más, por línea, la espera a una superficie ociosa y el turno, cada una
    # con su tope. Sin él, una sonda colgada dejaría esperando a quien la
    # lanzó (y sin restaurar volumen ni brillo).
    $turnMs = if ($TurnTimeoutMs -gt 0) { [double]$TurnTimeoutMs } else { 240000.0 }
    $lineCount = @(Get-Content $turnsPath -Encoding UTF8 | Where-Object { $_.Trim() }).Count
    $budgetMs = [Math]::Min([double][int]::MaxValue, 360000.0 + $lineCount * (2 * $turnMs + 30000.0))
    $probe = Start-Process -FilePath $app -WorkingDirectory (Split-Path $app) `
        -ArgumentList $appArguments -PassThru
    # Sin tocar Handle, ExitCode puede volver vacío en Windows PowerShell.
    $null = $probe.Handle
    if (-not $probe.WaitForExit([int]$budgetMs)) {
        # Por PID exacto y con su árbol (core, mente): nunca por nombre.
        & taskkill.exe /PID $probe.Id /T /F | Out-Null
        Write-Host ("la sonda supero su tope de {0:n0} s y se cerro (PID {1})" -f ($budgetMs / 1000), $probe.Id)
        exit 7
    }
    if ($probe.ExitCode -ne 0) { exit $probe.ExitCode }
    $terminal = if (Test-Path $UiCapture) {
        Get-Content $UiCapture -Encoding UTF8 | Where-Object { $_ -match '"type":"terminal"' } | Select-Object -Last 1
    }
    if (-not $terminal) {
        Write-Host "la sonda salio sin cierre en la captura: $UiCapture"
        exit 5
    }
    Write-Host $terminal
    if ($terminal -notmatch '"kind":"done"') { exit 6 }
    exit 0
}
Start-Process -FilePath $app -WorkingDirectory (Split-Path $app)
Write-Host "BAXY lanzada."
