# LLM Context & Memory Audit — Carter v2

Date: 2026-05-01
Scope: identity contamination, repetition, active-app leakage, placeholder
output, latency, style preference contamination.

## 1. Veredicto brutal

Carter no falla por el LLM. Falla por lo que el código le da al LLM.

| Síntoma | Causa real | No es |
|---|---|---|
| "soy Carter, asistente de Como" | `memory.get_user_name()` se inyecta en el system prompt sin validación de confianza ni resolución de conflictos contra OS username | bug del LLM |
| respuestas casi idénticas a "hola"/"dime hola"/"Que?" | `_format_prior_turn_context` mete las últimas 3 turnos verbatim como bloque "[Recent session context]"; en input trivial el modelo hace continuation del último reply | sampling |
| "a" → habla de mission.py | `_active_app_context_line()` se inyecta como mensaje system para CADA turno, sin gating por triviality ni intent signal | bug de active app |
| `////////////////////////////////////////` 140-154 s | output del modelo dominado por un solo símbolo no-alfanumérico; `_looks_like_stream_noise_line` solo lo filtra en streaming si la línea entera es ruido y ≥12 chars; en non-streaming el reply pasa intacto. Latencia: el modelo gasta el budget completo de tokens generando barras hasta `num_predict`/timeout | placeholder fijo |
| "Que pasa chaval" contamina | `save_fact("user", "style_preference", ...)` cae en la tabla `facts` igual que cualquier otro hecho; `_format_memory_facts` lo inyecta verbatim al system prompt en cada turno; sin scope ni TTL | preferencia legítima mal manejada |

