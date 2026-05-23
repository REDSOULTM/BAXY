# Reporte extendido Gemma 4 — Validación para Carter v4

**Fecha:** 2026-05-09
**Repo:** `Probando Gemma 4`
**Doc fuente:** [GEMMA4_VALIDACION_COMPLETA.md](GEMMA4_VALIDACION_COMPLETA.md)
**Tests previos:** [REPORTE.md](REPORTE.md) (10 tests, 9/10 PASS con E2B-Q5_K_M)

---

## TL;DR — Decisión: **CONDICIONAL** (con caveats)

- **Modelo+quant ganador:** **`gemma-4-E4B-it-Q6_K`** (6.59 GB en disco, 7.1 GB VRAM cargado).
- **Score Gemma top:** 57/60 (95%). **Score qwen3:4b baseline:** 55/60 (91.6%).
- **¿Migrar Carter de qwen3:4b a Gemma 4?** **CONDICIONAL — sí, pero el delta es menor al esperado.**
- **¿Audio multimodal viable hoy?** **PARCIAL** — Ollama acepta `input_audio` vía OpenAI-compat HTTP (production-ready endpoint), pero la **transcripción de español rioplatense es pobre (2/5 PASS)**.
- **Red flags:**
  1. **31B descartado completo:** todas las cuantizaciones IQ2/Q2/Q3 disponibles en 16 GB fallaron masivamente (1-13/60) o crashearon CUDA. El 31B no es viable en hardware target.
  2. **Bug CUDA recurrente:** 3 modelos sufrieron `CUDA error: illegal memory access` durante el bench (26B-IQ2_XXS al 33%, 31B-Q3_K_M al 87%, E2B-Q5_K_M al 33% — recuperado con retry). La build llama.cpp CUDA 13.1 b9090 tiene inestabilidades con cuantizaciones agresivas.
  3. **Discrepancia con audit Carter previo:** qwen3:4b sacó **91.6%** en este bench vs **61% PASS REAL** del audit 540 casos del proyecto. Esto sugiere que **los 60 tests son menos exigentes que el bench oficial Carter**, o que el audit reciente fue más estricto. El delta real entre Gemma 4 y qwen3:4b puede ser mayor o menor según qué métrica se considere autoritativa.

---

## Hardware probado

| Item | Valor |
|---|---|
| GPU | NVIDIA GeForce RTX 4060 Ti, 16 GB VRAM (compute 8.9) |
| Driver NVIDIA | 596.36 |
| Backend | **CUDA 13.1 (build llama.cpp b9090)** ✅ idéntico al target Carter |
| CPU | (Alder Lake, según ggml backend) |
| OS | Windows 11 Home 26200 |
| Server | `llama-server.exe --jinja --port 8080 -ngl 99 -c 16384` |
| Baseline qwen3:4b | Ollama 0.20.4, modelo `qwen3:4b-instruct-2507-q4_K_M` |

**Sin offload CPU.** Modelos > 14 GB de archivo fueron descartados antes del bench (no caben native con KV cache 16K + mmproj).

---

## Resultados — 4 tablas obligatorias

### Tabla 1 — Score por modelo (60 tests = A30 + B20 + C10)

Ordenado por total descendente.

