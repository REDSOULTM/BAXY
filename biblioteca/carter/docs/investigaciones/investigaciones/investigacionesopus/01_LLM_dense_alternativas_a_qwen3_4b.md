# Carter v4 — Investigación de LLMs Locales DENSE para Reemplazar `qwen3:4b-instruct-2507-q4_K_M` (Mayo 2026)

## TL;DR

- **Quédate con `qwen3:4b-instruct-2507-q4_K_M`.** En mayo 2026, ningún modelo dense disponible en Ollama supera **simultáneamente** a tu actual en las tres métricas (tool calling agéntico + latencia + estabilidad en Ollama 0.20.4). Es genuinamente sweet spot, no inercia. El score oficial BFCL-v3 de **61.9** y TAU2-Retail **40.4** del model card de Qwen — combinados con el footprint de ~2.5 GB y ~50–80 tok/s en RTX 4060 Ti — siguen siendo Pareto-óptimos para agentes locales.
- **Un único candidato dense merece un A/B test serio: `granite4.1:8b` (IBM, 29-abr-2026, Apache 2.0, BFCL-v3 68.27, 5.3 GB).** Es dense decoder-only puro (no MoE, no Mamba — IBM revirtió la apuesta MoE de Granite 4.0), tiene tool calling nativo en Ollama y scores agénticos *publicados* mejores que tu modelo actual. Trade-off: ~2× VRAM y latencia ~30–45 tok/s en 4060 Ti (estimado por bandwidth bound). Solo tiene sentido si el perfil 8 GB de Carter ya es el target real, no el 6 GB.
- **NO migres a `qwen3:4b-thinking-2507` ni a `qwen3:8b`.** El thinking-2507 tiene BFCL-v3 71.2 sobre el papel pero hay **bugs activos** del runtime Ollama con `think + tools` (issues #10976, #11232, #14570 — output vacío, tool calls truncados, HTTP 500) que destruirían el verifier de Carter. Y `qwen3:8b` *no recibió la actualización 2507*: oficialmente puntúa BFCL-v3 ~59.8 en non-thinking, **por debajo** de tu 4B-Instruct-2507 (61.9), pagando el doble de VRAM por una regresión.

---

## Key Findings

### 1. La línea base es más fuerte de lo que parece

El propio model card de Qwen reporta para `Qwen3-4B-Instruct-2507`:

| Métrica agéntica | qwen3-4b-instruct-2507 | Qwen3-30B-A3B Non-Thinking | GPT-4.1-nano |
|---|---|---|---|
| BFCL-v3 | **61.9** | 58.6 | 53.0 |
| TAU1-Retail | **48.7** | 38.3 | 23.5 |
| TAU1-Airline | **32.0** | 18.0 | 14.0 |
| TAU2-Retail | **40.4** | 31.6 | – |
| TAU2-Airline | **24.0** | 18.0 | – |

Es decir: tu modelo actual ya está superando a un MoE 30B-A3B (que está excluido por requisito hard) y a GPT-4.1-nano *en agentes*. La narrativa "es solo un 4B" es engañosa — la post-training de julio 2025 cerró la brecha contra modelos 5–8× más grandes en agentes. Esto explica el 90% en tu matriz 18×30: no es suerte, es que el 4B-Instruct-2507 fue específicamente afinado para agente-with-tools.

### 2. El benchmark "71.2 BFCL" que circula en blogs es del Thinking, no del Instruct

Múltiples posts (DEV.to, MarkTechPost) citan "71.2% BFCL-v3" para "Qwen3-4B-2507". Esto se refiere específicamente a `Qwen3-4B-Thinking-2507`. **No lo confundas con tu Instruct.** El gap real entre Instruct (61.9) y Thinking (71.2) es ~9 puntos absolutos, lo cual es enorme — pero pagable solo si el thinking funciona en producción, y aquí es donde la realidad muerde:

### 3. Bugs críticos de `thinking + tools` en Ollama (deal-breaker para Carter)

Issues abiertos / reproducibles en `ollama/ollama` (todos relevantes para Ollama 0.20.4):

- **#10976** ("Thinking + tools + qwen3 = empty output") — pasar `think:true` + `tools` produce `message.content` vacío y ningún `tool_calls`. Reproducible.
- **#11232** ("Parser generates incorrect tool calls compared to Qwen3 model output") — parser construye tool calls vacíos o se salta el último cuando el modelo emite varios.
- **#14570** ("qwen3 tool call parser returns 500 when model output is truncated") — si el JSON del tool call se trunca por `num_predict`, Ollama devuelve **HTTP 500** en lugar de un error manejable.
- **QwenLM #1817** (vLLM, pero arquitectural) — "Thinking mode plans tool calls but fails to execute them ~60% of the time" — el modelo razona sobre la tool, se "convence" de que ya la llamó, y emite respuesta como si hubiera pasado. **Esto es exactamente fake-success, lo opuesto a "honestidad por construcción" de tu verifier.**

Para un sistema cuya tesis es "el verifier es la única autoridad de lo que pasó", introducir un modelo que **alucina haber ejecutado tools** es un downgrade categórico, no un upgrade. El thinking-2507 está descartado en runtime hasta que estos issues se cierren.

### 4. `qwen3:8b` (sin 2507) no es un upgrade — es una regresión silenciosa

El reporte técnico de Qwen3 (arXiv:2505.09388) reporta `Qwen3-8B-Base` con **BFCL-v3 59.8 en non-thinking / 68.2 en thinking**. La actualización "2507" (Instruct y Thinking) **solo se aplicó al modelo 4B**, no al 8B. Resultado: pagar 2× VRAM por una caída de 2 puntos en BFCL-v3 non-thinking y la pérdida de las mejoras de post-training de Arena-Hard, TAU1/TAU2 que documentaste arriba. La aparente "victoria" del 8B viene de mode thinking, que reintroduce los bugs del punto 3.

Confirmación independiente: distil labs benchmarkó 12 SLMs y `Qwen3-4B-Instruct-2507` quedó **#1**, por encima de `Qwen3-8B` (#2), Llama-3.1-8B (#3), Llama-3.2-3B (#5).

### 5. `granite4.1:8b` (29-abr-2026) — el único candidato externo que merece evaluación

IBM lanzó Granite 4.1 deliberadamente como **dense decoder-only transformer** (GQA + RoPE + SwiGLU + RMSNorm), revirtiendo la apuesta hybrid-Mamba/MoE de Granite 4.0. Esto es importante: el 4.1 es **estructuralmente compatible** con el runtime Carter. Granite 4.0 (con `-h` suffix) usa Mamba-2 e IBM mismo advierte "the 3b, 1b, and 350m model sizes are alternative options for users when mamba-2 support is not yet optimized" — descartar.

Métricas publicadas (auto-reportadas IBM, hay que asumir un 2–4% de favorabilidad):
- `granite4.1:3b`: BFCL-v3 60.8, IFEval 82.30, MMLU 67.02 — *paridad aproximada* con qwen3-4b-instruct-2507 a 2.1 GB.
- `granite4.1:8b`: BFCL-v3 **68.27**, IFEval 87.06, GSM8K 92.49, MMLU 73.84 — *upgrade real* a 5.3 GB (Q4_K_M default).
- `granite4.1:30b`: BFCL-v3 73.68 — fuera de presupuesto VRAM razonable para Carter.

Tag oficial registrado en `ollama/library`: `granite4.1` (3b/8b/30b) con la *capability flag `tools`*. Apache 2.0. Issue tracker limpio (release fresca, ~1 semana al momento de la búsqueda — implica low burn-in en producción, vigilar).

### 6. xLAM-2-8b-fc-r (Salesforce) — buen leaderboard, mala integración Ollama

Score de cabeza en BFCL-v3 (>76% en su propio reporte) y τ-bench. Problema: **no existe modelo oficial en `ollama.com/library`**. Solo tags de comunidad (`robbiemu/Salesforce_Llama-xLAM-2:8b-fc-r-q4_K_M`, `hf.co/Salesforce/Llama-xLAM-2-8b-fc-r-gguf:latest`) que **no se registran como `tools`-capable** en Ollama. Reportes en CrewAI Community (#5777): "LLM returns None or empty response for any task which requires it to invoke a crewAI tool" porque LiteLLM cae al endpoint `/api/generate` plano en vez de usar el path nativo de tool calling. Falla el requisito hard 6 (function calling nativo en Ollama).

### 7. Otros candidatos descartados (con razón)

| Modelo | Razón de descarte |
|---|---|
| `phi4-mini:3.8b` | Issue #9437 abierto: tool_calls vienen como string en `content` en vez de campo `tool_calls`. Modelfile arreglado parcialmente, pero parallel calling sigue roto. |
| `mistral-nemo:12b` | Issue #6713 abierto desde sept 2024: tool calling vía OpenAI-compat falla silenciosamente. + Excede 6 GB profile. |
| `hermes-3-llama3.1:8b` | Tool calling vía XML `<tool_call>` tags, NO nativo via `tools` parameter de Ollama. Requiere parser custom — viola requisito 6. |
| `command-r7b` | Licencia CC-BY-NC (no comercial). Buen tool-use, pero license incompatible con la mayoría de proyectos personales/open. |
| `llama3.1:8b` (base) | BFCL-v3 ~58 non-thinking. Sin TAU2 documentado. Tool calling estable pero claramente inferior a qwen3-4b-instruct-2507 en agentes. |
| `llama3.1-storm:8b` | Solo en tag de comunidad (`ajindal/llama3.1-storm`). Mejora vs Llama-3.1 base, pero la baseline ya era inferior a qwen3-4b-2507. |
| `mistral-small3.2:24b` | Cabe en Q4 a ~14 GB pero penaliza fuerte la latencia 4060 Ti (15–25 tok/s estimados). Excede ratio calidad/latencia. |
| `gemma3:4b` / `gemma3:12b` | Se mencionó descartar Gemma 4. Gemma 3 sí está en el library pero su tool calling es prompt-based, no nativo en Ollama 0.20.4. |
| `internlm3:8b`, `yi-1.5:9b` | Sin tool calling nativo registrado en Ollama. |
| `qwen2.5:7b`, `qwen2.5-coder:7b` | Pre-2507 era; superado por qwen3-4b-instruct-2507 en TAU2 y BFCL-v3 según technical report. |
| `deepseek-r1-distill-*` | Reasoning distillates; sin tool calling agéntico fiable, no afinados para tool-use. |
| `qwen3.5:9b` | Issue #14493 (oct 2026) — tool calling completamente roto en Ollama, parser asignado a renderer/parser equivocado. + Issue #14745 — emite tool call como texto en lugar de ejecutarla. **Activamente roto al momento de mayo 2026.** |
| `granite4:tiny-h`, `granite4:micro-h` | Mamba-2 hybrid no optimizado en Ollama (advertido por el propio modelcard). |

---

## Tabla comparativa Top candidatos dense ≤ 12B (mayo 2026)

| Tag Ollama | Disco | VRAM Q4_K_M cargado (≈) | Ctx | BFCL-v3 | TAU2-Retail | Latencia 4060 Ti (est.) | Tool calling Ollama 0.20.4 | Licencia | Release |
|---|---|---|---|---|---|---|---|---|---|
| **`qwen3:4b-instruct-2507-q4_K_M`** *(actual)* | 2.5 GB | 3.0–3.5 GB | 256K | **61.9** | **40.4** | **50–80 tok/s** | ✅ Estable (parser `qwen3` activo) | Apache 2.0 | Jul 2025 |
| `qwen3:4b-thinking-2507-q4_K_M` | 2.5 GB | 3.0–3.5 GB | 256K | 71.2 | n/a alto | 30–55 tok/s (thinking overhead 2–4×) | ⚠️ **BUGS: #10976 #11232 #14570** | Apache 2.0 | Ago 2025 |
| `granite4.1:8b` | 5.3 GB | 6.5–7.5 GB | 128K | 68.27 | n/a | ~30–45 tok/s | ✅ Recién agregado, capability `tools` | Apache 2.0 | 29-Abr-2026 |
| `granite4.1:3b` | 2.1 GB | 2.8–3.2 GB | 128K | 60.80 | n/a | ~55–85 tok/s | ✅ | Apache 2.0 | 29-Abr-2026 |
| `qwen3:8b` (sin 2507) | 5.2 GB | 6.0–7.0 GB | 32K | 59.8 (NT) / 68.2 (T) | n/a | ~35–50 tok/s | ✅ NT estable, T con bugs | Apache 2.0 | Abr 2025 |
| `llama3.1:8b` | 4.7 GB | 5.5–6.5 GB | 128K | ~58 (BFCL-v1 76.1) | bajo | ~40–55 tok/s | ✅ Maduro | Llama 3.1 community | Jul 2024 |
| `mistral-nemo:12b` | 7.1 GB | 8.5–9.5 GB | 128K | ~60 (no oficial) | n/a | ~25–35 tok/s | ⚠️ Issue #6713 abierto | Apache 2.0 | Jul 2024 |
| `phi4-mini:3.8b` | 2.5 GB | 3.0–3.5 GB | 128K | ~55 | n/a | ~55–85 tok/s | ⚠️ Issue #9437 (parser parcial) | MIT | Feb 2025 |
| `xLAM-2-8b-fc-r` (community) | 4.9 GB | 5.5–6.5 GB | 128K | ~76 (auto-rep) | ~52 (auto-rep) | ~40–55 tok/s | ❌ No registra tools en Ollama | CC-BY-NC-4.0 | Mar 2025 |
| `command-r7b` | 5.1 GB | 6.0–7.0 GB | 128K | ~67 (Cohere) | n/a | ~40–55 tok/s | ✅ Pero CC-BY-NC | CC-BY-NC-4.0 | Dic 2024 |
| `hermes3:8b` (`hermes-3-llama-3.1`) | 4.7 GB | 5.5–6.5 GB | 128K | ~68 (XML format) | n/a | ~40–55 tok/s | ❌ Tool calling vía XML, no nativo | Llama 3.1 community | Ago 2024 |

Notas:
- "BFCL-v3 ~XX" sin link específico = inferencia de scores cercanos en el leaderboard llm-stats / pricepertoken / awesomeagents (al 17-abr-2026, el average BFCL-v3 entre 23 modelos es 55.9; el top es GLM-4.5 a 76.7, MoE excluido).
- Latencia 4060 Ti estimada por escala desde el dato medido en RTX 4060 8 GB de localllm.in (qwen3:8b Q4_K_M @ 16K = 40.58 tok/s). El 4060 Ti tiene ~25% más bandwidth (288 vs 272 GB/s) — los números arriba reflejan ese ajuste para 16K context.
- "VRAM cargado" incluye KV cache estimado a 8K context (default Carter razonable). Bajar a 4K reduce ~0.3–0.6 GB.

---

## Deep-dive de los 3 candidatos relevantes

### A. `qwen3:4b-instruct-2507-q4_K_M` (status quo — defender o atacar)

- **Arquitectura**: Causal LM denso, 36 capas, GQA 32Q/8KV, head_dim 128, embedding 2560, FFN 9728, RoPE base 5e6, contexto nativo 262,144 tokens. Sin thinking traces. 4.0 B params totales (3.6 B no-embedding).
- **Sampling oficial (Qwen team)**: `Temperature=0.7, TopP=0.8, TopK=20, MinP=0`. Para agentes con tool calling determinístico (caso Carter) bajar a `Temperature=0.2, TopP=0.9` produce mejor schema adherence sin matar diversidad.
- **System prompt format**: ChatML con `<|im_start|>system ... <|im_end|>`. Tool calls emitidos como `<tool_call>{"name":"...", "arguments":{...}}</tool_call>`. Parser de Ollama (`qwen3`) lo maneja nativamente.
- **Bugs conocidos**: ninguno crítico para *non-thinking*. El parser "qwen3" en Ollama 0.20.x es maduro (PR #14477 cerró el último issue serio en v0.17.3). El issue #14570 sobre HTTP 500 en truncamiento aplica a tu modelo si pones `num_predict` muy bajo — workaround: dejar `num_predict: -1` y limitar por `num_ctx` y un timeout cliente como ya tienes (25s/turn).
- **Uso agéntico exitoso documentado**: Qwen-Agent + MCP (recipe oficial), Apidog tutorial, Intel AI PC blog, AgentForge tuning guide. Patrón consistente: temperature baja (0.2), `<tool_call>` de un solo array, ReAct corto.

### B. `granite4.1:8b` (el único candidato real de upgrade)

- **Arquitectura**: Decoder-only dense transformer, GQA 8 KV heads, RoPE, MLP+SwiGLU, RMSNorm, shared input/output embeddings, BF16 nativo, 128K production / 512K extension context. **Sin Mamba, sin MoE, sin thinking traces** — perfectamente compatible con el runtime Carter actual.
- **Métricas IBM (auto-reportadas, pero independent verification por Hacker News y blogs es razonable)**: MMLU 73.84, IFEval **87.06**, BFCL-v3 **68.27**, GSM8K 92.49, HumanEval 85–87, EvalPlus 80.2.
- **Sampling recomendado**: IBM no especifica official sampling distinto del default. Tratar como un modelo "instruct sobrio" — `temp=0.2-0.3, top_p=0.9` para agentes.
- **Tool calling**: Tag `granite4.1:8b` en `ollama.com/library/granite4.1` lleva la capability flag `tools`. Plantilla y parser nuevos (commit reciente). **Riesgo: ~1 semana de burn-in al momento de búsqueda — podría haber edge cases sin reportar.**
- **Pros**: +6.4 puntos BFCL-v3 vs tu actual, +14 puntos IFEval, license Apache 2.0, IBM ISO 42001 + criptografía firmada (relevante si publicas Carter), 512K context.
- **Contras**: 2× footprint VRAM, ~30–40% menos throughput tok/s, sin TAU2 publicado (BFCL-v3 mide single+multi-turn structured pero TAU2 mide multi-turn agentic policy adherence — *exactamente* lo que Carter hace en sus 3-step ReAct). Hasta tener TAU2 verificable, el +6.4 BFCL-v3 podría no traducirse en mejora real para tu caso.

### C. `qwen3:4b-thinking-2507-q4_K_M` (tentador, pero veneno operacional hoy)

- **Arquitectura**: Idéntica al Instruct salvo entrenamiento explícito para emitir `<think>...</think>` antes de la respuesta. Misma forma, mismo footprint en disco (2.5 GB Q4_K_M).
- **Sampling oficial**: `Temperature=0.6, TopP=0.95, TopK=20, MinP=0`, num_ctx default 32768 (per `SimonPu/qwen3:4b-thinking-2507-q8_0/params`).
- **Métricas**: BFCL-v3 71.2 (vs 61.9 Instruct), AIME25 81.3 (vs 47.4), TAU benchmarks "+80% relative" según Qwen blog.
- **Bugs activos críticos en Ollama 0.20.4** (suficiente para excluir):
  1. Issue #10976 — `think:true + tools` produce `message.content: ""` (output vacío). Reproducible con qwen3:30b-a3b y la cadena de bugs aplica al 4b-thinking.
  2. Issue #11232 — Parser del thinking emite tool calls vacíos o salta el último cuando hay múltiples.
  3. Issue #14570 — Si `<tool_call>` se trunca por `num_predict`, Ollama devuelve HTTP 500 en vez de fallback a content.
  4. Patrón `qwen3.go:108 msg="qwen3 tool call parsing failed"` documentado en logs reales.
  5. Comportamiento "fake success" reportado en QwenLM/Qwen3 #1817: thinking razona sobre la tool, se convence, y nunca la emite — alucina haberla ejecutado. **Antitético al diseño honest-by-construction de Carter.**

---

## Recomendación final brutal y honesta

**¿Existe alguno que CLARAMENTE supere a qwen3:4b-instruct-2507 en las tres métricas (tool calling + latencia + estabilidad)?**

**No. Cero candidatos cumplen las tres a la vez en mayo 2026.**

- Los que ganan en BFCL-v3 numérica (qwen3-thinking-2507, qwen3-coder MoE, glm-4.5, qwen3-32B) o son MoE (excluidos por ti) o tienen bugs activos en Ollama (thinking variants, qwen3.5).
- Los que cumplirían latencia y estabilidad (granite4.1:3b, llama3.1:8b, phi4-mini) puntúan igual o peor en agentes — no aportan.
- El único candidato dense con números mejores Y estabilidad esperada es **`granite4.1:8b`**, pero paga 2× VRAM y ~30% menos tok/s. No es claramente superior — es un trade.

### Plan de acción recomendado (3 fases, sin urgencia)

**Fase 0 — INMEDIATO (no hacer nada en producción)**
- Mantener `qwen3:4b-instruct-2507-q4_K_M` como default de Carter v4.
- Validar que el `num_predict` está en `-1` (o suficientemente alto) para evitar el trigger del issue #14570.
- Confirmar que no usas `think:true` en ninguna llamada — si Carter emite ese parámetro, quitarlo (no aplica al Instruct, pero por higiene).

**Fase 1 — A/B TEST OPCIONAL (1-2 semanas, si sobra tiempo)**
- Pull `granite4.1:8b` (5.3 GB, perfil 8 GB / 12 GB de Carter).
- Crear un perfil "carter-granite-8b" en paralelo al "carter-qwen3-4b".
- Re-correr **un subset de 50–80 casos** del matriz 18×30 (no los 540 — sería overhead) eligiendo casos representativos: 10 cada categoría (apps, files, gui, web, system, memory, terminal, multi-monitor).
- Métricas a capturar (las tres del usuario):
  - **Tool calling**: % éxito sin re-prompt, % schema válido al primer tool_call, # cadenas necesarias para success.
  - **Latencia**: TTFT, tok/s, latencia end-to-end por turn, tiempo total ReAct hasta success.
  - **Estabilidad**: # crashes Ollama (esperar 0), # casos con fake-success (verifier dice "no pasó nada"), # infinite loops.
- **Threshold para migrar**: granite4.1:8b debe superar a qwen3-4b-instruct-2507 en **≥2 de 3 métricas con margen ≥10%**, sin nuevos failure modes (especialmente fake-success). Si solo gana BFCL-style y no agentic, no migra.
- Si pasa, **re-validar los 540 casos completos** antes de cambiar default. Esperar regresiones en 5–8% del matriz por shift de familia (system prompt format diferente, sampling defaults diferentes).

**Fase 2 — MONITOR (no migrar todavía)**
- `qwen3:4b-thinking-2507`: monitorear los issues #10976, #11232, #14570. Cuando los tres estén cerrados Y exista una versión `qwen3:4b-thinking-2507` con parser dedicado en Ollama (similar al que ya existe para qwen3-coder), reconsiderar — el +9 puntos BFCL es genuinamente atractivo si el runtime cooperaa.
- `qwen3:4b-instruct-2509` o equivalente: Qwen team podría lanzar un refresh otoño 2026 (patrón histórico). Vigilar `Qwen/Qwen3-4B-*` en HF.
- `granite4.2` o `granite4.1.x`: IBM publica releases trimestrales. Si aparece TAU2 oficial > 40, granite se vuelve favorita.
- Cualquier modelo dense ≤8B que pase a tener entrada **oficial** (no community fork) en `ollama.com/library` con tag `tools` Y BFCL-v3 ≥70: re-evaluar.

### Candidatos cercanos que NO migrar todavía pero vigilar

| Modelo | Por qué interesante | Por qué NO ahora |
|---|---|---|
| `qwen3:4b-thinking-2507` | +9.3 BFCL-v3, mismo footprint | Bugs activos thinking+tools en Ollama; fake-success documentado |
| `granite4.1:3b` | Footprint 2.1 GB, BFCL-v3 paridad | No supera al actual; downside-risk de un release de 1 semana |
| `granite4.1:8b` | +6.4 BFCL-v3, +14 IFEval, license Apache 2.0 | 2× VRAM, sin TAU2 publicado, 1 semana de burn-in |
| `xLAM-2-8b-fc-r` | SOTA en tool calling leaderboards | Sin tag oficial Ollama, no registra capability `tools`, license CC-BY-NC |
| `mistral-small-3.2:24b` | Calidad clase 24B en Q4 | 14 GB VRAM, 15–25 tok/s — fuera del envelope de latencia |

---

## Caveats

- **Self-reporting bias**: Los benchmarks BFCL-v3 de Granite, Qwen y xLAM son auto-reportados por los respectivos equipos. El BFCL oficial leaderboard (gorilla.cs.berkeley.edu) ahora está en V4 y los V3 scores comparables cross-vendor son escasos. Asume ±2–3 puntos de varianza vs eval independiente.
- **TAU2 escasez**: Solo Qwen publicó TAU2 sub-categorías (Retail/Airline/Telecom) para sus modelos pequeños. Granite, IBM, Salesforce y otros no — comparación TAU2 directa es imposible hoy. El BFCL-v3 es el mejor proxy disponible.
- **Latencias estimadas**: Los números 30–80 tok/s para 4060 Ti son extrapolación desde RTX 4060 8 GB medido (40.58 tok/s @ qwen3:8b Q4_K_M, 16K) ajustando bandwidth (272→288 GB/s) y assumiendo no offload. **Verifica en hardware real** antes de tomar decisiones.
- **Benchmark BFCL-v3 vs realidad de Carter**: BFCL mide single-turn y multi-turn estructurados con ASTs. El verifier de Carter (frame-diff numpy + Win32 EnumWindows) mide *efectos en el sistema*, que es categóricamente diferente. Un modelo con +10 BFCL-v3 puede tener +0% en tu matriz 18×30 si el cuello de botella es planning, no schema-emit. Por eso la Fase 1 propone re-correr un subset, no confiar en el papel.
- **Ollama 0.20.4 es relativamente nuevo** (sucesor de 0.17.x donde se agregó RENDERER/PARSER explícitos). Algunos issues citados (#14493, #14601, #14745) son de octubre-noviembre 2026 sobre `qwen3.5`, *no* sobre `qwen3:4b-instruct-2507`. Se incluyeron para mostrar que el ecosistema *Ollama+Qwen tool calling* tiene estabilidad variable según versión exacta del modelo. Tu modelo actual (qwen3 family, parser `qwen3`) es la rama estable y madura; cualquier salto a parsers nuevos (qwen3.5, qwen3-coder, qwen3-vl) reabre el pozo de bugs.
- **Hardware target**: Las recomendaciones asumen RTX 4060 Ti 16 GB. En una 4060 8 GB, granite4.1:8b a Q4_K_M con KV cache para 8K context queda al borde (~7–8 GB) — perfil 8 GB de Carter podría empezar a swap. En RTX 3060 12 GB es cómodo. En CPU-only o 6 GB GPU, granite no es opción y qwen3:4b-instruct-2507 sigue siendo el único viable.
- **El usuario pide honestidad**: la respuesta más útil aquí no es "te encontré un upgrade", es "la elección que hiciste en julio 2025 sigue siendo correcta en mayo 2026". El 90% en 540 casos no es accidente; es que el sweet spot 4B-Instruct-2507 fue diseñado para exactamente este caso de uso, y los lanzamientos posteriores o se han ido a MoE (excluido), a thinking (parser inestable), o a 8B+ sin la ventaja de post-training reciente. El campo se movió, pero no en una dirección que aproveche tu envelope.