Diseño peligroso real:
- la tabla `facts` no tiene `confidence` ni `confirmed` ni `scope` ni `category`.
- `_safe_memory_user_name` solo valida shape (≤3 tokens, alfa) → "Como"/"Red"/"Yo" pasan trivialmente.
- `_active_app_context_line` se inyecta dos veces (una en `extras`, otra como mensaje system separado) → ver [agent.py:992-996](src/carter_v2/turn/agent.py#L992-L996).
- timeout de backend = 180 s para todos los casos, sin recorte para inputs triviales.
- el detector de "low information" actual ([agent.py:541](src/carter_v2/turn/agent.py#L541-L551)) sólo mira reply ≤12 chars o "done"; no detecta `////////////` (40 chars).

## 2. Flujo actual de contexto

```
user_text
  → BrainRouter.decide()                      (structural, sin vocab)
  → AgentEngine.run()
      ├─ select_tools_for_turn(user_text)
      ├─ active_app_line = _active_app_context_line(session_state)   [SIN gate]
      ├─ active_app = _active_app_followup_context(...)              [con gate]
      ├─ user_name = memory.get_user_name()                           [SIN re-validate vs OS]
      ├─ base_system = _build_system_prompt(user_name, memory, ...)   [user_ref priority: param>memory>OS]
      ├─ extras = [system_context, "Available tool schemas: N", skills, lessons, prior_ctx]
      ├─ messages = [system + extras]
      ├─ if active_app_line: messages.append({"role":"system","content":active_app_line})  [SIEMPRE]
      ├─ messages.append({"role":"user","content":user_text})
      └─ for iteration in range(MAX_TOOL_ITERATIONS=8):
            response = backend.chat_with_tools(...)   timeout=180s
            ...
```

Lo que se inyecta SIEMPRE (problemático):
- `_active_app_context_line` como segundo mensaje system (ver [agent.py:993-995](src/carter_v2/turn/agent.py#L993-L995)).
- `_format_memory_facts(memory, user_text)` como bloque dentro del system prompt ([_system_prompt.py:114](src/carter_v2/turn/_system_prompt.py#L114)).
- `_format_prior_turn_context(prior_turns, max=3)` como extra ([agent.py:982-986](src/carter_v2/turn/agent.py#L982-L986)).
- `user_ref` resuelto en [_system_prompt.py:305-309](src/carter_v2/turn/_system_prompt.py#L305-L309) con prioridad `param > memory > OS > "the user"`.

## 3. Diagnóstico de user_ref

Orden actual: `user_name (param) > _safe_memory_user_name(memory) > settings.username/Path.home().name > "the user"`.
- Memory siempre gana al OS si tiene cualquier valor que pase `_is_plausible_user_name` (4 chars alfa).
- `set_user_name` valida shape pero NO semántica ni confianza → "Como" se acepta.
- No hay detección de conflicto: si la tabla tiene `user.name = Como, Red, Yo` (3 filas), `get_user_name` devuelve la más reciente sin chequear conflicto.
- No hay flag `confirmed`. La columna `source` en `facts` es libre; el código sólo filtra por `source='user_stated'`.

Fix universal (sin listas de nombres):
- introducir `resolve_user_ref(config, memory, os_username) -> UserRefDecision` con campos `value, source, confidence, ignored_memory_values, conflict_detected, reason`.
- regla: memoria gana sólo si hay un único valor `user.name` con `source='user_stated_confirmed'` (nuevo enum) **y** ese valor coincide con el OS username **o** no entra en conflicto con él.
- de lo contrario, OS username gana, y los valores ignorados se loguean en trace `suspicious_user_ref_ignored`.

## 4. Diagnóstico de historial repetido

`_format_prior_turn_context` ([agent.py:303-331](src/carter_v2/turn/agent.py#L303-L331)) emite verbatim los últimos 3 turnos como "U: …\nCarter: …" dentro de un único bloque etiquetado "Recent session context - verified trace". El modelo (Qwen3-Q4) lo lee como ejemplo de su propio estilo y lo reproduce.

No hay:
- deduplicación entre turnos (si las últimas 2 respuestas son casi idénticas, se inyectan ambas).
- supresión para input trivial (longitud ≤2 chars).
- normalización (case-fold + collapse espacios) para detectar duplicación.

Fix: dedupe por similitud estructural (longitud + token-set Jaccard ≥ 0.85), suprimir prior_ctx entero cuando `_is_trivially_short_input(user_text)`.

## 5. Diagnóstico de active app context

`_active_app_context_line(session_state)` se llama dos veces (líneas 887 y 992 de agent.py) y **se inyecta siempre como mensaje system** sin gating. La rama "follow-up" (`_active_app_followup_context`) sí gate-a por `_looks_like_short_followup`, pero esa rama solo afecta el catálogo de tools, no la inyección del mensaje system.

Resultado: input "a" recibe el system message "Currently active: VS Code window 'mission.py'" → modelo lo usa como tema.

Fix sin vocabulario:
- gating estructural: `should_inject_active_app_context(user_text, mission_active, has_followup_context)` returns False cuando:
  1. `_is_trivially_short_input(user_text)` (longitud/tokens),
  2. no hay misión activa,
  3. no hay `_active_app_followup_context` confiable.
- Trace: `active_app_context_injected`, `active_app_context_reason`, `active_app_context_suppressed_reason`, `active_app_chars`.

## 6. Diagnóstico del placeholder `////////////////////////////////////////`

Buscado en backends.py, _text.py, llama_backend.py, agent.py: no existe como string literal en ninguna parte. Es output del modelo.

Causas combinadas:
1. system prompt contaminado (memory junk + active_app + prior_ctx repetido) confunde al planner.
2. el modelo entra en "degenerate output" generando un solo char hasta agotar `num_predict` (default 4096+ tokens en Ollama).
3. el sanitizer `_strip_thinking_text` filtra líneas ruido sólo si `len ≥ 12` y la línea **entera** matchea `[\/\\|_\-]+`. En una línea de 40 caracteres puros `/`, sí matchea pero el reply puede tener whitespace alrededor que rompe `re.fullmatch`.
4. en non-streaming, el modelo devuelve `"////////..."` y el reply pasa por `_strip_thinking_text` → si aplica, se queda vacío → fallback `"(no response from LLM)"`. Pero el usuario ve barras → indicador de que streaming sí entrega y no se filtra.

Fix universal:
- nuevo `is_low_information_output(text)` que detecta cuando >70% de los caracteres no-whitespace pertenecen al mismo char (o cuando la diversidad alfa es < 3 chars únicos).
- aplicarlo después de `_strip_thinking_text` en el reply final.
- si dispara, hacer **un** retry con prompt mínimo y `think=False` y prior_ctx vacío. Si persiste, devolver "I could not produce a useful reply for that input." (estructural).
- trace: `low_information_detected`, `low_information_reason`, `placeholder_detected`, `raw_reply_excerpt`.

## 7. Diagnóstico de latencia 140–154 s

Backend timeout = 180 s ([backends.py:75](src/carter_v2/turn/backends.py#L75)). Para Qwen3-Q4 generando 4096 tokens de degenerate output, completa entre 120–170 s. Sin abort temprano.

Stages plausibles para "Nada":
- build_prompt_ms: 5–20 ms.
- llm_call_ms: 140000+ ms (modelo en degenerate loop).
- tool_exec_ms: 0.

Fix:
- timeout dinámico: para inputs triviales (`_is_trivially_short_input`), `effective_timeout = min(self._timeout, 30 s)`.
- detector de no-progress: si la primera iteración devuelve `is_low_information_output`, no hacer más iteraciones (exit con honest reply).
- trace: `timeout_hit`, `no_progress_loop_detected`, `termination_reason`.

## 8. Diagnóstico de style preference

`save_fact("user", "style_preference", "Que pasa chaval", source)` cae en `facts`. Luego `_format_memory_facts` lo lista junto a otros `KNOWN FACTS`, lo que hace que el modelo lo adopte como persona. El reply corto (`Que pasa chaval`) es porque es tanto la frase del estilo como el contenido más relevante para el modelo.

Fix sin hardcode:
- categoría estructural en attribute: `style_preference` → no se inyecta nunca como hecho durable salvo que tenga `source='user_stated_confirmed'`.
- por defecto va a scope=session (no persistente) **a menos** que se confirme.
- si se inyecta, va como sección separada "STYLE PREFERENCE (apply if it does not hide content)" con clamp.

## 9. Hallazgos

| ID | Archivo | Símbolo | Problema | Severidad | Fix |
|---|---|---|---|---|---|
| F-USR-1 | _system_prompt.py:305-309 | user_ref priority | memory > OS sin chequeo de confianza | CRITICO | resolve_user_ref con confidence + conflict detection |
| F-USR-2 | memory.py:515-540 | set_user_name | shape-only validation, sin confianza | CRITICO | añadir source='user_stated_confirmed' enum y rechazar memoria no confirmada en lectura para identity |
| F-MEM-1 | memory.py:328 | save_fact | sin confidence/scope/TTL | ALTO | añadir parámetros opcionales `confidence`, `scope` con defaults seguros (back-compat) |
| F-AAC-1 | agent.py:992-996 | active_app injection | siempre inyecta sin gating | CRITICO | gating estructural por triviality + mission + followup |
| F-AAC-2 | agent.py:887, 992 | active_app_line dual call | duplicado | MEDIO | calcular una vez |
| F-PCT-1 | agent.py:303-331 | _format_prior_turn_context | sin dedup, sin trivial gate | ALTO | dedup Jaccard + suprimir si trivial |
| F-LOW-1 | agent.py:541-551, _text.py:40 | low-info detector | cubre ≤12 chars y `[\/\\|_\-]+` 12+ pero no captura barras dominantes en reply final | CRITICO | nuevo `is_low_information_output` por diversidad |
| F-LAT-1 | backends.py:75 | timeout=180 | sin recorte para input trivial | ALTO | timeout dinámico + early abort en degenerate output |
| F-STY-1 | _system_prompt.py:114-150 | style_preference inyectado | contamina como hecho durable | ALTO | filtrar `attribute='style_preference'` salvo confirmación |

## 10. Plan de reparación (L1-L12)

L1 user_ref robusto · L2 memory write validation + cleanup script · L3 active app gating · L4 prior turn dedup · L5 prompt hygiene + trace · L6 low-info guard · L7 latency guard · L8 style preference scope · L9 LLM autonomy doc · L10 tests · L11 runtime probe · L12 final report.

Implementación a continuación.
