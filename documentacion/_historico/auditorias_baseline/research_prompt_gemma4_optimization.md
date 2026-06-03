# Prompt de auditoría exhaustiva — Optimización de Carter Agent (local Windows)

> **Cómo usar este prompt**: pegarlo verbatim en un agente de investigación con
> acceso a web (Perplexity Pro, ChatGPT Deep Research, Claude con web search,
> Gemini Deep Research). El agente tiene que tratar cada sección como
> requisitos no-negociables y devolver un informe estructurado.

---

## 0. Rol y misión

Eres un investigador senior en sistemas de IA local. Tu cliente acaba de
publicar un asistente personal local de Windows 11 construido sobre la
familia **Gemma 4** de Google (lanzada hace **menos de un mes** desde
la fecha de esta consulta). El sistema corre íntegramente en la máquina
del usuario sin tráfico saliente, y necesita funcionar en hardware de
6 GB de VRAM o más.

Tu misión es producir **el informe más riguroso posible** sobre cómo llevar
este sistema al 100% de optimización y calidad. No es opinión: cada
afirmación debe citar la fuente (issue de GitHub, paper, post oficial,
benchmark independiente con fecha). Si un dato no está medido o solo se
asume, marcarlo como `[EXTRAPOLATED]` con la base de extrapolación.

**Sesgo crítico que debes corregir**: muchos blogs y videos que recomiendan
flags y cuantizaciones para Gemma 4 son de Gemma 3 o Gemma 3n
(arquitecturas predecesoras) y los autores se confunden de versión. Antes
de aceptar una recomendación, **verifica que aplique a Gemma 4** explícita
y no a Gemma 3/3n. Si la fuente solo dice "Gemma" sin versión, marcarla
como `[VERSION_UNCONFIRMED]` y no la uses para decisiones críticas.

**Restricción temporal**: prioriza fuentes posteriores al release de
Gemma 4 (consultar la fecha exacta del release oficial de Google como
primer paso). Cualquier benchmark/issue/PR anterior al release es
referencial pero no normativo para esta familia.

---

## 1. Contexto del sistema bajo auditoría

### 1.1 Identidad del proyecto

- **Nombre**: Carter Agent (antes Gemma 4 Agent; paquete Python `gemma4_agent`).
- **Plataforma**: Windows 11 nativo (no WSL, no Docker, no servidor).
- **Lenguaje**: Python 3.10+, ~32 600 LoC.
- **Modo de operación**: agente con herramientas (tool-calling) +
  conversación de voz tipo "Alexa local".
- **Objetivo de UX**: latencia mic→texto ≤ 2 s, latencia texto→audio
  primer fonema ≤ 1 s tras primer punto del LLM.
- **Privacidad**: 100% local. Cero llamadas a APIs externas con
  identificadores del usuario.
- **Estado actual**: 71/71 unit tests del repo PASS, 143/143 smoke tests
  PASS sobre 62 tools del catálogo, bench Carter 540 reporta 99.81 %
  PASS con el modelo grande del dev (E4B-Q6_K).

### 1.2 Hardware target (orden de prioridad)

1. **6 GB de VRAM** (RTX 3050 6 GB, 4050 mobile, 3060 6 GB) — **prioridad alta**, es el caso límite que define la app.
2. **8 GB de VRAM** (3060 Ti, 4060, 2080) — caso cómodo.
3. **12 GB+ de VRAM** (3060 12 GB, 4060 Ti 16 GB, 4070+) — para el dev/power user.
4. **CPU-only** (sin GPU dedicada): degradado aceptable, no objetivo.

### 1.3 Stack técnico actual

| Componente | Implementación | Estado |
|---|---|---|
| LLM runtime | `llama-server.exe` de `llama.cpp` (CUDA build) | Ya funcionando |
| Tool calling | Formato OpenAI con `--jinja` + `--parse-tool-calls true` | Funciona, 4400+ invocaciones sin fallo de parseo en bench |
| STT | `faster-whisper` int8 CPU + `silero-vad` + `whisper-streaming` (LocalAgreement-2) | Pipeline reescrito recientemente anti-alucinaciones |
| Wake word | `Vosk small es-0.42` CPU | Funcional |
| TTS | `Piper VITS+ONNX` CPU (voz `es_MX-claude-high` o `es_ES-sharvard-medium`) | Funcional |
| Embedder/Rerank | Local Sentence-Transformers / cross-encoder, opcional por perfil | Existe |
| Vision opcional | mmproj F16 multimodal de Gemma 4 (visión + audio integrados) | Funciona pero tiene leak conocido |
| UI | PyQt6 + React (UI Field) | Funciona |

