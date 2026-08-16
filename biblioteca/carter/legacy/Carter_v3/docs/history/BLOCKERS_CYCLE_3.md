# BLOCKERS_CYCLE_3

Estado objetivo: `LIVE_TEXT_CORE_READY`

Veredicto actual: `LIVE_TEXT_CORE_NOT_READY`

Solo se listan los blockers que siguen apareciendo vivos en el smoke de Cycle 3.

---

## 1) Pending filesystem intent no se completa para `lee <path> + Sí`
- Prompt: `lee C:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI\ContextoCarter.md que es?`
- Respuesta exacta: `Intenté 1 acción(es), pero no pude verificar el resultado. Detalle: read-only or no external readback required`
- Prompt 2: `Sí`
- Respuesta exacta: `Sí. ¿Cómo estás?`
- Comportamiento esperado: si el primer intento requiere confirmación/permiso para continuar (o la verificación no permite mostrar el contenido), `Sí` debe continuar el flujo pendiente de lectura (o re-encaminar a `NEEDS_USER`/`NEEDS_PERMISSION` con siguiente paso honesto).
- Causa probable: el runtime no mantiene un objeto de “pending intent” universal para este tipo de flujo de lectura cuando el verificador/dispatcher no habilita el readback esperado; la respuesta queda como chat/trivial y el siguiente `Sí` no dispara la continuación estructural.
- Por qué no es hardcode: debe ser un contrato universal (estado de intención pendiente + evidencia de tool), no una respuesta escrita para un caso del log.
- Fix universal propuesto (próxima iteración): introducir `pending_intent` estructural en `SessionState` para flujos donde una tool ejecutó parcialmente o el verificador indica que falta readback/confirmación; el siguiente turno “sí/ok” debe resolver el objeto pendiente (sin routing por palabras).
- Archivos (probables): `src/carter_v3/session_state.py`, `src/carter_v3/agent.py` (pre-LLM pending_intent + ejecución condicionada), y potencialmente `src/carter_v3/response_composer.py` (para crear next-step consistente).
- Tests:
  - `tests/test_live_regressions_from_user_log.py` (extender `test_windows_path_plus_si_followup_works` para validar que existe el flujo pendiente cuando el readback no se pudo verificar).
- Riesgo: medio (impacta el contrato de continuación multi-turn; requiere aserciones estructurales y no solo de texto).

---

## 2) “Alarmas” sin tool real: `pon una alarma ...` no refleja NEEDS_USER/estado honesto consistente
- Prompt: `pon una alarma para hoy a las 9 am`
- Respuesta exacta: `Lo siento, no puedo establecer alarmas directamente. Te sugiero que uses la aplicación de Alarmas y Reloj en Windows o un servicio similar.`
- Comportamiento esperado: si Carter no tiene una tool de alarmas en el catálogo, debe evitar cualquier claim y también preferir terminar en `NEEDS_USER`/bloqueo honesto (o un estado terminal que obligue a siguiente paso) en vez de dejar la misión como `TRIVIAL` si el usuario espera acción.
- Causa probable: cuando la tool no existe/ no se ejecuta, la misión cae en “chat” en lugar de “capability missing” con next-step estructural basado en tool catalog.
- Por qué no es hardcode: la solución debe derivar de presencia/ausencia de herramientas (TOOL_CATALOG) y de evidencia verificada, no del texto “alarma”.
- Fix universal propuesto (próxima iteración): en el pipeline de misión/guard, cuando no hay tool de la capacidad solicitada y no hubo tool call ejecutada, convertir a `NEEDS_USER` con next-step honesto basado en catálogo.
- Archivos (probables): `src/carter_v3/agent.py` o `src/carter_v3/response_composer.py` (normalización de estado cuando no hay tool ejecutada para capacidad solicitada).
- Tests:
  - `tests/test_runtime_no_fake_success_live_cases.py` (añadir cobertura de “missing capability -> NEEDS_USER, no TRIVIAL genérico”).
- Riesgo: medio (manejo de states y no relajar honestidad).

