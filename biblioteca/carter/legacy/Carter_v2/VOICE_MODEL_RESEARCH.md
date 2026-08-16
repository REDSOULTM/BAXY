# Carter Voice Model Research (M8)

**Status:** Carter v2 does **not** ship STT/TTS yet (`capabilities/` is text + GUI only).
This document specifies the recommended voice stack per profile, the rationale,
and the install / probe commands so M11 can collect real numbers when voice is
adopted. The companion runner is `audit/runners/model_voice_eval.py` (offline,
mic/speaker NOT touched without explicit `--audio` / `--tts-text` flags).

---

## 1. STT — Speech-to-Text candidates

| backend | model size | params | RAM | VRAM | streaming | langs | lic | recommended profile |
|---|---|---:|---:|---:|---|---|---|---|
| **whisper.cpp tiny.en/tiny** | 39 MB | 39M | 0.4 GB | – | yes | EN/multi | MIT | CPU_ONLY, command-only |
| **whisper.cpp base** | 142 MB | 74M | 0.7 GB | – | yes | multi (90+) | MIT | CPU_ONLY, 6GB |
| **whisper.cpp small** | 466 MB | 244M | 1.0 GB | 1.0 GB GPU | yes | multi | MIT | 6GB / 8GB |
| **whisper.cpp medium** | 1.5 GB | 769M | 2.5 GB | 2.5 GB | yes | multi | MIT | 12GB / 16GB |
| **whisper.cpp large-v3** | 3.0 GB | 1.55B | 5.5 GB | 5.5 GB | yes | multi | MIT | 16GB+ |
| **faster-whisper large-v3** | 3.0 GB | 1.55B | 4.5 GB | **3.0 GB** (CT2 int8) | yes | multi | MIT | 12/16/24 GB ⭐ |
| **faster-whisper distil-large-v3** | 1.5 GB | 756M | 2.5 GB | 1.8 GB | yes | EN main, multi limited | MIT | 8/12 GB |
| **NVIDIA parakeet-tdt-0.6b** | 0.6B | 600M | – | 1.5 GB | yes | EN | CC-BY-4.0 | 8/12 GB EN-only |
| **WhisperX (large-v3 + diarization)** | 3+ GB | – | 5+ GB | 5+ GB | batch | multi | BSD | 16/24 GB if speaker labels needed |

**Decisión:**
- `faster-whisper` (CTranslate2 backend) gana en GPU por usar int8/fp16 nativo y
  resultar 4-5× más rápido que `whisper.cpp` con la misma calidad.
- `whisper.cpp` queda como fallback CPU/iGPU porque empaqueta como un único
  binario sin dependencias Python pesadas.
- En perfiles ≤ 8 GB se recomienda `small` (es+en) o `distil-large` (en).

## 2. TTS — Text-to-Speech candidates

| backend | size | latency first audio | langs | quality | lic | profile |
|---|---:|---|---|---|---|---|
| **Piper** | 25–60 MB / voz | < 300 ms CPU | 30+ (ES, EN, FR, DE, ...) | natural, stable | MIT | TODOS ⭐ default |
| **Kokoro-82M** | 82 MB | < 200 ms CPU | EN main, ES limited | very natural | Apache 2.0 | CPU_ONLY / 6GB |
| **Coqui XTTSv2** | 1.8 GB | ~600 ms GPU | 17 + voice cloning | premium, cloning | CPML (no comercial) | 16/24 GB opt-in |
| **Edge-TTS (cloud)** | – | network-bound | multi | premium | MS TOS | DESCARTADO (no local) |
| **VITS Spanish (multi-speaker)** | 100 MB | < 400 ms CPU | ES | natural | MIT | ES-only fallback |

**Decisión:**
- `Piper` es la elección por defecto en TODOS los perfiles (CPU/GPU friendly,
  multi-idioma, MIT, latencia < 300 ms con voces es_MX y en_US oficialmente
  publicadas). Voces sugeridas: `es_MX-claude-medium` (155 MB) y
  `en_US-amy-medium` (60 MB).
- `XTTSv2` opcional para perfiles 16/24 GB cuando se quiera cloning o
  prosodia premium; restricción de licencia limita uso comercial.

## 3. OCR (no LLM)

| backend | tipo | GPU | calidad | uso Carter |
|---|---|---|---|---|
| **pytesseract** (Tesseract 5) | clásico | no | media | ya integrado en `vision_router._ocr_all` ✓ |
| **PaddleOCR** | DL | sí (mejora) | alta | candidato perfil 12/16 GB |
| **EasyOCR** | DL | sí | alta | candidato 8/12 GB |
| **OmniParser-v2** (Microsoft) | UI parser | sí | excelente para UI | ya probe en `vision_router` ✓ |

## 4. Cámara

Carter v2 no expone `camera_capture()` aún. La pipeline de cámara reutilizará
el mismo `vision_router` (mismo VLM, misma política de unload). El budget VRAM
no cambia: la cámara solo añade un frame source, no un modelo extra.

## 5. Plan de adopción (out of scope para M11 numérico)

1. M8.A — instalar Piper + voces:
   ```powershell
   # Install Piper (Windows binary)
   # https://github.com/rhasspy/piper/releases
   # Voices:
   curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/medium/es_MX-claude-medium.onnx
   curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/medium/es_MX-claude-medium.onnx.json
   ```
2. M8.B — instalar `faster-whisper`:
   ```powershell
   ..\.venv\Scripts\python -m pip install faster-whisper
   ```
3. M8.C — probar: `python audit/runners/model_voice_eval.py --probe`
4. M8.D — recoger un set de fixtures `audit/fixtures/voice/{es,en}/*.wav`
   con consentimiento explícito antes de grabar nada.
5. M8.E — agregar `capabilities/voice.py` (modo `stt_transcribe(audio_bytes)`
   y `tts_speak(text)`) con la misma política `on-demand + unload` que
   `vision_router`. Prohibido cargar STT y VLM y LLM grandes simultáneamente
   en perfiles ≤ 12 GB.

---

**Ranking recomendado por perfil (sin números reales aún — pendiente M11/voice):**

| perfil | STT | TTS | OCR |
|---|---|---|---|
| CPU_ONLY | whisper.cpp tiny | Piper (es_MX-claude-low) | pytesseract |
| 6GB | whisper.cpp small | Piper (es_MX-claude-medium) | pytesseract |
| 8GB | faster-whisper distil-large | Piper | pytesseract / PaddleOCR |
| 10GB | faster-whisper small | Piper | PaddleOCR |
| 12GB | faster-whisper medium | Piper | PaddleOCR |
| 16GB | faster-whisper large-v3 (CT2 int8) | Piper + XTTSv2 opt | PaddleOCR + OmniParser |
| 24GB+ | faster-whisper large-v3 (fp16) | XTTSv2 | PaddleOCR + OmniParser |