### 1.4 Catálogo de modelos descargados localmente

| Archivo | Tamaño en disco | VRAM cargada medida (RTX 4060 Ti) |
|---|---:|---:|
| `models/E2B/gemma-4-E2B-it-Q4_K_M.gguf` | 2.9 GB | **4.46 GB** |
| `models/E2B/gemma-4-E2B-it-Q5_K_M.gguf` | 3.1 GB | **4.70 GB** |
| `models/E2B/gemma-4-E2B-it-Q3_K_M.gguf` | 2.4 GB | 4.21 GB |
| `models/E2B/gemma-4-E2B-it-UD-Q2_K_XL.gguf` | 2.2 GB | 4.08 GB |
| `models/E4B/gemma-4-E4B-it-Q4_K_M.gguf` | 4.6 GB | **6.10 GB** |
| `models/E4B/gemma-4-E4B-it-Q5_K_M.gguf` | 5.1 GB | 6.61 GB |
| `models/E4B/gemma-4-E4B-it-Q6_K.gguf` | 6.6 GB | **7.10 GB** ⭐ (modelo del dev) |
| `models/E4B/gemma-4-E4B-it-Q8_0.gguf` | 7.6 GB | 8.16 GB |
| `models/E4B/gemma-4-E4B-it-UD-IQ2_M.gguf` | 3.3 GB | 5.13 GB |
| `models/26B-A4B/gemma-4-26B-A4B-it-UD-IQ2_XXS.gguf` | 9.2 GB | 9.24 GB |
| `models/26B-A4B/gemma-4-26B-A4B-it-UD-IQ4_XS.gguf` | 12.7 GB | 12.66 GB |
| `models/26B-A4B/gemma-4-26B-A4B-it-MXFP4_MOE.gguf` | 15.4 GB | (no medido) |
| `models/26B-A4B/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf` | 15.8 GB | (no medido) |
| `mmproj-F16.gguf` (E4B) | 0.92 GB | 0.92 GB |
| `mmproj-BF16.gguf` (E4B) | 0.92 GB | (no medido) |
| `mmproj-F16.gguf` (26B-A4B) | 1.1 GB | (no medido) |

**Familias confirmadas en la línea Gemma 4**:
- **E2B** y **E4B**: MatFormer (no MoE) — pequeños y rápidos.
- **26B-A4B**: MoE con ~4 B parámetros activos por token.
- **31B**: existe pero no se distribuyó oficialmente.

### 1.5 Perfiles de runtime actualmente configurados

| Perfil | Modelo elegido | ctx | Vision | Voice | VRAM objetivo |
|---|---|---:|---|---|---|
| performance | (env var del usuario, Q6_K) | 32K | ON (mmproj) | ON (CPU) | 12 GB+ |
| **balanced** | **E2B-Q5_K_M** | 8K | OFF | ON (CPU) | **6 GB** |
| light | E2B-Q4_K_M | 4K | OFF | ON (CPU) | 4 GB |
| standby | (server off) | — | — | OFF | 0 |

Flags actuales del server (todos los perfiles): `-ngl 99 --jinja --flash-attn on --parallel 1 --ctx-checkpoints 1`. Para balanced/light se añade `--no-mmap` por VRAM tight.

### 1.6 Catálogo de 62 tools (resumen)

Las tools son compound (`{tool}({action}=...)`) y cubren: filesystem,
terminal, system, package, network, browser_real (Playwright),
database (sqlite/postgres/mysql con read-only enforcement),
maintenance (Defender/services/event logs), gui (OCR + click_text),
uia, vision, audio, notifications, routines/watchers, memory,
knowledge, smart_home (Home Assistant), media_edit (ffmpeg), etc.

Auditoría reciente cerró 8 cross-cutting (PS injection, confirmation
gating duro, private state API, json.loads guards, PID recycling,
credenciales redacción, OCR screen coords, rollback docs) + todos los
hallazgos críticos individuales. Anti-bypass de gates duros verificado
6/6 PASS en smoke tests.

### 1.7 Restricciones no negociables

