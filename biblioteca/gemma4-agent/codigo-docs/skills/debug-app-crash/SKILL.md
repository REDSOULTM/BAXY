---
name: debug-app-crash
description: Investigate why an app crashed, froze, or won't respond. Checks process status, event logs, system resources, and recent files. Use when user reports "X se colgó", "X dejó de responder", "X tira error".
priority: medium
metadata:
  examples:
    - "mi app se colgó, diagnosticá por qué"
    - "el programa dejó de responder, qué pasó"
    - "esta aplicación tira error, averiguá la causa"
    - "se me crasheó el programa, ayudame a diagnosticar"
    - "this app crashed, help me debug why"
    - "o aplicativo travou, descubra o porquê"
requires:
  os: [windows]
---

# Debug app crash

Tools: `window`, `system`, `maintenance`, `filesystem`, `verify`. Honesty-critical: SÍ — no inventar causas; solo reportar lo medido.

Usar cuando: "<app> se colgó / dejó de responder / tira error / no abre", "por qué crasheó X". NO usar para "<app> está lenta" (eso es performance → usar `system(action="cpu_ram_gpu")` directo).

## Steps

1. **Estado actual del proceso.** `verify(action="app_opened", name="<app>")`. Outcomes:
   - `found=True` con ventana visible → corre, quizás unresponsive → step 2.
   - `found=True` sin ventana → background, posible UI freeze → step 2.
   - `found=False` → NO corre, crasheó o nunca abrió → step 4.
2. **Si corre: chequear unresponsive.** `window(action="list")`. Buscar la ventana; si dice "(Not Responding)"/"(No responde)", decir al usuario que las opciones honestas son: esperar (a veces vuelve); `app(action="close")` (WM_CLOSE gracefully); si no responde, `terminal(action="run", command="taskkill", args=["/F", "/IM", "<exe>"])`. **Safety**: taskkill /F requiere confirmación si terminal está marcada destructive en el registry.
3. **Recursos del sistema.** `system(action="cpu_ram_gpu")`. CPU>95% → algún proceso pega el CPU; RAM>95% → memory pressure / swapping; GPU>95% → si la app usa GPU. Reportar números reales; NO inventar "tu RAM está alta" si no se midió.
4. **Si NO corre: buscar evidencia de crash.**
   - 4a. Event Viewer: `maintenance(action="event_logs_query", log="Application", hours=2, limit=20, level=2)` (level 2=Error). Filtrar por exe en `ProviderName`/`Message`. Si hay crash event: reportar timestamp, exit code, faulting module.
   - 4b. WER dumps: `filesystem(action="search", root="C:/ProgramData/Microsoft/Windows/WER/ReportArchive", pattern="*<app>*", budget_s=5)`. Si hay dumps <24h, reportar paths.
   - 4c. Logs de la app (best-effort) en `%LOCALAPPDATA%/<app>/logs/`, `%APPDATA%/<app>/logs/`, `%USERPROFILE%/Documents/<app>/logs/`: `filesystem(action="search", root="%LOCALAPPDATA%/<app>", pattern="*.log", budget_s=3)`. Listar últimos modificados; NO leerlos todos (son grandes; solo si el usuario lo pide).
5. **Reportar diagnóstico.** "Estado de `<app>`: Proceso [corriendo/no corriendo/unresponsive]; Última actividad [timestamp último log o crash event]; CPU/RAM/GPU al crash (si medido); Evidence [Event Viewer / WER dump / logs paths]. **Hipótesis** (no certeza): solo si la evidencia apunta claramente. **Próximo paso**: restart / soporte / updates / etc."

## Outcomes honestos

| Estado | Cómo reportar |
|---|---|
| App corriendo + unresponsive identificada | "`<app>` está corriendo pero la ventana dice 'No Responde'. ¿La cierro?" |
| App crasheó + Event Viewer tiene crash event | "Encontré un crash event a las HH:MM. Module: <X>. Probablemente <razón>." |
| App crasheó + sin evidencia clara | "`<app>` no está corriendo. No encontré crash events recientes ni WER dumps. ¿Cuándo dejó de funcionar?" |
| Sin permisos para Event Viewer | "Event Viewer requiere permisos elevados. Probá correr el agente como admin, o decime qué pasó cuando crasheó y vemos otras pistas." |
| App existe pero nunca crasheó (interpretation error) | "`<app>` está corriendo normal y no veo crash events. ¿Qué te hizo pensar que crasheó?" |

## Anti-patterns

- ❌ Inventar causas ("probablemente fue Windows Update") sin un crash event que lo respalde.
- ❌ Saltar directo a "reinstalá la app" sin diagnóstico.
- ❌ Asumir que alto CPU = causa del crash (correlación ≠ causa).
- ❌ Leer logs gigantes (>1MB) automáticamente — listar paths y pedir qué inspeccionar.
- ❌ Recomendar `taskkill /F` sin advertir que se pierde estado no guardado.
