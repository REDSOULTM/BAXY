---
name: debug-app-crash
description: Investigate why an app crashed, froze, or won't respond. Checks process status, event logs, system resources, and recent files. Use when user reports "X se colgó", "X dejó de responder", "X tira error".
priority: medium
requires:
  os: [windows]
---

# Debug app crash

**Tools used**: `window`, `system`, `maintenance`, `filesystem`, `verify`.
**Honesty-critical**: yes — no inventar causas; solo reportar lo medido.

## Cuándo usar este skill

El usuario dice:
- "<app> se colgó"
- "<app> dejó de responder"
- "<app> tira error"
- "por qué crasheó X"
- "<app> no abre"

NO usar para "<app> está lenta" (eso es performance, no crash) — para
performance usar el skill o `system(action="cpu_ram_gpu")` directo.

## Steps

### 1. Verificar estado actual del proceso

```
verify(action="app_opened", name="<app>")
```

Tres outcomes posibles:
- **found=True con ventana visible**: la app está corriendo. Quizás
  solo está unresponsive. Ir a step 2.
- **found=True sin ventana**: corre en background. Posible UI freeze.
  Ir a step 2.
- **found=False**: la app NO está corriendo. Crasheó o nunca abrió.
  Saltar a step 4.

### 2. Si está corriendo: chequear unresponsive

```
window(action="list")
```

Buscar la ventana de la app. Si está en la lista pero título dice
"(Not Responding)" o "(No responde)", el LLM debe decirle al usuario
que la opción honest es:
- Esperar (a veces vuelve).
- `app(action="close")` que intenta close gracefully (WM_CLOSE).
- Si no responde, `terminal(action="run", command="taskkill", args=["/F", "/IM", "<exe>"])`.

**Aplicar safety**: taskkill /F requiere confirmación si la tool de
terminal está marcada destructive en el registry.

### 3. Recursos del sistema (chequeo rápido)

```
system(action="cpu_ram_gpu")
```

Si:
- CPU > 95% → algún proceso (puede ser el de la app) está pegando el CPU.
- RAM > 95% → memory pressure; la app puede estar swapping a disco.
- GPU > 95% → si la app usa GPU (gaming, render).

Reportar números reales. NO inventar "tu RAM está alta" si la tool
no lo midió.

### 4. Si NO está corriendo: buscar evidencia de crash

#### 4a. Event Viewer

```
maintenance(action="event_logs_query", log="Application", hours=2, limit=20, level=2)
```

Level=2 = Error. Filtrar por nombre del exe en `ProviderName` o
`Message`. Si hay crash event:
- Reportar timestamp, exit code (si está), faulting module.

#### 4b. Windows Error Reporting (WER) dumps

```
filesystem(action="search",
           root="C:/ProgramData/Microsoft/Windows/WER/ReportArchive",
           pattern="*<app>*",
           budget_s=5)
```

Si encuentra dumps recientes (`<24h`), reportar paths.

#### 4c. Logs propios de la app (best-effort)

Apps comunes guardan logs en:
- `%LOCALAPPDATA%/<app>/logs/`
- `%APPDATA%/<app>/logs/`
- `%USERPROFILE%/Documents/<app>/logs/`

```
filesystem(action="search",
           root="%LOCALAPPDATA%/<app>",
           pattern="*.log",
           budget_s=3)
```

Si hay logs recientes, listar los últimos modificados (no leerlos
todos automáticamente — son grandes y el LLM no necesita el contenido
salvo que el usuario lo pida).

### 5. Reportar diagnóstico

Estructura del reply:

> "Estado de `<app>`:
> - Proceso: [corriendo / no corriendo / unresponsive]
> - Última actividad: [timestamp del último log o crash event]
> - CPU/RAM/GPU al momento de crash (si medido): [valores]
> - Evidence: [Event Viewer entry / WER dump / logs paths]
>
> **Hipótesis** (no certeza): [solo si la evidencia apunta claramente].
> **Próximo paso sugerido**: [restart app / reportar a soporte / chequear updates / etc]."

## Outcomes honestos

| Estado | Cómo reportar |
|---|---|
| App corriendo + unresponsive identificada | "`<app>` está corriendo pero la ventana dice 'No Responde'. ¿La cierro?" |
| App crasheó + Event Viewer tiene crash event | "Encontré un crash event a las HH:MM. Module: <X>. Probablemente <razón>." |
| App crasheó + sin evidencia clara | "`<app>` no está corriendo. No encontré crash events recientes ni WER dumps. ¿Cuándo dejó de funcionar?" |
| Sin permisos para Event Viewer | "Event Viewer requiere permisos elevados. Probá correr el agente como admin, o decime qué pasó cuando crasheó y vemos otras pistas." |
| App existe pero nunca crasheó (interpretation error) | "`<app>` está corriendo normal y no veo crash events. ¿Qué te hizo pensar que crasheó?" |

## Anti-patterns

- ❌ Inventar causas ("probablemente fue Windows Update") sin evidencia
  de un crash event que lo respalde.
- ❌ Saltar directo a "reinstalá la app" como solución sin diagnóstico.
- ❌ Asumir que un alto CPU = causa del crash (correlación ≠ causa).
- ❌ Leer logs gigantes (>1MB) automáticamente — listar paths y pedir al
  usuario qué quiere inspeccionar.
- ❌ Recomendar `taskkill /F` sin advertir que se pierde estado no guardado.
