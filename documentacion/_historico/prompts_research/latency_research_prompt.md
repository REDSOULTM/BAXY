# Prompt de investigación — Optimización de latencia de un asistente de voz local (Carter Agent)

> Pegá este documento completo en claude.ai con **Deep Research** activado.
> Es autocontenido: describe un sistema real, con cifras medidas, y pide una
> estrategia de optimización de latencia priorizada. Leélo entero antes de
> proponer nada.

---

# 🔒 RESTRICCIÓN INNEGOCIABLE — TODO TEXTO QUE EL USUARIO ESCUCHA LO GENERA EL LLM

**Este es el PRIMER filtro que tenés que aplicar a CADA optimización que propongas.**
Si una propuesta lo viola, descartala explícitamente aunque sea la más rápida.

Regla: **cada palabra que el usuario oye sale del modelo de lenguaje, en tiempo de
inferencia. Nunca de plantillas, f-strings, ni strings predefinidos (canned).**

Esto incluye, sin excepción:
- Confirmaciones de acción ("Listo, abrí Steam").
- Resúmenes de resultados de herramientas.
- Mensajes de error y de "no pude".
- Preguntas de seguimiento / desambiguación.
- Comentarios sobre resultados raros o inesperados.

**Por qué es innegociable** (es un requisito de producto, no una preferencia técnica):
naturalidad, adaptación al estilo y al idioma del usuario sin tocar código,
capacidad de comentar resultados atípicos, personalidad consistente, soporte
multi-idioma gratis. Una plantilla "Listo, abrí {app}" rompe los cinco.

**Anti-patrón ya explorado y DESCARTADO por diseño** (no propongas variantes de esto):
en esta misma sesión se implementó un short-circuit del segundo pase del LLM que,
tras una acción simple y verificada, **saltaba la llamada al modelo y devolvía una
confirmación por plantilla** (`_maybe_template_summary` / `_pending_template_reply`
en `gemma4_agent/agent.py`). Bajó "pon el volumen al 30" de 6.6s a 3.1s y "abre
steam" de 4.5s a 2.7s — pero **viola la restricción de arriba** porque el texto
deja de salir del LLM. **Ese commit se va a revertir.** La investigación tiene que
saber que esa dirección está cerrada: no recomiendes templatizar, ni "canned
replies", ni "skip the LLM for simple actions".

**Optimizaciones que SÍ respetan la restricción** (el LLM sigue generando cada
palabra; estas son válidas para evaluar):
- **Streaming token-por-token con TTS incremental**: el modelo genera y el TTS
  empieza a hablar antes de que termine la generación (time-to-first-audio bajo).
- **Modelo más chico/rápido solo para el pase 2** (el resumen post-tool): sigue
  siendo un LLM generando, no una plantilla. Draft model / modelo separado.
- **Speculative / assisted decoding**, draft models, prefix caching.
- **Reducir el contexto que entra al pase 2** (menos prefill → menos TTFT), sin
  cambiar quién genera el texto.
- **Quitar el "thinking" del pase 1** cuando el subset de tools es chico y obvio.
- **Arquitecturas voice-to-voice end-to-end** (Moshi, Sesame CSM, etc.) si son
  viables 100% local en el hardware target — el modelo sigue generando todo.
- Cualquier técnica que mantenga el invariante **"el LLM genera cada palabra que
  el usuario escucha"**.

Pedido concreto a la investigación: **evaluá cada optimización contra esta
restricción y marcá explícitamente PASA / VIOLA antes de rankearla.** Las que
violan no entran al ranking de impacto, ni siquiera como "quick win".

---

# 1. Qué es el sistema

**Carter Agent**: asistente de voz local para Windows, multi-idioma (default
español), 100% open-source y gratis (sin Picovoice, sin APIs cloud de pago). Corre
un pipeline en cascada **wake-word → VAD → STT → LLM agente con tools → TTS**.
El LLM hace tool-calling real (abrir apps, volumen, ventanas, media, web, screenshot
+ visión, etc.). El usuario reporta que **antes era rápido y algo lo volvió lento**;
el target es **3-5 s por turno de voz, 8 s ya es UX catastrófica**.

