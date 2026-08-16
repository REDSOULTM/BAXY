# Carter v4 — Investigación arquitectónica multimodal Gemma 4 E4B (UD-IQ2_M)
**Fecha de investigación:** 9 de mayo de 2026
**Objetivo:** Decidir cómo y cuándo activar audio + vision de `gemma-4-E4B-it-UD-IQ2_M` en Carter v4 sobre `llama-server` CUDA, RTX 4060 Ti 16 GB, Windows 11.

---

## TL;DR

- **Activá vision YA, mantené Whisper para audio, y aplicá sólo ~25 % del Stage 1 defensive del reporte Opus.** Vision via `llama-server --mmproj` está production-ready hoy y resuelve casos reales (verificación post-acción, lectura de diálogos, captcha). Audio nativo de Gemma 4 sobre `llama-server` está **bloqueado en el upstream** (issue #21868 cerrado "not planned" en mayo 2026): mantené Whisper-large-v3 + Gemma 4 separados, no es más lento de lo que sería una integración nativa hoy.
- **No reemplaces PaddleOCR todavía**: Gemma 4 E4B-IQ2 hace OCR razonable pero es ~5-15× más lento y la quant IQ2_M degrada texto chico; usalo como **Tier-3 fallback semántico** ("¿qué dice este diálogo?"), no como OCR de producción. Usá Gemma 4 vision específicamente para **verificación visual post-acción** (reemplaza opcionalmente al frame-diff numpy en casos donde `==` de pixeles falla por animación) y para **comprensión de UI no triviales**.
- **Texto: cambios mínimos.** El sampling de Google (temp=1.0, top_p=0.95, top_k=64) ya está usado; el único cambio accionable es **forzar el chat-template oficial actualizado de Google** vía `--chat-template-file gemma-4-E4B-it/chat_template.jinja` y `--jinja`, deshabilitar `<|think|>` por default en tool-calling (latencia), y reducir `num_predict` a 768 para tools (de 1024). El 91.7 % PASS no requiere reescribir el Stage 1 defensive: patrones A/L/J cerrados estructuralmente; sólo conservar **anti-eco + destructive-stems multilingüe + verifier rewrite** (~200 LOC de los 800 originales).

---

## 1) Estado del ecosistema runners HTTP (mayo 2026)

| Runner | Texto Gemma 4 E4B | Image input HTTP | **Audio input HTTP** | Tool-calling HTTP | GGUF nativo | Notas críticas |
|---|---|---|---|---|---|---|
| **llama-server** (llama.cpp ≥ b8775) | ✅ producción | ✅ `image_url` (base64 / URL) | ❌ **500 server_error** (issue [#21868](https://github.com/ggml-org/llama.cpp/issues/21868), closed not-planned) | ✅ `--jinja` + parser `peg-gemma4` (PR [#21326](https://github.com/ggml-org/llama.cpp/pull/21326), [#21343](https://github.com/ggml-org/llama.cpp/pull/21343), [#21697](https://github.com/ggml-org/llama.cpp/pull/21697)) | ✅ | mmproj **debe ser BF16**; F16/Q8 causan repetitions (PR [#21421](https://github.com/ggml-org/llama.cpp/pull/21421)) |
| **llama-mtmd-cli** | ✅ | ✅ `--image` | ✅ `--audio` (PR #21421 merged b8766) | ❌ no expone HTTP | ✅ | **Cold-load por invocación → 20–60 s**, inviable Alexa-tier |
| **Ollama** | ✅ | ✅ vía `images:` array | ⚠️ El tag `gemma4:e4b` en biblioteca expone sólo `Text, Image input`. La librería ggml subyacente carga el audio encoder, pero la API HTTP no lo expone como `input_audio` y **el tag oficial no lista audio** en mayo 2026. | ✅ pero con bugs de parsing reportados | ✅ | Calidad ASR rioplatense reportada por usuario: 2/5 en TTS sintético |
| **vLLM** ([recipe](https://docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html)) | ✅ | ✅ | ✅ `--limit-mm-per-prompt '{"image":4,"audio":1}'` + `vllm[audio]` | ✅ `--tool-call-parser gemma4 --reasoning-parser gemma4` | ❌ requiere HF safetensors | Day-0 support oficial. WSL2 obligatorio en Windows; **no soporta GGUF UD-IQ2_M** → cambia el modelo |
| **LM Studio** | ✅ | ✅ | ❌ idem llama.cpp | ✅ | ✅ | Wrapper de llama.cpp; misma limitación audio |
| **Docker Model Runner (Win + WSL2)** | ✅ vLLM o llama.cpp | ✅ | ✅ con vLLM | ✅ | parcial | `ai/gemma4-vllm` ahora soportado en Windows 11 con NVIDIA GPU desde abril 2026 |

**PRs clave que tienen que estar en tu build** (`llama.cpp ≥ b8775` recomendado):
- [#21421 — Gemma 4 audio conformer encoder](https://github.com/ggml-org/llama.cpp/pull/21421) (mtmd + CLI)
- [#21326 — Gemma 4 chat template fix](https://github.com/ggml-org/llama.cpp/pull/21326) (tool calling)
- [#21343 — Gemma 4 tokenizer fix](https://github.com/ggml-org/llama.cpp/pull/21343) (`\n\n` token 108)
- [#21697 — reasoning budget fix](https://github.com/ggml-org/llama.cpp/pull/21697)
- [#21825 — webui audio crash fix](https://github.com/ggml-org/llama.cpp/issues/21825)
- [#21816 — E4B audio assert fix](https://github.com/ggml-org/llama.cpp/issues/21816)

**Honestidad por construcción:** el audio nativo Gemma 4 a través de `llama-server` (que es el runner que Carter ya tiene en :8080) **no funciona en mayo 2026** y el mantenedor cerró el ticket como "not planned". Usar audio nativo requiere o bien (a) cambiar de runner a vLLM en WSL2 (lo que rompe la quant fija UD-IQ2_M y suma 4–6 GB de overhead), o (b) usar `llama-mtmd-cli` con cold-load por request (inviable). **Whisper-large-v3 separado sigue siendo la decisión correcta hoy.**

---

## 2) Recomendación arquitectónica final

### Opción A — **PRIMARY: hybrid llama-server + Whisper + vision via mmproj**
**Stack exacto**
- `llama-server.exe` (b8775+ CUDA) `--model gemma-4-E4B-it-UD-IQ2_M.gguf --mmproj mmproj-BF16.gguf --jinja --chat-template-file gemma4_e4b_chat_template.jinja --port 8080 --n-gpu-layers 99 --flash-attn on --image-min-tokens 280 --image-max-tokens 560 --temp 1.0 --top-p 0.95 --top-k 64 --ctx-size 16384`
- `faster-whisper large-v3` (CTranslate2, INT8) en proceso Python aparte, modelo cacheado en RAM, GPU compartida.
- `Piper TTS` ES voice (`es_ES-davefx` o `es_AR-daniela-x_low` si está disponible) — ~30 MB CPU only, latencia <500 ms para 50 palabras.
- `openWakeWord` (ONNX) wake-word custom "ey carter" entrenado vía Piper sintético + Colab notebook (~1 hora). CPU only.
- `webrtcvad` para silencio de fin de turno.

**LOC a cambiar en Carter:** ~600 nuevas (audio loop + adapter vision para tool_results) + ~200 a remover/simplificar del Stage 1 defensive Opus.
**VRAM real medida:**
- Gemma 4 E4B-IQ2_M weights: 3.55 GB
- mmproj-BF16 vision+audio encoder: ~0.95 GB
- KV cache 16 384 ctx (q8 K/V): ~0.6 GB
- Compute buffers + warmup: ~0.6 GB
- **Total Gemma stack: ~5.7 GB** (coincide con tu 5.13 GB observado, +0.5 GB cuando vision se invoca).
- faster-whisper large-v3 INT8 sólo se carga on-demand al wake-word: +1.5 GB durante voice turn, libera al timeout.
- **Pico simultáneo voice+vision: ~7.2 GB** (cabe holgado en 16 GB; deja 8 GB para dev/IDE/browser).
**Latencia objetivo (RTX 4060 Ti 16 GB, llama.cpp CUDA, mismo bench que tu 60-test):**
- Texto chat trivial: ~1.5 s p99 (igual a hoy)
- Texto + tool single-step: ~3 s p99 (igual a hoy, 7.58 s multi-step se mantiene)
- Voice trivial: wake (200 ms VAD) + capture (variable usuario) + Whisper (3 s para 5 s audio en 4060 Ti, ~1.6× realtime con large-v3 INT8) + Gemma texto (2 s) + Piper (0.5 s) ≈ **~6 s end-to-end** (cumple <5–7 s Alexa-tier para la parte AI; tiempo total domina por captura de voz humana)
- Vision query (verificación post-acción, 768×768 screenshot a 280 tokens): ~1.5 s prefill + 0.5 s decode ≈ **~2 s**
- Vision OCR alto (1120 tokens): ~3.5 s
- Multi-modal turn (audio→tool→screenshot verify): 5 s (Whisper) + 4 s (LLM tool) + 2 s (vision) ≈ **~11 s** (cumple <15 s)

**Pros:** No rompe el 91.7 % PASS. No requiere WSL. No cambia la quant fija. Audio honesto y mensurable. Vision usable para casos high-value sin reemplazar lo que ya funciona. Puede degradarse modular: si vision falla, frame-diff numpy queda como fallback; si Whisper falla, queda input texto.
**Contras:** Dos modelos cargan VRAM al hacer voice (Gemma + Whisper). El audio "Gemma nativo" queda como deuda técnica hasta que upstream lo arregle (no esperar antes de Q3 2026).

### Opción B — **FALLBACK: vLLM en WSL2 si querés audio nativo Gemma 4**
**Stack:** WSL2 Ubuntu 22.04 + `vllm[audio]` + `google/gemma-4-E4B-it` (HF safetensors, NO GGUF) + bitsandbytes 4-bit on-the-fly + `--limit-mm-per-prompt '{"image":2,"audio":1}' --gpu-memory-utilization 0.85`. Carter HTTP client apuntando a `http://localhost:8000/v1`.
**LOC:** ~150 (sólo cambiar `llm_endpoint` y manejar `input_audio` content type).
**VRAM real:** vLLM bnb-4bit del E4B: ~6.5 GB pesos + KV cache 8 K: ~1.5 GB + audio encoder warmup: ~0.8 GB → **~9 GB**, +Whisper si lo conservás como respaldo no cabe cómodo.
**Latencia:** prefill mejor que llama.cpp en batch (~30 % más rápido), pero **cold start de vLLM es ~45 s** y Carter pierde control de quant exacta (rompe restricción "modelo fijo IQ2_M").
**Pros:** audio + image + texto en un único turn, OpenAI-compat completo, oficialmente soportado por Google.
**Contras:** Rompe restricción 5 (quant fija). Setup WSL2: ~6 GB disco extra, mantenimiento de drivers cuDNN/CUDA dual, Docker Desktop o setup nativo. **No recomendado** dado las restricciones del proyecto.

### Opción C — **DESCARTAR: llama-mtmd-cli on-demand para audio**
Cold-load 20–60 s por request. Imposible para Alexa-tier. **No usar.**

---

## 3) Diseño por modalidad

### 3.A TEXTO (optimizar lo que ya funciona)

**Sampling — mantener:** `temperature=1.0, top_p=0.95, top_k=64` (recomendación oficial de Google y Unsloth). Tu config actual de `T=0.7` está **subóptima** según el model card: bajalo sólo si ves looping; con T=1.0 + top_k=64 BFCL real-world reporta tool-calling más estable. Notar que la comunidad LocalLLaMA reporta que **bajar temperatura para coding empeora Gemma 4** — la curva T-vs-PASS es contraintuitiva.

**`num_predict` / `max_tokens`:**
- Chat: 512 (bajalo de 1024 — tu p99 de 7.58 s en multi-step viene en parte de overshoot)
- Tool: 768 (suficiente para 2-3 tool calls JSON + reasoning corto)
- Mission: 2048
- **Razón:** decode rate con E4B-IQ2 en 4060 Ti es ~50 t/s; cada 256 tokens = 5 s. Bajar de 1024 → 768 te ahorra ~5 s en cola larga sin afectar PASS (medilo).

**Chat template — cambio crítico:**
La build de `llama-server` activa por defecto `peg-gemma4`. Logs muestran "outdated gemma4 chat template, applying compatibility workarounds": **bajá el template oficial actualizado** y forzalo:
```
--chat-template-file ./templates/gemma-4-E4B-it_chat_template.jinja
--jinja
```
Fuente: `https://huggingface.co/google/gemma-4-E4B-it/blob/main/chat_template.jinja`.
Para Carter (tool-calling de baja latencia, sin pensamiento expuesto al user) **no inyectes `<|think|>` en el system prompt**; eso evita el bloque de razonamiento que añade 200–600 tokens de overhead por turn. Si querés thinking selectivo (mission planner), pasalo por request:
```python
payload["chat_template_kwargs"] = {"enable_thinking": True}
payload["reasoning_format"] = "deepseek"  # los thoughts van a message.reasoning_content, no aparecen en content
```

**Context window adaptable — sí, mantener:**
La estrategia 4096 chat / 8192 tool / 16384 mission está bien. **No fijar 16384 siempre**: KV cache crece linealmente y a 16K con K/V f16 son ~600 MB; a 4K son ~150 MB. En llama-server sin reload no podés cambiar `--ctx-size` mid-flight, así que la solución es: arrancá con `--ctx-size 16384 --parallel 1` (cap máximo) y simplemente truncá el contexto en cliente (Carter ya lo hace). Activá `--cache-type-k q8_0 --cache-type-v q8_0` para bajar KV ~50 % sin pérdida medible (ya validado en Gemma 4 26B en setups del subreddit).

**Stage 1 defensive del reporte Opus — qué retener (~25 %, ~200 LOC):**

| Patrón Opus | ¿Necesario en Gemma 4 E4B-IQ2? | Acción |
|---|---|---|
| **Patrón A — URI hallucination** | NO, cerrado estructuralmente | **Eliminar** (Gemma 4 es disciplinado con URIs reales) |
| **Patrón L — negación** | NO, cerrado | **Eliminar** |
| **Patrón J — URL invention** | NO, cerrado | **Eliminar** |
| **Verifier rewrite (output → schema check → reasked)** | SÍ, marginal pero barato | **Mantener** (~80 LOC); cubre el ~3-5 % de tool args malformados que aún deja Gemma 4-IQ2 |
| **Anti-eco (modelo repite system prompt)** | SÍ, IQ2 a veces ecoaza | **Mantener** (~30 LOC) |
| **Hybrid retrieval (BM25 + dense)** | NO específico de IQ2 | **Mantener si ya está, no reimplementar** |
| **Mission planner (descomposición)** | SÍ pero simplificado | **Mantener planner, eliminar fallbacks por hallucination** (~50 LOC) |
| **App resolver sin URL fallback** | SÍ por disciplina | **Mantener** (~20 LOC) |
| **Destructive stems multilingüe ES/EN** | SÍ, crítico para safety | **Mantener intacto** (~40 LOC) |

Total: **~220 LOC** de los 800 originales. **El reporte Opus asumía un modelo qwen3:4b mucho más alucinador en su capa instrucciones-vs-tools; Gemma 4 con el chat template oficial y `--jinja` cierra esos vectores en arquitectura, no en defensa.** El test 91.7 % PASS lo confirma.

**Bloque drop-in para `prompt.py:CORE_PROMPT`** (Carter v4):
```
You are Carter, a local Windows assistant. Be direct and concise in Rioplatense Spanish unless asked otherwise.

# Tool calling rules (Gemma 4 native)
- Output a tool call ONLY when an action is required. Otherwise answer in plain text.
- Use exactly the parameter names declared in the tool schema. Never invent fields.
- For destructive actions (delete, close, kill, format, uninstall, send), require explicit user confirmation in this turn.
- Never invent file paths, URLs or app IDs. If unknown, call the resolver tool.

# Multimodal rules
- When you receive an image content block, treat it as ground truth about the user's screen at this instant.
- When you receive an audio transcription appended as system context (Whisper output), treat it as the user's literal utterance; do not re-paraphrase before tool calling.
- Place image content BEFORE the text question (Google's recommendation for Gemma 4).

# Honesty rules
- If a tool fails or returns ambiguous output, say so. Do not fabricate success.
- If you are uncertain about a numeric or factual claim, say "no tengo cómo verificarlo" and propose how to verify.
```
Esto encaja con el `system` role nativo de Gemma 4 y con `enable_thinking=False`.

### 3.B AUDIO (capacidad nueva — diseñar desde cero)

**Decisión brutal:** **no integrar audio nativo Gemma 4 hoy.** Fundamento:
1. `llama-server` HTTP `input_audio` está rechazado upstream (#21868).
2. Calidad rioplatense observada por vos en Ollama: 2/5 en TTS sintético. Google declara cobertura multilingüe pero el model card no lista métricas WER por dialecto y la app oficial Android lista 15 idiomas con español genérico, sin diferenciar es_ES/es_MX/es_AR. **Información insuficiente sobre rioplatense — recomiendo experimento mínimo: 20 audios humanos reales de tu uso (vos, microfono real Windows) cuando el upstream funcione, comparar contra Whisper-large-v3.**
3. Pipeline Whisper + Gemma 4 separado: latencia adicional **<300 ms** sobre un hipotético audio nativo (Whisper devuelve texto, Gemma reusa KV cache). El "round-trip extra" es sólo un POST adicional al servidor Whisper local que ya tenés montado.
4. Whisper-large-v3 ES Common Voice WER 4.9 % (modelo zuazo/whisper-large-v3-es fine-tuned) o 5.34 % turbo; rioplatense informalmente similar dado que el corpus de entrenamiento incluye muchas horas LATAM.

**Pipeline voice-loop completo (pseudocódigo Carter):**
```python
# carter/voice/voice_loop.py — ~280 LOC nuevas

import openwakeword, webrtcvad, sounddevice as sd, numpy as np
from faster_whisper import WhisperModel
import requests, soundfile as sf, io, subprocess

WAKE = openwakeword.Model(wakeword_models=["./models/ey_carter.onnx"])
VAD  = webrtcvad.Vad(2)  # aggressiveness 0..3
ASR  = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
LLM  = "http://127.0.0.1:8080/v1/chat/completions"
PIPER_VOICE = "./voices/es_AR-daniela-x_low.onnx"

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)  # 480

def listen_wake():
    """Stream 80ms chunks (1280 samples for OWW), trigger on score > 0.6."""
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16',
                        blocksize=1280) as s:
        while True:
            audio, _ = s.read(1280)
            audio_f = audio.flatten().astype(np.float32) / 32768.0
            scores = WAKE.predict(audio_f)
            if scores.get("ey_carter", 0) > 0.6:
                return  # wake detected

def capture_until_silence(max_s=12, silence_ms=800):
    """Capture audio until VAD reports `silence_ms` of silence, or max_s."""
    buf, silent = [], 0
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16',
                        blocksize=FRAME_SAMPLES) as s:
        for _ in range(int(max_s * 1000 / FRAME_MS)):
            frame, _ = s.read(FRAME_SAMPLES)
            buf.append(frame)
            is_speech = VAD.is_speech(frame.tobytes(), SAMPLE_RATE)
            silent = 0 if is_speech else silent + FRAME_MS
            if silent >= silence_ms and len(buf) > 20:  # min ~600ms
                break
    return np.concatenate(buf).flatten()

def transcribe(pcm_int16):
    """faster-whisper, language='es'. Returns text."""
    audio_f = pcm_int16.astype(np.float32) / 32768.0
    segments, _ = ASR.transcribe(audio_f, language="es",
                                  vad_filter=False, beam_size=1)
    return " ".join(seg.text.strip() for seg in segments).strip()

def llm_turn(transcript, history):
    """POST to llama-server. History = list[OpenAI msg]. Returns assistant text + maybe tool_calls."""
    history.append({"role": "user", "content": transcript})
    r = requests.post(LLM, json={
        "model": "gemma-4-E4B-it",
        "messages": history,
        "tools": CARTER_TOOLS,
        "temperature": 1.0, "top_p": 0.95, "top_k": 64,
        "max_tokens": 768,
    }, timeout=20).json()
    return r["choices"][0]["message"]

def speak(text):
    """Piper TTS → 22kHz WAV → sd.play."""
    proc = subprocess.run(
        ["piper.exe", "--model", PIPER_VOICE, "--output-raw"],
        input=text.encode("utf-8"), capture_output=True)
    audio = np.frombuffer(proc.stdout, dtype=np.int16)
    sd.play(audio, samplerate=22050); sd.wait()

def voice_loop():
    history = [{"role": "system", "content": CORE_PROMPT}]
    while True:
        listen_wake()                          # blocking, ~5ms CPU
        sd.play(short_beep(), samplerate=22050)  # ack
        pcm = capture_until_silence(max_s=12)
        text = transcribe(pcm)
        if not text or len(text) < 2:
            speak("no te escuché"); continue
        msg = llm_turn(text, history)
        if msg.get("tool_calls"):
            history.append(msg)
            for tc in msg["tool_calls"]:
                result = dispatch_tool(tc)     # Carter's existing 57-tool dispatcher
                history.append({"role":"tool","tool_call_id":tc["id"],"content":result})
            msg = llm_turn(None, history)      # second pass with tool results
        history.append(msg)
        speak(msg["content"])
```

**Comparación honesta Whisper-large-v3 vs hipotético audio Gemma 4 nativo:**

| Métrica | Whisper-large-v3 INT8 (4060 Ti) | Gemma 4 E4B audio nativo (cuando funcione) |
|---|---|---|
| WER ES Common Voice | 4.9–6.9 % (zuazo fine-tune 4.93) | sin datos públicos, anecdótico ≥10 % |
| WER rioplatense humano real | sin medir; estimar 7–10 % | desconocido; tu test sintético dio 60 % WER |
| VRAM extra | 1.5 GB (sólo durante turn) | 0 (mmproj ya cargado) |
| Latencia 5 s audio → texto | ~1.6 s | ~1.0 s (estimado) |
| Round-trips | 2 (Whisper + LLM) | 1 |
| Funciona hoy en `llama-server` | ✅ | ❌ |
| Soporte rioplatense | medio-alto (corpus YouTube/podcasts ES_AR) | desconocido |
| Audio >30 s | ✅ chunking nativo | ❌ máximo 30 s por request |

**Veredicto:** **Whisper gana en cada criterio práctico**, salvo "1 round-trip menos" (~600 ms ahorro irrelevantes para Alexa-tier). Mantener Whisper.

**Pre-procesamiento audio:** 16 kHz mono 16-bit PCM es lo correcto (lo que Gemma 4 espera además, según logs `n_mel_bins=128, sample_rate=16000`). Para >10 s con Whisper, no chunkear: `large-v3` lo maneja internamente. Si en el futuro pasás a Gemma 4 nativo, sí chunkear a 28 s con 2 s de overlap.

**Wake word — recomendación:** **openWakeWord** (no Porcupine). Razones: gratis, custom wake word "ey carter" entrenable en Colab en 1 hora con 100 muestras Piper sintéticas, ~50 MB CPU only, mejores curvas FAR/FRR que Porcupine en benchmarks 2024. Porcupine tiene español pero no acepta wake words custom multipalabra sin pagar.

**TTS — Piper.** ES neural voice `es_ES-davefx-medium` está en producción; `es_AR-daniela` o `es_MX-claude` aceptables. Latencia 50 palabras: ~400 ms en CPU. **No usar SAPI Windows** (suena robótico, mala UX). XTTS v2 es mejor calidad pero requiere ~3 GB VRAM extra y latencia 1.5–3 s — innecesario.

### 3.C VISION (capacidad nueva — sí integrar)

**Decisión:** activar vision como **Tier-0 verifier post-acción** y **Tier-3 fallback semántico** para diálogos/UI ambiguos. **No reemplaza PaddleOCR** todavía.

**Casos priorizados (high-value primero):**
1. **Verificación visual post-acción** ("¿Spotify se abrió?") — **PRIORITARIO**. Reemplaza al frame-diff numpy en casos donde haya animación legítima (frame-diff falsifica positivos en transición). Latencia añadida: ~2 s, vs frame-diff 50 ms — usar sólo cuando frame-diff es ambiguo (umbral < threshold). Hybrid: numpy decide, vision desempata.
2. **Lectura de diálogos modales y errores** ("hay un popup, leémelo") — alto valor. PaddleOCR funciona pero no entiende contexto ("¿es un error o una confirmación?"). Gemma 4 sí.
3. **Comprensión de UI no triviales** ("hacé click en el botón Aceptar verde abajo a la derecha") — Gemma 4 devuelve bounding boxes JSON nativos sin grammar-constrained generation; HF reportó IoU comparable a parsers especializados en ~50 web screenshots. Útil cuando los selectores UIA fallan.
4. **Captcha + bot-detection: SÓLO DETECTAR.** Gemma 4 puede identificar "esto es un captcha reCAPTCHA v3, requiere humano"; **no resolver, escalar a usuario.** ~1 LOC en una tool nueva `vision_inspect_for_blockers`.
5. **Comprensión de página/video en navegador** — moderado. Útil para "qué hay en pantalla ahora" sin OCR ciego.
6. **Reemplazo PaddleOCR para texto plano** — **NO**, ver abajo.

**Latencia y resolución óptima (RTX 4060 Ti, IQ2_M):**

| Token budget | Resolución equivalente | Latencia (1 image, 4060 Ti) | Caso |
|---|---|---|---|
| 70 | 224×224 effective | ~0.6 s | "¿se abrió Spotify? sí/no" |
| 280 | ~600×600 | ~1.5 s | UI inspect, dialog reading |
| 560 | ~1080×720 | ~2.5 s | OCR mediano, charts |
| 1120 | ~1920×1080 | ~4.0 s | OCR denso, screenshot completo full HD |

**Sweet spot Carter: 280 tokens default**, 1120 sólo on-demand (`vision_ocr_high` tool). Configurar en arranque:
```
--image-min-tokens 280 --image-max-tokens 1120
```
y dejar que el cliente pida más por request via mensaje "responde con detalle (max tokens 1120)". Carter `gui_screenshot` debería **redimensionar a 768×768 antes de enviar** salvo que haya pedido OCR de detalle: pre-resize en numpy/Pillow ahorra 60-70 % de tiempo encoder.

**Reemplazo PaddleOCR — comparación honesta:**

| Métrica | PaddleOCR (Tier 2 actual) | Gemma 4 E4B-IQ2 vision @ 1120 tokens |
|---|---|---|
| Latencia 1080p OCR | ~0.5–1.0 s GPU, ~3 s CPU | ~3.5–4.0 s |
| Accuracy texto chico ES | ~92 % (PP-OCRv5) a 94.5 % (PaddleOCR-VL 0.9B SOTA OmniDocBench) | desconocido en IQ2; estimación 80–88 % por degradación de quant agresiva |
| RAM/VRAM | 950 MB RAM CPU | 0 (mmproj ya en VRAM) |
| Multilingual ES | sí, robusto | sí, pero no probado en IQ2 |
| Tiene contexto semántico | no | sí ("¿es un error?") |
| Falla en handwriting | sí | sí, pero menos |

**Decisión:** **mantener PaddleOCR como Tier 2** (texto plano, rápido, validado). Gemma 4 vision como Tier 3 cuando: (a) PaddleOCR devuelve texto pero ambiguo semánticamente, (b) screenshot tiene layout complejo (charts, mixed text+image), (c) usuario pide explícitamente "leé y entendé". `~10× más lento` se compensa porque sólo se invoca cuando Tier 2 no alcanza.

**Vision verifier híbrido (reemplazo del frame-diff numpy en casos específicos):**
```python
# carter/verify/visual_verifier.py — ~120 LOC nuevas, frame-diff existente intacto

def verify_action(action_desc: str, before: np.ndarray, after: np.ndarray) -> dict:
    diff_pct = np.mean(np.abs(before.astype(int) - after.astype(int))) / 255
    # Tier 0: trivially identical or trivially different
    if diff_pct < 0.005:
        return {"changed": False, "verifier": "numpy", "confidence": 0.99}
    if diff_pct > 0.30:
        return {"changed": True, "verifier": "numpy", "confidence": 0.95}
    # Tier 1: ambiguous (animation, partial change). Ask Gemma 4 vision.
    after_b64 = pil_b64(after, max_side=768)
    msg = llm_post([
        {"role": "system", "content": "Sos un verificador visual. Responde SOLO 'YES' o 'NO'."},
        {"role": "user", "content": [
            {"type":"image_url", "image_url":{"url": f"data:image/png;base64,{after_b64}"}},
            {"type":"text", "text": f"Mostrá el estado tras: '{action_desc}'. ¿La acción se completó? YES o NO."}
        ]}
    ], max_tokens=8, temperature=0.0)
    yes = "YES" in msg["content"].upper()
    return {"changed": yes, "verifier": "vision", "confidence": 0.85}
```
Esto **mantiene los 50 ms de frame-diff para el 80 % trivial** y sólo paga 2 s de vision en el 20 % ambiguo. Total esperado p99: <500 ms. **No es un reemplazo, es un fallback.**

**Multi-monitor + DPI:** `gui_screenshot` con `mss` ya captura virtual screen (todos los monitores). Para Gemma 4 vision: si el virtual screen es 5760×1080 (3 monitores), pre-resize a 1920×1080 manteniendo aspect ratio (relleno negro vertical) o crop al monitor activo. **Recomendación:** captura por monitor activo o por ventana focused, no virtual screen completo (Gemma 4 a 1120 tokens y 5760×1080 le da ~7 s y degrada calidad).

**Captcha:** tool nueva `gui_check_blockers(screenshot) → {captcha: bool, login_wall: bool, type: str}`. Si captcha detectado: pausar misión, preguntar al usuario, esperar `usuario_resolved=True`. Nunca intentar resolver. ~30 LOC.

---

## 4) Integración multimodal en single turn

**¿Es viable un turn que combine `input_audio` + `image_url` + `tool_result`?**
- En `llama-server`: **no** (audio bloqueado upstream).
- Si el "audio" es ya transcripción Whisper como text content: **sí**, totalmente. Multi-content (text + image_url + image_url) en un solo `messages` array funciona, validado en multimodal docs. Tool results como `role:"tool"` en mensaje subsiguiente también funcionan.

**Costo VRAM con todo "cargado":**
- mmproj BF16: 945 MB (audio+vision encoders, residente siempre con `--mmproj`)
- KV cache 16K: ~600 MB
- Embeddings de 1 screenshot 768×768 a 280 tokens: ~80 MB transitorios
- **Total margen vision: ~1.6 GB sobre los 5.7 GB base = 7.3 GB pico**, cabe holgado.
- Si añadís Whisper: +1.5 GB → 8.8 GB pico. Aún cabe en 16 GB con margen para sistema.

**Tools que devuelven imágenes — formato exacto que `llama-server` acepta como tool_result con imagen:**
**No aceptado nativamente.** El protocolo OpenAI tool results sólo soporta `content: string`. Workaround: cuando una tool produce un screenshot, **NO** lo metas en `role:"tool"`. En su lugar:

```python
# carter/adapter/llamacpp_multimodal.py — ~140 LOC nuevas

def dispatch_with_image_return(history, tool_call):
    name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"]["arguments"])
    result = TOOLS[name](**args)
    if isinstance(result, dict) and "image_path" in result:
        # Step 1: tool result as plain text describing what was captured
        history.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": json.dumps({"status":"ok","note":"screenshot captured, see next user message"})
        })
        # Step 2: synthetic user message with the image
        img_b64 = base64.b64encode(open(result["image_path"], "rb").read()).decode()
        history.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {
                    "url": f"data:image/png;base64,{img_b64}"}},
                {"type": "text", "text": "Acá está la imagen capturada. Procedé."}
            ]
        })
    else:
        history.append({"role":"tool","tool_call_id":tool_call["id"],
                        "content": json.dumps(result)})
    return history
```
Esto es feo pero **es el patrón que llama-server soporta hoy**. Cuando upstream agregue tool results multimodales, simplificás. **NO inventés un formato que el server no parsea, vas a bajar PASS.**

**Streaming WS vs batch:** Carter ya es batch (`stream=False`). Para voice loop, streaming SSE (`stream=True`) baja TTFT percibida ~40 % y permite empezar Piper TTS antes de que el LLM termine. **Activar streaming sólo en chat puro** (sin tool calls). Para tool calls, batch es necesario porque tenés que parsear el JSON completo antes de despachar.

---

## 5) Plan de implementación staged

**Stage 1 — Optimización texto (1 día, ROI alto, riesgo cero)**
- Acciones:
  1. Bajar chat template oficial Google + flag `--chat-template-file`.
  2. Confirmar `--jinja --temp 1.0 --top-p 0.95 --top-k 64`.
  3. `--cache-type-k q8_0 --cache-type-v q8_0`.
  4. Bajar `max_tokens` a 768 en tool turns.
  5. Eliminar Patrón A/L/J del defensive Opus (~600 LOC).
  6. Mantener anti-eco + verifier rewrite + destructive-stems + mission planner simplificado (~220 LOC).
- LOC: −600 / +20.
- Días: 1.
- **Stage 1 done = bench 60-test ≥ 91.7 % PASS y multi-step p99 ≤ 7.0 s** (bajada por max_tokens menor).
- **Rollback:** `git revert`. Mantenés tu config actual.

**Stage 2 — Vision como verificador post-acción (3 días, ROI alto, riesgo bajo)**
- Acciones:
  1. Agregar `mmproj-BF16.gguf` al stack (descarga 945 MB).
  2. Actualizar `llama-server` con `--mmproj --image-min-tokens 280 --image-max-tokens 1120`.
  3. Implementar `visual_verifier.py` híbrido (numpy → vision fallback).
  4. Implementar `gui_check_blockers` (captcha/login wall detection).
  5. Implementar `vision_describe_dialog` tool.
  6. Implementar adapter multimodal `LlamaCppMultimodalAdapter` (synthetic-user-after-tool pattern).
- LOC: +400.
- Días: 3.
- **Stage 2 done = 10-case vision test passes (sec 6, casos 11-20) ≥ 8/10 PASS, latencia vision query p95 ≤ 3 s, no regresión texto.**
- **Rollback:** disable adapter, frame-diff queda intacto.

**Stage 3 — Vision como Tier-3 OCR semántico (2 días, ROI medio, riesgo medio)**
- Acciones:
  1. Hook en `gui_universal_action`: si Tier 2 (PaddleOCR) confidence < 0.7 o devuelve estructura ambigua, llamar Gemma 4 vision con prompt OCR semántico.
  2. **NO** reemplazar PaddleOCR como Tier 1/2.
- LOC: +120.
- Días: 2.
- **Stage 3 done = 5 casos OCR ambiguos donde PaddleOCR fallaba ahora pasan, sin regresión PaddleOCR-only en el resto.**
- **Rollback:** disable Tier 3 hook.

**Stage 4 — Audio nativo Gemma 4 (POSPONER hasta upstream lo soporte)**
- Trigger para iniciar: PR cerrando #21868 mergeado en `llama.cpp` master, O Ollama publica tag con audio HTTP funcional.
- Pre-trabajo HOY: conservar el voice_loop.py con Whisper como adapter abstracto (`ASRBackend`), de modo que cambiarlo a Gemma 4 nativo sea ~30 LOC.
- LOC: +30 cuando llegue.
- Días: 0.5 cuando llegue.
- **Stage 4 done = 20 audios humanos rioplatenses reales WER ≤ 8 %, latencia ≤ 1.2 s sobre Whisper, multi-modal turn audio+image PASS.**
- **Rollback:** swap adapter a Whisper.

**Stages que NO recomiendo:**
- Migrar a vLLM en WSL2: rompe restricción 5 (quant fija). Sólo si Stage 4 se vuelve crítico de negocio.
- Reemplazar PaddleOCR completo: 5–15× peor latencia, sin ganancia clara.
- Adapter multimodal genérico de >500 LOC: el patrón actual (synthetic user post-tool) es feo pero funcional; sobre-ingenierizar antes de Stage 4 desperdicia ROI.

---

## 6) Test plan multimodal (30 casos)

### Bloque A — 10 casos AUDIO → tool (Whisper + Gemma)
Hardware target: 4060 Ti, mic Windows real, español rioplatense, voz humana.

| # | Audio | Tool esperado | PASS criterio | Latencia objetivo |
|---|---|---|---|---|
| A1 | "ey carter abrí Spotify" | `app_open(name="Spotify")` | tool dispatch correcto, app abre | <8 s end-to-end |
| A2 | "qué hora es" | sin tool, respuesta texto | respuesta directa | <5 s |
| A3 | "subí el volumen al 60 por ciento" | `system_volume(level=60)` | parámetro 60 exacto | <8 s |
| A4 | "buscá en internet noticias del mundial" | `web_search(query)` | query contiene "mundial" | <10 s |
| A5 | "cerrá Chrome" | `app_close(name="Chrome")` con confirmación | pide confirmación destructive | <8 s |
| A6 | "no, no lo hagas" (turno tras A5) | cancela acción | no ejecuta close | <5 s |
| A7 | "leeme el último mail" | `mail_read_latest()` | tool correcto | <12 s |
| A8 | "che, ¿está lloviendo?" (rioplatense) | `weather_local()` | entiende "che" + query | <8 s |
| A9 | "anotá: comprar leche y pan" | `note_create(content)` | content correcto, no ecoaza system | <8 s |
| A10 | susurro inaudible / silencio | sin transcripción | "no te escuché", no inventa | <4 s |

PASS bloque: ≥8/10. Métrica VRAM pico: ≤8 GB.

### Bloque B — 10 casos IMAGEN → respuesta (Gemma 4 vision)
Hardware target: screenshot 1080p o 768×768 según prompt.

| # | Input | Tool/respuesta esperada | PASS criterio | Latencia objetivo |
|---|---|---|---|---|
| B1 | screenshot dialog "¿Guardar cambios?" | "es un dialog de guardar cambios, opciones: Sí/No/Cancelar" | identifica botones | <3 s |
| B2 | screenshot Spotify abierto | `verify=True` post `app_open` | dice abierto | <2 s |
| B3 | screenshot Spotify NO abierto | `verify=False` | dice no abierto | <2 s |
| B4 | screenshot con captcha reCAPTCHA | flag `captcha_present=True`, pausa misión | detecta sin resolver | <3 s |
| B5 | screenshot página loading | `loading=True`, espera | reconoce spinner | <2 s |
| B6 | screenshot error rojo "Connection failed" | extrae mensaje exacto | OCR + comprensión | <4 s |
| B7 | screenshot 3 monitores virtual | crop monitor activo, descripción | maneja multi-monitor | <5 s |
| B8 | screenshot con texto chico (font 8) | OCR `--image-max-tokens 1120` | accuracy ≥80 % | <5 s |
| B9 | screenshot chart de Excel | "es un gráfico de barras mostrando X" | interpretación correcta | <4 s |
| B10 | screenshot vacío / pantalla negra | "no hay contenido visible" | no inventa | <2 s |

PASS bloque: ≥8/10.

### Bloque C — 10 casos TRIPLE COMBO (audio → tool → vision verify)
| # | Flujo | PASS criterio | Latencia objetivo |
|---|---|---|---|
| C1 | "abrí Spotify y confirmá que se abrió" → `app_open` → screenshot → vision verify | ciclo completo, dice "sí, abierto" | <14 s |
| C2 | "abrí Notepad" → app no instalado → vision detecta error → respuesta honesta | "Notepad no se pudo abrir, vi un error" | <12 s |
| C3 | "tomá screenshot y leeme el mail visible" → screenshot + vision OCR | extracción texto correcto | <10 s |
| C4 | "buscá Mundial 2030 en Chrome y mostráme el primer titular" → web_open + vision read | titular extraído | <15 s |
| C5 | "cerrá esa ventana" + screenshot ambiguo → vision identifica ventana focused | cierra correcta | <12 s |
| C6 | "¿está abierto Discord?" → screenshot + vision check | sin abrir tool de control | <8 s |
| C7 | "subí volumen al 80, confirmá" → tool + screenshot system tray + vision read | confirma "80%" visible | <13 s |
| C8 | "leeme el captcha que apareció" → vision detect captcha → escala a usuario | NO intenta resolver | <8 s |
| C9 | flujo multi-step misión "abrir Excel, abrir archivo X, leer celda B5" → 3 tools + vision OCR final | resultado correcto | <30 s |
| C10 | error path: "abrí app inexistente" → tool fail → vision ve error → habla error | "no encontré, error visible" | <10 s |

PASS bloque: ≥7/10 (más complejo, tolerancia mayor).

**PASS global stages 1-3:** ≥23/30 (76 %). Si <70 %, **rollback Stage 3 primero, después Stage 2**, mantener Stage 1.

---

## 7) Sources

1. Google AI for Developers — [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
2. Google AI for Developers — [Audio understanding capability](https://ai.google.dev/gemma/docs/capabilities/audio)
3. Google blog (2026-04-02) — [Gemma 4: Byte for byte, the most capable open models](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/)
4. Hugging Face — [google/gemma-4-E4B-it model card](https://huggingface.co/google/gemma-4-E4B-it)
5. Hugging Face Blog — [Welcome Gemma 4: Frontier multimodal intelligence on device](https://huggingface.co/blog/gemma4)
6. Unsloth Docs — [Gemma 4 - How to Run Locally](https://unsloth.ai/docs/models/gemma-4)
7. Hugging Face — [unsloth/gemma-4-E4B-it-GGUF (UD-IQ2_M file)](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/tree/main)
8. llama.cpp PR #21421 — [mtmd: add Gemma 4 audio conformer encoder support](https://github.com/ggml-org/llama.cpp/pull/21421)
9. llama.cpp Issue #21868 — [server: input_audio routing for Gemma 4 (closed not-planned)](https://github.com/ggml-org/llama.cpp/issues/21868)
10. llama.cpp Issue #21316 — [Gemma 4 tool calling unexpected tokens](https://github.com/ggml-org/llama.cpp/issues/21316)
11. llama.cpp PR #21326 — [fix: Gemma 4 chat template](https://github.com/ggml-org/llama.cpp/pull/21326)
12. llama.cpp PR #21343 — [fix: Gemma 4 tokenizer (\n\n token)](https://github.com/ggml-org/llama.cpp/pull/21343)
13. llama.cpp Discussion #21334 — [How to input audio to Gemma 4 E4B](https://github.com/ggml-org/llama.cpp/discussions/21334)
14. llama.cpp Multimodal docs — [docs/multimodal.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)
15. llama.cpp Server docs — [tools/server/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
16. llama.cpp Function calling docs — [docs/function-calling.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md)
17. AwesomeAgents (2026-04) — [llama.cpp Lands Three Audio Models in 48 Hours](https://awesomeagents.ai/news/llama-cpp-three-audio-models-48-hours/)
18. vLLM Recipes — [Gemma 4 Usage Guide](https://docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html)
19. Red Hat Developer (2026-04-02) — [Run Gemma 4 with Red Hat AI on Day 0](https://developers.redhat.com/articles/2026/04/02/run-gemma-4-red-hat-ai-day-0-step-step-guide)
20. NVIDIA Developer Blog — [Bringing AI Closer to the Edge with Gemma 4](https://developer.nvidia.com/blog/bringing-ai-closer-to-the-edge-and-on-device-with-gemma-4/)
21. Datature Blog — [Gemma 4: What Computer Vision Engineers Actually Need to Know](https://datature.io/blog/gemma-4-what-computer-vision-engineers-actually-need-to-know)
22. CodeSOTA (2026-03) — [Best OCR Models 2026 benchmarks (PaddleOCR-VL leads OmniDocBench)](https://www.codesota.com/ocr)
23. Gist daniel-farina — [OpenCode + Gemma 4 26B + llama.cpp tool calling fix](https://gist.github.com/daniel-farina/87dc1c394b94e45bb700d27e9ea03193)
24. asf0/gemma4_jinja — [Custom Gemma 4 chat template (no thought leakage)](https://github.com/asf0/gemma4_jinja)
25. SYSTRAN/faster-whisper — [Production ASR with CTranslate2](https://github.com/SYSTRAN/faster-whisper)
26. Hugging Face — [zuazo/whisper-large-v3-es (WER 4.93 %)](https://huggingface.co/zuazo/whisper-large-v3-es)
27. dscripka/openWakeWord — [Custom wake words via Piper synthetic audio](https://github.com/dscripka/openWakeWord)
28. Avenchat — [How to Run Gemma 4 with llama.cpp](https://avenchat.com/blog/run-gemma-4-with-llama-cpp)
29. WaveSpeed Blog — [What Is Google Gemma 4? Architecture, Benchmarks](https://wavespeed.ai/blog/posts/what-is-google-gemma-4/)
30. AImadeTools — [Granite 4.1 vs Gemma 4 (BFCL V3 Gemma 4 27B = 72.7)](https://www.aimadetools.com/blog/granite-4-1-vs-gemma-4/)
31. Berkeley — [BFCL V4 Leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html)
32. Docker (2026) — [Docker Model Runner adds vLLM support on Windows WSL2](https://www.docker.com/blog/docker-model-runner-vllm-windows/)
33. Ollama Library — [gemma4 tags (lists Text/Image only)](https://ollama.com/library/gemma4/tags)