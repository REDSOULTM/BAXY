# Investigación: arquitectura óptima para voice pipeline (wake + STT) en agente local multi-usuario / multi-idioma

> Copiar y pegar TODO este documento como mensaje inicial en Claude.ai
> con **Modo Investigación** activado. El modo va a generar un reporte
> profundo con citas a papers, benchmarks, frameworks, y ejemplos de
> producción.

---

## Contexto del proyecto

Estoy construyendo **Gemma 4 Agent**, un asistente de voz local estilo Alexa/Siri que corre completamente en la máquina del usuario (sin cloud). El LLM principal es Gemma 4 vía Ollama. Necesito reemplazar la pipeline de voz actual (wake-word detection + speech-to-text) porque la implementación que tengo es frágil: dispara con ruido ambiente del micrófono y transcribe mal anglicismos.

### Lo que la pipeline de voz tiene que hacer

Flujo end-to-end:

```
mic stream (16kHz mono)
  → [WAKE DETECTOR]  detecta "hey gemma" en stream continuo
  → [VAD / endpoint] determina cuándo el usuario terminó de hablar el comando
  → [STT / ASR]      transcribe el comando a texto
  → texto al LLM (este pedazo NO está en scope de la investigación)
```

### Restricciones hard del sistema target

1. **Hardware típico**: laptop sin GPU dedicada o GPU modesta de 6GB VRAM. **La GPU está totalmente ocupada por el LLM (Gemma 4)** — no queda VRAM disponible para el voice stack.
2. **Wake detection + STT corren en CPU** (sin GPU acceleration). Solo CPU disponible, debe ser eficiente.
3. **Latencia tier-Alexa**: percepción instantánea. Wake-to-response debe sentirse <300ms para wake, transcripción de un comando de 2-3 segundos debe demorar <1s wall-clock.
4. **Multi-idioma y multi-usuario**: el sistema lo va a usar gente con distintas voces (hombres, mujeres, niños, acentos), en distintos idiomas (mínimo español y inglés, idealmente cualquier idioma soportado por modelos OSS), con distintas formas de hablar (rioplatense, mexicano, español ibérico, inglés americano/británico, etc.). **NO se puede fine-tunear a una sola voz**.
5. **Caso de uso crítico — anglicismos embebidos**: usuarios hispanohablantes dicen "abre Chrome", "reproduce Bohemian Rhapsody", "busca info sobre Benson Boone", "minimiza Counter-Strike 2". La pipeline tiene que preservar los nombres en inglés con su spelling original cuando aparecen embebidos en frases español. Esto rompe casi todos los STT genéricos configurados a un solo idioma. Análogamente, usuarios anglo pueden decir "play me La Bamba" — preservar palabras español.
6. **Privacy first**: todo local, nada de cloud APIs. Whisper / openWakeWord / Vosk / Picovoice (no-cloud tier) están OK. Google STT / OpenAI Whisper API / Azure Speech NO están OK.
7. **Open source preferido**: la pipeline debe poder ser inspeccionada, modificada, y redistribuida. Picovoice tiene "Personal/Non-Commercial Free Tier" — discutir si es aceptable.

### Lo que YA probé y no funcionó

Mi implementación actual (que voy a tirar):

**Wake detection**:
- **Vosk small es-0.42** como STT-genérico-forzado-a-wake-detection. Resultado: recall ~5% (perdía 94% de los wakes legítimos del operador).
- **openWakeWord con modelo pre-trained "hey_jarvis"** (que es lo más cercano a "hey gemma" disponible upstream). Resultado: recall ~2% (modelo entrenado solo en inglés, no entiende la pronunciación hispana de "Gemma").
- **openWakeWord con modelo custom entrenado fine-tune sobre 105 muestras del operador**: recall 84% en test audio, PERO falsos positivos crónicos con ruido ambiente del micrófono (ventilador del PC, AC, clicks del teclado). 6 fake wakes en 38 segundos de silencio absoluto. Probé múltiples iteraciones (v5, v6, v7) agregando silencio + ruido ambient como negativos. No se pudo separar audio ambient de speech humano usando solo features espectrales.
- **Agregué Silero VAD como gate** antes del wake detector: redujo FPs a 0 sobre las grabaciones de prueba pero el sistema sigue siendo frágil porque depende de mi modelo custom que solo funciona para mi voz.

