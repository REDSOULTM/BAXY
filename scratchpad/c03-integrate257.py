"""Finish the AEC owner replacement using the preserved255 input snapshot."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'astra-integration257'
OUT.mkdir(exist_ok=False)
before = json.loads((BASE / 'astra-integration255/BEFORE.json').read_text())
for name, expected in before.items():
    original = BASE / 'astra-integration255/before' / name
    assert hashlib.sha256(original.read_bytes()).hexdigest() == expected
    if name not in {'src/baxy_mind/voice.py', 'src/baxy_mind/voice_capture.py', 'runtime_wheels/README.md'}:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    target = OUT / 'before' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    # README changed in255 and is snapshotted at its actual current version.
    shutil.copyfile(ROOT / name if name == 'runtime_wheels/README.md' else original, target)
(OUT / 'PREREG.json').write_text(json.dumps({
    'hypothesis': 'Integrate the exact native255 two-view bridge and capture253 admission, one independent confirmation VAD per acoustic capture session. Replace DTLN, no cascade or new gains.',
    'before': {name: hashlib.sha256((OUT / 'before' / name).read_bytes()).hexdigest() for name in before},
    'scope': 'Native owner, capture, dependency graph, AEC descriptor/installer retirement, tests and owner docs. Preserve human content, echo controls and source lifecycle semantics.',
    'validation': 'Owner tests, lock installation, all12 DSP parity, actual capture/ASR253 parity, Fast; physical/UI/combined resources and full C03 acceptance remain.',
    'previousTurn': 'Progress: versioned native package built and verified, 13433 exact blocks, tests/Fast; no external blocker.'
}, indent=2)+'\n', encoding='utf-8')

def replace(name, old, new, count=1):
    path = ROOT / name
    text = path.read_text(encoding='utf-8')
    assert text.count(old) == count, (name, old, text.count(old))
    path.write_text(text.replace(old,new), encoding='utf-8', newline='\n')

replace('src/baxy_mind/requirements-voice.txt', 'ai-edge-litert==2.2.0', 'pywebrtc-audio==0.2.0+baxy.1')
replace('constraints-runtime-win-x64.txt', 'ai-edge-litert==2.2.0\n', '')
replace('constraints-runtime-win-x64.txt', 'backports.strenum==1.2.8\n', '')
replace('constraints-runtime-win-x64.txt', 'ml_dtypes==0.5.4\n', '')
replace('constraints-runtime-win-x64.txt', 'pywin32==311\n', 'pywebrtc-audio==0.2.0+baxy.1\npywin32==311\n')
path = ROOT / 'assets.manifest.json'
manifest = json.loads(path.read_text(encoding='utf-8'))
assert manifest['assets'].pop('echo_canceller')['environment'] == 'BAXY_AEC_MODEL_DIR'
path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
replace('scripts/run_voice_system_gate.py', 'baxy_mind.dtln_aec', 'baxy_mind.webrtc_aec')
replace('scripts/run_voice_system_gate.py', '"ai-edge-litert": ("2.2.0", "Apache-2.0"),', '"pywebrtc-audio": ("0.2.0+baxy.1", "Apache-2.0; bundled WebRTC and third-party notices"),')
replace('scripts/run_voice_system_gate.py', 'clean_frame, _, _ = canceller.process(', 'frame = canceller.process(')
replace('scripts/run_voice_system_gate.py', 'frames.append(clean_frame)', 'frames.append(frame.confirmation)')
replace('scripts/run_voice_system_gate.py', 'DTLN512 streaming capture AEC (CPU)', 'AEC3 aligned recognition/confirmation signals (CPU)')
replace('tests/test_python_runtime_lock.py', 'assert len(locked) == 62\n    assert locked["ai-edge-litert"] == "2.2.0"\n    assert locked["backports-strenum"] == "1.2.8"\n    assert locked["ml-dtypes"] == "0.5.4"',
    'assert len(locked) == 60\n    assert locked["pywebrtc-audio"] == "0.2.0+baxy.1"\n    assert not {"ai-edge-litert", "backports-strenum", "ml-dtypes"} & locked.keys()')
replace('docs/AI_CONTEXT_MAP.md', 'AEC en `dtln_aec.py` (activos: `scripts/install_dtln_aec.py`)', 'AEC en `webrtc_aec.py` (paquete: `scripts/build_webrtc_runtime.py`)')
replace('tests/test_mind_voice_runtime.py', '    monkeypatch.setattr(voice_module, "resolve_echo_canceller_directory", lambda: Path("fixture-models"))\n', '')
replace('tests/test_mind_voice_runtime.py', 'return mic * 3, mic * 32768, reference', 'return mic * 3, mic * 2, mic * 32768, reference')
replace('tests/test_mind_voice_runtime.py', '    engine._vad = Vad()  # noqa: SLF001\n',
    '    engine._vad = Vad()  # noqa: SLF001\n    monkeypatch.setattr(voice_module, "SileroVad", lambda: _SequenceVad([0.0, 0.0, *([0.9] * 12), *([0.0] * 23)]))\n')
for name in ('src/baxy_mind/dtln_aec.py', 'src/baxy_mind/licenses/DTLN-aec.txt',
             'scripts/install_dtln_aec.py', 'tests/test_dtln_aec.py'):
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == before[name]
    (ROOT/name).unlink()
print('257 owner/metadata replacement applied; lock generation and tests pending')
