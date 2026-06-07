"""Tests para loop_detection.LoopState.

NO toca la GUI ni el LLM ni el llama-server. Mockea results sintéticos para
exercer cada uno de los 5 patrones de stuck.

Run with:
    python -m gemma4_agent.test_loop_detection
    pytest gemma4_agent/tests/test_loop_detection.py -q
"""
from __future__ import annotations

import os
import sys

from ..safety_pkg.loop_detection import (
    GLOBAL_CIRCUIT_BREAKER,
    MAX_TOOL_CALLS_PER_RESPONSE,
    PING_PONG_WINDOW,
    REPEAT_CRITICAL,
    REPEAT_WARNING,
    UNKNOWN_TOOL_LIMIT,
    VISION_NOT_FOUND_LIMIT,
    LoopState,
    StuckSignal,
    _hash_tool_call,
    _result_signature,
    dedup_degenerate_batch,
)


# --------------------------------------------------------------------- helpers
def _record_n(state: LoopState, n: int, tool: str = "app",
              args: dict | None = None, result: dict | None = None,
              exists: bool = True) -> None:
    """Helper: registra n tool calls identicos para forzar repeat patterns."""
    if args is None:
        args = {"action": "open", "name": "Steam"}
    if result is None:
        result = {"ok": True, "verified": True}
    for _ in range(n):
        state.record(tool, args, exists=exists, result=result)


# ----------------------------------------------------------------- result_sig
def test_result_signature_stable() -> None:
    a = {"ok": True, "verified": True, "value": 42}
    b = {"verified": True, "ok": True, "value": 42}  # mismo contenido, otro orden
    assert _result_signature(a) == _result_signature(b)


def test_result_signature_filters_noise() -> None:
    """Polling legitimo cambia timestamps/pids/latencias pero la firma debe
    quedar igual para no confundirse con loop."""
    a = {"ok": True, "ts": "12:00:00", "pid": 1234, "latency_ms": 50, "value": 1}
    b = {"ok": True, "ts": "12:00:05", "pid": 5678, "latency_ms": 200, "value": 1}
    assert _result_signature(a) == _result_signature(b), (
        "result_signature deberia filtrar ts/pid/latency_ms"
    )


def test_result_signature_different_payload() -> None:
    a = {"ok": True, "value": 1}
    b = {"ok": True, "value": 2}
    assert _result_signature(a) != _result_signature(b)


def test_hash_includes_args_and_sig() -> None:
    h1 = _hash_tool_call("app", {"name": "Steam"}, "sig1")
    h2 = _hash_tool_call("app", {"name": "Opera"}, "sig1")
    h3 = _hash_tool_call("app", {"name": "Steam"}, "sig2")
    assert h1 != h2 and h1 != h3 and h2 != h3


# -------------------------------------------------------------- generic_repeat
def test_generic_repeat_warning_at_three() -> None:
    s = LoopState()
    _record_n(s, REPEAT_WARNING)  # 3 identicas
    sig = s.detect_stuck()
    assert sig is not None
    assert sig.level == "warning"
    assert sig.pattern == "generic_repeat"
    assert sig.detail["tool"] == "app"


def test_generic_repeat_critical_at_five() -> None:
    s = LoopState()
    _record_n(s, REPEAT_CRITICAL)  # 5 identicas
    sig = s.detect_stuck()
    assert sig is not None
    assert sig.level == "critical"
    assert sig.pattern == "generic_repeat"


def test_generic_repeat_below_threshold_returns_none() -> None:
    s = LoopState()
    _record_n(s, REPEAT_WARNING - 1)  # 2 identicas, debajo del umbral
    assert s.detect_stuck() is None