**STT**:
- **faster-whisper-small con `language="es"`** + initial_prompt con apps comunes. Resultado: WER ~52% sobre audio de prueba con tropezones. "Abre Chrome" → "Aurekrom", "Benson Boone" → "Benson Mould", "Open Chrome" → "Open cross". El modelo fonetiza anglicismos al español.
- Probé `language=None` (autodetect): mismo problema porque clips de comando son cortos (1-3s) y la detección de idioma falla con poca data.
- Probé bilingual initial_prompt (mezcla "abre Chrome" / "open Chrome"): mejoró algunos casos pero rompió otros (variabilidad alta sobre n=6 muestras).
- WER bajó de 0.52 → 0.27 con prompt tuning + semantic WER (sin puntuación) pero **el target era <0.20** y sigo lejos.

### Por qué la pipeline actual es frágil

Identifiqué estos problemas estructurales:

1. **Wake detector custom-trained a una sola voz**: imposible generalizar. Si otro usuario habla, no funciona.
2. **VAD posterior al wake**: agrega latencia secuencial. Pipeline rígida.
3. **STT con language=es hardcoded**: rompe anglicismos. Cambiar a None rompe clips cortos.
4. **initial_prompt es una hack frágil**: cada nuevo nombre de app/canción/persona requiere actualizar el prompt. No escalable.
5. **Debounce + threshold + RMS + VAD gates** se acumulan como parches. No hay diseño coherente.
6. **0 separación entre "wake fase" y "command fase"**: una vez que el wake dispara, el STT corre con la misma config que un comando largo, lo cual no aprovecha que ya sabemos que "hey gemma" empieza la frase.

### Qué quiero de la investigación

Necesito una **arquitectura nueva, robusta, multi-usuario, multi-idioma**, que respete las restricciones hard del hardware target. La investigación debe responder concretamente:

#### A. Wake-word detection

1. **¿Cuál es el state-of-the-art 2024-2026 para wake-word detection on-device, CPU-only, agnostic to user?** Comparar (con benchmarks reales si existen):
   - **openWakeWord** (dscripka): qué tan bien generaliza a voces no vistas, latencia real CPU, false-positive rate en producción.
   - **Picovoice Porcupine**: arquitectura, performance, qué incluye su Personal Tier free, si su modelo "hey gemma" custom keyword se puede generar sin internet.
   - **Snowboy**: descontinuado pero referencia histórica. ¿Mejor sucesor?
   - **microWakeWord** (kahrendt): variant of openWakeWord optimizado para ESP32 — ¿sirve en laptop CPU?
   - **NVIDIA NeMo wake-word** o cualquier model recente de NVIDIA.
   - **Custom transformer-based** (¿hay alguna referencia en HuggingFace que sea wake-word-only, no STT-forzado?)
   - **Pyannote.audio + speaker-agnostic embedding + similarity to prompt embedding** — ¿es viable usar speaker-agnostic embeddings (wav2vec, HuBERT) para hacer wake-by-prompt-matching en lugar de modelo entrenado?

2. **¿Cuál es la mejor estrategia para "hey gemma" específicamente?**
   - "hey jarvis" del repo openWakeWord es el pre-trained más cercano. ¿Cuán cercano fonéticamente está? ¿Qué WER cross-keyword espero?
   - ¿Se puede entrenar un wake-word **sintéticamente** con cientos de voces TTS variadas (Piper voices en N idiomas) para tener un modelo que generalice sin necesitar el audio del operador?
   - ¿Hay datasets públicos de wake-words con la frase "hey [X]" donde X varía y se pueda transferir?

