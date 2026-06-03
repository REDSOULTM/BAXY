# HOTFIX 2026-05-17 (E) — Activar router_v2 como default + voice telemetry + tabular keys

> Continuá el chat de Claude Code (Sprints 0-8b + voice fixes
> 795f7a6/b38ec32 + hotfixes A `c1531a1`, B `2410cce`, C
> `aad741e`/`6f6d8c6`/`bb59fb4`/`2f8a1a4`, D `113ca8b`/`0cf50a0`/
> `d274752`/`2d2f3cb`/`a666781`).
>
> La auditoría del 2026-05-17 surfaceó que el **planner regex-based
> de Sprint 3a sigue siendo el path autoritativo de routing**, y
> que router_v2 (Sprint 8a/8b — e5-small multilingual int8 + BM25
> + Tool2Vec descriptions) está OFF por default. La raíz de los
> bugs P0 de routing no es "faltan más regex": es que el sistema
> NO USA el router que ya construimos. Sprint 8c estaba planeado
> para hacer la activación; este hotfix lo ejecuta y consolida
> los arreglos de voice + history alrededor.

---

## Por qué Sprint E NO es "más regex"

`gemma4_agent` debe servir a **usuarios que hablan de cualquier
forma** — voseo argentino, español neutro, inglés, portugués,
francés, italiano, alemán, y cualquier mezcla. La auditoría
detectó casos como:

```
>>> select_tool_names('instala vlc', plan_mission('instala vlc'))
['session']

>>> select_tool_names('apaga la pc', ...)
['session']

>>> select_tool_names('pone benson boone', ...)
['session']
```

La tentación es agregar más buckets regex (`apaga|reinicia|...`,
`pone|reproduce|...`). Eso es deuda: cada usuario nuevo trae una
variante que no está en el regex, y la deuda crece con cada
idioma/dialecto.

**El fix correcto es activar router_v2**, que para esto fue
construido:
- e5-small int8 ONNX, 100 idiomas, cross-lingual alignment.
- BM25 sobre `tool_descriptions.yaml` (Sprint 8b) con
  `example_queries` ES + EN que incluyen voseo y formas coloquiales.
- Smalltalk gate calibrado por **delta** entre centroides
  (no por keyword list).
- Telemetría completa (`router_v2` trace event) ya wired y testeado
  contra los 27 tests de `test_router_v2.py`.

Los 4 bugs P0 que la auditoría documentó se resuelven cuando
router_v2 es el path autoritativo:

| Query | v1 (regex) actual | v2 (semantic) |
|---|---|---|
| `instala vlc` | `['session']` ❌ | `package` en top-K ✓ |
| `apaga la pc` | `['session']` ❌ | `system` en top-K ✓ |
| `pone benson boone` | `['session']` ❌ | `media` en top-K ✓ |
| `gracias por todo` | `['notes_tasks', ...]` ❌ (regex matches "todo") | smalltalk gate, `[]` ✓ |
| `ouvre chrome` (FR) | suerte (no es ES+EN) | `browser` ✓ |
| `öffne das Steam-Spiel` (DE) | no match | `steam` ✓ |

Esto NO se logra con regex; se logra con un router multilingual
que ya tenemos y solo necesita ser activado con calibración real
de producción.

---

## OBJETIVO DEL HOTFIX

Cinco commits chicos. Tres son la activación de router_v2; dos
son la cosecha de bugs independientes que la auditoría surfaceó
(voice telemetry, breadcrumb tabular keys).

1. `feat(routing)`: correr router_v2 en **shadow mode permanente**
   (default ON) durante este hotfix, recolectando un mínimo de
   comparativos contra v1 con telemetry estructurada.
2. `feat(routing)`: pre-flight del bootstrap automático. Si
   `~/.gemma4/models/e5-small/` no existe, el launcher lo
   descarga en el primer arranque (idempotente). Eliminamos el
   step manual del path-a-producción.
