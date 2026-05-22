# Tradeoffs para decisión de RED — sprint de latencia 2026-05-22

## T1 — Streaming del reply a TTS vs los guards post-generación (ARQUITECTURA vs LATENCIA percibida)

**Contexto:** la palanca #1 de latencia PERCIBIDA es streamear el reply final al
usuario token-a-token (TTS empieza a hablar en ~1s en vez de esperar el reply
completo). La infra (`llm_client.chat_stream`) existe y la dejé funcional en
router mode (commit 3fc94f8, TTFT 130ms medido). PERO:

**El conflicto:** el reply final pasa por guards que REESCRIBEN el texto DESPUÉS
de generarlo:
- `guard_grounded_action_claim`: si el modelo dice "abrí X / busqué Y" SIN que
  corriera la tool, reemplaza el claim por un fallback honesto.
- `guard_promise_without_action`: idem para promesas ("voy a abrir X") sin acción.
- `_guard_unverified_final`, `_guard_phrase_confirm`, `_strip_trailing_footers`.

Si streameo los tokens al TTS en vivo y LUEGO un guard reescribe, el usuario YA
escuchó la versión sin corregir — se rompe el invariante "el agente no miente
sobre su estado" (no fake success). Para turnos puramente informativos los guards
son pass-through, pero NO puedo garantizar que un answer no contenga "abrí" en
una explicación y dispare el grounding guard.

**Opciones:**
- **(A) No streamear a TTS (status quo).** Reply completo → guards → TTS. Latencia
  percibida = total. Seguro. Es lo que hay hoy.
- **(B) Streamear a TTS solo en turnos sin tools y sin claims de acción.** Requiere
  un pre-check barato (¿el texto contiene morfología de acción pasada/futura?)
  antes de decidir streamear. Si el pre-check da "limpio", streamear; si no,
  caer a (A). Riesgo: el pre-check tiene que ser tan bueno como el guard, o
  escapa un claim. Latencia percibida ~1s en la mayoría de los turnos.
- **(C) Streamear SOLO a la UI (texto en pantalla), NO al TTS.** El texto aparece
  incremental (percibida ~1s visual), pero la voz espera los guards. Rompe nada
  (la UI muestra texto provisional, marcado como "escribiendo"), pero la voz
  sigue en latencia total. Bajo riesgo, gana percepción visual no auditiva.

**Recomendación:** **(C) para la UI ya** (sin riesgo) + **(B) para TTS** si RED
acepta el pre-check de claims como suficiente (es el mismo criterio que el guard
usa, solo adelantado). NO implementé (B) unilateralmente porque adelantar el
criterio del guard es un cambio de superficie de seguridad que merece tu visto
bueno. (C) tampoco lo cablé porque toca el contrato del `progress`/UI y quería tu
decisión de si la UI debe mostrar texto provisional.

**Costo de no hacer nada:** la latencia percibida sigue = total. Con Fase 2/3 el
total baja a <5s en casi todo, así que la percibida ya mejora sin streaming.
Streaming llevaría la percibida a ~1s, que es el objetivo declarado — vale la
pena, pero necesita tu decisión sobre el balance seguridad/percepción.

**Pregunta de 1 línea:** ¿implemento (C) UI-streaming ya (sin riesgo) y (B)
TTS-streaming con pre-check de action-claims, o preferís que la voz espere
siempre a los guards (status quo, percibida=total pero ya <5s con Fase 2/3)?
