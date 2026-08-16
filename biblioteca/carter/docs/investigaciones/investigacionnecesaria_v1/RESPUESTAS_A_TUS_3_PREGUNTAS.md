# Respuestas a tus 3 preguntas antes de arrancar la investigación

Buenas. Te respondo las 3 preguntas y armo el paquete completo en esta misma carpeta. **Ya tenés acceso a los 13 archivos** — están en `codigo_carter/`, `research_dossiers/` y `audit_qwen3/`. Ver `INDICE.md` para mapeo numerado.

---

## Pregunta 1: ¿Acceso a los 13 archivos?

**Sí, todos disponibles.** Los empaqueté numerados del 01 al 16 (16 archivos en total porque agregué 3 docs adicionales que ayudan al contexto). Estructura:

```
investigacionnecesaria/
├── INDICE.md                              ← empezá acá
├── RESPUESTAS_A_TUS_3_PREGUNTAS.md        ← este archivo
├── PROMPT_INVESTIGACION.md                 ← prompt original con tus deliverables
├── 01_BENCH_540_CASOS.md                   ← los 540 casos completos del bench oficial
├── 02_full_matrix_runner.py                ← cómo se evalúa cada caso (audit_case + scorer)
├── codigo_carter/
│   ├── 03_models_gemma4.py                 ← config Gemma 4 actual (CORE_PROMPT v2.3 + sampling + flags + turn profiles)
│   ├── 04_agent.py                         ← ReAct loop, max_depth=3, budget 25s
│   ├── 05_tool_retrieval.py                ← anchors actuales, top-K dinámico, multilingual-e5-small
│   ├── 06_adapter_llamacpp.py              ← adapter + filtro thought leakage + multimodal helper
│   ├── 07_verifier_orchestrator.py         ← TOOL_OK_VERIFIER_INCONCLUSIVE + INTENT_NOT_FULFILLED
│   ├── 08_reply_checks.py                  ← anti-eco/anti-genérico/anti-unverified post-LLM
│   └── 09_tools_init.py                    ← lista de tools registradas (cómo se autoload el catálogo)
├── research_dossiers/
│   ├── 10_REPORTE_BENCH_60_CASOS.md        ← bench externo Gemma 4: 55/60 (91.7%) con resultados detallados
│   ├── 11_INFORME_AUDIO.md                 ← análisis de 4 caminos para audio multimodal (NO scope)
│   ├── 12_OPT_GEMMA4_DOSSIER.md            ← research dossier de optimización Gemma 4 (sampling, flags, prompt)
│   └── 13_MULTIMODAL_GEMMA4.md             ← research multimodal Gemma 4 (vision integration)
└── audit_qwen3/
    ├── 14_OPUS_DOSSIER_PATRONES_A_P.md     ← análisis manual del audit qwen3:4b sobre los 540 casos con los 16 patrones residuales
    └── 15_OPUS_DOSSIER_PROYECTO.md         ← reporte Opus alterno con perspectiva de Carter como proyecto
```

**Nota sobre el "PROMPT_INVESTIGACION_FAILS_RESIDUALES_V20.md"** que mencionaba el prompt original: ese archivo no se conservó como standalone, su contenido equivalente (análisis de los 16 patrones A-P sobre el audit qwen3 de 540 casos) está en `14_OPUS_DOSSIER_PATRONES_A_P.md`. Es la mejor referencia disponible para entender qué patrones residuales aparecieron en el audit qwen3:4b.

---

## Pregunta 2: Granularidad del Deliverable 1

**Confirmo: formato "agrupar similares + expandir únicos".** No tabla literal de 540 filas.

El criterio:

1. **Agrupar por patrón** los casos que siguen la misma estructura. Ej: si 25 casos de C06+C07+C08 son "abrir app X" / "cerrar app X", todos resuelven con `gui_deeplink` o `app_open` y la misma tool chain → un párrafo común con la lista de cids cubiertos.

2. **Expandir individualmente** solo los casos que:
   - Tienen patrón único (ej. C04-08 "recuerda temporalmente" — tiene comportamiento distinto a memoria normal)
   - Disparan FALSE_PASS conocidos en el audit qwen3 (ver dossier 14)
   - Requieren multi-step compleja (todos los C14, varios C09)
   - Son casos donde el research dice "Gemma 4 cierra estructuralmente" — esos importa marcarlos para celebrar el ahorro de defensive layer
   - Son casos donde estimás que Gemma 4 IQ2 NO llega (techo del modelo)

3. **Un caso = una fila** solo cuando aporta información nueva. La tabla puede ser ~50-80 filas + grupos agregados que cubran los otros ~460 casos.

Lo que SÍ quiero ver para CADA grupo o caso individual:

- cids cubiertos
- patrón residual identificado (A/B/C/D/E/F/J/K/L/M/N/O/P1)
- tool chain ideal (concreta, no abstracta)
- qué falla en Gemma 4 hoy con la config actual (basado en research + sentido común; no necesitás correr el bench)
- fix concreto: ¿cubre regla CORE_PROMPT? ¿anchor? ¿ReAct policy? ¿vision trigger? ¿no se puede cerrar?

---

## Pregunta 3: ¿Gemma 4 es real o nomenclatura interna?

