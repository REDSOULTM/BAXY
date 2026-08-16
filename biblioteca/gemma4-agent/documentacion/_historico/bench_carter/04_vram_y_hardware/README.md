# 04 — VRAM y selector de hardware

VRAM real medida con `nvidia-smi --query-gpu=memory.used` durante el bench, en RTX 4060 Ti 16 GB.

---

## VRAM cargado por modelo (medido, no estimado)

![VRAM por modelo](../graficos/03_vram_por_modelo.png)

Incluye: pesos del modelo + mmproj F16 (vision/audio) + KV cache 16K context + overhead llama.cpp.

### Tabla completa

| Modelo | VRAM cargado | Delta del modelo |
|---|---:|---:|
| E2B-UD-Q2_K_XL | 4.08 GB | 2.91 GB |
| E2B-Q3_K_M | 4.21 GB | 3.04 GB |
| E2B-UD-Q3_K_XL | 4.29 GB | 3.12 GB |
| E2B-Q4_K_M | 4.46 GB | 3.29 GB |
| E2B-UD-Q4_K_XL | 4.54 GB | 3.36 GB |
| E2B-Q5_K_M | 4.70 GB | 3.52 GB |
| E4B-UD-IQ2_M | 5.13 GB | 3.96 GB |
| E4B-Q4_K_M | 6.10 GB | 4.97 GB |
| E4B-Q5_K_M | 6.61 GB | 5.44 GB |
| **E4B-Q6_K** ⭐ | **7.10 GB** | **5.94 GB** |
| E4B-Q8_0 | 8.16 GB | 6.98 GB |
| 31B-UD-IQ2_XXS | 7.95 GB | 6.78 GB |
| 26B-UD-IQ2_XXS | 9.24 GB | 8.07 GB |
| 26B-UD-IQ2_M | 9.33 GB | 8.16 GB |
| 26B-UD-Q2_K_XL | 9.82 GB | 8.65 GB |
| 31B-UD-IQ2_M | 10.01 GB | 8.84 GB |
| 31B-UD-Q2_K_XL | 10.97 GB | 9.80 GB |
| 26B-UD-Q3_K_M | 11.85 GB | 10.68 GB |
| 26B-UD-Q3_K_XL | 12.02 GB | 10.85 GB |
| 26B-UD-IQ4_XS | 12.66 GB | 11.49 GB |
| 31B-Q3_K_M | 13.72 GB | 12.55 GB |

---

## Selector hardware Carter (recomendación)

![Selector hardware](../graficos/15_selector_hardware.png)

El bootstrap de Carter detecta VRAM con `nvidia-smi` y elige automáticamente:

```python
def recommended_model() -> str:
    vram_mb = detect_vram_mb()
    if vram_mb == 0:           return "qwen3:4b (CPU fallback Ollama)"
    if vram_mb < 6000:         return "gemma-4-E2B-it-Q4_K_M.gguf"
    if vram_mb < 8000:         return "gemma-4-E4B-it-Q4_K_M.gguf"
    if vram_mb < 12000:        return "gemma-4-E4B-it-Q5_K_M.gguf"
    return                     "gemma-4-E4B-it-Q6_K.gguf"  # 12+ GB
```

| Perfil VRAM | Modelo elegido | mmproj | PASS proyectado | Estado |
|---|---|---|---|---|
| CPU only | qwen3:4b vía Ollama | — | ~70% | Fallback |
| <6 GB | E2B-Q4_K_M | Sin (sin vision/audio) | ~80-85% | Extrapolado |
| 6-8 GB | E4B-Q4_K_M | F16 | ~93-96% | Extrapolado |
| 8-12 GB | E4B-Q5_K_M | F16 | ~96-98% | Extrapolado |
| 12-16 GB | **E4B-Q6_K** | F16 | **100%** | **Medido** |
| 16+ GB | E4B-Q6_K | F16 | **100%** | **Medido** |

Solo el último renglón está medido. Los demás son extrapolaciones del bench Fase 2.

---

## Riesgos de cuantizaciones agresivas

Documentado en [localbench KV cache benchmark](https://localbench.substack.com/p/kv-cache-quantization-benchmark):

> "Gemma 4 26B-A4B es **el modelo más sensible a quantization tested**. q8_0 KV cache da KL 0.377 (vs Qwen <0.04)."

Por eso:
- **NO usar `--cache-type-k q8_0`** en Gemma 4 sin medir.
- **NO bajar de Q3** en modelos densos grandes (31B IQ2_XXS = 1/60 PASS).
- **Evitar** cuantizaciones IQ2_XXS de cualquier MoE — destruyen routing.

---

## Bug CUDA conocido en b9090

Issue observado en mi bench:
- `26B-UD-IQ2_XXS`: crash a mitad de chunk
- `31B-Q3_K_M`: crash en test 51
- `E2B-Q5_K_M`: crash en test 19 (recuperado en retry)

Patrón: cuantizaciones agresivas (IQ2/Q3) en modelos densos grandes con prompts largos. **E4B-Q6_K NO sufre este bug** en ninguna corrida.

Tracking upstream: [llama.cpp issue #21424](https://github.com/ggml-org/llama.cpp/issues/21424).