- llama.cpp como runtime único (vLLM/Ollama/MLC/TensorRT-LLM **descartados** por requerir WSL2, Docker o cambio de formato).
- Sampling oficial Google: `T=1.0 / top_p=0.95 / top_k=64 / repeat_penalty=1.0 / max_tokens=1280`.
- Tool calling via `--jinja` (template oficial de Gemma 4) + parser nativo de llama-server.
- Cero dependencias nuevas pesadas (ya hay 32K LoC; queremos consolidar, no expandir).
- Compatibilidad Python 3.10+ obligatoria.

### 1.8 Issues conocidos relevantes (al momento de escribir esto)

- llama.cpp `#21868`: `input_audio` en `/v1/chat/completions` "closed not planned".
- llama.cpp `#21468`: `cache_reuse` (host-memory prompt caching, ~93% TTFT reduction) **roto en Gemma 4**. PR `#22288` abierto.
- llama.cpp `#21690`: leak en mmproj (~6.4 MiB/imagen + 46 MiB host/request). Tras ~60-80 imágenes hay OOM en 6 GB.
- llama.cpp `#22673`: MTP drafters merged solo para Qwen3.x; Gemma 4 heads no liberados por Google.
- localbench substack: "Gemma 4 26B-A4B es el modelo más sensible a KV quant testeado, KL 0.377 con q8_0 KV vs Qwen <0.04". E2B/E4B no son MoE pero está sin confirmar si la sensibilidad aplica.

---

## 2. Preguntas que el informe DEBE responder

Cada pregunta se entrega numerada y con respuesta tabulada o estructurada.
Si la respuesta requiere "depende", listar los casos. **Cero respuestas
de tipo "podría", "suele", "generalmente"** sin cita.

### Bloque A — Cuantizaciones óptimas por hardware

A1. Para cada nivel de VRAM (4, 6, 8, 12, 16, 24 GB), **¿cuál es la
combinación modelo+cuantización Gemma 4 que maximiza calidad real medida
en benchmarks publicados después del release de Gemma 4**?
  - Distinguir: tareas multi-step agentic (tool calling), conversación
    larga, razonamiento, código.
  - Para cada respuesta dar: nombre exacto del GGUF (Unsloth/Bartowski/
    oficial Google), VRAM medida en una RTX consumer reciente, calidad
    relativa al BF16 si está medida, fuente.

A2. **¿Las cuantizaciones UD (Unsloth Dynamic) ganan a las K_M tradicionales
en Gemma 4 específicamente?** Si la ventaja existe, ¿en qué tier de
quant (Q2, Q3, Q4, Q5)? Si no, ¿cuál es la pérdida exacta?

A3. **¿`MXFP4_MOE` (cuantización experimental para Gemma 4 26B-A4B) está
maduro?** Reporta: estabilidad, soporte upstream en llama.cpp build
≥b9090, calidad vs Q4_K_M y vs IQ4_XS, hash conflicts conocidos.

A4. **¿IQ4_XS supera a Q4_K_M en Gemma 4 E4B y 26B-A4B?** Citar
benchmarks específicos de la familia (no de LLaMA/Mistral).

### Bloque B — Flags óptimos de llama-server para Gemma 4

B1. **Lista exhaustiva de flags `llama-server` que afectan calidad o
latencia en Gemma 4**, con valor recomendado por familia (E2B/E4B/
26B-A4B) y nivel de VRAM. Para cada uno:
  - Default actual en `b9090+`.
  - Valor recomendado y por qué.
  - Riesgo de tocarlo.
  - Interacción con otros flags.

Flags que el informe DEBE cubrir explícitamente (no asumas que el lector
los conoce):
  - `--flash-attn on/off/auto`
  - `--cache-type-k`, `--cache-type-v` (con foco en si `q8_0` o `q5_1`
    es seguro en Gemma 4 — el dato de localbench dice que el 26B es muy
    sensible, ¿qué pasa con E2B/E4B?)
  - `--no-mmap` vs default
  - `--mlock`
  - `--n-gpu-layers` (`-ngl`)
  - `--parallel`, `--cont-batching`
  - `--ctx-checkpoints` (recientemente añadido a llama-server)
  - `--cache-reuse` (¿reparado en alguna build post-`#21468`?)
  - `--threads`, `--threads-batch`
  - `--ubatch-size`, `--batch-size`
  - `--rope-freq-base`, `--rope-freq-scale` (¿Gemma 4 acepta YaRN para
    extender contexto más allá del entrenado?)
  - `--predict`
  - `--temp`, `--top-p`, `--top-k`, `--repeat-penalty`, `--min-p`,
    `--dry-multiplier`, `--xtc-probability`, `--xtc-threshold`
    (¿qué sampling realmente recomienda Google para Gemma 4 vs el
    sampling que recomendaba para Gemma 3?)
  - `--jinja` (template path correcto para tool calling en Gemma 4)
  - `--parse-tool-calls`
  - `--reasoning-format`, `--reasoning-budget` (¿Gemma 4 soporta reasoning
    como Qwen3?)
  - Cualquier flag nuevo (post-release de Gemma 4) que sea relevante.

