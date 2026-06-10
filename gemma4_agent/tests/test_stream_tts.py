"""Unit tests for streaming token->TTS (GEMMA4_STREAM_TTS, opt-in).

Tests the SAFETY-CRITICAL primitives in isolation (fake client + fake sink, no
server, no audio): the summary-pass streamer feeds sanitized prose incrementally
and returns a chat()-shaped resp; the post-guard tail logic never double-speaks
or contradicts ("el agente no miente"); the gate is honored.

End-to-end eligibility (only summary-pass / tool-turn / no-routine) + TTFA are
validated LIVE in scripts/_validate_stream_tts.py — the 4B is non-deterministic,
so the live run is the real gate. See
documentacion/SPRINT_streaming_tts_truthful.md.
"""
import os
import unittest

from ..agent_core.agent import Gemma4Agent, _stream_tts_enabled
from ..support.reasoning import sanitize_text


class _Trace:
    def event(self, *a, **k):
        pass

    def new_turn_id(self):
        return "t"


class _StreamClient:
    """Fake LLMClient: chat_stream yields the given pieces then a final frame."""

    def __init__(self, pieces, final=None, tool_calls=None):
        self.pieces = pieces
        self._final = final if final is not None else "".join(pieces)
        self._tcs = tool_calls or []
        self.chat_called = False

    def chat_stream(self, msgs, **kw):
        for p in self.pieces:
            yield {"type": "delta", "content_delta": p, "tool_call_delta": None}
        yield {"type": "final", "finish_reason": "stop",
               "content": self._final, "tool_calls": self._tcs}

    def chat(self, *a, **k):  # only used by the fallback path
        self.chat_called = True
        return {"choices": [{"message": {"content": self._final, "tool_calls": self._tcs}}]}


class _Self:
    """Duck-typed stand-in for Gemma4Agent for the streaming primitives — avoids
    constructing the full agent (heavy deps) just to exercise two methods."""

    def __init__(self, client, sink):
        self.client = client
        self._active_tts_sink = sink
        self._tts_streamed = False
        self._tts_streamed_text = ""
        self.trace = _Trace()


def _run_stream(pieces, final=None, guard_check=False):
    fed = []
    client = _StreamClient(pieces, final=final)
    s = _Self(client, fed.append)
    resp = Gemma4Agent._chat_streaming(
        s, [{"role": "user", "content": "x"}],
        model=None, max_tokens=160, thinking_budget=256, timeout_s=10, turn_id="t",
        guard_check=guard_check,
    )
    return s, fed, resp


class TestSummaryStreaming(unittest.TestCase):
    def test_feeds_prose_incrementally_and_returns_resp(self):
        s, fed, resp = _run_stream(["Listo, ", "abrí ", "la calculadora."])
        self.assertEqual("".join(fed), sanitize_text("Listo, abrí la calculadora."))
        self.assertTrue(s._tts_streamed)
        self.assertEqual(s._tts_streamed_text, sanitize_text("Listo, abrí la calculadora."))
        msg = resp["choices"][0]["message"]
        self.assertEqual(msg["content"], "Listo, abrí la calculadora.")  # RAW returned
        self.assertEqual(msg["tool_calls"], [])

    def test_voiced_is_prefix_of_final_guarded(self):
        # TRUTHFULNESS invariant: whatever was voiced must be a prefix of the
        # final guarded reply (sanitize is what finalize re-applies).
        s, fed, resp = _run_stream(["Listo, ", "abrí Steam."])
        voiced = "".join(fed)
        final_guarded = sanitize_text(resp["choices"][0]["message"]["content"])
        self.assertTrue(final_guarded.startswith(voiced),
                        f"voiced={voiced!r} not a prefix of final={final_guarded!r}")

    def test_multiple_deltas_never_overlap_or_gap(self):
        # incremental feeding must reconstruct exactly the sanitized prose
        pieces = ["Su", "bí ", "el vol", "umen ", "al 50%."]
        s, fed, _ = _run_stream(pieces)
        self.assertEqual("".join(fed), sanitize_text("Subí el volumen al 50%."))

    def test_no_sink_marks_not_streamed(self):
        client = _StreamClient(["Listo."])
        s = _Self(client, None)
        resp = Gemma4Agent._chat_streaming(
            s, [{"role": "user", "content": "x"}],
            model=None, max_tokens=160, thinking_budget=256, timeout_s=10, turn_id="t")
        self.assertFalse(s._tts_streamed)
        self.assertEqual(resp["choices"][0]["message"]["content"], "Listo.")


