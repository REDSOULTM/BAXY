# Una tanda de uso real en la ventana oficial, de punta a punta.
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\uso_real\tanda.ps1 `
#     -Tanda scripts\uso_real\tandas\t1.json [-Out <carpeta>] [-Profile uso-real-v3]
#   powershell -ExecutionPolicy Bypass -File scripts\uso_real\tanda.ps1 `
#     -Tanda scripts\uso_real\tandas\t1.json -Out <carpeta> -SoloInforme
#
# 1. Convierte la tanda al JSONL de la sonda (session.new entre conversaciones).
# 2. Guarda volumen, silencio y brillo; los restaura pase lo que pase.
# 3. Lanza scripts\run_baxy.ps1 -UiProbe con un perfil de prueba propio
#    (nunca dev-mente-v2: es el del dueño) y las auditorías en la carpeta.
# 4. Une respuestas y latencias (conversation.v1.jsonl) en
#    tanda_resultado.jsonl y tanda_resultado.md, listos para puntuar.
# 5. Cierra lo que la tanda abrió (scripts\cu_live\libro_lote.ps1: foto antes,
#    cierre por PID exacto después, releído) y avisa si el navegador del
#    dueño cambió; nunca toca lo que ya estaba abierto. -SinCierre lo omite.
# -SoloInforme rehace sólo el paso 4 con la captura que ya está en -Out.
# Requiere la build Release de este checkout (dotnet build src\Baxy.App -c Release;
# dotnet publish src\Baxy.Core -c Release -r win-x64) y BAXY cerrada.

param(
    [Parameter(Mandatory = $true)][string]$Tanda,
    [string]$Out,
    [string]$Profile = 'uso-real-v3',
    [int]$TurnTimeoutMs = 0,
    [int]$StableMs = 0,
    [switch]$SoloInforme,
    [switch]$SinCierre
)

$ErrorActionPreference = 'Stop'
$scripts = Split-Path -Parent $PSScriptRoot
$repo = Split-Path -Parent $scripts
$driver = Join-Path $PSScriptRoot 'tanda_driver.py'
$stateScript = Join-Path $scripts 'semantic_replay_state.ps1'

$python = Join-Path $env:LOCALAPPDATA 'BAXYRuntime\python\mind-runtime-v1\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

if ($Profile -match '(^|[\\/])dev-mente-v2[\\/]?$') {
    throw 'dev-mente-v2 es el perfil vivo del dueno: las tandas usan uno propio.'
}
$profileRoot = if ($Profile -match '[\\/:]') {
    $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Profile).TrimEnd('\')
} else {
    Join-Path $env:LOCALAPPDATA "BAXY\$Profile"
}

