# 04 — Investigación Externa

**Fecha**: 2026-05-11

Cada decisión arquitectónica de Carter debe estar respaldada por evidencia. Aquí están las fuentes consultadas y qué saqué de cada una.

---

## 1. Papers científicos

### 1.1 UI-TARS-2 ([arxiv 2509.02544](https://arxiv.org/abs/2509.02544))

**ByteDance, Sep 2025**. GUI agent con multi-turn RL.

**Aporte a Carter**:
- Pattern de **causal recovery**: cuando una acción falla, comparar pantalla actual vs target y re-planear (no adivinar). Aplicado en `_focus_window_changed_by_last_action`.
- Resultados OSWorld 47.5%, WindowsAgentArena 50.6%. Como referencia: Carter usa 4B no entrenado para GUI; UI-TARS-2 es 7-72B con RL específico.
- Pattern de **percepción integrada al action token**: vision inline en el mismo forward pass. Para Carter (que delega a tools), el equivalente es inyectar screenshot+description al next_messages automáticamente.

**Limitación**: el RL post-training no es reproducible en local (requiere infra distribuida). Para Carter, el equivalente práctico es LoRA fine-tune con el bench oficial 540 como dataset.

### 1.2 Voyager ([NeurIPS 2023](https://voyager.minedojo.org/))

**MineDojo, Wang et al.**. Embodied agent en Minecraft con skill library y curriculum.

**Aporte a Carter**:
- **Skill library** persistente: Carter tiene `skill_store.py` (recipes COMPLETED). OK.
- **Verifier on-target**: Voyager verifica si la **meta** está cumplida, no si una sub-acción se ejecutó. **Esto es lo que falta en Carter** — el `mission_goal verifier`.
- **Automatic curriculum**: Voyager genera "qué skill aprender después" via LLM. Carter no tiene esto. Es nice-to-have, no crítico para 540 bench.

> "Voyager consists of three key components: 1) an automatic curriculum, 2) an ever-growing skill library, 3) iterative prompting mechanism that incorporates environment feedback, execution errors, and self-verification."

Pattern aplicado parcialmente. Mission_goal verifier sería el componente 3 completo.

### 1.3 Reflexion ([NeurIPS 2023](https://arxiv.org/abs/2303.11366))

**Shinn et al.**. Self-reflection sobre errores para mejorar próximo intento.

**Aporte a Carter**:
- **Two-tier escalation**: primer match dispara self-correction prompt, segundo match aborta. Aplicado en `loop_detection.py` v2.
- **Result-aware hashing**: incluido en mi v2 implementación (mejora sobre Reflexion vanilla).

### 1.4 RAG-MCP ([arxiv 2505.03275](https://arxiv.org/abs/2505.03275))

**Tool retrieval via dense embeddings**.

**Aporte a Carter**:
- accuracy 13.62% → 43.13% con top-K vs all-tools
- tokens -50%
- Carter usa multilingual-e5-small (384-dim), top-K=12 default. Aligned.

**Insight nuevo**: bajar top-K a 8 puede mejorar Gemma 4 4B accuracy más todavía (Google docs: 5-15 tools recomendado).

### 1.5 Tool-to-Agent Retrieval ([arxiv 2511.01854](https://arxiv.org/pdf/2511.01854))

**Embeddings compartidos tools + agentes, retrieval granular**.

**Aporte a Carter**: confirma el approach actual de Carter. No requiere cambio.

### 1.6 Online-Optimized RAG ([arxiv 2509.20415](https://arxiv.org/html/2509.20415v1))

**Adaptación online del retriever con feedback**.

**Aporte a Carter**: nice-to-have futuro. Por ahora el retriever es estático.

### 1.7 OSWorld ([NeurIPS 2024](https://os-world.github.io/))

**XLANG, 369 tasks computer-use, multi-OS**.

**Aporte a Carter**:
- Frontier: Claude Opus 4.6 = 72.7%, Holo3-35B-A3B = 82.6%.
- Open-source SOTA: Qwen3-VL-235B = 66.7%.
- Human baseline: 72-84%.
- **4B no aparece en leaderboard**.

**Implicación honesta**: Carter no aspira a OSWorld-level. Aspira a "Jarvis local honesto con tools simples".

### 1.8 OSWorld-Human ([MLSys 2026](https://mlsys.wuklab.io/posts/oshuman/))

**Eficiencia de computer-use agents**.

> "As an agent uses more steps to complete a task, each successive step can take 3x longer than steps at the beginning of a task. Additionally, even the best agents take 1.4-2.7x more steps than necessary."

**Aporte a Carter**: confirma que el problema de latencia es inherente al pattern "1 LLM call por tool". Mitigación: encadenar tools sin follow-up cuando el verifier confirma.

---

## 2. Documentación oficial

### 2.1 Anthropic: Building Effective Agents