# ---------------------------------------------------- polling no dispara loop
def test_polling_distinct_results_does_not_trigger() -> None:
    """Llamar 5 veces system.processes con results distintos NO debe disparar
    generic_repeat porque el result canonicalizado cambia cada vez."""
    s = LoopState()
    for i in range(REPEAT_CRITICAL):
        s.record(
            "system",
            {"action": "processes"},
            exists=True,
            # campos NO filtrados que cambian -> firma distinta
            result={"ok": True, "processes": [{"name": f"p{i}", "cpu": i}]},
        )
    sig = s.detect_stuck()
    assert sig is None, f"polling no deberia disparar loop, pero disparo: {sig}"


def test_polling_with_only_noise_does_trigger() -> None:
    """Si lo unico que cambia entre calls son timestamps/pids (filtrados),
    el detector SI lo trata como repeat porque la semantica es la misma."""
    s = LoopState()
    for i in range(REPEAT_CRITICAL):
        s.record(
            "system",
            {"action": "time"},
            exists=True,
            result={"ok": True, "ts": f"12:00:{i:02d}", "pid": 1000 + i,
                    "latency_ms": i * 10},
        )
    sig = s.detect_stuck()
    assert sig is not None, "ts/pid/latency cambiando son ruido, debe disparar"
    assert sig.level == "critical"


# ------------------------------------------------------- unknown_tool_repeat
def test_unknown_tool_repeat_critical() -> None:
    s = LoopState()
    for _ in range(UNKNOWN_TOOL_LIMIT):
        s.record("nonexistent_tool", {}, exists=False,
                 result={"ok": False, "error": "unknown tool: nonexistent_tool"})
    sig = s.detect_stuck()
    assert sig is not None
    assert sig.level == "critical"
    assert sig.pattern == "unknown_tool"
    assert sig.detail["tool"] == "nonexistent_tool"


def test_unknown_tool_below_limit_returns_none() -> None:
    s = LoopState()
    s.record("phantom", {}, exists=False, result={"ok": False, "error": "unknown tool: phantom"})
    s.record("phantom", {}, exists=False, result={"ok": False, "error": "unknown tool: phantom"})
    assert s.detect_stuck() is None


# ----------------------------------------------------------------- ping_pong
def test_ping_pong_critical() -> None:
    s = LoopState()
    # A -> B -> A -> B -> A -> B (PING_PONG_WINDOW = 6)
    for i in range(PING_PONG_WINDOW):
        if i % 2 == 0:
            s.record("app", {"action": "open", "name": "X"},
                     exists=True, result={"ok": True, "tag": "A"})
        else:
            s.record("verify", {"action": "app_opened", "name": "X"},
                     exists=True, result={"ok": True, "tag": "B"})
    sig = s.detect_stuck()
    assert sig is not None
    assert sig.pattern == "ping_pong"
    assert sig.level == "critical"


def test_ping_pong_three_tools_no_alternation() -> None:
    """A -> B -> C -> A -> B -> C NO es ping_pong (3 hashes distintos)."""
    s = LoopState()
    for i in range(PING_PONG_WINDOW):
        tag = ["A", "B", "C"][i % 3]
        s.record(f"tool_{tag}", {}, exists=True,
                 result={"ok": True, "tag": tag})
    sig = s.detect_stuck()
    # No es ping_pong; podria ser otra cosa o None. No deberia ser ping_pong.
    assert sig is None or sig.pattern != "ping_pong"


# ---------------------------------------------------------- circuit breaker
def test_global_circuit_breaker_critical() -> None:
    s = LoopState()
    for i in range(GLOBAL_CIRCUIT_BREAKER):
        # results todos distintos para no disparar repeat antes
        s.record("system", {"i": i}, exists=True,
                 result={"ok": True, "n": i})
    sig = s.detect_stuck()
    assert sig is not None
    assert sig.pattern == "circuit_breaker"
    assert sig.level == "critical"
    assert sig.detail["count"] >= GLOBAL_CIRCUIT_BREAKER


