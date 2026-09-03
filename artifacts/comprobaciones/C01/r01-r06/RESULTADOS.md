# R01–R06 — captura fiel (C01)

Comando:

```powershell
py main.py --conductor --turns-file artifacts\comprobaciones\C01\r01-r06.turns.jsonl --capture artifacts\comprobaciones\C01\r01-r06 --timeout-ms 180000
```

Commit adjunto en `events.jsonl` `meta`: `b2505da8f15820f94e47d874a66e26a927ea2e9a`.
Runtime: manifiesto `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` (Qwen3-4B-Q4_K_M, python mind-runtime-v1, llama-server, parakeet STT, piper TTS).
Perfil persistente: `%LOCALAPPDATA%\BAXY\comprobaciones-c01` (no se vació entre turnos).
Oráculos independientes: `oracles-before.txt` / `oracles-after.txt`.
JSONL público: `events.jsonl`.

C01 exige captura, no que estos casos ya pasen. Owners: C03–C05.

## Oráculos

| Momento | Reloj local | Calculadora | Red 1.1.1.1 |
|---|---|---|---|
| Antes | 2026-09-02 23:57:14 -04:00 | ausente | True |
| Después | 2026-09-02 23:58:26 -04:00 | `ApplicationFrameHost` título «Calculadora» + `CalculatorApp` | True |

Restauración propia: se cerró `CalculatorApp` tras observar. No se tocó el store ni se relanzó el caso.

Journal del perfil (operaciones emitidas, no inyectadas): `memory.status` (arranque), `system.time` completed/verified a las `2026-09-03T03:57:42.4436484+00:00` offset −240 min, `app.open` `verification_failed` / `effectUncertain=true`.

## Casos

### R01 — Hola / conocimiento / seguimiento — FAIL (C03/C06)

| Entrada | Terminal | Texto final publicado |
|---|---|---|
| Hola, ¿qué puedes hacer? | published_final | Puedo ayudarte con diversas tareas, como responder preguntas, proporcionar información, resolver problemas y ofrecer orientación. |
| Explícame qué es un huso horario en una frase. | published_final | No puedo explicar qué es un huso horario en una frase. |
| ¿Por qué importa? | published_final | Quieres que force la terminación de un proceso por nombre exacto…? |

Capacidades genéricas, no verdaderas. La pregunta de conocimiento se niega. El seguimiento propone matar un proceso (acción no pedida, pide confirmación). `hasPendingPlan=false` tras el primero; tras el tercero status `Esperando tu aclaración`.

### R02 — ¿Qué hora es? — FAIL (C03/C04)

Texto: `No pude: no pude encontrarlo.` `compositionFailure=no_response`.
Journal: `system.time` **sí** completó con UTC `2026-09-03T03:57:42.4436484+00:00` (23:57:42 -04:00), dentro del oráculo 23:57:14–23:58:26. El Core acertó; la prosa no.

### R03 — Abre la calculadora — FAIL (C04)

Texto: `No pude: la composición se perdió y se verificaron hechos.`
Journal: `app.open` `verification_failed`, `effectUncertain=true`.
Observación independiente: la ventana **Calculadora** estaba abierta. Efecto real + prosa de fallo + plan pendiente (`hasPendingPlan=true`, `awaiting_mission_resume`).

### R04 — Cuéntame un chiste corto — FAIL (C05)

Tras el efecto incierto de R03. Texto: `La aplicación está abierta y muestra el título "Nota: Informe de actividad".`
No es un chiste. Habla de otra app. `hasPendingPlan` sigue true: el plan viejo capturó el turno. No se observó Notepad tras la corrida.

### R05 — ¿Tengo conexión a internet? — FAIL (C05/C06)

Texto: `¿Tienes conexión a internet?` (eco). Oráculo: red True. No hay operación de red en el journal. `hasPendingPlan` sigue true.

### R06 — Nueva sesión → hora y audio — FAIL (C05/C03)

`POST /sessions/new` status 200. Entrada: `Dime la hora y el estado del audio.`
Texto: `Listo, audio está abierto.` Sin hora. Éxito de audio inventado (C08 no se certifica aquí). Posterior: `messageCount=3` (sesión nueva en UI) pero `hasPendingPlan=true` — `StartNewUiSession` no retira `_pendingMindPlan` (defecto ya trazado, owner C05).

## Qué demuestra C01

Todos los turnos tienen `admission` distinto de `terminal`. Ningún `status=accepted` se tomó como final. El conductor no inventó texto ni reparó la sesión (el plan pendiente sobrevivió a Nueva sesión, igual que en la UI). Visual/acústico no se declara verificado.