$tandaPath = (Resolve-Path $Tanda).Path
$name = [IO.Path]::GetFileNameWithoutExtension($tandaPath)
if ([string]::IsNullOrWhiteSpace($Out)) {
    $Out = Join-Path $env:LOCALAPPDATA ("BAXY\uso-real-v3-evidencia\{0}-{1}" -f $name, (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
$Out = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Out)
New-Item -ItemType Directory -Path $Out -Force | Out-Null
$turns = Join-Path $Out 'turnos.jsonl'
$capture = Join-Path $Out 'ui-probe.jsonl'
$sinceFile = Join-Path $Out 'desde_utc.txt'
$conversationLog = Join-Path $profileRoot 'conversation\conversation.v1.jsonl'
$libro = Join-Path $scripts 'cu_live\libro_lote.ps1'
$fotoTanda = Join-Path $Out 'libro_foto.json'

function Invoke-Driver {
    param([string[]]$Arguments)
    & $python -X utf8 $driver @Arguments
    if ($LASTEXITCODE -ne 0) { throw "tanda_driver.py $($Arguments[0]) salio con $LASTEXITCODE" }
}

function Write-Report {
    # PowerShell 5.1 descarta un argumento vacio al llamar a un ejecutable: '-' es sin filtro.
    $since = if (Test-Path $sinceFile) { (Get-Content $sinceFile -Raw).Trim() } else { '-' }
    Invoke-Driver @('report', $tandaPath, $capture, $conversationLog, $since, $Out)
    Write-Host "informe: $(Join-Path $Out 'tanda_resultado.md')"
}

if ($SoloInforme) {
    Write-Report
    exit 0
}

Invoke-Driver @('convert', $tandaPath, $turns)

function Get-MachineState {
    $volume = & powershell -NoProfile -ExecutionPolicy Bypass -File $stateScript volume get | ConvertFrom-Json
    $brightness = & powershell -NoProfile -ExecutionPolicy Bypass -File $stateScript brightness get | ConvertFrom-Json
    [pscustomobject]@{ Volume = $volume; Brightness = @($brightness.levels) }
}

$before = Get-MachineState
$before | ConvertTo-Json -Compress -Depth 4 | Set-Content (Join-Path $Out 'estado_antes.json') -Encoding ascii
Write-Host "estado antes: volumen $($before.Volume.level) silencio $($before.Volume.muted) brillo $($before.Brightness -join ',')"

# Foto de todo lo abierto antes de la tanda: es del dueño y no se toca.
# Registro del input del dueno durante TODA la tanda (cu_live\registro_dueno.py), empezado antes de la foto: el libro
# solo da por quieto al dueno donde este registro cubre; sin el, nada que pueda ser suyo se cierra.
$registro = Join-Path $Out 'registro_dueno.json'
$registroParar = "$registro.parar"
$registroProc = $null
if (-not $SinCierre) {
    Remove-Item -LiteralPath $registro, $registroParar -ErrorAction SilentlyContinue
    $argsRegistro = @('-3.12', ('"{0}"' -f (Join-Path $scripts 'cu_live\registro_dueno.py')), '--salida', ('"{0}"' -f $registro),
        '--raiz', $PID, '--parar', ('"{0}"' -f $registroParar))
    $registroProc = Start-Process -FilePath 'py' -ArgumentList $argsRegistro -WindowStyle Hidden -PassThru
    $limite = (Get-Date).AddSeconds(30)
    while (-not (Test-Path $registro) -and (Get-Date) -lt $limite) { Start-Sleep -Milliseconds 200 }
    if (Test-Path $registro) { Start-Sleep -Seconds 3; $env:CU_REGISTRO = $registro }
    else { Write-Host 'AVISO: sin registro del dueno: el cierre lo tratara como activo (no cierra nada suyo)' }
    # Lo que un caso o una tanda anterior dejo abierto y el libro de procesos del arnes prueba suyo se cierra antes de
    # la foto (cu_live\estado\sin_restos.ps1); si no, entraria en la foto como del dueno.
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $scripts 'cu_live\estado\base.ps1') -Estados sin_restos | Write-Host
    & powershell -NoProfile -ExecutionPolicy Bypass -File $libro -Foto -Libro $fotoTanda | Out-Null
}

$code = 1
try {
    [DateTime]::UtcNow.ToString('o') | Set-Content $sinceFile -Encoding ascii
    # Owner order (2026-10-10): every test runs in bypass mode (the Core rereads it from the profile each invocation).
    New-Item -ItemType Directory -Force $profileRoot | Out-Null
    [IO.File]::WriteAllText((Join-Path $profileRoot 'confirmation-mode'), 'bypass')
    $arguments = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', (Join-Path $scripts 'run_baxy.ps1'),
        '-Profile', $profileRoot,
        '-UiProbe', $turns,
        '-UiCapture', $capture
    )
    if ($TurnTimeoutMs -gt 0) { $arguments += @('-TurnTimeoutMs', $TurnTimeoutMs) }
    if ($StableMs -gt 0) { $arguments += @('-StableMs', $StableMs) }
    $started = Get-Date
    & powershell @arguments
    $code = $LASTEXITCODE
    Write-Host ("sonda: salida {0} en {1:n0} s" -f $code, ((Get-Date) - $started).TotalSeconds)
}
finally {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $stateScript volume set ([int]$before.Volume.level) | Out-Null
    & powershell -NoProfile -ExecutionPolicy Bypass -File $stateScript volume mute ([int][bool]$before.Volume.muted) | Out-Null
    if ($before.Brightness.Count -gt 0) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $stateScript brightness set ([int]$before.Brightness[0]) | Out-Null
    }
    $after = Get-MachineState
    Write-Host "estado restaurado: volumen $($after.Volume.level) silencio $($after.Volume.muted) brillo $($after.Brightness -join ',')"
    # Lo que la tanda abrió (apps de las misiones: Office, Edge, Paint, Spotify, Bloc de notas...) se cierra por PID
    # exacto y se relee; las pestañas nuevas del navegador del dueño sólo se avisan.
    if (-not $SinCierre -and (Test-Path $fotoTanda)) {
        # El diario de misiones del perfil de la tanda: una ventana nueva en un proceso del dueno solo se cierra donde
        # BAXY trabajo (un recordatorio o una llamada que la app abrio sola no se toca).
        $cierre = & powershell -NoProfile -ExecutionPolicy Bypass -File $libro -Cerrar -Libro $fotoTanda -Journal (Join-Path $profileRoot 'journal\missions.jsonl')
        $cierre | Set-Content (Join-Path $Out 'libro_cierre.jsonl') -Encoding ascii
        Write-Host "cierre: $cierre"
        if ($cierre -match '"verificado":false') { Write-Host 'AVISO: la tanda dejo algo abierto (ver sobreviven)' }
        if ($cierre -match 'navegador_del_dueno') { Write-Host 'AVISO: el navegador del dueno cambio durante la tanda (no se toca)' }
        if ($cierre -match 'sin_procedencia') { Write-Host 'AVISO: algo nacio durante la tanda sin procedencia de BAXY (no se cierra; ver avisos)' }
    }
    if ($registroProc) {
        New-Item -ItemType File -Path $registroParar -Force | Out-Null
        [void]$registroProc.WaitForExit(5000)
    }
}

Write-Report
exit $code