# 2. STACK REAL (extraído del código/configs/entorno, no de memoria)

### Dependencias instaladas (versiones exactas, `importlib.metadata`)
```
faster-whisper == 1.2.1
ctranslate2    == 4.7.1   (backend de faster-whisper)
piper-tts      == 1.4.2
onnxruntime    == 1.23.2  (wake-word + VAD)
silero-vad     == 6.2.1
sounddevice    == 0.5.5
numpy          == 1.26.4
```

### Servidor LLM
- **llama.cpp build `b9090-5757c4dcb`** (servidor `llama-server`, modo OpenAI-compat
  en `127.0.0.1:8080`).
- Corre en **modo router experimental** (`--models`/presets): expone dos presets por
  perfil y se elige por request vía el campo `model`:
  - `vram8-text`  → GGUF de texto, **sin** `--mmproj` (KV cache prefix-reuse activo)
  - `vram8-vision` → mismo GGUF **con** `--mmproj` (visión; reuse limitado)
- Flags del comando (de `gemma4_agent/llama_server.py`):
  `-ngl 99 -c 16384 --parallel 1 --ctx-checkpoints 1 --flash-attn on --keep -1
  --cache-reuse 256 --no-webui` (+ `--no-mmap` solo en perfiles ≤6 GB:
  vram3/vram4/vram6).
- Comentario en el código: `--cache-reuse 256` se reactivó porque el PR llama.cpp
  **#22288** (merged 2026-04-24, en release ≥b9084) cerró el bug **#21468**
  (cache-reuse roto en Gemma 4 por shared-KV/SWA). `--keep -1` complementa.

### Modelo LLM (exacto, de `gemma4_agent/profiles.py`)
- Perfil **vram8** (el de la sesión lenta): `models/E4B/gemma-4-E4B-it-UD-Q4_K_XL.gguf`
  - mmproj: `models/E4B/mmproj-F16.gguf`
  - context_size: **16384**, vision_enabled=True, voice_enabled=True
- Perfil **vram6** (mínimo fiable 6 GB): `models/E4B/gemma-4-E4B-it-Q4_K_M.gguf`,
  mismo mmproj F16, ctx 16384.
- Gemma 4 **E4B** = variante "effective 4B" (familia E2B/E4B). E4B hace tool-calling
  fiable; E2B no a través del agente completo (medido en sesiones previas).

### STT (de `gemma4_agent/voice/stt.py`)
- **faster-whisper, modelo `small`** (244M params, ~480 MB disco, ~900 MB RAM infer).
- **device=cpu, compute_type=int8, cpu_threads=4** (obligatorio CPU: la VRAM está
  consumida por el LLM — restricción de producto).
- `language="es"` fija (no autodetect: clips de 1-3 s no se autodetectan fiable).
- `beam_size=1, best_of=1, temperature=0.0, condition_on_previous_text=False,
  vad_filter=False` (la VAD la hace el pipeline aparte), `without_timestamps=True`.
- `initial_prompt` dinámico construido del inventario de apps/dominio (`inventory.py`).
- Recién agregado esta sesión (sospechoso de costo, ver §4):
  `no_speech_threshold=0.6, log_prob_threshold=-1.0, compression_ratio_threshold=2.4`
  + filtrado de segmentos con `no_speech_prob>=0.6`.

### Wake-word (de `gemma4_agent/voice/wake.py`)
- **LiveKit WakeWord** (conv-attention) ONNX: `voice/models/livekit/hey_gemma.onnx`,
  entrenado con pipeline LiveKit sobre Piper LibriTTS. Fallback: openWakeWord.
