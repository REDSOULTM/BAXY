"""Compare frozen speech using an isolated native sherpa build, no installation."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time

import numpy as np
from scipy.io import wavfile

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
experiment = Path('D:/BAXYRuntime/experiments/voice/sherpa205')
label = sys.argv[1]
assert label in {'baseline', 'patched'}
out = base/f'astra-native205-{label}'
out.mkdir(exist_ok=False)
bundle = experiment/f'bundle-{label}'
bundle.mkdir(exist_ok=False)
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))
def save(name, data):
    (out/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

binaries = []
for folder in [experiment/'build/bin/Release', experiment/'build/lib/Release']:
    for path in folder.iterdir():
        if path.suffix.lower() in {'.dll', '.pyd'}:
            target = bundle/path.name
            if target.exists():
                assert sha(target) == sha(path)
            else:
                shutil.copy2(path, target)
                binaries.append({'path': str(target), 'sha256': sha(target)})
pyds = list(bundle.glob('_sherpa_onnx*.pyd'))
assert len(pyds) == 1
native_name = 'sherpa_onnx.lib._sherpa_onnx'
dll_handle = os.add_dll_directory(str(bundle))
spec = importlib.util.spec_from_file_location(native_name, pyds[0])
native = importlib.util.module_from_spec(spec)
sys.modules[native_name] = native
spec.loader.exec_module(native)
import sherpa_onnx
assert Path(sys.modules[native_name].__file__).resolve() == pyds[0].resolve()
sys.path.insert(0, str(root/'src'))
from baxy_mind.voice import _decode_offline_text

inputs = read(base/'astra-segment201-retry/RESULTS.json')
beam = read(base/'astra-decode202/RESULTS.json')
humans = read(base/'astra-human195/DOWNLOADS.json')
original_beam = [r for r in read(base/'astra-human197/RESULTS.json') if r['recognizer'] == 'parakeet']
manifest_path = Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest = read(manifest_path)
owner = experiment/'source/sherpa-onnx/csrc/offline-transducer-modified-beam-search-nemo-decoder.cc'
save('PREREG.json', {'label': label, 'binaries': binaries,
    'nativeModule': str(pyds[0]), 'decoderSourceSha256': sha(owner),
    'runtimeSha256': sha(manifest_path),
    'method': 'Same47 inputs and padding as203, modified_beam_search/paths8/CPU6, no hotwords or gain. Isolated native build with unchanged installed Python wrapper. Baseline then upstream3657 patch, preserve each reading.',
    'segments': inputs, 'originals': humans})
stt = Path(manifest['stt_dir'])
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(stt/'encoder.int8.onnx'), decoder=str(stt/'decoder.int8.onnx'),
    joiner=str(stt/'joiner.int8.onnx'), tokens=str(stt/'tokens.txt'),
    num_threads=6, model_type='nemo_transducer', decoding_method='modified_beam_search',
    max_active_paths=8)
results = []
def decode(fields, audio, previous):
    started = time.monotonic()
    text = _decode_offline_text(recognizer, audio)
    row = {**fields, 'text': text, 'installedBeamText': previous,
        'seconds': time.monotonic()-started}
    results.append(row)
    save('RESULTS.json', results)
    print(json.dumps(row, ensure_ascii=True), flush=True)
for row in inputs:
    path = Path(row['privateOutput'])
    assert sha(path) == row['sha256']
    with np.load(path) as archive:
        for segment in row['segments']:
            previous = next(r for r in beam if r['case'] == row['case'] and r['segment'] == segment['index'])
            decode({k: previous[k] for k in ['case','human','condition','engine','segment','humanOverlapSamples']},
                archive[f'segment{segment["index"]}'], previous['text'])
for i, row in enumerate(humans):
    path = Path(row['asset'])
    assert sha(path) == row['sha256']
    rate, audio = wavfile.read(path)
    assert rate == 16000
    audio = np.r_[np.zeros(16000, np.float32), audio, np.zeros(16000, np.float32)]
    decode({'original': True, 'human': i}, audio,
        next(r['text'] for r in original_beam if r['input'] == i))
decode({'silenceControl': True}, np.zeros(32000, np.float32), None)
save('COMPLETE.json', {'readings': len(results), 'sourceChanged': False,
    'runtimeUnchanged': sha(manifest_path) == read(out/'PREREG.json')['runtimeSha256']})
