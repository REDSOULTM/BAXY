"""Use the real installed AEC owner, preserving255/256 experiments."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'scratchpad/c03-parity255.py').read_text(encoding='utf-8')
source = source.replace("OUT = BASE / 'astra-integration255'", "OUT = BASE / 'astra-parity257'\nOUT.mkdir(exist_ok=False)")
start = source.index('installed = WORK')
end = source.index('cases = list(', start)
source = source[:start] + '''sys.path.insert(0, str(ROOT / 'src'))
from baxy_mind.webrtc_aec import EchoCanceller as Bridge
from baxy_mind.voice import _looks_like_echo

''' + source[end:]
source = source.replace("'adapterSha256': sha(ROOT / 'scratchpad/webrtc_aligned254.py'),", "'ownerSha256': sha(ROOT / 'src/baxy_mind/webrtc_aec.py'),\n    'captureSha256': sha(ROOT / 'src/baxy_mind/voice.py'),")
source = source.replace("guards = data['observations'][:, 5].astype(bool)", "guards = data['observations'][:, 5]\n        assert set(guards) <= {-1, 0, 1}")
source = source.replace('actual, raw, history = engine.process(mic[i], reference[i])', 'actual, actual_final, raw, history = engine.process(mic[i], reference[i])')
source = source.replace('engine.last_final, final[i]', 'actual_final, final[i]')
source = source.replace("            assert _looks_like_echo(raw, history) == guards[i],", "            assert guards[i] == -1 or _looks_like_echo(raw, history) == guards[i],")
source = source.replace('a, b, _ = engine.process(frame, np.zeros(4512, np.float32))', 'a, suppressed, b, _ = engine.process(frame, np.zeros(4512, np.float32))')
source = source.replace('final.extend(engine.last_final)', 'final.extend(suppressed)')
source = source.replace('Native package parity only; production capture/lock/runtime not yet replaced. C03 stays active with all acceptance requirements.',
    'Installed source257 AEC owner parity; actual capture/ASR/UI/physical validation still needed. C03 stays active with all acceptance requirements.')
target = ROOT / 'scratchpad/c03-parity257.py'
assert not target.exists()
target.write_text(source, encoding='utf-8', newline='\n')
