# Handoff — 09.5.11C revalidar 07–09 — 2026-08-31

## Objetivo
Demostrar que los trasplantes conservan Goals 07–09.

## Estado
Hecho: matriz 07–09, holdouts misiones/primera señal/voz, next=09.5.12.
En curso: nada. Sin empezar: 09.5.12.

## Decisiones tomadas
- Cola transplant vacía no exime holdouts 07–09.
- R6 no se reabre (reuse_for_promotion_forbidden); se revalida el sello + planner vivo.
- Steam físico no se convierte desde el fixture.
- Ducking opcional no puede abortar captura: `_com_apartment()` va dentro del `try` de `duck`/`restore`.
- Hash de paquete/wake/attest usa SHA256 .NET; no depende de `Get-FileHash`.
- Pin STT `EXPECTED_PROGRAM_TREE_SHA256` resealed after `voice_aec.py`.
- Cero aplazos al Goal 10.

## Archivos tocados
- `src/baxy_mind/voice_aec.py` — COM apartment inside duck/restore try
- `scripts/product_build_common.ps1`, `scripts/attest_in_place_upgrade.ps1`, `scripts/install_baxy_wake_model.ps1`
- `experiments/stt_quality/*.py` — program tree pin `28aa1fbb…`
- `artifacts/goal095/synthesis/09.5.11C_revalidar_07_09.v1.json`
- `artifacts/goal095/ledger/revalidate-09.5.11C.json`
- `documentacion/herencia/09_5_11C_REVALIDAR.md`
- `artifacts/goal095/environment/09.5.11C.md`

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md` — se nombra, no se ejecuta
- `tests/test_goal09_voice_engines.py` — no editado
- `tests/test_goal095_09511c_revalidate.py` — no editado

## Hipotesis
Confirmadas: traceback `voice_aec.py:227 import comtypes` → `voice.py:2515`; R6 6/6 orphan=0; asserted_result=False; voice_hold=True; Full `source_quality_gate_passed: mode=Full`.
Descartadas: «falta silero_vad en la captura». «Relajar notepad». «Get-FileHash ausente = FALLO_DE_AMBIENTE».

## Comandos ejecutados y resultado
- `py -3.12 -m pytest tests/test_goal095_09511c_revalidate.py tests/test_goal09_voice_engines.py -q` → 15 passed in 43.37s
- `.\scripts\test_source_quality.ps1 -Mode Full` → source_quality_gate_passed: mode=Full; EXIT=0; python 8755 passed
- validate_report errors=[]

## Problemas pendientes
Ninguno de 09.5.11C. No ejecutar 09.5.12 en esta meta.

## Siguiente accion recomendada
`documentacion/sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md` (sesión nueva, un pegado).
