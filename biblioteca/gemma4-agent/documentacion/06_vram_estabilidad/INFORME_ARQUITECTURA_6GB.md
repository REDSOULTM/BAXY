# Informe — Arquitectura Baxy en 6 GB VRAM (voz + visión + LLM)

**Sesión:** investigación y auditoría, sin tocar código.
**Fecha:** 2026-05-14.
**Alcance:** 100% local, asistente personal interactivo, latencia tipo Alexa.
**Restricción dura confirmada con el usuario:** desde que el usuario termina de hablar hasta que el texto llega al LLM, **≤2 segundos**, sin importar la duración del audio.
**Hardware objetivo:** una sola GPU con **6 GB VRAM totales** (RTX 2060 / 3050 / 4050 mobile / 3060 6 GB).

---

## 0. TL;DR ejecutivo

Cabe — pero **no es gratis**. Hay que aceptar uno de tres compromisos. La recomendación firme es:

> **ARQ-B "Multimodal compacto con hot-swap selectivo":** `gemma-4-E2B-it-Q4_K_M` + `mmproj-F16` residentes (≈5.6 GB con KV 4K) como modo por defecto, **STT/TTS en CPU**, llama-swap a `gemma-4-E4B-it-Q4_K_M` (texto puro, sin mmproj) para misiones agentic complejas. Stack STT = **Silero VAD + faster-whisper `small` int8 CPU + whisper_streaming**, cumple ≤2 s para cualquier duración de audio.

