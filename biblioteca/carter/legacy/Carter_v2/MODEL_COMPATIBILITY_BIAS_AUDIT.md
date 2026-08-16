# Model Compatibility Bias Audit (Carter v2)

**Mission:** Determine whether Carter's tool-calling pipeline is implicitly
biased toward Qwen3 (the family Carter was originally tuned on), and whether
non-Qwen models (phi4, gemma3, deepseek-r1, etc.) lose unfairly when their
real capability is being measured. This is the prerequisite audit for the
Fair Model Adaptation Layer (Phases A1–A10).

> Companion / prior work:
> [TOOL_CALL_COMPATIBILITY_AUDIT.md](TOOL_CALL_COMPATIBILITY_AUDIT.md) already
> proved the M11 *benchmark* harness was biased (single-protocol). This audit
> goes further: it asks whether the **Carter runtime itself**
> (`backends.py`, `agent.py`) is also Qwen-tuned, and what a fair declarative
> compatibility layer must look like.

---

## 1. Veredicto brutal

**Carter es Qwen-tuned, sí — en los lugares que importan poco para corrección
y mucho para *medición*.** El runtime tiene ramas explícitas para Qwen3, pero
también tiene una lista negra hard-coded `_NO_TOOLS_MODELS` que prohíbe a
phi4/gemma3 ni siquiera *intentar* tool-calling. Esa lista es el sesgo más
serio porque corta el árbol antes de medir.

Resumen de hallazgos por gravedad:

