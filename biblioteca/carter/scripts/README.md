# scripts/

Scripts de utilidad para Carter v4.

## Scheduled Task: llama-server al login

Para que llama-server con Gemma 4 arranque automáticamente al iniciar sesión:

```powershell
# Instalar
.\install_llama_service.ps1

# Arrancar AHORA sin reloguear
Start-ScheduledTask -TaskName CarterLlamaServer

# Verificar
Get-ScheduledTask -TaskName CarterLlamaServer
curl http://127.0.0.1:8080/health

# Desinstalar
.\uninstall_llama_service.ps1
```

**No requiere admin.** Usa Windows Task Scheduler corriendo con el user actual.

**Logs**: `%LOCALAPPDATA%\Carter\logs\server_*.log` (mantiene los 5 más recientes).

**Comportamiento**:
- Al login: arranca llama-server si el puerto 8080 está libre
- Si ya hay algo en :8080: no arranca duplicado, deja una línea de log y termina
- Si llama-server crashea: Windows reintenta hasta 3 veces con 5 min de intervalo

## Scripts del proyecto

Otros scripts útiles en `Carter_v4/scripts/`:
- `smoke_gemma.py` — smoke test del adapter Gemma 4 (3 probes)
- `minimum_test_gemma.py` — 10 prompts del Contrato sobre el Agent real
