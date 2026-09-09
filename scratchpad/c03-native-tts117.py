"""Isolate the missing sentence terminator in the current eSpeak CLI adapter."""
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
sys.path.insert(0, str(root / 'src'))
sys.stdout.reconfigure(encoding='utf-8')
from baxy_mind.voice_output import _PiperOnnxEngine
out = root / 'artifacts/comprobaciones/C03/astra-native-tts117'
out.mkdir(exist_ok=False)
assert not any(p.info['name'] in {'Baxy.exe', 'llama-server.exe'} for p in psutil.process_iter(['name']))
def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
prior = json.loads((out.parent / 'astra-native-tts114/PREREG.json').read_text(encoding='utf-8'))
manifest_path = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
assert sha(manifest_path) == prior['registrationSha256']
assert sha(root / 'src/baxy_mind/voice_output.py') == prior['sourceSha256']
model = Path(prior['model'])
assert sha(model) == prior['modelSha256']
prereg = {**prior, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'method': 'Same source112 engine/PAD, john medium voice/config and three consumed texts114. '
                    'Only add the actual final period to the exact observed CLI phoneme string. '
                    'All three inputs are single sentences ending in period. Upstream Piper phonemizer '
                    'preserves clause terminator, current CLI adapter discards it. This is a scoped '
                    'native experiment, not a general punctuation implementation, no product edit. '
                    'Same Parakeet CPU/no hints, no fixed ONNX noise seed, no physical audio.',
          'source': 'https://raw.githubusercontent.com/rhasspy/piper-phonemize/master/src/phonemize.cpp:99-119; consulted2026-09-07',
          'limitation': 'Punctuation/NFD/language flags/sentence segmentation differ in the manual frontend. '
                        'This experiment isolates only final period; do not claim canonical frontend parity.'}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
tts = _PiperOnnxEngine(model)
original_phonemes = tts._phonemes
stt = Path(manifest['stt_dir'])
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(stt / 'encoder.int8.onnx'), decoder=str(stt / 'decoder.int8.onnx'),
    joiner=str(stt / 'joiner.int8.onnx'), tokens=str(stt / 'tokens.txt'), num_threads=6,
    model_type='nemo_transducer', decoding_method='modified_beam_search', max_active_paths=8)
rows = []
for index, text in enumerate(prereg['cases']):
    assert text.endswith('.')
    phonemes = original_phonemes(text)
    assert not phonemes.endswith('.')
    tts._phonemes = lambda _text: phonemes + '.'
    start = time.monotonic()
    pcm = tts.generate(text)
    generation = time.monotonic() - start
    path = out / f'{index:02d}-with-period.wav'
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(tts.sample_rate)
        wav.writeframes((pcm * 32767).astype('<i2').tobytes())
    stream = recognizer.create_stream()
    stream.accept_waveform(16000, resample_poly(pcm, 16000, tts.sample_rate).astype(np.float32))
    recognizer.decode_stream(stream)
    row = {'index': index, 'text': text, 'phonemes': phonemes + '.',
           'seconds': pcm.size / tts.sample_rate, 'generationSeconds': generation,
           'transcript': str(stream.result.text or '').strip(), 'wavSha256': sha(path)}
    rows.append(row)
    (out / 'RESULTS.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(row, ensure_ascii=False), flush=True)
assert sha(root / 'src/baxy_mind/voice_output.py') == prior['sourceSha256']
