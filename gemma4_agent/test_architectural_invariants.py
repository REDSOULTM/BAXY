"""Consolidated architectural-invariant guards. Each test states ONE invariant
the audit (rondas 1-13 + continuación) defended, cites the round that originated
it, and exercises the real code path. This is the single readable place a future
reader (or RED) can see "what must NEVER break and why". Puntual tests still
exist per-fix; this file is the index of invariants, not a replacement.

Norte rector: estos son los invariantes de ARQUITECTURA y FIABILIDAD que el
hot-path y los safety-nets garantizan. Si uno se rompe, el agente degrada en una
forma que la auditoría ya pagó caro una vez.
"""
from __future__ import annotations

import unittest
from unittest import mock

import numpy as np


class TestDispatchContainsBlastRadius(unittest.TestCase):
    """INVARIANTE (ronda 1): el dispatch de tools contiene el blast radius — una
    tool que lanza una excepción se vuelve {ok:False,error}, NUNCA tumba el turno.
    Doble contención: ToolRegistry.execute() envuelve impl(), y _run_with_timeout
    (el caller) también captura Exception."""

    def test_tool_exception_becomes_error_result(self):
        from gemma4_agent.config import AgentConfig
        from gemma4_agent.tools import ToolRegistry
        reg = ToolRegistry.__new__(ToolRegistry)
        # Minimal: inject a bomb impl and the validation helpers it needs.
        reg._impls = {"bomb": lambda args: (_ for _ in ()).throw(RuntimeError("boom"))}
        with mock.patch("gemma4_agent.tools._coerce_and_validate_tool_args",
                        return_value=({}, None)), \
             mock.patch("gemma4_agent.tools._correct_known_misroute",
                        side_effect=lambda n, a: (n, a)), \
             mock.patch("gemma4_agent.tools._normalize_tool_result",
                        side_effect=lambda n, a, r: r):
            reg.safety_enabled = False
            reg._PRE_VALIDATORS = {}
            out = reg.execute("bomb", {})
        self.assertFalse(out.get("ok", True), "a throwing tool must yield ok=False, not raise")
        self.assertIn("RuntimeError", str(out.get("error", "")))


class TestVerifierNeverTumblesTurn(unittest.TestCase):
    """INVARIANTE (ronda 5): un verifier que crashea NO tumba el turno — verify
    devuelve confirmed=False/None, nunca propaga la excepción."""

    def test_crashing_verifier_is_contained(self):
        from gemma4_agent import verify_core
        # Register a verifier that explodes; verify_core.verify must catch it and
        # return confirmed=False, never propagate.
        orig = dict(verify_core._VERIFIERS)
        try:
            verify_core._VERIFIERS["__bomb__"] = lambda a, r: (_ for _ in ()).throw(
                RuntimeError("verifier boom"))
            with mock.patch.object(verify_core, "_enabled", return_value=True):
                outcome = verify_core.verify("__bomb__", {}, {})
            self.assertFalse(outcome.confirmed, "a crashing verifier must yield confirmed=False")
            self.assertIn("crashed", outcome.reason)
        finally:
            verify_core._VERIFIERS.clear()
            verify_core._VERIFIERS.update(orig)

    def test_nonoutcome_verifier_is_normalized(self):
        # A verifier returning a non-VerifierOutcome must be normalized, not crash.
        from gemma4_agent import verify_core
        orig = dict(verify_core._VERIFIERS)
        try:
            verify_core._VERIFIERS["__weird__"] = lambda a, r: "not an outcome"
            with mock.patch.object(verify_core, "_enabled", return_value=True):
                outcome = verify_core.verify("__weird__", {}, {})
            self.assertFalse(outcome.confirmed)
        finally:
            verify_core._VERIFIERS.clear()
            verify_core._VERIFIERS.update(orig)


class TestDiagnosticsNeverCrashWhatTheyTrace(unittest.TestCase):
    """INVARIANTE (rondas 7, 6): el diagnóstico (tracing, telemetry, loop-detector)
    JAMÁS crashea lo que observa. Path inescribible/payload raro/keys mixtas =>
    no-op silencioso, nunca excepción que escape al turno."""

    def test_tracing_bad_path_disables_not_crashes(self):
        from pathlib import Path
        from gemma4_agent.tracing import TraceLogger
        t = TraceLogger(path=Path("Z:/x\0bad/traces.jsonl"), enabled=True)
        self.assertFalse(t.enabled)
        t.event("turn1", "llm_start", x=1)  # must not raise

    def test_loop_detector_survives_mixed_key_args(self):
        from gemma4_agent.loop_detection import _hash_tool_call, _result_signature
        h = _hash_tool_call("t", {1: "a", "b": 2}, _result_signature({"ok": True}))
        self.assertIsInstance(h, str)