3. `feat(routing)`: activar router_v2 como **default** cuando el
   modelo está presente. v1 queda como fallback automático si
   v2 falla a cargar. Flag inverso `GEMMA4_ROUTER_V1_ONLY=1`
   para forzar v1 (debugging).
4. `fix(voice)`: emitir `voice_silent_reject` trace event en los
   2 paths VAD del STT (`no_speech`, `too_short`).
5. `fix(history)`: extender `_TABULAR_KEYS` con 8 keys más
   observadas en tool outputs reales.

---

## REGLAS GENERALES

1. PortandoLoMejor. Commits chicos, prefijos `feat(routing):`,
   `fix(voice):`, `fix(history):`.
2. **NO toques** el planner regex (`_suggest_tools` en
   `planner.py:212+`). Sigue siendo el fallback determinístico
   cuando v2 no carga. La idea NO es borrarlo este sprint —
   queda como red de seguridad hasta confirmar v2 estable en uso real.
3. NO toques modes.py, voice/controller.py beyond el trace event,
   tool_descriptions.yaml (ya está completo en Sprint 8b),
   tool_schemas.py, las 65 compound tools.
4. NO instales libs nuevas. Todas las deps de router_v2 ya están
   (onnxruntime, tokenizers, rank-bm25, huggingface_hub).
5. NO `git add -A`.
6. Verificación post-commit:
   - `python -m pytest gemma4_agent/ -q` debe pasar (~849 +
     nuevos, 1 pre-existing failure).
   - `python -m gemma4_agent.launcher status` corre.
   - `python -m pytest gemma4_agent/test_router_v2.py -q` (27 tests
     existentes deben seguir verdes).

---

## FIX E1 — Shadow mode por default

### E1.1 — Editar `gemma4_agent/router_v2.py`

Localizar `is_shadow()`:
```python
def is_shadow() -> bool:
    raw = (os.environ.get("GEMMA4_ROUTER_V2_SHADOW") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}
```

Cambiar a **default ON** cuando el modelo está disponible:
```python
def is_shadow() -> bool:
    """Shadow mode logs how v2 would route without changing v1's pick.

    Default behavior (hotfix E 2026-05-17): shadow is ON whenever
    the e5-small model is on disk AND GEMMA4_ROUTER_V2_SHADOW is
    not explicitly '0' / 'false' / 'off'. Operator can disable
    with GEMMA4_ROUTER_V2_SHADOW=0 if shadow logging itself causes
    problems.
    """
    raw = (os.environ.get("GEMMA4_ROUTER_V2_SHADOW") or "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    # Default: shadow is ON if the model is available (model_path exists
    # AND the singleton can be loaded). The check is cheap because the
    # singleton is lazy; we only test MODEL_PATH.
    return MODEL_PATH.exists()
```

### E1.2 — Tests

Actualizar `gemma4_agent/test_router_v2.py::EnvFlagsTest`:

```python
def test_is_shadow_default_when_model_present(self) -> None:
    """Without an explicit env, shadow defaults to ON if model
    is on disk. Skip when the model isn't there (CI machines)."""
    old = os.environ.pop("GEMMA4_ROUTER_V2_SHADOW", None)
    try:
        if MODEL_PATH.exists():
            self.assertTrue(is_shadow(),
                            "shadow should default ON when model present")
        else:
            self.assertFalse(is_shadow(),
                             "shadow should default OFF when model absent")
    finally:
        if old is not None:
            os.environ["GEMMA4_ROUTER_V2_SHADOW"] = old

def test_is_shadow_explicit_off_overrides_default(self) -> None:
    old = os.environ.get("GEMMA4_ROUTER_V2_SHADOW")
    os.environ["GEMMA4_ROUTER_V2_SHADOW"] = "0"
    try:
        self.assertFalse(is_shadow())
    finally:
        if old is None:
            os.environ.pop("GEMMA4_ROUTER_V2_SHADOW", None)
        else:
            os.environ["GEMMA4_ROUTER_V2_SHADOW"] = old
```

