# 05 — Latencia y compliance Alexa-tier

Latencias medidas en RTX 4060 Ti 16 GB CUDA con E4B-Q6_K v14.

---

## Latencia por categoría (Carter 540, v14)

![Latencias por categoría](../graficos/05_latencia_categoria_540.png)

| Cat | Nombre | p50 | p90 | p99 | max | avg |
|---|---|---:|---:|---:|---:|---:|
| C01 | Saludos | 1.84s | 6.20s | 7.49s | 8.30s | 2.75s |
| C02 | Identidad | 5.19s | 9.02s | 10.70s | 11.14s | 6.05s |
| C03 | Conocimiento | 3.83s | 7.88s | 9.69s | 10.62s | 4.63s |
| C04 | Memoria | 2.88s | 7.25s | **18.38s** | 35.38s | 5.05s |
| C05 | Apps duales | 3.36s | 6.66s | 8.56s | 8.73s | 4.17s |
| C06 | Sistema | 3.30s | 8.70s | 11.78s | 12.94s | 4.62s |
| C07 | Apps | 4.01s | 11.62s | 15.08s | 18.14s | 5.80s |
| C08 | Web | 5.00s | 11.64s | 14.53s | 15.53s | 6.12s |
| C09 | Steam | 4.98s | 16.55s | **25.06s** | 28.33s | 7.88s |
| C10 | Filesystem | 5.42s | 10.69s | 18.34s | 20.64s | 6.92s |
| C11 | Terminal | 4.26s | 8.48s | 13.06s | 14.78s | 5.11s |
| C12 | Destructive | 3.39s | 9.19s | 9.62s | 9.73s | 4.61s |
| C13 | GUI | 6.11s | 12.92s | 13.94s | 19.00s | 7.04s |
| C14 | Multi-step | 9.25s | 14.92s | **20.45s** | 27.42s | 10.16s |
| C15 | Typos | 3.80s | 16.64s | 19.00s | 19.06s | 6.64s |
| C16 | Phonetic | 3.42s | 7.94s | 8.90s | 12.17s | 4.37s |
| C17 | Conversación | 3.53s | 7.89s | 9.64s | 13.80s | 4.60s |
| C18 | Multi-turn | 4.01s | 13.41s | 14.86s | 15.90s | 5.90s |
| **GLOBAL** | | **4.26s** | **11.25s** | **20.45s** | 35.38s | **5.69s** |

---

## Compliance Alexa-tier (targets del Contrato Carter)

| Bucket | p50 | p99 | Target | p50 OK | p99 OK |
|---|---:|---:|---:|:---:|:---:|
| Trivial | 3.81s | 16.64s | <5s | ✅ | ❌ |
| Tool simple | 3.53s | 14.78s | <8s | ✅ | ❌ |
| App open | 4.91s | 25.06s | <15s | ✅ | ❌ |
| Multi-step | 6.84s | 20.64s | <20s | ✅ | ⚠️ marginal |

**Lectura honesta:** p50 cumple Alexa-tier en todas las categorías. **p99 fuera de target** en todas.

Significa que el caso típico (mediana) cumple, pero el peor 1% no. En producción Carter:
- **Usuario común percibirá 4-6s** la mayoría de interacciones.
- **1 de cada 100 turnos puede tomar 15-25s.** Necesita streaming + UI progress para que no se sienta colgado.

---

## Mitigaciones documentadas

### 1. Streaming SSE (la más impactante)

llama-server soporta `stream: true` en `/v1/chat/completions`. Carter debe wire SSE chunks:
- Primer token visible en ~500ms en lugar de esperar p99 final.
- Estados intermedios: "Buscando ventana de WhatsApp...", "Llamando a app_open...".

### 2. Multi-Token Prediction drafters (futuro)

[Google blog MTP](https://blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/): **3× speedup** sin pérdida calidad. Disponible en vLLM, MLX, Ollama, SGLang. **NO disponible en llama.cpp stable** todavía. Cuando llegue: ganancia transparente.

### 3. Reducir context dinámicamente

Carter ya usa `num_ctx` adaptable según intent:
- Saludos: `-c 4096`
- Tool simple: `-c 8192`
- Misión compuesta: `-c 16384`

KV cache crece linealmente con context. Bajar context cuando no se necesita reduce latencia.

### 4. Prompt caching host-memory

Issue [#20574 llama.cpp](https://github.com/ggml-org/llama.cpp/discussions/20574) habilita 93% TTFT reduction para prefix cacheado. **Pero issue [#21468](https://github.com/ggml-org/llama.cpp/issues/21468)** documenta que **NO funciona en Gemma 4 todavía** (Shared KV Cache architecture). PR #22288 abierto. Carter debe aceptar p99 actual hasta que se mergee.

---

## Vulkan vs CUDA — backend importa

![Vulkan vs CUDA](../graficos/12_vulkan_vs_cuda.png)

Mi bench inicial corrió en Vulkan (winget llama.cpp default). Después migré a CUDA b9090 build ai-dock. Resultado: **CUDA es 30-40% más rápido en NVIDIA**.

Decisión: para Carter en hardware NVIDIA, **siempre CUDA build de llama.cpp**, no Vulkan.

---

## Outliers identificados

### C04 Memoria max 35s
Modelo entró en loop con "olvida mi preferencia" en algún caso. Resuelto en system_prompt v3 con regla explícita "olvida mi X → memory_delete(key=X) DIRECTO sin list previo".

### C09 Steam p99 25s
Multi-step con vision escalation: `gui_deeplink(steam) + screenshot + locate + click`. Cada step suma. Es comportamiento correcto del modelo, pero acumula latencia. Carter debe mostrar progreso por step.

### C14 Multi-step p99 20s
Misiones de 4+ tools (HEAVY-2: read+open+type+write). Cada turno del modelo + verificación = naturalmente lento.
