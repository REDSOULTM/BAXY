# HOTFIX 2026-05-17 (I) — Closing gaps: pending_intent extension + Listo validator + verifier expansion + safety enforcement

> Continuá el chat post hotfixes E + F + G + H. Sprint de cierre
> que cubre los gaps que quedaron explícitamente fuera de los 4
> sprints previos. Los issues aquí son los que la auditoría
> marcó pero NO entraron en E/F/G/H porque eran más profundos o
> requerían infra adicional.

---

## Contexto: lo que quedó fuera de E+F+G+H

Después de E+F+G+H el sistema cubre los 8 bugs de la sesión real
2026-05-17 (D1-D8). Pero la auditoría dejó marcado:

### Gap I1 — `pending_intent` no se setea cuando el LLM pregunta por su cuenta
F1 cubrió el caso donde **la tool** devuelve `status=needs_user`.
Pero en Bug D8 part 2 el LLM **decidió por su cuenta**
preguntar "¿lo comprás o ya lo tenés?" SIN que `steam` devolviera
needs_user — el LLM lo previó. En ese path no hay structural
signal: solo texto del reply terminando en `?`.

Solución sin matchear idioma del user: detectar **estructural-
mente** el reply del asistente — `?` final + presencia de un
tool_call cancelado/pendiente, o un `<intent>` tag emitido por
el LLM cuando el subset era ambiguo (intent_validator).

### Gap I2 — Listo-on-no-tool sigue dependiendo del prompt
Hotfix B reescribió el system_hint del fast_action mode para
distinguir "Listo, X" (post-tool) de "de nada / no hay de qué"
(social ack). El modelo es chico — eventualmente va a ignorar
la regla. Solución: **validador post-reply** que detecte
estructuralmente "Listo" en turns sin tool_call exitoso y
forzar regeneración con un hint corto.

### Gap I3 — 47 tools todavía sin verifier
Sprint F llevó de 13 a 18. Las 47 restantes siguen confiando
en `ok=True` de la tool. Las de mayor traffic post-auditoría:
`browser_real`, `device_settings`, `network`, `package`,
`download`, `local_calendar`, `notes_tasks`, `reminder`,
`contacts`, `database`. Esas 10 cubren ~80% del uso.

### Gap I4 — Safety enforcement es solo declarativo
`purchase-guard` es un skill markdown. No hay código que bloquee
un click "Buy" / "Comprar". Si el LLM ignora la rule (modelo
chico), el agente puede gastar plata sin querer. Solución:
**enforced safety hook** que intercepta tool_calls cuyos args
contienen URLs/keywords de checkout antes de despachar.

### Gap I5 — Telemetría de "Gemma respondió sin llamar tool que debía"
La auditoría no tiene forma de medir "el LLM no llamó la tool
que estaba en el subset y debería haber llamado". Es el síntoma
final de Bug D1 (Que hora es → respuesta inventada). El fix de
D era prompt-based ("ANTI-HALLUCINATION rule"). Sin métrica no
podemos validar.

### Gap I6 — Multi-turn slot-filling general (WhatsApp body,
email recipient, file confirmation)
F1 cubre el caso "tool needs_user con asks_for". Pero los
flujos donde el LLM hace preguntas free-form sin que la tool
las catalogue (e.g. "¿qué cuenta de email querés usar?") quedan
fuera. Igual que I1 estructural-mente.

---

## OBJETIVO

Seis commits chicos, todos atacando structural signals — cero
matching de idioma del user.

1. `feat(state)`: extender `pending_intent` para que también se
   setee cuando el LLM emite un `<intent>` tag pero NO emite
   tool_call (intent declarado pero no ejecutado, suele ser
   pregunta clarificatoria).
2. `feat(reply-validator)`: detectar "Listo" estructuralmente
   en reply sin tool_call exitoso this-turn → forzar regeneración
   con hint.
3. `feat(verifiers)`: 10 verifiers nuevos para cubrir 80% del
   traffic restante.
4. `feat(safety)`: enforced hook que bloquea tool_calls con args
   de checkout-pattern cuando safety_enabled=True; warning trace
   event cuando safety está OFF pero el pattern aparece.
5. `obs(routing)`: contador `tool_call_skipped_when_expected`
   que dispara cuando una tool del subset NO fue llamada y el
   LLM contestó con texto. Solo telemetría, no fuerza nada.
6. `feat(state)`: slot genérico `pending_question` con TTL=2
   para multi-turn slot-filling no catalogado por la tool.
   Estructural: triggered por `?` al final del reply +
   pending tool_call cancelled.

---

## REGLAS GENERALES

1. PortandoLoMejor. Commits chicos.
2. **CERO matching de idioma del user**. Todas las detecciones
   son estructurales: shape del reply (`?` final), shape del
   tool result (`status`, `ok`, `args.url`), o tags emitidos
   por el LLM (`<intent>`).
