# Baseline de latencia — sprint de latencia (Fase 0) 2026-05-22

Medido contra el server de producción real (router `vram12-text`, E4B-Q6, b9090)
vía `bench/_latency_harness.py` (cada prompt 3×, mediana; tool dispatch mockeado
no-op para no tocar el sistema). Corpus: `bench/latency_corpus.jsonl` (27 prompts).

## Por tipo de turno

| tipo | n | mediana | max |
|------|---|---------|-----|
| smalltalk | 5 | 0.78s | 1.11s |
| factual-simple | 6 | 0.59s | **15.78s** (fs2) |
| pregunta-compleja | 5 | 2.27s | **48.23s** (cx5) |
| accion | 6 | **6.17s** | 15.92s |
| accion-multistep | 3 | **10.98s** | 12.44s |
| research | 2 | **6.84s** | 8.52s |

- **Corpus median 4.00s, max 48.23s. 12/27 turnos SLOW (≥5s).**
- Quality aggregate baseline: **0.959** (quality eval).

## Diagnóstico (de las trazas del harness)

1. **Acciones (ac1-ac6) y multistep (am1-am3): 3+ LLM calls/turno.** thinking ON
   (quick_action) para decidir el tool-call + el summary pass + (a veces) un pass
   extra. El thinking de la decisión + el decode del summary = el grueso.
2. **Outliers de thinking-runaway:** fs2 "cuándo salió GTA 5" (15.78s) cayó en
   `research` (marker " salio " no, pero el routing lo mandó a thinking) con 961
   chars de reasoning; cx5 "RAM vs disco" 48.23s (2 calls, thinking masivo).
3. **research (rs1/rs2): thinking_budget 2048** — el modelo piensa mucho antes de
   decidir si llamar web/knowledge.
4. **smalltalk + factual-simple ya están bien** (<1.2s): fast_action thinking OFF.

## Palancas (orden del sprint)

- **Fase 1 (riesgo 0):** streaming del reply (percibida ~1s), fact-extraction
  off-path (cuando está ON), saltar summary pass redundante.
- **Fase 2 (riesgo bajo):** gating de thinking — las acciones simples y factuales
  no necesitan 384-2048 tok de reasoning; recortar donde no agrega.
- **Fase 3 (riesgo medio):** calibrar thinking_budget de research/quick_action
  (curva latencia/calidad) — resuelve la decisión #3 del MERGE_CHECKLIST.

Objetivo: TODOS < 5s al reply completo, first-token < 1.5s, quality ≥ ~0.92
(caída leve aceptable si el promedio de latencia mejora claro).
