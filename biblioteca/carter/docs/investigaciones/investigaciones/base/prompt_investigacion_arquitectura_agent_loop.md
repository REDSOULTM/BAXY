# Prompt de Investigación — Arquitectura del Agent Loop para Misiones Multi-step

## Contexto del proyecto

Carter v4 es un asistente local Jarvis-style con loop ReAct single-thread, modelo `qwen3:4b-instruct-2507-q4_K_M`, latencia tipo Alexa. Tengo 47 tools, 75 unit tests verde. Audit manual de la matrix oficial 540 dio 96.1% PASS REAL.

Las **categorías más débiles** son:

- **C14 misiones multi-paso** (25/30 manual): "abre Steam, ve a biblioteca, busca Batman" — el modelo se rinde después del paso 2-3.
- **C11 terminal** (27/30): tasks que requieren combinar terminal_run con filesystem, el modelo no encadena.
- **C13 GUI** (27/30): cuando un click falla, el modelo no reintenta con estrategia distinta.

El loop actual es:
```
run_turn(user_text):
  resp = llm.chat(system, history+user, tools)
  if resp.tool_calls:
    return _execute_tool_calls(...)
  else:
    return resp.text + footer

_execute_tool_calls:
  for tc in tool_calls:
    safety_check + dispatch + verifier
  followup = llm.chat(system, history+user+assistant+tools, tools)
  if followup.tool_calls:
    return _chain_more_tools(depth=1)
  else:
    return reply
```

Max depth=3, max budget=25s. Compaction al 70% num_ctx.

## Lo que necesito que investigues a fondo

### 1. Plan-and-Execute light vs ReAct puro vs híbrido

El research dossier inicial recomendaba ReAct single-thread. Pero los fails C14 sugieren que para misiones explícitas (≥3 pasos), un planner LLM call único al inicio podría ayudar.

- ¿Cuándo conviene planner vs ReAct puro? Heurística estructural sin keyword lists.
- ¿Cómo implementar "planner light" que NO rompa latencia Alexa para casos simples? (ej: detectar misión por ≥2 verbos imperativos coordinados).
- Implementaciones de referencia: LangGraph plan-and-execute, Devin's AgentScheduler, Cursor Composer's planner.
- Planner debe devolver lista de tool stubs (no args concretos) para que cada paso resuelva sus args en runtime.

### 2. Skill library / procedural memory aprendida

Audit competidores reveló que OS-Copilot/FRIDAY guarda recipes exitosas y las reutiliza.

- ¿Cómo implementarlo en SQLite (ya tengo) sin rompimiento?
- Schema sugerido: `skills(prompt_fts, recipe_json, score, evidence)`.
- ¿Qué prompt usar como crítico LLM (0-10)? Costo/beneficio de un LLM call extra al final de turns exitosos.
- ¿Cómo retrieve top-K skills similares al prompt actual sin ralentizar el turn?
- ¿Inyectar como few-shot en system prompt o como context separado?

### 3. Action ledger cross-turn anti-loop

Ya implementé `loop_detection.py` con 4 detectores (generic_repeat, unknown_tool_repeat, ping_pong, global_circuit_breaker). 

- ¿Hay otros patrones de stuck que debería detectar?
- Heurística de "no progress" más sofisticada que SHA-256 hash. ¿Cómo medir progreso real (e.g., cambio de estado del SO)?
- ¿Cuándo invocar el detector? Hoy lo hago antes de cada tool call. ¿Conviene también end-of-turn?

### 4. Error classifier RETRY/SKIP/REPLAN/ABORT

Mark-XXXIX tiene un mini-LLM call que clasifica errores en 4 categorías. Carter tiene reflection booleana.

- ¿Vale la pena el 1 LLM call extra (300-500ms con qwen3:4b) en error path?
- Schema sugerido y implementación.
- ¿Cómo evitar que el classifier mismo cree loops?

### 5. Tool retrieval semántico (top-K)

47 tools en el catálogo. ¿El modelo se confunde?

- ¿Vale la pena retrieval semántico para inyectar solo top-K relevantes? (Inv #11 OS-Copilot pattern)
- Tradeoff: más tokens prompt vs LLM perdido en catálogo grande.
- ¿Hay benchmark de qwen3 con catálogos de 30 vs 50 vs 100 tools?

### 6. Compaction strategies

Hoy hago compaction al 70% del num_ctx con resumen LLM.

- ¿Qué estrategias existen además de "rolling summary"? Hierarchical summary, semantic compression, etc.
- ¿Cuál es óptima para qwen3:4b?
- ¿Dónde está el sweet spot de cuándo compactar (50%, 70%, 90%)?

### 7. Streaming + early termination

Hoy Carter espera el reply completo. Para tools, esto es necesario.

- ¿Hay forma de detectar "el modelo va a emitir tool_call" en streaming y cortarlo temprano?
- Pre-emisión de stop tokens custom.

### 8. Multi-tool batching

Si el modelo emite varios tool_calls en un turn (ej: app_open + window_manage), Carter los ejecuta secuencial. ¿Conviene paralelo cuando son independientes?

- ¿Cómo detectar dependency entre tool_calls?
- Riesgos de paralelismo (race conditions sobre filesystem, ventanas).

### 9. Verifier orchestration

Hoy cada tool tiene verifier inline. Para multi-step:
- ¿Conviene un verifier orchestrator que ve la cadena completa y declara success/partial/fail global?
- ¿Cómo evitar que un fail temprano aborte una cadena que aún puede completarse?

### 10. Implementación práctica

Dame **código Python concreto** para:

1. Detector heurístico de "esto es misión multi-step" (sin keyword list).
2. Planner light que se invoca solo cuando se detecta misión.
3. Skill library SQLite + retrieval cosine.
4. Error classifier mini-LLM call.
5. Verifier orchestrator que declare PARTIAL/COMPLETED honestos.

### 11. ContextoCarter.md compliance

Cualquier solución debe respetar:
- Local + privado (no cloud)
- Latencia Alexa-tier (3-8s simple, NO romper para casos simples)
- Honest by construction
- NO keyword lists per idioma
- NO per-app hardcodes
- Universal multilingüe

### 12. ROI esperado por categoría

Para cada propuesta, estimar **fails reales que cerraría**:
- C14 misiones (5 fails actuales)
- C13 GUI (3 fails)
- C11 terminal (3 fails)
- C07 apps (3 fails)
- Otros (7 fails distribuidos)

---

## Formato esperado

1. **TL;DR** (top 5 cambios arquitecturales con esfuerzo/impacto/ROI específico).
2. **Código snippets** Python concretos.
3. **Tabla** comparativa de approaches (planner vs ReAct vs híbrido).
4. **Roadmap**: qué cambiar primero, qué medir.
5. **Caveats**: cosas que la documentación afirma pero no se sostienen, dependencia de hardware.

**Restricciones**: Local + privado, no cloud, no migrar Ollama→vLLM, no cambiar modelo.

Reporte detallado pero conciso (~2000-3500 palabras). Foco en accionabilidad inmediata para los 21 fails residuales.
