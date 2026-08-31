# Handoff — 09.5.9 decidir herencia — 2026-08-31

## Objetivo
Convertir la evidencia 09.5.2–09.5.8 en una decisión exhaustiva
reusar/adaptar/conservar/medir/rechazar y dejar la campaña `transplant` acotada.

## Estado
Hecho: matriz 09.5.9, asignación 9.268 tarjetas, campaña `transplant` vacía
(pending=0 claimed=0 total=0), guardas de rechazo, tests dueño. En curso: ejecutar
09.5.10 una vez bajo esta misma meta (campaña ya vacía). Sin empezar: 09.5.11A.

## Decisiones tomadas
- Cero `reusar_exacto` / `adaptar` / `medir_antes`. El vivo iguala o supera la herencia.
- 09.5.8 `medir` (unload-on-idle, arranque frío) → `conservar_actual`: incomparable, Goal 10.2 mide el producto, no se transplanta vram_manager.
- GGUF/datasets/checkpoints dispersos: hashes not invented, no se reutilizan.
- Rechazos protegidos: FunctionGemma en pesos, Qwen-VL R-023, Ollama/servicio Windows, AUTO_APPROVE, soak 24 h como requisito, Gemma-native-audio.

## Archivos tocados
- `artifacts/goal095/synthesis/09.5.9_decidir_herencia.v1.json`
- `artifacts/goal095/synthesis/09.5.9_card_assignment.v1.json`
- `artifacts/goal095/campaigns/transplant.json`
- `artifacts/goal095/ledger/synthesis-09.5.9.json`
- `scripts/goal095_0959_matrix.py` + `scripts/goal095_0959_build.py` + `tests/test_goal095_0959_matrix.py`
- `documentacion/herencia/09_5_9_DECIDIR_HERENCIA.md` + `09_5_COBERTURA.md` + `documentacion/APLAZADOS.md`

## Archivos relevantes aun sin tocar
- `documentacion/sprints/09.5.10_TRASPLANTAR_LOTE.md` — se ejecuta a continuación, no se pega otra vez
- `src/` — no cambia

## Hipotesis
Confirmadas: recinto 25/477/132 pending=0; 100 responsabilidades y 9.268 tarjetas una vez; campaña vacía con razón escrita.
Descartadas: «hay que medir Gemma E4B / unload histórico ahora». «Un segundo runtime/UI/catálogo por si acaso».

## Comandos ejecutados y resultado
- `py -3.12 scripts/goal095_0959_build.py` → 96 rows, 9268 cards, 0 lots
- `py -3.12 -m pytest tests/test_goal095_0959_matrix.py -q` → 6 passed (re-run after counts fix)

## Problemas pendientes
Ninguno de 09.5.9. Ejecutar 09.5.10 sobre la campaña ya vacía y apuntar el siguiente humano a 09.5.11A.

## Siguiente accion recomendada
No pegar 09.5.9 otra vez. Vaciar 09.5.10 (pending ya 0) y dejar `09.5.11A_REVALIDAR_01_03C.md`.
