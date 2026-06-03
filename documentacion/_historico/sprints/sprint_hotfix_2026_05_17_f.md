# HOTFIX 2026-05-17 (F) — Pending intent + locator alignment + verifiers + intent cross-validation

> Continuá el chat de Claude Code post hotfix E (router_v2 ya es
> el ruteo autoritativo). Este sprint ataca cuatro bugs P1 que la
> auditoría 2026-05-17 surfaceó y que requieren código, no más
> prompts.

---

## Contexto: bugs P1 confirmados

### Bug F1 — Cross-turn intent perdido (Bug D8 part 2)
```
[16:55:34] YOU: Instala doom eternal en steam
[16:55:37] GEMMA: Antes de instalar Doom Eternal, necesito confirmar
                  si deseas comprarlo o si ya lo tienes...
[16:55:44] YOU: Ya lo tengo comprado
[16:55:46] GEMMA: No alcancé a completar la acción. ¿La repetimos?
                  ← INTENT PERDIDO
[16:55:56] YOU: Instala doom eternal en steam, ya lo tengo comprado
                  ← user tiene que repetir todo
```

Grep `pending_intent|pending_action|intent_slot` en el repo: cero.
Cada turn arranca confiando en que el LLM se acuerda del intent
pendiente — pero hotfix C demostró que los `tool_result` se
dropean. El `assistant.content` sobrevive (la pregunta "¿lo
comprás o ya lo tenés?") pero NO hay infra para que el ruteo del
próximo turn sepa cuál tool resumir.

**Importante**: este fix es language-agnostic. NO depende de
matchear "ya lo tengo" o "sí" o "yes" o "oui". El planner v1
queda sin tocar; lo que cambia es que router_v2 (post hotfix E)
recibe una pista del intent pendiente como **input adicional**,
para que su retrieval pondere ese tool. Si el user dice "no" o
cambia de tema, el LLM decide no usarlo — el slot solo amplía el
subset, no lo fuerza.

### Bug F2 — `compact_tool_result.core_keys` no incluye `deeplink`
`agent_compaction.py:170-193`: la lista `core_keys` que sobrevive
cuando un tool_result excede `TOOL_RESULT_LIMIT` incluye
`path, url, image_path, title, selected_title` pero NO `deeplink`.

En cambio, `_LOCATOR_KEYS` del breadcrumb (línea 215) sí lo incluye.
La regla `EVIDENCE CITATION` del core.md promete preservar
`deeplink`. Resultado: para tools que devuelven deeplink en
payloads grandes, el valor se pierde durante la compactación.

### Bug F3 — 52 de 65 tools no tienen verifier
`gemma4_agent/verifiers.py` tiene solo 13 `verify_*`. Las restantes
52 dependen del LLM mismo para reportar honestamente — implica
que cualquier tool con `status='dispatched'` (URL opens,
deeplinks, keypresses) reporta "Listo" sin auditoría.

El Spotify race bug fue un special-case dentro de `domain_tools`.
Generalizamos a los 5 verifiers de mayor impacto: `media`,
`office`, `email`, `routine`, `notification`.

**Importante**: cada verifier chequea evidencia **estructural** del
result (paths del filesystem, message_ids, resource_ids). NUNCA
matchea texto en `result.content` ni en el reply del LLM —
language-agnostic por construcción.

### Bug F4 — intent_validator solo cubre 4 pares ambiguos
`gemma4_agent/intent_validator.py:22-44`: solo
`audio↔window/browser_real/app/media`. Pares igualmente confusos
sin guard: `email ↔ whatsapp`, `browser ↔ browser_real`,
`filesystem ↔ download`, `terminal ↔ developer`.

**Importante**: el validator usa el `<intent>` tag que el LLM
emite — el tag es un verbo neutro tipo `close`, `send_email`,
`automate_page`. No depende de idioma del usuario.

---

## OBJETIVO

Cuatro commits chicos:

1. `feat(state)`: `pending_intent` slot con TTL=3 turns. Hint
   al planner + a router_v2 SIN matchear texto del user.
2. `fix(history)`: alinear `core_keys` de `compact_tool_result`
   con `_LOCATOR_KEYS` (agregar `deeplink`).
3. `feat(verifiers)`: 5 verifiers nuevos basados en evidencia
   estructural (paths, IDs) — no en texto.
4. `feat(intent-validator)`: 4 pares de cross-reject más
   (todos en términos de intent abstracto).

---

## REGLAS GENERALES

1. PortandoLoMejor. Commits chicos.
2. **NUNCA** matchees texto del user para inferir intent
   (eso es lo que router_v2 hace bien y donde v1 falla).
   El `pending_intent` se setea cuando el LLM **emite** una
   pregunta clarificatoria en su reply, y se persiste con
   metadata del tool. El ruteo del próximo turn USA ese metadata,
   no el texto del user.
3. NO toques las 65 compound tools NI sus schemas.
4. NO toques modes.py, planner.py beyond añadir el kwarg
   `pending_intent`, router_v2.py beyond añadir el hook,
   agent_runner.py, voice/*, tool_descriptions.yaml.
5. Cada verifier nuevo: solo evidencia estructural. Si el tool
   no expone evidencia, el verifier devuelve `_unverifiable(...)`.
6. NO instales libs nuevas.
7. NO `git add -A`.

---

## FIX F1 — Pending intent slot

### F1.1 — Detección del intent (sin matchear user text)

El intent NO se infiere del idioma del user. Se setea cuando el
agente **decide** que su próximo reply es una pregunta
clarificatoria sobre una acción pendiente. Hay 3 sources
language-agnostic:

a) **Tool devuelve `needs_user` / `needs_confirmation`**:
   muchas tools (whatsapp, steam, filesystem destructivos)
   devuelven `status: "needs_user"` con `asks_for: <slot>`. Ese
   shape es estructural — no texto.
b) **LLM emite `<intent>` tag**: si el subset es ambiguo
   (intent_validator), el LLM emite un tag con el verbo
   abstracto.
c) **Heurística posterior** (este sprint NO lo incluye):
   detectar `?` final en el reply + presencia de tool calls
   pendientes. Lo dejamos para sprint futuro porque requiere
   parsear texto.

Este sprint cubre **(a)**: cuando una tool result trae
`status: "needs_user"` con metadata, ESE es el trigger del slot.
Es 100% estructural.

### F1.2 — Inspeccionar `gemma4_agent/state.py`

```bash
grep -n "^class \|^def " gemma4_agent/state.py | head
```

Identificar el backing store. Probablemente `self.data` (dict)
con `self.save()` automático. Si la API es distinta, adaptá los
métodos al patrón real.

### F1.3 — Agregar el slot al `AgentState`

```python
_PENDING_INTENT_KEY = "_pending_intent"

def set_pending_intent(
    self,
    tool: str,
    args: dict,
    asks_for: str,
    current_turn: int,
    ttl_turns: int = 3,
) -> None:
    """Stash a pending tool intent that survives across turns.

    Hotfix F 2026-05-17. Triggered when a tool result returns
    status='needs_user' (or equivalent structural signal). The
    next turn's router uses this to widen its subset toward the
    pending tool without depending on the user reply matching
    any language-specific keywords.

    Schema:
      tool       — compound tool name (e.g. 'steam').
      args       — args passed to the tool that returned needs_user.
      asks_for   — what slot is missing ('ownership_confirmation',
                   'message_body', 'recipient', ...).
      created_turn / ttl_turns — TTL=3 by default (user typically
                   confirms within 1-2 turns; 3 is the upper bound
                   before the intent is stale).
    """
    self.data[_PENDING_INTENT_KEY] = {
        "tool": tool,
        "args": args,
        "asks_for": asks_for,
        "created_turn": int(current_turn),
        "ttl_turns": int(ttl_turns),
    }
    self.save()

def get_pending_intent(self, current_turn: int) -> dict | None:
    pi = self.data.get(_PENDING_INTENT_KEY)
    if not pi:
        return None
    if int(current_turn) - int(pi.get("created_turn", 0)) > int(pi.get("ttl_turns", 3)):
        self.clear_pending_intent()
        return None
    return dict(pi)

def clear_pending_intent(self) -> None:
    if _PENDING_INTENT_KEY in self.data:
        del self.data[_PENDING_INTENT_KEY]
        self.save()
```

### F1.4 — Trigger del slot desde `agent.py`

Localizá donde se procesan los `tool_result` events. Buscar:
```bash
grep -n "needs_user\|status.*needs\|asks_for" gemma4_agent/agent.py
```

Donde una tool result llega con `status == "needs_user"`, agregar:

```python
# Hotfix F 2026-05-17: persist the intent so the next turn's
# router can resume even if the user reply lacks tool-keyword
# signal. Language-agnostic: we read 'asks_for' from the tool
# result, never from user text.
if isinstance(result, dict) and str(result.get("status") or "").lower() == "needs_user":
    asks_for = str(result.get("asks_for") or result.get("missing") or "user_input")
    self.state.set_pending_intent(
        tool=tool_name,
        args=dict(args or {}),
        asks_for=asks_for,
        current_turn=self._turn_counter,
    )
```

### F1.5 — Consumir el slot en el router

Modificar `gemma4_agent/router_v2.py::RouterV2.route()`:

```python
def route(
    self,
    query: str,
    *,
    pending_tool_hint: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Resolve a query to a tool subset.

    pending_tool_hint (hotfix F 2026-05-17): tool name from a
    pending intent. When present, that tool is forced into the
    returned subset regardless of retrieval scores. The LLM still
    decides whether to call it — the slot only widens reachability.
    """
    ...
    # existing pipeline ...

    # After RRF + popular fallback, ensure pending_tool_hint is
    # in the subset. Insert at the head if missing.
    if pending_tool_hint and pending_tool_hint not in subset:
        subset.insert(0, pending_tool_hint)
        telemetry["pending_tool_injected"] = pending_tool_hint
    ...
```

Y el módulo entry `route_v2()`:
```python
def route_v2(query: str, *, pending_tool_hint: str | None = None) -> tuple[list[str], dict[str, Any]]:
    return RouterV2.get().route(query, pending_tool_hint=pending_tool_hint)
```

### F1.6 — Wire desde `agent.py`

Donde se llama `route_v2(raw_text_early or "")` (post hotfix E),
pasar el hint:

```python
pending = self.state.get_pending_intent(self._turn_counter) if hasattr(self.state, "get_pending_intent") else None
pending_tool = (pending or {}).get("tool")
_v2_subset, _v2_telemetry = route_v2(raw_text_early or "", pending_tool_hint=pending_tool)
```

Y también pasar el hint al planner v1 (signature change ya
existente; queda como red de seguridad si v2 está OFF):

```python
selected = select_tool_names(
    user_content, plan,
    safety_enabled=self.config.safety_enabled,
    last_assistant_text=last_assistant_text,
    pending_intent=pending,  # <- new kwarg
)
```

Modificar `gemma4_agent/planner.py::select_tool_names` signature:

```python
def select_tool_names(
    content: str | list[dict[str, Any]],
    plan: MissionPlan,
    *,
    safety_enabled: bool = False,
    last_assistant_text: str | None = None,
    pending_intent: dict | None = None,
) -> list[str]:
    ...
    # After existing logic, before the cap:
    if pending_intent:
        pi_tool = str(pending_intent.get("tool") or "")
        if pi_tool and pi_tool not in names:
            names.insert(0, pi_tool)
```

### F1.7 — Clear-on-resolve

Después de procesar los tool_calls del turn, si la tool target
del intent corrió exitosamente, limpiar:

```python
if pending and pending.get("tool"):
    if any(call.get("tool") == pending["tool"] and not _is_unverified_result(call.get("result") or {}) for call in tool_calls_this_turn):
        self.state.clear_pending_intent()
```

### F1.8 — Tests

Crear `gemma4_agent/test_pending_intent.py`:

```python
"""Cross-turn pending intent rescue (hotfix F 2026-05-17).

The intent is set when a tool result returns status='needs_user'
(structural signal), and consumed by the next turn's router as a
tool hint. NO user text matching is involved.
"""
from __future__ import annotations

import os
import tempfile
import unittest


class AgentStatePendingIntentTest(unittest.TestCase):
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

    def test_set_get_clear(self) -> None:
        self.state.set_pending_intent(
            tool="steam",
            args={"action": "install", "query": "Doom Eternal"},
            asks_for="ownership_confirmation",
            current_turn=1,
        )
        pi = self.state.get_pending_intent(current_turn=2)
        self.assertIsNotNone(pi)
        self.assertEqual(pi["tool"], "steam")
        self.assertEqual(pi["asks_for"], "ownership_confirmation")
        self.state.clear_pending_intent()
        self.assertIsNone(self.state.get_pending_intent(current_turn=2))

    def test_expires_after_ttl(self) -> None:
        self.state.set_pending_intent(
            tool="steam", args={}, asks_for="x",
            current_turn=1, ttl_turns=3,
        )
        self.assertIsNone(self.state.get_pending_intent(current_turn=10))


@unittest.skipUnless(
    __import__("gemma4_agent.router_v2", fromlist=["MODEL_PATH"]).MODEL_PATH.exists(),
    "e5-small ONNX model not installed",
)
class RouterV2PendingHintTest(unittest.TestCase):
    """When pending_tool_hint is passed, the router injects that
    tool into the subset regardless of retrieval scores."""

    @classmethod
    def setUpClass(cls) -> None:
        from gemma4_agent.router_v2 import RouterV2
        RouterV2.reset()
        cls.router = RouterV2.get()
        if not cls.router._ensure_loaded():
            raise unittest.SkipTest(cls.router._load_error)

    def test_hint_injected_when_missing(self) -> None:
        # User reply is 100% language-neutral confirmation; without
        # the hint, router_v2 would land in smalltalk gate. The hint
        # forces steam into the subset.
        from gemma4_agent.router_v2 import route_v2
        subset, telemetry = route_v2("sí", pending_tool_hint="steam")
        self.assertIn("steam", subset)
        self.assertEqual(telemetry.get("pending_tool_injected"), "steam")

    def test_hint_not_duplicated_when_already_present(self) -> None:
        from gemma4_agent.router_v2 import route_v2
        # 'abrime el steam' already routes to steam; the hint should
        # not double-insert.
        subset, _ = route_v2("abrime el steam", pending_tool_hint="steam")
        self.assertEqual(subset.count("steam"), 1)


if __name__ == "__main__":
    unittest.main()
```

### F1.9 — Commit

`feat(state): pending_intent slot widens router reachability across turns`

Mensaje:

```
feat(state): pending_intent slot widens router reachability across turns

Audit 2026-05-17 bug D8 part 2: 'instala doom eternal' -> Gemma
'¿lo comprás o ya lo tenés?' -> user 'ya lo tengo' -> 'no alcancé
a completar' (intent lost). User had to repeat the full command.

The fix is language-agnostic. We do NOT match user reply text
("ya lo tengo", "sí", "yes", "oui"). Instead:

1. AgentState gains set_pending_intent / get_pending_intent /
   clear_pending_intent. Schema: {tool, args, asks_for,
   created_turn, ttl_turns=3}.

2. The slot is SET when a tool result returns status='needs_user'
   — a structural signal emitted by the tool itself, not derived
   from any natural-language text.

3. The slot is CONSUMED by router_v2.route() via a new
   pending_tool_hint kwarg, which injects the tool name into the
   returned subset regardless of retrieval scores. The planner v1
   gets the same hint via select_tool_names(pending_intent=...).

4. The slot is CLEARED after the target tool runs successfully in
   a subsequent turn (verified=True or status not in {failed,
   needs_verification, attempted, needs_confirmation}).

5. TTL=3 turns. After expiration the slot self-clears on next
   get(); the user has moved on.

The LLM still decides whether to call the hinted tool. The hint
only widens reachability — if the user says "no" or changes
topic, the LLM picks something else and the slot stays parked
until TTL elapses.

Tests cover state set/get/clear/expire and router_v2 hint
injection. Skips integration test when model is absent.
```

---

## FIX F2 — Align core_keys with _LOCATOR_KEYS

### F2.1 — Editar `gemma4_agent/agent_compaction.py:170-193`

Buscar la tupla `core_keys`. Agregar `deeplink`:

```python
core_keys = (
    "ok",
    "status",
    "verified",
    "completion_status",
    "error",
    "tool",
    "action",
    "evidence",
    "path",
    "url",
    "image_path",
    "title",
    "selected_title",
    "deeplink",          # ← NEW: aligns with _LOCATOR_KEYS (hotfix F)
    "level",
    "query",
    ...
)
```

### F2.2 — Test

Crear `gemma4_agent/test_compact_tool_result_locator_alignment.py`:

```python
"""compact_tool_result.core_keys must include every key in
_LOCATOR_KEYS so locators survive both compaction (when payload
exceeds TOOL_RESULT_LIMIT) and the breadcrumb pre-pass.

Hotfix F 2026-05-17.
"""
from __future__ import annotations

import unittest

from gemma4_agent.agent_compaction import (
    _LOCATOR_KEYS,
    compact_tool_result,
)


class LocatorAlignmentTest(unittest.TestCase):
    def test_compact_preserves_each_locator_key_when_oversized(self) -> None:
        big_payload: dict = {
            "junk": "x" * 5000,  # over TOOL_RESULT_LIMIT
            "path": "C:\\file.pptx",
            "url": "https://example.com/path",
            "selected_title": "Daredevil",
            "image_path": "C:\\screenshot.png",
            "deeplink": "spotify:track:abc",
        }
        out = compact_tool_result("tool", {}, big_payload)
        for k in _LOCATOR_KEYS:
            self.assertIn(k, out, f"{k} dropped during compaction; "
                                  f"got keys: {list(out.keys())}")
            self.assertEqual(out[k], big_payload[k],
                             f"{k} value changed during compaction")


if __name__ == "__main__":
    unittest.main()
```

### F2.3 — Commit

`fix(history): align compact_tool_result.core_keys with _LOCATOR_KEYS`

Mensaje:

```
fix(history): align compact_tool_result.core_keys with _LOCATOR_KEYS

Audit 2026-05-17: compact_tool_result.core_keys (the tuple of keys
preserved when a tool_result exceeds TOOL_RESULT_LIMIT) listed
path/url/image_path/title/selected_title but NOT deeplink. The
breadcrumb pre-pass _LOCATOR_KEYS did include deeplink. Drift means
that for tools returning a deeplink in a large payload, the value
got dropped before the breadcrumb pre-pass could harvest it.

Fix: add deeplink to core_keys. Test pins the invariant that every
_LOCATOR_KEYS member survives compact_tool_result with an oversized
payload.

Pure addition; no other behavior change.
```

---

## FIX F3 — 5 new verifiers (structural-evidence only)

### F3.1 — Estudiar el shape

```bash
grep -A 30 "^def verify_app\|^def verify_filesystem" gemma4_agent/verifiers.py
```

Identificar `VerifierOutcome`, `_ok_evidence`, `_unverifiable`,
`_failed`, `_result_says_unverified`.

### F3.2 — Implementar

Agregar al final de `gemma4_agent/verifiers.py` (antes del
registro):

```python
def verify_media(args: dict, result: dict) -> VerifierOutcome:
    """Verify media playback / open actions.

    Structural-evidence only: we check auto_play_info.played +
    query_match for streaming plays, and trust media keys for
    pause/next/etc. We do NOT inspect the LLM's reply or
    user-facing text.
    """
    if _result_says_unverified(result):
        return _failed("media", "tool reported failure", result)
    action = str(args.get("action") or "").lower()
    if action in {"pause", "resume", "play_pause", "stop", "next", "previous"}:
        return _ok_evidence("media", "media key dispatched", ["action"])
    if action == "play":
        api = result.get("auto_play_info") or {}
        played = api.get("played")
        verified = api.get("verified")
        query_match = api.get("query_match")
        if played and (verified or query_match):
            return _ok_evidence("media", "auto-play verified",
                                ["auto_play_info.played", "auto_play_info.query_match"])
        if result.get("url") or result.get("deeplink"):
            return _unverifiable("media", "URL/deeplink dispatched, no playback signal",
                                 {"url": result.get("url"), "deeplink": result.get("deeplink")})
    return _unverifiable("media", "no playback evidence in tool result")


def verify_office(args: dict, result: dict) -> VerifierOutcome:
    """Verify office document creation / open / convert.

    Structural-evidence: the returned path must exist on the
    filesystem with non-zero size.
    """
    if _result_says_unverified(result):
        return _failed("office", "tool reported failure", result)
    action = str(args.get("action") or "").lower()
    path = result.get("path")
    if action.startswith("create") or action.startswith("convert"):
        if path:
            import os
            if os.path.exists(path):
                size = os.path.getsize(path)
                if size > 0:
                    return _ok_evidence("office", "file created on disk",
                                        ["path", "size"], {"size": size})
                return _failed("office", "file exists but empty", {"path": path})
            return _failed("office", "claimed path does not exist", {"path": path})
        return _unverifiable("office", "no path in result")
    return _ok_evidence("office", "non-create action", [])


def verify_email(args: dict, result: dict) -> VerifierOutcome:
    """Verify email send actions.

    Structural-evidence: message_id or sent=True. Both are
    backend-generated, never inferred from text.
    """
    if _result_says_unverified(result):
        return _failed("email", "tool reported failure", result)
    action = str(args.get("action") or "").lower()
    if action in {"send", "send_message"}:
        if result.get("message_id") or result.get("sent") is True:
            return _ok_evidence("email", "send confirmed",
                                ["message_id", "sent"])
        return _unverifiable("email", "no send confirmation")
    return _ok_evidence("email", "non-send action", [])


def verify_notification(args: dict, result: dict) -> VerifierOutcome:
    """Verify notification creation actions.

    Structural-evidence: id / resource_id / task_name returned by
    the OS scheduler.
    """
    if _result_says_unverified(result):
        return _failed("notification", "tool reported failure", result)
    action = str(args.get("action") or "").lower()
    if action in {"toast_now", "toast_schedule", "timer_start",
                  "alarm_create", "reminder_create"}:
        rid = result.get("id") or result.get("resource_id") or result.get("task_name")
        if rid:
            return _ok_evidence("notification", "resource registered",
                                ["id", "resource_id", "task_name"])
        return _unverifiable("notification", "no id in result")
    return _ok_evidence("notification", "non-creation action", [])


def verify_routine(args: dict, result: dict) -> VerifierOutcome:
    """Verify routine creation actions.

    Structural-evidence: id / resource_id assigned by the
    routine store.
    """
    if _result_says_unverified(result):
        return _failed("routine", "tool reported failure", result)
    action = str(args.get("action") or "").lower()
    if action in {"create"}:
        rid = result.get("id") or result.get("resource_id")
        if rid:
            return _ok_evidence("routine", "routine registered",
                                ["id", "resource_id"])
        return _unverifiable("routine", "create returned no id")
    return _ok_evidence("routine", "non-create action", [])
```

### F3.3 — Registrar

Buscar dónde están los verifiers viejos en el dict de registro:
```bash
grep -n "verify_app\|VERIFIERS\|_VERIFIER" gemma4_agent/verifiers.py | tail
```

Agregar las 5 entries nuevas.

### F3.4 — Tests

Crear `gemma4_agent/test_verifiers_expansion.py`:

```python
"""Tests for the 5 new verifiers (hotfix F 2026-05-17).

Contract: each verifier returns _failed on tool-reported failure,
_unverifiable when evidence absent, _ok_evidence on structural
evidence. NO verifier inspects natural-language text.
"""
from __future__ import annotations

import os
import tempfile
import unittest

from gemma4_agent.verifiers import (
    verify_email,
    verify_media,
    verify_notification,
    verify_office,
    verify_routine,
)


class VerifyMediaTest(unittest.TestCase):
    def test_play_with_auto_play_played_and_verified_is_ok(self) -> None:
        out = verify_media(
            {"action": "play"},
            {"ok": True, "auto_play_info": {"played": True, "verified": True}},
        )
        self.assertEqual(out.kind, "ok")

    def test_play_with_url_but_no_playback_is_unverifiable(self) -> None:
        out = verify_media(
            {"action": "play"},
            {"ok": True, "url": "https://netflix.com/watch/123"},
        )
        self.assertEqual(out.kind, "unverifiable")

    def test_pause_is_ok_when_dispatched(self) -> None:
        out = verify_media({"action": "pause"}, {"ok": True})
        self.assertEqual(out.kind, "ok")


class VerifyOfficeTest(unittest.TestCase):
    def test_create_with_real_path_is_ok(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
            f.write(b"dummy")
            p = f.name
        try:
            out = verify_office(
                {"action": "create_presentation"},
                {"ok": True, "path": p},
            )
            self.assertEqual(out.kind, "ok")
        finally:
            os.unlink(p)

    def test_create_with_missing_path_is_failed(self) -> None:
        out = verify_office(
            {"action": "create_presentation"},
            {"ok": True, "path": r"C:\nonexistent\file.pptx"},
        )
        self.assertEqual(out.kind, "failed")

    def test_create_with_no_path_is_unverifiable(self) -> None:
        out = verify_office(
            {"action": "create_presentation"},
            {"ok": True},
        )
        self.assertEqual(out.kind, "unverifiable")


class VerifyEmailTest(unittest.TestCase):
    def test_send_with_message_id_is_ok(self) -> None:
        out = verify_email(
            {"action": "send"},
            {"ok": True, "message_id": "abc123"},
        )
        self.assertEqual(out.kind, "ok")

    def test_send_without_id_is_unverifiable(self) -> None:
        out = verify_email({"action": "send"}, {"ok": True})
        self.assertEqual(out.kind, "unverifiable")


class VerifyNotificationTest(unittest.TestCase):
    def test_toast_with_task_name_is_ok(self) -> None:
        out = verify_notification(
            {"action": "toast_schedule"},
            {"ok": True, "task_name": "Gemma4Agent\\toast_1"},
        )
        self.assertEqual(out.kind, "ok")


class VerifyRoutineTest(unittest.TestCase):
    def test_create_with_id_is_ok(self) -> None:
        out = verify_routine(
            {"action": "create"},
            {"ok": True, "id": "routine_abc"},
        )
        self.assertEqual(out.kind, "ok")


if __name__ == "__main__":
    unittest.main()
```

Si `VerifierOutcome.kind` no es el atributo correcto (puede ser
`.status`, `.outcome`), ajustá los tests al shape real.

### F3.5 — Commit

`feat(verifiers): add 5 structural-evidence verifiers (media/office/email/notification/routine)`

Mensaje:

```
feat(verifiers): add 5 structural-evidence verifiers

Audit 2026-05-17: only 13/65 tools had post-action verifiers.
The remaining 52 trusted the LLM to honestly report success —
which breaks under 'ok=true, status=dispatched' where the agent
fires-and-forgets.

Fix: 5 new verifiers for high-traffic tools. Each verifies
STRUCTURAL evidence only — paths on the filesystem, message_ids,
resource_ids — never natural-language text. This keeps the
verifiers language-agnostic, which matters because the agent
serves users in many languages.

- verify_media: auto_play_info.played + query_match for streams;
  trust media keys for pause/next/etc.
- verify_office: filesystem check that the returned path exists
  with size > 0 for create/convert.
- verify_email: message_id or sent=True for send.
- verify_notification: id/resource_id/task_name for
  toast/timer/alarm/reminder creation.
- verify_routine: id/resource_id for create.

Each verifier follows the same contract: _failed on tool failure,
_unverifiable on absent evidence, _ok_evidence on present. No new
dependencies. Tests cover the 3 paths per verifier.
```

---

## FIX F4 — Expand intent_validator cross-reject pairs

### F4.1 — Editar `gemma4_agent/intent_validator.py`

Las entries usan verbos abstractos (`close`, `send_email`,
`automate_page`) — agnósticos al idioma del user. Agregar 6
pares más:

```python
CROSS_REJECT_PAIRS: dict[tuple[str, str, str], str] = {
    # ... 6 existing entries ...

    # Hotfix F 2026-05-17 — additional pairs from real bug audit.
    # Each (declared_intent_type, chosen_tool, chosen_action) tuple
    # describes a confused pairing the LLM might emit. Reasons are
    # in English by convention (the prompt's reject reason is
    # visible to the LLM, which speaks all the prompts).
    ("send_email", "whatsapp", "send_message"):
        "Intent is to send EMAIL — whatsapp.send_message uses WhatsApp Desktop/web, not an email client. Use email(action='send').",
    ("send_whatsapp", "email", "send"):
        "Intent is to send a WhatsApp message — email.send opens Outlook/Gmail. Use whatsapp(action='send_message').",
    ("automate_page", "browser", "open"):
        "Intent is to automate a page (click, fill, extract) — browser.open just navigates. Use browser_real.",
    ("just_navigate", "browser_real", "click"):
        "Intent is to just open a URL — browser_real.click requires an attached Playwright session. Use browser(action='open').",
    ("download_file", "filesystem", "copy"):
        "Intent is to download from the web — filesystem.copy only moves between local paths. Use download.",
    ("git_workflow", "terminal", "run"):
        "Intent is a git workflow (commit, push, branch) — prefer developer(action='git_*') for git-aware safety.",
}
```

Y agregar los pares ambiguos:

```python
_AMBIGUOUS_SUBSETS: tuple[tuple[str, str], ...] = (
    ("audio", "window"),
    ("audio", "browser_real"),
    ("audio", "app"),
    ("audio", "media"),
    # Hotfix F:
    ("email", "whatsapp"),
    ("browser", "browser_real"),
    ("filesystem", "download"),
    ("terminal", "developer"),
)
```

### F4.2 — Test

Crear `gemma4_agent/test_intent_validator_expansion.py`:

```python
from __future__ import annotations

import unittest

from gemma4_agent.intent_validator import (
    CROSS_REJECT_PAIRS,
    needs_intent_tag,
)


class IntentValidatorExpansionTest(unittest.TestCase):
    def test_email_whatsapp_pair_triggers_intent_tag(self) -> None:
        self.assertTrue(needs_intent_tag(["email", "whatsapp", "session"]))

    def test_browser_browser_real_pair_triggers_intent_tag(self) -> None:
        self.assertTrue(needs_intent_tag(["browser", "browser_real", "session"]))

    def test_filesystem_download_pair_triggers_intent_tag(self) -> None:
        self.assertTrue(needs_intent_tag(["filesystem", "download", "session"]))

    def test_terminal_developer_pair_triggers_intent_tag(self) -> None:
        self.assertTrue(needs_intent_tag(["terminal", "developer", "session"]))

    def test_send_email_to_whatsapp_send_message_is_rejected(self) -> None:
        reason = CROSS_REJECT_PAIRS.get(("send_email", "whatsapp", "send_message"))
        self.assertIsNotNone(reason)
        self.assertIn("EMAIL", reason)

    def test_just_navigate_with_browser_real_click_is_rejected(self) -> None:
        reason = CROSS_REJECT_PAIRS.get(("just_navigate", "browser_real", "click"))
        self.assertIsNotNone(reason)


if __name__ == "__main__":
    unittest.main()
```

### F4.3 — Commit

`feat(intent-validator): expand cross-reject pairs to email/browser/filesystem/git`

Mensaje:

```
feat(intent-validator): expand cross-reject pairs to email/browser/filesystem/git

Audit 2026-05-17: intent_validator only covered 4 audio-vs-X
pairs. Same-shape confusions for other pairs had zero guard:
email ↔ whatsapp (wrong channel), browser ↔ browser_real
(navigate vs automate), filesystem ↔ download (move vs fetch),
terminal ↔ developer (raw cmd vs git workflow).

Fix:
- 6 new CROSS_REJECT_PAIRS entries covering the 4 pair groups.
- 4 new _AMBIGUOUS_SUBSETS entries so the intent-tag instruction
  fires when those pairs co-occur in a subset.

Intent labels stay in their existing abstract-verb form
(send_email, automate_page, git_workflow) — they describe what
the LLM declared intending to do, not what the user said. So the
validator remains language-agnostic.

Tests pin the new pair contracts.
```

---

## REPORTE FINAL

Devolveme:
1. Hashes de los 4 commits.
2. Output de `python -m pytest gemma4_agent/test_pending_intent.py gemma4_agent/test_verifiers_expansion.py gemma4_agent/test_intent_validator_expansion.py gemma4_agent/test_compact_tool_result_locator_alignment.py -v`.
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`.
4. Smoke del pending intent end-to-end:
   ```python
   from gemma4_agent.router_v2 import route_v2
   # User reply is purely confirmation in any language.
   for q in ['sí', 'yes', 'oui', 'já o tenho', 'ya lo tengo']:
       subset, tel = route_v2(q, pending_tool_hint='steam')
       assert 'steam' in subset, f'{q!r}: missing'
       print(f'{q!r:20s} -> source={tel["source"]:9s} steam in subset')
   ```

## CRITERIO DE ÉXITO

- 4 commits aterrizados.
- ≥10 tests nuevos verdes.
- Suite completa verde (modulo Sprint 3a pre-existing failure).
- El smoke del pending intent muestra que múltiples idiomas
  llegan al mismo subset cuando hay hint.
- `python -m gemma4_agent.launcher status` OK.

## NO HACER (anti-scope)

- NO matchees texto del user para inferir intent. La detección es
  estructural (tool result devuelve `status=needs_user`).
- NO agregues verifiers que parsen texto del result. Solo
  evidencia estructural (paths, IDs, booleans).
- NO inventés trigger types nuevos para `routine` (ya cubierto en
  hotfix D — los 6 trigger types existentes son la fuente de
  verdad).
- NO migres los verifiers a un framework genérico. Las 5 funciones
  explícitas son más fáciles de leer.
- NO toques el comportamiento existente de los 6 cross_reject_pairs
  originales (real bug log backing).
- Si AgentState no tiene un patrón de persistencia simple, NO
  inventés JSON I/O nuevo — usá lo que ya hace `state.save()`.
