# 📚 Índice maestro — Documentación `Probando Gemma 4`

Documentación completa, trackeable y comparativa del proyecto desde la primera línea hasta la última. **5,800+ invocaciones al modelo, 22 cuantizaciones probadas, 14 iteraciones del bench Carter 540, 16 gráficos comparativos, 9 secciones temáticas.**

---

## 🎯 TL;DR

**Modelo ganador:** `gemma-4-E4B-it-Q6_K` con **540/540 = 100%** en bench oficial Carter, tools individuales y consolidated 16. **VRAM 7.1 GB**, hardware target RTX 4060 Ti 16 GB CUDA.

Si solo vas a leer una cosa: [REPORTE_GEMMA4_PARA_CARTER.md](../docs/REPORTE_GEMMA4_PARA_CARTER.md) en `docs/`.

---

## 📂 Estructura de esta documentación

### Texto + análisis

| Carpeta | Tema | Lectura sugerida |
|---|---|---|
| [01_resumen_ejecutivo/](01_resumen_ejecutivo/) | TL;DR del proyecto entero | ⭐ empezar acá |
| [02_comparacion_modelos/](02_comparacion_modelos/) | Las 22 cuantizaciones evaluadas en Fase 2 | si te interesa el "por qué Q6_K" |
| [03_iteraciones_540/](03_iteraciones_540/) | v1 → v14 del bench Carter 540 con causas | si te interesa "cómo iteramos" |
| [04_vram_y_hardware/](04_vram_y_hardware/) | VRAM real medida + selector por hardware | si tu hardware no es 16 GB |
| [05_latencia_y_alexa_tier/](05_latencia_y_alexa_tier/) | p50/p90/p99 + compliance Alexa-tier | si te interesa la velocidad |
| [06_consolidacion_tools/](06_consolidacion_tools/) | 60 → 16 tools composite (Anthropic best practice) | si Carter va a escalar tools |
| [07_audio_y_vision/](07_audio_y_vision/) | Bloque D + estado mmproj real | si querés audio/vision en Carter |
| [08_investigacion_externa/](08_investigacion_externa/) | ~40 fuentes oficiales citadas (Google/llama.cpp/Anthropic) | si querés verificar claims |
| [09_arquitectura_decisiones/](09_arquitectura_decisiones/) | 14 decisiones técnicas con justificación medida | si vas a defender el stack |
| [10_carter_integration/](10_carter_integration/) | Plan de migración + 30 valores Carter cumplidos | si vas a integrar a Carter |

### Visual

| Carpeta | Contenido |
|---|---|
| [graficos/](graficos/) | 16 PNG comparativos generados con matplotlib |
| [datos_crudos/](datos_crudos/) | JSONs y CSV originales referenciados |

### 🧭 Router de tools (subsistema)

| Documento | Tema |
|---|---|
| [router/](router/) | ⭐ **Carpeta completa del router** — punto de entrada único para entenderlo |
| [router/README.md](router/README.md) | Visión general, estado actual, arranque rápido |
| [router/01_ARQUITECTURA.md](router/01_ARQUITECTURA.md) | El pipeline de 6 capas, diagrama de flujo por turno |
| [router/02_COMPONENTES.md](router/02_COMPONENTES.md) | Cada módulo y artefacto de datos, con su receta de regeneración |
| [router/03_GATES_Y_CONFIG.md](router/03_GATES_Y_CONFIG.md) | Todas las env vars `GEMMA4_*` con default y efecto |
| [router/04_EVAL_Y_METRICAS.md](router/04_EVAL_Y_METRICAS.md) | Corpus, `router_eval.py`, métricas y gates de éxito |
| [router/05_HISTORIAL_SPRINTS.md](router/05_HISTORIAL_SPRINTS.md) | S0–S6 con resultados medidos |
| [router/06_PENDIENTE_Y_NO_FORZADO.md](router/06_PENDIENTE_Y_NO_FORZADO.md) | Lo diferido/rechazado con su medición + lo que sigue |
| [PLAN_MAESTRO_router.md](PLAN_MAESTRO_router.md) | Plan maestro original del programa router |

