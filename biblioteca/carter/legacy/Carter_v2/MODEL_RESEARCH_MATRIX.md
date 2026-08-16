# Carter Model Research Matrix (M1)

**Scope:** Modelos open-weight viables para Carter local. Fuentes prioritarias: cards
oficiales en Hugging Face, registry de Ollama, documentación de llama.cpp y
benchmarks técnicos públicos (LMArena, HELM, SWE-Bench, BigCodeBench, RULER, MMMU,
DocVQA) hasta **mayo 2026**.

> **Disclosure:** Esta sesión fue ejecutada sin acceso de red activo desde el agente.
> Las cifras de tamaño y cuantización marcadas ✔ provienen de inspección directa de
> los modelos ya instalados (`ollama list`, `nvidia-smi`). El resto se basa en model
> cards públicas conocidas a la fecha de la base de entrenamiento del agente; cuando
> un dato no es verificable se marca `UNKNOWN`. No se inventan métricas.

Leyenda:
- **VRAM** = Q4_K_M en GGUF + ctx típico (8k–16k) bajo llama.cpp / Ollama.
- **Tools** = soporte nativo de function/tool-calling vía OpenAI-compat (Ollama).
- **Vision** = capacidad multimodal de imagen.
- **License** simplificada; verificar antes de uso comercial.
- ✔ = instalado localmente y disponible para tournament hoy.

## 1. LLM texto general / razonamiento / tool-calling

| modelo | tipo | params | quant rec. | VRAM est. | ctx max | tools | visión | idioma | licencia | fuente | notas / instalado |
|---|---|---:|---|---:|---:|---|---|---|---|---|---|
| `qwen3:1.7b` | LLM | 1.7B | Q4_K_M | ~1.4 GB | 32k | sí | no | multi (ES/EN ok) | Apache 2.0 | HF Qwen/Qwen3-1.7B | ✔ Pequeño, fallback CPU/iGPU |
| `qwen3:8b` | LLM | 8B | Q4_K_M | ~6.8 GB | 128k | sí | no | multi | Apache 2.0 | HF Qwen/Qwen3-8B | ✔ Carter actual baseline |
| `qwen3:14b` | LLM | 14B | Q4_K_M | ~10–11 GB | 128k | sí | no | multi | Apache 2.0 | HF Qwen/Qwen3-14B | ✔ Mejor calidad razonamiento |
| `qwen2.5:32b-instruct-q4_K_M` | LLM | 32B | Q4_K_M | ~21 GB | 32k | sí | no | multi | Qwen License | Ollama lib | ✔ Solo perfil 24 GB+ |
| `qwen2.5-coder:14b-instruct-q4_K_M` | LLM código | 14B | Q4_K_M | ~10 GB | 32k | sí | no | EN, código | Apache 2.0 | HF Qwen/Qwen2.5-Coder-14B | ✔ Especialista código |
| `phi4:latest` | LLM | 14B | Q4 | ~9 GB | 16k | **no** (catálogo `_NO_TOOLS_MODELS`) | no | EN principal | MIT | HF microsoft/phi-4 | ✔ NO usar como backend Carter (sin tools) |
| `gemma3:12b` | LLM | 12B | Q4 | ~8 GB | 128k | **no** (Ollama runner) | sí (12B IT vision) | multi | Gemma TOS | HF google/gemma-3-12b-it | ✔ Solo texto/visión, no tools en Carter actual |
| `granite3.3:8b` | LLM | 8B | Q4 | ~5 GB | 128k | sí | no | EN/ES limitado | Apache 2.0 | HF ibm-granite/granite-3.3-8b-instruct | ✔ Tool-calling oficial |
| `devstral:24b` | LLM código + tools | 24B | Q4 | ~14 GB | 128k | sí | no | EN, código, agéntico | Apache 2.0 | Mistral/Devstral | ✔ Especialista agente código |
| `mistral-small:24b` (no instalado) | LLM | 24B | Q4 | ~14 GB | 32k | sí | no | multi | Apache 2.0 | Mistral | UNKNOWN_NOT_TESTED |
| `llama3.1:8b` (no instalado) | LLM | 8B | Q4 | ~5 GB | 128k | sí | no | multi | Llama 3 CL | Meta | UNKNOWN_NOT_TESTED |
| `llama3.3:70b` (no instalado) | LLM | 70B | Q4 | ~42 GB | 128k | sí | no | multi | Llama 3 CL | Meta | Solo 48 GB+ → fuera de scope Carter |
| `gpt-oss:20b` (no instalado) | LLM | 20B | Q4 | ~12 GB | 128k | sí | no | multi | Apache 2.0 | OpenAI gpt-oss | UNKNOWN_NOT_TESTED |
| `nemotron-nano-9b` (no instalado) | LLM | 9B | Q4 | ~6 GB | 128k | sí | no | multi | NVIDIA OL | NVIDIA | UNKNOWN_NOT_TESTED |
| `qwen3:4b` (no instalado) | LLM | 4B | Q4_K_M | ~2.6 GB | 32k | sí | no | multi | Apache 2.0 | HF Qwen/Qwen3-4B | Recomendable bajar para perfil 6 GB |