3. **¿Cuál es la arquitectura óptima para rechazar ambient noise** (ventilador, AC, teclado, TV) **sin perder recall**?
   - VAD-then-wake en cascada (lo que tengo): pros/cons.
   - Wake-and-VAD-fused (modelo único que aprende voice-vs-noise + wake-vs-not): ¿existe?
   - Spectral subtraction / noise gating antes del modelo: ¿qué papers lo recomiendan?

#### B. STT (transcripción del comando post-wake)

1. **¿Cuál es la mejor STT on-device 2024-2026 para CPU**, multi-idioma, low latency, que maneje anglicismos embebidos en español/otros idiomas?
   - **faster-whisper / whisper.cpp** small/medium/turbo: latencia real CPU int8 para clips 2-3s. ¿Qué WER realista esperar multi-idioma sin language pinning?
   - **NVIDIA Parakeet / Canary**: ¿sirven CPU? ¿Multilingual?
   - **Distil-Whisper**: 6× más rápido que Whisper, ¿WER comparable?
   - **MMS (Massively Multilingual Speech) de Meta**: 1,107 idiomas. ¿Viable on-device?
   - **SeamlessM4T**: multimodal, multilingual. ¿Demasiado pesado para CPU?
   - **Moonshine** (Useful Sensors): mucho hype 2024, ¿está listo?
   - **wav2vec2 con CTC**: viejo pero solido. ¿Multilingual versions?

2. **¿Cómo se resuelve el problema de anglicismos embebidos en otros idiomas?**
   - ¿Hay modelos STT explícitamente multilingual code-switching aware?
   - **Whisper sin language pinning + temperature 0**: ¿funciona o degrada otros casos?
   - ¿Existe una técnica de "two-pass decoding": primero detect language por sub-segment, después transcribir con language correcto?
   - ¿`initial_prompt` style biasing es la solución de facto o hay algo mejor?
   - **Forced alignment + grapheme-to-phoneme bilingüe**: ¿es feasible?

3. **¿Qué hacer con nombres propios y entidades específicas del usuario** (Spotify, Counter-Strike 2, nombres de contactos, nombres de canciones que el usuario tiene)?
   - **Domain prompts dinámicos**: usar el inventario real de apps/contactos para sesgar STT. ¿Cómo se hace eficientemente?
   - **Post-correction con fuzzy matching**: transcribir "Buca mi info sobre Benson Mould" y después matchear "Buca mi" → "Búscame" y "Mould" → "Boone" via lookup en domain vocab. ¿Mejor que prompt biasing?
   - **RAG sobre vocabulario personal**: ¿se usa en STT?

#### C. Arquitectura overall

1. **¿Cuál es el patrón canónico moderno para voice pipelines on-device?**
   - **Pipecat** (Daily.co): framework full-stack, ¿sirve para local?
   - **Linto Voice Assistant**: open source completo, ¿qué pipeline usa?
   - **Rhasspy 3** (community successor de Mycroft): pipeline modular, ¿qué wake/STT recomiendan?
   - **Mycroft.AI** (descontinuado pero arquitectura documentada).
   - **Sherpa-ONNX / sherpa.cpp**: framework moderno on-device speech, ¿qué incluye?
   - **Vosk** moderno (no la versión vieja que probé): ¿sigue siendo relevante?

2. **¿Fusionar wake + STT en un solo modelo end-to-end es viable?**
   - **NeMo Streaming ASR** con keyword spotting integrado: ¿existe?
   - **Whisper streaming con wake-word como prompt prefix**: ¿hack viable?
   - Pros/cons vs cascada wake → STT separados.

3. **¿Cómo manejar barge-in (interrumpir TTS con un nuevo wake)?**
   - Patrón estándar de Alexa/Siri.
   - Echo cancellation (AEC): librerías open source (speexdsp, WebRTC AEC3).