- Necesita ~2 s de audio para score no-cero; stride ~32 ms/chunk.
- `LIVEKIT_THRESHOLD = 0.25` (recall ~0.74, fp/hr 0.000 en held-out de 25 voces /
  13 idiomas). ONNX Runtime con throttle (2 intra-op threads, sin spinning) para no
  congelar Windows.

### VAD (de `gemma4_agent/voice/vad.py`)
- **Silero VAD v6.2.1** (paquete `silero-vad`), usado solo para end-of-speech en
  CAPTURE, no como gate del wake.

### TTS (de `gemma4_agent/voice/tts.py`)
- **Piper VITS+ONNX**, voz **`es_MX-claude-high`**, **sample_rate 22050 Hz**.
  (VoxCPM descartado: segfaulta en RTX 40-series por bug SDPA en warm-up.)
- Worker thread consume cola de oraciones; reproduce con `sounddevice.OutputStream`.
- Streaming a **nivel de ORACIÓN** (no palabra/fonema): el LLM va llenando un buffer,
  y al cerrar una oración (`.!?;¡¿\n\n`) se encola para sintetizar. `feed_tts()` /
  `flush_tts()` desde `agent_runner.py`.

### Hardware target
- **RTX 4060 (16 GB VRAM según el usuario), Windows 11 Home (build 26200).**
  (Nota: la dev box es RTX 4060 **Ti** 16 GB; el código asume laptop modesto / GPU
  6 GB o sin GPU dedicada como piso. STT siempre en CPU.)
- CLAUDE.md fija: latencia tope 4-5 s/turno, STT en CPU+int8, todo OSS/gratis.

### Pipeline de voz (archivos y clases reales)
- `gemma4_agent/voice/pipeline.py` → `VoicePipeline`, máquina de estados de un solo
  thread (AudioPump): `IDLE → CAPTURE → TRANSCRIBE → COOLDOWN`. Constantes actuales:
  - `PREROLL_SECONDS = 0.5`
  - `END_OF_SPEECH_SILENCE_S = 0.8`  ← bajado de 1.4 esta sesión (ver §4)
  - `MIN_CAPTURE_S = 1.0`
  - `COMMAND_TIMEOUT_S = 8.0`, `COOLDOWN_S = 0.4`
  - `WAKE_GATE_THRESHOLD = 0.3`, `EOS_VAD_THRESHOLD = 0.5`
  - `MIN_CAPTURE_RMS = 180.0` (gate de energía, nuevo esta sesión)
- `gemma4_agent/voice/wake.py` → `WakeDetector` (LiveKit runtime en
  `voice/livekit_runtime.py`, ONNX puro; el paquete livekit-wakeword pide Python 3.11,
  el runtime corre en 3.10).
- `gemma4_agent/voice/stt.py` → `STT`; `vad.py` → `SileroVAD`; `tts.py` →
  `StreamingTTS`; `corrector.py` → `FuzzyCorrector` (RapidFuzz post-corrección de
  anglicismos, no toca latencia LLM).
- `gemma4_agent/agent.py` → `Gemma4Agent.run_content` (loop de turnos del agente,
  tool-calling, guards de honestidad).
- `gemma4_agent/agent_runner.py` → puente voz↔agente: `on_command` → `run_text` →
  `VOICE.feed_tts(content)` por token + `flush_tts()` al final.
- `gemma4_agent/llm_client.py` → `chat()` (HTTP a llama-server, soporta
  `enable_thinking`, `thinking_budget`, `force_tool`, `model` para presets router).

# 3. NÚMEROS MEDIDOS HOY (stamps reales, no estimados)

Las latencias del usuario en una sesión real (perfil vram8, log
`~/.gemma4/logs/_pre_session/full.log`, 21:51-21:55, "inicio→respuesta", INCLUYE la
espera de fin-de-habla):

