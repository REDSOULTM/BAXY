"""Verify per-stream native decoding with one model and unchanged contextual beam."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np
import psutil
from scipy.io import wavfile

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
experiment = Path('D:/BAXYRuntime/experiments/voice/sherpa205')
out = base/'astra-shared206'
out.mkdir(exist_ok=False)
bundle = experiment/'bundle-shared206'
bundle.mkdir(exist_ok=False)
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))
def save(name, data):
    (out/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
patch = subprocess.check_output(['git','-C',str(experiment/'source'),'diff','--',
    'sherpa-onnx/csrc/offline-recognizer-transducer-nemo-impl.h'])
(out/'shared-model.patch').write_bytes(patch)
binaries = []
for folder in [experiment/'build/bin/Release', experiment/'build/lib/Release']:
    for path in folder.iterdir():
        if path.suffix.lower() in {'.dll', '.pyd'}:
            target = bundle/path.name
            shutil.copy2(path, target)
            binaries.append({'path': str(target), 'sha256': sha(target)})
pyds = list(bundle.glob('_sherpa_onnx*.pyd'))
assert len(pyds) == 1
dll_handle = os.add_dll_directory(str(bundle))
native_name = 'sherpa_onnx.lib._sherpa_onnx'
spec = importlib.util.spec_from_file_location(native_name, pyds[0])
native = importlib.util.module_from_spec(spec)
sys.modules[native_name] = native
spec.loader.exec_module(native)
import sherpa_onnx
sys.path.insert(0, str(root/'src'))
from baxy_mind.voice import _compile_contextual_hotwords, WakePhraseMatcher

inputs = read(base/'astra-segment201-retry/RESULTS.json')
greedy_expected = read(base/'astra-greedy203/RESULTS.json')
beam_expected = read(base/'astra-native205-baseline/RESULTS.json')
humans = read(base/'astra-human195/DOWNLOADS.json')
manifest_path = Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest = read(manifest_path)
stt = Path(manifest['stt_dir'])
save('PREREG.json', {'method': 'One unchanged beam8 recognizer, CPU6. Alternate greedy_search stream override and default beam on same47 frozen inputs. Assert every greedy result equals203 and every beam result equals205 baseline, including silence. Context graph plus greedy must raise, unknown mode must raise. Compare mixed-method batch to individual outputs. No source/runtime installation, physical devices or calibration change.',
    'binaries': binaries, 'patchSha256': sha(out/'shared-model.patch'),
    'sourceCommit': '142807252687d81b40d6315f23470a1512a00de3',
    'runtimeSha256': sha(manifest_path), 'inputs': inputs, 'originals': humans})
process = psutil.Process()
start = time.monotonic()
rss_start = process.memory_info().rss
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(stt/'encoder.int8.onnx'), decoder=str(stt/'decoder.int8.onnx'),
    joiner=str(stt/'joiner.int8.onnx'), tokens=str(stt/'tokens.txt'),
    num_threads=6, model_type='nemo_transducer', decoding_method='modified_beam_search',
    max_active_paths=8, hotwords_score=5)
build_seconds = time.monotonic()-start
audio_inputs = []
for row in inputs:
    path = Path(row['privateOutput'])
    assert sha(path) == row['sha256']
    with np.load(path) as archive:
        for segment in row['segments']:
            audio_inputs.append(archive[f'segment{segment["index"]}'].copy())
for row in humans:
    path = Path(row['asset'])
    assert sha(path) == row['sha256']
    rate, audio = wavfile.read(path)
    assert rate == 16000
    audio_inputs.append(np.r_[np.zeros(16000,np.float32), audio, np.zeros(16000,np.float32)])
audio_inputs.append(np.zeros(32000, np.float32))
assert len(audio_inputs) == 47
def stream_for(audio, method=None, hotwords=''):
    stream = recognizer.create_stream(hotwords=hotwords) if hotwords else recognizer.create_stream()
    if method is not None:
        stream.set_option('decoding_method', method)
    stream.accept_waveform(16000, audio)
    return stream
rows = []
for index, audio in enumerate(audio_inputs):
    for method, expected in [('greedy_search', greedy_expected[index]['text']),
                              ('modified_beam_search', beam_expected[index]['text'])]:
        stream = stream_for(audio, 'greedy_search' if method == 'greedy_search' else None)
        start = time.monotonic()
        recognizer.decode_stream(stream)
        row = {'index': index, 'method': method, 'text': stream.result.text.strip(),
            'expected': expected, 'applied': stream.get_option('applied_decoding_method'),
            'seconds': time.monotonic()-start}
        rows.append(row)
        save('RESULTS.json', rows)
        assert row['text'] == expected, row
        assert row['applied'] == method, row
hotwords = _compile_contextual_hotwords(stt/'tokens.txt', WakePhraseMatcher().aliases)
rejections = []
for method, context in [('greedy_search', hotwords), ('unknown_decoder', '')]:
    stream = stream_for(audio_inputs[40], method, context)
    try:
        recognizer.decode_stream(stream)
    except ValueError as error:
        rejections.append({'method': method, 'hotwords': bool(context), 'error': str(error)})
    else:
        raise AssertionError('Invalid decoder/context combination silently accepted')
batch = [stream_for(audio_inputs[40], 'greedy_search'), stream_for(audio_inputs[40])]
recognizer.decode_streams(batch)
assert [s.result.text.strip() for s in batch] == [greedy_expected[40]['text'], beam_expected[40]['text']]
save('COMPLETE.json', {'readings': len(rows), 'identical': len(rows),
    'rejections': rejections, 'mixedBatchTexts': [s.result.text.strip() for s in batch],
    'buildSeconds': build_seconds, 'rssMiB': process.memory_info().rss/2**20,
    'incrementRssMiB': (process.memory_info().rss-rss_start)/2**20,
    'runtimeUnchanged': sha(manifest_path) == read(out/'PREREG.json')['runtimeSha256']})
print(json.dumps(read(out/'COMPLETE.json'), ensure_ascii=True), flush=True)