class TestMarkupGuard(unittest.TestCase):
    """El 4B a veces emite la sintaxis de tool-call como TEXTO en el content.
    Los patrones de sanitize_text son de bloque COMPLETO: en el stream
    incremental el markup llegaba de a pedazos y se VOCABA antes de que el
    patrón cerrara (medido en vivo: '<|tool_call>call:window{action:maximize'
    crudo al sink). El markup guard aborta ante '<|' confirmado y RETIENE un
    sufijo que puede ser una apertura a medio llegar."""

    def test_toolcall_markup_never_voiced(self):
        # el split EXACTO del leak en vivo: el delta corta ANTES del '>' — ahí
        # ningún patrón de sanitize matchea todavía (todos exigen el '>' o el
        # cierre) y el texto se vocaba crudo. El guard aborta en el '<|'.
        s, fed, _ = _run_stream(["<|tool_call", ">call:window{action:maximize"])
        voiced = "".join(fed)
        self.assertNotIn("<|", voiced)
        self.assertNotIn("tool_call", voiced)
        self.assertFalse(s._tts_streamed)

    def test_piecemeal_opener_held_then_aborted(self):
        # la apertura llega carácter a carácter: '<' solo es ambiguo (se
        # retiene), '<|' confirma markup (aborta). Nada se voca jamás.
        s, fed, _ = _run_stream(["<", "|tool_call>call:window{a", "ction:max"])
        self.assertEqual("".join(fed), "")
        self.assertFalse(s._tts_streamed)

    def test_markup_after_prose_never_voices_markup(self):
        # prosa limpia + markup en un delta COMPLETO: sanitize lo come entero
        # (patrón de bloque) -> lo vocado queda "Listo." == final sanitizado
        # (el invariante voiced==final se sostiene; no hace falta abortar).
        s, fed, _ = _run_stream(["Listo. ", "<|tool_call>call:app{"])
        voiced = "".join(fed)
        self.assertNotIn("<|", voiced)
        self.assertEqual(voiced, "Listo.")
        # y si el markup llega PARTIDO tras la prosa, el guard aborta:
        s2, fed2, _ = _run_stream(["Listo. ", "<|tool_call", ">call:app{"])
        self.assertNotIn("<|", "".join(fed2))
        self.assertFalse(s2._tts_streamed)

    def test_legit_less_than_sign_released(self):
        # '<' legítimo en prosa ('2 < 3') se retiene UN delta y se libera.
        s, fed, _ = _run_stream(["2 ", "< ", "3 es verdad."])
        self.assertEqual("".join(fed), sanitize_text("2 < 3 es verdad."))
        self.assertTrue(s._tts_streamed)