| Acción | Latencia | Inicio → Respuesta |
|---|---|---|
| Abrir Steam | 7 s | 21:51:50 → 21:51:57 |
| Buscar en Steam | 8 s | 21:52:08 → 21:52:16 |
| Ajustar volumen del PC | 7 s | 21:52:37 → 21:52:44 |
| Búsqueda web (fecha GTA VI) | 12 s | 21:53:05 → 21:53:17 |
| Análisis de captura de pantalla | 25 s | 21:53:31 → 21:53:56 |
| Enviar WhatsApp | 21 s | 21:54:32 → 21:54:53 |
| Reproducir en Spotify | 14 s | 21:55:45 → 21:55:59 |

Target del usuario: **3-5 s máx**. Todo lo de arriba lo excede.

### Desglose por etapa (de `gemma4_agent/data/traces.jsonl`, perfil vram8)
Cada turno de acción hace **DOS round-trips al LLM**:
1. Pase 1 (decide + emite tool_call) — **thinking ON** en `quick_action`.
2. Pase 2 (resume el resultado: "Listo, …") — thinking OFF, pero igual round-trip.

Stamps crudos medidos hoy (agente warm, servidor vram8 ya cargado):
```
=== 'pon el volumen al 30' total=6.6s ===
  +0.02s start
  +0.03s tool_subset
  +0.00s llm_start
  +3.93s llm_response      ← PASE 1 (thinking ON): 3.93 s
  +0.00s tool_start
  +0.08s tool_end          ← la tool en sí: 80 ms
  +0.00s llm_start
  +2.51s llm_response      ← PASE 2 (resumen "Listo"): 2.51 s
  +0.00s final

=== 'abre steam' total=4.5s ===
  +0.06s tool_subset
  +2.00s llm_response      ← PASE 1: 2.00 s
  +0.56s tool_end          ← tool: 0.56 s
  +1.89s llm_response      ← PASE 2: 1.89 s
```

Lectura: la **tool real cuesta 80-560 ms**. El costo está casi todo en los **dos
round-trips del LLM**: pase 1 (2-4 s, con thinking) + pase 2 (1.9-2.5 s, solo para
decir "Listo"). El pase 2 es ~2-2.5 s de **cada** turno de acción. La captura de
pantalla (25 s) suma un tercer round-trip de visión (mmproj, prefill de imagen).

A esto se le suma la **latencia de fin-de-habla del STT**: el usuario reporta "habla
y se queda un rato más escuchándome". `END_OF_SPEECH_SILENCE_S` estaba en **1.4 s**
de silencio fijo después de terminar de hablar (bajado a 0.8 s esta sesión) + STT
batch al final (faster-whisper small int8 en CPU, ~0.6-0.9 s para 2 s de clip).

### ¿Cuándo se rompió? (de `git log --oneline`)
Commits sospechosos de haber introducido la regresión, en orden cronológico:
```
9da4fd3 fix(agent): enable reasoning for action commands — reliable tool-calling (root cause)
112c7ab fix(agent): cap reasoning budget — thinking ON for tool-calls without latency runaway
592f60a perf(agent): skip reasoning on the post-tool reply (thinking only for the tool decision)
9614770 perf(boot): warm intent-router centroids + embed cache at startup (kill 14s cold start)
aefcd60 feat(agent): force tool-call retry when a weak model skips it (research-backed)
699865d feat(profiles): upgrade small-profile models to reliable tool-callers (all Gemma 4)
3f1c278 perf(server): lazy-vision via llama.cpp router mode — cuts action latency ~2-3x
83e997d fix(boot): router-mode warmup hung ~2min — wrong model name + separate manager
77c5df9 docs(profiles): vram6 is the reliable 6GB-minimum profile
ada7a21 fix(ui): settings dialog referenced old profile names
```
Hipótesis principal de la regresión: **`9da4fd3` activó "thinking" (reasoning) en el
pase 1 de tool-calling** para subir fiabilidad — esto solo el pase 1 cuesta 2-4 s.
Antes de ese commit, el tool-calling era sin reasoning (más rápido pero menos fiable).
El trade-off fiabilidad↔latencia es el núcleo del problema. `3f1c278` (router mode /
lazy-vision) cambió cómo se sirve el modelo y pudo afectar el reuse del KV cache.

