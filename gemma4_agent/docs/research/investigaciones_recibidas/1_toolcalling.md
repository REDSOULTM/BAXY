# Tool-calling fiable y structured output en Gemma 4 E4B-it (Q4_K_M) sobre llama.cpp sin reasoning

## TL;DR
- **Sí es viable desacoplar tool-calling de thinking** en este stack, pero la palanca dominante NO es la gramática (llama.cpp `--jinja` ya la activa por debajo en modo **lazy**, lo que NO cura el 2/6), sino dos cambios baratos: **(a) bajar drásticamente el sampling** en modo "acción" (`temperature=0.0` greedy o `temp≈0.2, top_k=1–5, top_p=1.0`) y **(b) sesgar el inicio de la respuesta** hacia el token `<|tool_call|>` (prefill / few-shot canónicos de Gemma 4). Esto ataca directamente la causa del 2/6 (alta entropía en los primeros tokens hace al modelo "narrar" en vez de disparar el trigger).
- **GBNF custom es subóptimo aquí**: con `--jinja` y herramientas en la request, llama.cpp ya genera y aplica una gramática lazy (`peg-gemma4`) que se activa cuando aparece `<|tool_call|>`; un GBNF propio entra en conflicto con la pipeline del autoparser y la única forma realmente fuerte de "forzar formato desde token 0" sin reasoning es `tool_choice="required"` (que el usuario ya descarta como retry) o `response_format: json_schema` (que vuelve la gramática NON-lazy pero rompe el flujo conversacional / fallback). La gramática garantiza **sintaxis**, no **decisión correcta** de tool/args — TOOLDEC (Zhang et al., 2023, arXiv 2310.07075) lo enmarca como reducción de errores **sintácticos** a cero, no semánticos.
- **Few-shot 2–3 ejemplos en el formato nativo `<|tool_call|>call:name{...}<|/tool_call|>` + prefill agresivo + sampling determinista**: combinación de mayor ROI inmediato, baja complejidad, latencia neutra (cacheable). **QLoRA** sólo si tras las dos palancas anteriores aún quedas por debajo del objetivo; el upside del fine-tune para Gemma 4 E4B es real pero menor en términos absolutos que el "58→85%" reportado para FunctionGemma‑270M (que parte de un baseline mucho más bajo).

---

## Diagnóstico transversal (causa raíz del 2/6 → 6/6 con thinking)

El thinking no añade información: **re-organiza la distribución de probabilidad sobre los primeros tokens del turno del asistente**. Después de un bloque `<|channel|>thought ... </channel|>`, la cabeza de salida queda "calibrada" en un régimen de baja entropía donde el siguiente token con mayor probabilidad es directamente el trigger especial `<|tool_call|>`. Sin thinking, partiendo de `<start_of_turn>model\n` con sampling `temp=1.0, top_p=0.95, top_k=64` (defaults Gemma), la entropía en el primer token es alta y compite con tokens de prosa ("Voy", "Sure", "Let", "Abriendo"…). Una vez emitido un token de prosa, el modelo se compromete a una secuencia narrativa por la causa autoregresiva: este es exactamente el fenómeno de "first-token misalignment" descrito en Cappelletti, Poppi et al. (Univ. of Modena & Reggio Emilia), *"Improving LLM First-Token Predictions in Multiple-Choice Question Answering via Output Prefilling"*, arXiv 2505.15323 (mayo 2025). El paper aborda MCQA con prefijos "The correct option is:", pero el mecanismo (un prefijo benigno corto reduce el first-token misalignment) es directamente aplicable como interpretación al caso tool-calling. Refuerza esto la línea Qi et al. *"Safety alignment should be made more than just a few tokens deep"* (2024) — **los primeros tokens deciden el modo**.

Esto da tres puntos de ataque, en orden de coste-beneficio:

1. **Reducir entropía en el primer token** (sampling agresivo en modo acción).
2. **Sesgar el primer token al trigger** (prefill `<|tool_call|>`, few-shot que termina siempre en ese token).
3. **Eliminar la opción de prosa** (constrained decoding **non-lazy**: solo viable con `tool_choice="required"` o `response_format`, ambos con trade-offs).

Thinking funciona porque hace **(1) + (2)** implícitamente a costa de 268 tokens. Replicarlo explícitamente cuesta ~0–8 tokens (prefill + sampling). **Esto es el resultado clave.**

---

## 1. GBNF / Grammar-constrained decoding en llama.cpp con `--jinja` (PRIORIDAD ALTA)

### 1.1 Diagnóstico

