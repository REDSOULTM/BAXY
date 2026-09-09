"""Upstream Windows Piper as a reference for the incomplete handwritten frontend."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
import wave

import numpy as np
import psutil
from scipy.signal import resample_poly
import sherpa_onnx

root = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8')
out = root / 'artifacts/comprobaciones/C03/astra-reference-tts118'
out.mkdir(exist_ok=False)
assert not any(p.info['name'] in {'Baxy.exe', 'llama-server.exe'} for p in psutil.process_iter(['name']))
def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
manifest_path = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
prior = json.loads((out.parent / 'astra-native-tts114/PREREG.json').read_text(encoding='utf-8'))
assert sha(manifest_path) == prior['registrationSha256']
assert sha(root / 'src/baxy_mind/voice_output.py') == prior['sourceSha256']
runtime = Path('D:/BAXYRuntime/experiments/voice/piper-reference118/piper')
models = {'en': Path(prior['model']), 'es': Path(manifest['tts_model'])}
cases = [{'language': 'en', 'text': t} for t in prior['cases']]
cases += [{'language': 'es', 'text': t} for t in ['¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?', 'Son las 07:13.', 'Son las 07:15.']]
prereg = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'method': 'Official archived MIT Piper Windows2023.11.14-2 as reference. Same two voice '
                    'packages already measured, CPU/default scales, default0.2s sentence silence. '
                    'One CLI process per text, debug phonemes/IDs preserved. This contrasts whole '
                    'reference frontend/backend, not punctuation alone (native117 isolated period). '
                    'Includes punctuation, NFD, language-flag handling and sentence segmentation. '
                    'Parakeet CPU/no hints; no playback, user reserve or runtime promotion.',
          'source': 'https://github.com/rhasspy/piper/releases/tag/2023.11.14-2',
          'archiveSha256': 'f3c58906402b24f3a96d92145f58acba6d86c9b5db896d207f78dc80811efcea',
          'runtimeHashes': {n: sha(runtime / n) for n in ('piper.exe', 'piper_phonemize.dll', 'espeak-ng.dll', 'onnxruntime.dll')},
          'cases': cases, 'models': {lang: {'path': str(p), 'sha256': sha(p), 'configSha256': sha(p.with_suffix('.onnx.json'))} for lang, p in models.items()},
          'sourceSha256': prior['sourceSha256'], 'registrationSha256': sha(manifest_path)}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
stt = Path(manifest['stt_dir'])
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(stt / 'encoder.int8.onnx'), decoder=str(stt / 'decoder.int8.onnx'),
    joiner=str(stt / 'joiner.int8.onnx'), tokens=str(stt / 'tokens.txt'), num_threads=6,
    model_type='nemo_transducer', decoding_method='modified_beam_search', max_active_paths=8)
rows = []
for index, case in enumerate(cases):
    path = out / f'{index:02d}-reference.wav'
    start = time.monotonic()
    result = subprocess.run([str(runtime / 'piper.exe'), '--model', str(models[case['language']]),
                             '--output_file', str(path), '--debug', '--espeak_data', str(runtime / 'espeak-ng-data')],
                            input=(case['text'] + '\n').encode('utf-8'), capture_output=True, timeout=40)
    generation = time.monotonic() - start
    (out / f'{index:02d}-reference.log').write_bytes(result.stdout + b'\n' + result.stderr)
    assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')
    with wave.open(str(path), 'rb') as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
        rate = wav.getframerate()
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float32) / 32768
    stream = recognizer.create_stream()
    stream.accept_waveform(16000, resample_poly(pcm, 16000, rate).astype(np.float32))
    recognizer.decode_stream(stream)
    row = {'index': index, **case, 'seconds': pcm.size / rate, 'generationAndProcessSeconds': generation,
           'transcript': str(stream.result.text or '').strip(), 'wavSha256': sha(path)}
    rows.append(row)
    (out / 'RESULTS.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(row, ensure_ascii=False), flush=True)
assert sha(manifest_path) == prereg['registrationSha256']
assert sha(root / 'src/baxy_mind/voice_output.py') == prior['sourceSha256']