(Y modificá el `test_is_shadow_false_without_env` existente — no
seguirá valiendo en máquinas con modelo presente.)

### E1.3 — Commit

`feat(routing): default router_v2 shadow ON when model is available`

Mensaje:

```
feat(routing): default router_v2 shadow ON when model is available

Audit 2026-05-17: router_v2 (Sprint 8a) was OFF by default; both
GEMMA4_ROUTER_V2 and GEMMA4_ROUTER_V2_SHADOW required explicit
opt-in. As a result, every user ran the v1 planner regex (ES+EN
keyword buckets) as the authoritative routing path, with v2
producing no telemetry. The audit could not measure v1-vs-v2
agreement on real queries because nobody had ever enabled shadow.

Fix: is_shadow() now defaults to True when MODEL_PATH exists.
Operator can disable with GEMMA4_ROUTER_V2_SHADOW=0/false/off.
Shadow mode itself does not change behavior — it only emits the
'router_v2' trace event with v2's subset alongside v1's, so we
collect comparison data passively. This is preparation for E3
which makes v2 authoritative.

Pure flag default change. Existing 27 tests in test_router_v2.py
remain green; 2 new EnvFlagsTest cases pin the new contract.
```

---

## FIX E2 — Automatic bootstrap on first launch

### E2.1 — Inspeccionar el launcher

```bash
grep -n "def status\|def start\|bootstrap_e5_small\|MODEL_PATH" gemma4_agent/launcher.py
```

### E2.2 — Editar `gemma4_agent/launcher.py`

Localizar el `start` / `run` command. ANTES de que arranque
llama-server, hacer un pre-flight que descargue e5-small si no
está. Patrón:

```python
def _ensure_router_v2_model() -> None:
    """Idempotent: download e5-small ONNX + tokenizer + smalltalk
    centroid on first launch. ~113 MB int8 model.

    Hotfix E 2026-05-17. The previous path-to-production required
    the user to run scripts/bootstrap_e5_small.py manually. That
    step is now automated — if MODEL_PATH doesn't exist, the
    launcher invokes the same bootstrap script before starting.
    Already-installed models are detected by checking MODEL_PATH;
    re-runs print 'already complete' and return in <1s.

    Errors during bootstrap log a warning but do NOT block the
    launcher — v1 is still a valid fallback path.
    """
    try:
        from .router_v2 import MODEL_PATH
        if MODEL_PATH.exists():
            return  # already installed
        # Print a one-line notice so the user sees the network
        # activity. ~113 MB on a fresh machine.
        print(
            "First-run router_v2 bootstrap: downloading e5-small "
            "(~113 MB, multilingual int8 ONNX) to ~/.gemma4/models/e5-small/. "
            "This happens once."
        )
        from scripts.bootstrap_e5_small import main as bootstrap_main
        bootstrap_main()
    except Exception as exc:
        # Non-fatal: v1 router will still serve traffic.
        print(f"router_v2 bootstrap failed ({exc}); falling back to v1 routing.")
```

Llamar a esto desde `start` (no desde `status`) — `status` solo
inspecciona, no debe iniciar descargas.

Si `scripts/bootstrap_e5_small.py` no expone una función `main()`,
abrílo y refactorialo para que sí — el grueso del trabajo es:

