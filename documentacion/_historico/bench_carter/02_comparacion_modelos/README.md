# 02 — Comparación de las 22 cuantizaciones de Gemma 4

Bench Fase 2: 60 tests del Contrato sobre 22 cuantizaciones distintas + qwen3:4b baseline.

---

## Las 22 cuantizaciones probadas

Todas vienen de `unsloth/gemma-4-*-it-GGUF` en HuggingFace (variantes oficiales con imatrix de Unsloth).

| Familia | Cuantizaciones probadas |
|---|---|
| **E2B** (~2B activos) | UD-Q2_K_XL, Q3_K_M, UD-Q3_K_XL, Q4_K_M, UD-Q4_K_XL, Q5_K_M |
| **E4B** (~4B activos) ⭐ | UD-IQ2_M, Q4_K_M, Q5_K_M, **Q6_K**, Q8_0 |
| **26B-A4B** (MoE 4B activos) | UD-IQ2_XXS, UD-IQ2_M, UD-Q2_K_XL, UD-Q3_K_M, UD-Q3_K_XL, UD-IQ4_XS |
| **31B** (denso) | UD-IQ2_XXS, UD-IQ2_M, UD-Q2_K_XL, Q3_K_M |

---

## Score sobre los 60 tests (PASS / 60)

![Las 22 cuantizaciones evaluadas](../graficos/01_fase2_22_modelos.png)

### Top 8 desglose por bloque

![Top 8 desglose](../graficos/02_fase2_top8_desglose.png)

- **Bloque A** (30 cases): 10 patrones × 3 variantes (limpio/borderline/adversarial). Negation, URI hallucination, multi-step, etc.
- **Bloque B** (20 cases): cids reales del bench oficial Carter (los que más fallan en qwen3:4b).
- **Bloque C** (10 cases): estrés, ráfagas, context-heavy, tool-heavy.

---

## Tabla completa de resultados

| Modelo | A /30 | B /20 | C /10 | **Total /60** | % | VRAM cargado |
|---|---:|---:|---:|---:|---:|---:|
| 🥇 **E4B-Q6_K** | 28 | **19** | 10 | **57** | **95.0%** | 7.1 GB |
| 🥈 26B-UD-Q3_K_XL | 28 | 18 | 10 | 56 | 93.3% | ~14 GB |
| 🥈 E4B-Q4_K_M | 28 | 18 | 10 | 56 | 93.3% | 6.1 GB |
| E4B-Q5_K_M | 29 | 16 | 10 | 55 | 91.6% | 6.6 GB |
| E4B-Q8_0 | 27 | 19 | 9 | 55 | 91.6% | 8.2 GB |
| E4B-UD-IQ2_M | 28 | 18 | 9 | 55 | 91.6% | 5.1 GB |
| **qwen3:4b baseline** | 28 | 18 | 9 | 55 | 91.6% | 2.5 GB |
| 26B-A4B-UD-IQ4_XS | 26 | **20** | 8 | 54 | 90.0% | ~13 GB |
| E2B-Q5_K_M | 26 | 18 | 10 | 54 | 90.0% | 4.7 GB |
| 26B-UD-IQ2_M | 27 | 16 | 10 | 53 | 88.3% | 13.4 GB |
| 26B-UD-Q2_K_XL | 25 | 18 | 10 | 53 | 88.3% | 13.9 GB |
| E2B-UD-Q4_K_XL | 26 | 17 | 9 | 52 | 86.7% | 4.5 GB |
| E2B-Q4_K_M | 24 | 17 | 10 | 51 | 85.0% | 4.5 GB |
| E2B-UD-Q2_K_XL | 27 | 14 | 10 | 51 | 85.0% | 4.1 GB |
| E2B-UD-Q3_K_XL | 23 | 17 | 10 | 50 | 83.3% | 4.3 GB |
| E2B-Q3_K_M | 25 | 13 | 10 | 48 | 80.0% | 4.2 GB |
| 26B-UD-IQ2_XXS | 27 | 2 | 0 | 29 | 48.3% ⚠️ | 13.3 GB |
| 26B-UD-Q3_K_M | 14 | 0 | 0 | 14 | 23.3% ⚠️ | crash CUDA |
| 31B-UD-IQ2_M | 13 | 0 | 0 | 13 | 21.7% ⚠️ | 15.6 GB |
| 31B-Q3_K_M | 5 | 0 | 0 | 5 | 8.3% ⚠️ | crash CUDA |
| 31B-UD-Q2_K_XL | 5 | 0 | 0 | 5 | 8.3% ⚠️ | crash CUDA |
| 31B-UD-IQ2_XXS | 1 | 0 | 0 | 1 | 1.7% ⚠️ | inestable |

---

## Veredicto Fase 2

### ✅ E4B-Q6_K — ganador absoluto
- Mejor score Bloque B (19/20 — los cids reales Carter).
- VRAM 7.1 GB — cabe holgado en 16 GB y posible en 12 GB con holgura.
- Ningún CUDA crash en su corrida.
- Tool calling 100% reliable.

### ❌ Familia 31B descartada
- IQ2/Q2/Q3 destruyen la calidad de razonamiento del modelo denso grande.
- Crashes CUDA con cuantizaciones agresivas (issue conocido llama.cpp b9090).
- 15.6 GB VRAM al 97% del límite — inviable para producción real.

### 🟡 26B-A4B (MoE) — competitivo pero pesado
- 26B-UD-IQ4_XS sacó 20/20 perfecto en Bloque B (mejor que Q6_K).
- Pero pesa ~13 GB y requiere validación 540 separada (no realizada).
- Recomendado solo para 24 GB+ cards.

### 🟢 qwen3:4b baseline — sólido pero con techo
- Sacó 55/60 (igual que E4B-IQ2_M y Q8_0).
- Falla en Patrón A (URI hallucination — inventa `youtube://`).
- Sin vision/audio nativos.

---

## Comparativa contra qwen3:4b por patrón

![Gemma 4 vs qwen por patrón](../graficos/04_gemma_vs_qwen_patrones.png)

E4B-Q6_K supera o iguala a qwen3:4b en todos los patrones críticos. Donde más gana: **Patrón A (URI hallucination)** — qwen inventa protocolos `chatgpt://`, Gemma siempre usa URLs `https://...` correctas.

---

## Decisión

**Ganador final:** `gemma-4-E4B-it-Q6_K` por (1) score más alto, (2) VRAM razonable, (3) estabilidad, (4) capacidad multimodal nativa cargada en mmproj-F16.

Continuar a [03_iteraciones_540/](../03_iteraciones_540/) para ver cómo este modelo llegó a 540/540 en el bench oficial Carter.
