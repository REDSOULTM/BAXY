# MANUAL_LIVE_LLM_FIRST_BLOCKERS

Fecha: 2026-05-05

## Estado

No hay blockers abiertos para `MANUAL_LIVE_LLM_FIRST_READY`.

## Riesgos no bloqueantes

| Riesgo | Estado | Mitigación |
|---|---|---|
| Variación del modelo local real | No bloqueante para unit/smoke exacto | Re-ejecutar live con Ollama/local model antes de distribución final. |
| Emergency fallback si LLM devuelve vacío/placeholder | Aceptado por seguridad | Ruta normal llama LLM; fallback preserva evidencia y evita fake success. |
| Smoke usa adapter controlado | Aceptado como manual-equivalent | Secuencia exacta `18/18 PASS`; full suite y guard pasan. |