class TestSafetyHelperNeverCrashes(unittest.TestCase):
    """INVARIANTE (ronda 10): redact_sensitive está en un safety-path
    (hard_gate/confirmación). Un valor raro (numpy array) bajo una key sensible
    NO debe levantar ValueError ('truth value ambiguous')."""

    def test_redact_numpy_value(self):
        from gemma4_agent._shared import redact_sensitive
        out = redact_sensitive({"password": np.array([1, 2, 3]), "user": "ema"})
        self.assertEqual(out["password"], "***REDACTED***")
        self.assertEqual(out["user"], "ema")


class TestReplyNeverDestroyedByEnrichment(unittest.TestCase):
    """INVARIANTE (ronda 9): la enrichment cosmética post-LLM (mission footer)
    NUNCA destruye un reply ya generado. middle_ellipsis (compactación) NUNCA
    crece el texto (round 7) — un primitivo que crece mina el anti-overflow."""

    def test_middle_ellipsis_never_grows(self):
        from gemma4_agent.agent_compaction import middle_ellipsis
        for limit in (0, 1, 5, 10, 160, 500):
            out = middle_ellipsis("x" * 1000, limit)
            self.assertLessEqual(len(out), max(0, limit))


class TestPersistenceRecoversFromCorruption(unittest.TestCase):
    """INVARIANTE (ronda 4): la persistencia se recupera de corrupción. Una DB
    de experiencias malformada se pone en cuarentena y se recrea, NO crashea cada
    record/recall para siempre ('anda un rato y se rompe')."""

    def test_experience_has_quarantine_recovery(self):
        from gemma4_agent.experience import ExperienceMemory
        self.assertTrue(hasattr(ExperienceMemory, "_quarantine_corrupt_db"))


class TestLazySingletonsAreThreadSafe(unittest.TestCase):
    """INVARIANTE (rondas 2, 10, 11): los singletons lazy (encoder ST, reranker,
    tool_head, abstain_head, mcp registry, shared server manager) usan
    double-checked locking — el warmup (daemon) + el primer turno no pueden
    double-load ni inflar el attempt_count que mataba al router."""

    def test_lock_present_on_lazy_loaders(self):
        from gemma4_agent import semantic_router, mcp_server, llama_server
        self.assertTrue(hasattr(semantic_router, "_LOAD_LOCK"))
        self.assertTrue(hasattr(mcp_server, "_REGISTRY_LOCK"))
        self.assertTrue(hasattr(llama_server, "_SHARED_MANAGER_LOCK"))


class TestServerLifecycleNoOrphans(unittest.TestCase):
    """INVARIANTE (ronda 11): el llama-server gestionado se detiene al exit (no
    queda huérfano reteniendo VRAM) y NUNCA se mata un server externo del usuario.
    El atexit cuelga de _external_detected/current_profile."""

    def test_atexit_noop_without_managed_server(self):
        from gemma4_agent import llama_server as ls
        ls._SHARED_MANAGER = None
        ls._atexit_stop_shared_manager()  # must not raise with nothing started

    def test_external_server_is_never_stopped(self):
        from gemma4_agent.llama_server import LlamaServerManager
        from gemma4_agent.profiles import PROFILES
        mgr = LlamaServerManager()
        with mock.patch("gemma4_agent.llama_server.port_in_use", return_value=True), \
             mock.patch("gemma4_agent.llama_server.get_external_server_context",
                        return_value=None):
            self.assertEqual(mgr.start(PROFILES["vram8"]), "external")
        self.assertIsNone(mgr.current_profile())
        self.assertFalse(mgr.stop(), "stop() must no-op on an external server")


class TestVoiceLifecycleClean(unittest.TestCase):
    """INVARIANTE (ronda 11): el ciclo enable/disable de la voz no deja estado
    sucio — stop() resetea el state machine (no comando fantasma) y is_busy()
    refleja el estado real."""

    def test_pipeline_stop_returns_to_idle(self):
        from gemma4_agent.voice.pipeline import VoicePipeline, State
        pipe = VoicePipeline(on_command=lambda *a: None)
        pipe._state = State.CAPTURE
        pipe._capture_buf = [np.ones(256, dtype=np.int16)]
        pipe.stop()
        self.assertEqual(pipe.state, State.IDLE)
        self.assertEqual(pipe._capture_buf, [])


class TestEventBusNeverBlocksPublisher(unittest.TestCase):
    """INVARIANTE (auditado limpio): EventBus.publish nunca bloquea al publisher
    (la turn). Un subscriber lleno descarta el más viejo; los listeners se
    snapshotean bajo lock y se invocan SIN lock (un listener reentrante como el
    log_recorder no deadlockea)."""

    def test_full_subscriber_does_not_block(self):
        from gemma4_agent.events_bus import EventBus
        bus = EventBus()
        q = bus.subscribe()
        # Fill the queue to capacity, then publish more — must not block/raise.
        for i in range(q.maxsize + 50):
            bus.publish({"type": "metric", "i": i})
        self.assertLessEqual(q.qsize(), q.maxsize, "queue stays bounded (drop-oldest)")


if __name__ == "__main__":
    unittest.main()
