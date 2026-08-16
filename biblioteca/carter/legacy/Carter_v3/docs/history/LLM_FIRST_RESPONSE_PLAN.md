# LLM_FIRST_RESPONSE_PLAN

Fecha: 2026-05-05

## 1. Rutas que deben llamar LLM siempre

- `trivial_lowinfo`: saludos, `ok`, `gracias`, mono-token bajo en información. No tools; final por `generate_chat_reply(...)`.
- `ambiguous_short`: `qué?`, `?`, texto corto ambiguo. No tools; final por `generate_chat_reply(...)`.
- identity/persona: pregunta normal sin tools; la llamada LLM existente con `build_messages(...)` redacta la respuesta.
- architecture/capabilities: llamada LLM sin tools con persona + `TOOL_CATALOG` completo.
- knowledge/simple chat: llamada LLM sin tools; final directo del LLM.
- memory reply: tool `memory_save`/`memory_recall` produce facts reales; final por `generate_result_reply(...)`.
- capability reply: si no hay tool/target seguro, deterministic decide `needs_user`; final por `generate_result_reply(...)`.
- architecture reply: LLM recibe stack real (`text core`, tools catalog, policy, verifier, memory, local model adapter).
- tool result reply: tools/verifier/status se calculan estructuralmente; final por `generate_result_reply(...)`.
- policy block: policy decide bloqueo; LLM redacta explicación segura desde facts bloqueados.
- unsupported capability/environment: runtime decide ausencia; LLM verbaliza sin inventar acción.

## 2. Capas que siguen determinísticas

- `PolicyEngine` y clasificación de riesgo.
- `VerificationManager` y `compute_mission_status(...)`.
- Tool dispatch y selección de tools permitidas.
- Evidence collection (`ToolResult`, `VerifiedOutcome`, `policy_blocks`, `engine_errors`).
- `response_composer.py` como factual scaffold interno/emergency fallback.
- `hardcode_guard.py` y reply guards.
- Ruta estructural `no tools` para trivial/direct chat.
- Guards anti fake-success, placeholder, low-info, memory/history/active-app contamination.

## 3. Fake success

- El LLM verbalizer recibe `mission_status`, `termination_reason`, `tool_calls`, `tool_results`, `verifier_outcomes`, `policy_blocks` y `engine_errors` como locked facts.
- El LLM no decide status, no despacha tools, no modifica memoria y no puede ocultar evidencia.
- Si `mission_status` es `unverified`, `needs_user`, `failed` o `partial`, el prompt prohíbe claims de completion global.
- Después de la verbalización, `run_reply_guards(...)` sigue bloqueando fake success.
- Si el LLM contradice evidence, el emergency fallback estructural conserva honestidad aunque no sea la ruta normal deseada.

## 4. Latencia

- Trivial/direct chat sigue sin tools, sin UIA, sin screenshots, sin resolver apps y sin contexto largo.
- `generate_chat_reply(...)` usa `max_short=True` y prompt mínimo con snapshots compactos.
- Tool-result verbalization usa el mismo adapter ya precargado/keep-alive; no carga modelos extra.
- `TOOL_CATALOG` snapshot se compacta y limita.
- `prior_turns` se limita a los últimos turnos útiles.

## 5. Tests

- Mock LLM dinámico que cambia salida para probar que no hay respuesta fija.
- Contador de llamadas (`verbalizer_calls`, `planning_calls`) para probar no-tools + LLM.
- Tests de identity/architecture/capability verifican que el prompt contiene contexto Carter y capabilities reales.
- Memory recall prueba facts reales + LLM verbalizer.
- Tool result unverified prueba que el LLM fue llamado pero no puede dejar un claim `Completado` sin verifier.
- `hardcode_guard.py` detecta literales triviales canned exactos.
- Manual-equivalent smoke prueba repetición de `Hola`, typo, identidad, arquitectura, filesystem, memoria, pycaw missing y alarm missing.

## 6. Emergency fallback

Existe fallback determinístico si el LLM devuelve vacío, placeholder o una respuesta de prueba tipo `OK.`. Ese fallback queda documentado como safety/emergency fallback para preservar evidencia y no fake-success; no es la ruta normal de chat.