# ---------------------------------------------------------- vision not found
def test_vision_not_found_repeat() -> None:
    s = LoopState()
    for i in range(VISION_NOT_FOUND_LIMIT):
        s.record("vision", {"action": "locate", "target": "Comprar"},
                 exists=True,
                 # screenshot_path cambia cada vez (distinto path), pero el
                 # patron semantico visible=False se acumula
                 result={"ok": True, "visible": False, "screenshot_path": f"/tmp/{i}.png"})
    sig = s.detect_stuck()
    assert sig is not None
    assert sig.pattern == "vision_not_found"
    assert sig.level == "critical"


def test_vision_visible_true_resets_counter() -> None:
    s = LoopState()
    # 2 not found, despues 1 found, despues 2 not found = no debe disparar
    s.record("vision", {"target": "x"}, exists=True, result={"visible": False})
    s.record("vision", {"target": "x"}, exists=True, result={"visible": False})
    s.record("vision", {"target": "x"}, exists=True, result={"visible": True})
    s.record("vision", {"target": "x"}, exists=True, result={"visible": False})
    s.record("vision", {"target": "x"}, exists=True, result={"visible": False})
    assert s.vision_not_found_count == 2, (
        f"expected 2 (despues del reset por visible=True), got {s.vision_not_found_count}"
    )


# ---------------------------------------------------------- evidence reset
def test_evidence_resets_warning_count() -> None:
    s = LoopState()
    # 3 identicas -> warning, warning_count = 1
    _record_n(s, REPEAT_WARNING)
    sig = s.detect_stuck()
    assert sig is not None and sig.level == "warning"
    assert s.warning_count == 1
    # Evidencia de progreso resetea warning_count
    s.record_evidence("app:Steam")
    assert s.warning_count == 0
    assert "app:Steam" in s.evidence_keys_changed


# ---------------------------------------------------------- opt-out env var
def test_detector_disabled_via_env() -> None:
    """GEMMA4_LOOP_DETECTOR_OFF=1 deshabilita todas las detecciones."""
    os.environ["GEMMA4_LOOP_DETECTOR_OFF"] = "1"
    try:
        s = LoopState()
        _record_n(s, REPEAT_CRITICAL)  # 5 identicas - deberia ser critical
        assert s.detect_stuck() is None, "opt-out deberia devolver None siempre"
    finally:
        os.environ.pop("GEMMA4_LOOP_DETECTOR_OFF", None)


# ---------------------------------------------------------- reset()
def test_reset_clears_all_state() -> None:
    s = LoopState()
    _record_n(s, REPEAT_WARNING)
    s.record_evidence("file:/tmp/x")
    assert s.global_count > 0 and s.evidence_keys_changed
    s.reset()
    assert s.global_count == 0
    assert len(s.history) == 0
    assert not s.evidence_keys_changed
    assert s.warning_count == 0
    assert s.vision_not_found_count == 0


# --------------------------------------------------------------- no_progress
def test_no_progress_critical_without_evidence() -> None:
    """9 tool calls sin NINGUNA evidencia de cambio -> no_progress critical.
    Args/results varían (no es generic_repeat), pero no se logra nada medible."""
    s = LoopState()
    for i in range(9):
        s.record("app", {"action": "open", "name": f"x{i}"},
                 exists=True, result={"ok": False, "attempt": i})
    sig = s.detect_stuck()
    assert sig is not None and sig.pattern == "no_progress"
    assert sig.level == "critical"


def test_no_progress_warning_tier() -> None:
    s = LoopState()
    for i in range(6):
        s.record("web", {"q": f"q{i}"}, exists=True, result={"ok": True, "data": i})
    sig = s.detect_stuck()
    assert sig is not None and sig.pattern == "no_progress"
    assert sig.level == "warning"


def test_no_progress_resets_on_evidence() -> None:
    """Evidencia frecuente de progreso real -> NUNCA dispara no_progress."""
    s = LoopState()
    for i in range(9):
        s.record("app", {"action": "open", "name": f"x{i}"},
                 exists=True, result={"ok": True})
        if i % 2 == 0:
            s.record_evidence(f"app:x{i}")
    sig = s.detect_stuck()
    assert sig is None or sig.pattern != "no_progress"


