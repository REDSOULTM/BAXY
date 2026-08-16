# 01 — Resumen ejecutivo

**Documentación completa del proyecto `Probando Gemma 4`.**
Validación, benchmarking y diseño arquitectural de Gemma 4 para el proyecto Carter v4/v5.

---

## TL;DR del proyecto entero

- **Misión:** evaluar si Gemma 4 puede reemplazar a `qwen3:4b` como cerebro de Carter, y dejar todo configurado para integración.
- **Resultado:** **540/540 PASS** sobre el bench oficial Carter con `gemma-4-E4B-it-Q6_K`, tanto con tools individuales (60) como consolidadas (16 composite).
- **Hardware target:** RTX 4060 Ti 16 GB CUDA — idéntico al de producción Carter.
- **Esfuerzo:** ~5,800 invocaciones al modelo, ~18 horas de GPU efectivas, 14 iteraciones del bench.
- **Entregables:** 4 reportes técnicos, 1 carpeta `evidencia pruebas gemma4/` para el agente Carter, 16 gráficos comparativos, esta documentación.

---

## Las tres fases del proyecto

![Cobertura de fases](../graficos/14_cobertura_fases.png)

| Fase | Qué se midió | Tests | Modelos | Resultado |
|---|---|---|---|---|
| **Fase 1** | Validación inicial Gemma 4 viable | 10 | 7 cuantizaciones E2B + E4B | E2B-Q5_K_M y E4B-UD-IQ2_M sacaron 9/10 |
| **Fase 2** | Comparativa exhaustiva modelos | 60 × 22 | 22 cuantizaciones E2B/E4B/26B-A4B/31B + qwen3:4b baseline | E4B-Q6_K ganador con 57/60 (95%) |
| **Fase 3** | Bench oficial Carter en hardware target | 540 | E4B-Q6_K (individuales y consolidated) | **540/540 = 100%** |

---

## Modelo ganador medido

| Métrica | Valor |
|---|---|
| Modelo | `gemma-4-E4B-it-Q6_K.gguf` |
| Origen | `unsloth/gemma-4-E4B-it-GGUF` |
| Tamaño en disco | 6.59 GB |
| **VRAM cargado real** | **7.1 GB** (modelo + mmproj F16 + KV cache 16K) |
| Hardware probado | RTX 4060 Ti 16 GB CUDA b9090 |
| **PASS Carter 540** | **540/540 = 100%** |
| Latencia p50 global | 4.26s |
| Latencia p99 global | 20.45s |

---

## Por qué este modelo y no otro

![Selector hardware](../graficos/15_selector_hardware.png)

- **E4B (Efficient 4B activos)** — mejor balance calidad/VRAM en consumer GPU.
- **Q6_K** — sweet spot. Q4 pierde 2-5pp; Q8 no aporta sobre Q6 medido.
- **Tools individuales o consolidated 16** — ambos llegan a 540/540. Consolidated reduce tokens schema 68% para escalar a Carter 100+ tools sin romper context.

Ver [02_comparacion_modelos/](../02_comparacion_modelos/) para el desglose de las 22 cuantizaciones probadas.

---

## Cumplimiento de los 30 valores de Carter

![30 valores Carter](../graficos/16_30_valores_carter.png)

26 de 30 valores se cumplen en el modelo. Los 4 restantes (Valores 2, 4, 17, 22, 26) requieren **wiring runtime del lado de Carter** — no son bugs del modelo. Ver [10_carter_integration/](../10_carter_integration/).

---

## Mapa de la documentación

| Carpeta | Tema |
|---|---|
| **01_resumen_ejecutivo/** | Este README |
| **02_comparacion_modelos/** | Las 22 cuantizaciones evaluadas |
| **03_iteraciones_540/** | v1 → v14 del bench Carter 540 |
| **04_vram_y_hardware/** | VRAM real medida + perfiles por hardware |
| **05_latencia_y_alexa_tier/** | p50/p90/p99 por categoría + Alexa-tier check |
| **06_consolidacion_tools/** | 60 → 16 tools composite (Anthropic best practice) |
| **07_audio_y_vision/** | Bloque D + estado mmproj |
| **08_investigacion_externa/** | Fuentes oficiales Google/llama.cpp/Anthropic citadas |
| **09_arquitectura_decisiones/** | Por qué Q6_K vs Q4/Q5/Q8, por qué CUDA vs Vulkan, por qué llama.cpp vs vLLM |
| **10_carter_integration/** | Plan de migración + 30 valores cumplidos |
| **graficos/** | 16 PNG comparativos |
| **datos_crudos/** | Subset de results/ relevantes |

---

## Reportes principales generados durante el proyecto

Estos viven en `docs/`:

- [`docs/REPORTE.md`](../../docs/REPORTE.md) — Fase 1 (10 tests inicial)
- [`docs/REPORTE_EXTENDIDO.md`](../../docs/REPORTE_EXTENDIDO.md) — Fase 2 (60 tests × 22 modelos)
- [`docs/INFORME_AUDIO_PARA_CARTER.md`](../../docs/INFORME_AUDIO_PARA_CARTER.md) — análisis específico de audio nativo
- [`docs/REPORTE_GEMMA4_PARA_CARTER.md`](../../docs/REPORTE_GEMMA4_PARA_CARTER.md) — reporte definitivo final, alineado a 30 valores Carter
- [`harness_carter540/REPORTE_540_GEMMA4.md`](../../harness_carter540/REPORTE_540_GEMMA4.md) — bench Carter 540
