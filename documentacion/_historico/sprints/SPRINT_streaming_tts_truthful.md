# Sprint — Streaming token→TTS (preservando "el agente no miente")

**Fecha:** 2026-05-28 · **Item:** punto 2 #1 del backlog (mayor ROI de latencia
percibida). Opt-in `GEMMA4_STREAM_TTS` (default OFF hasta validar en vivo).

## Problema

Hoy la voz espera el reply COMPLETO + el synth COMPLETO antes de hablar. Para
turnos de ACCIÓN (confirmación post-tool) eso es 5-6s hasta el primer audio. La
infra `LLMClient.chat_stream` (SSE, TTFT 130ms medido) existe pero `agent.py`
nunca la adoptó. El `StreamingTTS.feed_text` ya chunkea por oración + tiene
fast-path de cláusula inicial (TTFA ~0.4s).

## El blocker que frenó esto antes (tradeoffs.md T1, 2026-05-22)

Streamear tokens al TTS choca con los guards post-generación que REESCRIBEN el
texto: si hablo y después un guard corrige, el usuario ya escuchó la versión sin
corregir → se rompe "el agente no miente sobre su estado". El sprint anterior
NO lo bypasseó (correcto) y lo dejó a decisión del usuario. Su única opción era
un pre-check MÁS DÉBIL que el guard (aproximar) — riesgoso.

## La solución sólida (no un atajo): verdad por construcción

Leyendo el código real de los guards (`agent_guards.py`, `grounding_gate.py`):

- `detect_action_claim_without_evidence` → `should_replace=False` **apenas
  `tool_events` no está vacío** (grounding_gate.py:206).
- `guard_promise_without_action` → `if events: return content` (agent_guards.py:253).

⇒ **Los DOS guards que REEMPLAZAN el texto son pass-through siempre que corrió una
tool.** Los demás solo AGREGAN al final (`unverified_final`, `plan_status`) o
ANTEPONEN (`phrase_confirm`, solo rutinas).

**Regla de elegibilidad para streamear (todas deben cumplirse):**
1. `_is_summary_pass` — es la pasada de confirmación post-tool (`len(events)>0` ∧
   modo `fast_action`/`quick_action` ∧ sin imagen). `events>0` ⇒ guards de
   reemplazo NO pueden disparar. **Es justo el camino lento (5-6s).**
2. `not self._phrase_fires` — sin rutina (evita el guard que antepone).
3. Hay un `tts_sink` (modo voz) y `GEMMA4_STREAM_TTS` está ON.

En ese subconjunto, el thinking ya está OFF (`_think_now = ... and len(events)==0`)
→ el stream es prosa limpia (sin `<think>`). Se sanitiza incremental igual
(`sanitize_text` por prefijo acumulado, con ABORT defensivo si alguna vez
encoge texto ya hablado).

**Garantía:** lo que se habla = prosa final con guards, ± una nota-hedge/footer
que se dice AL FINAL (aditiva, honesta). Para el éxito limpio (caso común) NO hay
footer ni nota → lo hablado == el reply final, idéntico. Nunca se pronuncia algo
que después se retracta. **Misma veracidad que hoy, dicho antes.**

## Diseño

- `run_text`/`run_content`: nuevo kwarg `tts_sink: Callable[[str],None]|None`.
  Se stashea en `self._active_tts_sink` durante el turno (limpia en `finally`).
- `_execute_turn` (chat 1948): si elegible → `_chat_summary_streaming(...)` que
  itera `chat_stream`, alimenta prosa sanitizada-incremental al sink, acumula, y
  devuelve un `resp` con la misma forma que `chat()` (el resto del pipeline no
  cambia). Cualquier excepción → fallback a `chat()` (veraz, solo más lento).
- `_finalize_turn` (antes del return 3281): si se streameó, alimenta el TAIL
  (`assistant_content` final − prosa ya hablada) al sink. `startswith`-guard:
  si diverge (inalcanzable con `events>0`), loguea y NO habla nada extra (jamás
  double-speak). Devuelve `AgentReply(tts_streamed=...)`.
