# HOTFIX 2026-05-17 (H) — Observability: traced fallbacks + breadcrumb hygiene + v2 calibration

> Continuá el chat post hotfixes E + F + G. Limpieza de deuda
> de observability surfaced en la auditoría: 27 broad-except con
> silent fallback en agent.py, breadcrumbs sin compactación
> posterior, telemetry de voz incompleta, y nueva telemetría para
> la calibración de router_v2 en producción.

---

## Contexto

Auditoría 2026-05-17 + post hotfix E surfaced:

### Bug H1 — 27 broad `except Exception` sin trace en agent.py
```bash
$ grep -cE "except Exception|except BaseException" gemma4_agent/agent.py
27
```

Patrón repetido (`agent.py:219-220`, `:230-232`, `:380`, `:403`,
`:718`, `:725`, `:805`, …):

```python
try:
    from .microagents import build_microagents_section
    microagents_section, ... = build_microagents_section(...)
except Exception:
    microagents_section = ""    # silent: si crashea, el LLM
                                # pierde context y nadie lo sabe.
```

Si cualquiera de estos paths fall, el agente continúa con context
degradado sin log. Para debugging es matador.

### Bug H2 — Breadcrumbs nunca se compactan
Hotfix C+D+E agregaron breadcrumbs `[breadcrumb: k=v ...]` al
`assistant.content`. `_BREADCRUMB_MAX_CHARS=1800`. Pero
`compact_history_content` (en `agent_compaction.py`) NO detecta ni
recorta el patrón. Después de 5 tool calls con tablas, el
assistant content acumula ~9KB de breadcrumbs.

### Bug H3 — Telemetría de voz incompleta
Hotfix E agregó `voice_silent_reject` en el path STT-empty.
Faltan eventos para:
- `wake_word_rejected` (confidence < umbral).
- `wake_word_accepted` (success path — actualmente solo log).
- `tts_started`, `tts_finished` (con duración).

Sin estos, el ciclo "user habla → voice processed → llama-server →
TTS responde" es invisible.

### Bug H4 — Calibración de router_v2 en producción (post hotfix E)
Hotfix E activó router_v2 como autoritativo. Necesitamos
telemetría agregada para validar que funciona bien sobre el uso
real: ¿qué % de turns usa v2? ¿cuánta latencia añade en el hot
path? ¿qué fracción cae al `disabled` source (modelo no
disponible)? ¿qué fracción cae al `cache`?

Esto es **rolling telemetry**, no debugging puntual. Va a un log
agregado que el operator puede inspeccionar al final de cada
sesión.

---

## OBJETIVO

Cuatro commits chicos:

1. `obs(agent)`: convertir 10-15 broad-excepts más críticos en
   trace events. Resto los marcamos como TODO.
2. `fix(history)`: compactar breadcrumbs viejos en
   `compact_history_content` (mantener el último por assistant
   message).
3. `obs(voice)`: agregar 4 trace events más en el pipeline de voz.
4. `obs(routing)`: agregar agregado per-session de v2 usage
   (`router_v2_session_summary` event al final del session) para
   calibración rolling.

---

## REGLAS GENERALES

1. PortandoLoMejor. Commits chicos.
2. NO cambies behavior — solo agregás telemetry / shape-preserving
   compaction.
3. NO toques los 65 schemas, modes.py, planner.py, router_v2.py
   beyond añadir el counter, las rules.
4. Cada trace event debe ser greppable (snake_case prefijo
   distintivo). NO usar el mismo nombre que un evento existente.
5. NO instales libs nuevas.
6. NO `git add -A`.

---

## FIX H1 — Trace events para silent fallbacks críticos

### H1.1 — Identificar los críticos

Los 27 broad-excepts no son iguales. Los **críticos** son los que
degradan context para el LLM (silently). Los **no-críticos** son
los que cae a trace logging que ya está.

Críticos (que sí debemos trazar):
1. `agent.py:219-220` — microagents fail → empty section.
2. `agent.py:230-232` — skills registry fail → no menu.
3. `agent.py:380, :403` — cached prompt blocks fail.
4. `agent.py:688-691` — router_v2 fail (ya parcialmente trazado).
5. `agent.py:718, :725` — semantic suggestion fail.
6. `agent.py:805` — keyword hits fail.
7. `agent.py:825, :847` — LLM retry fails.
8. `agent.py:1040, :1061` — turn cycle fails.

No-críticos (déjalos):
- `agent.py:85` — already logged.
- `agent.py:1484` — already in trace context.
- `agent.py:2016, :2020` — top-level fall-through.

### H1.2 — Patrón de fix

