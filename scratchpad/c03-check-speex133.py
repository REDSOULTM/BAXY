"""Adjudicate130 PCM against the existing echo guard and an independent local ASR."""
from pathlib import Path
import datetime as dt
import json
import os
import sys
import wave
import numpy as np
from scipy.signal import resample_poly
import sherpa_onnx

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
sys.stdout.reconfigure(encoding='utf-8')
from baxy_mind.voice import SileroVad, _looks_like_echo

base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = root / 'artifacts/comprobaciones/C03/astra-speex133'
out.mkdir(exist_ok=False)

def read(path):
    with wave.open(str(path), 'rb') as wav:
        rate = wav.getframerate()
        audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').reshape(-1, wav.getnchannels()).mean(axis=1)/32768
    return resample_poly(audio, 16000, rate) if rate != 16000 else audio

capture = json.loads((root / 'artifacts/comprobaciones/C03/astra-voice125/AUDIO_RESULT.json').read_text(encoding='utf-8'))
origins = {k: dt.datetime.fromisoformat(v['streamReadyUtc']).timestamp() for k, v in capture['streams'].items()}
offset = round((origins['microphone'] - origins['loopback']) * 16000)
events = [json.loads(line) for line in (root / 'artifacts/comprobaciones/C03/astra-voice125/EVENTS.jsonl').read_text(encoding='utf-8').splitlines()]
start = next(e for e in events if e.get('speaking') and e['phase'] == 'direct')
end = next(e for e in events if e.get('speaking') is False and e['monotonic'] > start['monotonic'])
first_speech = round((dt.datetime.fromisoformat(start['utc']).timestamp()-origins['microphone'])*16000)
last_speech = round((dt.datetime.fromisoformat(end['utc']).timestamp()-origins['microphone'])*16000)
ready = next(e for e in events if e['event'] == 'ready' and e['phase'] == 'direct')
crop_first = max(0, round((dt.datetime.fromisoformat(ready['utc']).timestamp()-origins['microphone'])*16000))
first_speech -= crop_first
last_speech -= crop_first
offset += crop_first
loop = read(base / 'C03-voice125-private/loopback.wav')
manifest = json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json').read_text(encoding='utf-8'))
stt = Path(manifest['stt_dir'])
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(stt/'encoder.int8.onnx'), decoder=str(stt/'decoder.int8.onnx'),
    joiner=str(stt/'joiner.int8.onnx'), tokens=str(stt/'tokens.txt'), num_threads=6,
    model_type='nemo_transducer', decoding_method='modified_beam_search', max_active_paths=8)
vad = SileroVad()
rows = []
for name in ['physical_echo']:
    raw = read(base / f'C03-speex132-private/{name}-raw.wav')
    processed = read(base / f'C03-speex132-private/{name}-aec_residual.wav')
    for alignment_phase in range(0, 512, 64):
        for method, signal, delay in [('raw_with_existing_guard', raw, 0), ('aec_with_existing_guard', processed, 512)]:
            vad.reset()
            floor, count = .002, 0
            barge = []
            candidates = []
            for first in range(alignment_phase, signal.size-511, 512):
                frame = signal[first:first+512].astype(np.float32)
                probability = vad.process(frame)
                energy = float(np.sqrt(np.mean(frame**2)))
                if probability < .5:
                    floor = .98*floor + .02*energy
                if not first_speech <= first <= last_speech:
                    continue
                if probability >= .5:
                    aligned = max(0, first-delay)
                    ref_end = min(loop.size, aligned+512+offset)
                    history = loop[max(0, ref_end-4512):ref_end] if name != 'near_only' else np.zeros(4512)
                    echo = _looks_like_echo(raw[aligned:aligned+512]*32768, history*32768)
                    if echo:
                        count = 0
                    elif energy >= max(.004, floor*1.8):
                        count += 1
                        candidates.append(round((first-first_speech)/16000, 3))
                        if count == 3:
                            barge.append(round((first-first_speech)/16000, 3))
                    else:
                        count = 0
            window = signal[max(0, first_speech-8000):min(signal.size, last_speech+8000)]
            stream = recognizer.create_stream()
            stream.accept_waveform(16000, window.astype(np.float32))
            recognizer.decode_stream(stream)
            row = {'case': name, 'alignmentPhaseSamples': alignment_phase, 'method': method, 'bargeSequencesSeconds': barge,
                   'candidateSeconds': candidates, 'transcript': str(stream.result.text or '').strip()}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            (out / 'RESULTS.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
(out / 'LIMITS.json').write_text(json.dumps({
    'input': 'Failed direct125, fixed eight capture-frame phases0..448 step64 to test sensitivity; no tuning or best-phase selection; local CPU only',
    'alignment': 'Approximate common streamReadyUtc; preprocessor one-frame delay compensated for echo guard',
    'criterion': 'Existing VAD/energy/count/echo thresholds unchanged; no effect routing. Do not infer live scheduling, causal mic/reference synchronization or physical double-talk acceptance.',
}, indent=2), encoding='utf-8')
