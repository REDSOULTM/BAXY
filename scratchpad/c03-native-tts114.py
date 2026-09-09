"""Native English voice probe; no playback, application or user reserve."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import sys
import time
import wave

import numpy as np
import psutil
from scipy.signal import resample_poly
import sherpa_onnx

root = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(root / 'src'))
from baxy_mind.voice_output import _PiperOnnxEngine
out = root / 'artifacts/comprobaciones/C03/astra-native-tts114'
assert not any(p.info['name'] in {'Baxy.exe', 'llama-server.exe'} for p in psutil.process_iter(['name']))
def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
download = json.loads((out / 'DOWNLOAD.json').read_text(encoding='utf-8'))
for entry in download['files']:
    assert sha(entry['path']) == entry['sha256']
model = Path(next(x['path'] for x in download['files'] if x['path'].endswith('.onnx')))
manifest_path = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
prior = json.loads((out.parent / 'astra-native-tts113/PREREG.json').read_text(encoding='utf-8'))
assert sha(root / 'src/baxy_mind/voice_output.py') == prior['sourceSha256']
assert sha(manifest_path) == prior['registrationSha256']
prereg = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'method': 'Same source112 engine/PAD, voice package configured English phonemizer en, CPU/default inference scales. '
                    'Replace Spanish ONNX/config with English john medium ONNX/config; comparison is '
                    'trained voice package, not weights alone. Same three consumed English responses '
                    'as native113, no human reserve. Same registered Parakeet CPU, no hints/prompt. '
                    'ASR errors require inspection; no physical audio, classifier or promotion.',
          'cases': prior['cases'], 'model': str(model), 'modelSha256': sha(model),
          'configSha256': sha(model.with_suffix('.onnx.json')),
          'sourceSha256': prior['sourceSha256'], 'registrationSha256': sha(manifest_path)}
if '--resume' in sys.argv:
    saved = json.loads((out / 'PREREG.json').read_text(encoding='utf-8'))
    assert {k: v for k, v in prereg.items() if k != 'utc'} == {k: v for k, v in saved.items() if k != 'utc'}
else:
    with (out / 'PREREG.json').open('x', encoding='utf-8') as f:
        json.dump(prereg, f, ensure_ascii=False, indent=2)
tts = _PiperOnnxEngine(model)
assert tts._voice == 'en'
stt = Path(manifest['stt_dir'])
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(stt / 'encoder.int8.onnx'), decoder=str(stt / 'decoder.int8.onnx'),
    joiner=str(stt / 'joiner.int8.onnx'), tokens=str(stt / 'tokens.txt'), num_threads=6,
    model_type='nemo_transducer', decoding_method='modified_beam_search', max_active_paths=8)
rows = json.loads((out / 'RESULTS.json').read_text(encoding='utf-8')) if '--resume' in sys.argv else []
for index, text in enumerate(prereg['cases']):
    if index < len(rows):
        assert rows[index]['index'] == index and rows[index]['text'] == text
        assert sha(out / f'{index:02d}-en-us.wav') == rows[index]['wavSha256']
        continue
    start = time.monotonic()
    pcm = tts.generate(text)
    generation = time.monotonic() - start
    path = out / f'{index:02d}-en-us.wav'
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(tts.sample_rate)
        wav.writeframes((pcm * 32767).astype('<i2').tobytes())
    stream = recognizer.create_stream()
    stream.accept_waveform(16000, resample_poly(pcm, 16000, tts.sample_rate).astype(np.float32))
    recognizer.decode_stream(stream)
    row = {'index': index, 'text': text, 'phonemes': tts._phonemes(text),
           'seconds': pcm.size / tts.sample_rate, 'generationSeconds': generation,
           'transcript': str(stream.result.text or '').strip(), 'wavSha256': sha(path)}
    rows.append(row)
    (out / 'RESULTS.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(row, ensure_ascii=False), flush=True)
assert sha(manifest_path) == prereg['registrationSha256']
assert sha(root / 'src/baxy_mind/voice_output.py') == prereg['sourceSha256']
