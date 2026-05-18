"""M.2.3: _transcribe_buffer returns (text, reason, raw_text)
and STTEvent.raw_text carries the pre-filter Whisper text on
rejection.
"""
from __future__ import annotations

import unittest


class STTRawTextContractTest(unittest.TestCase):
    def test_stt_event_has_raw_text(self) -> None:
        from gemma4_agent.voice.stt import STTEvent
        self.assertIn("raw_text", STTEvent.__dataclass_fields__)
        ev = STTEvent(
            kind="final", text="", reject_reason="BoH_match",
            raw_text="[musica]",
        )
        self.assertEqual(ev.raw_text, "[musica]")
        # Default empty when not set.
        ev2 = STTEvent(kind="partial", text="hola")
        self.assertEqual(ev2.raw_text, "")

    def test_transcribe_buffer_docstring_documents_raw_text(self) -> None:
        from gemma4_agent.voice.stt import StreamingSTT
        doc = StreamingSTT._transcribe_buffer.__doc__ or ""
        self.assertIn(
            "raw_text", doc,
            "M.2.3: _transcribe_buffer should document the new "
            "(text, reason, raw_text) tuple",
        )


if __name__ == "__main__":
    unittest.main()
