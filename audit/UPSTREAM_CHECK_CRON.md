# Cron upstream check — setup

`audit/schedule_upstream_check.ps1` registra una tarea semanal en Windows Task
Scheduler que ejecuta `python audit/check_upstream_prs.py` los lunes a las 09:00.

## Registrar / actualizar

```powershell
# Desde la raiz del repo, en PowerShell (NO requiere admin)
.\audit\schedule_upstream_check.ps1
```

El script detecta automaticamente:
- `.venv\Scripts\python.exe` si existe (preferido)
- caso contrario `python` en PATH

## Inspeccionar

```powershell
Get-ScheduledTask -TaskName 'Gemma4Agent-WeeklyUpstreamCheck' | Get-ScheduledTaskInfo
```

## Probar manualmente

```powershell
Start-ScheduledTask -TaskName 'Gemma4Agent-WeeklyUpstreamCheck'
# Salida en audit/upstream_check_cron.log
```

## Eliminar

```powershell
.\audit\schedule_upstream_check.ps1 -Unregister
```

## Notas

- La tarea corre con permisos limitados del usuario actual (sin elevacion).
- Si la laptop estaba apagada el lunes 09:00, la tarea se dispara al proximo
  boot dentro de la ventana semanal (`StartWhenAvailable`).
- Limite de ejecucion: 10 minutos (suficiente; el script suele tardar <30s).
- Log acumulativo en `audit/upstream_check_cron.log` (no rota — limpiar
  manualmente cuando crezca).