[https://www.anthropic.com/research/building-effective-agents](https://www.anthropic.com/research/building-effective-agents)

**Aporte a Carter**:

> "When building applications with LLMs, find the simplest solution possible, and only increase complexity when needed."

> "Successful implementations use simple, composable patterns rather than complex frameworks."

> "Only 1.6% of Claude Code's codebase is AI decision logic — the other 98.4% is deterministic infrastructure including permission gates, context management, tool routing, and recovery logic."

> "Frameworks can create extra layers of abstraction that obscure underlying prompts and responses, making them harder to debug, and can make it tempting to add complexity when a simpler setup would suffice."

**Aplicación a Carter**: refactor de agent.py para simplificar. NO eliminar la infra determinística (es 98% del valor). SÍ reducir abstracciones innecesarias (3 routers → 1, etc.).

### 2.2 Google AI: Gemma 4 Function Calling

[https://ai.google.dev/gemma/docs/capabilities/function-calling](https://ai.google.dev/gemma/docs/capabilities/function-calling)

**Aporte a Carter**:
- Gemma 4 tiene 6 special tokens nativos (`<|tool>`, `declaration:`, `<|tool_call>`, `call:`, `<|tool_response>`, `response:`).
- Estos los maneja la chat template (`--jinja` en llama-server).
- OpenAI-compat schema funciona directamente.

**Carter ya lo usa correctamente** via llama-server.

### 2.3 Google AI: Gemma 4 Prompt Formatting

[https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4](https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4)

**Aporte**: el format oficial es manejado por Jinja. Carter no necesita escribir prompts en formato Gemma — el adapter lo hace.

### 2.4 HuggingFace: Gemma 3 4B discussion #24

[https://huggingface.co/google/gemma-3-27b-it/discussions/24](https://huggingface.co/google/gemma-3-27b-it/discussions/24)

**Aporte CRÍTICO a Carter**:

> "The 4b models have a genuine tool-call bias regardless of prompt."

> "If you need to use the 4b model in a context with conversational turns, add an explicit system prompt instruction: **Only call a tool when the user asks you to perform an action. For questions and explanations, respond in plain text.**"

> "Large system prompts with 22+ tools result in accuracy degradation and format errors increase."

> "Tool selection accuracy is roughly the same between base and fine-tuned models — the base 12b and 27b already perform well. However, the key benefit of fine-tuning is reliable XML format compliance."

**Aplicación**: añadir frase explícita al CORE_PROMPT + limitar tools visibles a ≤16.

### 2.5 llama.cpp function calling docs

[https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md)

**Aporte**:
- `--jinja` requerido para tool calling correcto.
- GBNF grammar opcional para JSON estricto.
- llama-server emite tool_calls en OpenAI-compat.

**Carter usa**: `--jinja --port 8080 -ngl 99 -c 16384 --parallel 1 --ctx-checkpoints 1 --flash-attn on`. Sin GBNF. Adecuado.

### 2.6 Microsoft Learn: AllowSetForegroundWindow

[https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-allowsetforegroundwindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-allowsetforegroundwindow)

**Aporte a Carter**:
- `SetForegroundWindow` está bloqueado por defecto en procesos no-foreground.
- Solución: `AllowSetForegroundWindow(ASFW_ANY)` antes de cambiar foreground.
- + truco ALT-press (documentado en gist Aetopia/pinvoke.net) si lo anterior no alcanza.

**Aplicado en `_force_set_foreground` y `_allow_foreground_any`** (sesión anterior).

### 2.7 Microsoft Learn: URI Schemes HKCR

[https://learn.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/platform-apis/aa767914](https://learn.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/platform-apis/aa767914(v=vs.85))

**Aporte a Carter**:
- Apps registran URI handlers en `HKEY_CLASSES_ROOT\<scheme>\URL Protocol`.
- Para detectar si un scheme está disponible: leer ese registry path.

**Aplicado en `deeplinks.is_protocol_registered`**. Cero hardcode de "Steam está instalado" — pregunta al SO.

### 2.8 pywinauto docs

[https://pywinauto.readthedocs.io/](https://pywinauto.readthedocs.io/)

**Aporte**:
- backend="uia" para apps modernas.
- `set_focus()` desde 0.6.2+ maneja restore de ventana minimizada.
- Performance: `searchDepth=1`, evitar `print_control_identifiers()`, cache control references.

**Aplicación**: Carter usa COM UIA directo (no pywinauto), pero los principios aplican. `_enumerate_clickable_uia` debe tener depth limit.

### 2.9 Pydantic AI

[https://ai.pydantic.dev/agent/](https://ai.pydantic.dev/agent/)

**Aporte**:
- Type-safe tools con Pydantic models.
- Provider switching (OpenAI/Anthropic/Ollama/llama.cpp).
- `Agent` con typed deps + output type.

**Aplicación a Carter**: introducir `MissionGoal`, `OutcomeState`, `ToolResult` como Pydantic models. Mantener `dict` para tool args (flexibilidad).

---

## 3. Repositorios open source serios

### 3.1 ByteDance UI-TARS

[https://github.com/bytedance/UI-TARS](https://github.com/bytedance/UI-TARS)

Reference de cómo construir GUI agent moderno. Carter no es un VLM nativo como UI-TARS, pero el pattern de causal recovery aplica.

### 3.2 ggml-org llama.cpp

[https://github.com/ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)

Backend de Carter para Gemma 4. Build b9090 CUDA. Issue 22396 documenta fix de Gemma 4 PEG parser en multi-turn (resuelto upstream).

### 3.3 pydantic/pydantic-ai

[https://github.com/pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai)

Reference de cómo construir agent framework con types. Carter NO se va a portar a Pydantic AI (mucho refactor) pero adopta el principio de typed schemas.

### 3.4 xlang-ai/OSWorld

[https://github.com/xlang-ai/osworld](https://github.com/xlang-ai/osworld)

Reference benchmark. Carter no participa pero el setup informa qué tipos de task son realísticos para 4B (responses cortas, tools deterministas, no GUI compleja).

---

## 4. Benchmarks reconocidos

### 4.1 OSWorld-Verified Leaderboard 2026

[https://benchlm.ai/benchmarks/osWorldVerified](https://benchlm.ai/benchmarks/osWorldVerified)

Confirma que 4B no es competitivo en GUI benchmarks. Carter debe definir su scope honesto.

### 4.2 LLM Stats

[https://llm-stats.com/benchmarks](https://llm-stats.com/benchmarks)

Source de comparación SOTA. Útil para ajustar expectativas.

---

## 5. Blogs/reportes técnicos confiables

### 5.1 Anthropic 2026 Agentic Coding Trends Report

[https://resources.anthropic.com/hubfs/2026 Agentic Coding Trends Report.pdf](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf)

> "Only 1.6% of Claude Code's codebase is AI decision logic..."

Source de la cifra usada en mi auditoría. Carter alinea con esa filosofía pero el agent.py se infló.

### 5.2 Stanford 2026 AI Index

[https://aiindex.stanford.edu/](https://aiindex.stanford.edu/)

> "while frontier models are advancing fast, the gap between benchmark performance and real-world deployment performance remains wide."

Aplicable a Carter: usuario reporta que el bench oficial sale bien pero el uso real falla — eso es el gap.

### 5.3 Coasty Blog: OSWorld 2026 results

[https://coasty.ai/blog/osworld-benchmark-results-2026-computer-use-ranked](https://coasty.ai/blog/osworld-benchmark-results-2026-computer-use-ranked)

Resumen de quién gana qué. Útil para contexto SOTA.

---

## 6. Mapeo evidencia → decisión Carter

| Decisión Carter | Evidencia | Fuente |
|----------------|-----------|--------|
| Mantener tool retrieval top-K | accuracy +30 pts | RAG-MCP arxiv 2505.03275 |
| CORE_PROMPT <1500 tokens | reduce format errors en 4B | HF Gemma discussion #24 |
| Tools visibles ≤16 | "22+ degrada accuracy" | HF Gemma discussion #24 |
| Mission goal verifier | Voyager pattern | Voyager NeurIPS 2023 |
| Causal focus post-action | UI-TARS-2 recovery | arxiv 2509.02544 |
| Sampling T=1.0 top_p=0.95 | sampling oficial Gemma | Google AI docs |
| `--jinja` en llama-server | chat template correcto | llama.cpp docs |
| AllowSetForegroundWindow | unblock SetForegroundWindow | Microsoft Learn |
| HKCR `URL Protocol` lookup | universal app detection | Microsoft Learn |
| Loop detection two-tier | self-correction antes de abort | Reflexion NeurIPS 2023 |
| `MissionGoal` Pydantic | type safety en boundaries | Pydantic AI |
| Refactor agent.py | "keep loop minimal" | Anthropic Effective Agents |
| Eliminar per-app hardcodes | V7 ContextoCarter + universal | Self-imposed value |

---

## 7. Síntesis para Carter

La investigación externa confirma:

1. **Carter aplica patrones SOTA correctos**: tool retrieval, causal focus, loop detection v2, verifier por-tool. Eso justifica el 8/10 de diseño.
2. **Lo que falta**: mission_goal verifier (Voyager), CORE_PROMPT compactado, tools≤16, ModelCapability abstraction.
3. **Lo que no se puede lograr con 4B**: OSWorld-level GUI workflows. Aspirar a eso es honestamente irrealista. Pero "Jarvis local + tools simples + cadenas cortas" SÍ es alcanzable y útil.
4. **Latencia es el cuello de botella real**, no funcionalidad. Reducir LLM calls post-tool es la palanca de mayor impacto.

Las fuentes están registradas. Cada decisión que tome en Fase 3-4 referenciará una de estas.
