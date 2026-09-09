# C03 — memoria: causa localizada, conducta todavía pendiente

Entrada humana99 de TRANSCRIPT282: pide guardar el nombre, todavía no aporta el
valor y quiere que BAXY lo recuerde cuando vuelva a preguntarlo. Sigue fallando en
producto325. No se ha cambiado esta ruta en324/326.

Diagnóstico sin modificar fuente: con memory.status/save/recall/forget disponibles,
resolve_explicit_effects devuelve None; effect_request_is_authoritative=True;
known_unsupported_effect_request=False; _closed_unsupported_request=False;
_explicit_stable_no_effect_turn_decision=None. unresolved_compound_contract devuelve
CompoundEffectContract(minimum_effects=1, required_clause_sequences=()).

Traza de líneas localiza la decisión en effect_intent.py:13384, rama deferred_effect.
_has_unsupported_deferred_effect interpreta «cuando te lo pregunte» como un efecto
que hay que programar. __main__.py:5792–5825 transforma el contrato sin resolver en
unsupported. Esto mezcla recordar un dato para una futura pregunta con ejecutar
una acción automáticamente al ocurrir un evento.

Precisar el orden: sí hubo una llamada nativa en post1, pero sólo con cuatro
herramientas ajenas a memoria (wifi/game/procesos). La redacción post2 ya recibió la
instrucción explícita de negar el resultado. No atribuir esa negativa únicamente
al modelo ni decir que nunca se llamó al selector. Los posteos325 y322 coinciden
en esta parte. No se debe corregir sólo el texto de la negativa.

La frontera privada también requiere atención: NaturalMemoryRequestParser.Classify
no reconoce este pedido de valor pendiente; ClarifySave existe, pero VM:763 sólo
publica la aclaración y sale. MemoryTurnSession gestiona confirmaciones y operaciones
por reconciliar, no un valor aún no aportado. VM:2103 rechaza puentear memory.* desde
una selección del modelo sin el canal privado. Conservar autenticación, confirmación
de datos sensibles y separación respecto a notas. No añadir el literal humano al
switch TryParseAuditedLiteral.

Herencia consultada: biblioteca/carter/legacy/Carter_v2/LLM_CONTEXT_MEMORY_REPORT.md,
líneas12–40: identidad con procedencia; no usar frases previas del asistente como
identidad confirmada. biblioteca/gemma4-agent/codigo-docs/prompts/tool_rules/memory.lean.md,
líneas1–4: guardar sólo a petición explícita; memoria persistente no equivale a notas
ni al historial de sesión. Evidencia histórica, no permiso para restaurar sus APIs.

Siguiente investigación: resolver admisión y continuidad del valor solicitado en
el canal privado existente, contrastando el primer cambio de clasificación con el
modelo local y los mismos seis turnos. No introducir otra instrucción al compositor
para que diga que recuerda sin que haya persistencia verificada.
