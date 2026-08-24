# Handoff — Goal 10 — 2026-08-24 — `5b65951`

## Objetivo
BAXY se usa en una dosis real concentrada, no miente, se queda encendido barato, y eso queda en `origin/main`.

## Estado
Hecho:
- Identidad leída. Journal: `%LOCALAPPDATA%\BAXY\dev-mente-v2\journal\missions.jsonl`. Idle goal 09: `artifacts/goal09/idle_listen.json` (RSS 1088 MB, llama-server off, GPU 510/16380).
- **No había bandeja ni autostart.** Ahora sí, en `origin/main`.
- **El panel de memoria era un stub** (`private_memory_requires_chat`). Ahora GET/POST/DELETE pegan al almacén real.
- El input de Field UI salía `enabled=false` tras `startup.ready`: el welcome se encola a la mente, `IsBusy=true`, y eso cerraba el teclado. Arreglado.
- Tres commits en `origin/main` (`rev-list origin/main..main` = 0).

En curso: **el primer `py main.py` + turno real todavía no cerró**. Último intento (post-`5b65951`) seguía compilando/lanzando al cortar. **No hay soak de 24 h arrancado.** No hay dosis.

Sin empezar: launch ×2 verificado, sampler idle, 200 turnos / 5×20, modos+narración+memoria+web.search en el producto vivo, reboot Windows, idle final, costuras, APLAZADOS de uso, compuerta Full.

## Commits ya en origin/main
1. `77537bf` — bandeja, `HKCU\...\Run\BAXY` → `"Baxy.exe" --tray`, X oculta, 2ª instancia muestra la 1ª, panel de memoria real, `py main.py` mata si CloseMainWindow sólo oculta.
2. `e787281` — `IsInputEnabled => IsReady && !_turnExecutionActive` (ya no `!IsBusy`). `/agent/status.ready` = `IsInputEnabled`. Test de hora alineado a hechos JSON (Bypass de tests).
3. `5b65951` — **el WS `AgentEvent.ready` también era `IsReady && !IsBusy`** y pisa el poll de `/agent/status`. Ahora `IsInputEnabled`. **Sin este commit el input sigue disabled.**

## Decisiones — no reabrir sin dato nuevo
- WinForms `NotifyIcon` con `UseWindowsForms=true` **y** `<Using Remove="System.Drawing"/>` + `System.Windows.Forms`. Si no, CS0104 en todo WPF (`Brush`, `Application`, `Size`).
- Panel de memoria: el `window.confirm` del Field **es** la confirmación de esa invocación. Core pide token; `MemoryPanelBridge` lo reenvía. Enable va por `memory.configure`, no `memory.enable` (el parser no admite el nombre de cable).
- Edit del mismo `key` = `memory.correct`; alta = `memory.save` kind `preference`.
- `py main.py` / `CloseMainWindow`: si sólo oculta, `Stop-Process -Force` a los 3 s. Si no, el mutex cede y no relanzas.
- Test `NaturalTimeQueryReturnsVerifiedLocalTimeUnderFourSeconds` esperaba prosa «La fecha local es…» con `BypassLlmCompositionForTests=true`. Los tests hermanos (status) esperan el JSON de `OperationVisibleFacts`. **Eso ya fallaba en `77537bf` sin el cambio de input.** Se reescribió para leer `observed.utc` verificado vs reloj. La prosa la pone el compositor con mente; no es el camino Bypass.
- No se tocó FieldUi (sello SHA `8EA54763…`, 38 ficheros). El panel ya tenía CRUD; faltaba el puente.

## Bloqueo vivo al cortar
UIA del producto lanzado (`ControlType.Edit` name=`message input`):
- El control **existe**.
- Hasta `e787281` inclusive: `IsEnabled=false` porque el evento WS `agent.ready` seguía atado a `!IsBusy`.
- `5b65951` arregla eso. **No se llegó a confirmar UIA `enabled=true` ni un `core.call` de turno.** Ésa es la primera acción.

También visto, no cerrado:
- Tras `startup.ready` (~0,8–1,7 s) **no había proceso hijo `baxy-core.exe` ni python/llama-server**. El handshake sí ocurrió (si no, `startup.failed`). O el core muere después, o el poll lo pierde. `OnCoreDisconnected` pone `IsReady=false`. Distinguir con `Get-CimInstance Win32_Process` cada 200 ms al arrancar.
- Runtime mente: `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`. `llama_server` sigue en `Programacion\BAXY\legacy\models\artifacts\llama-b9980\` (aplazado goal 01). `python` y `gguf` sí apuntan a este árbol / `D:\BAXYRuntime`. Si la mente no sube, el compose del welcome se queda en cola; con `5b65951` el teclado no debería depender de eso. Los turnos que necesiten el decisor sí.
- Semáforo de core por data root: `BAXY core is already running for this local data profile.` (exit 73). Un `baxy-core` huérfano o un arranque suelto de diagnóstico ocupa `dev-mente-v2`.

## Cómo se lanza y se dosifica (ya escrito)
Scratch: `C:\Users\usuario\AppData\Local\Temp\grok-goal-4501eb8b7158\implementer\`
- `launch_once.ps1` — `py main.py` con `BAXY_APP_TRACE`, espera `startup.ready`, llama al dose.
- `scripts/goal10_dose_turns.ps1` — UIA igual que `scripts/probe_mvp_ui_smoke.ps1`: Edit habilitado + `ValuePattern` + Enter. Falla si el Edit está `enabled=false`.
- `scripts/goal10_idle_sampler.py` — proceso **aparte**. `--output artifacts/goal10/soak.json --interval 60`. Aún no se arrancó.
- Datos de `run_baxy.ps1`: `%LOCALAPPDATA%\BAXY\dev-mente-v2`. Trace: env `BAXY_APP_TRACE`. Autostart: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` valor `BAXY`.
- PowerShell: no interpolar `"launch-$RunId:"` — usar `("launch-{0}: ..." -f $RunId)`.