---

## 🖼️ Tour visual rápido

### El proyecto en 1 imagen
![Cobertura de las 3 fases](graficos/14_cobertura_fases.png)

### El ganador
![Selector hardware](graficos/15_selector_hardware.png)

### Cómo se llegó al 100%
![Progresión v1-v14](graficos/06_progresion_v1_v14.png)

### Las 22 cuantizaciones evaluadas
![Fase 2 modelos](graficos/01_fase2_22_modelos.png)

### Consolidación de tools (clave para escalabilidad Carter)
![Consolidated vs individual](graficos/08_consolidated_vs_individual.png)

### Por qué consolidación importa
![Escalabilidad](graficos/09_escalabilidad_tools.png)

---

## 📊 Los 16 gráficos generados

| # | Archivo | Tema |
|---:|---|---|
| 01 | `01_fase2_22_modelos.png` | Score 60 tests sobre las 22 cuantizaciones |
| 02 | `02_fase2_top8_desglose.png` | Top 8 modelos desglosados por bloque A/B/C |
| 03 | `03_vram_por_modelo.png` | VRAM real medida con nvidia-smi |
| 04 | `04_gemma_vs_qwen_patrones.png` | E4B-Q6_K vs qwen3:4b por patrón |
| 05 | `05_latencia_categoria_540.png` | p50/p90/p99 por categoría en Carter 540 |
| 06 | `06_progresion_v1_v14.png` | Iteración v1 → v14 con anotaciones |
| 07 | `07_categorias_v14_540.png` | PASS rate por categoría en v14 final |
| 08 | `08_consolidated_vs_individual.png` | Tools 60 vs 16 — métricas comparativas |
| 09 | `09_escalabilidad_tools.png` | Proyección escalabilidad 60 → 200 tools |
| 10 | `10_audio_gemma_vs_whisper.png` | Bloque D audio: Gemma vs Whisper |
| 11 | `11_consolidated_v1_v6.png` | Iteración consolidated 6 versiones |
| 12 | `12_vulkan_vs_cuda.png` | Backend comparison |
| 13 | `13_causas_raiz_fails.png` | Pie chart de tipos de fail v1-v14 |
| 14 | `14_cobertura_fases.png` | Esfuerzo total — Fase 1 / 2 / 3 |
| 15 | `15_selector_hardware.png` | Modelo recomendado por VRAM |
| 16 | `16_30_valores_carter.png` | Cumplimiento 30 valores Carter |

---

## 📁 Datos crudos disponibles

`datos_crudos/`:

- `fase2_summary.json` — Score consolidado de las 22 cuantizaciones (60 tests cada una)
- `vram_real_medida.csv` — VRAM con nvidia-smi por modelo
- `carter540_v14_GANADOR.json` — Bench Carter 540 v14 = 540/540 medido
- `carter540_consolidated_v6.json` — Bench con 16 tools composite
- `baseline_qwen3-4b_60tests.json` — Comparación con modelo actual Carter
- `audio_blockD_E4B.json` — Resultados Bloque D audio
- `schemas_60_individuales.json` — Catálogo legacy
- `schemas_16_consolidated.json` — Catálogo composite

---

## 🗓️ Historia del proyecto en orden cronológico