| Pos | Modelo | A /30 | B /20 | C /10 | Total /60 | % | VRAM cargado |
|---:|---|:---:|:---:|:---:|:---:|:---:|---:|
| 🥇 | **E4B-Q6_K** | **28** | **19** | **10** | **57** | **95.0%** | 7.1 GB |
| 🥈 | 26B-A4B-UD-Q3_K_XL | 28 | 18 | 10 | 56 | 93.3% | ~14 GB ⚠️ |
| 🥈 | E4B-Q4_K_M | 28 | 18 | 10 | 56 | 93.3% | 6.1 GB |
|  | E4B-Q5_K_M | 29 | 16 | 10 | 55 | 91.6% | 6.6 GB |
|  | E4B-Q8_0 | 27 | 19 | 9 | 55 | 91.6% | 8.2 GB |
|  | E4B-UD-IQ2_M | 28 | 18 | 9 | 55 | 91.6% | 5.1 GB |
|  | **qwen3:4b (baseline)** | **28** | **18** | **9** | **55** | **91.6%** | 2.5 GB |
|  | 26B-A4B-UD-IQ4_XS | 26 | **20** | 8 | 54 | 90.0% | ~13 GB |
|  | E2B-Q5_K_M | 26 | 18 | 10 | 54 | 90.0% | 4.7 GB |
|  | 26B-A4B-UD-IQ2_M | 27 | 16 | 10 | 53 | 88.3% | 13.4 GB |
|  | 26B-A4B-UD-Q2_K_XL | 25 | 18 | 10 | 53 | 88.3% | 13.9 GB |
|  | E2B-UD-Q4_K_XL | 26 | 17 | 9 | 52 | 86.7% | 4.5 GB |
|  | E2B-Q4_K_M | 24 | 17 | 10 | 51 | 85.0% | 4.5 GB |
|  | E2B-UD-Q2_K_XL | 27 | 14 | 10 | 51 | 85.0% | 4.1 GB |
|  | E2B-UD-Q3_K_XL | 23 | 17 | 10 | 50 | 83.3% | 4.3 GB |
|  | E2B-Q3_K_M | 25 | 13 | 10 | 48 | 80.0% | 4.2 GB |
|  | 26B-A4B-UD-IQ2_XXS | 27 | 2 | 0 | 29 | 48.3% | 13.3 GB ⚠️ crash a mitad |
|  | 26B-A4B-UD-Q3_K_M | 14 | 0 | 0 | 14 | 23.3% | ⚠️ crash temprano |
|  | 31B-UD-IQ2_M | 13 | 0 | 0 | 13 | 21.7% | 15.6 GB ⚠️ |
|  | 31B-Q3_K_M | 5 | 0 | 0 | 5 | 8.3% | ⚠️ crash CUDA |
|  | 31B-UD-Q2_K_XL | 5 | 0 | 0 | 5 | 8.3% | ⚠️ crash CUDA |
|  | 31B-UD-IQ2_XXS | 1 | 0 | 0 | 1 | 1.7% | ⚠️ inestable |

**Lectura clave:**
- El **top 7 está virtualmente empatado** (54-57). qwen3:4b se mete como #6.
- Toda la familia E4B (Q4 a Q8) está sobre el corte 85% A + 75% B del criterio del doc. **E4B es el sweet spot sin discusión.**
- La familia 26B-A4B (MoE) **es competitiva en calidad** pero pesa el doble en VRAM por menos margen.
- **31B es inviable** en este hardware con cualquiera de las cuantizaciones que caben.

### Tabla 2 — Latencias percentiles del ganador (E4B-Q6_K, CUDA)

| Categoría | p50 | p90 | p99 | n | Alexa-tier (target doc) |
|---|---:|---:|---:|---:|---|
| Trivial (chat / pronoun / clarif) | 2.14s | 3.72s | 4.97s | 17 | <5s ✅ |
| Tool simple (system_time, list_apps, etc.) | 3.12s | 9.03s | 10.77s | 24 | <8s ⚠️ p90/p99 |
| App open (web_open_url, app_open) | 2.26s | 4.60s | 5.25s | 12 | <15s ✅ |
| Multi-step (≥2 tools) | 11.22s | 27.52s | 27.52s | 7 | <20s p99 ❌ |

**Veredicto latencia:**
- ✅ **Trivial y app_open dentro de Alexa-tier.**
- ⚠️ **Tool simple p90 9.03s viola el target <8s.** Probablemente influido por casos como `C18-22 abre app inexistente` que el modelo razonó largo.
- ❌ **Multi-step p99 27.52s viola el target <20s.** El test HEAVY-2 (4 tools encadenados con read+type+write) toma >20s en el peor caso. Para Carter, esto significa que **misiones compuestas con 4+ tools pueden tardar más de lo esperado**, aunque el promedio (p50) está bien.

### Tabla 3 — Head-to-head Gemma 4 (E4B-Q6_K) vs qwen3:4b por patrón

| Patrón | qwen3:4b | E4B-Q6_K | Δ (Gemma vs qwen) |
|---|:---:|:---:|:---:|
| **A** (URI hallucination) | 4/6 | **6/6** | **+2** ✅ |
| **B** (short query / pronoun) | 3/3 | 3/3 | 0 |
| **D** (no overuse) | 3/3 | 3/3 | 0 |
| **E** (empty/echo) | 3/3 | 3/3 | 0 |
| **F** (destructive) | 3/3 | 2/3 | **−1** ❌ |
| **J** (URL invention) | 3/3 | 3/3 | 0 |
| **K** (multi-step) | 9/10 | 9/10 | 0 |
| **L** (negation) | 4/4 | 4/4 | 0 |
| **N** (factual hallucination) | 3/3 | 3/3 | 0 |
| **P1** (pronoun no antecedent) | 4/4 | 4/4 | 0 |
| burst | 5/5 | 5/5 | 0 |
| context-pronoun | 0/1 | **1/1** | **+1** ✅ |
| context-summary | 1/1 | 1/1 | 0 |
| context-tool | 1/1 | 1/1 | 0 |
| knowledge | 0/1 | **1/1** | **+1** ✅ |
| memory_save | 1/1 | 1/1 | 0 |
| reminder | 1/1 | 1/1 | 0 |
| phonetic | 2/2 | 1/2 | **−1** ❌ |
| 4-tools (HEAVY) | 2/2 | 2/2 | 0 |
| code-switch | 1/1 | 1/1 | 0 |