B2. **¿Existe alguna combinación de flags que reduzca el VRAM total del
proceso llama-server sin degradar más de 2% en el benchmark Carter 540?**
Ejemplo: `--mlock` + `--no-mmap` + KV q8_0 ¿gana o pierde?

B3. **¿La build oficial de llama.cpp para CUDA (release binaries) o
compilar desde fuente con flags específicos da mejoras medibles en
Gemma 4?** Reporta flags de cmake/make relevantes: `LLAMA_CUDA_F16`,
`LLAMA_CUDA_FORCE_MMQ`, `LLAMA_CUDA_DMMV_X`, etc.

### Bloque C — Tool calling en Gemma 4

C1. **¿El template Jinja oficial de Gemma 4 para tool calling es estable?**
Reporta: si Google publicó un template canónico, dónde, version, y si la
implementación de llama-server `--jinja` lo respeta sin parches.

C2. **¿Hay bugs conocidos en el parser de tool calls de llama-server
específicos para Gemma 4** (formato de argumentos, escape de strings,
manejo de tool_calls múltiples en una respuesta)?

C3. **¿Gemma 4 soporta `parallel_tool_calls` nativamente o lo emula?**
Si lo emula, ¿qué pasa cuando el cliente pide múltiples calls en una
respuesta? ¿Hay degradación de calidad?

C4. **¿Existe alguna técnica para mejorar el "tool selection accuracy"
en agentes locales con Gemma 4 sin fine-tuning?** Ejemplos buscados:
function-calling-aware prompting, schema compression, few-shot
embedding en system prompt.

### Bloque D — Latencia y streaming

D1. **¿`--cache-reuse` está reparado para Gemma 4 en alguna build post-
`#21468`?** Reporta build mínimo y comportamiento exacto.

D2. **¿Existe ya soporte de MTP drafters (multi-token prediction) para
Gemma 4 en llama.cpp?** PR `#22673` mergeo Qwen3.x; ¿hay sucesor para
Gemma 4? ¿Google publicó los drafter heads?

D3. **¿Speculative decoding con un "draft model" Gemma 4 E2B sobre target
E4B/26B-A4B funciona?** Reporta: build flags necesarios, ganancia real
en tok/s, costo en VRAM.

D4. **¿Streaming SSE de tool calls en llama-server está completo en
b9090+?** Específicamente: el caso "el modelo emite texto + tool_call
+ texto en el mismo turno" ¿se entrega chunk a chunk sin esperar?

### Bloque E — Visión y audio nativo

E1. **¿El leak de mmproj (`#21690`) está cerrado en build reciente?**
Reporta build mínimo donde el leak fue eliminado y la fuente.

E2. **¿`input_audio` en `/v1/chat/completions` se reabrió en algún PR
post-`#21868`?** Si no, ¿hay algún workaround que NO requiera
`llama-mtmd-cli` con cold-load?

E3. **¿La calidad WER del audio nativo de Gemma 4 en español mejoró en
algún checkpoint posterior al release inicial?** El bench interno
midió 2/5 (40%) vs Whisper-small ~92%. ¿Hay benchmarks publicados que
sugieran que la brecha se cerró?

E4. **¿Conviene reemplazar Whisper-small por Whisper-large-v3-turbo en
CPU?** Reporta RTF en CPU x86 4-6 cores típica, WER es-MX, RAM,
trade-offs.

E5. **¿Hay alternativas open-source a Whisper más rápidas (Distil-Whisper,
NVIDIA Parakeet, AssemblyAI Universal-2) que corran 100% local en CPU
con calidad ≥ Whisper-small en español?**

