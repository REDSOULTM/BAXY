# Handoff — 09.5.8 runtime/UI/recursos — 2026-08-31

## Objetivo
Reconciliar runtime, UI, memoria, recursos y setup históricos contra el
producto vivo, sin rescatar frameworks ni un segundo camino.

## Estado
Hecho: síntesis 09.5.8 cerrada. Campañas 09.5.2–09.5.4 siguen pending=0 claimed=0.
En curso: nada de 09.5.8.
Sin empezar: `09.5.9_DECIDIR_HERENCIA.md`.

## Decisiones tomadas
- Conservar llama-server sidecar, FieldUi dist ADR-0008, journal HMAC, Setup NativeAOT, process_lifecycle, memoria protegida. Cero trasplantes.
- Medir (no inventar win): unload-on-idle y arranque en frío — lotes de Goal 10.2.
- Rechazar cámara-gaze POC y Qwen-VL (R-023, no se silencia). Rechazar Ollama/servicio Windows, vram_watchdog.py entero, jarvis proactive, hf_publish, telemetry/API_KEY, AUTO_APPROVE, soak 24 h como requisito.
- Runtime, FieldUi `dist` y Setup vivos: no se tocaron.

## Archivos tocados
- `artifacts/goal095/synthesis/09.5.8_runtime_ui_recursos.v1.json`
- `artifacts/goal095/ledger/synthesis-09.5.8.json`
- `documentacion/herencia/09_5_8_SINTESIS_RUNTIME.md`
- `documentacion/herencia/09_5_COBERTURA.md`
- `scripts/goal095_0958_synthesis.py` + `tests/test_goal095_0958_synthesis.py`
- `scripts/_goal095_validate_evidence_campaign.py` y `campaigns/evidence_assets.json` `next_human_prompt` → 09.5.9

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.9_DECIDIR_HERENCIA.md` — siguiente prompt humano

## Hipotesis
Confirmadas: recinto 25/25, 477/477, 132/132 pending=0. 15/15 áreas. p50 2,18 s / pico 3066 MiB / idle RSS 1088 MB conservan hardware+versión+escenario+denominador.
Descartadas: «traer vram_watchdog/ui_field/cámara/proactive cierra presencia». «Falta relanzar 09.5.2–09.5.7». «Soak 24 h es el listón».

## Comandos ejecutados y resultado
- `py -3.12 -m pytest tests/test_goal095_0958_synthesis.py tests/test_goal095_0957_synthesis.py tests/test_goal095_0956_synthesis.py tests/test_goal095_0955_synthesis.py -q` → 16 passed, 0 skip, 0 failed (dos veces)
- `py -3.12 scripts/_goal095_validate_docs_campaign.py` → 25/25 pending=0 claimed=0
- `py -3.12 scripts/_goal095_validate_code_campaign.py` → 477/477 pending=0 claimed=0
- `py -3.12 scripts/_goal095_validate_evidence_campaign.py` → pending=0 claimed=0 complete=132 relaunch_09_5_4=0 next_human=09.5.9 errors=[]
- No ejecutado: `.\scripts\test_source_quality.ps1` — el diff no toca `src`

## Problemas pendientes
Ninguno de 09.5.8. Siguiente humano: 09.5.9.

## Siguiente accion recomendada
Pegar `documentacion/sprints/09.5.9_DECIDIR_HERENCIA.md` (sesión nueva, /goal). No relanzar 09.5.2–09.5.8.