3. NO toques las 65 compound tools NI sus schemas.
4. NO toques modes.py, planner.py, router_v2.py beyond añadir
   los hooks listados, voice/*, tool_descriptions.yaml.
5. NO instales libs nuevas.
6. NO `git add -A`.
7. Verificación post-commit:
   - `python -m pytest gemma4_agent/ -q` debe pasar.
   - `python -m gemma4_agent.launcher status` corre.

---

## FIX I1 — Extender pending_intent al caso "LLM preguntó por su cuenta"

### I1.1 — Detección estructural

Triggers (todos sin matchear texto del user):

a) **`<intent>` tag emitido + ningún tool_call en el turn**: el
   LLM declaró intent pero no ejecutó. Probable que esté
   pidiendo clarification antes de actuar.

b) **`?` al final del reply + tool_call pendiente abortado**:
   alguna tool fue invocada pero falló con `needs_user`, Y el
   LLM agregó una pregunta.

c) **`?` al final del reply + subset contenía tool no-trivial Y
   ningún tool_call fue emitido**: el LLM probablemente está
   pidiendo info antes de ejecutar.

El (c) es el más amplio pero también el más ruidoso. Lo
incluimos con un guard: el `pending_intent` se setea con
`tool=` siendo el primer tool del subset que NO sea meta
(session/state/verify/safety).

### I1.2 — Editar `gemma4_agent/agent.py`

Localizar el final del turn loop, donde se procesa el reply
final del LLM. ANTES de retornar del turn, agregar:

```python
# Hotfix I 2026-05-17: pending_intent rescue when the LLM asked
# a clarifying question without firing a tool. Triggers are
# structural; we never match user text.
def _should_set_pending_intent_from_reply(
    reply_text: str,
    tool_calls_this_turn: list[dict],
    selected_tool_names: list[str],
) -> tuple[str, str] | None:
    """Return (tool_name, asks_for) if a pending_intent should be
    set based on the reply shape, else None.

    Trigger conditions (all structural):
      1. Reply text trimmed ends with '?' or '¿' or any
         question-equivalent (?,؟,？ — all single chars, NOT a
         language match).
      2. AT MOST one successful tool_call this turn (so we don't
         override a normal action).
      3. selected_tool_names contains at least one non-meta tool
         (a domain tool that COULD be the pending target).
    """
    META = {"session", "state", "verify", "safety", "skill_load", "subagent"}
    QUESTION_CHARS = {"?", "¿", "؟", "？"}  # ASCII + Spanish + Arabic + CJK fullwidth
    if not reply_text:
        return None
    stripped = reply_text.rstrip().rstrip("\"'`*_)")
    if not stripped or stripped[-1] not in QUESTION_CHARS:
        return None
    successful = [
        c for c in tool_calls_this_turn
        if isinstance(c, dict)
        and not _is_unverified_result(c.get("result") or {})
    ]
    if len(successful) > 1:
        return None
    candidates = [t for t in selected_tool_names if t not in META]
    if not candidates:
        return None
    return (candidates[0], "user_clarification")


pending_target = _should_set_pending_intent_from_reply(
    reply_text=final_reply or "",
    tool_calls_this_turn=events,  # or whatever holds the turn's tool events
    selected_tool_names=selected_tool_names,
)
if pending_target and not self.state.get_pending_intent(self._turn_counter):
    target_tool, asks_for = pending_target
    self.state.set_pending_intent(
        tool=target_tool,
        args={},  # the LLM didn't specify args; the next turn will resolve
        asks_for=asks_for,
        current_turn=self._turn_counter,
        ttl_turns=2,  # shorter TTL — this is a guess based on '?' shape
    )
    self.trace.event(
        turn_id, "pending_intent_from_reply_shape",
        target_tool=target_tool,
        reason="reply_ended_with_question_no_tool",
    )
```

(Adaptar al shape real de `events` / `final_reply` / el
módulo-level helper `_is_unverified_result` que ya existe en
agent.py.)

### I1.3 — Test

Crear `gemma4_agent/test_pending_intent_from_reply_shape.py`:

```python
"""When the LLM ends its reply with a question mark and didn't
fire any tool this turn, pending_intent gets set targeting the
first non-meta tool in the subset. The next turn's router will
inject that tool.

100% structural detection — no user text matching.
Hotfix I 2026-05-17.
"""
from __future__ import annotations

import unittest


class PendingFromReplyShapeTest(unittest.TestCase):
    def _detect(self, reply: str, tool_calls: list, subset: list) -> tuple[str, str] | None:
        # The function lives inside agent.py as a private helper;
        # we import it for unit testing. If it's nested, lift to
        # module-level during the fix so it's testable.
        from gemma4_agent.agent import _should_set_pending_intent_from_reply
        return _should_set_pending_intent_from_reply(reply, tool_calls, subset)

    def test_question_mark_es_triggers(self) -> None:
        r = self._detect("¿lo comprás o ya lo tenés?", [], ["steam", "session"])
        self.assertEqual(r, ("steam", "user_clarification"))

    def test_question_mark_en_triggers(self) -> None:
        r = self._detect("Do you own it already?", [], ["steam", "session"])
        self.assertEqual(r, ("steam", "user_clarification"))

    def test_question_mark_fr_triggers(self) -> None:
        # Cross-lingual: French question. Structural detection on
        # '?' char only — language-agnostic.
        r = self._detect("Voulez-vous l'acheter?", [], ["steam", "session"])
        self.assertEqual(r, ("steam", "user_clarification"))

    def test_no_question_mark_does_not_trigger(self) -> None:
        r = self._detect("Listo, abrí Steam.", [], ["steam", "session"])
        self.assertIsNone(r)

    def test_successful_tool_call_blocks_trigger(self) -> None:
        # If a tool actually ran successfully, this is a normal
        # turn ending — don't stash a pending intent.
        calls = [{"tool": "steam", "result": {"ok": True}}]
        r = self._detect("¿algo más?", calls, ["steam", "session"])
        self.assertIsNone(r)

    def test_only_meta_subset_does_not_trigger(self) -> None:
        # No domain tool to target.
        r = self._detect("¿qué querés hacer?", [], ["session", "state"])
        self.assertIsNone(r)


if __name__ == "__main__":
    unittest.main()
```

### I1.4 — Commit

`feat(state): pending_intent triggered by reply-shape (LLM asked clarifying question)`

Mensaje:

```
feat(state): pending_intent triggered by reply-shape

Hotfix F1 set pending_intent when a tool returned
status='needs_user' (structural). But Bug D8 part 2 had a
different shape: the LLM decided ON ITS OWN to ask
'¿lo comprás o ya lo tenés?' before calling steam.install. No
tool returned needs_user — the question came from the model.

Fix: structural reply-shape detection. Trigger pending_intent
when ALL of:
  1. Final reply text ends with a question char ('?', '¿', '؟',
     '？' — covers ASCII, Spanish, Arabic, CJK). Single-char
     check, never a keyword list.
  2. At most one successful tool_call this turn (don't override
     a normal action turn).
  3. selected_tool_names contains at least one non-meta tool to
     target.

When triggered, pending_intent is set with tool=<first non-meta
in subset>, args={} (LLM didn't specify), asks_for=
'user_clarification', ttl_turns=2 (shorter than the F1 case
because this is a guess, not a structural tool signal).

Language-agnostic by construction — only '?' family chars are
checked, no keyword matching. Tests cover ES, EN, FR question
forms and the negative cases (no '?', successful tool ran,
meta-only subset).
```

---

## FIX I2 — Reply validator: detect "Listo" on no-tool turns

### I2.1 — Helper de detección estructural

`gemma4_agent/reply_validator.py` (nuevo módulo o append a
`reasoning.py` si tiene scope adecuado):

```python
"""Post-reply structural validators.

These run after the LLM emits its turn's final reply, BEFORE
we ship it to TTS / chat. If a structural anti-pattern is
detected, the agent triggers a single regeneration with a
short hint. The validators NEVER match user text — only the
shape of the LLM's reply and the tool_call activity this turn.

Hotfix I 2026-05-17.
"""
from __future__ import annotations

import re


# Languages don't matter — "Listo" is a Spanish marker the LLM
# uses because core.md says to. The structural anti-pattern is
# "ack template emitted on a turn where no tool ran". We detect
# the specific phrase the prompt teaches.
_LISTO_PATTERN = re.compile(
    r"^\s*(listo|listo[,.!])",
    re.IGNORECASE,
)


def is_listo_on_no_tool_turn(
    reply_text: str,
    successful_tool_calls_this_turn: list[dict],
) -> bool:
    """True iff the reply starts with 'Listo' AND no tool ran
    successfully this turn.

    'Listo' is the template the fast_action prompt teaches for
    POST-TOOL acks. Emitting it without a tool is the anti-pattern
    Bug B caught. The fix in B was prompt-level; this is the
    structural backstop.
    """
    if not reply_text or not _LISTO_PATTERN.match(reply_text):
        return False
    return not successful_tool_calls_this_turn


LISTO_REGEN_HINT = (
    "Your previous reply started with 'Listo' but no tool ran "
    "in this turn. 'Listo' is reserved for post-tool acks. "
    "Rewrite your reply naturally — for social acks like a "
    "thank-you, use 'de nada', 'no hay de qué', or the equivalent "
    "in the user's language."
)
```

### I2.2 — Wire en `agent.py`

Localizar donde se finaliza el reply del turn (probablemente
después de procesar todos los tool_calls). ANTES de devolver,
inyectar un **system message correctivo en `self.history`** que
el LLM va a ver en el próximo turn (NO regenerar el reply del
turn actual — Gemma4Agent no tiene `_regen_reply`, lo verifiqué
pre-flight).

```python
from .reply_validator import is_listo_on_no_tool_turn, LISTO_REGEN_HINT

successful = [
    c for c in events
    if isinstance(c, dict)
    and not _is_unverified_result(c.get("result") or {})
]
if is_listo_on_no_tool_turn(final_reply or "", successful):
    self.trace.event(
        turn_id, "reply_anti_pattern_detected",
        pattern="listo_on_no_tool",
    )
    # Inject a corrective system message AFTER the assistant's
    # bad reply so the LLM sees the correction context next turn.
    # This is the deferred-correction path: we don't rewrite this
    # turn's reply (no _regen_reply method), but the next turn's
    # LLM will see both its previous 'Listo' AND the system hint
    # explaining why that was wrong. The pattern is shape-
    # preserving: history grows by one system message, no other
    # state changes.
    #
    # Idempotency: we don't add this hint twice for the same
    # turn because we wire this right after the assistant reply
    # is finalized.
    self.history.append({
        "role": "system",
        "content": LISTO_REGEN_HINT,
    })
```

Rationale for the deferred-correction path:
- Gemma4Agent does NOT have a `_regen_reply` method (verified
  pre-flight). Adding one would require refactoring the turn
  loop to invoke `self.client.chat()` again with a synthetic
  message list — too much for this sprint's scope.
- Appending a system message to `self.history` is a 1-line change
  that uses existing infrastructure. The next turn's LLM will
  read its previous 'Listo' reply AND the corrective system note
  in the same context window, which is the lesson we want.
- The trace event `reply_anti_pattern_detected` still fires, so
  observability is intact. If the operator notices the pattern
  recurring even after this hint, that's data to inform whether
  a true regen is worth building.

If you find a `_regen_reply` or equivalent method we missed,
USE IT — synchronous regen on the same turn is strictly better
than deferred correction. But do NOT build the regen machinery
from scratch in this sprint.

### I2.3 — Test

Crear `gemma4_agent/test_reply_validator.py`:

```python
"""Reply validator detects structural anti-patterns post-reply.

Hotfix I 2026-05-17.
"""
from __future__ import annotations

import unittest

from gemma4_agent.reply_validator import (
    is_listo_on_no_tool_turn,
    LISTO_REGEN_HINT,
)


class ListoValidatorTest(unittest.TestCase):
    def test_listo_with_no_tool_calls_triggers(self) -> None:
        self.assertTrue(is_listo_on_no_tool_turn("Listo, hecho.", []))

    def test_listo_with_successful_tool_does_not_trigger(self) -> None:
        # 'Listo' is OK post-tool — the prompt teaches it.
        calls = [{"tool": "app", "result": {"ok": True, "verified": True}}]
        self.assertFalse(is_listo_on_no_tool_turn("Listo, abrí Chrome.", calls))

    def test_non_listo_reply_does_not_trigger(self) -> None:
        self.assertFalse(is_listo_on_no_tool_turn("De nada.", []))

    def test_listo_with_only_unverified_calls_triggers(self) -> None:
        # An unverified tool result doesn't count as 'tool ran'.
        calls = [{"tool": "app", "result": {"ok": False}}]
        self.assertTrue(is_listo_on_no_tool_turn("Listo.", calls))

    def test_hint_text_is_non_empty(self) -> None:
        self.assertGreater(len(LISTO_REGEN_HINT), 50)


if __name__ == "__main__":
    unittest.main()
```

### I2.4 — Commit

`feat(reply-validator): structural backstop for 'Listo' on no-tool turns`

Mensaje:

```
feat(reply-validator): structural backstop for 'Listo' on no-tool turns

Hotfix B reshaped the fast_action prompt to distinguish post-tool
ack ('Listo, X') from social ack ('de nada'). With a small model,
prompts alone are not enough — eventually the LLM drifts.

Fix: post-reply structural validator. After the LLM emits its
final reply, check if reply.startswith('Listo') AND no successful
tool ran this turn. If true, emit a trace event AND inject a
corrective system message into self.history so the next turn's
LLM sees both its previous mistake and the correction note in the
same context.

Deferred-correction path (not same-turn regen): Gemma4Agent has
no _regen_reply method, and building one would require
refactoring the turn loop. The system-message injection uses
existing infrastructure (1 line: self.history.append). The next
turn the LLM reads the bad reply + corrective note together,
which is the lesson we want it to internalize.

This is a backstop, not a replacement for the prompt. The prompt
still does 95% of the work; the validator catches the residual
5% where the model ignores the rule.

The validator NEVER matches user text — only the shape of the
LLM's own reply ('Listo' prefix) and the structural tool result
(was there a successful tool call this turn?).

Trace event 'reply_anti_pattern_detected' surfaces when this
fires, so we can monitor in production. If the pattern recurs
despite the deferred correction, we have data to inform whether
to build a true same-turn regen path.

Test pins the 4 paths: triggered, not-triggered (tool ran),
not-triggered (non-Listo reply), triggered (only failed calls).
```

---

## FIX I3 — 10 more structural verifiers (~80% traffic coverage)

### I3.1 — Verifiers a agregar

Mismo patrón estructural que F3. Cada verifier chequea evidencia
del result, nunca texto. Lista:

- `verify_browser_real` — `result.page_title`, `result.url`
  matched, `extract_chars > 0` para extract actions.
- `verify_device_settings` — `wifi_connected=True`, `bluetooth_on`,
  `display_resolution` matching the requested one.
- `verify_network` — `ping.success`, `dns_resolved`, `port_open`
  for the requested host.
- `verify_package` — `installed=True`, `version` set, OR
  `package_already_present=True`.
- `verify_download` — file at `dst_path` exists with `size > 0`
  and `expected_size` matches if provided.
- `verify_local_calendar` — `event.id` returned for create.
- `verify_notes_tasks` — `note.id` or `task.id` returned for
  create.
- `verify_reminder` — `reminder.id` AND scheduled task name
  returned.
- `verify_contacts` — `contact.id` returned for create/update;
  `match.id` for resolve_recipient.
- `verify_database` — `rows_affected` field present for
  INSERT/UPDATE/DELETE; `rows_returned` for SELECT.

### I3.2 — Implementación (template)

Patrón general (sigue verifiers existentes F3):

```python
def verify_browser_real(args: dict, result: dict) -> VerifierOutcome:
    """Verify browser_real (Playwright) actions.

    Structural-evidence: page_title, extracted content size,
    URL match. Never inspects natural-language text.
    """
    if _result_says_unverified(result):
        return _failed("browser_real", "tool reported failure", result)
    action = str(args.get("action") or "").lower()
    if action in {"click", "fill", "press"}:
        if result.get("ok") is True:
            return _ok_evidence("browser_real", "action dispatched", ["ok"])
        return _unverifiable("browser_real", "no ok flag")
    if action == "extract":
        chars = result.get("extracted_chars") or len(result.get("text") or "")
        if isinstance(chars, int) and chars > 0:
            return _ok_evidence("browser_real", "content extracted",
                                ["extracted_chars"], {"chars": chars})
        return _unverifiable("browser_real", "extract returned no text")
    if action in {"screenshot", "open", "goto"}:
        if result.get("path") or result.get("url"):
            return _ok_evidence("browser_real", "page or screenshot reached",
                                ["path", "url"])
        return _unverifiable("browser_real", "no path/url evidence")
    return _ok_evidence("browser_real", "non-evidence-bearing action", [])
```

Cada uno de los 10 sigue ese shape. ~10-15 líneas cada uno.

### I3.3 — Registrar

Agregar las 10 entries en `_VERIFIERS` dict.

### I3.4 — Tests

Crear `gemma4_agent/test_verifiers_expansion_round_2.py` con al
menos 2 cases por verifier (ok path + unverifiable path).
Patrón identico a `test_verifiers_expansion.py` del hotfix F.

### I3.5 — Commit

`feat(verifiers): 10 more structural verifiers (browser_real, device_settings, network, package, download, local_calendar, notes_tasks, reminder, contacts, database)`

Mensaje:

```
feat(verifiers): 10 more structural verifiers

Audit + hotfix F added 5 verifiers (media/office/email/notification/
routine). Verifier count went from 13/65 to 18/65. This commit
adds 10 more — chosen by traffic frequency — bringing coverage
to 28/65 (~43% of tools, ~80% of traffic).

New verifiers:
- verify_browser_real: page_title, extracted_chars, path/url for
  Playwright actions.
- verify_device_settings: wifi_connected, bluetooth_on,
  display_resolution.
- verify_network: ping.success, dns_resolved, port_open.
- verify_package: installed/version flags, package_already_present.
- verify_download: dst_path exists, expected_size matches.
- verify_local_calendar: event.id for create.
- verify_notes_tasks: note.id / task.id for create.
- verify_reminder: reminder.id + scheduled task name.
- verify_contacts: contact.id / match.id.
- verify_database: rows_affected / rows_returned.

All structural — checks evidence in result dict, never text.
Same VerifierOutcome contract as the F batch. Tests cover 2+
cases per verifier.
```

---

## FIX I4 — Enforced safety hook (purchase-guard backstop)

### I4.1 — Hook estructural

`gemma4_agent/safety_hook.py` (nuevo módulo):

```python
"""Pre-dispatch safety hook for purchase / paid-action attempts.

When safety_enabled, this hook intercepts tool_calls whose args
contain checkout-pattern URLs or paid-action keywords. The hook
returns either {block: True, reason: <str>} (the dispatcher
refuses the call and emits a confirmation request) or
{block: False} (the call proceeds).

When safety is OFF, the hook only emits a 'safety_hook_warning'
trace event so operators can see when paid-pattern args slipped
through.

Structural detection — checks args (URLs, action names) but
NEVER user text or LLM reply.

Hotfix I 2026-05-17.
"""
from __future__ import annotations

import re
from typing import Any


# URL patterns observed in real checkout / payment flows. Each
# pattern is anchored to the URL structure (host or path
# segment), not free text. Adding a pattern requires a real
# checkout URL example as backing.
_CHECKOUT_URL_PATTERNS = (
    re.compile(r"://(www\.)?steampowered\.com/checkout", re.IGNORECASE),
    re.compile(r"://(www\.)?epicgames\.com/store/.*/checkout", re.IGNORECASE),
    re.compile(r"://(www\.)?gog\.com/checkout", re.IGNORECASE),
    re.compile(r"://(www\.)?microsoft\.com/.*/checkout", re.IGNORECASE),
    re.compile(r"://(www\.)?paypal\.com/checkoutnow", re.IGNORECASE),
    re.compile(r"://checkout\.stripe\.com/", re.IGNORECASE),
    re.compile(r"://(www\.)?amazon\.com/gp/buy", re.IGNORECASE),
    re.compile(r"://(www\.)?amazon\.[a-z.]+/gp/buy", re.IGNORECASE),
)


