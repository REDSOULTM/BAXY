# Sprint — Cache-hit del summary pass (el lever REAL de latencia de acción)

**Fecha:** 2026-05-29 · **Resultado:** acción turn ~3.3s → ~2.2s (**−~1s**),
`GEMMA4_SUMMARY_KEEP_TOOLS` **default ON**, validado en vivo. Driver: research
`compass_artifact_*` (respuesta a `PROMPT_RESEARCH_prefill_cache_latency.md`).

## El problema (medido)
Un turno de acción hace 2 LLM calls; el costo DOMINA en el PREFILL del prompt
(~2.3s de ~3.3s). La pass-2 (confirmación) re-prefileaba ~5.3k tokens (~1s) en vez
de reusar el prefijo de la pass-1.

## Causa raíz (2 divergencias del prefijo, ambas necesarias de arreglar)
1. **El summary DROPEA las tools** (slimming 2026-05-20) → prefijo distinto a pass-1.
2. **`enable_thinking` TOGGLEA** (pass-1 True / summary False) → el chat-template
   re-renderiza desde el token ~0. MEDIDO con `_diag_prefix_divergence.py`: con
   tools mantenidas pero enable_thinking distinto, `cache_n=4` (miss TOTAL).

El research confirmó: el prefix-cache YA funciona (PR #21749 para SWA + `--swa-full`
en b9384); **NO** hay que tocar `--cache-reuse` (Gemma 4 lo rechaza por shared-KV,
#21468). Solo hay que mantener el prefijo byte-idéntico.

## El fix (en `_execute_turn`, success-gated)
En el summary pass, cuando la última tool SUCCEEDED:
- mantener las tools (`_pass_tools = selected_schemas`),
- **matchear el `enable_thinking` de pass-1** (`mode.enable_thinking`) con
  `thinking_budget=16` (el budget es sampler param, NO va en chat_template_kwargs
  → no afecta el prefijo cacheado; 16>0 evita el corte mid-think de budget=0).

→ pass-2 prefill **5229 → 82 tokens** (`cache_n=5708`), pass-2 wall ~1017ms → ~33ms.

**SUCCESS-GATING (crítico):** `enable_thinking=True` hace que el modelo RE-ENGANCHE
con una acción FALLIDA → runaway (MEDIDO: brillo WMI-fail 6 calls@budget0, 3@16, vs
2 con thinking-off). Por eso cache-mode SOLO en éxito (verified/ok/status∈{ok,
success,dispatched}); en fallo → path original (slim + thinking off), idéntico a
antes (sin penalidad, sin runaway).

## Validación en vivo (`scripts/_verify_cache_hit.py`)
- volumen ×6 (éxito): cache hit (pass2=79-82), 2 calls, ~2.2-2.4s, replies correctos.
- minimizá (no-window soft-fail, dispatched ok): cache hit 118/172, 2 calls, correcto.
- **brillo (hard WMI-fail): KEEP == off EXACTO** (2 calls, 7200 prefill) — sin penalidad.
- SOAK 8 acciones: **cache-hits 7/8, runaways 0, bad 0**. (El 1 no-hit = el fallo
  no-window, correctamente off-pathed.)
- 53 tests de regresión verdes con default ON.

## Config de server (confirmado por research, sin cambios necesarios)
Mantener `--flash-attn off` (estabilidad, mata el crash #22527 en E2B) + `--swa-full`
(hace funcionar el prefix-reuse para SWA + saltea el checkpoint-restore buggy, PR
#21749). NO `--cache-reuse`. NO KV-quant (necesita FA). mmproj lazy. `-np 1`.

## Descartado por el research (confirmado, no refutado)
prefill `<|tool_call|>` (assistant-prefill incompatible con thinking, #21889/#20861;
thinking es load-bearing); streaming de acciones (~0 win); KV-quant con FA-off.

## Pendiente
- Soak de 50 turnos variados (gate del research) para confirmar 0 crashes + cobertura
  de más tipos de tool en el success-gate.
- El residual de prefill de pass-1 (cuando NO hay hit cross-turn) sigue ~1.2s — es el
  prefill genuino del prompt; el lever ahí ya es el lean mode (aplicado).