Turno representativo de launch: hora. Con Bypass de tests el cuerpo es JSON `system.time` verificado; en producto vivo, si la mente formula, prosa. El observable de gating es **qué afirmó y que la verificación lo sostiene** (utc vs reloj, o `core.call.start` detail `system.time` + `verified`).

## Tests que ya pasan (no re-derivar)
```
dotnet test tests\Baxy.Integration.Tests -c Release --filter "FullyQualifiedName~PresenceAutostartTests|FullyQualifiedName~MemoryPanelBridgeTests|FullyQualifiedName~NaturalSystemTimeViewModelEndToEndTests|FullyQualifiedName~MainWindowShellContractTests.NativeBridgePreservesTheHistoricalContractLocally"
```
Presence 3 + MemoryPanel round-trip store + tiempo JSON + NativeBridge. `ConfirmationModeTests` 4/4.

`MemoryPanelBridgeTests`: POST/GET/correct/DELETE + relectura de `LocalMemoryStore` en el mismo data root. Arranca ViewModel+core de verdad (~11 s).

## Costuras (vacías, goal 10)
`documentacion/03_COSTURAS.md` filas: Almacén de memoria; Capa visual (bandeja/WebView); Instalación y arranque. Rellenar con medición repetible **después** de idle+reboot+panel vivo.

## Siguiente acción — una, por este fichero
1. Matar `Baxy` / `py` / `python` huérfanos si los hay.
2. `py main.py` desde `BAXY Definitivo` con `BAXY_APP_TRACE` a scratch `launch-1.trace.jsonl`.
3. Cuando haya `startup.ready`, dump UIA: Edit `message input` tiene que estar **enabled=true**. Si no, el WS `AgentEvent` o el poll no están en el binario que corre (mirar timestamp de `Baxy.dll` vs `5b65951`).
4. Un turno «qué hora es» por `scripts/goal10_dose_turns.ps1`. Guardar `{SCRATCH}/launch-1.log` con operación, verified, hora vs reloj.
5. **En el mismo momento** sampler idle 24 h (`scripts/goal10_idle_sampler.py`) a `artifacts/goal10/soak.json` **y** copia en scratch. El soak no se comprime; cada hora sin él es hora perdida.
6. Kill + segundo `py main.py` → `launch-2.log`. Dejar esa instancia viva para soak+dosis.
7. Dosis ≥200 en ≥3 sesiones (POST `/sessions/new` o relanzar). Cinco más usadas **a partir de esa dosis**, luego ×20. Honestidad por sesión; un mentir = arreglo + repetir sesión.
8. Lived-checks: normal confirma sólo destrucción de datos; bypass por Settings `confirmationPolicy` y un segundo turno; narración sin pantalla; panel memoria ver/editar/borrar + relectura; `web.search` sin PII en la query.
9. Reboot real o `{SCRATCH}/reboot-unavailable.log` con la causa (no simular). Autostart tiene que levantar BAXY sin mano.
10. Compuerta `.\scripts\test_source_quality.ps1 -Mode Full`. Costuras. APLAZADOS. `git status` vacío y `origin/main` al día.

## Hipótesis
Confirmadas:
- Sin bandeja/autostart en el árbol → implementado, tests de registro en subclave `Software\BAXY\goal10-autostart-*` (no tocan el Run real en tests; el producto sí).
- Panel stub → `MemoryPanelBridge` + test de almacén.
- Input disabled = compose welcome + `IsBusy` en **dos** sitios (`/agent/status` y `AgentEvent`).

Descartadas:
- «El Edit no está en el árbol UIA» → sí está, name `message input`.
- «Hay que reescribir FieldUi» → no; el CRUD ya estaba.

Abiertas:
- ¿El core se muere tras el hello? → medir.
- ¿La mente no arranca en `py main.py`? → si el decisor no sube, muchos turnos de la dosis fallarán de compose; el camino determinista (hora, status, parsers) puede servir para el launch gating.

## No hacer
- No bajar umbral FAR. No skip/xfail. No soak sintético `overnight_soak.py`. No corpus como dosis. No tocar el repo `BAXY` a secas. No `spawn_subagent`. No inventar un HTTP extra para dosificar: el producto se dosifica por UIA como el smoke MVP.
