"""Apply the bounded owner substitution with exact source preconditions."""
from pathlib import Path
import ast
import json

root = Path(__file__).resolve().parents[1]
path = root / 'src/baxy_mind/voice.py'
s = path.read_text(encoding='utf-8')

def change(old, new, count=1):
    global s
    assert s.count(old) == count, (old, s.count(old), count)
    s = s.replace(old, new)

change('from .voice_aec import AudioDucker, EchoCanceller, LoopbackReference', 'from .voice_aec import AudioDucker, LoopbackReference\nfrom .speex_aec import EchoCanceller, REFERENCE_SAMPLES, resolve_echo_canceller_library')
change('    reference: np.ndarray\n    origin: str', '    aec_applied: bool\n    origin: str')
change('        self._loopback = LoopbackReference()\n', '        self._loopback = LoopbackReference()\n        self._aec_active = False\n        self._aec_sha256: str | None = None\n')
change('"aec": _module_available("pyaudiowpatch"),', '"aec": bool(\n                _module_available("pyaudiowpatch") and resolve_echo_canceller_library()\n            ),')
change('                "loopbackActive": self._loopback.active,', '                "loopbackActive": self._loopback.active,\n                "aec": self._aec_active,\n                "aecSha256": self._aec_sha256,')
change('# applies AEC; this stream is intentionally one-way preview.', '# receives the same cleaned audio; this stream is one-way preview.')
change('        references: list[np.ndarray] = []\n', '        canceller: EchoCanceller | None = None\n')
change('deque[tuple[np.ndarray, np.ndarray]]', 'deque[np.ndarray]', 2)
change('            cached: tuple[tuple[np.ndarray, np.ndarray], ...],', '            cached: tuple[np.ndarray, ...],')
change('            cached_audio = tuple(item[0] for item in cached)', '            cached_audio = cached')
change('            for cached_audio, cached_reference in cached:\n                utterance.append(cached_audio)\n                references.append(cached_reference)', '            utterance.extend(cached)')
change('            nonlocal utterance, references, silence_frames, speech_started', '            nonlocal utterance, silence_frames, speech_started')
change('            reference = (\n                np.concatenate(references) if references else np.empty(0, np.int16)\n            )\n', '')
change('            utterance, references = [], []', '            utterance = []')
change('                        audio,\n                        reference,\n                        origin,', '                        audio,\n                        canceller is not None,\n                        origin,')
change('            inbox = self._pcm_inbox\n', '''            if self._loopback.active and resolve_echo_canceller_library() is not None:
                canceller = EchoCanceller()
                if self._session_is_current(session_epoch):
                    self._aec_active = True
                    self._aec_sha256 = canceller.sha256
            inbox = self._pcm_inbox
''')
change('                    reference = self._loopback.latest(VAD_WINDOW_SAMPLES)\n                    probability = vad.process(mono)', '''                    history = self._loopback.latest(REFERENCE_SAMPLES)
                    if canceller is not None:
                        mono, echo_microphone, echo_reference = canceller.process(
                            mono, history
                        )
                    else:
                        echo_microphone, echo_reference = mono * 32768.0, history
                    probability = vad.process(mono)''')
change('''                        history = self._loopback.latest(
                            VAD_WINDOW_SAMPLES + int(0.25 * SAMPLE_RATE)
                        )
                        echo = _looks_like_echo(mono * 32768.0, history)''', '''                        echo = _looks_like_echo(echo_microphone, echo_reference)''')
change('acoustic_pre_roll.append((mono, reference))', 'acoustic_pre_roll.append(mono)')
change('vad_pre_roll.append((mono, reference))', 'vad_pre_roll.append(mono)')
change('                            references.append(reference)\n', '', 2)
change('''        finally:
            if speech_started:
                finish_utterance()
            if self._session_is_current(session_epoch):
                self._ducker.restore()
            ready_event.set()
''', '''        finally:
            try:
                if canceller is not None:
                    canceller.close()
            finally:
                if self._session_is_current(session_epoch):
                    self._aec_active = False
                if speech_started:
                    finish_utterance()
                if self._session_is_current(session_epoch):
                    self._ducker.restore()
                ready_event.set()
''')
change('''            elif isinstance(item, tuple) and len(item) == 2:
                # Compatibility seam for old diagnostic callers. Runtime
                # capture always carries an explicit origin now.
                request = _DecodeRequest(item[0], item[1], "direct")
''', '')
change('                    request.reference,', '                    request.aec_applied,')
change('        reference: np.ndarray,\n        origin: str = "direct",', '        aec_applied: bool,\n        origin: str = "direct",')
change('''        aec_applied = False
        if reference.size >= clean.size and _rms(reference) >= 80.0:
            clean = EchoCanceller().process(clean * 32768.0, reference[-clean.size :])
            aec_applied = True
''', '')
ast.parse(s)
path.write_text(s, encoding='utf-8')

path = root / 'src/baxy_mind/voice_aec.py'
s = path.read_text(encoding='utf-8')
tree = ast.parse(s)
node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'EchoCanceller')
lines = s.splitlines(keepends=True)
del lines[node.lineno-1:node.end_lineno]
s = ''.join(lines).replace('loopback WASAPI, AEC NLMS y ducking reversible', 'loopback WASAPI y ducking reversible').replace('CHUNK = 512\n', '')
path.write_text(s, encoding='utf-8')

path = root / 'tests/test_mind_voice_runtime.py'
s = path.read_text(encoding='utf-8')
tree = ast.parse(s)
lines = s.splitlines(keepends=True)
offsets = [0]
for line in lines:
    offsets.append(offsets[-1]+len(line))
edits = []
for n in ast.walk(tree):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == '_decode_utterance':
        arg = n.args[1]
        old = ast.get_source_segment(s, arg)
        assert old == 'np.empty(0, dtype=np.int16)', old
        edits.append((offsets[arg.lineno-1]+arg.col_offset, offsets[arg.end_lineno-1]+arg.end_col_offset, 'False'))
    if isinstance(n, ast.FunctionDef) and n.name == 'test_nlms_aec_reduces_a_delayed_reference':
        edits.append((offsets[n.lineno-1], offsets[n.end_lineno], ''))
for first, last, replacement in sorted(edits, reverse=True):
    s = s[:first]+replacement+s[last:]
s = s.replace('from baxy_mind.voice_aec import EchoCanceller\n', '')
ast.parse(s)
path.write_text(s, encoding='utf-8')

path = root / 'assets.manifest.json'
manifest = json.loads(path.read_text(encoding='utf-8'))
assert 'echo_canceller' not in manifest['assets']
manifest['assets']['echo_canceller'] = {
    'kind': 'file', 'required': False, 'environment': 'BAXY_AEC_LIBRARY',
    'candidates': ['${BAXY_ASSETS_ROOT}\\aec\\speexdsp-1.2.1\\speexdsp.dll',
                   'D:\\BAXYRuntime\\assets\\aec\\speexdsp-1.2.1\\speexdsp.dll',
                   '${LOCALAPPDATA}\\BAXYRuntime\\assets\\aec\\speexdsp-1.2.1\\speexdsp.dll'],
    'repair': 'Restaura SpeexDSP Windows atestado o declara BAXY_AEC_LIBRARY; sin el proveedor la captura informa AEC inactivo.',
}
path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'sourceEdited': ['voice.py','voice_aec.py','assets.manifest.json'], 'privateDecodeTestCallsUpdated': len(edits)-1}))
