"""Transcribe preserved 113/114 PCM with a second existing local recognizer."""
from pathlib import Path
import datetime
import hashlib
import json
import sys
import wave

import numpy as np
import psutil
from scipy.signal import resample_poly
import sherpa_onnx

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
sys.path.insert(0, str(root / 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
from baxy_mind.voice import resolve_streaming_stt_directory
from test_mind_voice import transcribe_streaming
flush = '--flush' in sys.argv
out = root / ('artifacts/comprobaciones/C03/astra-observe-tts116' if flush else 'artifacts/comprobaciones/C03/astra-observe-tts115')
out.mkdir(exist_ok=False)
assert not any(p.info['name'] in {'Baxy.exe', 'llama-server.exe'} for p in psutil.process_iter(['name']))
def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
stt = resolve_streaming_stt_directory()
assert stt is not None
inputs = []
for tranche in (113, 114):
    directory = out.parent / f'astra-native-tts{tranche}'
    rows = json.loads((directory / 'RESULTS.json').read_text(encoding='utf-8'))
    for row in rows:
        if tranche == 113 and row['phonemizerVoice'] != 'en-us':
            continue
        path = directory / f"{row['index']:02d}-en-us.wav"
        assert sha(path) == row['wavSha256']
        inputs.append({'tranche': tranche, 'index': row['index'], 'path': str(path),
                       'sha256': sha(path), 'priorTranscript': row['transcript']})
prereg = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'method': 'No synthesis or playback. Existing Nemotron streaming CPU bundle, product helper '
                    'transcribe_streaming, greedy/auto language, no hints or expected text. Same '
                    'preserved PCM from all three English candidates113/114; no regeneration, '
                    'no selecting a favorable run. Independent model observation helps distinguish '
                    'Parakeet transcription error from speech content; neither alone proves human hearing.',
          'inputs': inputs, 'recognizer': str(stt),
          'tailPaddingSeconds': 0.66 if flush else 0.0,
          'tailPaddingSource': 'https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/master/python-api-examples/online-decode-files.py:383-387; consulted2026-09-07; append0.66s silence before input_finished. Observer115 had no tail and truncated final tokens;116 changes only flush, no resynthesis.',
          'recognizerHashes': {name: sha(stt / name) for name in ('encoder.int8.onnx', 'decoder.int8.onnx', 'joiner.int8.onnx', 'tokens.txt')}}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
    encoder=str(stt / 'encoder.int8.onnx'), decoder=str(stt / 'decoder.int8.onnx'),
    joiner=str(stt / 'joiner.int8.onnx'), tokens=str(stt / 'tokens.txt'), num_threads=6,
    model_type='nemo_transducer', decoding_method='greedy_search',
    enable_endpoint_detection=False, provider='cpu')
results = []
for item in inputs:
    with wave.open(item['path'], 'rb') as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
        rate = wav.getframerate()
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(np.float32) / 32768
    pcm = resample_poly(pcm, 16000, rate).astype(np.float32)
    if flush:
        pcm = np.concatenate((pcm, np.zeros(int(0.66 * 16000), dtype=np.float32)))
    transcript, elapsed = transcribe_streaming(recognizer, pcm)
    row = {**item, 'transcript': transcript, 'decodeSeconds': elapsed}
    results.append(row)
    (out / 'RESULTS.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(row, ensure_ascii=False), flush=True)