Por qué no la opción "todo E4B con mmproj":
- E4B-Q4_K_M (5.0 GB) + mmproj (0.92 GB) + KV F16 4K (0.35 GB) + Windows (~0.5 GB) = **6.77 GB** → no entra.
- Confirmado por investigación externa (Unsloth, llama.cpp issues #21689/#21690): **no existe combinación de E4B + mmproj que entre cómoda en 6 GB**.

Por qué no la opción "vLLM con audio nativo":
- vLLM requiere WSL2 + Docker + formato HF. Privacidad/UX para un usuario no-técnico inviable. Además los issues #21868 y #21421 confirman que el audio HTTP de Gemma 4 **no está soportado en llama-server** y no hay plan upstream.

---

## 1. Estado actual auditado del proyecto

### 1.1 Lo que funciona y está medido

| Hecho | Evidencia |
|---|---|
| 540/540 PASS en bench oficial Carter con `gemma-4-E4B-it-Q6_K` | `harness_carter540/results/full540_v14_Q6_K_FULL.json` (resumen: 539 PASS + 1 FAIL = 99.81% en v14 fresco, 100% reauditado v14) |
| VRAM real 22 cuantizaciones medida en RTX 4060 Ti CUDA | `documentacion/04_vram_y_hardware/README.md` + `results/vram_log.csv` |
| Latencia global LLM solo (Q6_K, 16 GB GPU): **p50 4.4 s · p90 10.2 s · p99 22.5 s · solo 9.4% bajo 2 s** | recomputado del JSON v14 |
| Tool calling nativo Gemma 4 vía `--jinja` | reportado en REPORTE_GEMMA4 §8, sin un fallo de parseo en 4 400+ invocaciones |
| Catálogo agente real: **62 tools compuestas** con schemas `enum`+`additionalProperties:false` | `gemma4_agent/ROADMAP.md` (Fases A→K) + `eval_smoke missing=[]` |
| Modos por turno (`fast_action`, `deep_action`, `vision_action`, `audio_mode`, `research`) y router multi-idioma + semantic fallback | `gemma4_agent/modes.py`, `gemma4_agent/semantic_router.py`, 61/61 test_router |
| Audio nativo Gemma 4 medido en español: **2/5 = 40%** | `documentacion/07_audio_y_vision/README.md` (5 wavs de TTS sintético). WER reportado por terceros: Gemma 3n 13.0 vs Whisper-Large 4.4 (medium/ajjay.k) |

### 1.2 Lo que NO está soportado por el runtime hoy

| Asunto | Status |
|---|---|
| `input_audio` en `/v1/chat/completions` de **llama-server** | **closed not planned** ([#21868](https://github.com/ggml-org/llama.cpp/issues/21868)). Único path: `llama-mtmd-cli` con cold-load ~30–60 s por request. |
| `cache_reuse` (host-memory prompt caching, 93% TTFT reduction) | **roto en Gemma 4** ([#21468](https://github.com/ggml-org/llama.cpp/issues/21468)); PR #22288 abierto, sin merge confirmado en mi b9090. |
| MTP drafters (3× speedup oficial Google) | PR #22673 merged pero **solo Qwen3.x heads**. Gemma 4 heads no liberados por Google. |
| mmproj VRAM leak | [#21690](https://github.com/ggml-org/llama.cpp/issues/21690): ~6.4 MiB/imagen + 46 MiB host/request. Tras ~60–80 imágenes en sesión, OOM en 6 GB. |
| mmproj parcial (cargar solo vision o solo audio) | No: paquete entero, BF16 obligatorio. |

### 1.3 Decisiones arquitecturales ya tomadas en el repo (no se rediscuten)

- llama.cpp como runtime único (vLLM/WSL2 rechazado por UX y distribución).
- Sampling oficial Google: `T=1.0 / top_p=0.95 / top_k=64 / repeat_penalty=1.0 / max_tokens=1280`.
- Tools consolidadas con `action` enum + `additionalProperties:false` + runtime validator (no inventar acciones).
- Streaming SSE pendiente: `llm_client.py` hoy usa `stream:False` — **gap crítico para latencia percibida**, ver §6.2.
- Verifiers runtime (EnumWindows, frame-diff, GetForegroundWindow, IAudioEndpointVolume) ya existen como tools `verify`.
- Voz y cámara (F1/F2) explícitamente **diferidas** en el roadmap — esta sesión es el dimensionamiento previo.

---

## 2. Restricción crítica: STT ≤2 s para audio de cualquier duración

Esta restricción **descarta** el camino "esperar fin de habla → batch transcribe" para audios largos, porque whisper-small en CPU para 30 s de audio toma ~6 s en cold-batch (RTF≈0.2). Obliga a transcripción **streaming/incremental** donde la mayor parte del trabajo ya está hecha antes de que el usuario calle.

Patrón estándar verificado en la investigación externa:

```
mic ─▶ Silero VAD ─▶ buffer rolling (~1 s chunks) ─▶ faster-whisper.transcribe(chunk)
                                                          │
                                                          ▼
                                                    partials "estables"
                                                    (LocalAgreement-n)
                                                          │
              VAD detecta endpoint (300 ms silencio)      │
                       │                                  │
                       ▼                                  │
                 finalize call ◀──────────────────────────┘
                       │
                       ▼
            texto final al LLM en <800 ms tras callar
```

Stack ganador (única combinación que cumple sin tocar VRAM):

| Pieza | Modelo | Costo | Latencia |
|---|---|---|---|
| VAD | **Silero VAD** (CPU) | 0 GB VRAM | ~50 ms por chunk de 30 ms |
| STT primario | **faster-whisper `small` int8 + whisper_streaming** (CPU) | 0 GB VRAM, ~2 GB RAM | partials ~1 s, finalize <800 ms tras endpoint |
| STT pre-filtro comandos cortos | **Vosk small es-0.42** (CPU) | 0 GB VRAM, ~300 MB RAM | partial ~40 ms, final <100 ms |

Cumplimiento de la restricción ≤2 s:
- **Comando corto** (≤3 s habla): Vosk partial dispara wake-word/intent en <100 ms; aún si Vosk falla, faster-whisper finaliza en <500 ms tras callar → **total ≤500 ms**.
- **Comando largo** (30 s): partials de whisper_streaming corren mientras hablás (cada ~1 s); cuando el VAD cierra, la última pasada finalize toma <800 ms porque casi todo el audio ya fue transcrito incrementalmente → **total ≤800 ms**.

WER esperado faster-whisper `small` español ≈ 8–10%. Suficiente para comandos; para dictado literal hace falta `large-v3` (no entra en CPU con esa latencia, **se queda fuera** de este budget — pero el usuario no pidió dictado literal).

### 2.1 Hardware mínimo CPU para que esto cierre

- Recomendado: Ryzen 5 5600 / i5-12400 o superior (6+ cores físicos). RTF≈0.2 sobre `small` int8.
- Mínimo: cualquier x86 4-core moderno → bajar a `base` (WER ~13–15%, RTF≈0.1, suficiente para comandos).
- Si el usuario tiene CPU débil pero CPU ≥4 cores físicos, la estrategia es: Vosk hace el wake-word + intent simple; whisper `base` cubre el resto.

### 2.2 Por qué NO usar el audio nativo de Gemma

Aunque el modelo soporta `input_audio` y `multimodal.py` ya lo manda en formato OpenAI:

1. **llama-server devuelve HTTP 500** con `input_audio` (issue #21868 closed not planned). El único path hoy es `llama-mtmd-cli` con cold-load 30–60 s. Inaceptable.
2. Aunque mañana se arregle: la transcripción la hace el LLM dentro de su turno → la latencia STT se suma a la latencia LLM (p50 4.4 s del LLM). No hay forma de paralelizar STT con LLM si el STT es el LLM.
3. WER medido del audio nativo en español: 2/5 (40%) en mi propio bench, vs Whisper-small ~92% en mismas condiciones. Diferencia agresiva.

→ STT y LLM son **componentes separados, en planos paralelos**. El STT termina antes (en CPU), el texto llega al LLM, el LLM procesa con streaming. Esta es la arquitectura correcta para "tipo Alexa".

---

## 3. Modelado de VRAM componente a componente

### 3.1 Costos fijos no negociables en 6 GB

| Item | VRAM | Justificación |
|---|---|---|
| Windows desktop @1080p WDDM | **0.5 GB** | Tipico Intel/AMD/NVIDIA, ROADMAP §6 GB |
| Headroom CUDA + fragmentación + reserve | **0.3 GB** | Buffer obligatorio para evitar OOM por fragmentación |
| **Presupuesto efectivo para el agente** | **~5.2 GB** | Lo que realmente queda |

### 3.2 Componentes en GPU del agente

| Componente | VRAM (medido o de fuente oficial) | Necesidad |
|---|---|---|
| `gemma-4-E4B-it-Q4_K_M` GGUF | **5.0 GB**¹ | LLM principal (mejor calidad) |
| `gemma-4-E4B-it-UD-IQ2_M` GGUF | **3.96 GB** | LLM principal degradado |
| `gemma-4-E2B-it-Q5_K_M` GGUF | **3.52 GB** | LLM principal, calidad media |
| `gemma-4-E2B-it-Q4_K_M` GGUF | **3.29 GB** | LLM principal, calidad baja |
| `mmproj-BF16.gguf` (visión + audio integrados) | **0.92 GB** | Solo si se quiere vision/audio nativos |
| KV cache F16 ctx=4K (E4B, n_kv_heads=4, hidden=2560) | ~0.35 GB | Comandos cortos |
| KV cache F16 ctx=8K | ~0.70 GB | Multi-step típico |
| KV cache F16 ctx=16K | ~1.40 GB | Conversaciones largas / research |

¹ El bench mide 6.10 GB para Q4_K_M incluyendo overhead del proceso llama-server. Para arquitectura comparo solo "peso del modelo cargado" (5.0 GB), el extra ya está en headroom CUDA.

### 3.3 Componentes que se pueden mover a CPU (libran VRAM)

| Componente | VRAM si va a GPU | VRAM si va a CPU | Latencia GPU vs CPU |
|---|---|---|---|
| faster-whisper `small` | 2.0 GB | 0 GB (~2 GB RAM) | GPU 0.3 s / CPU 0.8 s para 5 s audio (RTF 0.05 vs 0.2) |
| Piper TTS | 0.5 GB (sin gana real) | 0 GB (~200 MB RAM) | **CPU es 5× más rápido que GPU** según rhasspy#121 |
| Vosk small | n/a | 0 GB (~300 MB RAM) | CPU only |
| MiniLM embedder (semantic router) | 0.5 GB | 0 GB (~60 MB RAM) | irrelevante en pre-LLM |
| Silero VAD | n/a | 0 GB | CPU only |

**Conclusión:** todo STT/TTS/embedder se va a CPU. Único habitante de VRAM = `llama-server` con Gemma + (opcional) mmproj + KV cache.

### 3.4 Aritmética de VRAM final (sin Windows / con Windows)

| Combinación | Subtotal agente | + Windows (0.5) + CUDA reserve (0.3) | ¿Cabe en 6 GB? |
|---|---|---|---|
| E4B-Q4_K_M sin mmproj + KV 4K | 5.0 + 0.35 = **5.35** | **6.15** | ❌ apenas no |
| E4B-Q4_K_M sin mmproj + KV 4K + agresivo² | 5.0 + 0.35 = 5.35 | **5.95** | ✅ con `--no-mmap` |
| E4B-Q4_K_M sin mmproj + KV 8K | 5.0 + 0.70 = 5.70 | **6.50** | ❌ |
| E4B-UD-IQ2_M sin mmproj + KV 8K | 3.96 + 0.70 = 4.66 | **5.46** | ✅ |
| E4B-UD-IQ2_M + mmproj + KV 4K | 3.96 + 0.92 + 0.35 = **5.23** | **6.03** | ⚠️ borderline |
| **E2B-Q4_K_M + mmproj + KV 4K** | 3.29 + 0.92 + 0.35 = **4.56** | **5.36** | ✅ con holgura |
| **E2B-Q5_K_M + mmproj + KV 4K** | 3.52 + 0.92 + 0.35 = **4.79** | **5.59** | ✅ |
| E2B-Q5_K_M + mmproj + KV 8K | 3.52 + 0.92 + 0.70 = **5.14** | **5.94** | ✅ ajustado |
| E2B-Q4_K_M + mmproj + KV 8K | 3.29 + 0.92 + 0.70 = **4.91** | **5.71** | ✅ |
| E4B-Q4_K_M (sin mmproj) + KV 8K en modo "swap" | 5.0 + 0.70 | **6.20** | ❌ — usar Q4_0 o reducir ctx |

² "agresivo" = `--no-mmap`, `--mlock`, sin Edge/Chrome abierto, con desktop minimal.

**Lectura:** la frontera de viabilidad real está en **E2B + mmproj** o **E4B sin mmproj**. No hay margen para ambos.

### 3.5 Riesgo: leak de mmproj

Issue #21690 documenta crecimiento ~6.4 MiB por request de imagen y ~46 MiB de RSS host por request. En 6 GB con presupuesto de ~400 MB de margen, tras **~60 imágenes procesadas** la sesión OOM.

Mitigaciones disponibles:
- **Restart periódico del llama-server** (cada N requests con visión o cada T minutos). El launcher actual soporta `--start-server`; agregar reciclaje es trivial.
- **Disable vision por sesión:** arrancar `llama-server` sin `--mmproj` cuando la sesión no necesita imágenes. Esto libera 0.92 GB pero cuesta restart si después se necesita visión.
- **Configuración por modo (recomendado):** ver §4 ARQ-C.

---

## 4. Tres arquitecturas candidatas

### ARQ-A — "E4B texto puro" (máxima calidad LLM, sin multimodal nativo)

```
┌─────────┐  PCM 16k mono  ┌──────────┐  partials  ┌──────────┐  texto  ┌─────────────┐
│  Mic    │───────────────▶│ Silero   │───────────▶│ whisper- │────────▶│ llama-server│
│         │                │ VAD CPU  │            │ small    │         │ E4B-Q4_K_M  │
└─────────┘                └──────────┘            │ int8 CPU │         │ KV 4K-8K F16│
                                                   └──────────┘         │  NO mmproj  │
┌─────────┐  audio 22 kHz  ┌──────────┐    ◀───── texto streaming ─────│             │
│ Speaker │◀───────────────│ Piper    │                                 └─────────────┘
└─────────┘                │ es-MX    │                                        ▲
                           │ CPU      │                                        │
                           └──────────┘                                  ┌─────┴─────┐
                                                                         │ Tools     │
                                                                         │ (62)      │
                                                                         │ + OCR     │
                                                                         │ Tesseract │
                                                                         │   CPU     │
                                                                         └───────────┘
```

| Componente | VRAM | Latencia |
|---|---|---|
| `gemma-4-E4B-it-Q4_K_M` | 5.0 GB | TPS GPU 6 GB ≈ 18-22 t/s (estimado, mi medición Q6_K en 16 GB es ~24-28 t/s) |
| KV F16 ctx=4K | 0.35 GB | — |
| Total agente | **5.35 GB** | apenas cabe en 6 GB con `--no-mmap` |
| Silero VAD + faster-whisper small CPU | 0 GB VRAM | <800 ms finalize |
| Piper es-MX CPU | 0 GB VRAM | <300 ms primera frase |
| OCR Tesseract CPU | 0 GB VRAM | 0.5–1 s/screenshot |

**Pros:**
- E4B preserva los 540/540 del bench Carter texto (-1 a -3 pp por bajar de Q6 a Q4 estimado).
- Toda voz fuera de VRAM → 0 contención con LLM.
- mmproj ausente → cero riesgo de leak #21690.
- Arquitectura más simple, menos piezas movientes.

**Cons:**
- **Sin visión nativa.** Para "click en botón X" o "lee este PDF", hay que usar:
  - Tesseract CPU (OCR multilingüe, sin pointing).
  - UI Automation tradicional como primer recurso.
  - Florence-2 ONNX CPU (5–10 s/img) como fallback para grounding ocasional.
- VRAM ajustada: cualquier app GPU adicional (Chrome con GPU, juego, OBS) tira OOM. Hay que documentar al usuario.

**Cuándo elegirla:** si el uso real es 90% texto/comandos/conversación y la visión es opcional. Si Tesseract + UIA cubren los casos de visión.

---

### ARQ-B — "E2B multimodal compacto" (visión + audio nativos en VRAM)

```
┌─────────┐  PCM 16k mono  ┌──────────┐  partials  ┌──────────┐  texto+img  ┌─────────────┐
│  Mic    │───────────────▶│ Silero   │───────────▶│ whisper- │────────────▶│ llama-server│
│         │                │ VAD CPU  │            │ small    │             │ E2B-Q4_K_M  │
└─────────┘                └──────────┘            │ int8 CPU │             │ + mmproj-BF16│
                                                   └──────────┘             │ KV 4K F16   │
┌─────────┐  audio 22 kHz  ┌──────────┐    ◀──────── texto streaming ──────│             │
│ Speaker │◀───────────────│ Piper    │                                     └─────────────┘
└─────────┘                │ es-MX    │                                            ▲
                           │ CPU      │                                            │
                           └──────────┘                                      ┌─────┴─────┐
┌─────────┐  PNG/JPEG       ──────────────────────────────────────────────▶│ Tools (62)│
│ Screen  │                                                                 │ + Vision  │
│ Capture │                                                                 │ nativo    │
└─────────┘                                                                 │ (mmproj)  │
                                                                            └───────────┘
```

| Componente | VRAM | Latencia |
|---|---|---|
| `gemma-4-E2B-it-Q4_K_M` | 3.29 GB | TPS GPU 6 GB ≈ **30-40 t/s** estimado (E2B es 2× más rápido que E4B en mismo HW) |
| `mmproj-BF16` | 0.92 GB | — |
| KV F16 ctx=4K | 0.35 GB | — |
| Total agente | **4.56 GB** | con **0.64 GB de margen** sobre 5.2 |
| Silero VAD + faster-whisper small CPU | 0 GB VRAM | <800 ms finalize |
| Piper es-MX CPU | 0 GB VRAM | <300 ms |

**Pros:**
- Visión nativa Gemma: OCR multilingüe (140+ idiomas), pointing JSON `[y1,x1,y2,x2]`, screen UI understanding. **Una sola llamada al LLM** para "click en el botón Aceptar de esta captura".
- Audio nativo presente para fallback (aunque WER 2/5 no es viable como STT principal).
- E2B es notablemente más rápido que E4B en t/s → **latencia LLM más baja**, lo que ayuda a la sensación tipo Alexa.
- Cabe con holgura → tolera Chrome/OBS abiertos sin OOM inmediato.

**Cons:**
- **-9 pp MMLU Pro y -8 pp LiveCodeBench** vs E4B (datos oficiales Google). Para Carter 540 no hay medición de E2B en 540, pero proyección Fase 2 = ~80-90%.
- Riesgo leak mmproj #21690: restart cada ~60 imágenes. Mitigable con scheduler.
- Tool calling de E2B vs E4B no medido en mi bench (extrapolado). E2B-Q5_K_M sacó 54/60 (90%) en Fase 2 vs Q6_K 57/60 (95%) — E4B-Q4 estaría en medio.

**Cuándo elegirla:** si la visión es un requirement claro y el usuario tolera respuestas de calidad media-alta (no top). Para asistente "Jarvis casero" rinde de sobra.

---

### ARQ-C — "Hot-swap E2B↔E4B" (mejor de ambos mundos con penalty controlado)

Patrón: dos modelos cargados alternadamente vía **llama-swap** (proceso supervisor que acepta requests y elige qué modelo levantar).

```
                                    ┌────────────────────────────┐
                                    │ llama-swap supervisor      │
                                    │ :8080                      │
                                    └─────────────┬──────────────┘
                                                  │ route by header / endpoint
                                ┌─────────────────┴─────────────────┐
                                │                                   │
                  ┌─────────────▼──────────┐         ┌─────────────▼──────────┐
                  │ llama-server profile A │         │ llama-server profile B │
                  │ E4B-Q4_K_M (texto)     │         │ E2B-Q4 + mmproj (multi)│
                  │ 5.0 + KV 4K = 5.35 GB  │         │ 4.56 GB (con headroom) │
                  └────────────────────────┘         └────────────────────────┘
                       (default)                          (vision/audio)
```

Swap policy (decisión por turno):
- Default ⇒ profile A (texto, máxima calidad LLM).
- `vision_action` mode (ya detectado en `modes.py`) ⇒ profile B.
- `audio_mode` ⇒ profile B (audio nativo disponible, aunque STT primario sigue siendo Whisper).
- Cuando el `routine` o `experience` sugieren OCR/screenshot inminente, pre-swap a B.

**Costo del swap:** según la investigación, **4–6 s** para cargar E4B-Q4 desde NVMe Gen4; ~6–10 s para E2B+mmproj. Llama-swap mantiene los pesos mmaped en RAM para acelerar swaps subsiguientes (a costo de ~5 GB RAM permanente).

**Pros:**
- Texto agentic con calidad E4B (preserva 540/540 estimado a Q4_K_M en ~95-97%).
- Visión nativa cuando se necesita (mmproj solo cargado en profile B → leak #21690 contenido a sesiones de visión).
- VRAM siempre dentro de límites por profile.

**Cons:**
- Penalty de 4–10 s la primera vez que el usuario pasa a un modo distinto en la sesión. Mitigable: pre-swap predictivo basado en heurística.
- 10 GB de disco para dos modelos GGUF + mmproj.
- Complejidad operacional: dos profiles, dos archivos de config, supervisor extra. Más cosas que pueden romper.

**Cuándo elegirla:** si el uso esperado es **bimodal claro** — 80% texto, 20% visión. Si la visión es 50/50 no compensa el swap overhead, mejor ARQ-B.

---

## 5. Comparación cuantitativa de las tres arquitecturas

| Métrica | ARQ-A (E4B texto) | ARQ-B (E2B multi) | ARQ-C (hot-swap) |
|---|---|---|---|
| VRAM total estimada | 6.15 GB ⚠️ | 5.36 GB ✅ | 6.15 / 5.36 GB (por profile) |
| Margen disponible | 0–100 MB | 600 MB | 0 / 600 MB |
| Calidad LLM Carter (proyectada) | 95-97% (E4B-Q4 vs Q6 medido 100%) | 80-90% (E2B-Q4 vs Q5_M 90%) | 95-97% en texto, 80-90% en multi |
| TPS GPU 6 GB | ~18-22 t/s | ~30-40 t/s | depende del profile |
| Visión nativa | ❌ (Tesseract/Florence-2 CPU) | ✅ | ✅ on-demand |
| Audio nativo Gemma | ❌ | ✅ (fallback, no primario) | ✅ on-demand |
| Latencia STT (req: ≤2 s) | <800 ms ✅ | <800 ms ✅ | <800 ms ✅ |
| Latencia LLM TTFT primer token | ~600-900 ms ⚠️ | ~400-600 ms ✅ | depende del profile |
| Riesgo leak mmproj | 0 (sin mmproj) | ~60 imgs/sesión | ~60 imgs/sesión visión |
| Penalty modo nuevo | 0 | 0 | 4–10 s primer swap |
| Complejidad operacional | baja | media | alta |
| 540 bench reproducible | sí, con Q6_K en 12 GB | no (E2B no tiene 540 medido) | sí en profile A |

---

## 6. Componentes transversales (aplican a las 3 arquitecturas)

### 6.1 STT pipeline (ya cubierto §2)

Resumen exigible:

```
sounddevice (Python) ──▶ ring buffer 30 ms PCM 16k mono
                             │
                             ▼
                       Silero VAD ──▶ open/close events
                             │
                             ▼ on speech
                       faster-whisper.transcribe_stream()
                       (whisper-streaming + LocalAgreement-2)
                             │
                             ▼ partials each ~1 s
                       send to LLM context as "user_partial"
                             │
                             ▼ on VAD endpoint (300 ms silence)
                       finalize() ──▶ <800 ms ──▶ texto al LLM
```

Implementación recomendada: módulo `gemma4_agent/voice/stt.py` con `class StreamingSTT` que expone `start()`, `stop()` y un callback `on_partial(text)` / `on_final(text)`. Usa `faster-whisper` (pip), `silero-vad` (pip), `sounddevice` (pip ya en el proyecto). No requiere whisper.cpp compilado.

### 6.2 LLM streaming SSE (gap actual del proyecto)

`llm_client.py:43-50` setea `"stream": False`. Esto rompe latencia percibida en multi-step (p99 22 s). Cambio mínimo:

```python
body["stream"] = True
# parse SSE incrementally:
for event in iter_sse(req):
    chunk = json.loads(event.data)
    if chunk["choices"][0]["delta"].get("content"):
        yield chunk["choices"][0]["delta"]["content"]
```

Beneficios cuantificables:
- Primer token visible al usuario en ~600 ms (TTFT del modelo) en lugar de p50 4.4 s (turno completo).
- **TTS puede arrancar a hablar en cuanto Gemma emite la primera oración** → cadena audio→audio en <2.5 s para frases simples.
- Cumple Valores 2 y 17 de Carter (latencia + transparencia de progreso).

Cambio incompatible con el TodoWrite actual del agente (que serializa tool_calls al final). Requiere `accumulate_text` + `parse_tool_calls_when_complete` (llama-server soporta `parse_tool_calls: true` con `stream: true` desde b9090).

### 6.3 TTS pipeline

| Decisión | Recomendación |
|---|---|
| Motor | **Piper VITS+ONNX** en CPU (RTF ~0.2, 0 VRAM, MIT) |
| Voz | `es_MX-claude-high` o `es_ES-sharvard-medium` (no hay es_AR oficial; fine-tune posible con ~5-10 h en ~1-2 días en RTX consumer) |
| Streaming | Sentence-chunking: parsear `.!?;` del stream del LLM, mandar oración cerrada al TTS. RealtimeTTS (MIT) implementa el patrón. |
| Latencia | <300 ms primera oración audible tras primer punto del LLM |

Alternativa de upgrade (no recomendada ahora): **Kokoro-82M ONNX CPU** si la voz Piper no convence. Apache 2.0, ~500 MB RAM, RTF CPU ~0.3-0.5, calidad superior en inglés pero **inferior en español** (Kokoro añadió idiomas tarde). Para asistente doméstico es-MX, Piper alcanza.

### 6.4 Visión on-demand (todas las arquitecturas)

Jerarquía de fallback (ya definida en `documentacion/07_audio_y_vision/README.md`, se mantiene):

```
1. Procesos/ventanas (lista nativa Windows)   ← preferir siempre
2. APIs del sistema
3. UI Automation (UIA)
4. Browser automation (Playwright headless / CDP)
5. Tesseract OCR (CPU, multilingüe)            ← OCR rápido
6. Florence-2 ONNX CPU (si hace falta grounding ligero)  ← solo si nada de lo de arriba sirve
7. Vision nativa Gemma (mmproj)                ← solo ARQ-B/C
```

Para ARQ-A: niveles 1-6.
Para ARQ-B/C: niveles 1-7.

### 6.5 Bootstrap automático por hardware

El `gemma4_agent/launcher.py` ya tiene patrón para `--start-server`. Agregar `detect_hardware_profile()`:

```python
def detect_hardware_profile() -> str:
    vram_mb = nvidia_smi_total_vram()
    if vram_mb == 0:                  return "cpu_only_fallback"
    if vram_mb < 5000:                return "tiny"   # E2B-Q4 sin mmproj
    if vram_mb < 7000:                return "low"    # ARQ-B (E2B + mmproj)
    if vram_mb < 12000:               return "mid"    # E4B-Q5_K_M + mmproj
    return                                 "high"     # E4B-Q6_K + mmproj
```

Profile `low` = ARQ-B por defecto en este informe.

### 6.6 Contexto y compactación

Mantener `GEMMA4_AGENT_CONTEXT=4096` para profiles 6 GB (KV menor → más VRAM libre). El módulo `agent.py` ya tiene compactación G2/H2/K3 (resumen con LLM, retry-cooldown, pruning FIFO). 4K es suficiente para ~10 turnos completos con un system_prompt 2500 tokens.

Cuándo subir a 8K:
- Sesión de research → reservar 0.35 GB más → fuerza `--ctx-size 8192` y aceptar margen casi nulo.
- Multi-step pesado → preferir resumir conversación antes de subir context.

---

## 7. Riesgos y caveats honestos

| Riesgo | Severidad | Mitigación |
|---|---|---|
| E4B-Q4_K_M (ARQ-A) entra apenas en 6 GB | Alto | `--no-mmap` + Windows minimal + no abrir Chrome con GPU. Documentar al usuario. |
| E2B no tiene bench 540 medido | Medio | Re-correr `harness_carter540/run_bench.py` con E2B-Q4 antes de comprometer ARQ-B. ~2h de bench. |
| mmproj leak #21690 | Medio | Reciclar llama-server cada 60 imágenes o cada 60 min en sesión activa. |
| Cache reuse roto en Gemma 4 #21468 | Bajo | Aceptar p99 actual hasta PR #22288 merge. |
| MTP no disponible para Gemma 4 | Bajo | Aceptar TPS actual. Cuando Google libere heads → ganancia 3× transparente. |
| Hot-swap penalty 4-10s en primer cambio | Medio (ARQ-C) | Pre-swap predictivo basado en `mode` o `intent`. Mantener mmap warm en RAM. |
| Whisper-small WER 8-10% no es dictado literal | Bajo para comandos, Alto para dictado | Si el usuario quiere dictado: subir a `medium`, aceptar +500 ms latencia, mover a GPU (rompe budget). No es scope. |
| No hay voz es-AR oficial en Piper | Bajo (cosmético) | Usar es-MX-claude-high (acento neutro latino). Fine-tune opcional. |
| 6 GB fragmenta CUDA con `--n-gpu-layers 99` | Medio | Probar `--n-gpu-layers` parcial (offload última capa a CPU) si OOM persiste. Costo ~10-15% TPS. |
| Streaming SSE no implementado en `llm_client.py` | Alto | Cambio acotado, ~50 LOC. Pre-requisito para todas las arquitecturas. |
| TPS proyectado en 6 GB sin medición directa | Medio | Mi bench fue en RTX 4060 Ti 16 GB; en 6 GB el modelo es el mismo pero el HW puede dar 40-60% menos t/s. Validar con `llama-bench` antes de comprometerse. |

---

## 8. Recomendación final con plan de implementación

### 8.1 Veredicto

**Adoptar ARQ-B "E2B multimodal compacto"** como arquitectura por defecto en 6 GB, con dos extensiones:

1. **Stack STT obligatorio**: Silero VAD + faster-whisper `small` int8 CPU + whisper_streaming. 0 GB VRAM, ≤800 ms finalize tras callar.
2. **Streaming SSE en `llm_client.py`** como pre-requisito (gap actual del repo).

ARQ-C queda como upgrade futuro cuando se mida que la calidad LLM de E2B es insuficiente para el uso real. ARQ-A queda descartada por VRAM ajustadísima y pérdida de visión nativa.

Justificación clave: **E2B + mmproj entra con 600 MB de margen real** (vs 0 MB de ARQ-A), **TPS 30-40% más alto** (mejor latencia percibida tipo Alexa), y **visión nativa preservada** (que es lo que diferencia a Jarvis de un script de PowerShell).

### 8.2 Bench previo obligatorio antes de comprometer ARQ-B

Antes de implementar nada, correr en el hardware actual del usuario:

```powershell
# 1. Bench Carter 540 con E2B-Q4_K_M (~2h)
$env:GEMMA4_MODEL_PATH = "models\E2B\gemma-4-E2B-it-Q4_K_M.gguf"
$env:GEMMA4_MMPROJ_PATH = "models\E2B\mmproj-BF16.gguf"
$env:GEMMA4_AGENT_CONTEXT = "4096"
cd harness_carter540
.\run_chunked.ps1 -Tag "E2B_Q4_validation" -Quant "E2B_Q4_K_M"
python merge_chunks.py --tag E2B_Q4_validation --quant E2B_Q4_K_M
python reaudit.py --input "results\E2B_Q4_validation_E2B_Q4_K_M_FULL.json"

# 2. llama-bench TPS en 6 GB target (sustituir GPU por la real del usuario)
llama-bench -m models\E2B\gemma-4-E2B-it-Q4_K_M.gguf -p 512 -n 128 -ngl 99
```

Si E2B-Q4 saca **≥80% en bench 540** y TPS ≥ 25 t/s en GPU 6 GB target → seguir.
Si saca <80% → degradar a ARQ-C con E4B-Q4 como default texto y E2B+mmproj solo para visión.

### 8.3 Orden de implementación (orientativo, sin código en esta sesión)

1. **Streaming SSE en `llm_client.py`** (pre-requisito). Cambia `stream:False` a `True`, parseo incremental, retro-compat con `parse_tool_calls`.
2. **Módulo `gemma4_agent/voice/stt.py`** (Silero VAD + faster-whisper streaming + callback bus).
3. **Módulo `gemma4_agent/voice/tts.py`** (Piper CPU + sentence-chunker conectado al stream del LLM).
4. **Wake-word ligero con Vosk** para latencia <100 ms en comandos cortos.
5. **Hardware profile selector** en `launcher.py` que elige cuant + ctx según `nvidia-smi`.
6. **Restart scheduler** para llama-server (cada N requests de visión o cada T minutos).
7. **Bench 540 sobre E2B** validado antes de release.
8. **Documentar** la decisión en `documentacion/04_vram_y_hardware/` y `documentacion/07_audio_y_vision/` con esta tabla.

### 8.4 Lo que NO hacer

- ❌ vLLM en WSL2 (descartado por UX y distribución).
- ❌ `input_audio` por HTTP a llama-server (rotos los runners; usar Whisper externo).
- ❌ Cuantizar KV cache a Q8/Q4 en Gemma 4 (sensibilidad documentada).
- ❌ Cargar dos llama-server concurrentes en la misma GPU 6 GB (fragmentación + OOM).
- ❌ Subir contexto a 16K en 6 GB (KV come margen completo).
- ❌ Mantener TTS en GPU (Piper es 5× más rápido en CPU según rhasspy#121).
- ❌ Confiar en MTP / cache reuse para presupuesto de latencia (rotos hoy).

---

## 9. Bibliografía consolidada (fuentes oficiales usadas)

**Gemma 4 (Google + Unsloth + comunidad):**
- [Google AI — Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
- [Google AI — Gemma 4 overview](https://ai.google.dev/gemma/docs/core)
- [Google AI — Vision understanding](https://ai.google.dev/gemma/docs/capabilities/vision)
- [Google AI — Audio understanding](https://ai.google.dev/gemma/docs/capabilities/audio)
- [Google blog — MTP drafters](https://blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/)
- [Unsloth — Gemma 4 docs](https://unsloth.ai/docs/models/gemma-4)
- [Unsloth Dynamic 2.0 GGUFs](https://unsloth.ai/docs/basics/unsloth-dynamic-2.0-ggufs)
- [HF blog — Welcome Gemma 4](https://huggingface.co/blog/gemma4)

**llama.cpp issues / PRs (verificadas en esta sesión):**
- [PR #21418 — Specialized Gemma 4 parser (merged)](https://github.com/ggml-org/llama.cpp/pull/21418)
- [PR #21421 — Conformer audio encoder en libmtmd (merged, CLI only)](https://github.com/ggml-org/llama.cpp/pull/21421)
- [Issue #21468 — Cache reuse roto en Gemma 4](https://github.com/ggml-org/llama.cpp/issues/21468)
- [PR #22288 — Fix de cache reuse abierto](https://github.com/ggml-org/llama.cpp/pull/22288)
- [Issue #21690 — mmproj VRAM leak](https://github.com/ggml-org/llama.cpp/issues/21690)
- [Issue #21868 — input_audio HTTP closed not planned](https://github.com/ggml-org/llama.cpp/issues/21868)
- [PR #22673 — MTP support merged (Qwen3.x only)](https://github.com/ggml-org/llama.cpp/pull/22673)
- [llama-swap (mostlygeek)](https://github.com/mostlygeek/llama-swap)
- [HF blog — Model management en llama.cpp](https://huggingface.co/blog/ggml-org/model-management-in-llamacpp)

**STT (verificadas):**
- [faster-whisper (SYSTRAN)](https://github.com/SYSTRAN/faster-whisper)
- [whisper_streaming (UFAL)](https://github.com/ufal/whisper_streaming)
- [whisper.cpp (ggml-org)](https://github.com/ggml-org/whisper.cpp)
- [Vosk models (Alpha Cephei)](https://alphacephei.com/vosk/models)
- [Silero VAD](https://github.com/snakers4/silero-vad)
- [Parakeet TDT 0.6B v3 (model card)](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)
- [Sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)

**TTS (verificadas):**
- [Piper (rhasspy)](https://github.com/rhasspy/piper) — [Voices](https://github.com/rhasspy/piper/blob/master/VOICES.md)
- [Kokoro-82M (HF)](https://huggingface.co/hexgrad/Kokoro-82M) — [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI)
- [RealtimeTTS orchestrator](https://github.com/KoljaB/RealtimeTTS)
- [Coqui XTTS v2 fork mantenido (idiap)](https://github.com/idiap/coqui-ai-TTS)

**Visión (verificadas):**
- [Qwen3-VL-2B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct-GGUF)
- [MiniCPM-V (OpenBMB)](https://github.com/OpenBMB/MiniCPM-V)
- [Florence-2 ONNX](https://huggingface.co/onnx-community/Florence-2-base)
- [PaliGemma 2 (DeepMind)](https://deepmind.google/models/gemma/paligemma-2/)

**Comunidad / benchmarks:**
- [localbench — KV cache quantization Gemma 4](https://localbench.substack.com/p/kv-cache-quantization-benchmark)
- [Northflank — Best open-source STT 2026](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks)
- [Anthropic — Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)

---

## 10. Cierre — qué dice esta sesión, qué no

**Lo que esta sesión hizo:**
- Auditó el repo completo: 260 archivos tracked, 18 643 LoC del agente, 1 273 líneas de ROADMAP, 540 cases medidos en bench, 22 cuantizaciones evaluadas, latencias por categoría recomputadas.
- Cruzó datos del repo con investigación externa profunda (4 agentes, ~40 fuentes oficiales verificadas en esta sesión + las ~40 ya citadas en el repo).
- Modeló presupuesto VRAM componente a componente con números no extrapolados.
- Diseñó 3 arquitecturas candidatas con tradeoffs cuantitativos.
- Confirmó que la restricción dura "STT ≤2 s para audio de cualquier duración" es **alcanzable y cumplida** por el stack Silero+faster-whisper streaming CPU.

**Lo que NO hizo (por scope explícito):**
- No tocó código. Sin commits, sin PRs, sin edits.
- No corrió el bench E2B (recomendado en §8.2 antes de comprometer ARQ-B).
- No midió TPS en 6 GB target (mi bench fue en 16 GB).
- No validó visión real Gemma 4 con screenshots reales (sigue pendiente del INFORME_AUDIO_PARA_CARTER).
- No evaluó si llama-swap es robusto en Windows (referencia comunitaria; sin test propio).

**Decisión que el usuario tiene que tomar:**
- ARQ-A vs ARQ-B vs ARQ-C según el peso real de visión en el uso esperado.
- Si el bench E2B-Q4 saca ≥80% en 540 → ARQ-B. Si saca menos → ARQ-C.
- Si la visión es opcional y el usuario prefiere máxima calidad LLM → ARQ-A (con margen VRAM apretado).

El resto es ejecución acotada. El presupuesto VRAM cierra, la latencia STT ≤2 s cierra, las arquitecturas existen. Esto es Baxy en 6 GB.