class TestInfoGuardCheck(unittest.TestCase):
    """Info turns (guard_check=True, NO tool ran) where the content-replacing
    guards CAN fire: clean prose streams; a claim/promise ABORTS before it is
    ever voiced. Uses the REAL detectors (grounding_gate + agent_guards)."""

    def test_clean_info_prose_streams(self):
        s, fed, _ = _run_stream(
            ["La fotosintesis ", "es el proceso ", "por el que las plantas ", "hacen energia."],
            guard_check=True)
        self.assertTrue(s._tts_streamed)
        self.assertEqual("".join(fed),
                         sanitize_text("La fotosintesis es el proceso por el que las plantas hacen energia."))

    def test_promise_aborts_and_is_never_voiced(self):
        # "te aviso" is a promise pattern -> guard fires -> abort before voicing it.
        s, fed, _ = _run_stream(["Claro. ", "Te aviso ", "cuando termine."], guard_check=True)
        voiced = "".join(fed)
        self.assertFalse(s._tts_streamed)          # aborted -> runner voices full guarded reply
        self.assertNotIn("aviso", voiced.lower())  # the promise was NEVER spoken
        self.assertNotIn("aviso", s._tts_streamed_text.lower())

    def test_action_claim_opening_aborts(self):
        # opens with a 1st-person past-tense action claim and NO tool ran -> abort.
        s, fed, _ = _run_stream(["Abrí el navegador.", " Ya está."], guard_check=True)
        self.assertFalse(s._tts_streamed)
        self.assertNotIn("Abrí", "".join(fed))

    def test_summary_pass_does_not_guard_check(self):
        # guard_check=False (a tool ran): a grounded "abrí" claim streams freely.
        s, fed, _ = _run_stream(["Listo, ", "abrí Steam."], guard_check=False)
        self.assertTrue(s._tts_streamed)
        self.assertEqual("".join(fed), sanitize_text("Listo, abrí Steam."))


class TestFeedTail(unittest.TestCase):
    def _self_with(self, spoken):
        fed = []
        s = _Self(_StreamClient([]), fed.append)
        s._tts_streamed = True
        s._tts_streamed_text = spoken
        return s, fed

    def test_clean_success_no_tail(self):
        s, fed = self._self_with("Listo, abrí la calculadora.")
        Gemma4Agent._feed_tts_tail(s, "Listo, abrí la calculadora.", "t")
        self.assertEqual(fed, [])  # final == voiced -> nothing extra spoken

    def test_appended_note_is_voiced_as_tail(self):
        s, fed = self._self_with("Listo, abrí Steam.")
        final = "Listo, abrí Steam.\n\nNota: no dejó evidencia suficiente."
        Gemma4Agent._feed_tts_tail(s, final, "t")
        self.assertEqual(len(fed), 1)
        self.assertIn("Nota", fed[0])
        self.assertNotIn("Listo", fed[0])  # only the TAIL, prose not repeated

    def test_divergence_voices_nothing(self):
        # unreachable for tool-turns (replacing guards pass-through), but the
        # guard must NEVER double-speak nor contradict if it somehow happened.
        s, fed = self._self_with("Listo, abrí Steam.")
        Gemma4Agent._feed_tts_tail(s, "No pude abrir Steam.", "t")
        self.assertEqual(fed, [])

    def test_final_shorter_than_voiced_voices_nothing(self):
        s, fed = self._self_with("Listo, abrí Steam ahora mismo.")
        Gemma4Agent._feed_tts_tail(s, "Listo, abrí Steam", "t")
        self.assertEqual(fed, [])

    def test_not_streamed_no_tail(self):
        fed = []
        s = _Self(_StreamClient([]), fed.append)
        s._tts_streamed = False  # never streamed -> tail must be a no-op
        Gemma4Agent._feed_tts_tail(s, "cualquier cosa", "t")
        self.assertEqual(fed, [])


class TestGate(unittest.TestCase):
    def test_default_off(self):
        # Default OFF preserves voice == final visible GEMMA reply. The low
        # latency streaming path remains available as an explicit opt-in.
        prev = os.environ.pop("GEMMA4_STREAM_TTS", None)
        try:
            self.assertFalse(_stream_tts_enabled())
        finally:
            if prev is not None:
                os.environ["GEMMA4_STREAM_TTS"] = prev

    def test_on_values(self):
        prev = os.environ.get("GEMMA4_STREAM_TTS")
        try:
            for v in ("1", "true", "yes", "on"):
                os.environ["GEMMA4_STREAM_TTS"] = v
                self.assertTrue(_stream_tts_enabled(), v)
            for v in ("0", "false", "no", "off"):
                os.environ["GEMMA4_STREAM_TTS"] = v
                self.assertFalse(_stream_tts_enabled(), v)
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_STREAM_TTS", None)
            else:
                os.environ["GEMMA4_STREAM_TTS"] = prev


if __name__ == "__main__":
    unittest.main()
