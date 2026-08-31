# Handoff — 09.5.11C revalidar 07–09 — 2026-08-31

## Objetivo
Demostrar que los trasplantes conservan Goals 07–09.

## Estado
Pausado: FALLO_DE_AMBIENTE de voz en py -3.12. next=09.5.12.
En curso: espera silero_vad y sounddevice en el intérprete de pytest. Sin empezar: 09.5.12 no se ejecuta.

## Decisiones tomadas
- Cola transplant vacía no exime holdouts 07–09.
- R6 no se reabre (reuse_for_promotion_forbidden); se revalida el sello + planner vivo.
- Steam físico no se convierte desde el fixture.
- test_goal09_voice_engines resuelve STT/wake/TTS por las funciones enviadas; falta de asset = fail, no skip.
- Cero aplazos al Goal 10.
- No se afirma stt=True/tts_neural=True si `py -3.12 -m pytest` no lo prueba.
- Los cuatro extractos pre-campaña no se restauran (bdb8919 / never versioned; hashes not invented).

## Archivos tocados
- `artifacts/goal095/synthesis/09.5.11C_revalidar_07_09.v1.json` — matriz machine-readable
- `artifacts/goal095/ledger/revalidate-09.5.11C.json` — ledger 09.5.11C
- `documentacion/herencia/09_5_11C_REVALIDAR.md` — cierre documental
- `artifacts/goal095/revalidate/goal09511c_campaigns.json` — pytest in-scope 07–09
- `tests/test_goal09_voice_engines.py` — resolvers enviados, fail cerrado
- `tests/test_goal095_09511c_revalidate.py` — prueba dueña
- `artifacts/goal095/environment/09.5.11C.md` — FALLO_DE_AMBIENTE

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md` — se nombra, no se ejecuta

## Hipotesis
Confirmadas: R6 6/6 orphan=0; asserted_result=False; voice_hold=False.
Descartadas: «cola vacía = no medir». «Skip de asset ausente = pass». «Reabrir R6». «runtime-python pytest cuenta como py -3.12».

## Comandos ejecutados y resultado
- R6 orphan=0 unverified=[]
- first_signal asserted_result=False
- voice stt not proven; tts_neural not proven; wake onnx present
- `py -3.12 -m pytest tests/test_goal095_09511c_revalidate.py tests/test_goal09_voice_engines.py -q` → 8 passed, 7 failed (FALLO_DE_AMBIENTE silero_vad/sounddevice). Relabel keeps fail closed.
- Runtime python `tests/test_goal09_voice_engines.py -q` → 7 passed in 42.63s. No sustituye py -3.12.
- `.\scripts\test_source_quality.ps1 -Mode Full` → static+dotnet passed; python-tests failed (exit -1). No se afirma passed.

## Problemas pendientes
FALLO_DE_AMBIENTE: py -3.12 no importa silero_vad ni sounddevice. No declarar el goal completo.

## Siguiente accion recomendada
`documentacion/sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md` (sesión nueva, un pegado). No se lanza mientras el comando dueño de voz no sea verde.
