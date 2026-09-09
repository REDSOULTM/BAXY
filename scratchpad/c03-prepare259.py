"""Prepare the physical test of installed257; no experimental AEC/capture swap."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'scratchpad/c03-voice254.py').read_text(encoding='utf-8')
source = source.replace('integrated DTLN512', 'installed AEC3 two-view capture')
start = source.index('from webrtc_aligned254 import')
end = source.index('OUT = ROOT', start)
source = source[:start] + source[end:]
source = source.replace('voice254', 'voice259').replace('tap254', 'tap259').replace('generated254', 'generated259')
source = source.replace('assert importlib.metadata.version("ai-edge-litert") == "2.2.0"', 'assert importlib.metadata.version("pywebrtc-audio") == "0.2.0+baxy.1"')
source = source.replace('assert voice.EchoCanceller.__module__ == "webrtc_aligned254"\n    assert candidate_session is None', 'assert voice.EchoCanceller.__module__ == "baxy_mind.webrtc_aec"')
source = source.replace('Experimental253 separation: same native AEC3 supplies linear recognition and final confirmation, both256samples total delay; capture252 copy in live voice namespace. Real RAW capture/Piper/baxy.2. IndependentVADs, criteria unchanged, four fixed187texts. No installed runtime/source changes, no UI/LLM or human acceptance. Waves are regenerated and retained, not falsely called samePCM240243.',
    'Installed257 source and lock: real AEC3 capture supplies aligned recognition/confirmation, independent VAD states, RAW WASAPI, Piper and baxy.2 ASR. No AEC replacement or capture-method copy. Four fixed187texts are regenerated and effective waves retained. This tests pure echo; no UI/LLM or simultaneous human acceptance.')
source = source.replace('src/baxy_mind/dtln_aec.py', 'src/baxy_mind/webrtc_aec.py')
source = source.replace(', "captureCopySha256": sha(capture_copy), "adapterSha256": sha(ROOT / "scratchpad/webrtc_aligned254.py"), "aecDirectory": str(voice.resolve_echo_canceller_directory())', ', "nativePackage": "pywebrtc-audio0.2.0+baxy.1"')
source = source.replace('confirmation[i] = self.last_final', 'confirmation[i] = result.confirmation')
source = source.replace('6 if self is engine._confirmation_vad else 4', '4 if self is engine._vad else 6')
source = source.replace('            engine._confirmation_vad = voice.SileroVad()\n            engine._confirmation_frame = lambda: candidate_session.last_final\n', '')
source = source.replace('Physical RAW/experimental split AEC3 direct session ready', 'Physical RAW/installed two-view AEC3 direct session ready')
assert 'candidate_session' not in source and 'capture_copy' not in source and 'webrtc_aligned254' not in source
target = ROOT / 'scratchpad/c03-voice259.py'
assert not target.exists()
target.write_text(source, encoding='utf-8', newline='\n')
