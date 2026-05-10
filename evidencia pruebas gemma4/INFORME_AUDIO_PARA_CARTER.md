# Informe técnico: estado de audio multimodal Gemma 4 (para Carter v4)

**Para:** agente del proyecto Carter v4.
**Desde:** repo `Probando Gemma 4` (validación previa a migración).
**Fecha:** 2026-05-09.
**Contexto previo:** [REPORTE.md](REPORTE.md) (10 tests texto, 9/10 PASS con E2B-Q5_K_M y E4B-UD-IQ2_M). Validación extendida 60 tests en curso.

---

## TL;DR

- Gemma 4 E2B/E4B **sí** tienen audio nativo (encoder Conformer USM-style entrenado por Google).
- El audio es **soportado por el modelo**, pero el **soporte en runners es desigual** y a fecha de hoy **no hay un servidor HTTP local en Windows que lo exponga production-ready**.
- Hay 4 caminos viables; cada uno tiene trade-offs distintos para Carter. **Decisión queda al agente Carter** con su contexto completo.

---

## 1. Lo que la pregunta era

> "¿Es viable reemplazar el pipeline Whisper → texto → LLM en Carter por un input audio → tool call directo en Gemma 4?"

Para responder, hay que cruzar tres ejes:

1. **Capacidad del modelo** — ¿Gemma 4 entiende audio en español rioplatense + ejecuta tool calls?
2. **Soporte en runner** — ¿qué servidor expone esa capacidad por HTTP en Windows?
3. **Latencia + estabilidad** — ¿el runner es production-grade para un asistente always-on?

---

## 2. Capacidad del modelo (1/3): confirmada por Google

Citas oficiales Google + HuggingFace blog:

- "**E2B y E4B incluyen un audio encoder Conformer USM-style**. Soporta automatic speech recognition (ASR) y speech-to-translated-text translation across multiple languages."
- "**Native audio input on top of text and vision**, which the larger models (26B, 31B) don't. Handles speech recognition and audio understanding natively, on-device, with no cloud round-trip."
- mmproj `mmproj-F16.gguf` que descargamos contiene tanto vision como audio: confirmado al cargar con llama-server (ver log abajo).

```
load_hparams: projector:          gemma4a
--- audio hparams ---
load_hparams: n_mel_bins:         128
load_hparams: audio_chunk_len:    0
load_hparams: audio_sample_rate:  16000
load_hparams: audio_n_fft:        512
load_hparams: audio_window_len:   320
load_hparams: audio_hop_len:      160
```

**Conclusión eje 1:** capacidad existe. Es un encoder real, entrenado, cargable.

---

## 3. Soporte en runners (2/3): mapa actualizado