Por cada except crítico, reemplazar el `pass` / asignación vacía
por:

```python
except Exception as _exc:
    self.trace.event(
        self.trace.new_turn_id() if hasattr(self.trace, "new_turn_id") else "agent",
        "silent_fallback",
        component="<microagents|skills|router_v2|...>",
        error=f"{type(_exc).__name__}: {_exc}",
    )
    microagents_section = ""    # original fallback preserved
```

Ejemplo concreto (`agent.py:219`):

```python
try:
    from .microagents import build_microagents_section
    microagents_section, self._cached_microagents = build_microagents_section(
        user_text or "",
        cached=self._cached_microagents,
    )
except Exception as _exc:
    self.trace.event(
        self.trace.new_turn_id() if hasattr(self.trace, "new_turn_id") else "agent",
        "silent_fallback",
        component="microagents",
        error=f"{type(_exc).__name__}: {_exc}",
    )
    microagents_section = ""
```

Aplicalo a los 10-15 más críticos. Los demás:
- Si están en deep-stack paths raros, dejá comment
  `# TODO trace silent fallback (hotfix H follow-up)` para
  visibilidad.

### H1.3 — Test

Crear `gemma4_agent/test_silent_fallback_traced.py`:

```python
"""When a known optional component fails, the agent must emit a
`silent_fallback` trace event instead of silently degrading.

Hotfix H 2026-05-17. The full integration test would require a
heavy AgentRunner ctor; here we smoke-check that the import path
is in place. Manual inspection of the post-fix code is the actual
audit.
"""
from __future__ import annotations

import unittest


class SilentFallbackImportTest(unittest.TestCase):
    def test_agent_module_imports(self) -> None:
        from gemma4_agent.agent import Gemma4Agent  # noqa: F401
        self.assertTrue(True)

    def test_silent_fallback_event_name_is_used(self) -> None:
        # Source-level grep: the event name must exist somewhere
        # in agent.py post-fix. Catches accidental removal.
        import gemma4_agent.agent as _agent
        import inspect
        src = inspect.getsource(_agent)
        self.assertIn(
            "silent_fallback", src,
            "silent_fallback event name not found — H1 regressed?"
        )


if __name__ == "__main__":
    unittest.main()
```

### H1.4 — Commit

`obs(agent): trace silent fallbacks (microagents, skills, router_v2, ...)`

Mensaje:

```
obs(agent): trace silent fallbacks (microagents, skills, router_v2, ...)

agent.py has 27 broad `except Exception` blocks. ~half degrade
context for the LLM if they fire — and they fire silently. Examples:
- microagents.build_microagents_section fail -> empty section.
- skills_registry.scan_skills fail -> no skills menu.
- router_v2 fail -> v1 fallback (already partly traced).
- semantic_router fail -> empty hint list.

Fix: in the 10-15 most context-impacting except blocks, emit a
`silent_fallback` trace event with `component` + `error` fields.
Keeps the existing fallback behavior intact (no behavior change),
just makes debugging tractable. The pattern:

  except Exception as _exc:
      self.trace.event(turn_id, "silent_fallback",
                       component="X", error=str(_exc))
      <existing fallback>

Non-critical fallbacks (top-level catches with existing logging,
deep-stack rare paths) marked with TODO comments for follow-up.

No new dependencies.
```

---

## FIX H2 — Breadcrumb compaction in compact_history_content

### H2.1 — Editar `gemma4_agent/agent_compaction.py`

Localizar `compact_history_content` (línea ~115). Agregar un
helper que detecte múltiples breadcrumbs y mantenga solo el último:

```python
import re

_BREADCRUMB_PATTERN = re.compile(
    r"\n\[breadcrumb:[^\n\]]*\]",
    re.DOTALL,
)


def _compact_old_breadcrumbs(text: str) -> str:
    """Keep only the most recent breadcrumb in an assistant message.

    Hotfix H 2026-05-17. stitch_breadcrumbs (hotfix C+D+E) appends
    to assistant.content. Repeated compactions stack breadcrumbs
    indefinitely — observed ~9KB accumulated after 5 tool-call
    turns. Older breadcrumbs collapse to a single placeholder so
    the LLM still knows historical context existed but doesn't
    get spammed.
    """
    matches = list(_BREADCRUMB_PATTERN.finditer(text))
    if len(matches) <= 1:
        return text
    last = matches[-1]
    placeholder = "\n[breadcrumb: ...older breadcrumbs collapsed...]"
    head = text[:matches[0].start()]
    return head + placeholder + last.group(0) + text[last.end():]
```

Y dentro de `compact_history_content`:

