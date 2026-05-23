# Prompt para el agente Gemma 4 (operación sobre modelos Gemma 4)

> Pegar este prompt completo a una sesión nueva del agente que vaya a operar
> sobre `harness_carter540/`. Define objetivo, scope, datos de referencia y
> reglas de iteración.

---

## OBJETIVO

Llegar a **540/540 PASS** en el bench oficial Carter usando un modelo
Gemma 4 (E4B variants) con stubs deterministas. NO tocar el repo Carter.
Solo iterar sobre:

1. `system_prompt.py` (CORE_PROMPT v3+)
2. `auditor.py` (PASS/FAIL rules)
3. `stubs.py` (ajustar valores fijos si afecta auditor)
4. Quant del modelo (Q4_K_M, Q5_K_M, Q6_K, Q8_0)

NO modificar `tool_schemas.json` (es snapshot fijo del catálogo Carter).
NO modificar `tests_540.md` (es la fuente de verdad oficial).

## DATOS VERIFICABLES (fundamentación obligatoria)

Cada cambio debe citar al menos una fuente:

- **Gemma 4 Model Card (Google)**: https://ai.google.dev/gemma/docs/core/model_card_4
  - Sampling oficial: T=1.0, top_p=0.95, top_k=64
  - repeat_penalty=1.0 (Unsloth + Google)
- **Unsloth Gemma 4 docs**: https://unsloth.ai/docs/models/gemma-4
- **llama.cpp issues**:
  - #21690 mmproj OOM → `--ctx-checkpoints 1`, `--parallel 1`
  - #19523 parallel slots slow tg
  - #22527 SWA + FA CUDA error (sin workaround completo)
  - #21316 JSON delimiter leak (fixed PR #21327)
- **14_OPUS_DOSSIER_PATRONES_A_P** (en repo Carter): patrones A-P del audit
- **REPORTE_EXTENDIDO.md** (`Probando Gemma 4/`): scores por quant en 60-test
  bench
  - IQ2_M: 91.6% | Q4_K_M: 93.3% | Q5_K_M: 91.6% | Q6_K: 95.0% | Q8_0: 91.6%

## HARDWARE TARGET

- RTX 4060 Ti 16 GB VRAM
- Techo de uso útil para Carter: **6-8 GB** (deja headroom para mmproj +
  embeddings + KV cache)
- Modelos viables (cargados, sin mmproj):
  - IQ2_M (5.1 GB), Q4_K_M (6.1 GB), Q5_K_M (6.6 GB), Q6_K (7.1 GB), Q8_0 (8.2 GB)

## METODOLOGÍA DE ITERACIÓN

1. **Smoke 18 cases** (per-cat=1) — ciclo rápido (~3 min) para validar cambios
2. **Bench 90 cases** (per-cat=5) — ciclo medio (~15 min) para confirmar
3. **Bench full 540** — solo cuando smoke + 90 case están sólidos (~2-3h)

Para cada iteración:
- Diagnóstico fundamentado: leer fails, agruparlos por bucket
- Citar fuente: dossier 14 Pattern X, model card §Y, etc.
- Aplicar UN solo fix por iteración (variable aislada)
- Re-correr smoke; si mejora, escalar a 90; si mejora, full 540

## REGLAS DE OPERACIÓN

1. **Honestidad sobre el techo**: el dossier Opus dice 96-98% es el ceiling
   realista para qwen3:4b en este bench. Gemma 4 puede mejorarlo marginalmente
   pero no garantizado.

2. **Estabilidad llama-server**: el bench full debe correr en chunks de 90
   cases en processes Python frescos para evitar SIGSEGV (issue #22527 sin fix).

3. **Prompt cache invalidation**: cualquier cambio al SYSTEM_PROMPT invalida
   el prompt cache de llama-server. NO cambiar mid-bench.

4. **No regresiones**: cada cambio debe mantener o mejorar las categorías que
   ya están en 100%. Si una categoría a 100% baja, revertir el cambio.

5. **Escribir reportes JSON**: cada bench guarda JSON en `results/`. Iteración
   N+1 lee el JSON de N para ver qué cambió.

## SCOPE CLARO — QUÉ NO HACER

- NO importar ningún módulo del repo Carter (`carter_v4.*`)
- NO modificar el llama-server build (b9090 está fijo)
- NO bajar T<0.7 (Gemma 4 fue DPO/RLHF tuned a T=1.0)
- NO añadir agent loop / retrieval / step_planner (eso es Carter, este harness
  es modelo-puro)
- NO hardcodear per-app keywords (R5 del proyecto Carter aplica acá: lógica
  estructural multilingüe)

## CRITERIO DE ÉXITO

| Hito | Bench | Pass rate target |
|---|---|---|
| Mínimo viable | smoke 18 | ≥85% |
| Iteración productiva | per-cat 5 = 90 | ≥95% |
| Producción | full 540 | ≥97% |
| **Misión** | **full 540** | **100% (540/540)** |

## ENTREGABLES POR ITERACIÓN

1. `results/{ALIAS}_run.json` con resultados detallados
2. Análisis top-3 buckets de fails con fuente citada
3. Diff del cambio aplicado (idealmente <30 LOC)
4. Comparativa vs iteración anterior

## QUÉ DEVOLVER AL USUARIO

- Resultado numérico: PASS/TOTAL (%)
- Top 5 categorías mejor y peor
- Bucket dominante de fails
- Próximo fix planeado con fundamentación

---

**Empezar siempre con smoke 18 antes de full 540.**