## 2. VLM / Visión

| modelo | params | VRAM est. | tareas | OCR | grounding | licencia | fuente | instalado |
|---|---:|---:|---|---|---|---|---|---|
| `moondream:latest` | 1.8B | ~1.8 GB | describe pequeñas | mediocre | no | Apache 2.0 | vikhyatk/moondream2 | ✔ Ideal CPU/iGPU/6GB |
| `minicpm-v:latest` | 8B | ~5.5 GB | describe + OCR | bueno | parcial | OpenBMB CL | OpenBMB MiniCPM-V 2.6 | ✔ |
| `llava:7b` | 7B | ~5 GB | describe genérico | mediocre | no | Apache 2.0 | liuhaotian/llava-1.5-7b | ✔ Carter actual `describe_image` |
| `llava-llama3:latest` | 8B | ~5.5 GB | describe + razonamiento | mediocre | no | Llama 3 CL | xtuner/llava-llama-3-8b | ✔ |
| `qwen2.5vl:7b` | 7B | ~6 GB | describe + grounding boxes | bueno | **sí** | Qwen License | HF Qwen/Qwen2.5-VL-7B-Instruct | ✔ Carter actual `find_element` |
| `qwen2.5vl:32b` (no instalado) | 32B | ~22 GB | top-tier visión | excelente | sí | Qwen License | HF Qwen/Qwen2.5-VL-32B | UNKNOWN_NOT_TESTED |
| `gemma3:12b` (vision) | 12B | ~8 GB | describe + OCR | bueno | parcial | Gemma TOS | HF google/gemma-3-12b-it | ✔ Doble uso texto+visión |
| `internvl2.5:8b` (no instalado) | 8B | ~5 GB | describe + OCR | bueno | parcial | MIT | HF OpenGVLab/InternVL2_5-8B | UNKNOWN_NOT_TESTED |

## 3. OCR / document understanding (no LLM)

| herramienta | tipo | dependencias | GPU | licencia | notas |
|---|---|---|---|---|---|
| `pytesseract` | OCR clásico | Tesseract 5 binario | no | Apache 2.0 | ✔ ya disponible en Carter; baseline |
| `easyocr` | OCR DL | PyTorch | sí (mejora) | Apache 2.0 | UNKNOWN_NOT_TESTED |
| `paddleocr` | OCR DL | PaddlePaddle | sí | Apache 2.0 | UNKNOWN_NOT_TESTED |
| `omniparser` | UI parser | PyTorch | sí | MIT (Microsoft) | ✔ probe-only en Carter (`vision_router._probe_status`) |

## 4. STT / transcripción

