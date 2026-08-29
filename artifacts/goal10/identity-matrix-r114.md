# Identity matrix — live use after confirmation last-resort (r114-d)

Tree: Debug `Baxy.exe`. `BAXY_DENY_HOST_POWER_TRANSITION=1`. Host power **not** sent.
Last boot: 2026-08-27 21:25:24.

Welcome: «Hola.» then last-resort «Quedó una operación de memoria pendiente. Escribe continuar o reintentar.» (compose confirmation `no_response` no longer publishes «No pude: no responde.»).

Dose `identity-turns-r114-d.json` / `trace-identity-r114-d.jsonl`:

| Identidad | Evidence | Verdict |
|---|---|---|
| Starts, window, core | pid 18516, `startup.ready` 16.8 s, input enabled | pass |
| Speaks / name / local chrome | welcome voice earlier; UIA `BAXY`, `local · no telemetry`, TOOLS 169 | pass |
| Ordinary conversation | t1 `hola, como estas` → `decision.start` → «Bien.» | pass |
| Current time | t2 `que hora es` → `system.time` → «11:50.» (not trapped by recovery) | pass |
| Web search | t3 `busca el clima en buenos aires` → `web.search` → «Listo, el clima en Buenos Aires está parcialmente nublado…» | pass |
| Memory save while recovery pending | t4 `acordate…` correctly stays on recovery («continuar o reintentar») | pass (pending durable memory still blocks competing memory) |
| Memory recall | t5 `cual es mi color…` → «mi color de prueba es azul.» | pass |
| Apagar / reiniciar | **Not sent.** | environmental |
| Does not send live apagar | no such turn | pass (constraint) |

The dose harness still races `response.final` vs UIA; core operations and visible texts above are from the dose JSON and `decision.start` / `core.call.start` in the trace.
