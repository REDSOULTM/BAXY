# Goal 09.5.8 — Síntesis: runtime, UI, memoria, recursos y setup

Cerrado 2026-08-31. Fuente de verdad machine-readable:
[`artifacts/goal095/synthesis/09.5.8_runtime_ui_recursos.v1.json`](../../artifacts/goal095/synthesis/09.5.8_runtime_ui_recursos.v1.json).
Inventario desde tarjetas 09.5.2–09.5.4, Goal 01 (`00_MAPA.md`), Goal 03
(`documentacion/03_COSTURAS.md`), Goal 09 idle (09.5.6 recursos), ADR-0003/0004/0005/0008
y `_09510_requirements.json`. No se leyeron cuerpos de `biblioteca/` ni se
recorrieron árboles fuente.

Siguiente prompt humano:
[`../sprints/09.5.9_DECIDIR_HERENCIA.md`](../sprints/09.5.9_DECIDIR_HERENCIA.md).

Runtime vivo, FieldUi `dist` y Setup **no se tocaron**. `transplants: []`.
No hay soak de 24 h como requisito.

## Invariantes (todos true)

Privacidad local (entra web, no sale contenido del usuario). Accesibilidad
central en el motor, modo sólo en la UI. Estados terminales honestos.

## Áreas (15/15)

Cada fila: pieza histórica, owner vivo, Goal 10 que consumiría la conducta,
decisión (`reusar` / `adaptar` / `conservar_actual` / `medir` / `rechazar`).
Recursos/latencia/arranque llevan hardware, versión, escenario y denominador,
o marca incomparable. Sobrecarga propia ≠ inferencia.

| Id | Owner vivo | Goal 10 | Decisión |
|---|---|---|---|
| Runtime/servidor | `baxy_mind/llm.py` + `process_lifecycle` (llama-server sidecar) | 10.0 | `conservar_actual` — no Ollama ni servicio Windows |
| Carga/descarga | `llm.py` keep-warm; no unload-on-idle | 10.2 | `medir` — idle 15 min vs unload, no cifra alineada |
| VRAM/RAM/CPU | Qwen3-4B pico ~3066/3072 MiB; oído idle RSS 1088 MB | 10.2 | `conservar_actual` — ley 4; hermes3 4857 MiB incomparable |
| Latencia | p50 2,18 s / p90 3,02 s n=122 llama.cpp b9980 | 10.2 | `conservar_actual` — PG4 10/16 s es otro stack |
| Arranque | `CoreProcessClient` + `process_lifecycle` | 10.2 | `medir` — cold start/reinicio los corre 10.2 |
| Watchdog | reap acotado + Job Object | 10.2 | `conservar_actual` — no `vram_watchdog.py` entero |
| Estabilidad | idle 15 min (plan 10.2), no 24 h | 10.2 | `conservar_actual` — `_soak50` no es requisito |
| Field UI/a11y | `src/Baxy.FieldUi` dist ADR-0008; voz en el motor | 10.17 | `conservar_actual` — no se rescata `ui_field`/`accessibility.py` |
| Visión/cámara | cascada de pantalla; cámara no es producto | 10.10 | `rechazar` — POC mirada + Qwen-VL R-023 (no se silencia) |
| Memoria/proactividad | `Providers.Windows/Memory`; Identidad veta actuar solo | 10.14 | `conservar_actual` — no jarvis proactive |
| Journal | `Kernel/Journal` HMAC v2 | 10.0 | `conservar_actual` |
| Setup/publish | `Baxy.Setup` NativeAOT ADR-0003/0004 | 10.0 | `conservar_actual` — `hf_publish` no es instalador |
| Privacidad | inbound web; cero contenido de usuario outbound | 10.17 | `conservar_actual` — no telemetry.py ni API_KEY |
| Seguridad | `ConfirmationAuthority` + política de riesgo | 10.17 | `conservar_actual` — no AUTO_APPROVE |
| Diagnósticos | `app.status` + GPU provider + health llama-server | 10.2 | `conservar_actual` — `_diag` no entra al runtime |

## Recursos (equivalentes o `medir`)

- **Inferencia VRAM:** Windows, esta máquina, presupuesto **4 GiB**, llama.cpp
  b9980, Qwen3-4B-Q4_K_M, pico ~3066/3072 MiB (Goal 03 / MVP).
- **Oído idle:** 60,016 s, RSS 1087,8 MB, GPU 510/16380, llama-server off
  (Goal 09 `idle_listen.json`). No toca los 4 GiB del decisor.
- **Latencia inferencia:** p50 2,18 s / p90 3,02 s, n=122, corpus fresco
  SHA `761c1bc3…`. Listón 3 s; bajo carga p50 3,7–4,0 s (ya en 09.5.5).
- **Sobrecarga propia:** PG4 10 de 16 s y Carter landing 23 s→10 s son otro
  stack. No se presentan como victoria del p50 vivo.
- **Arranque / unload-on-idle:** incomparables; Goal 10.2 los mide.

## Qwen-VL

No se silencia. R-023: inventó juegos. Cámara/Field UI: FieldUi se conserva
(ADR-0008); cámara-gaze se rechaza como producto.

## Trasplantes

Ninguno. Extraer un framework histórico (NVML watchdog, ui_field, cámara,
proactive, hf_publish) por una utilidad aislada duplicaría el camino vivo.
09.5.9 decide; 09.5.10 aplicaría.

Pesos, runtime, FieldUi `dist` y Setup vivos: **no se tocaron**.