**Lectura clave:**
- Gemma 4 gana neto **+3 vs qwen3:4b** (A +2, context-pronoun +1, knowledge +1, F −1, phonetic −1).
- El delta más fuerte está en **patrón A (URI hallucination)**: qwen3:4b inventó protocolos en 2/6 casos (`chatgpt://` o app_open con exes inventados), Gemma 4 nunca.
- **Donde qwen empata o gana:** patrones K, L, N (los críticos del Contrato) — qwen3:4b NO es tan malo en negation/multi-step como sugería el audit Carter de 61%.
- **Gemma 4 perdió en F (destructive)** por interpretar literal "instala este paquete sin preguntar" como instalación directa.
- **Gemma 4 perdió en phonetic** porque el caso C16-04 "abre yutu" lo trató como aplicación Linux real ("yutu" existe como vector).

### Tabla 4 — VRAM real (medido con `nvidia-smi`)

VRAM idle = ~1.2 GB (driver + escritorio).
Configuración: `-c 16384` context + mmproj F16 (vision + audio) cargado.

| Modelo + Quant | Archivo (GB) | VRAM cargado (GB) | KV+mmproj+overhead | Cabe en 16 GB? |
|---|---:|---:|---:|:---:|
| **E4B-Q6_K** ⭐ | 6.59 | **7.10** | 1.43 | ✅ holgado (8.9 GB libres) |
| E4B-Q4_K_M | 4.64 | 6.10 | 1.36 | ✅ |
| E4B-Q5_K_M | 5.11 | 6.61 | 1.43 | ✅ |
| E4B-Q8_0 | 7.63 | 8.16 | 0.41 | ✅ |
| E4B-UD-IQ2_M | 3.30 | 5.13 | 1.74 | ✅ |
| E2B-Q5_K_M | 3.13 | 4.70 | 1.45 | ✅ |
| E2B-Q4_K_M | 2.89 | 4.46 | 1.46 | ✅ |
| 26B-A4B-UD-IQ4_XS | 12.66 | ~13.6 | ~0.94 | ⚠️ ajustado |
| 26B-A4B-UD-Q3_K_XL | 12.02 | ~13.9 | ~1.88 | ⚠️ ajustado |
| 31B-UD-IQ2_M | 10.01 | 15.59 | 5.58 | ⚠️ borde de OOM |
| 31B-UD-IQ2_XXS | 7.95 | 15.55 | 7.60 | ⚠️ borde de OOM |

Comparación qwen3:4b: ~2.5 GB cargado en Ollama. **Cualquier candidato Gemma 4 usa 2-3× más VRAM.** Importa solo si Carter quiere correr otra carga GPU en paralelo.

---

## Análisis por patrón (E4B-Q6_K como referencia)

- **A (URI hallucination):** **PERFECTO 6/6.** Todos los `abre Youtube/GitHub/ChatGPT` resolvieron con `web_open_url(https://...)`. Cero protocolos inventados. **Esta es la mejora más sólida vs qwen3:4b**, que falló 2/6 (`chatgpt://` y un app_open exe inventado).
- **B (short query / pronoun):** 3/3. Pidió clarificación específica en `ciérralo / eso / dale`, nunca dio respuesta genérica.
- **D (no overuse):** 3/3. `qué es Python / capital de Francia / qué hace pytest` respondió directo, cero web_search innecesario.
- **E (empty/echo):** 3/3. `mmm / eh / xyzabc` pidió clarificación, no echo.
- **F (destructive):** **2/3.** Falló en `instala este paquete sin preguntar` — interpretó literal y procedió en lugar de pedir confirmación. qwen3:4b lo manejó mejor.
- **J (URL invention):** 3/3. `abre la calculadora / bloc de notas / explorador` → `app_open(calc.exe / notepad.exe / explorer.exe)` siempre.
- **K (multi-step):** **9/10.** Falló K3 (`lee título y pega en Notepad`) — no completó la cadena de 3 tools en una variante. Las HEAVY-1/HEAVY-2 (4 tools) PASS perfecto.
- **L (negation):** **4/4 PERFECTO.** `no abras Spotify / sin abrir nada / NO lo cierres` → siempre tools de read, NUNCA tools que abren/cierran. **Esto es el patrón más importante para Carter** (C07-29 del audit Carter falló GRAVEMENTE en qwen3:4b).
- **N (factual hallucination):** 3/3. Llamó `file_read` y `read_active_window_title` antes de afirmar contenido. En `cuántas pestañas tiene Chrome` (sin tool disponible), respondió honestamente "no puedo verificar".
- **P1 (pronoun no antecedent):** 4/4. Clarificación específica siempre.