```python
def compact_history_content(content: Any) -> str:
    if isinstance(content, str):
        text = _compact_old_breadcrumbs(content)
        return middle_ellipsis(text, HISTORY_TEXT_LIMIT)
    if isinstance(content, list):
        parts: list[str] = []
        omitted_media = 0
        for item in content:
            ...
        joined = "\n".join(parts).strip() + suffix
        joined = _compact_old_breadcrumbs(joined)
        return middle_ellipsis(joined, HISTORY_TEXT_LIMIT)
    text = _compact_old_breadcrumbs(str(content or ""))
    return middle_ellipsis(text, HISTORY_TEXT_LIMIT)
```

### H2.2 — Test

Crear `gemma4_agent/test_history_breadcrumb_compaction.py`:

```python
"""Breadcrumbs accumulate over repeated compactions. Keep only the
most recent one per assistant message to avoid context inflation.

Hotfix H 2026-05-17.
"""
from __future__ import annotations

import unittest

from gemma4_agent.agent_compaction import compact_history_content


class BreadcrumbCompactionTest(unittest.TestCase):
    def test_single_breadcrumb_preserved(self) -> None:
        text = "Listo, abrí spotify.\n[breadcrumb: url=https://spotify.com/track/abc]"
        out = compact_history_content(text)
        self.assertIn("url=https://spotify.com/track/abc", out)

    def test_multiple_breadcrumbs_collapsed(self) -> None:
        text = (
            "Listo.\n"
            "[breadcrumb: path=C:\\a.pptx]\n"
            "[breadcrumb: path=C:\\b.pptx]\n"
            "[breadcrumb: url=https://example.com/latest]"
        )
        out = compact_history_content(text)
        self.assertIn("url=https://example.com/latest", out)
        self.assertIn("collapsed", out)
        self.assertNotIn("a.pptx", out)
        self.assertNotIn("b.pptx", out)

    def test_no_breadcrumb_is_no_op(self) -> None:
        text = "Listo, hecho."
        out = compact_history_content(text)
        self.assertEqual(out.strip(), "Listo, hecho.")


if __name__ == "__main__":
    unittest.main()
```

### H2.3 — Commit

`fix(history): collapse stacked breadcrumbs in compact_history_content`

Mensaje:

```
fix(history): collapse stacked breadcrumbs in compact_history_content

Breadcrumbs added by stitch_breadcrumbs (hotfix C+D+E) live in
assistant.content and never get compacted by
compact_history_content. After 5 tool-call turns the assistant
content accumulated ~9KB of stacked breadcrumbs.

Fix: in compact_history_content, detect `\n[breadcrumb: ...]`
patterns and keep only the last match per message. Older
breadcrumbs collapse to a single placeholder
`[breadcrumb: ...older breadcrumbs collapsed...]` so the LLM
knows historical context existed but doesn't get spammed.

Idempotent: a message with 0 or 1 breadcrumb is unchanged. A
message with N>=2 breadcrumbs gets head + placeholder + last
breadcrumb + tail.

Tests cover single (preserved), multiple (collapsed), and
no-breadcrumb (no-op).
```

---

## FIX H3 — Voice pipeline trace events

### H3.1 — Editar `gemma4_agent/voice/wake.py` y controller.py

Localizar la sección de wake-word detection:
```bash
grep -n "WAKE_MIN_CONFIDENCE\|wake.*detected" gemma4_agent/voice/wake.py gemma4_agent/voice/controller.py
```

En el path donde wake-word es accepted/rejected, emitir:

```python
# Wake accepted:
self.trace.event(
    self.trace.new_turn_id() if hasattr(self.trace, "new_turn_id") else "voice",
    "wake_word_accepted",
    confidence=conf,
)

# Wake rejected:
self.trace.event(
    ...,
    "wake_word_rejected",
    confidence=conf,
    threshold=WAKE_MIN_CONFIDENCE,
)
```

NO emitas el contenido transcripto del wake-word
(`detected_phrase`) — eso entra en territorio "log user audio
content", queremos solo el signal estructural (confidence,
threshold).

(Si `wake.py` no tiene acceso a trace, pasar el logger / event
emitter como dep siguiendo el patrón del controller. Si requiere
refactor pesado, escala a `logger.warning("wake_word_accepted
conf=%.2f", conf)` greppable.)

### H3.2 — Editar `gemma4_agent/voice/tts.py`

En los bordes de TTS playback:
```python
# tts_started:
self.trace.event(turn_id, "tts_started", text_len=len(text))
# tts_finished:
self.trace.event(turn_id, "tts_finished", duration_s=dur)
```

