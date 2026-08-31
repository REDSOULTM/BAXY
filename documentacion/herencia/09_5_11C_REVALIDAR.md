# Goal 09.5.11C — Revalidar Goals 07–09

Cerrado 2026-08-31. Fuente de verdad machine-readable:
[`../artifacts/goal095/synthesis/09.5.11C_revalidar_07_09.v1.json`](../../artifacts/goal095/synthesis/09.5.11C_revalidar_07_09.v1.json).
Ledger: [`../artifacts/goal095/ledger/revalidate-09.5.11C.json`](../../artifacts/goal095/ledger/revalidate-09.5.11C.json).

Siguiente prompt humano:
[`../sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md`](../sprints/09.5.12_INTEGRAR_Y_REPLANIFICAR.md).
No remite a 09.5.11C, 09.5.11B, 09.5.11A, 09.5.10 ni 10.0.

## Cola transplant

**Vacía.** `pending=0` `claimed=0`. 09.5.10 no aportó lotes; los holdouts 07–09
se corrieron igual. Hashes sparse **not invented**.

## Etiquetas fisica / fixture

Cada criterio de la matriz lleva `label`. Steam físico no se reabrió:
el cierre vigente es fixture/sello. TTS `cancel()` a media frase es el
único holdout físico reejecutado. Hardware ausente habría sido
`FALLO_DE_AMBIENTE`, no `pytest.skip`.

## Holdouts

### Misiones (Goal 07)

R6 sello **6/6**, pasos **22**,
huérfanos **0** (recount `0`), ambiguos **0**.
Reuse for promotion **forbidden**. Planner vivo ES/EN/spanglish:
`app.open` + `input.visible.click` con postcondición de etiqueta.
El veto de conservación corta «Abre Steam y envía un mensaje a Ana».

### Primera señal (Goal 08)

asserted_result=False. Reconocedor calla, modelo avisa.
GPU p50=0.009 p95=0.161 máx=0.551.
measure_first_signal_latency no se reabrió: runtime no trasplantado.

### Voz (Goal 09)

STT complete=True; TTS neural=True; wake present=True; noise FA=False.
WAV inyectado, no micrófono. Interrupción: NeuralSpeechOutput.cancel.
Comando dueño en `py -3.12`: 15 passed in 43.37s. `AudioDucker` envuelve
`_com_apartment()` en el `try` de duck/restore. Pin STT resealed
`28aa1fbb4375f30e853a3d4d390d78e1fcf22afccabbc342f61250a2f2cbfe07`.

### Campañas no reejecutadas

- `r6-execution` — sello reuse_for_promotion_forbidden; se revalida el sello y el planner vivo
- `measure_first_signal_latency` — runtime no trasplantado; contrato funcional reejecutado en test_first_signal
- `steam-physical` — cierre vigente fixture/sello; 11C no abre Steam ni convierte el fixture
- `wake-far-tv` — holdout FAR sellado; umbral 0,5 no se retoca
- `idle-listen-60s` — runtime de voz no trasplantado; artifacts/goal09/idle_listen.json

### Procedencia y reproducibilidad

Procedencia: sparse_not_invented=True; transplant {'pending': 0, 'claimed': 0, 'complete': 0, 'total': 0}.
Reproducibilidad: `.\scripts\test_source_quality.ps1 -Mode Full` → source_quality_gate_passed: mode=Full.

Cero aplazos al Goal 10.