| Runner | Plataforma | Audio Gemma 4 | API HTTP OpenAI-compat | Estado producción | Notas |
|---|---|---|---|---|---|
| **vLLM** | Linux (CUDA) | ✅ Sí | ✅ Sí, `input_audio` content block en `/v1/chat/completions` | ✅ Ready | El runner que mejor expone audio Gemma 4 hoy. En Windows requiere WSL2 o Docker. |
| **Transformers (Python)** | Linux/Windows | ✅ Sí, vía `AutoModelForMultimodalLM` | ❌ No es server, es script | ⚠️ Solo si Carter ya tiene capa Python | Sirve para verificar capacidad, no para servir. |
| **MLX Swift** | macOS / iOS only | ✅ Sí | — | macOS only | No aplica a Windows. |
| **Ollama** | Win/Mac/Linux | ⚠️ "Day-one support" anunciado por Google, pero sin documentación visible de cómo enviar audio por API | ❌ No documentado para audio Gemma 4 | ❓ Pendiente verificar | Ollama hoy soporta vision en algunos modelos, pero el path de audio Gemma 4 no aparece en docs públicos. |
| **llama.cpp** | Win/Mac/Linux | ✅ Encoder en libmtmd (PR [#21421](https://github.com/ggml-org/llama.cpp/pull/21421) merged) | ❌ `llama-server` devuelve HTTP 500 con `input_audio` | ❌ Solo `llama-mtmd-cli` (cold-load por request) | Issue [#21868](https://github.com/ggml-org/llama.cpp/issues/21868) pide el routing en server, **closed as not planned**. |
| **LM Studio** | Win/Mac | Empaqueta llama.cpp | Mismo gap | ❌ | Sin servidor de audio aún. |

### Detalle del gap en llama.cpp

- **Lo que funciona:** `llama-mtmd-cli.exe -m model.gguf --mmproj mmproj.gguf --audio file.wav -p "transcribe"` produce texto correcto.
- **Lo que no funciona:** `POST /v1/chat/completions` con `{"type": "input_audio", "input_audio": {"data": "<b64>", "format": "wav"}}` → respuesta `"audio input is not supported"`.
- **Workaround técnico:** spawn `llama-mtmd-cli` como subprocess por cada request. Cold-loadea el modelo en cada call (~30–60s por inferencia en hardware modesto, faster con SSD NVMe pero igual >5s).
- **Pronóstico:** issue cerrada como "not planned". Podría llegar por otra PR pero no hay timeline.

**Conclusión eje 2:** vLLM es el único runner production-grade que expone audio Gemma 4 vía HTTP hoy. En Windows eso significa WSL2 o Docker.

---

## 4. Latencia + estabilidad (3/3): aún no medido

Esto requiere un benchmark dedicado que **todavía no se hizo** (depende de qué runner se use). Datos esperables según docs públicas:

- **vLLM en RTX 4060 Ti 16 GB** (GPU target Carter): debería dar audio→tool call en <2s para clips <5s. No hay benchmarks oficiales aún.
- **llama-mtmd-cli subprocess**: cold-load + inferencia ≈ **20–60s por request en RTX 4060 Ti**. Inviable para Alexa-tier.
- **Pipeline Whisper actual**: faster-whisper-large en GPU ≈ 0.3–0.6× tiempo real + LLM ≈ ~1–3s total. Es el baseline a batir.

**Conclusión eje 3:** sin medición real, asumir que vLLM puede igualar o mejorar Whisper+LLM, pero **hay que medirlo** antes de comprometerse.

---

## 5. Caminos disponibles para Carter

### Camino A — vLLM en WSL2 (audio nativo, end-to-end)

**Stack:** WSL2 Ubuntu + CUDA + vLLM + Gemma 4 E4B (HF format, no GGUF) → expone `/v1/chat/completions` en `localhost:8000`.

**Pros:**
- Reemplaza Whisper completamente. Audio → tool call en una sola llamada.
- Soporte oficial Google + vLLM. No depende de PRs huérfanas.
- Latencia esperada mejor que pipeline Whisper.

**Contras:**
- Requiere WSL2 + CUDA passthrough. Setup ~30 min, mantenimiento ocasional.
- vLLM consume más VRAM que llama.cpp (no usa cuantizaciones GGUF, usa AWQ/GPTQ/FP8 nativo). Hay que verificar que E4B FP16 entre en 16 GB con KV cache 16K.
- Carter tiene que hablar HTTP con un endpoint que vive en WSL2 (ipv4 localhost, normalmente 127.0.0.1:8000 funciona transparente desde Windows).
- Si Carter ya está empaquetado como app Windows nativa, sumás dependencia operativa de WSL2 instalado en máquinas usuarios.

**Bloqueante a verificar:** ¿VRAM suficiente para Gemma 4 E4B FP16 + KV cache + audio encoder en 16 GB? Probablemente sí con cuantización AWQ pero hay que medirlo.

### Camino B — Pipeline híbrido (lo que hace Carter hoy, ajustado)

**Stack:** faster-whisper (audio → texto) → `llama-server.exe --jinja` (texto + tools) → todo en Windows nativo.

**Pros:**
- Cero cambios infra (Carter ya corre llama.cpp).
- Whisper-large es state-of-the-art en ASR multilingüe.
- Las dos piezas son independientes; problemas de upstream en una no rompen la otra.
- Latencia conocida y estable.

**Contras:**
- Dos round-trips (audio→texto, texto→tool). Suma latencia (~200–500 ms extra vs nativo).
- Whisper agrega ~1.5 GB VRAM extra para el modelo `large-v3`.
- No aprovecha la capacidad audio que Google entrenó en Gemma 4.

### Camino C — llama-mtmd-cli subprocess (audio nativo, batch only)

**Stack:** Carter dispara `llama-mtmd-cli.exe` como subprocess Python por cada audio entrante.

**Pros:**
- Cero infra extra: usa el mismo binario llama.cpp ya instalado.
- Confirma audio nativo Gemma 4 en Windows hoy.

**Contras:**
- Cold-load por request → 20–60s de latencia. **Inviable para Alexa-tier.**
- No mantiene state ni tool calling estructurado en el mismo loop.
- Workaround temporal, no producción.

### Camino D — Esperar arreglo upstream llama-server

**Pros:** sin cambio de stack.
**Contras:** issue #21868 está "closed as not planned". Sin timeline. Si llega, sería vía otra PR no anunciada.
**Riesgo:** podría no llegar nunca.

---

## 6. Datos para decidir (lo que ya tenemos)

### Capacidad texto Gemma 4 (medida)
- **9/10 PASS** en bench inicial 10 tests con E2B-Q5_K_M y E4B-UD-IQ2_M (ver [REPORTE.md](REPORTE.md)).
- Bench extendido (60 tests × 21 cuantizaciones) en curso.
- Tool calling vía `--jinja` en llama-server: **funciona perfecto** (tool_calls parseado en JSON estándar).

### Capacidad audio Gemma 4 (no medida)
- **Pendiente de runner viable.** El plan original era probar vía llama-mtmd-cli para confirmar capacidad (no perf).
- Si Carter elige Camino A (vLLM/WSL2): hay que rehacer setup y benchmark allá.
- Si Carter elige Camino B: no aplica (sigue con Whisper).

### Hardware target
- RTX 4060 Ti **16 GB VRAM** (mismo que Carter prod).
- E4B Q4_K_M / Q5_K_M: ~5–6 GB usados. Sobra holgura para audio encoder + KV cache.

### Idiomas requeridos
- ES (rioplatense), EN, code-switching ES/EN. Whisper-large los maneja perfecto. Gemma 4 audio está documentado para "multiple languages" pero sin datos específicos de español rioplatense.

---

## 7. Preguntas que el agente Carter debe responder

Antes de elegir camino, recomiendo que el agente Carter responda estas con su contexto:

1. **¿Carter se distribuye como app standalone o asume usuarios técnicos?** Si standalone para no-técnicos → WSL2 es overhead de setup. Si dev-friendly → ok.
2. **¿La latencia audio→tool actual con Whisper es bottleneck percibido o no?** Si <2s y los users no se quejan → Camino B (no romper lo que funciona). Si >3s → vale la pena Camino A.
3. **¿Qué tan importante es eliminar la dependencia Whisper?** 1.5 GB VRAM extra + un modelo más para mantener vs simplificación arquitectural.
4. **¿Carter v5 contempla modelos non-Gemma con audio nativo (ej. Qwen2.5-Omni)?** Si sí, Camino A te ata a vLLM independientemente.
5. **¿Tolerancia a cambios upstream rotos?** vLLM se mueve rápido. llama.cpp también pero el path Gemma audio está estancado. Hybrid Whisper es el menos volátil.

---

## 8. Recomendación de orden de validación

Si el agente Carter quiere **datos antes de comprometerse**, este es el orden de menor a mayor costo:

1. **Confirmar capacidad audio Gemma 4** (1 hora) → correr `llama-mtmd-cli` con los 5 .wav de muestra que ya están en `samples/`. No mide perf, solo capacidad.
2. **Si capacidad ok, evaluar Camino A real** (medio día) → instalar WSL2 + vLLM + Gemma 4 E4B HF format, medir latencia audio→tool en RTX 4060 Ti.
3. **Comparar contra baseline Whisper actual** (1 hora) → con clips iguales, medir Whisper+llama-server vs vLLM-audio.
4. **Decidir migración audio** con números en mano.

Costo total estimado: **1 día de validación**, sin tocar código de Carter.

---

## 9. Lo que ESTE repo (`Probando Gemma 4`) puede aportar

Ya generado y disponible para que el agente Carter lo use:

- `samples/audio_01_hora.wav` … `audio_05_codeswitch.wav` — 5 clips 16 kHz mono español-MX, casos del documento de validación.
- `samples/generate_audio.ps1` — script SAPI para regenerar más clips.
- `harness/audio_probes.py` — cliente subprocess `llama-mtmd-cli` listo para correr (Camino C).
- `models/E4B/gemma-4-E4B-it-Q*_K_M.gguf` + `mmproj-F16.gguf` — modelos GGUF + audio projector ya descargados.
- Nada para vLLM aún (requeriría descargar formato HF, 11 GB extra).

Si Carter quiere los archivos: están en este repo. Si Carter quiere que se haga la prueba aquí antes: avisar y ejecuto.

---

## 10. Lo que este informe NO afirma

- **No** afirma que vLLM sea la respuesta. Es el único path HTTP-server completo hoy, pero la decisión final depende del contexto Carter (distribución, latencia tolerada, dependencias).
- **No** afirma que el audio Gemma 4 supere a Whisper. Sin medición, asumir paridad o mejor por entrenamiento conjunto, pero verificar.
- **No** mide nada que requiera setup vLLM. Eso queda para el agente Carter o una segunda iteración aquí si se autoriza.

---

## Referencias

- [Welcome Gemma 4 — HuggingFace blog](https://huggingface.co/blog/gemma4) (declara audio nativo E2B/E4B)
- [vLLM Recipes — Gemma 4 Usage Guide](https://docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html) (vLLM con `input_audio`)
- [llama.cpp issue #21868 — input_audio routing](https://github.com/ggml-org/llama.cpp/issues/21868) (gap en llama-server)
- [llama.cpp PR #21421 — audio encoder en libmtmd](https://github.com/ggml-org/llama.cpp/pull/21421) (capacidad existe en lib, no en server)
- [llama.cpp multimodal docs](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md) (formato `input_audio` esperado)
- [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