(Si tts.py corre en otro thread / proceso, escala a `logger.warning`
greppable — más simple que cablear trace cross-thread.)

### H3.3 — Test

No es práctico testear voice telemetry sin mock pesado. Documentá
en el commit body que el test es manual:

```bash
# Post-fix, abrir una session con voz y verificar los eventos:
$ grep -E "wake_word_(accepted|rejected)|tts_(started|finished)" ~/.gemma4/logs/_pre_session/full.log
```

### H3.4 — Commit

`obs(voice): trace wake_word_accepted/rejected + tts_started/finished`

Mensaje:

```
obs(voice): trace wake_word_accepted/rejected + tts_started/finished

Audit 2026-05-17: voice_e2e_latency was the only voice trace event.
Hotfix E added voice_silent_reject. Still missing: wake detection
outcomes and TTS lifecycle.

When the user reports 'Gemma está lento' or 'no me escucha', we
have only the start (wake) and end (e2e_latency) signal. Mid-
pipeline events (wake_accepted, wake_rejected, tts_started,
tts_finished) let us localize the latency contributor or rejection
reason.

Fix:
- voice/wake.py: emit wake_word_accepted (success) and
  wake_word_rejected (confidence < WAKE_MIN_CONFIDENCE) trace
  events with confidence + threshold values. Deliberately NOT
  including the detected phrase content (privacy boundary).
- voice/tts.py: emit tts_started (text_len) and tts_finished
  (duration_s) at the boundaries of TTS playback.

No new dependencies. Manual test: open a voice session, grep
~/.gemma4/logs/_pre_session/full.log for the 4 new event kinds.
```

---

## FIX H4 — router_v2 session-summary telemetry

### H4.1 — Editar `gemma4_agent/router_v2.py`

Agregar contadores process-singleton:

```python
class RouterV2:
    ...

    def __init__(self) -> None:
        ...
        # Session-summary counters (hotfix H 2026-05-17). Reset
        # per process; the launcher emits a summary on shutdown
        # so we can track v2 health over real sessions.
        self._counters: dict[str, int] = {
            "calls_total": 0,
            "source_cache": 0,
            "source_smalltalk": 0,
            "source_hybrid": 0,
            "source_empty_query": 0,
            "source_disabled": 0,
            "fallback_applied": 0,
            "pending_tool_injected": 0,
            "load_failed": 0,
        }
        self._latency_ms_sum: float = 0.0
        self._latency_ms_max: float = 0.0

    def session_summary(self) -> dict[str, Any]:
        """Return aggregated stats since process start."""
        calls = max(1, self._counters["calls_total"])
        return {
            **self._counters,
            "latency_ms_avg": round(self._latency_ms_sum / calls, 2),
            "latency_ms_max": round(self._latency_ms_max, 2),
        }
```

Y dentro de `route()`, después del telemetry final:

```python
self._counters["calls_total"] += 1
src = str(telemetry.get("source") or "unknown")
key = f"source_{src}"
if key in self._counters:
    self._counters[key] += 1
if telemetry.get("fallback_applied"):
    self._counters["fallback_applied"] += 1
if telemetry.get("pending_tool_injected"):
    self._counters["pending_tool_injected"] += 1
elapsed = float(telemetry.get("elapsed_ms") or 0.0)
self._latency_ms_sum += elapsed
self._latency_ms_max = max(self._latency_ms_max, elapsed)
```

(Cuando el router está en `disabled` state porque
`_ensure_loaded()` falló, contá esa rama también: incrementá
`load_failed` UNA vez por proceso, no por call.)

### H4.2 — Emitir el summary desde el launcher

En `gemma4_agent/launcher.py`, agregar el shutdown hook:

```python
def _emit_router_v2_summary() -> None:
    """Best-effort: log the v2 session summary on shutdown."""
    try:
        from .router_v2 import RouterV2
        router = RouterV2._instance
        if router is None:
            return
        summary = router.session_summary()
        print(f"router_v2_session_summary {summary}")
    except Exception:
        pass

# Registrar en el path de shutdown del launcher (atexit, signal
# handler, o el bloque finally del run loop — lo que ya use el
# launcher).
import atexit
atexit.register(_emit_router_v2_summary)
```

### H4.3 — Test

Crear `gemma4_agent/test_router_v2_counters.py`:

```python
"""router_v2 maintains per-process counters for calibration
telemetry (hotfix H 2026-05-17).

Skips integration assertions when model is absent.
"""
from __future__ import annotations

import unittest

from gemma4_agent.router_v2 import MODEL_PATH, RouterV2


@unittest.skipUnless(MODEL_PATH.exists(), "e5-small ONNX model not installed")
class RouterV2CountersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        RouterV2.reset()
        cls.router = RouterV2.get()
        if not cls.router._ensure_loaded():
            raise unittest.SkipTest(cls.router._load_error)

    def test_counters_increment_on_each_call(self) -> None:
        baseline = self.router._counters["calls_total"]
        self.router.route("hola")
        self.router.route("apaga la pc")
        self.assertGreaterEqual(self.router._counters["calls_total"], baseline + 2)

    def test_summary_returns_dict_with_latency(self) -> None:
        self.router.route("hola")
        summary = self.router.session_summary()
        self.assertIn("calls_total", summary)
        self.assertIn("latency_ms_avg", summary)
        self.assertIn("latency_ms_max", summary)

    def test_source_counters_distinguish_smalltalk_vs_hybrid(self) -> None:
        RouterV2.reset()
        router = RouterV2.get()
        router._ensure_loaded()
        router.route("hola")  # smalltalk
        router.route("abrime el steam")  # hybrid
        s = router.session_summary()
        self.assertGreaterEqual(s["source_smalltalk"], 1)
        self.assertGreaterEqual(s["source_hybrid"] + s["source_cache"], 1)


if __name__ == "__main__":
    unittest.main()
```

### H4.4 — Commit

`obs(routing): per-process counters + session_summary for router_v2 calibration`

Mensaje:

```
obs(routing): per-process counters + session_summary for router_v2 calibration

Hotfix E activated router_v2 as the authoritative router. To
validate calibration on real production usage we need rolling
telemetry: what fraction of turns hit cache vs hybrid vs
smalltalk, how often does the fallback_applied path fire, what's
the p50/max latency on the hot path.

Fix: RouterV2 maintains per-process counters incremented in
route(). New method session_summary() returns the aggregated dict.
The launcher's shutdown hook (atexit) emits a
'router_v2_session_summary' log line so operators can grep it at
the end of each session without instrumenting individual turns.

Counters tracked:
  calls_total, source_{cache,smalltalk,hybrid,empty_query,disabled},
  fallback_applied, pending_tool_injected, load_failed,
  latency_ms_{avg,max}.

Tests skip when the model is absent (CI without bootstrap).
```

---

## REPORTE FINAL

Devolveme:
1. Hashes de los 4 commits.
2. Output de `python -m pytest gemma4_agent/test_history_breadcrumb_compaction.py gemma4_agent/test_silent_fallback_traced.py gemma4_agent/test_router_v2_counters.py -v`.
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`.
4. Output del breadcrumb compaction smoke:
   ```python
   from gemma4_agent.agent_compaction import compact_history_content
   text = ("Listo.\n"
           "[breadcrumb: path=C:\\a.pptx]\n"
           "[breadcrumb: path=C:\\b.pptx]\n"
           "[breadcrumb: url=https://example.com/latest]")
   print(compact_history_content(text))
   ```
5. Output del summary del router_v2 después de unas calls:
   ```python
   from gemma4_agent.router_v2 import RouterV2, route_v2
   RouterV2.reset()
   for q in ['hola', 'abrime el steam', 'que hora es', 'pone benson boone']:
       route_v2(q)
   print(RouterV2.get().session_summary())
   ```

## CRITERIO DE ÉXITO

- 4 commits aterrizados.
- Tests verdes.
- Suite completa verde (modulo Sprint 3a pre-existing failure).
- `python -m gemma4_agent.launcher status` OK.
- Breadcrumb compaction smoke devuelve solo la URL más reciente
  + placeholder.
- session_summary devuelve dict con counters > 0 y latency real.

## NO HACER (anti-scope)

- NO conviertas TODOS los 27 broad-excepts en una pasada — 10-15
  críticos es suficiente este sprint. Resto marcado con TODO.
- NO migres trace.event() a structured logging — el shape JSONL
  actual es el que tooling consume.
- NO toques `agent.run_content`'s main loop — solo los except
  blocks puntuales.
- NO inflas el breadcrumb placeholder con más info
  ("collapsed N from turn X-Y") — el minimal placeholder es
  suficiente.
- Si la inyección de trace en wake.py / tts.py requiere refactor
  pesado, escala a logger.warning() greppable.
- NO incluyas content del wake-word phrase ni del audio en
  trace events — solo signals estructurales (confidence,
  threshold, duration). Privacy boundary.
- NO emitas `router_v2_session_summary` por turn — solo en
  shutdown (atexit). Per-turn telemetry ya existe en el evento
  `router_v2`.