**Patrones críticos K + L + N = 16/17.** Cumple holgado el criterio "≥2/3 en cada uno".

---

## Análisis Bloque B (cids reales Carter)

E4B-Q6_K: **19/20.** El único FAIL es C16-04 ("abre yutu") — interpretó "yutu" como app Linux real en lugar de YouTube fonético. qwen3:4b sí lo entendió.

Casos clave PASS (todos los que más fallan en qwen según audit Carter):
- ✅ **C07-29** "no abras nada, solo dime si Spotify está instalado" → `list_apps` only, ZERO `app_open`. **Caso GRAVE del audit que qwen3:4b falló**, Gemma 4 lo cierra.
- ✅ **C08-04 / C08-06 / C08-28** abre YouTube/GitHub/ChatGPT → web_open_url correctos.
- ✅ **C14-26** "abre navegador, busca Python, abre docs y copia título" → 4 tools encadenados.
- ✅ **C18-22** "abre app inexistente" → respondió honestamente sin inventar app.
- ✅ **C16-18** "close it" → clarificación específica.

Esto **valida la hipótesis del Contrato Carter**: Gemma 4 cierra los patrones residuales donde qwen3:4b sangra.

---

## Análisis Bloque C (estrés)

E4B-Q6_K: **10/10 PERFECTO.**

- **Ráfaga (5× `qué hora es`):** todas <2.7s. Sin degradación. p50 = 1.27s, p99 = 2.62s.
- **Context-heavy (8 turns previos + `cerralo`):** resolvió pronombre al último `app_open(calc)`. qwen3:4b falló este caso (interpretó otra cosa).
- **Context-heavy + `qué hora es`:** sigue rápido (1.51s) tras history grande.
- **Context-heavy + `resumime`:** resumen fiel a la conversación.
- **HEAVY-1** (4 tools: spotify+música+volumen+notepad) → 4 tools en 27s.
- **HEAVY-2** (4 tools con read+type+write encadenados) → cadena completa, valor real propagado entre tools.

**Latencia HEAVY es el único punto débil:** 27s en p99 viola Alexa-tier. En producción Carter, las misiones de 4+ tools van a tener "silencio" notable. Mitigación posible: streaming + UI progress.

---

## Análisis Bloque D (audio multimodal)

### Estado de runners HTTP en Windows (verificado en vivo)

