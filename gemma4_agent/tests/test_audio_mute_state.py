"""audio_mute: contrato del state. Bug MEDIDO 2026-05-30: 'quita el silencio' /
'desmuteá' emiten action=mute SIN state (None) → el viejo `bool(args.get('state',
True))` MUTEABA un pedido de DESMUTEAR (lo opuesto), y `bool("false")` (string del
parser de leaks) también daba True. Fix: state=None → TOGGLE; strings coercionan
bien. Mock del endpoint COM (no toca el audio real del sistema)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ..memory_pkg.memory import MemoryStore
from ..memory_pkg.state import AgentState
from ..tools_pkg.tools import ToolRegistry


class _FakeVol:
    """Endpoint de volumen falso: registra los SetMute y refleja GetMute."""
    def __init__(self, muted: bool):
        self.muted = muted
        self.set_calls: list[int] = []

    def GetMute(self) -> int:
        return 1 if self.muted else 0

    def SetMute(self, val, _ctx):
        self.muted = bool(val)
        self.set_calls.append(int(val))


class AudioMuteState(unittest.TestCase):
    def _run(self, args: dict, muted_before: bool) -> _FakeVol:
        tmp = Path(tempfile.mkdtemp(prefix="gemma4_audio_"))
        reg = ToolRegistry(MemoryStore(tmp / "mem.json"), tmp / "captures",
                           state=AgentState(tmp / "data" / "state.json"))
        fake = _FakeVol(muted_before)
        with mock.patch.object(reg, "_audio_endpoint_volume", return_value=fake):
            reg.audio_mute(args)
        return fake

    def test_none_toggles_muted_to_unmuted(self):
        # "quitá el silencio" sin state, ya muteado → debe DESMUTEAR.
        self.assertEqual(self._run({}, muted_before=True).set_calls, [0])

    def test_none_toggles_unmuted_to_muted(self):
        # "muteá" sin state, sin mutear → debe MUTEAR.
        self.assertEqual(self._run({}, muted_before=False).set_calls, [1])

    def test_explicit_false_unmutes(self):
        self.assertEqual(self._run({"state": False}, muted_before=True).set_calls, [0])

    def test_string_false_unmutes(self):
        # bool("false") era True (bug) → ahora coerciona a False.
        self.assertEqual(self._run({"state": "false"}, muted_before=True).set_calls, [0])

    def test_explicit_true_mutes(self):
        self.assertEqual(self._run({"state": True}, muted_before=False).set_calls, [1])

    def test_string_true_mutes(self):
        self.assertEqual(self._run({"state": "true"}, muted_before=False).set_calls, [1])


if __name__ == "__main__":
    unittest.main()