```python
# scripts/bootstrap_e5_small.py
def main() -> int:
    ...  # existing body
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

### E2.3 — Test

Crear `gemma4_agent/test_launcher_bootstrap.py`:

```python
"""The launcher's start() command must call the router_v2 bootstrap
helper exactly once when the model is missing, and skip when it's
already present.

Hotfix E 2026-05-17.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class LauncherBootstrapTest(unittest.TestCase):
    def test_bootstrap_skipped_when_model_present(self) -> None:
        from gemma4_agent.launcher import _ensure_router_v2_model
        with patch("gemma4_agent.router_v2.MODEL_PATH") as mock_path:
            mock_path.exists.return_value = True
            with patch("scripts.bootstrap_e5_small.main") as mock_main:
                _ensure_router_v2_model()
                mock_main.assert_not_called()

    def test_bootstrap_invoked_when_model_absent(self) -> None:
        from gemma4_agent.launcher import _ensure_router_v2_model
        with patch("gemma4_agent.router_v2.MODEL_PATH") as mock_path:
            mock_path.exists.return_value = False
            with patch("scripts.bootstrap_e5_small.main") as mock_main:
                mock_main.return_value = 0
                _ensure_router_v2_model()
                mock_main.assert_called_once()

    def test_bootstrap_failure_does_not_raise(self) -> None:
        # If bootstrap raises, the launcher must continue (v1 fallback).
        from gemma4_agent.launcher import _ensure_router_v2_model
        with patch("gemma4_agent.router_v2.MODEL_PATH") as mock_path:
            mock_path.exists.return_value = False
            with patch("scripts.bootstrap_e5_small.main",
                       side_effect=RuntimeError("network")):
                # Should NOT raise.
                _ensure_router_v2_model()


if __name__ == "__main__":
    unittest.main()
```

### E2.4 — Commit

`feat(routing): auto-bootstrap e5-small model on first launcher start`

Mensaje:

```
feat(routing): auto-bootstrap e5-small model on first launcher start

Removes the manual step from the path-to-production. Previously,
to enable router_v2 the user had to:
  1. python scripts/bootstrap_e5_small.py
  2. set GEMMA4_ROUTER_V2_SHADOW=1
  3. restart launcher

That friction kept router_v2 OFF on every install. Audit 2026-05-17
confirmed: zero shadow-mode telemetry collected in 1+ week despite
the infra being shipped Sprint 8a.

Fix: launcher.start() runs _ensure_router_v2_model() as a pre-
flight. If MODEL_PATH exists, no-op. If not, invoke
scripts.bootstrap_e5_small.main() which downloads the ~113 MB int8
ONNX + tokenizer + configs idempotently. Failures are non-fatal —
v1 routing keeps working as fallback.

Refactor: scripts/bootstrap_e5_small.py now exposes main() as a
function (was script-only). The __main__ guard still runs it.

Tests cover the 3 paths: skip when present, invoke when absent,
swallow failures without raising.
```

---

## FIX E3 — Promote router_v2 to authoritative default

### E3.1 — Editar `gemma4_agent/router_v2.py`

Localizar `is_enabled()`:
```python
def is_enabled() -> bool:
    raw = (os.environ.get("GEMMA4_ROUTER_V2") or "").strip().lower()
    if raw not in {"1", "true", "yes", "on"}:
        return False
    return RouterV2.get().is_available()
```

Cambiar a **default ON cuando el modelo está disponible**, con un
flag inverso `GEMMA4_ROUTER_V1_ONLY` para forzar el camino viejo
(debugging):

```python
def is_enabled() -> bool:
    """v2 is the authoritative router by default when the model is
    available (hotfix E 2026-05-17, Sprint 8c activation).

    Operator controls:
      GEMMA4_ROUTER_V1_ONLY=1   -> force v1 (regex planner) only.
      GEMMA4_ROUTER_V2=0/false  -> same effect; explicit.
      <unset> + model present   -> v2 is authoritative.
      <unset> + model absent    -> v1 fallback automatically.

    If router_v2 fails to load (sticky _load_failed), v1 is the
    automatic fallback — no env var needed.
    """
    v1_only = (os.environ.get("GEMMA4_ROUTER_V1_ONLY") or "").strip().lower()
    if v1_only in {"1", "true", "yes", "on"}:
        return False
    explicit = (os.environ.get("GEMMA4_ROUTER_V2") or "").strip().lower()
    if explicit in {"0", "false", "no", "off"}:
        return False
    if explicit in {"1", "true", "yes", "on"}:
        return RouterV2.get().is_available()
    # Default: enabled if the model is on disk AND the singleton
    # is healthy. RouterV2.get().is_available() is cheap when the
    # singleton is already loaded.
    return RouterV2.get().is_available()
```

### E3.2 — Editar `gemma4_agent/agent.py:670-687`

El bloque actual (Sprint 8a) trata `_v2_on` y `_shadow` como
mutuamente excluyentes, con shadow ganando si `_v2_on` está OFF.
Después del cambio de E1+E3, el comportamiento natural sería:

- `is_enabled()` True + `is_shadow()` True/False → v2 autoritativo
  (la observación SHADOW pierde sentido cuando v2 ya manda).
- `is_enabled()` False + `is_shadow()` True → v1 autoritativo,
  v2 logueado para comparación.
- `is_enabled()` False + `is_shadow()` False → v1 autoritativo,
  v2 no se invoca.

Simplificá:

```python
try:
    from .router_v2 import is_enabled as _v2_enabled, is_shadow as _v2_shadow, route_v2
    _v2_on = _v2_enabled()
    _shadow = (not _v2_on) and _v2_shadow()  # shadow only when v1 still authoritative
    if _v2_on or _shadow:
        _v2_subset, _v2_telemetry = route_v2(raw_text_early or "")
        self.trace.event(
            turn_id, "router_v2",
            authoritative=_v2_on,
            shadow=_shadow,
            v2_subset=list(_v2_subset),
            v1_subset=list(selected_tool_names),
            agreement=sorted(set(_v2_subset) & set(selected_tool_names)),
            disagreement_v2_only=sorted(set(_v2_subset) - set(selected_tool_names)),
            disagreement_v1_only=sorted(set(selected_tool_names) - set(_v2_subset)),
            **_v2_telemetry,
        )
        if _v2_on:
            selected_tool_names = list(_v2_subset)
except Exception as _v2_exc:  # noqa: BLE001 — never break a turn
    try:
        self.trace.event(turn_id, "router_v2_error", error=str(_v2_exc))
    except Exception:
        pass
```

### E3.3 — Asegurar que el v1-fallback funciona cuando v2 falla a cargar

Si `RouterV2.get().is_available()` devuelve False (modelo ausente,
ONNX corrupto, tokenizer faltante), `is_enabled()` también
devuelve False. Eso significa que `selected_tool_names` queda con
el output del planner v1 — lo cual está bien.

PERO: el code-path de v1 (planner.select_tool_names) **debe seguir
intacto**. NO removamos los keyword buckets ni el semantic
fallback del planner v1 en este sprint. Esa migración va más
adelante cuando confirmemos que v2 manda bien en producción
durante 1-2 semanas. El planner regex queda como **plan B
determinístico**, no como deuda permanente.

### E3.4 — Smoke tests de los 4 repros de la auditoría

Crear `gemma4_agent/test_routing_audit_repros.py`:

```python
"""End-to-end smoke tests for the 4 audit-day routing failures.