def test_no_progress_below_threshold_returns_none() -> None:
    s = LoopState()
    for i in range(3):
        s.record("web", {"q": f"q{i}"}, exists=True, result={"ok": True, "data": i})
    assert s.detect_stuck() is None


def test_no_progress_unverifiable_reads_exempt() -> None:
    """Turno read-heavy legítimo (9 búsquedas, todas confirmed=None) NO debe
    disparar no_progress: leer no es no-progresar. note_unverifiable() descuenta."""
    s = LoopState()
    for i in range(9):
        s.record("web", {"q": f"q{i}"}, exists=True, result={"ok": True, "data": i})
        s.note_unverifiable()  # el agente lo llama cuando confirmed is None
    sig = s.detect_stuck()
    assert sig is None or sig.pattern != "no_progress"


# ============================================================================
# dedup_degenerate_batch (bug Gemma 4 #1756)
# ============================================================================
def _call(name: str, args: dict | str) -> dict:
    """Construye un tool_call crudo estilo OpenAI con un id único."""
    import json as _json
    arguments = args if isinstance(args, str) else _json.dumps(args)
    return {"id": f"call_{id(args)}_{name}", "type": "function",
            "function": {"name": name, "arguments": arguments}}


def test_dedup_collapses_exact_duplicates() -> None:
    """Bug #1756: 72 calls que colapsan a 5 únicos -> quedan los 5 (capados a 8)."""
    # 5 (name,action) únicos, cada uno repetido ~14 veces, mismo args.
    bases = [("web", {"action": "search", "q": "h2o"}),
             ("web", {"action": "research", "q": "h2o"}),
             ("web", {"action": "read", "q": "h2o"}),
             ("web", {"action": "open", "q": "h2o"}),
             ("knowledge", {"action": "search", "q": "h2o"})]
    raw = []
    for _ in range(14):
        for n, a in bases:
            raw.append(_call(n, a))
    kept, info = dedup_degenerate_batch(raw)
    assert info["original"] == 70
    assert info["after_dedup"] == 5
    assert info["dropped_duplicates"] == 65
    assert len(kept) == 5  # 5 únicos < cap 8 -> sin recorte por cap


def test_dedup_caps_distinct_over_limit() -> None:
    """Si hay MÁS de MAX_TOOL_CALLS_PER_RESPONSE únicos, capar al límite."""
    raw = [_call("web", {"action": "search", "q": f"q{i}"})
           for i in range(MAX_TOOL_CALLS_PER_RESPONSE + 5)]
    kept, info = dedup_degenerate_batch(raw)
    assert info["dropped_duplicates"] == 0  # todos distintos
    assert info["dropped_over_cap"] == 5
    assert len(kept) == MAX_TOOL_CALLS_PER_RESPONSE


def test_dedup_keeps_first_occurrence_order() -> None:
    """Conserva el PRIMER ocurrencia de cada único, en orden."""
    raw = [_call("a", {"x": 1}), _call("b", {"y": 2}), _call("a", {"x": 1}),
           _call("c", {"z": 3}), _call("b", {"y": 2})]
    kept, info = dedup_degenerate_batch(raw)
    names = [c["function"]["name"] for c in kept]
    assert names == ["a", "b", "c"]
    assert info["dropped_duplicates"] == 2


def test_dedup_legit_parallel_untouched() -> None:
    """Research genuino: 4 calls DISTINTAS pasan intactas (no es degenerado)."""
    raw = [_call("web", {"action": "search", "q": "clima hoy"}),
           _call("web", {"action": "search", "q": "pronostico"}),
           _call("web", {"action": "open", "q": "accuweather"}),
           _call("knowledge", {"action": "search", "q": "buenos aires"})]
    kept, info = dedup_degenerate_batch(raw)
    assert len(kept) == 4
    assert info["dropped_duplicates"] == 0
    assert info["dropped_over_cap"] == 0