E6. **TTS open-source local que supere a Piper en español neutro
(es-MX/es-ES)**: ¿Kokoro-82M ha mejorado en español? ¿XTTS-v2 sin
servidor central existe? ¿hay voces es-AR disponibles oficialmente?

### Bloque F — Costos ocultos en el budget de VRAM

F1. **¿Cuál es el overhead real de Windows 11 + CUDA driver + WDDM en
una GPU con ≤8 GB VRAM**, medido en `nvidia-smi` con desktop @1080p
sin nada corriendo? Citar fuente.

F2. **¿Cuánto crece el KV cache en Gemma 4 por cada 1K tokens de contexto,
por familia (E2B / E4B / 26B-A4B) y por precision (F16 / q8_0 / q5_1)?**
Dar la fórmula exacta (n_kv_heads × head_dim × n_layers × 2 × bytes).

F3. **`--ctx-checkpoints` que añadió llama-server recientemente**, ¿es
gratis en VRAM o tiene overhead? Comportamiento exacto.

F4. **¿Hay alguna manera de hacer que el server "duerma" liberando VRAM
sin cerrar el proceso** (para que voice CPU y el resto de la app sigan
funcionando)? Algunos servers tienen `idle` mode; ¿llama-server tiene
algo equivalente?

### Bloque G — Profile switching ("hot-swap")

G1. **Tiempo real de swap entre dos GGUF en llama-server** (mantener
proceso, cambiar `-m` y reload) vs **kill + relaunch**: ¿qué es más
rápido y por qué?

G2. **¿llama-server tiene endpoint para hot-reload de modelo sin perder
la conexión HTTP del cliente?** Si no, ¿qué proyectos lo añaden
(llama-swap, etc.)?

G3. **¿Mantener un GGUF mmaped en RAM mientras otro está en VRAM
acelera el swap subsiguiente?** Cuantificar.

### Bloque H — Calidad medida vs el bench interno (Carter 540)

H1. **Para cada GGUF de la tabla §1.4, ¿qué % de PASS proyecta** la
literatura externa (LMArena, MMLU, GSM8K, HumanEval, RAG-bench) y
**cuál es la correlación esperada con un bench tipo Carter** (540
tareas mixtas: agente local, tool calling, español)?

H2. **¿Hay benchmarks publicados que midan tool calling accuracy en
Gemma 4** específicamente (no Gemma 3)? Citar.

H3. **¿Qué proxies cheap (1-shot eval, GSM8K subset, MT-Bench mini) son
los predictores más fuertes de "PASS rate en un agente local con tool
calling"? Si no se sabe, decirlo.

### Bloque I — Acciones concretas para llegar al 100%

I1. **Top 10 cambios concretos** (cada uno con: archivo a tocar, líneas
aproximadas, mejora esperada en una métrica medible, riesgo, costo de
implementación). Ordenarlos por (impacto × baja-fricción).

I2. **¿Qué cambios deberían ser feature-flagged** para usuarios power
vs default? Ejemplo: KV q8_0 podría ser opt-in si la calidad lo soporta.

I3. **Roadmap de 90 días** para llegar a "100% de optimización dado
nuestras restricciones". Sprints semanales, entregables por sprint.

I4. **¿Qué medir en producción (telemetría local opt-in)** para saber
si la app va bien en máquinas de 6 GB sin recibir feedback explícito?
Métricas, frecuencia, almacenamiento.

---

## 3. Forma del entregable

Estructura obligatoria del informe:

```
# Carter Agent — Informe de Optimización (auditoría externa)

## TL;DR ejecutivo (máx 1 página, 8 bullet points clave con citas)

## 0. Mapa de incertidumbre
   Lista lo que NO se pudo verificar y por qué (fuente caída, dato no
   publicado, requiere medición propia). Si el informe se basa en >40%
   de extrapolaciones, decirlo arriba del todo.

## 1. Bloque A — Cuantizaciones (responde A1-A4)
## 2. Bloque B — Flags llama-server (responde B1-B3)
## 3. Bloque C — Tool calling (responde C1-C4)
## 4. Bloque D — Latencia (responde D1-D4)
## 5. Bloque E — Visión/audio (responde E1-E6)
## 6. Bloque F — Costos ocultos VRAM (responde F1-F4)
## 7. Bloque G — Profile switching (responde G1-G3)
## 8. Bloque H — Calidad medida (responde H1-H3)
## 9. Bloque I — Plan de acción (responde I1-I4)

## Anexo — Fuentes citadas (≥30 fuentes, mínimo)
   Formato: [#] título — autor — fecha — URL — relevancia (1 línea).
```