Hotfix E 2026-05-17. These queries were collapsing to ['session']
or wrong tools under v1's regex planner. With router_v2 as
authoritative default, they should land in the right subset
regardless of dialect or language.

We test the v2 path DIRECTLY (route_v2) rather than going through
the full agent dispatch. If the model isn't available locally, we
skip — these are integration tests, not unit tests.
"""
from __future__ import annotations

import unittest

from gemma4_agent.router_v2 import MODEL_PATH, RouterV2, route_v2


_HAS_MODEL = MODEL_PATH.exists()


@unittest.skipUnless(_HAS_MODEL, "e5-small ONNX model not installed")
class AuditReprosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        RouterV2.reset()
        router = RouterV2.get()
        if not router._ensure_loaded():
            raise unittest.SkipTest(router._load_error)

    def _assert_tool_in_topk(self, query: str, expected_tool: str) -> None:
        subset, telemetry = route_v2(query)
        if telemetry.get("source") == "smalltalk":
            # smalltalk gate fired — only OK if we EXPECTED no tool.
            self.fail(f"{query!r}: smalltalk gate fired, expected {expected_tool}")
        self.assertIn(
            expected_tool, subset,
            f"{query!r}: expected {expected_tool} in subset, "
            f"got {subset[:8]} (telemetry={telemetry.get('source')})",
        )

    def test_install_app_es(self) -> None:
        self._assert_tool_in_topk("instala vlc", "package")

    def test_install_app_voseo(self) -> None:
        self._assert_tool_in_topk("instalame vlc", "package")

    def test_install_app_en(self) -> None:
        self._assert_tool_in_topk("install vlc", "package")

    def test_power_off_es(self) -> None:
        self._assert_tool_in_topk("apaga la pc", "system")

    def test_power_off_voseo(self) -> None:
        self._assert_tool_in_topk("apagame la pc", "system")

    def test_play_music_es(self) -> None:
        self._assert_tool_in_topk("pone benson boone", "media")

    def test_play_music_en(self) -> None:
        self._assert_tool_in_topk("play benson boone", "media")

    def test_play_music_fr(self) -> None:
        # Cross-lingual: French. e5-small is multilingual; we expect
        # this to land on media even without explicit FR queries in
        # the YAML.
        self._assert_tool_in_topk("mets benson boone", "media")

    def test_gracias_por_todo_does_not_route_to_notes(self) -> None:
        # 'todo' regex false positive in v1. v2 should treat this
        # as smalltalk (smalltalk gate) — no tool subset.
        subset, telemetry = route_v2("gracias por todo")
        self.assertNotIn("notes_tasks", subset,
                         f"got {subset}; smalltalk gate should have fired "
                         f"or notes_tasks should not have been picked")

    def test_open_chrome_fr(self) -> None:
        # Cross-lingual French: 'ouvre chrome' should hit browser.
        self._assert_tool_in_topk("ouvre chrome", "browser")

    def test_open_chrome_de(self) -> None:
        self._assert_tool_in_topk("öffne chrome", "browser")


if __name__ == "__main__":
    unittest.main()
```

### E3.5 — Commit

`feat(routing): make router_v2 the authoritative default (Sprint 8c activation)`

Mensaje:

```
feat(routing): make router_v2 the authoritative default

This is Sprint 8c activation. Audit 2026-05-17 confirmed v1's
regex planner collapses to ['session'] for short commands that
don't match its ES+EN keyword list ('instala vlc', 'apaga la pc',
'pone benson boone'). Adding more regex would be language-specific
debt; the right fix is to use router_v2 which we already built
(Sprint 8a) and enriched with Tool2Vec descriptions (Sprint 8b).

is_enabled() now defaults ON when the e5-small model is available
and not explicitly disabled via GEMMA4_ROUTER_V1_ONLY=1 or
GEMMA4_ROUTER_V2=0. If the model fails to load (corrupt, missing
after bootstrap), the singleton's sticky _load_failed flag flips
is_available() to False and v1 (the regex planner) becomes the
automatic fallback — no operator intervention needed.

The agent.py wiring is simplified: shadow mode is now ONLY active
when v1 is authoritative (i.e., the model is unavailable). When v2
is authoritative, the same router_v2 trace event still emits with
authoritative=True for telemetry continuity.

The v1 planner code is intentionally left intact as the deterministic
fallback path. It will be re-evaluated for removal after v2 proves
stable in production over 1-2 weeks.

Smoke tests in test_routing_audit_repros.py pin the 4 audit-day
failures + cross-lingual coverage (FR 'ouvre chrome', DE 'öffne
chrome', voseo 'instalame'). Skip cleanly when the model isn't on
disk (CI machines without bootstrap).
```

---

## FIX E4 — Voice silent-reject telemetry

### E4.1 — Editar `gemma4_agent/voice/stt.py:707-712`

```python
# Before:
if trimmed is None:
    logger.info("VAD: no speech detected, rejecting transcription")
    return ""
if trimmed.size < int(0.3 * SAMPLE_RATE):
    logger.info("VAD: speech too short (<0.3s), rejecting")
    return ""

# After:
if trimmed is None:
    logger.warning(
        "voice_silent_reject reason=no_speech orig_duration_s=%.3f",
        audio.size / float(SAMPLE_RATE),
    )
    return ""
if trimmed.size < int(0.3 * SAMPLE_RATE):
    logger.warning(
        "voice_silent_reject reason=too_short "
        "trimmed_duration_s=%.3f orig_duration_s=%.3f",
        trimmed.size / float(SAMPLE_RATE),
        audio.size / float(SAMPLE_RATE),
    )
    return ""
```

### E4.2 — Editar `gemma4_agent/voice/controller.py`

Localizar donde el controller recibe `""` de `stt.transcribe()`:
```bash
grep -n "transcribe\b" gemma4_agent/voice/controller.py
```

Donde el código detecta empty string y descarta el turn, emitir
trace event:

```python
if not transcribed:
    # Hotfix E 2026-05-17: surface silent rejects so 'mic ignored me'
    # reports are debuggable in the JSONL trace alongside
    # voice_e2e_latency.
    self.trace.event(
        self.trace.new_turn_id() if hasattr(self.trace, "new_turn_id") else "voice",
        "voice_silent_reject",
        reason="stt_empty_or_vad_reject",
    )
    return
```

(Adaptar al call shape real del controller.)

### E4.3 — Commit

`fix(voice): emit telemetry on silent VAD/STT rejects`

Mensaje:

```
fix(voice): emit telemetry on silent VAD/STT rejects

Audit 2026-05-17: when the user reports 'Gemma no me escuchó',
no trace event distinguishes wake-fail / VAD-no-speech /
VAD-too-short / STT-empty. The voice path had 3 silent drop points
(memory: project_voice_silent_rejects, 2026-05-17), only one
fixed previously.

Fix:
- stt.py: the 2 VAD-reject returns ('' on no_speech and too_short)
  upgrade from logger.info to logger.warning with structured
  reason= and *_duration_s= fields. Greppable in
  _pre_session/full.log.
- controller.py: when stt.transcribe() returns empty, emit a
  voice_silent_reject trace event so 'mic ignored me' bugs surface
  in the JSONL trace alongside voice_e2e_latency.

No behaviour change; pure observability.
```

---

## FIX E5 — Extend `_TABULAR_KEYS`

### E5.1 — Editar `gemma4_agent/agent_compaction.py`

```python
_TABULAR_KEYS: tuple[str, ...] = (
    "disks", "processes", "devices", "results", "items", "windows", "tabs",
    # Hotfix E 2026-05-17: more list-of-dict result keys observed in
    # real tool outputs. Bounded by _TABULAR_MAX_ROWS=20, so large
    # lists still produce a clipped breadcrumb.
    "games", "installed_apps", "tracks", "events",
    "contacts", "notes", "tasks", "reminders",
)
```

### E5.2 — Test

Append a `gemma4_agent/test_history_breadcrumb_tabular.py`:

```python
def test_games_list_stitched(self) -> None:
    games = [
        {"appid": 730, "name": "CS2"},
        {"appid": 570, "name": "Dota 2"},
    ]
    hist = [
        {"role": "user", "content": "qué juegos tengo"},
        {"role": "assistant", "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "steam", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1",
         "content": json.dumps({"ok": True, "games": games})},
        {"role": "assistant", "content": "Tenés CS2 y Dota 2."},
    ]
    out = stitch_breadcrumbs(hist)
    final_text = ""
    for m in out:
        if m.get("role") == "assistant" and not m.get("tool_calls"):
            final_text += str(m.get("content") or "")
    self.assertIn("appid=730", final_text)
    self.assertIn("appid=570", final_text)

def test_events_list_stitched(self) -> None:
    events = [
        {"id": "e1", "title": "reunión equipo", "start": "2026-05-18 10:00"},
        {"id": "e2", "title": "dentista", "start": "2026-05-19 15:00"},
    ]
    hist = [
        {"role": "user", "content": "qué tengo agendado"},
        {"role": "assistant", "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "local_calendar", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1",
         "content": json.dumps({"ok": True, "events": events})},
        {"role": "assistant", "content": "Tenés 2 eventos esta semana."},
    ]
    out = stitch_breadcrumbs(hist)
    final_text = ""
    for m in out:
        if m.get("role") == "assistant" and not m.get("tool_calls"):
            final_text += str(m.get("content") or "")
    self.assertIn("title=reunión equipo", final_text)
    self.assertIn("title=dentista", final_text)
```

### E5.3 — Commit

`fix(history): extend tabular breadcrumb keys to games/events/contacts/etc`

Mensaje:

```
fix(history): extend tabular breadcrumb keys to games/events/contacts/etc

Audit 2026-05-17: hotfix D's _TABULAR_KEYS covered 7 keys
(disks/processes/devices/results/items/windows/tabs) but real tool
outputs use more: steam.list_library returns 'games',
local_calendar.list returns 'events', contacts.list returns
'contacts', notes_tasks returns 'notes'/'tasks', reminder.list
returns 'reminders', media.queue_list returns 'tracks', app.list
returns 'installed_apps'.

Result: 'qué juegos tengo' + 'y el segundo de la lista?' lost the
list between turns (same shape as Bug D6 with disks).

Fix: extend _TABULAR_KEYS with 8 more entries. The bounded
rendering (max 20 rows × 200 chars × total 1200 chars) already
caps the breadcrumb size, so no risk of context blow-up.
```

---

## REPORTE FINAL

Devolveme:
1. Hashes de los 5 commits.
2. Output de `python -m pytest gemma4_agent/test_router_v2.py gemma4_agent/test_routing_audit_repros.py gemma4_agent/test_launcher_bootstrap.py gemma4_agent/test_history_breadcrumb_tabular.py -v`.
3. Output de `python -m pytest gemma4_agent/ -q --tb=line`.
4. Output del repro post-fix con router_v2:
   ```bash
   python -c "
   from gemma4_agent.router_v2 import RouterV2, route_v2
   RouterV2.reset()
   for q in ['instala vlc', 'apaga la pc', 'pone benson boone',
             'gracias por todo', 'ouvre chrome', 'öffne chrome',
             'instalame vlc']:
       subset, tel = route_v2(q)
       print(f'{q!r:30s} -> source={tel.get(\"source\"):9s} top3={subset[:3]}')
   "
   ```
5. Output del status con v2 default:
   ```bash
   python -m gemma4_agent.launcher status
   ```

## CRITERIO DE ÉXITO

- 5 commits aterrizados.
- ≥10 tests nuevos verdes (entre routing_audit_repros, bootstrap,
  tabular, env_flags update).
- Suite completa verde (modulo Sprint 3a pre-existing failure).
- Repro post-fix muestra todas las queries problemáticas resolviendo
  correctamente — en ES, voseo, EN, FR, DE.
- `launcher status` no rompe si el modelo todavía no está
  descargado (E2 lo descarga en `start`, no en `status`).
- `python -m gemma4_agent.launcher status` OK.

## NO HACER (anti-scope)

- NO borres el planner regex de v1 todavía. Sigue siendo el plan B
  determinístico si v2 falla. La remoción del regex es un sprint
  futuro DESPUÉS de validar v2 en uso real durante 1-2 semanas.
- NO agregues más regex a `_suggest_tools`. Ese fue justamente el
  approach equivocado que la auditoría descartó.
- NO toques tool_descriptions.yaml (ya está completo en Sprint 8b).
- NO migres `MODEL_PATH` a config. Está bien hardcoded en
  `~/.gemma4/models/e5-small/`.
- NO inflas `bootstrap_e5_small.py` con UX (progress bar,
  retry logic). El user verá una línea "downloading…" y ~30s después
  el launcher arranca. Eso es suficiente.
- Si el voice trace event en controller.py requiere refactor
  pesado, commit solo los warning() upgrades en stt.py y deja un
  TODO claro para el sub-step de controller.