#### D. Evaluación / benchmarks honestos

1. **¿Cuáles son los benchmarks/datasets públicos para evaluar wake-word detection multi-usuario?**
   - Hey-Snips dataset (Snips/Sonos).
   - Mini Librispeech? Common Voice for command sets?
   - Hey-Mycroft / Alexa-Wakeword datasets si son públicos.

2. **¿Cuáles para STT multilingual + code-switching?**
   - SeamlessM4T eval set.
   - FLEURS multilingual.
   - CommonVoice code-switched.

3. **¿Cómo se miden objetivamente "false wakes per hour" y "wake recall" en producción?**
   - Datasets de "idle noise" estandarizados.
   - Métricas formales (FAR, FRR, EER) — ¿cuáles son los target rates aceptables para asistentes consumer (Alexa, Google)?

### Lo que NO necesito que la investigación responda

- Cómo entrenar mi propio modelo wake-word desde cero (lo intenté, no funciona generalización).
- LLM choice / prompt engineering (out of scope).
- TTS (Piper funciona bien, no toco).
- Speaker diarization / multi-speaker handling (single-mic close-talk).
- VAD para diarization (sí para gating si es necesario).

### Formato del reporte que necesito

1. **Tabla comparativa concreta** de wake-word detection options:
   - Latencia CPU (ms por ventana de 80ms).
   - Recall esperado out-of-the-box en voces no vistas.
   - False-positive rate en ambient noise típico de casa.
   - Open source vs commercial.
   - Effort to ship (días-hombre).

2. **Tabla comparativa concreta** de STT options:
   - Latencia CPU para 2s de audio (int8 / fp16).
   - WER multilingual (FLEURS / CommonVoice).
   - Code-switching handling (calidad subjetiva con ejemplos).
   - RAM footprint.
   - Cold-start latency.

3. **Arquitectura recomendada end-to-end** con diagrama de bloques, especificando:
   - Stack exacto (wake model + lib, STT model + lib, AEC lib si aplica).
   - Cómo se conectan los bloques (streaming vs batch, qué activa qué).
   - Threading model (cuáles bloques son async, qué corre en background, qué corre en cb del mic).
   - Memory budget estimado (RAM total para todo el voice stack).
   - Latencia esperada end-to-end (wake-to-response).

4. **Roadmap de implementación** en sprints concretos:
   - Sprint 1: bootstrap (X días).
   - Sprint 2: ...
   - Cada sprint debe ser un cambio chico y testeable.

5. **Riesgos identificados** con cada opción y plan B si falla.

### Información extra para el investigador

- El proyecto tiene **~1100 tests Python** funcionando, suite estable, infraestructura sólida.
- Tengo torch + ctranslate2 + faster-whisper + openwakeword + Silero VAD + piper TTS ya instalados.
- Tengo Python 3.10 + venv aislado para training (.venv_train con torch+CUDA en mi máquina dev).
- El audio del operador para testing es: `gemma4_agent/voice/tests/Grabación (2).wav` (5 min de comandos rioplatense con anglicismos, 105 wakes anotados manualmente con timestamps en `testaudio_v2_expected.json`).
- El proyecto está en `c:/Users/usuario/Desktop/ETC/Programacion/Probando Gemma 4`.
- Plataforma target: Windows + macOS + Linux (cross-platform). Mac M-series puede usar Metal Performance Shaders.

### Pregunta final operacional

**Si tuvieras que diseñar HOY este voice pipeline para producción, qué stack elegirías y por qué?** Espero una recomendación concreta con justificación basada en data, no un "depende".

---

**Asunto del reporte**: "Voice pipeline architecture for local multi-user multilingual agent (CPU-only, <300ms wake latency)"

**Profundidad esperada**: ~8000-15000 palabras con citaciones, comparaciones cuantitativas, y código de ejemplo si aplica.