- `agent_runner`: pasa `tts_sink=VOICE.feed_tts`; si `reply.tts_streamed` NO
  re-alimenta `content` (ya se streameó), solo `flush_tts()`.
- Fuera de scope v1 (ya rápidos / más complejos): turnos sin-tool (info, <2.2s),
  describe-pass (visión), rutinas. Documentado.

## Gate (medir, no celebrar)

1. **TTFA (time-to-first-audio)** en una acción ("abre la calculadora", "sube el
   volumen") con `GEMMA4_STREAM_TTS=1` vs OFF. Criterio: TTFA baja claramente
   (objetivo <1s vs ~varios s). Medido en vivo con sink que estampa t del 1er feed.
2. **Veracidad (test estructural):** para `events>0`, la prosa streameada es
   PREFIJO del `assistant_content` final con guards (nunca se habló algo
   reemplazado). Test unit con sink fake + chat_stream fake.
3. **No-regresión:** gate OFF ⇒ usa `chat()`, comportamiento idéntico (tests
   existentes verdes). Texto/GUI (sin sink) sin cambio.
4. **En vivo:** correr 3-4 acciones reales, confirmar reply hablado correcto y
   SIN contradicción (lo dicho coincide con lo hecho).

## Item 2 — streaming de turnos INFO (2026-05-29)

Extendido a turnos INFO (`fast_info`, events==0): el reply se genera en UNA pasada
(sin la espera pass-1+execute), así que el win es REAL y grande. Seguridad: en
turnos sin-tool los guards de claim PUEDEN disparar -> `_chat_streaming(guard_check=True)`
corre los detectores REALES (`detect_action_claim_without_evidence` + `reply_claims_action`)
por-incremento y ABORTA antes de hablar algo que un guard reemplazaría. Además
fuerza `tools=None` en la pasada streameada (prosa pura desde el conocimiento del
modelo). `chat_stream` extendido con `greedy`/`sampling` (paridad con `chat()`).

**Medido EN VIVO (4 preguntas):** streameó 4/4, **first-audio 0.14-0.19s** vs reply
base 1.2-3.5s -> **win 1.0-3.3s** (¡el win real del streaming, vs ~0 en acciones!).
PERO veracidad 2/4:
- `qué es Python`, `por qué el cielo es azul` (events=0): **voiced == final, TRUTH OK**, win 1.0-1.3s. ✅
- `qué es la fotosíntesis`, `capital de Francia` (events=1): **TRUTH FAIL** — el agente
  corre un tool DESPUÉS de la prosa streameada (forced-retry / red determinista),
  produciendo un final post-tool DISTINTO que NO se habla (tts_streamed=True hace que
  el runner lo saltee). Lo hablado es CORRECTO (no es mentira), pero ≠ el "final
  verificado" del agente. En preguntas de conocimiento atemporal el tool post-prosa
  es probablemente ESPURIO (el modelo ya sabe) -> streamear lo saltea y responde más
  rápido; pero NO se garantiza que siempre sea espurio.

### Root-cause del tool-post-prosa (investigado 2026-05-29, `scripts/_diag_info_tool.py`)

NO es el forced-retry (que YA se saltea en fast_info por `_info_answered`). Es el
**MODELO**: para preguntas de BÚSQUEDA-DE-DATO ("qué es X", "cuál es X") emite
`web(action="search", query=...)` como TEXTO PLANO → el **RESCUE parser** lo
ejecuta como tool `web` real → turno de 2 pasadas (web + summary). Para preguntas
EXPLICATIVAS ("explicame X", "por qué X") responde en prosa directa (events=0).
El router mete `web` en el subset (kw_matches ['web','knowledge']) para ambas.

El web en una pregunta de conocimiento atemporal es probablemente ESPURIO (el
modelo ya sabe), pero es INDISTINGUIBLE de un web genuino de info-actual sin tocar
el router → suprimirlo arriesga respuestas obsoletas en preguntas de info-actual
(riesgo de "miente"). Speak-both es veraz pero redundante.

### Fix aplicado: demote-on-tool (veraz, sin bypass)

`_chat_streaming(guard_check=True)` marca `_tts_info_stream`. En `_finalize_turn`,
si se streameó un pase INFO **y** corrió un tool (events>0) → `tts_streamed=False`
→ el runner habla el FINAL VERIFICADO (post-tool), nunca saltea verificación.
Pasadas de info prosa-pura (events==0) siguen streameadas y limpias.

**Medido EN VIVO (post-fix): streameó 2/4, veracidad OK (0 violaciones).**
- explicativas (Python, cielo): streamean limpio, win ~1.0-1.3s, voiced==final. ✅
- búsqueda-de-dato (fotosíntesis, capital): demote → habla el final verificado. ✅
  RESIDUAL: redundancia (se oye el draft de conocimiento + el summary verificado).

**Decisión: GEMMA4_STREAM_TTS sigue default OFF.** Es VERAZ (0 violaciones) pero la
redundancia en preguntas de búsqueda-de-dato no es 100% limpia. Limpieza total =
que el router NO meta `web` en preguntas de conocimiento atemporal (cambio de router,
riesgoso, separado). Tests: `test_stream_tts.py` 15/15. Infra dormant lista.

## Estado

- [x] Implementación (gated `GEMMA4_STREAM_TTS`, default OFF). 8 edits en
  `agent.py` (+`_chat_summary_streaming`/`_feed_tts_tail`/`_stream_tts_enabled`,
  AgentReply.tts_streamed, run_text/run_content sink) + `agent_runner.py`.
- [x] Tests unit (`tests/test_stream_tts.py`, 11/11) + 38 de regresión verdes.
- [x] Validación EN VIVO (server FA-off vram4, `scripts/_validate_stream_tts.py`).

## Resultado medido (2026-05-28) — HONESTO

**Veracidad: OK, 0 violaciones (3/3 summary-pass).** El stream alimenta prosa
sanitizada incremental; en el caso de FALLO (minimizá sin ventana) la prosa se
streamea y el footer `[1 no confirmada(s)]` se dice como TAIL después de los
guards → lo hablado reconstruye exactamente el reply final. "No miente" preservado
por construcción. ✅

**Latencia: el win NO se materializa para turnos de ACCIÓN (~0).** Medido (sink
falso = TTFA de generación):

| acción | base reply listo | 1er audio (stream) | win |
|--------|------------------|--------------------|-----|
| calculadora | 4.22s | 6.11s | **0.00s** |
| bloc de notas | 7.55s | 7.50s | +0.05s |
| minimizar | 4.26s | 3.88s | +0.39s |

Win promedio ~0, DENTRO de la varianza run-a-run (±2s). **Causa raíz (diagnóstico,
CLAUDE.md #4):** el costo dominante de una acción es **pass-1 (decidir+emitir
tool-call) + execute (~4-7s)**, que precede a cualquier texto hablable. El pass-2
(confirmación) es CORTO (1-2 oraciones) → el 1er audio cae casi al final de su
generación → streamear no adelanta nada perceptible. Solo el caso multi-oración
con fallo (minimizar) dio +0.39s.

**Dónde SÍ ayudaría:** replies LARGOS multi-oración = turnos INFO (sin tool). Pero
esos los excluí por seguridad (ahí los guards de claim SÍ pueden disparar) y ya
están <2.2s. Streamearlos requiere correr los guards POR ORACIÓN (sólido, no un
pre-check débil) — más delicado, win sobre turnos ya rápidos.

## Conclusión / recomendación

Infra truthful de streaming construida, testeada y validada — pero **gateada OFF
porque NO mejora la latencia de acciones (medido)**. El dato REDIRIGE: el lever
real de latencia es **pass-1**, = backlog #2 (**prefill `<|tool_call|>` +
thinking_budget→0**), que ataca los 4-7s dominantes. Decisión de RED: (a) extender
streaming a turnos INFO con guards por-oración (win modesto sobre turnos ya
rápidos), o (b) pivotar a #2 (prefill), que ataca el costo real. El código de
streaming queda listo y dormant para (a) si se decide.
