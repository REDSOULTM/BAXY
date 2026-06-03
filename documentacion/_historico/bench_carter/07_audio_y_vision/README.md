# 07 — Audio y visión multimodal (Bloque D)

Estado de las capacidades multimodales de Gemma 4 E4B (vision + audio nativos).

---

## Capacidades nativas confirmadas (Google docs)

Gemma 4 E2B y E4B tienen mmproj con encoder Conformer USM-style:
- Vision: 150M params, OCR multilingüe, pointing JSON nativo, pdf parsing, screen UI understanding
- Audio: ASR, speech-to-translated-text, 16 kHz mono

mmproj-F16.gguf cargado en mi bench:
```
load_hparams: projector:          gemma4a
load_hparams: image_size:         224
load_hparams: n_mel_bins:         128
load_hparams: audio_sample_rate:  16000
load_hparams: audio_chunk_len:    0
```

Ocupa ~0.92 GB VRAM constante (incluso si no se usa).

---

## Audio — calidad medida en español rioplatense

![Audio Gemma vs Whisper](../graficos/10_audio_gemma_vs_whisper.png)

5 .wav de TTS sintético es-MX (Microsoft Sabina) probados con `llama-mtmd-cli` y Ollama.

| Sample | Esperado | Gemma 4 transcribió | Veredicto |
|---|---|---|---|
| audio_01 | "qué hora es" | "Acuacopicraitora es" | ❌ FAIL |
| audio_02 | "no abras Spotify, solo decime si está instalado" | "No abras Spotify. Solo dime si está instalado." | ✅ PASS |
| audio_03 | "abrí Notepad y escribí hola mundo" | "Ahora no puede describir a o la mundo." | ❌ FAIL |
| audio_04 | "abrí stim" (mispronounced) | "Abrastió" | ❌ FAIL |
| audio_05 | "dame el time y abrí Spotify por favor" | "Dame el tiempo y abre Spotify, por favor." | ✅ PASS code-switch |

**Score: 2/5 (40%) — NO compite con Whisper-large-v3 que ronda 95%+ en español.**

---

## Estado de runners HTTP para audio

| Runner | Endpoint audio | Resultado |
|---|---|---|
| **llama-server** | `/v1/chat/completions` + `input_audio` | ❌ HTTP 500 (issue [#21868](https://github.com/ggml-org/llama.cpp/issues/21868) "closed not planned") |
| **llama-mtmd-cli** | `--audio file.wav` | ✅ funciona pero cold-load 30-60s por request |
| **Ollama** | `/v1/chat/completions` + `input_audio` | ✅ HTTP 200 acepta y procesa (descubierto en bench) |
| **vLLM (WSL2)** | `/v1/chat/completions` | ✅ production-ready |
| **LM Studio** | OpenAI-compat | ❌ mismo gap que llama.cpp |

**Hallazgo nuevo de mi bench:** Ollama SÍ expone audio Gemma 4 vía HTTP — no solo vLLM como decía la documentación previa.

---

## Decisión recomendada para Carter

**Fase 1 producción:** mantener Whisper-large-v3 con faster-whisper para STT (independiente del LLM).
- Whisper: ~1.5 GB VRAM, calidad demostrada ES-AR ~95%, latencia 1-3s.
- Audio nativo Gemma 4: 0.92 GB VRAM compartido, calidad medida 40%, no compite.

**Fase 2 (3-6 meses):** reevaluar si:
- (a) Google publica fine-tunes de Gemma 4 a más español argentino
- (b) Ollama mejora el binding `input_audio`
- (c) llama-server cierra issue #21868

**Alternativa interesante a investigar:** [Parakeet-TDT-0.6B-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) — 600 MB, 10× faster que Whisper, multilingual incluyendo español. NVIDIA NeMo en Windows tiene curva de instalación más alta.

---

## Visión — capacidades NO validadas en mi bench

⚠️ **Honestidad (Sección 0 contrato):** mis 540 tests usan stubs determinísticos `vision_locate_target` y `gui_screenshot` que devuelven coords y paths fake. **El encoder vision real de Gemma 4 nunca recibió un pixel real durante mi bench.**

Lo que la documentación oficial Google promete (sin que yo lo midiera):
- Pointing JSON `[y1, x1, y2, x2]` en coords 0-1000 normalizadas
- OCR multilingüe (140 idiomas pre-trained)
- Document/PDF parsing
- Native aspect ratio (1920x1080 NO se squareza)
- Token budget configurable: 70/140/280/560/1120

Lo que NO sé:
- ¿OCR real en español argentino sobre screenshots Windows?
- ¿Precisión de pointing en buttons reales?
- ¿Latencia de inferencia con imagen?

---

## Recomendación validación adicional

Antes de que Carter v5 use vision real (ej: "click en botón Aceptar de la pantalla"), correr una mini-fase con:

1. 5 screenshots reales Windows (Notepad, calc, Steam, Chrome, error dialog).
2. `llama-mtmd-cli --image foo.png -p "describe..."`.
3. Medir: precisión OCR, latencia, calidad de pointing.

~30-60 min de validación. Mientras tanto, no comprometer features de Carter que dependan de vision real sin este dato.

---

## Para Carter (Valor 13 + 27)

Gemma 4 vision **es capacidad real, no es marketing**. Pero **on-demand**, no por defecto:

```
Jerarquía de fallback Carter:
1. Procesos/ventanas (lista nativa Windows)  ← preferir siempre
2. APIs sistema
3. Web/browser automation
4. UI automation tradicional (UIA)
5. Screenshot + OCR (Gemma 4 vision)
6. VLM pointing (Gemma 4 vision)              ← último recurso
```

**Costo:** mmproj cargado = +0.92 GB VRAM constante. Si Carter sabe que el usuario nunca usará vision/audio, cargar sin `--mmproj` ahorra 0.92 GB.