| modelo | tamaño | VRAM/RAM | latencia stream | idiomas | licencia | fuente |
|---|---|---:|---|---|---|---|
| `whisper.cpp tiny` | 39M | <0.5 GB RAM | ~1.5× RT CPU | multi | MIT | ggml-org/whisper.cpp |
| `whisper.cpp base` | 74M | <0.7 GB RAM | ~1× RT CPU | multi | MIT | mismo |
| `whisper.cpp small` | 244M | ~1 GB | ~0.6× RT CPU / ~0.2× RT GPU | multi | MIT | mismo |
| `whisper.cpp medium` | 769M | ~2.5 GB | 0.3× RT GPU | multi | MIT | mismo |
| `whisper.cpp large-v3` | 1.55B | ~6 GB | 0.15× RT GPU | multi (90+) | MIT | mismo |
| `faster-whisper large-v3` | 1.55B | ~5 GB | streaming | multi | MIT | guillaumekln/faster-whisper |
| `distil-whisper-large-v3` | 756M | ~3 GB | streaming | EN/multi | MIT | distil-whisper |
| `nvidia parakeet-tdt-0.6b` | 0.6B | ~2 GB | streaming | EN | CC-BY-4.0 | nvidia/parakeet-tdt-0.6b-v2 |

## 5. TTS

| modelo | tamaño | latencia | idiomas | licencia | notas |
|---|---|---|---|---|---|
| `Piper` (rhasspy) | 25–60 MB | <300 ms first audio en CPU | multi (ES, EN, +30) | MIT | Recomendado CPU/embedded |
| `coqui-XTTSv2` | ~1.8 GB | ~600 ms first audio GPU | multi 17 + voice cloning | CPML (no comercial) | Voz natural, restricción licencia |
| `kokoro-82M` | 82M | <200 ms CPU | EN principal, ES limitado | Apache 2.0 | Excelente perfil bajo |
| `Edge-TTS` (Microsoft) | cloud | nube | multi | Microsoft TOS | NO local, descartado por privacidad |

## 6. Modelos pequeños CPU / iGPU

| modelo | params | RAM | tools | uso |
|---|---:|---:|---|---|
| `qwen3:1.7b` Q4 | 1.7B | ~1.5 GB | sí | ✔ baseline CPU |
| `phi-3.5-mini-instruct` Q4 | 3.8B | ~2.5 GB | parcial | UNKNOWN_NOT_TESTED |
| `llama3.2:3b` Q4 | 3B | ~2 GB | sí | UNKNOWN_NOT_TESTED |
| `gemma3:1b` Q4 | 1B | ~1 GB | no | UNKNOWN_NOT_TESTED |

---

## 7. Decisiones derivadas (input para M2 / M9 / M11)

1. **Carter en Ollama solo aprovecha tool-calling con familias compatibles** (`qwen3*`, `qwen2.5*`, `granite3.3*`, `devstral*`, `llama3.1+`). `phi4`, `gemma3`, `llava*`, `moondream`, `minicpm-v` quedan **prohibidos como backend de chat** y se mantienen como VLM/texto puro on-demand.
2. **Visión:** `qwen2.5vl:7b` para grounding sigue siendo SOTA local en 6 GB; `llava:7b` puede sustituirse por `minicpm-v:latest` (mejor OCR, mismo presupuesto).
3. **STT:** `faster-whisper-large-v3` cuando sobre VRAM (≥12 GB), `whisper.cpp small` para 6–8 GB, `whisper.cpp tiny/base` CPU.
4. **TTS:** `Piper` por defecto (cubre ES + EN, latencia mínima, MIT). `XTTSv2` opcional GPU para naturalidad sin cloning.
5. Carter NUNCA carga simultáneamente: `qwen3:14b + qwen2.5vl:7b + faster-whisper-large-v3` (suma > 22 GB). Política de unload obligatoria.
6. **Reserva de mediciones reales** se hará en M11 sobre los 12 modelos texto ya instalados (sin descargas).