# 4. CAMBIOS DE ESTA SESIÓN Y LA ANTERIOR (posible impacto en latencia)

Todos sin commitear al momento de escribir esto. Por archivo, qué cambió e hipótesis:

| Archivo | Cambio | ¿Pudo agregar latencia? |
|---|---|---|
| `agent.py` | **Summary short-circuit por plantilla** (`_maybe_template_summary`, `_pending_template_reply`) que salta el pase 2 del LLM en acciones simples verificadas | **BAJA latencia (6.6→3.1s)** pero **VIOLA la restricción innegociable → SE REVIERTE** |
| `agent.py` / `agent_runner.py` | **Resolución de modelo router POR LLAMADA** (`resolve_turn_model` sondea `/v1/models`, cacheado 30 s; `_router_model_for` re-evalúa si los mensajes llevan imagen) | Posible: un HTTP GET `/v1/models` por turno (cacheado 30 s). Medir su costo real. |
| `agent.py` | Reset de flags por turno; forced-tool retry (de sesión previa) | Forced-retry agrega 1 round-trip extra SOLO cuando el modelo no emite tool en el pase 1 |
| `tool_schemas.py` | Hints de desambiguación (next-track, ventana actual) en descripciones de tools | Aumenta tokens del system prompt → más prefill por turno (marginal) |
| `tools.py` | `window_control` cae a ventana foreground si no hay título | Sin impacto de latencia |
| `grounding_gate.py` | Nuevos detectores de falsa-confirmación (artifact-handover, telemetría fabricada), regex puro | Trivial (regex sobre el reply) |
| `planner.py` | **Over-offer fix**: cuando keywords ya dieron tool de dominio, el union semántico se limita a la banda de confianza (17→8 tools para "pon el volumen del pc a 10") | **BAJA prefill del pase 1** (menos schemas de tools en el prompt). Posible mejora de latencia. Recall del router se mantuvo 0.82. |
| `voice/pipeline.py` | `END_OF_SPEECH_SILENCE_S` 1.4→0.8; gate de RMS (`MIN_CAPTURE_RMS=180`); blocklist de alucinaciones; gate de TTS en CAPTURE | EOS más corto = **menos espera percibida**. RMS/blocklist son baratos. |
| `voice/stt.py` | `no_speech_threshold`/`log_prob_threshold`/`compression_ratio_threshold` + drop de segmentos `no_speech_prob>=0.6` | A evaluar: ¿el cálculo de no_speech_prob agrega costo medible al decode? |
| `voice/tts.py` | `is_busy()` ahora cubre síntesis + ventana de gracia `TTS_TAIL_GRACE_S=0.6` post-audio (anti self-hearing) | Mantiene el mic muteado 0.6 s más tras el TTS — esto es ANTI-eco, no latencia del turno, pero alarga el "puede volver a hablar" |

Contexto del problema original que disparó estos cambios: en logs reales el sistema
**se escuchaba a sí mismo** (el TTS salía por el parlante, el mic lo capturaba como
"comando", y Whisper alucinaba "¡Suscríbete!"/"hola" sobre silencio). Eso ya está
arreglado; la latencia es el frente abierto.

# 5. RESTRICCIONES DEL PROYECTO (de CLAUDE.md y memorias)

- **Innegociable**: todo texto al usuario lo genera el LLM (ver header arriba).
- **Todo OSS y gratis**: sin Picovoice, sin APIs cloud de pago. Modelos locales
  obligatorios. Si la mejor solución es paga, decílo pero NO la asumas.
- **STT en CPU+int8 siempre**: la VRAM está consumida por el LLM (6 GB de presupuesto
  en el target). Las cifras de STT en GPU son solo techo de medición, no prod.