**Es Gemma 4 real, recién salido. Tu cutoff de conocimiento no lo cubre.**

### Evidencia operacional verificable en el repo

El modelo actual es `gemma-4-E4B-it-UD-IQ2_M.gguf` publicado por Unsloth en Hugging Face:
- URL real: `https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF`
- Tamaño exacto: 3.55 GB (UD-IQ2_M)
- Otras variantes en el mismo repo: E2B, E4B, 26B-A4B, 31B (todos con sufijo "-it" instruct + variantes de cuantización)

### Confirmación por logs de llama-server (no inferencia mía)

Cuando arrancamos `llama-server` con este GGUF, los logs muestran:

```
load_hparams: projector:          gemma4a
--- audio hparams ---
load_hparams: n_mel_bins:         128
load_hparams: audio_chunk_len:    0
load_hparams: audio_sample_rate:  16000
```

El `projector: gemma4a` es la firma del nuevo encoder Conformer USM-style de Gemma 4 (audio nativo + vision). NO existe en Gemma 3.

### Hubo confusión inicial con Gemma 3n

Hubo una sospecha temprana de que era Gemma 3n (que también tiene variantes E2B/E4B con MatFormer architecture). La evidencia operacional confirma que NO:

- Gemma 3n es la familia anterior (anuncio Google mayo 2024)
- Gemma 4 es la nueva familia anunciada por Google el **2 de abril de 2026**
- El blog post oficial: `https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/`
- Model card oficial: `https://ai.google.dev/gemma/docs/core/model_card_4` (last updated 2026-04-17)

### Releases del modelo

- Google lanzó Gemma 4 en abril 2026 con E2B, E4B, 26B-A4B y 31B
- Apache 2.0
- Multimodal nativo (texto + imagen + audio en E2B/E4B; texto + imagen en 26B/31B)
- Audio encoder Conformer USM-style (~300M params)
- Vision encoder ~150M params
- BFCL/τ²-bench scores publicados en model card: E4B = 42.2%, 26B-A4B = 68.2%, 31B = 76.9%
- Native function calling con special tokens (`<|tool>`, `<|tool_call>`, `<|tool_response>`, `<|"|>`)

### Build llama.cpp soportando Gemma 4

PRs específicos que necesitás conocer (todos mergeados antes de mayo 2026):
- #21326: fix Gemma 4 chat template
- #21343: fix Gemma 4 tokenizer
- #21390: final_logit_softcapping
- #21406: newline split fix
- #21418: Gemma 4 specialized parser (`peg-gemma4`)
- #21421: mtmd Gemma 4 audio conformer encoder
- #21500: BOS handling
- #21566: CUDA buffer overlap fix

Build actual del repo Carter: **b9090** (commit `5757c4dcb`, 2026-05-09 12:45 UTC). Confirmado mediante smoke test: tool args salen sin `<|"|>` delimiter leak.

### El research dossier `12_OPT_GEMMA4_DOSSIER.md` tiene TODO esto

Ese archivo (compass_artifact_wf-ea836957) hizo investigación exhaustiva 2026-05-09 sobre Gemma 4 con todas las refs verificadas. Si tu knowledge cutoff no llega, **trabajá sobre los facts establecidos en ese dossier** — son auditados. Puntos clave que el dossier ya tiene resueltos:

1. Sampling oficial Google: T=1.0, top_p=0.95, top_k=64, repeat_penalty=1.0, min_p no especificado
2. Special tokens completos
3. Chat template oficial Google + variantes (Unsloth, vLLM, asf0/gemma4_jinja)
4. Comportamiento de E4B con thinking enabled/disabled (E4B no leakea como sí lo hace 26B/31B)
5. KV cache MUY sensible: q8_0 KV rompe Gemma 4 (KL 0.108 en 31B vs <0.04 en Qwen). f16 obligatorio.
6. Flash attention REQUERIDO (sin FA, V-cache padding blowup en SWA+global hybrid de Gemma 4 — issue #22527)
7. CUDA 13.2 produce poor outputs (Unsloth warning); usar CUDA 12.x. Build b9090 ya viene con CUDA 12.4.

### TL;DR de la pregunta 3

- Es Gemma 4 real, lanzado abril 2026 por Google DeepMind
- Tu knowledge cutoff probablemente termina antes de eso, no podés "saber" Gemma 4 desde tu training
- Pero **NO inventes comportamiento basado en Gemma 3** — hay diferencias fundamentales (audio/vision nativo, special tokens nuevos, peg-gemma4 parser)
- Trabajá sobre lo que dicen los 2 research dossiers (`12_OPT_GEMMA4_DOSSIER.md` + `13_MULTIMODAL_GEMMA4.md`) que ya investigaron Gemma 4 y verificaron todas las refs
- Si en algún punto algo del comportamiento Gemma 4 no está claro en los dossiers ni en el código, marcalo como "información insuficiente, recomiendo experimento mínimo" en lugar de generalizar de Gemma 3

---

## Si tenés más preguntas

Listálas todas juntas en un mensaje y las respondo de un saque antes de que arranques las 6-10h. Mejor invertir 30 min en clarificar que entregar un reporte con asunciones erradas.

Avisame cuando empezás. Adelante.