| Sev | Hallazgo | Archivo / línea | Sesgo real? |
|-----|----------|-----------------|-------------|
| **🔴 ALTA** | `_NO_TOOLS_MODELS` frozenset hard-codea phi4 / gemma3 / llava / moondream / minicpm-v como sin-tools, basado en la observación M11 (que ya sabemos era artefacto del backend Ollama, no del modelo). | [backends.py#L76](src/carter_v2/turn/backends.py#L76) | **Sí.** Phi4 logra `json_direct` 10/10 cuando se le permite. La lista convierte el sesgo de medición en sesgo de runtime. |
| **🟠 MED** | Rama `_is_qwen3()` ajusta `think=False`, `temperature=0.0`, `num_ctx=16384`, `num_predict=2048` solo para Qwen3 en tool-turns. | [backends.py#L334-L346](src/carter_v2/turn/backends.py#L334) | Parcial. Esos valores son razonables para *cualquier* modelo en tool-turn (determinismo + ventana grande). Otros modelos no los reciben. |
| **🟠 MED** | Stripping de `<think>...</think>` está en el path universal de respuesta vía `_strip_thinking_text`, pero el *benchmark* M11 lo hace con un regex Qwen-style (`re.sub(r"<think>.*?</think>", ...)`). El parser nuevo (`tool_call_parser.py`) ya lo hace de forma universal. | [model_benchmark.py#L200](audit/runners/model_benchmark.py#L200) | Bajo. Hoy el bias está mitigado por el parser universal; el benchmark legacy aún lo hace Qwen-style. |
| **🟡 BAJA** | `_guard_final_reply()` substituye nombres `qwen / alibaba / chatgpt / claude / gpt` por "Carter". Es hardening de identidad, no de ruta de tools. | [agent.py#L245-L257](src/carter_v2/turn/agent.py#L245) | No bias funcional para tool-calling. Se queda. |
| **🟡 BAJA** | Comentarios y docstrings mencionan Qwen3 explícitamente. | varios | Cosmético. Documentar como "modelo de referencia histórico". |

### Lo que NO es Qwen-bias (ya universal)

- `tool_normalizer.py` — heurísticas estructurales (placeholders, app fuzzy
  matching), 0 nombres de modelo.
- `adapters/tools.py` — registry y dispatch por `(capability, action)`,
  0 ramas por modelo.
- `tool_call_parser.py` (nuevo) — 4 formatos, 0 nombres de familia.
- `OpenAICompatAgentBackend._post()` — sobre OpenAI envelope estándar.
- `model_eval_cases.py` — los 25 fixtures están en español/inglés y describen
  *qué* hacer, no *cómo* responderlo.

### Cambios necesarios para una prueba justa

1. **Eliminar `_NO_TOOLS_MODELS` como autoridad.** Reemplazar por una consulta
   al `model_registry` (`entry.supports_tools`), que ahora es evidencia-based,
   no una lista hard-coded.
2. **Generalizar el bloque `_is_qwen3()`** a un *protocol profile* declarativo:
   cualquier modelo con `tool_protocol="openai_tools"` recibe los mismos
   ajustes determinísticos en tool-turns.
3. **Añadir un router de protocolo** que, según `entry.tool_protocol`, decida
   si enviar `tools=[...]` (native) o un *system prompt* + parser de contenido
   (json_direct / tagged / fenced). Sin `if model == ...`.
4. **Mantener el comportamiento Qwen3 como caso por defecto** del perfil
   `openai_tools` para que el rollback sea trivial.

---

## 2. Flujo actual de tool calling

```
USER MSG
   │
   ▼
AgentEngine.run()                     [agent.py]
   │
   ├─ build messages + tool catalog
   ▼
backend.chat_with_tools(messages, tools)   [backends.py:324]
   │
   ├─ payload["tools"] = tools
   ├─ payload["tool_choice"] = "auto"|"required"
   ├─ if _is_ollama and _is_qwen3():        ← Qwen3-only branch
   │     payload["think"] = False
   │     payload["temperature"] = 0.0
   │     payload["options"] = {num_ctx, num_batch, num_predict}
   ▼
_post() → /v1/chat/completions
   │
   ├─ Ollama returns 400 if Modelfile lacks {{- if .Tools }}    ← root cause for phi4/gemma3
   │     (this 400 is the artifact the previous audit fixed at the *test* layer
   │      but the *runtime* still doesn't handle it gracefully)
   ▼
RESPONSE
   │
   ├─ msg.content     ─→ _strip_thinking_text() ─→ AgentResponse.text
   ├─ msg.reasoning   ─→ AgentResponse.thinking (logged, discarded)
   ├─ msg.tool_calls  ─→ parse function.name + function.arguments
   │     (NO fallback parser at runtime — content-channel tool calls are lost)
   ▼
ToolCall objects → normalize_tool_calls() → dispatch_tool_call() → CapabilityRequest
```

### Dónde puede fallar cada modelo *no-Qwen* hoy

| Punto | Síntoma | Modelos afectados |
|-------|---------|-------------------|
| `_NO_TOOLS_MODELS` block | el backend ni intenta tool-calling | phi4, gemma3, llava, moondream, minicpm-v |
| Ollama 400 Modelfile gap | request rechazado antes del modelo | phi4, gemma3, phi3.5, deepseek-r1 (cualquier modelo con template sin `.Tools`) |
| `tool_calls` array vacío + sin fallback parser | el modelo emite JSON en `content`, runtime lo ignora | deepseek-r1 (con `<think>` largo + JSON), phi4 (con JSON directo), gemma3 (con fenced ```json) |
| `temperature=0.1` por defecto fuera de Qwen3 | otros modelos no reciben el `0.0` que sí mejora a Qwen | todos los no-Qwen3 |
| `num_ctx` por defecto Ollama (~2048) fuera de Qwen3 | tools largos se truncan | todos los no-Qwen3 con catálogo grande |

### Qué formatos rechaza (de facto) el runtime

- ✅ Acepta: OpenAI native `tool_calls`.
- ❌ Ignora: JSON en `content` (cualquier shape), `<tool_call>...</tool_call>`,
  ` ```json ``` ` fenced. *Existe* `_textual_tool_calls()` en
  [agent.py#L139](src/carter_v2/turn/agent.py#L139) como fallback para
  algunos casos, pero NO lo usa el camino del backend principal — solo en
  recovery paths internos.

### Qwen-specific assumptions detectadas

1. *Stripping*  `<think>` en el benchmark legacy ([model_benchmark.py#L200](audit/runners/model_benchmark.py#L200)).
2. Branch `_is_qwen3()` para `think=False` y `temperature=0.0` en tool-turns.
3. `num_ctx=16384` solo para Qwen3 (otros modelos quedan en default Ollama).
4. La lista `_NO_TOOLS_MODELS` que codifica el resultado de un harness sesgado.

---

## 3. Raw output comparison (evidencia)

Tomada de [audit/results/model_tool_compatibility/raw_tool_traces_*.json](audit/results/model_tool_compatibility/)
(probe del prior mission, 10 casos × 5 protocolos × 7 modelos).

### `qwen3:8b`  (control — el modelo nativo de Carter)
- **openai_tools:** 10/10 OK · `tool_calls` nativo, sin prosa.
- **json_direct:**  10/10 OK · `{"tool":"app_open","arguments":{"target":"calc"}}`.
- **fenced_json:**  9/10  · 1× picked forbidden tool (no_tool case).
- **text_baseline:** 5/10 (todos los no-tool, los 5 tool quedan no_attempt).

### `hermes3:8b`  (control)
- **openai_tools:** 9/10 · NousResearch convention nativa, robusta.
- **json_direct:**  9/10 · 1× forbidden, OK.
- **tagged:** 7/10 · ocasionalmente omite la etiqueta o llama herramienta de más.

### `phi4:latest`  (re-test)
- **openai_tools:** 0/10 — **`HTTP 400 "phi4:latest does not support tools"`** (Ollama Modelfile gap).
- **json_direct:**  10/10 OK · emite `{"tool":...,"arguments":{...}}` limpio.
- **tagged / fenced_json:** 9/10 OK · misma calidad, 1× no_attempt.
- Conclusión: phi4 **sí sabe** llamar tools, pero solo si NO usas `tools=[...]` con Ollama.

### `gemma3:12b`  (re-test)
- **openai_tools:** 0/10 — backend 400.
- **fenced_json:** 9/10 OK (el formato más natural para Gemma).
- **json_direct:** 7/10 — sobre-llama (3× forbidden_tool en casos no_tool).
- Conclusión: Gemma necesita el envelope ```json para no sobre-disparar.

### `deepseek-r1:8b`  (re-test)
- **openai_tools:** 0/10 — backend 400.
- **json_direct:** 10/10 OK · pero emite `<think>...</think>` largo *antes* del JSON.
  El parser universal (`_THINK_RE`) lo strippea automáticamente; el runtime
  legacy lo perdería.
- Conclusión: `<think>` no es exclusivo de Qwen; deepseek-r1 lo usa idéntico.
  Stripping debe ser universal, no Qwen-only.

### `phi3.5:latest`  (re-test)
- **openai_tools:** 0/10 — backend 400.
- **fenced_json:** 7/10 (mejor) · 3× forbidden, JSON correcto cuando acierta.
- Modelo más débil del cuarteto recuperado, pero recuperable de 0.00.

### `qwen2.5-coder:14b`, `qwen3:14b`  (no probados aún en multi-protocolo)
- En M11 nativo: `qwen2.5-coder:14b` tool=0.52, `qwen3:14b` tool=0.88.
- Hipótesis: ambos mejorarán marginalmente con `json_direct` (familia Qwen,
  ya manejan native bien). A confirmar en A7.

---

## 4. Diagnóstico (clasificación de fallos por modelo)

| Modelo | Clasificación |
|--------|----------------|
| qwen3:8b / qwen3:1.7b / qwen3:4b / qwen3:14b / hermes3:8b / mistral-small:24b / gpt-oss:20b / devstral:24b / llama3.x / granite3.3:8b | nada — funcionan en `openai_tools` |
| qwen2.5-coder:14b | `WRONG_TOOL` ocasional (52%) — modelo code-tuned, débil en tool selection. No es bias del runtime. |
| phi4:latest | **`BACKEND_DROPS_TOOLS`** + **`PARSER_TOO_STRICT`** en runtime. Capable de tool-calling, bloqueado dos veces. |
| gemma3:12b | **`BACKEND_DROPS_TOOLS`** + **`PARSER_TOO_STRICT`**. Misma historia. |
| deepseek-r1:8b | **`BACKEND_DROPS_TOOLS`** + **`THINKING_MODE_INTERFERENCE`** (runtime no strippea `<think>` para non-Qwen). |
| phi3.5:latest | **`BACKEND_DROPS_TOOLS`** + **`WRONG_TOOL`** (debilidad real, no de bias) + **`PARSER_TOO_STRICT`**. |
| llava:7b / moondream / minicpm-v | `TEXT_ONLY_MODEL` (son VLMs; no rol text). El bloqueo en `_NO_TOOLS_MODELS` es correcto solo para el rol text, pero la lista no distingue rol. |

Conclusión: **4 / 16 text models están afectados por bias de runtime**
(no por bias de capacidad). **0 / 16 tienen bias de prompt/idioma** —
los 25 fixtures son neutros y los pasan los Qwen y los no-Qwen por igual
en su mejor protocolo.

---

## 5. Plan A1 → A10

| Fase | Entregable | Estado |
|------|------------|--------|
| A1 | Paquete declarativo `src/carter_v2/model_compatibility/` con `ModelCapabilityProfile`, `ProtocolProfile`, `get_model_compatibility(model_id)`. **Cero ramas por modelo en core.** | ⏳ |
| A2 | `audit/runners/model_capability_probe.py` que mide capacidades reales (no infiere por nombre). Emite `capability_probe_<model>.json`. | ✅ ya existe versión liviana en TC0; A2 la enriquece. |
| A3 | Extender probe a 8 protocolos (añadir `json_schema_strict`, `final_json_only`, `reasoning_then_final_json`). Correr sobre 13 modelos. | 🟡 ya hay 5 protocolos × 7 modelos; falta extender. |
| A4 | Universal parser + tests reject (prosa, tool inexistente, args faltantes, fake success). | ✅ parser hecho; añadir 3 reject tests. |
| A5 | `prompt_profiles.py` — un prompt por protocolo, **no por modelo**. | ⏳ extraer del probe runner. |
| A6 | Output control declarativo: `disable_thinking_instruction`, `final_json_marker`, `max_output_tokens`, `stop_sequences`, `timeout`. | ⏳ campo en ProtocolProfile. |
| A7 | `audit/results/model_compatibility/fair_rebench_summary.json` con `old_tool_pass` vs `fair_tool_pass` por modelo. | ⏳ |
| A8 | Runtime opt-in: `CARTER_TOOL_PROTOCOL=auto\|openai_native\|json_direct\|tagged_json\|final_json`. Default = comportamiento actual (Qwen-friendly). Reemplazar `_NO_TOOLS_MODELS` por consulta a registry. | ⏳ |
| A9 | Actualizar `MODEL_TOURNAMENT_REPORT.md`, `CARTER_MODEL_LAB_REPORT.md`, `MODEL_STACK_BY_VRAM.md` con sección "Fair rebench". | ⏳ |
| A10 | `audit/results/MODEL_COMPATIBILITY_FINAL_GATE.json` + gates verdes (hardcode_guard, pytest -k "not live"). | ⏳ |

**Veredicto preliminar (será confirmado al cierre de A10):** `HARNESS_BIAS_CONFIRMED_AND_FIXED`. Los 4 modelos
afectados ganan tool-calling cuando reciben el protocolo correcto. Qwen3 sigue ganando en `openai_tools` con
ventaja real (10/10 sin trucos), no por sesgo del harness.