- **Uso universal multi-usuario/idioma/acento**: prohibido fine-tunear sobre la voz
  del operador como atajo (degrada al resto). Cualquier cambio de STT/wake se evalúa
  contra held-out diverso, no una sola voz.
- **No romper el recall del router** (~0.82 dev / 0.83 holdout) ni la **honestidad de
  los guards** (el agente nunca debe afirmar una acción que no se verificó; hay
  promise-guard + grounding-gate que reemplazan falsas confirmaciones por un fallback
  honesto).
- **Anti-keyword**: el routing de intención es semántico (embeddings multi-idioma), no
  listas de keywords. No agregar atajos por palabra clave que degraden la generalidad.
- **Hardware fijo**: RTX 4060 / Windows 11; asumir laptop modesto como piso. La GPU es
  para entrenar, no necesariamente el target de runtime.
- **Build de llama.cpp fijado** en ≥b9090 (por fixes de tokenizer/parser de Gemma 4 y
  el fix de cache-reuse #22288). `tool_choice` en este build es STRING, no objeto.

# 6. PREGUNTAS CONCRETAS A INVESTIGAR

Aplicá el filtro de la **restricción innegociable** a cada respuesta (PASA/VIOLA).

1. **Time-to-first-audio <2 s en cascada STT→LLM→TTS 100% local en RTX 4060 / Win11**:
   ¿qué presupuesto por etapa es realista y qué técnicas lo logran sin violar la
   restricción? Dame un budget objetivo por etapa (wake, EOS, STT, LLM pase 1, tool,
   LLM pase 2, TTS first-audio).

2. **Qué hacen los frameworks de referencia** para minimizar latencia, y qué es
   portable a este stack (cascada local, sin cloud): **LiveKit Agents, Pipecat,
   Vocode, Home Assistant Voice (Assist), Willow / WillowVoice**. Interesa
   especialmente cómo encadenan STT parcial → LLM → TTS y cómo manejan endpointing.

3. **End-of-speech / endpointing**: hoy son **0.8 s de silencio fijo** con Silero VAD
   v6 + `MIN_CAPTURE_S=1.0`. ¿Conviene **Silero VAD v5 vs v6**, **ten-vad**, o
   **semantic/neural endpointing** (predecir fin de turno por contenido, no solo
   silencio)? ¿Cuánto se puede bajar el silence window sin cortar al usuario a mitad
   de frase? ¿Endpointing adaptativo por prosodia?

4. **STT streaming vs batch**: hoy es **batch al final del turno** (faster-whisper
   small int8 CPU). ¿Vale la pena STT **streaming/incremental** (transcribir mientras
   habla) para que el LLM arranque antes? ¿faster-whisper soporta streaming útil, o
   conviene **whisper-streaming / WhisperLive / distil-whisper / whisper small.en
   vs small multilingüe**? Restricción: CPU int8, español, clips 1-3 s. ¿Cuánto baja
   el TTFT real?

5. **Empezar a generar el LLM antes de terminar la transcripción**: ¿es viable con un
   STT parcial estable? ¿Vale el riesgo de re-prompt si la transcripción cambia?

6. **LLM — el costo central (2 round-trips, 2-4 s + 1.9-2.5 s)**:
   - **Speculative / assisted decoding** en Gemma 3/4 4B con llama.cpp: ¿hay draft
     model chico (1B) compatible? ¿ganancia real en CPU/GPU mixto?
   - **Prefix caching / cache-reuse** en modo router con dos presets (-text/-vision):
     ¿el reuse sobrevive al cambio de preset por request? ¿`--keep -1 --cache-reuse
     256` está bien tuneado? ¿el mmproj del preset vision rompe el reuse del text?
   - **Pase 2 (resumen "Listo, hice X")**: el LLM TIENE que generarlo (restricción).
     Opciones válidas: (a) **streaming token→TTS** para que empiece a hablar al primer
     token; (b) **modelo más chico solo para el pase 2** (¿un Gemma 1B/2B o un draft
     corre el resumen mientras el grande queda para el pase 1?); (c) **reducir el
     contexto del pase 2** (no re-mandar todos los schemas de tools ni el system
     completo). Rankear (a)/(b)/(c) por impacto/esfuerzo.
   - **Pase 1**: ¿se puede mantener fiabilidad de tool-calling **sin** thinking
     (que cuesta 2-4 s)? ¿`tool_choice=required` + grammar/constrained decoding
     reemplaza al reasoning sin perder fiabilidad? ¿"thinking" solo cuando el subset
     es ambiguo y off cuando es chico/obvio?
   - ¿Conviene un **modelo más chico de base** (E2B) si se compensa la fiabilidad de
     tool-calling por otra vía (grammar, retry)? Antes E2B no era fiable a través del
     agente — ¿qué lo haría fiable?

7. **TTS — streaming sub-oración**: hoy Piper sintetiza **por oración completa**.
   ¿Conviene streaming a nivel de **palabra/frase/fonema** para emitir audio antes de
   cerrar la oración? ¿Piper soporta chunking incremental útil, o conviene otro TTS
   local de baja latencia (Kokoro-ONNX, Parler, XTToS streaming) sin perder calidad
   ni romper "todo local"? ¿first-audio antes de que el LLM termine de generar?

8. **Arquitecturas voice-to-voice end-to-end**: ¿es viable hoy correr **Moshi**,
   **Sesame CSM**, o similar **100% local en RTX 4060 16 GB / Win11**, manteniendo
   tool-calling y el invariante "el LLM genera todo"? ¿Latencia real, VRAM, soporte
   de tools, soporte español? ¿Reemplaza la cascada o convive?

9. **Específico al proyecto**:
   - El **modo router con dos presets** y la **resolución de modelo por llamada**
     (`resolve_turn_model` sondeando `/v1/models`, cacheado 30 s): ¿el overhead
     importa? ¿hay forma de resolver el preset sin un HTTP GET por turno?
   - El tercer round-trip de **visión** (screenshot → mmproj → 25 s): ¿prefill de
     imagen optimizable? ¿resolución/tiling del mmproj? ¿vale un modelo de visión
     separado más chico?
   - El **forced-tool retry** (round-trip extra cuando el pase 1 no emite tool):
     ¿cómo evitar que se dispare sin perder fiabilidad?

# 7. FORMATO DE RESPUESTA QUE QUIERO

1. **Causa(s) probable(s) de la regresión** (antes era rápido): rankeá tus hipótesis
   contra los commits sospechosos del §3-4 y los números medidos. Decí qué medirías
   para confirmar cada una.
2. **Ranking de optimizaciones por impacto/esfuerzo**, en tabla. Cada fila con:
   técnica · etapa que ataca · ganancia estimada (ms/s) · esfuerzo · riesgo ·
   **PASA/VIOLA la restricción innegociable**. Las que VIOLAN no entran al ranking.
3. **Plan de implementación priorizado** (qué hacer primero, segundo, tercero) con
   el budget de latencia objetivo por etapa para llegar a <5 s (idealmente <3 s) por
   turno de acción simple y <2 s de time-to-first-audio.
4. **Riesgos de cada cambio** (fiabilidad de tool-calling, recall del router,
   honestidad, calidad de voz, VRAM, compatibilidad con el build b9090).
5. **Referencias con links**: papers, benchmarks, issues/PRs de llama.cpp y
   faster-whisper, docs de LiveKit/Pipecat/HA Voice, model cards de cualquier modelo
   que recomiendes (STT, draft, TTS, voice-to-voice). Preferí fuentes recientes y
   verificables.

Recordá: **el primer filtro es la restricción innegociable.** Una optimización que
hace al sistema instantáneo pero reemplaza texto del LLM por plantillas **no sirve**
para este proyecto y debe descartarse explícitamente.