| # | Hito | Output |
|---:|---|---|
| 1 | Investigación inicial Gemma 4 (cuál descargar, cómo correrlo) | `chat_gemma.py` + 7 cuantizaciones E2B/E4B |
| 2 | Fase 1: 10 tests inicial sobre Gemma 4 | [REPORTE.md](../docs/REPORTE.md) |
| 3 | Descarga y prueba de 22 cuantizaciones (E2B, E4B, 26B, 31B) | `models/` ~335 GB |
| 4 | Bench Fase 2: 60 tests × 22 modelos + qwen3:4b baseline | [REPORTE_EXTENDIDO.md](../docs/REPORTE_EXTENDIDO.md) |
| 5 | Bloque D audio con TTS español-MX | [INFORME_AUDIO_PARA_CARTER.md](../docs/INFORME_AUDIO_PARA_CARTER.md) |
| 6 | Migración Vulkan → CUDA b9090 (decisión arquitectural) | resultados/ con CUDA |
| 7 | Bench Fase 3: Carter 540 sobre el ganador, iteraciones v1-v14 | `harness_carter540/results/` |
| 8 | Consolidación 60 → 16 tools composite | `harness_carter540/tool_schemas_consolidated.json` |
| 9 | Iteración consolidated v1 → v6 hasta 540/540 | `harness_carter540/results/consolidated_*` |
| 10 | Lectura de [ContextoCarter.md](../docs/ContextoCarter.md) (30 valores) | mapping de evidencia a valores |
| 11 | Investigación profunda fuentes oficiales (40+ links) | [08_investigacion_externa/](08_investigacion_externa/) |
| 12 | Reporte definitivo final | [REPORTE_GEMMA4_PARA_CARTER.md](../docs/REPORTE_GEMMA4_PARA_CARTER.md) |
| 13 | Paquete entregable agente Carter | `evidencia pruebas gemma4/` |
| 14 | Esta documentación visual y trackeable | `documentacion/` |

---

## 🔗 Referencias a archivos fuera de esta carpeta

| Archivo | Propósito |
|---|---|
| [docs/Contrato.md](../docs/Contrato.md) | Contrato original (10 tests / capacidades) |
| [docs/GEMMA4_VALIDACION_COMPLETA.md](../docs/GEMMA4_VALIDACION_COMPLETA.md) | Doc autoritativo del bench Fase 2 |
| [docs/ContextoCarter.md](../docs/ContextoCarter.md) | 30 valores de Carter v4/v5 |
| [docs/REPORTE.md](../docs/REPORTE.md) | Fase 1 — 10 tests inicial |
| [docs/REPORTE_EXTENDIDO.md](../docs/REPORTE_EXTENDIDO.md) | Fase 2 — 60 tests × 22 modelos |
| [docs/INFORME_AUDIO_PARA_CARTER.md](../docs/INFORME_AUDIO_PARA_CARTER.md) | Audio nativo Gemma 4 vs Whisper |
| [docs/REPORTE_GEMMA4_PARA_CARTER.md](../docs/REPORTE_GEMMA4_PARA_CARTER.md) | ⭐ Reporte definitivo final |
| [chat_gemma.py](../chat_gemma.py) | Chat conversacional simple sin tools |
| [chat_carter.py](../chat_carter.py) | Chat con tools REALES Windows (no stubs) |
| [scripts/watch.py](../scripts/watch.py) | Live watcher de benches en curso |
| [scripts/download_all.ps1](../scripts/download_all.ps1) | Descarga las 22 cuantizaciones |
| [evidencia pruebas gemma4/](../evidencia%20pruebas%20gemma4/) | Paquete entregable agente Carter |

---

## 🛠️ Cómo regenerar esta documentación

Si modificás los datos en `results/` o `harness_carter540/results/`:

```powershell
python "C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\documentacion\generar_graficos.py"
```

Regenera los 16 PNG con los datos actuales. Los .md son estáticos (escritos a mano).

---

## ✅ Estado final

- [x] 540/540 medido y reproducible con E4B-Q6_K
- [x] 540/540 reproducible con 16 composite tools
- [x] VRAM medida para 22 cuantizaciones
- [x] Latencia medida en CUDA
- [x] Comparativa vs qwen3:4b (mismo modelo Carter actual)
- [x] Audio Bloque D ejecutado y documentado
- [x] 30 valores Carter mapeados a evidencia
- [x] 40+ fuentes oficiales citadas
- [x] Paquete entregable agente Carter
- [x] 16 gráficos comparativos generados
- [x] Documentación visual y trackeable

**Misión cumplida.** El próximo paso lo hace el agente Carter en su repo.
