# schedule_upstream_check.ps1
# Registra una tarea semanal en Windows Task Scheduler que ejecuta
# `python audit/check_upstream_prs.py` y deja log en audit/upstream_check_cron.log
#
# Uso (desde PowerShell con permisos de usuario, NO requiere admin):
#   .\audit\schedule_upstream_check.ps1                 # registra/actualiza
#   .\audit\schedule_upstream_check.ps1 -Unregister     # elimina la tarea
#
# La tarea corre:
#   - Cada lunes a las 09:00 hora local
#   - Solo si el equipo esta encendido (sin wake-up)
#   - Si se perdio (laptop apagada), se ejecuta al proximo boot dentro de la semana

param(
    [switch]$Unregister
)

$TaskName    = "Gemma4Agent-WeeklyUpstreamCheck"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ScriptPath  = Join-Path $ProjectRoot "audit\check_upstream_prs.py"
$LogPath     = Join-Path $ProjectRoot "audit\upstream_check_cron.log"

if ($Unregister) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Output "Tarea '$TaskName' eliminada."
    } else {
        Write-Output "Tarea '$TaskName' no existe — nada que hacer."
    }
    exit 0
}

# Resolver python (preferir el que esta en PATH; si hay venv en .venv, usarlo)
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
    Write-Output "Usando venv: $PythonExe"
} else {
    $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $PythonExe) {
        Write-Error "No se encontro 'python' en PATH ni venv en .venv\"
        exit 1
    }
    Write-Output "Usando python del sistema: $PythonExe"
}

if (-not (Test-Path $ScriptPath)) {
    Write-Error "No se encontro el script: $ScriptPath"
    exit 1
}

# Comando: redirige stdout+stderr al log con timestamp, sin sobreescribir
$Cmd = "& '$PythonExe' '$ScriptPath' *>> '$LogPath'"
$WrappedCmd = "Set-Location '$ProjectRoot'; Write-Output \"=== Run $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===\" *>> '$LogPath'; $Cmd"

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"$WrappedCmd`""

# Lunes 09:00, repetir cada semana
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 09:00

# Si la PC estaba apagada, ejecutar al boot dentro de la ventana semanal
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

# Correr como el usuario actual, sin elevacion
$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

$Task = New-ScheduledTask `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Gemma 4 Agent: chequeo semanal de PRs/issues upstream relevantes (llama.cpp). Log: audit/upstream_check_cron.log"

# Register / Update
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Set-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings
    Write-Output "Tarea '$TaskName' actualizada."
} else {
    Register-ScheduledTask -TaskName $TaskName -InputObject $Task | Out-Null
    Write-Output "Tarea '$TaskName' registrada."
}

Write-Output ""
Write-Output "Detalles:"
Write-Output "  Comando : $PythonExe $ScriptPath"
Write-Output "  Trigger : Lunes 09:00 (semanal)"
Write-Output "  Log     : $LogPath"
Write-Output ""
Write-Output "Inspeccionar con:"
Write-Output "  Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
Write-Output ""
Write-Output "Probar manualmente (sin esperar al lunes):"
Write-Output "  Start-ScheduledTask -TaskName '$TaskName'"