`--jinja` en builds recientes (rama `b8000+`, que incluye PR #18675 "autoparser" y para Gemma 4 PR #21418 "common: add gemma 4 specialized parser" mergeado el 4-abr-2026 por aldehir) **ya genera y aplica una gramática automáticamente cuando hay `tools` en la request**, sin necesidad de pasar `--grammar` o `--grammar-file`. El comportamiento exacto depende de `tool_choice`:

| Caso                                                                  | `grammar_lazy` | Cuándo aplica el masking de tokens                                                                     |
|-----------------------------------------------------------------------|----------------|--------------------------------------------------------------------------------------------------------|
| `tool_choice="auto"` (default) + `tools=[...]`                        | **true**       | Solo después de que el modelo emite el trigger `<|tool_call|>`. Antes, generación libre (incl. prosa). |
| `tool_choice="required"` + `tools=[...]`                              | **false**      | Desde token 0 del turno del asistente — fuerza el formato `<|tool_call|>call:name{...}<|/tool_call|>`. |
| `response_format={type: json_schema, json_schema: {...}}` (sin tools) | **false**      | Desde token 0 — fuerza JSON conforme al schema.                                                       |
| `response_format=json_schema` **+** `tools` + thinking activo         | **bug**        | La gramática se desactiva silenciosamente (issue #20345, abierto Mar 2026, build d088d5b).            |

Código primario (`common/chat-auto-parser-generator.cpp`, visible en discussion #20459 del repo `ggml-org/llama.cpp`):

```cpp
bool has_response_format = !inputs_resolved.json_schema.empty()
                           && inputs_resolved.json_schema.is_object();
bool include_grammar = has_response_format ||
    (has_tools && ((tool_choice == COMMON_CHAT_TOOL_CHOICE_AUTO && !trigger_marker.empty())
                   || tool_choice == COMMON_CHAT_TOOL_CHOICE_REQUIRED));
if (include_grammar) {
    data.grammar_lazy = !has_response_format
                        && tool_choice == COMMON_CHAT_TOOL_CHOICE_AUTO;
    ...
}
```

Para Gemma 4 el formato detectado se loguea como `Chat format: peg-gemma4` y el trigger es la cadena literal `<|tool_call|>` (per_call_start), terminador `<|/tool_call|>` (per_call_end). El template lo trata como token especial preservado (`common/chat-diff-analyzer.cpp`, `preserved_tokens.push_back("<|tool_call|>")`).

### 1.2 Implicación para el 2/6 sin thinking

**Esta es la clave que invalida la solución "más obvia"**: en modo `tool_choice="auto"` la gramática lazy NO ayuda al problema del usuario, porque cuando el modelo decide narrar ("Voy a abrir el navegador") **nunca emite el trigger** y por tanto la gramática nunca se activa. La gramática garantiza que SI emite el trigger, lo que sigue será sintácticamente válido contra el wrapper; no garantiza que lo emita.

Esto coincide con el resultado canónico de constrained decoding: Zhang et al. *TOOLDEC* (arXiv 2310.07075) reporta que la FSM "always generates **syntactically correct** tool calls" pero la corrección semántica (tool correcto, valores correctos) no está garantizada. Para forzar la decisión, hay dos rutas:

- **`tool_choice="required"`** — el usuario ya lo usa como forced-retry; usarlo siempre tiene dos costes: (i) elimina la posibilidad legítima de respuesta conversacional (el router de 4-6 tools tendría que incluir un `noop` o `respond_in_natural_language` como tool para no romper el flujo); (ii) puede degradar la calidad cuando el comando es ambiguo (el modelo no puede "pensar en voz alta" ni pedir clarificación).
- **`response_format: json_schema`** — sólo aplica bien sin `tools` o cuando codificas la decisión completa (tool name + args) como un objeto JSON. Útil si reescribes el protocolo: el modelo emite `{"tool":"open_browser","args":{...}}` puro y tú lo enrutas. Riesgo: pierdes el parser nativo de Gemma 4 (que tiene fixes específicos para el delimitador `<|"|>`, ver issue #21316).

Importante: **PR #21418 (aldehir, 4-abr-2026) advierte explícitamente** que para Gemma 4 "JSON schema support for tool calling is not included in this PR. The grammar constrains the model to generate proper tool calls, but the schema is not strictly enforced for tool call arguments. It is enforced for `response_format`." (discussion #21839 lo confirma: *"Most models use GBNF grammar to ensure proper tool calls. Gemma 4 only forces the structure, not the arguments"*). Si necesitas validación estricta de argumentos vía gramática, tienes que ir por `response_format` (no por `tools`), o validar JSON-schema post-hoc en tu cliente.

### 1.3 ¿GBNF custom puede sobreescribir lo que `--jinja` genera?

Comportamiento documentado en discussions #12204 y #20459 e issue #11847:
- `/v1/chat/completions` con `--jinja`: si pasas `grammar` raw + `response_format`, el server devuelve HTTP 400 con `"Either json_schema or grammar can be specified, but not both"` (issue #11847).
- Si pasas `grammar` raw + `tools` (sin response_format), la rama del autoparser que setea `data.grammar` aún corre cuando `include_grammar` es true. El precedente exacto entre user-grammar y tool-grammar **no está documentado**; los tests del repo no cubren ese caso. **Recomendación operativa: no mezclar**.
- `/completion` (endpoint legacy, no OAI-compat): acepta `grammar` y `grammar_lazy` + `grammar_triggers` directamente, pero **NO procesa el template Jinja ni los tools**, así que pierdes el chat-template de Gemma 4 (y el `<|tool_call|>` no lo emite el modelo solo si tú no lo pones en el prompt). Para tu caso de chat con tools, usa siempre `/v1/chat/completions`.

### 1.4 Overhead de la gramática en latencia

Los grammar samplers de llama.cpp (FSM-based) tienen overhead **bajo y constante por token** una vez compilados. Dong et al., *"XGrammar: Flexible and Efficient Structured Generation Engine for Large Language Models"* (arXiv 2411.15100 / MLSys 7, Nov 2024) benchmarkea sobre Llama-3.1-8B-Instruct en AMD Ryzen 9 7950X + RTX 4090: XGrammar alcanza **<40 µs/token para JSON Schema y CFG**, con un speedup reportado de **hasta 100×** sobre el grammar engine de llama.cpp (build b3998). La implementación nativa de llama.cpp en build b9090 es más lenta que XGrammar pero igualmente sub-milisegundo por token, despreciable frente al cost de forward del modelo. **Compilación inicial**: con un schema de ~5 tools la compilación es del orden de ms en Q4_K_M sobre CPU típica; **se amortiza por sesión** porque el server cachea por sesión/slot.

| Aspecto                                          | Impacto en TTFT | Impacto en latencia total                                                          |
|--------------------------------------------------|-----------------|------------------------------------------------------------------------------------|
| Gramática lazy (`tool_choice=auto`)              | ~0 ms           | Despreciable hasta que aparece el trigger; luego sub-ms por token de masking      |
| Gramática non-lazy (`tool_choice=required`)      | +5–20 ms (compilación si schema nuevo) | sub-ms por token aplicado desde token 0                                            |
| `response_format=json_schema` con schemas grandes | +20–80 ms       | Igual que non-lazy una vez compilado                                              |

**El argumento "gramática frena el TTFT" es marginal**. El verdadero ahorro de latencia viene de **no generar 268 tokens de thinking**, no de la elección lazy/non-lazy.

### 1.5 Veredicto

**VIABLE pero con caveats** para forzar formato (sintaxis JSON, nombre de tool del set permitido). **NO RESUELVE** el 2/6 en modo lazy/`auto`. Para resolverlo realmente vía gramática hay que cambiar a non-lazy (`required`) — que es justo lo que el usuario ya hace como retry — o reescribir el protocolo con `response_format` puro. Para este stack, **gramática NO es la palanca principal**; lo es el sampling + prefill (sección 2).

### 1.6 Flags y código concretos (llama.cpp build ~b9090)

```bash
# Configuración del servidor para Gemma 4 E4B-it con tool-calling nativo
llama-server \
  -m gemma-4-E4B-it-Q4_K_M.gguf \
  --jinja \                                  # activa minja + autoparser PEG (peg-gemma4)
  --reasoning-format auto \                  # extrae <|channel|>thought a reasoning_content
  --temp 0.0 \                               # GREEDY como default del servidor (override por request)
  --top-k 1 \
  --top-p 1.0 \
  --min-p 0.0 \
  -c 8192 \
  -ngl 99 \
  -fa \
  --port 8080
```

```bash
# Verificar el formato detectado y el template:
curl -s http://localhost:8080/props | jq '.chat_format, .chat_template_source'
# Esperado: "peg-gemma4" o "Content-only" si el template GGUF no incluye tool tokens.
# Si sale "Content-only" debes pasar --chat-template-file con el template oficial de Gemma 4.
```

Para sampling distinto por modo (acción vs. conversación), **override por request**, no por server flag:

```json
// Modo ACCIÓN: comando "crisp", router selecciona 4-6 tools
{
  "messages": [...],
  "tools": [...],
  "tool_choice": "auto",
  "temperature": 0.0,
  "top_k": 1,
  "top_p": 1.0,
  "min_p": 0.0,
  "repeat_penalty": 1.0
}

// Modo CONVERSACIÓN: aclaraciones, respuestas naturales
{
  "messages": [...],
  "temperature": 1.0,
  "top_k": 64,
  "top_p": 0.95,
  "min_p": 0.01
}
```

**HIPOTÉTICO (MEDIR)**: si necesitas estructura forzada sin perder la opción "no llamar tool", añade un tool sintético `respond_in_natural_language(text: str)` al router y usa `tool_choice="required"` siempre. Esto convierte cada turno en "qué tool elegir" (incluyendo "responder en lenguaje natural") y elimina por completo la rama de prosa. **Mide TTFT y latencia E2E; espero que sea ~igual o mejor que el caso `auto` actual** porque elimina el retry de forced-retry para el 33% de turnos que hoy fallan.

---

## 2. Sampling óptimo para tool-calling en SLMs <10B (PRIORIDAD ALTA)

### 2.1 Diagnóstico

Los defaults conversacionales de Gemma (`temp=1.0, top_k=64, top_p=0.95, min_p=0.0`) provienen de la recomendación oficial del equipo Gemma para "respuestas creativas y variadas" — están optimizados para escritura libre, no para decisiones discretas como "elegir 1 de 6 tools y rellenar 2 argumentos". El paper de min-p (Nguyen, Baker, Neo et al., *"Turning Up the Heat: Min-p Sampling for Creative and Coherent LLM Outputs"*, arXiv 2407.01082) muestra que **a temperaturas altas, top-p ancho conserva tokens de baja probabilidad** que en una decisión categórica (elegir el siguiente token entre `<|tool_call|>`, `Voy`, `Abriendo`, `Claro`, ...) son justamente el ruido que destruye la fiabilidad.

Para tareas estructuradas / no-creativas la convergencia en la literatura es clara: **greedy (temp=0)** o **temp=0.0–0.3 con top_k bajo** maximizan accuracy. La línea relevante:

- TOOLDEC paper (Zhang et al., 2023, arXiv 2310.07075): usa greedy + constrained decoding y observa que un Mistral-Instruct sube de 0% a 52% en ToolEval. El greedy aquí es supuesto, no la palanca, pero confirma el régimen.
- BFCL prompting: el changelog del repo Berkeley (Sep 2025) discute específicamente que las evaluaciones FC usan temp baja por defecto.
- llama.cpp PR #9639 (ochafik, el PR original de tool-call con lazy grammars): los commits `542853b3`, `259d9e45`, `c6a22edc` se llaman literalmente `tool-call: greedy sampling in server tests` y `Greedy sampling in tool call tests` — **el equipo de llama.cpp testea tool-calling en greedy** (aunque no es una recomendación oficial para producción; los defaults en `tools/server/README.md` siguen siendo `temp=0.8`).

### 2.2 Trade-off conversacional

Sí, greedy degrada la naturalidad del lenguaje **si lo usas para todo el turno**. Solución: **sampling dual**.

- **Modo acción** (prompt indica que hay tools + comando crisp del usuario): `temp=0.0`, `top_k=1`. Greedy puro.
- **Modo conversación / respuesta tras tool_result**: `temp=0.7–1.0, top_p=0.95, top_k=64, min_p=0.01`.

En llama.cpp lo controlas por request (sección 1.6). Para sistemas multimodo con voz, lo razonable es que el orquestador decida el modo por el contexto del turno (¿última cosa que dijo el modelo fue `<|tool_response|>...`? → modo conversación para sintetizar; ¿el usuario acaba de pedir algo? → modo acción).

### 2.3 Valores concretos a probar (en este orden)

| Preset                          | temp | top_k | top_p | min_p | Tasa esperada vs. defaults | Riesgo                                                                 |
|---------------------------------|------|-------|-------|-------|----------------------------|------------------------------------------------------------------------|
| **A. Greedy puro**              | 0.0  | 1     | 1.0   | 0.0   | **+3–4/6** (objetivo 5–6/6 sin thinking) | Argumentos pueden quedar "estancados" si el modelo loopea; mitigar con `repeat_penalty=1.0` (NO subir) y EOG correcto |
| **B. Casi-greedy estable**      | 0.2  | 5     | 1.0   | 0.0   | +3/6                       | Mejor que A si A causa loops; ligeramente más entrópico                |
| **C. Min-p estricto**           | 0.7  | 0     | 1.0   | 0.1   | +2–3/6                     | Compromiso: mantiene algo de naturalidad incluso si emite prosa antes del trigger |
| **D. Defaults Gemma (baseline)**| 1.0  | 64    | 0.95  | 0.0   | 2/6 (medido por el usuario)| —                                                                      |

**Recomendación de partida: Preset A**, fallback Preset B si observas degradación específica en argumentos (p. ej. el modelo siempre escribe `"path": "/home/user"` aunque el comando diga otra cosa — esto es típico de greedy + low-data en argumentos). El parámetro `seed` fíjalo para reproducibilidad en el smoke test (`"seed": 42`).

**No subir `repeat_penalty`** por encima de 1.0 en Gemma 4: hay bugs reportados (issues #21338, ollama/ollama#15502) donde causan tokens espurios `<unused49>` y rotura del parser tag-based. Mantener en 1.0 (default llama.cpp).

### 2.4 Recomendación oficial Google/Gemma sobre tool-calling

**No existe** una recomendación oficial separada de Google para function-calling con Gemma 4 distinta de los defaults conversacionales. Unsloth (*"Gemma 3 / Gemma 3n How to Run"*, docs.unsloth.ai) cita la recomendación oficial del equipo Gemma: *"According to the Gemma team, the optimal config for inference is temperature = 1.0, top_k = 64, top_p = 0.95, min_p = 0.0"*. La doc de ai.google.dev describe el lifecycle y los 6 tokens especiales pero no toca sampling. **Esto significa que tienes libertad: los defaults NO son una recomendación específica de tool-calling, son una recomendación general de inferencia**. Bajar a greedy para modo acción no viola ninguna guideline de Google.

### 2.5 Veredicto

**VIABLE, alto impacto, riesgo bajo.** Cambio de una línea por request. Es la palanca #1.

### 2.6 Smoke test sugerido (medir el usuario)

Sobre los mismos 6 comandos crisp + 6 ambiguos:

| Configuración                                       | Tasa tool-call (esperado) | TTFT p50 / p90 | Latencia total p90 |
|-----------------------------------------------------|---------------------------|----------------|--------------------|
| Defaults Gemma + thinking activo (estado actual)    | 6/6 crisp                 | medido por el usuario | 4.3 s (medido)     |
| Defaults Gemma sin thinking                         | 2/6 crisp                 | -              | mucho menor        |
| Greedy (A) sin thinking                             | **MEDIR**                 | mismo que sin thinking | mismo                |
| Greedy (A) sin thinking + prefill `<|tool_call|>`   | **MEDIR**                 | mismo          | mismo              |
| Greedy (A) sin thinking + 2 few-shots               | **MEDIR**                 | +pequeño TTFT por prefill cacheable | similar |

---

## 3. El acoplamiento reasoning ↔ tool-call en SLMs 4B

### 3.1 Por qué el thinking sube 2/6 → 6/6

Tres hipótesis (no mutuamente excluyentes), con evidencia:

1. **Calibración / reducción de entropía** (más sólida): después del bloque `<|channel|>thought ... </channel|>`, las activaciones en las últimas capas del transformer concentran su masa de probabilidad en un puñado de tokens compatibles con "acción inminente". Cappelletti & Poppi et al. (Univ. of Modena & Reggio Emilia, arXiv 2505.15323, mayo 2025) muestra empíricamente — para MCQA, no tool-calling — que un prefijo benigno corto ("The correct option is: ") reduce el first-token misalignment de forma medible; el thinking actúa como un prefijo largo aprendido (interpretación nuestra).
2. **Re-enfoque de la atención sobre la instrucción del sistema**: el bloque de thought re-cita explícitamente las tools disponibles y el comando del usuario. En modelos 4B con ventana de atención limitada y system prompt largo (65 tools + ejemplos genéricos en el system), esto **mueve la información relevante al "recent past"** del KV-cache, donde la atención local es más fuerte.
3. **Sesgo de formato adquirido en post-training**: si Gemma 4 fue post-entrenado con muchos ejemplos `thought → tool_call`, el modelo aprende `P(tool_call_token | thought) >> P(tool_call_token | no_thought)`. El thinking activa esa correlación. Sin acceso al dataset de Google esto es **hipotético**; pero coincide con el patrón Lushbinary documenta para Gemma 4 ("Configurable thinking modes show step-by-step reasoning before tool calls, improving accuracy on complex tasks").

### 3.2 Sustitutos baratos

| Sustituto                                                       | Coste tokens | Eficacia esperada (HIPOTÉTICO)               | Comentario                                                                                                             |
|-----------------------------------------------------------------|--------------|----------------------------------------------|------------------------------------------------------------------------------------------------------------------------|
| **Greedy sampling**                                             | 0            | +3/6                                         | Ataca (1). Casi gratis.                                                                                                |
| **Prefill `<|tool_call|>` en assistant**                        | +2–3 tokens  | +2/6 adicional sobre greedy                  | Ataca (1) y (3). Requiere que en modo conversación NO se prefille (decisión del orquestador).                          |
| **Few-shot 2 ejemplos en system**                               | +50–120 tokens (cacheables) | +1/6 adicional                                | Ataca (3). KV-cache del sistema se reutiliza entre turnos si tu cliente preserva el prefix.                            |
| **Thinking "mini" (budget 16–32 tokens)**                       | +16–32       | Similar a thinking completo                  | Compromiso pragmático si las palancas baratas no llegan a 6/6. La medición del usuario (268 tokens p90) sugiere overuse. |
| **Re-prompt del sistema con las 4-6 tools en ese turno** (ya hecho) | 0 (ya hecho) | —                                            | Ya implementado por el router.                                                                                         |

### 3.3 Evidencia en benchmarks BFCL/ToolBench

- **EGPO** (Hao et al., *"Reasoning through Exploration: A Reinforcement Learning Framework for Robust Function Calling"*, arXiv 2508.05118, ago 2025): partiendo de **Qwen3-4B-Instruct-2507** y entrenando con xlam-function-calling-60k durante 5 épocas (lr=1×10⁻⁶) con CoT-guided exploration, su 4B *"achieves state-of-the-art results among similar sized models and outperforms a series of strong competitors like GPT-4o and Gemini-2.5 on BFCLv3"*. **Conclusión**: un 4B competitivo en function-calling es realista en 2025-2026, pero solo via RL/fine-tune dedicado, no via prompting estándar.
- **TinyLLM** (arXiv 2511.22138, nov 2025): los modelos <1B fallan en multi-turn/parallel/multi-function; el "sweet spot" 1–3B alcanza FC fiable en edge.
- **Hammer paper** (arXiv 2410.04587): Qwen2-1.5B con function masking supera a xLAM-7b-fc en BFCL.

### 3.4 Veredicto

**Reasoning NO es estrictamente necesario** — es un mecanismo costoso para hacer lo que sampling + prefill hacen barato. **VIABLE quitarlo si combinas ≥2 palancas baratas**.

---

## 4. Few-shot / prompting para tool-calling en 4B

### 4.1 Diagnóstico

Evidencia mixta pero útil:
- **LangChain blog "Few-shot prompting to improve tool-calling performance"**: few-shot mejora claramente en modelos open-weight medianos. El formato importa.
- **Sachin Kumar, *"Meta-Tool: Efficient Few-Shot Tool Adaptation for Small Language Models"*, arXiv 2604.20148 (22-abr-2026)**: con backbone Llama-3.2-3B-Instruct evaluado en Gorilla APIBench, Spider 2.0, WebArena e InterCode, el paper concluye: *"few-shot examples contribute +21.5% to performance and documentation contributes +5.0%, while the hypernetwork adds 0%"* (Tabla 2 del paper). Es decir, **few-shot es la palanca dominante** para SLMs en strict tool-calling.
- **Google Research blog "Few-shot tool-use doesn't really work (yet)"**: en zero-shot QA con tools, few-shot NO supera no-tool baseline en modelos grandes. Esto NO contradice lo anterior: es otro setting (decisión "usar tool sí/no" vs. "qué tool usar dado que ya decidiste").
- **PromptHub "The Few Shot Prompting Guide"**: la curva se aplana después de 2 ejemplos; añadir más a veces empeora.

Para tu caso (decisión: "qué tool de las 4-6 que el router ya seleccionó + qué args"), **2–3 ejemplos en el formato nativo Gemma 4** deberían dar el mayor lift por token gastado.

### 4.2 Formato exacto requerido (Gemma 4)

Los ejemplos few-shot DEBEN matchear el formato nativo o el modelo no los reconocerá como tool-calls válidos. Estructura:

```
<start_of_turn>user
Abre el navegador
<end_of_turn>
<start_of_turn>model
<|tool_call|>call:open_browser{url:<|"|>about:blank<|"|>}<|/tool_call|>
<end_of_turn>
<start_of_turn>user
Sube el volumen
<end_of_turn>
<start_of_turn>model
<|tool_call|>call:set_volume{level:50}<|/tool_call|>
<end_of_turn>
```

Notas críticas:
- El delimitador de strings es `<|"|>` (sí, ese token literal — ver issue #21316). NO uses comillas regulares dentro del JSON; el parser PEG de Gemma 4 lo rompe.
- Cierre con `<|/tool_call|>` (per_call_end).
- `function.name_prefix = "call:"` — siempre con prefijo `call:`.
- Separador de args: `,` (no newlines).

### 4.3 ¿Genéricos o específicos del turno?

**Genéricos canónicos** (2 ejemplos en el system, fijos) **+ específicos opcionales** (1 ejemplo construido por el router con una de las 4-6 tools del turno). El KV-cache de los genéricos se reutiliza siempre; el específico añade ~30–60 tokens de prefill que solo se computan en el primer turno con ese set de tools.

| Estrategia                              | Prefill extra | Reutilización KV-cache | Lift esperado (HIPOTÉTICO) |
|-----------------------------------------|---------------|------------------------|----------------------------|
| 0 few-shot (estado actual sin thinking) | 0             | 100%                   | baseline 2/6               |
| 2 genéricos en system                   | ~80 tokens    | 100%                   | +1–2/6                     |
| 2 genéricos + 1 específico por turno    | ~120 tokens   | 100% para genéricos    | +2/6                       |
| Solo 1 específico por turno             | ~40 tokens    | 0%                     | +1/6                       |

### 4.4 Veredicto

**VIABLE, riesgo bajo, alto impacto**. La interacción con el router es positiva: el router ya sabe las 4-6 tools del turno, sintetiza el específico desde un template. **MEDIR** el lift incremental sobre greedy puro.

---

## 5. QLoRA como último recurso

### 5.1 Diagnóstico

Vale el ROI **solo si** tras (sampling + prefill + few-shot) sigues por debajo del objetivo, **Y** si tu set de tools es estable (los 65 tools no van a cambiar drásticamente en los próximos meses). El fine-tune introduce un coste de mantenimiento permanente: cada vez que añades/modificas una tool, debes reentrenar o el modelo regresiona a comportamiento base sobre la tool nueva.

### 5.2 Referencias concretas 2025–2026

- **FunctionGemma (Google, blog.google, dic 2025)**: variante de Gemma 3 270M específicamente fine-tuneada para function-calling. El post oficial *"FunctionGemma: Bringing bespoke function calling to the edge"* reporta **58%→85%** en el dataset oficial **Mobile Actions** después de fine-tune (Google no especifica el tamaño del set de entrenamiento en ese benchmark). La cifra de "284 ejemplos / 3 funciones" proviene de un demo separado de Sasha Denisov (Google Developer Expert, *"On-Device Function Calling with FunctionGemma"*, Medium / google-developer-experts, dic 2025) con flutter_gemma sobre `change_background_color, change_app_title, show_alert` — no es el benchmark oficial. **Caveat importante**: FunctionGemma es un modelo *generalmente* débil (270M); su upside con fine-tune es alto pero parte de un baseline muy bajo. **Tu Gemma 4 E4B parte de un baseline mucho más alto** (modelo más capaz, ya entrenado con tool tokens nativos), por lo que el delta de fine-tune será **menor en términos absolutos** — más en el régimen +5–15 pp.
- **Hammer paper (arXiv 2410.04587)**: fine-tune de Qwen2-1.5B con dataset xlam-function-calling + función masking → outperforma xLAM-7b-fc en BFCL. Demuestra que SFT/QLoRA en 1.5B–7B con datos correctos sube tool-calling claramente. Detalle clave: **fine-tunear en xlam SIN augmentation degrada irrelevance detection** (el modelo llama tools cuando no debe). Necesitas datos negativos.
- **Medium "Fine Tuning SLMs on Agentic Tool Calling" (nicolas / dataenthusiast, Gemma 1B + xLAM, MacBook)**: reporta 10% → 79% en 15 min, sin GPU. Resultado muy llamativo pero sobre tooling sintético — extrapolar con cuidado.
- **EGPO (Hao et al., arXiv 2508.05118, ago 2025)**: RL con CoT-guided exploration sobre Qwen3-4B-Instruct-2507 + xlam-function-calling-60k (5 épocas, lr=1×10⁻⁶) alcanza SOTA en BFCLv3 superando a GPT-4o y Gemini-2.5. Modelo 4B competitivo en function-calling es realista en 2025-2026.

### 5.3 Costo entrenar y servir

| Item                                                       | Valor                                                                                                |
|------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| Hardware mínimo Gemma 4 E4B QLoRA                          | 16 GB VRAM (RTX 4090 / A5000); Unsloth reduce a ~12–14 GB                                            |
| Tiempo de fine-tune (1000–5000 ejemplos, 3 epochs)         | 1–4 h en RTX 4090                                                                                    |
| Dataset                                                    | xlam-function-calling-60k + tu domain (65 tools) + ~20% negativos (irrelevance) **CRÍTICO**          |
| Riesgo de regresión generalista                            | Real; mitigar con LoRA rank bajo (r=8–16) y mezclando 10–20% de instruction data general en el batch |
| Servir LoRA en llama.cpp                                   | `--lora <path.gguf>` + `--lora-scale 1.0`; o fusionar y reconvertir a GGUF (más rápido en inferencia)|

### 5.4 Veredicto

**NO RECOMENDADO COMO PRIMERA LÍNEA**. Pruébalo solo si después de sampling + prefill + few-shot estás <5/6 sostenido en producción. ROI marginal sobre las palancas baratas, con coste de mantenimiento alto. Si te decides, prioriza:
1. **Dataset propio** de ~500–2000 trayectorias de tus 65 tools reales (no genéricas).
2. **20–30% de ejemplos negativos** (irrelevancia, abstención, ambiguity).
3. **LoRA rank 8–16** (no más, para no inducir overfitting que rompa generalización).
4. **Evaluación en tu smoke test E2E, no en BFCL** — BFCL no representa tu distribución.

---

## Recomendaciones (orden de implementación)

### Fase 0 — Verificar el stack (HOY, 30 min)
- `curl /props` → confirmar `chat_format: peg-gemma4`. Si dice `Content-only`, el template del GGUF no incluye los tool tokens; pasar `--chat-template-file` con el oficial de Gemma 4.
- Confirmar build llama.cpp incluye PR #18675 (autoparser) y PR #21418 (peg-gemma4). b9090 lo cubre.

### Fase 1 — Sampling dual (HOY, 1 h, riesgo bajo)
- Modo acción: `temperature=0.0, top_k=1, top_p=1.0, min_p=0.0`. Override por request.
- Modo conversación: defaults Gemma.
- **Medir**: smoke test E2E de 6 crisp + 6 ambiguos. **Threshold**: si pasa de 2/6 a ≥4/6, sigue a Fase 2 sin más. Si <4/6, ajustar a Preset B.

### Fase 2 — Prefill + few-shot (1–2 días, riesgo bajo)
- Prefill: en modo acción, append `<|tool_call|>` al final del prompt como assistant prefix (vía `messages` con un último `assistant` con content `<|tool_call|>` parcial, o vía OpenAI-compat `extra_body` si tu cliente lo soporta).
- Few-shot: 2 ejemplos genéricos en el system, formato nativo exacto (sec. 4.2).
- **Medir** lift incremental. **Threshold**: si ≥5/6 sostenido en 50+ comandos reales, **declarar éxito sin reasoning**.

### Fase 3 — Estructura forzada (1 semana, riesgo medio)
- Si Fase 2 no llega a 5/6, evaluar `tool_choice="required"` permanente + tool sintético `respond_in_natural_language`. Requiere refactor del router.
- Alternativa: `response_format=json_schema` puro con un wrapper `{tool, args, abstain}`.
- **Threshold**: si sí mejora pero rompe naturalidad en respuestas, mantener el split sampling + few-shot y aceptar 4-5/6 (o reintroducir thinking con budget 16-32 tokens).

### Fase 4 — Thinking con presupuesto (mientras Fase 1–3 maduran)
- En el ínterin, **bajar el budget de thinking de 268 a 16–32 tokens** y medir si la tasa se sostiene a 6/6. Ahorro de latencia 80–90% sin cambios estructurales.

### Fase 5 — QLoRA (último recurso, 2–4 semanas, riesgo alto)
- Solo si Fase 1+2+3 sostienen <5/6 sobre 1000+ comandos reales.
- Dataset propio + 25% negativos + LoRA r=16.
- Servir con `--lora` o fusionar.

### Benchmarks que disparan el cambio de fase
- **Fase 1 → 2**: <4/6 en smoke test.
- **Fase 2 → 3**: <5/6 sostenido sobre 50 comandos reales.
- **Fase 3 → 4**: respuestas naturales degradadas (medir con thumbs-up rate o evaluación humana).
- **Fase 4 → 5**: latencia thinking-minified todavía >1.5 s p90 Y tasa <6/6.

---

## Caveats

1. **Distinción de familias (CRÍTICO)**: tu stack dice "Gemma 4 E4B-it" pero menciona "tipo Gemma 3n / MatFormer". Estas son familias distintas. Solo **Gemma 4** (E2B/E4B/26B-A4B/31B, 2026) tiene el path `peg-gemma4` con `<|tool_call|>` nativo y autoparser. **Gemma 3n** (E2B/E4B, 2025) **no tiene template nativo de tool-call** en llama.cpp (cae a `Content-only`/`Generic`, confirmado en llama-cpp-python PR #1989: *"gemma3 does not have builtin support for tool call tokens or json schema enforcement … chat_template does not include tool use structures"*); para tool-calling con Gemma 3n tienes que inyectar manualmente el formato y un GBNF propio. **Verifica con `/props` cuál tienes realmente**. Si el stack real es Gemma 3n, gran parte de la sección 1 (autoparser lazy, peg-gemma4, trigger `<|tool_call|>`) **no aplica directamente** y debes implementar el trigger + grammar tú mismo en el system prompt y vía `grammar` raw.
2. **PR #21418 advierte explícitamente** que la gramática auto-generada para Gemma 4 fuerza el formato del wrapper pero **NO valida los argumentos JSON contra el schema de la tool**. Validación post-hoc en tu cliente sigue siendo necesaria.
3. **Issue #20345 (abierta Mar 2026, build d088d5b)**: `response_format=json_schema` con thinking activo desactiva silenciosamente la gramática (*"When response_format (JSON schema) is used with enable_thinking: true, grammar enforcement is completely inactive"*). Si combinas ambos, verifica con `--verbose`.
4. **Issues #21316, #21384, #21338**: el parser `peg-gemma4` tiene bugs activos en builds recientes (tokens `<|"|>` filtrados, arrays serializados como string, infinite loops). Si encuentras outputs raros, contrastar con esos issues antes de asumir que es problema tuyo.
5. La cifra **FunctionGemma 58→85%** se refiere al **Mobile Actions dataset oficial de Google** sobre Gemma 3 **270M** (post oficial en blog.google, dic 2025); la cifra "284 ejemplos / 3 funciones" es de un demo independiente de Sasha Denisov, no del benchmark oficial. El lift absoluto para tu Gemma 4 E4B (modelo 15× mayor, con tool tokens nativos) será menor.
6. Todas las cifras de "lift esperado" en few-shot, prefill y sampling son **hipotéticas**, basadas en literatura general (Meta-Tool +21.5 pp en SLMs es el dato más sólido que tenemos); **deben medirse con tu smoke test E2E**. No hay benchmarks públicos específicos de Gemma 4 E4B + tool-calling sin reasoning en BFCL al 23 mayo 2026.
7. Los defaults `temp=1.0, top_k=64, top_p=0.95` recomendados por Google son para inferencia general, no específicamente para tool-calling. No estás violando ninguna guideline al bajarlos para modo acción.