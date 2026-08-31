# Handoff — 09.5.11C revalidar 07–09 — 2026-08-31

## Objetivo
Demostrar que los trasplantes conservan Goals 07–09.

## Estado
Pausado: dueño 15 passed in 46.70s; Full no reejecutado en esta verificación. next=09.5.12.
En curso: Full. Sin empezar: 09.5.12 no se ejecuta.

## Decisiones tomadas
- Cola transplant vacía no exime holdouts 07–09.
- R6 no se reabre (reuse_for_promotion_forbidden); se revalida el sello + planner vivo.
- Steam físico no se convierte desde el fixture.
- Captura `ModuleNotFoundError` en `voice.py:2515`: `AudioDucker.duck()` importaba `comtypes` fuera del `try`. Ducking opcional no puede abortar captura.
- `rapidfuzz` en `py -3.12` corrige `nootpad` → `notepad`. No se relajó la aserción.
- Cero aplazos al Goal 10.
- No se afirma Full verde.

## Archivos tocados
- `src/baxy_mind/voice_aec.py` — `duck()`/`restore()` envuelven `_com_apartment()` en el `try` de degradado
- `artifacts/goal095/synthesis/09.5.11C_revalidar_07_09.v1.json`
- `artifacts/goal095/ledger/revalidate-09.5.11C.json`
- `documentacion/herencia/09_5_11C_REVALIDAR.md`
- `artifacts/goal095/revalidate/goal09511c_campaigns.json`
- `artifacts/goal095/environment/09.5.11C.md`

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md` — se nombra, no se ejecuta
- `tests/test_goal09_voice_engines.py` — no editado
- `tests/test_goal095_09511c_revalidate.py` — no editado

## Hipotesis
Confirmadas: traceback `voice_aec.py:227 import comtypes` → `voice.py:2515`; R6 6/6 orphan=0; asserted_result=False; voice_hold=True; owner 15 passed in 46.70s.
Descartadas: «falta silero_vad en la captura». «Relajar notepad». «Skip de asset = pass».

## Comandos ejecutados y resultado
- `py -3.12 -c "import silero_vad, sounddevice; print('READY_IMPORTS=1')"` → READY_IMPORTS=1
- Duck con `comtypes` oculto → `duck=False` (ya no levanta). Duck vivo → `True`.
- `py -3.12 -m pytest tests/test_goal095_09511c_revalidate.py tests/test_goal09_voice_engines.py -q` → 15 passed in 46.70s
- `py -3.12 -m pytest tests/test_mind_voice_runtime.py::test_voice_cleanup_restores_ducking_before_stopping_loopback -q` → 1 passed in 0.60s

## Problemas pendientes
Full no reejecutado en esta verificación. No declarar 09.5.11C completo. No ejecutar 09.5.12.

## Siguiente accion recomendada
`documentacion/sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md` (sesión nueva, un pegado). No se lanza mientras Full no sea verde.