# Action names that imply money movement, regardless of args.
# These come from the schema definitions, NOT user text.
_PAID_ACTION_NAMES = (
    ("steam", "purchase"),
    ("steam", "buy"),
    ("game_launcher", "purchase"),
    ("browser", "checkout"),
    # Note: browser(action='open', url='...checkout...') is caught
    # by the URL pattern check, not by action name.
)


def evaluate_tool_call(
    tool_name: str,
    action: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Inspect a planned tool_call. Returns:

      {"block": False}                                — safe.
      {"block": True, "reason": "<why>",
       "pattern": "<which_pattern_matched>"}         — paid-pattern detected.

    Caller decides whether to enforce (block) or just warn
    based on safety_enabled.
    """
    # URL pattern check
    url = args.get("url") or args.get("href") or ""
    if isinstance(url, str) and url:
        for pat in _CHECKOUT_URL_PATTERNS:
            if pat.search(url):
                return {
                    "block": True,
                    "reason": "URL matches a known checkout pattern. "
                              "Confirm with user before proceeding.",
                    "pattern": pat.pattern,
                }

    # Action name check
    if (tool_name, action) in _PAID_ACTION_NAMES:
        return {
            "block": True,
            "reason": f"{tool_name}.{action} is a paid action. "
                      "Confirm with user before proceeding.",
            "pattern": f"action:{tool_name}.{action}",
        }

    return {"block": False}
```

### I4.2 — Wire en `agent.py`

Localizar el dispatch de tool_calls. ANTES del `tools.run(name, args)`:

```python
from .safety_hook import evaluate_tool_call

verdict = evaluate_tool_call(
    tool_name=name,
    action=str(args.get("action") or ""),
    args=args or {},
)
if verdict.get("block"):
    self.trace.event(
        turn_id, "safety_hook_match",
        tool=name,
        pattern=verdict.get("pattern"),
        reason=verdict.get("reason"),
        enforced=self.config.safety_enabled,
    )
    if self.config.safety_enabled:
        # Hard block. Return a synthetic result so the LLM sees
        # the block and asks the user for confirmation.
        result = {
            "ok": False,
            "status": "needs_confirmation",
            "error": "purchase_guard",
            "reason": verdict["reason"],
        }
        # ... attach the synthetic result and skip the real call
        continue
    # safety OFF: only warn (already traced); let the call proceed.
```

### I4.3 — Test

Crear `gemma4_agent/test_safety_hook.py`:

```python
"""Safety hook intercepts checkout-pattern URLs and paid actions.

Hotfix I 2026-05-17. Structural detection — operates on args
(URL, action), never on user/LLM text.
"""
from __future__ import annotations

import unittest

from gemma4_agent.safety_hook import evaluate_tool_call


class SafetyHookTest(unittest.TestCase):
    def test_steam_checkout_url_is_blocked(self) -> None:
        v = evaluate_tool_call(
            "browser", "open",
            {"url": "https://store.steampowered.com/checkout/?cart=123"},
        )
        self.assertTrue(v["block"])
        self.assertIn("checkout", v["reason"].lower())

    def test_paypal_checkout_is_blocked(self) -> None:
        v = evaluate_tool_call(
            "browser_real", "goto",
            {"url": "https://www.paypal.com/checkoutnow?token=abc"},
        )
        self.assertTrue(v["block"])

    def test_steam_purchase_action_is_blocked(self) -> None:
        v = evaluate_tool_call(
            "steam", "purchase",
            {"app_id": 730},
        )
        self.assertTrue(v["block"])

    def test_safe_url_passes(self) -> None:
        v = evaluate_tool_call(
            "browser", "open",
            {"url": "https://store.steampowered.com/app/730/CSGO/"},
        )
        self.assertFalse(v["block"])

    def test_no_url_no_paid_action_passes(self) -> None:
        v = evaluate_tool_call(
            "filesystem", "list",
            {"path": "C:\\Users"},
        )
        self.assertFalse(v["block"])


if __name__ == "__main__":
    unittest.main()
```

### I4.4 — Commit

`feat(safety): enforced purchase-guard hook (structural URL/action match)`

Mensaje:

```
feat(safety): enforced purchase-guard hook

Audit 2026-05-17 gap: purchase-guard was declarative only (a
skills/purchase-guard/SKILL.md file). No code blocked a click on
'Comprar' or a navigation to a checkout URL. With a small model,
declarative prompts are not enough.

Fix: pre-dispatch safety hook that inspects tool_call args for:
1. URL patterns matching known checkout flows
   (steampowered.com/checkout, paypal.com/checkoutnow,
   amazon.com/gp/buy, stripe checkout, etc.). Each pattern is
   anchored to URL structure, not free text.
2. Paid action names from the schema (steam.purchase,
   steam.buy, game_launcher.purchase, browser.checkout).

When the hook matches AND safety_enabled=True, the call is hard-
blocked: a synthetic 'needs_confirmation' result is returned to
the LLM so it asks the user before proceeding.

When safety_enabled=False, the hook only emits a
'safety_hook_match' trace event — visible to operators in the
JSONL log so we can audit whether the LLM is trying paid paths
even without enforcement.

NEVER matches user text or LLM reply text. Operates only on the
args of the planned tool_call.

Tests cover 5 paths: steam checkout URL, paypal checkout URL,
steam.purchase action, safe steam app page URL, no-URL action.
```

---

## FIX I5 — `tool_call_skipped_when_expected` telemetry

### I5.1 — Detección estructural

Después del turn loop, comparar:
- `selected_tool_names` (subset que pasó al LLM).
- Tools que efectivamente fueron llamadas.

Si:
1. `selected_tool_names` contiene al menos 1 tool no-meta.
2. NINGÚN tool_call fue emitido en el turn.
3. El reply del LLM NO es smalltalk (proxy: el subset NO es solo
   meta — porque entonces el smalltalk gate del router ya lo
   habría agarrado).

Emit `tool_call_skipped_when_expected` trace event con el subset
y la primera oración del reply (para que el operator pueda
inspeccionar). Solo telemetría, no fuerza nada.

### I5.2 — Wire en `agent.py`

Final del turn:

```python
META = {"session", "state", "verify", "safety", "skill_load", "subagent"}
domain_subset = [t for t in selected_tool_names if t not in META]
tool_calls_emitted = len([c for c in events if c.get("tool")])
if domain_subset and tool_calls_emitted == 0:
    self.trace.event(
        turn_id, "tool_call_skipped_when_expected",
        domain_subset=domain_subset,
        reply_preview=(final_reply or "")[:200],
        v2_source=getattr(self, "_last_router_v2_source", None),
    )
```

(Si no hay un `_last_router_v2_source` capturado, sacarlo del
último `router_v2` event que se haya emitido en este turn —
agregar el setter cuando se procesa ese event.)

### I5.3 — Test

Crear `gemma4_agent/test_tool_skipped_telemetry.py`:

```python
"""tool_call_skipped_when_expected emits when the subset had a
domain tool but no tool_call was made.

Hotfix I 2026-05-17. The detection helper is pure; the wiring is
verified by reading the source (smoke).
"""
from __future__ import annotations

import unittest


class ToolSkippedDetectionTest(unittest.TestCase):
    def test_domain_subset_filtered_correctly(self) -> None:
        # The filter logic is in agent.py — extract to a helper
        # during the fix and test it here.
        from gemma4_agent.agent import _domain_subset
        META = {"session", "state", "verify", "safety"}
        self.assertEqual(_domain_subset(["session"]), [])
        self.assertEqual(_domain_subset(["steam", "session"]), ["steam"])
        self.assertEqual(_domain_subset(["system", "media", "state"]),
                         ["system", "media"])

    def test_event_name_constant_exists(self) -> None:
        import gemma4_agent.agent as _agent
        import inspect
        src = inspect.getsource(_agent)
        self.assertIn("tool_call_skipped_when_expected", src)


if __name__ == "__main__":
    unittest.main()
```

### I5.4 — Commit

`obs(routing): tool_call_skipped_when_expected event`

Mensaje:

```
obs(routing): tool_call_skipped_when_expected event

Audit gap: no telemetry for 'the LLM had a domain tool in its
subset and chose not to call it'. This is the final-stage
symptom of Bug D1 (Que hora es -> hallucinated time despite
system.time being in subset). Hotfix D added the ANTI-
HALLUCINATION prompt rule; without metrics we can't validate it.

Fix: at the end of each turn, structurally check:
  1. domain_subset = subset \ {session, state, verify, safety,
     skill_load, subagent}.
  2. tool_calls_emitted = number of tool_calls this turn.
  3. If domain_subset is non-empty AND tool_calls_emitted == 0,
     emit tool_call_skipped_when_expected with the subset + first
     200 chars of the reply.

Pure telemetry. Doesn't force anything. Operators grep the trace
to find drift between subset selection and LLM behavior.

Helper _domain_subset() lifted to module-level for testability.
```

---

## FIX I6 — Generic pending_question slot (multi-turn slot-filling)

### I6.1 — Detección estructural

I1 cubre "LLM preguntó por su cuenta + subset tiene tool no-meta".
Pero hay un caso adicional: la pregunta vino con tool_call
exitoso (la tool ejecutó pero pidió clarificación adicional vía
un campo `needs_clarification` o similar).

Patrón:
- Tool result `ok=True` Y `status='partial'` Y campo
  `clarification_needed=<str>` (estructural).
- Reply termina con `?`.
- Mismo handling que pending_intent pero con clave separada
  (`_pending_question`) y TTL=2.

### I6.2 — Editar `gemma4_agent/state.py`

```python
_PENDING_QUESTION_KEY = "_pending_question"

def set_pending_question(
    self,
    tool: str,
    question_topic: str,
    last_args: dict,
    current_turn: int,
    ttl_turns: int = 2,
) -> None:
    self.data[_PENDING_QUESTION_KEY] = {
        "tool": tool,
        "question_topic": question_topic,
        "last_args": last_args,
        "created_turn": int(current_turn),
        "ttl_turns": int(ttl_turns),
    }
    self.save()

def get_pending_question(self, current_turn: int) -> dict | None:
    pq = self.data.get(_PENDING_QUESTION_KEY)
    if not pq:
        return None
    if int(current_turn) - int(pq.get("created_turn", 0)) > int(pq.get("ttl_turns", 2)):
        self.clear_pending_question()
        return None
    return dict(pq)

def clear_pending_question(self) -> None:
    if _PENDING_QUESTION_KEY in self.data:
        del self.data[_PENDING_QUESTION_KEY]
        self.save()
```

### I6.3 — Trigger desde agent.py

Cuando un tool result llega con `status='partial'` o
`clarification_needed` set:

```python
clarif = result.get("clarification_needed") or result.get("partial_reason")
if clarif and isinstance(clarif, str):
    self.state.set_pending_question(
        tool=tool_name,
        question_topic=clarif,
        last_args=dict(args or {}),
        current_turn=self._turn_counter,
    )
```

### I6.4 — Hint al router (igual que F1)

Modificar `route_v2` para aceptar `pending_question_tool` y
inyectarlo en el subset igual que `pending_tool_hint`. O reusar
el mismo kwarg `pending_tool_hint` — la fuente (intent vs
question) no le importa al router.

### I6.5 — Test

Crear `gemma4_agent/test_pending_question.py`:

```python
"""pending_question slot for multi-turn slot-filling.

Hotfix I 2026-05-17. Triggered when a tool result has
clarification_needed or status='partial' — structural signal.
"""
from __future__ import annotations

import os
import tempfile
import unittest


class PendingQuestionStateTest(unittest.TestCase):
    def setUp(self) -> None:
        from gemma4_agent.state import AgentState
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        self.tmp.write("{}")
        self.tmp.close()
        try:
            self.state = AgentState(self.tmp.name)
        except TypeError:
            self.state = AgentState()

    def tearDown(self) -> None:
        try:
            os.unlink(self.tmp.name)
        except Exception:
            pass

    def test_set_get_clear_pending_question(self) -> None:
        self.state.set_pending_question(
            tool="email",
            question_topic="which_account",
            last_args={"action": "send"},
            current_turn=1,
        )
        pq = self.state.get_pending_question(current_turn=2)
        self.assertIsNotNone(pq)
        self.assertEqual(pq["tool"], "email")
        self.state.clear_pending_question()
        self.assertIsNone(self.state.get_pending_question(current_turn=2))

    def test_pending_question_expires_faster(self) -> None:
        # ttl=2 by default — should expire by turn 4.
        self.state.set_pending_question(
            tool="email", question_topic="x", last_args={},
            current_turn=1,
        )
        self.assertIsNotNone(self.state.get_pending_question(current_turn=3))
        self.assertIsNone(self.state.get_pending_question(current_turn=10))


if __name__ == "__main__":
    unittest.main()
```

### I6.6 — Commit

`feat(state): pending_question slot for tool-emitted clarifications`

Mensaje:

```
feat(state): pending_question slot for tool-emitted clarifications

Hotfix F1 covered: tool returned status='needs_user'.
Hotfix I1 covered: LLM asked a question on its own.
This covers: tool succeeded but emitted a clarification_needed
field (e.g. partial success that requires more info).

Structural detection — looks for clarification_needed or
partial_reason in the tool result, never matches text.

Separate slot from pending_intent because:
- TTL shorter (2 vs 3 turns) — a partial result is more
  time-sensitive.
- Source field 'question_topic' so the next turn's LLM can
  see WHAT was asked even though the tool already ran.

The router consumes both slots via the same pending_tool_hint
kwarg added in F1 — no router signature change.

Test pins set/get/clear/expire.
```

---

## REPORTE FINAL

Devolveme:
1. Hashes de los 6 commits.
2. Output de los tests específicos:
   ```bash
   python -m pytest gemma4_agent/test_pending_intent_from_reply_shape.py \
                    gemma4_agent/test_reply_validator.py \
                    gemma4_agent/test_verifiers_expansion_round_2.py \
                    gemma4_agent/test_safety_hook.py \
                    gemma4_agent/test_tool_skipped_telemetry.py \
                    gemma4_agent/test_pending_question.py -v
   ```
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`.
4. Smoke del safety hook:
   ```python
   from gemma4_agent.safety_hook import evaluate_tool_call
   urls = [
       "https://store.steampowered.com/checkout/?cart=123",
       "https://www.paypal.com/checkoutnow",
       "https://store.steampowered.com/app/730/CSGO/",
   ]
   for u in urls:
       v = evaluate_tool_call("browser", "open", {"url": u})
       print(f'{u[:60]:60s} block={v["block"]}')
   ```

## CRITERIO DE ÉXITO

- 6 commits aterrizados.
- ≥15 tests nuevos verdes.
- Suite completa verde (modulo Sprint 3a pre-existing failure).
- `python -m gemma4_agent.launcher status` OK.
- Safety hook smoke muestra block=True solo para URLs de checkout
  reales.

## NO HACER (anti-scope)

- NO bloquees por LLM reply text — solo args estructurales.
- NO expandas `_CHECKOUT_URL_PATTERNS` preemptivamente. Cada
  pattern requiere un ejemplo real de checkout URL backing.
- NO loop infinito en el Listo regen — `_listo_regen_done_this_turn`
  garantiza one-shot.
- NO emitas content del reply en `tool_call_skipped_when_expected`
  más allá de los primeros 200 chars (privacy + log size).
- NO unifiqués `pending_intent` y `pending_question` en una sola
  estructura — semánticas distintas (intent = "voy a llamar X
  cuando confirmes", question = "X ya corrió y pidió más info").
- Si `_regen_reply` requiere refactor pesado para invocar el LLM
  con el hint adicional, escala a logger.warning + trace event +
  no regen — el trace event ya es lo más importante.
- Si el agent.py main loop no permite agregar el reply validator
  sin tocar el dispatcher de tools, dejá el reply validator como
  módulo independiente con test, y deja un TODO para wirearlo en
  el siguiente sprint.