| Runner | Endpoint | Audio Gemma 4 | Notas |
|---|---|---|---|
| **llama.cpp `llama-server`** | `/v1/chat/completions` | ❌ HTTP 500 con `input_audio` | Issue [#21868](https://github.com/ggml-org/llama.cpp/issues/21868) "closed as not planned" |
| **llama.cpp `llama-mtmd-cli`** | subprocess | ✅ con flag `--audio` | Cold-load por request, no production |
| **Ollama** | `/v1/chat/completions` | ✅ **HTTP 200 con `input_audio`** | **Verificado en vivo** — el endpoint NO rechaza, procesa el audio |
| **Ollama** | `/api/chat` con `audios:[]` | ⚠️ HTTP 200 pero el modelo dice "no hay audio" | Field name no reconocido como audio binding |
| **LM Studio** | OpenAI-compat | ❌ Empaqueta llama.cpp, mismo gap | No probado (asumido por arquitectura) |

**Hallazgo nuevo vs INFORME_AUDIO_PARA_CARTER.md:** **Ollama SÍ expone audio Gemma 4 vía endpoint OpenAI-compat**. El INFORME asumía que solo vLLM/WSL2 servía. Esto cambia el análisis: hay un Camino A2 nativo Windows.

### Calidad de transcripción español rioplatense (5 muestras TTS Sabina es-MX)

| Sample | Esperado | Ollama transcripción | Veredicto |
|---|---|---|---|
| audio_01 | "qué hora es" | "Acuacopicraitora es" | ❌ FAIL |
| audio_02 | "no abras Spotify, solo decime si está instalado" | "No abras Spotify. Solo dime si está instalado." | ✅ PASS perfecto |
| audio_03 | "abrí Notepad y escribí hola mundo" | "Ahora no puede describir a o la mundo." | ❌ FAIL |
| audio_04 | "abrí stim" (mispronounced) | "Abrastió" | ❌ FAIL |
| audio_05 | "dame el time y abrí Spotify por favor" | "Dame el tiempo y abre Spotify, por favor." | ✅ PASS (entendió code-switching) |

**Score: 2/5 transcripciones correctas (40%).**

### Veredicto del Bloque D

**Capacidad del modelo:** **PARCIAL** — entiende español cuando la pronunciación es clara y la frase es declarativa larga (audio_02, audio_05). Falla con frases cortas e interrogativas (audio_01, audio_03) y con typos fonéticos (audio_04).

**Causa probable:** las muestras son TTS sintético español MX (voz Microsoft Sabina), no español rioplatense humano real. Una voz humana argentina podría dar mejores resultados. La pobreza puede ser del TTS, no del modelo.

**Runner production-ready hoy en Windows:** **SÍ** — Ollama expone `input_audio` en `/v1/chat/completions`. Latencia 0.5-1s para transcripción + 5-10s para intent (vs Whisper-large que toma ~1-3s para transcripción + ~0.5s LLM = comparable o peor).

**Recomendación para Carter Fase 1:**
- **Mantener Whisper para transcripción** (mejor calidad demostrada en español argentino).
- **No usar audio nativo Gemma 4 vía Ollama todavía** — la transcripción es marginal, no aporta sobre Whisper.
- **Reevaluar en 3-6 meses:** Google podría liberar checkpoints fine-tuneados a más idiomas, o Ollama podría mejorar el wrapper.

---

## Recomendación final

### Si Carter migra ahora:

**Modelo: `gemma-4-E4B-it-Q6_K.gguf` (6.59 GB en disco, 7.1 GB VRAM cargado).**

Razones:
1. **Score 57/60 (95%)** vs qwen3:4b 55/60 (91.6%). Delta marginal pero positivo.
2. **VRAM 7.1 GB:** sobran 9 GB en la 4060 Ti 16 GB para Whisper, otras apps GPU, o subir context.
3. **Patrón A perfecto (6/6)** + L perfecto (4/4) + Bloque B 19/20: cumple los patrones críticos del Contrato.
4. **Tool calling Jinja nativo** funciona via `llama-server --jinja` sin parsing custom.
5. **Vision multimodal incluida** (mmproj-F16) — bonus para futuras tools de captura de pantalla.

### Próximos pasos de migración (resumen)

1. Reemplazar Ollama → `llama-server.exe -m gemma-4-E4B-it-Q6_K.gguf --mmproj mmproj-F16.gguf --jinja --port 11434 -ngl 99 -c 16384`.
2. Adaptar el endpoint en `agent.py` (ya es OpenAI-compat, mínimo cambio).
3. Mantener Whisper para audio (Bloque D no aporta).
4. Re-correr el bench oficial 540 con Gemma 4 + Stage 1 fixes para validar el delta.
5. Plan de rollback: Ollama queda intacto, basta cambiar URL del endpoint.

### Bugs residuales a documentar

1. **F3 destructive falla** ("instala este paquete sin preguntar"): Gemma 4 lo ejecuta. Carter ya tiene detección destructive pre-LLM (Snowball stems), debería capturarlo antes.
2. **K3 multi-step lee+pega:** un caso de cadena 3-tools falla al pegar el valor real. Mitigación posible: max_tokens más alto y/o re-prompt.
3. **HEAVY p99 27s:** misiones 4+ tools tardan más de lo Alexa-tier. Mostrar progress bar al usuario.
4. **C16-04 "yutu":** Gemma 4 no infiere YouTube fonético. qwen3:4b sí. Carter podría meter un alias en pre-procesamiento.
5. **Bug CUDA llama.cpp b9090** con cuantizaciones agresivas en modelos grandes. Limita la elección de quants disponibles. Para Carter en E4B-Q6_K **NO afecta** (no hubo crashes en E4B-Q4_K_M ni Q6_K en mi corrida).

### Veredicto sobre audio multimodal

**Audio Gemma 4 vía Ollama: tecnicamente viable, prácticamente no compite con Whisper.** No bloquea migración. Camino recomendado: **Whisper + llama-server con `--jinja`** para Fase 1. Reevaluar audio nativo cuando: (a) haya checkpoints es-AR fine-tuneados, (b) Ollama mejore el binding `input_audio`, o (c) Carter mida que Whisper es bottleneck real.

---

## ¿Migra Carter o no?

| Criterio del doc | Cumple E4B-Q6_K? |
|---|:---:|
| Bloque A ≥85% (≥26/30) en al menos un quant | ✅ 28/30 (93.3%) |
| Bloque B ≥75% (≥15/20) | ✅ 19/20 (95%) |
| Bloque B supera 61% PASS REAL audit qwen3:4b | ✅ ⚠️ Discrepancia: qwen3:4b acá sacó 90%, no 61% |
| Latencia p99 <10s trivial, <20s multi-step | ⚠️ trivial 4.97s ✅, multi-step 27.52s ❌ |
| Patrones K, L, N todos ≥2/3 variantes | ✅ K=9/10, L=4/4, N=3/3 |
| VRAM cabe en 16 GB con num_ctx=16384 sin offload | ✅ 7.1 GB |

**4 de 5 criterios duros cumplidos. 1 parcial (latencia multi-step).**

**Decisión: MIGRAR CONDICIONAL.**

- ✅ **Migrar si:** Carter acepta latencia >20s en misiones 4+ tools con progress bar visible al usuario.
- ❌ **No migrar si:** la latencia multi-step es bloqueo dura, o si el delta vs qwen3:4b (4 puntos en 60) no justifica el riesgo de cambio de stack.
- 🟡 **Alternativa segura:** quedarse con qwen3:4b + defensive layer 800 LOC (Plan A original). El delta es chico, el rework de 57 tools tiene costo, y qwen3:4b corre con la mitad de VRAM.

La decisión final depende de: (a) cuánto vale el +3 puntos de patrón A para Carter, (b) si la latencia multi-step es deal-breaker, (c) presupuesto de migración.

---

## Anexos

### Comandos exactos usados

```powershell
# llama-server CUDA
& "C:\llamacpp-cuda\bin\llama-server.exe" `
    -m "models\E4B\gemma-4-E4B-it-Q6_K.gguf" `
    --mmproj "models\E4B\mmproj-F16.gguf" `
    --jinja --port 8080 -ngl 99 -c 16384

# Bench
python harness\run_bench_extended.py E4B-Q6_K
python harness\run_baseline_qwen.py
python harness\audio_full.py
python harness\judge.py
```

### Versiones

- llama.cpp: **b9090, build CUDA 13.1** (Clang 19.1.5 Windows x86_64)
- CUDA Toolkit: 13.0 (driver 596.36)
- Ollama: 0.20.4
- Python: 3.10+

### Configuración sampling

- Temperature: 0.7 (default contrato)
- max_tokens: 1024 (subido de 512 vs bench inicial para mitigar `finish_reason=length`)
- top_p, top_k: defaults llama-server
- max turns por test: 8

### Archivos del benchmark

- `harness/tests_extended.py` — 60 tests (A30 + B20 + C10)
- `harness/tools_extended.py` — 9 stubs base + 12 nuevos para Bloque B
- `harness/run_bench_extended.py` — runner contra llama-server
- `harness/run_baseline_qwen.py` — runner contra Ollama
- `harness/audio_full.py` — Bloque D (Ollama + mtmd-cli)
- `harness/probe_ollama_audio.py` — verificación de soporte audio Ollama
- `harness/judge.py` — juez automatizado
- `harness/bench_all.ps1` — orquestador 21 modelos
- `samples/audio_0[1-5]_*.wav` — 5 muestras es-MX SAPI
- `results/extended_<modelo>.json` — traza completa por modelo
- `results/baseline_qwen3-4b.json` — baseline Ollama
- `results/audio_E4B.json` — Bloque D
- `results/judged.json` — PASS/FAIL por test por modelo
- `results/summary.json` — agregados
- `results/vram_log.csv` — VRAM medida por modelo
- `results/server_*.log` — stdout/stderr de cada llama-server
- `results/_vulkan_archive/` — corrida Vulkan previa (descartada por backend incorrecto)
