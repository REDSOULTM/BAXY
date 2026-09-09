"""Stage attested development AEC and compare integrated owner to physical134 PCM."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys
import time

import numpy as np

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-native137'
out.mkdir(exist_ok=False)
experimental = Path('D:/BAXYRuntime/experiments/voice/speexdsp129')
prereg = json.loads((base / 'astra-speex129/PREREG.json').read_text(encoding='utf-8'))
dll = experimental / 'build/speexdsp.dll'
assert hashlib.sha256(dll.read_bytes()).hexdigest() == prereg['dllSha256']
asset = Path('D:/BAXYRuntime/assets/aec/speexdsp-1.2.1')
asset.mkdir(parents=True, exist_ok=False)
for source, name in [(dll, 'speexdsp.dll'), (experimental / 'speexdsp-1.2.1/COPYING', 'COPYING'),
                     (experimental / 'DOWNLOAD.json', 'DOWNLOAD.json'),
                     (root / 'scratchpad/c03-build-speex129.cmd', 'build.cmd'),
                     (root / 'scratchpad/c03-speex129.def', 'exports.def')]:
    shutil.copyfile(source, asset / name)
from baxy_mind.speex_aec import EchoCanceller, resolve_echo_canceller_library

assert resolve_echo_canceller_library() == asset / 'speexdsp.dll'
source = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-voice134-private'
observations = np.load(source / 'candidate134.npz')
pins = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in [
    'src/baxy_mind/speex_aec.py', 'src/baxy_mind/voice.py', 'src/baxy_mind/voice_aec.py', 'assets.manifest.json']}
(out / 'PREREG.json').write_text(json.dumps({'sources':pins, 'input':str(source/'candidate134.npz'),
    'inputSha256':hashlib.sha256((source/'candidate134.npz').read_bytes()).hexdigest(),
    'method':'No replay or capture. Feed exact recorded raw microphone/reference pairs134 to integrated session owner; demand bit-identical clean PCM and aligned raw guard pairs. Development asset staged from attested DLL; runtime manifest not promoted.'}, indent=2), encoding='utf-8')
canceller = EchoCanceller()
costs = []
expected_mic = np.zeros(512, dtype=np.float32)
expected_ref = np.zeros(4512, dtype=np.int16)
try:
    for raw, reference, expected in zip(observations['raw'], observations['reference'], observations['clean'], strict=True):
        start = time.perf_counter()
        clean, old_mic, old_ref = canceller.process(raw, reference)
        costs.append(time.perf_counter()-start)
        assert np.array_equal(clean, expected), len(costs)
        assert np.array_equal(old_mic, expected_mic), len(costs)
        assert np.array_equal(old_ref, expected_ref), len(costs)
        expected_mic, expected_ref = raw*32768, reference
finally:
    canceller.close()
result = {'frames':len(costs), 'cleanPcmBitIdentical':True, 'guardPairsAligned':True,
          'librarySha256':canceller.sha256, 'libraryPath':str(canceller.library_path),
          'meanFrameMs':1000*float(np.mean(costs)), 'p99FrameMs':1000*float(np.quantile(costs,.99)),
          'nativeOwnerClosed':canceller._state is None and canceller._preprocessor is None,
          'physicalAcceptance':False}
(out / 'RESULTS.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