Cada bloque devuelve:

1. **Hallazgo en negrita** (1 frase).
2. **Evidencia**: cita exacta con fuente y fecha.
3. **Aplicabilidad**: ¿directo en Gemma 4 E2B/E4B/26B-A4B?
4. **Acción recomendada**: archivo del repo + tipo de cambio.
5. **Confianza** (`MEDIDO` / `CITADO` / `EXTRAPOLADO` / `ESPECULATIVO`).

## 4. Calidad de fuentes que debes priorizar

**Tier 1** (cita libremente):
- Blog técnico oficial Google AI / DeepMind sobre Gemma 4.
- Issues / PRs / discussions de `ggml-org/llama.cpp` post-release Gemma 4.
- Repos oficiales: `unsloth/gemma-4-GGUF`, `bartowski/gemma-4-it-GGUF`,
  `google/gemma-4-*` en HuggingFace.
- Benchmarks de organizaciones reconocidas (LMArena, Artificial Analysis,
  Hugging Face Open LLM Leaderboard) con Gemma 4 explícitamente.

**Tier 2** (cita con cuidado):
- Posts técnicos de practitioners conocidos (Bartowski, Unsloth team
  Daniel/Michael, ggerganov, John Allard, etc.).
- Substacks técnicos como localbench, MoE explainers, etc.
- Discussions de r/LocalLLaMA con upvotes >100 y verificación cruzada.

**Tier 3** (NO usar para decisiones críticas; solo señales):
- Videos de YouTube generalistas.
- Tweets sin código/medición.
- Posts de Medium sin autor verificable.

**RECHAZAR explícitamente**:
- Cualquier post que mezcle Gemma 2 / Gemma 3 / Gemma 3n / Gemma 4 sin
  distinguir versiones.
- Posts pre-release de Gemma 4 que extrapolan desde Gemma 3.
- "Reviews" sin números.

---

## 5. Restricciones de forma del informe

- **Idioma**: español neutro (admitido inglés en citas literales).
- **Longitud objetivo**: 15–25 páginas. Más corto si no hay datos; más
  largo solo si cada sección lo justifica.
- **Tablas** preferidas sobre prosa para datos comparativos.
- **NO inventar** números. Si el dato no está en una fuente, decirlo
  con `[NO MEDIDO PÚBLICAMENTE]` y proponer cómo medirlo en casa.
- **NO repetir** lo que ya dijo el cliente en §1. El informe debe agregar
  información nueva, contrastarla o corregirla.
- **Cero "según mi experiencia"** o "lo más común suele ser". Cita o
  silencio.

---

## 6. Auto-evaluación final (incluir en el informe)

Antes de entregar, autoevalúate respondiendo:

```
[ ] ¿Cité ≥30 fuentes con URL y fecha?
[ ] ¿Marqué cada afirmación con su nivel de confianza?
[ ] ¿Distingo Gemma 4 de Gemma 3/3n en cada sección donde aplica?
[ ] ¿El TL;DR cabe en 1 página?
[ ] ¿Identifiqué al menos 3 cosas que el cliente está haciendo MAL?
[ ] ¿Identifiqué al menos 3 cosas que el cliente está haciendo MEJOR
    que la práctica común?
[ ] ¿El roadmap de 90 días es accionable sin recursos infinitos?
[ ] ¿Hay un solo número en el informe que no esté citado o marcado
    como extrapolación?
```

Si alguna casilla queda en `[ ]`, **vuelve a iterar** antes de entregar.

---

## 7. Bonus (si tienes tiempo extra)

- **Análisis de competencia**: comparar el stack (llama.cpp + faster-whisper
  + Piper + Gemma 4) contra alternativas locales recientes (LM Studio,
  Ollama, GPT4All, Jan.ai, Cherry Studio, etc.). Una tabla con
  trade-offs.
- **Quick wins de UX** que no requieren tocar el modelo: pre-warm de KV
  para el system prompt, splash con progreso real, manejo elegante de
  OOM con mensaje claro al usuario.
- **Seguridad operacional**: ¿hay flags de llama-server que reducen el
  superficie de ataque (logs de prompts, endpoints expuestos, CORS)?

---

**Fin del prompt. Empieza la investigación.**