def test_dedup_single_call_noop() -> None:
    raw = [_call("app", {"action": "open", "name": "Steam"})]
    kept, info = dedup_degenerate_batch(raw)
    assert kept == raw and info["kept"] == 1


def test_dedup_empty_noop() -> None:
    kept, info = dedup_degenerate_batch([])
    assert kept == [] and info["original"] == 0


def test_dedup_disabled_via_env() -> None:
    raw = [_call("web", {"q": 1}), _call("web", {"q": 1}), _call("web", {"q": 1})]
    os.environ["GEMMA4_BATCH_DEDUP_OFF"] = "1"
    try:
        kept, info = dedup_degenerate_batch(raw)
        assert len(kept) == 3  # apagado -> sin cambios
        assert info["dropped_duplicates"] == 0
    finally:
        del os.environ["GEMMA4_BATCH_DEDUP_OFF"]


def test_dedup_string_args_duplicates() -> None:
    """Los arguments del LLM llegan como STRING JSON crudo; dups exactos colapsan."""
    raw = [_call("web", '{"action":"search","q":"x"}'),
           _call("web", '{"action":"search","q":"x"}'),
           _call("web", '{"action":"search","q":"y"}')]
    kept, info = dedup_degenerate_batch(raw)
    assert len(kept) == 2
    assert info["dropped_duplicates"] == 1


def test_dedup_never_raises_on_garbage() -> None:
    """Red de seguridad: input malformado NO debe lanzar."""
    raw = [{"function": None}, {"nope": 1}, _call("a", {"x": 1})]
    kept, info = dedup_degenerate_batch(raw)
    assert isinstance(kept, list) and isinstance(info, dict)


# ============================================================================
# Runner standalone
# ============================================================================
TESTS = [
    test_result_signature_stable,
    test_result_signature_filters_noise,
    test_result_signature_different_payload,
    test_hash_includes_args_and_sig,
    test_generic_repeat_warning_at_three,
    test_generic_repeat_critical_at_five,
    test_generic_repeat_below_threshold_returns_none,
    test_polling_distinct_results_does_not_trigger,
    test_polling_with_only_noise_does_trigger,
    test_unknown_tool_repeat_critical,
    test_unknown_tool_below_limit_returns_none,
    test_ping_pong_critical,
    test_ping_pong_three_tools_no_alternation,
    test_global_circuit_breaker_critical,
    test_vision_not_found_repeat,
    test_vision_visible_true_resets_counter,
    test_evidence_resets_warning_count,
    test_detector_disabled_via_env,
    test_reset_clears_all_state,
    test_no_progress_critical_without_evidence,
    test_no_progress_warning_tier,
    test_no_progress_resets_on_evidence,
    test_no_progress_below_threshold_returns_none,
    test_no_progress_unverifiable_reads_exempt,
    test_dedup_collapses_exact_duplicates,
    test_dedup_caps_distinct_over_limit,
    test_dedup_keeps_first_occurrence_order,
    test_dedup_legit_parallel_untouched,
    test_dedup_single_call_noop,
    test_dedup_empty_noop,
    test_dedup_disabled_via_env,
    test_dedup_string_args_duplicates,
    test_dedup_never_raises_on_garbage,
]


def main() -> int:
    failures = 0
    for t in TESTS:
        try:
            ok = t()
            if not ok:
                print(f"[FAIL] {t.__name__}: returned falsy")
                failures += 1
        except AssertionError as exc:
            print(f"[FAIL] {t.__name__}: {exc}")
            failures += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {t.__name__}: {type(exc).__name__}: {exc}")
            failures += 1
    total = len(TESTS)
    passed = total - failures
    print(f"\n{passed}/{total} pass")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
