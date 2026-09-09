"""Offline AEC comparison, preserved signals; no capture, output or effect routing."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import sys
import time
import wave

import numpy as np
from scipy.signal import correlate, correlation_lags, resample_poly
import psutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-webrtc174'
private_base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private = private_base / 'C03-webrtc174-private'
private.mkdir(exist_ok=False)
sys.path[:0] = [str(root / 'src'), 'D:/BAXYRuntime/experiments/voice/webrtc174/python']
from pywebrtc_audio import EchoCanceller as WebRtc
from baxy_mind.speex_aec import EchoCanceller as Speex
from baxy_mind.voice import SileroVad

inputs = []
def track(p):
    inputs.append({'privatePath': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size})
    return p
def read(p):
    with wave.open(str(track(p)), 'rb') as f:
        rate = f.getframerate()
        signal = np.frombuffer(f.readframes(f.getnframes()), '<i2').reshape(-1, f.getnchannels()).mean(axis=1) / 32768
    return np.asarray(resample_poly(signal, 16000, rate) if rate != 16000 else signal, dtype=np.float32)
def write(p, signal):
    with wave.open(str(p), 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
        f.writeframes(np.clip(signal * 32768, -32768, 32767).astype('<i2').tobytes())
def save(p, value):
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

index = json.loads((base / 'astra-voice149/OBSERVATION_INDEX.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256(Path(r['privatePath']).read_bytes()).hexdigest() == r['sha256'] for r in index)
tap = np.load(track(private_base / 'C03-voice149-private/tap149.npz'))
mic149 = tap['microphone'].ravel().astype(np.float32)
ref149 = tap['reference'][:, -512:].ravel().astype(np.float32) / 32768
cases = [('native_echo149', mic149, ref149)]
capture = json.loads((base / 'astra-voice127/AUDIO_RESULT.json').read_text(encoding='utf-8'))
origins = {k: dt.datetime.fromisoformat(v['streamReadyUtc']).timestamp() for k,v in capture['streams'].items()}
offset = round((origins['microphone'] - origins['loopback']) * 16000)
loop = read(private_base / 'C03-voice127-private/loopback.wav')
for name in ['physical_echo', 'near_only', 'physical_echo_plus_synthetic_near']:
    raw = read(private_base / f'C03-speex129-private/{name}-raw.wav')
    positions = np.arange(len(raw)) + offset
    ref = np.zeros_like(raw)
    valid = (positions >= 0) & (positions < len(loop))
    if name != 'near_only':
        ref[valid] = loop[positions[valid]]
    cases.append((name, raw, ref))
cases.append(('cold_silence', np.zeros(32000, np.float32), np.zeros(32000, np.float32)))
save(private / 'INPUTS.json', inputs)
save(out / 'INPUT_INDEX.json', {'privateIndex': str(private / 'INPUTS.json'), 'sha256': hashlib.sha256((private / 'INPUTS.json').read_bytes()).hexdigest(), 'cases': [{'name':n,'samples':len(m)} for n,m,r in cases], 'limits': '149 native exact arrays. 127/129 approximate streamReadyUtc alignment, as131. Near signal is synthetic. VAD qualification omits raw echo guard: an upper bound, not actual cancellation or full engine acceptance.'})

vad = SileroVad()
rows = []
for name, mic, ref in cases:
    for method in ('raw', 'speex', 'webrtc'):
        milliseconds = []
        before = psutil.Process().memory_info().rss
        if method == 'raw':
            clean = mic.copy()
        elif method == 'speex':
            n = len(mic) // 512 * 512
            history = np.r_[np.zeros(4000, np.float32), ref] * 32768
            if name == 'native_echo149':
                history[:4000] = tap['reference'][0, :-512]
            engine = Speex()
            chunks = []
            try:
                for first in range(0, n, 512):
                    t = time.perf_counter()
                    c, _, _ = engine.process(mic[first:first+512], history[first:first+4512])
                    milliseconds.append((time.perf_counter()-t)*1000)
                    chunks.append(c)
            finally:
                engine.close()
            clean = np.concatenate(chunks)
            if name == 'native_echo149':
                assert np.array_equal(clean, tap['clean'].ravel()), 'Speex149 replay mismatch'
        else:
            engine = WebRtc(sample_rate=16000, num_channels=1, stream_delay_ms=0)
            n = len(mic) // 160 * 160
            chunks = []
            for first in range(0, n, 160):
                t = time.perf_counter()
                c = engine.process(np.ascontiguousarray(mic[first:first+160]), np.ascontiguousarray(ref[first:first+160]))
                milliseconds.append((time.perf_counter()-t)*1000)
                chunks.append(c)
            clean = np.concatenate(chunks)
            del engine
        assert np.isfinite(clean).all()
        after = psutil.Process().memory_info().rss
        vad.reset()
        floor, run, longest, speech_frames, qualified = .002, 0, 0, 0, []
        for first in range(0, len(clean)-511, 512):
            frame = clean[first:first+512]
            probability = vad.process(frame)
            energy = float(np.sqrt(np.mean(frame.astype(np.float64)**2)))
            if probability < .5:
                floor = .98*floor + .02*energy
            speech_frames += int(probability >= .5)
            if probability >= .5 and energy >= max(.004, floor*1.8):
                run += 1
                qualified.append(first/16000)
                longest = max(longest, run)
            else:
                run = 0
        row = {'case':name,'method':method,'samples':len(clean),'speechFrames':speech_frames,
               'qualifiedFramesWithoutEchoGuard':len(qualified),'maxConsecutiveWithoutEchoGuard':longest,
               'firstQualifiedSeconds':qualified[0] if qualified else None,
               'rms':float(np.sqrt(np.mean(clean.astype(np.float64)**2))),
               'nativeTimeMs': {'mean':float(np.mean(milliseconds)), 'p99':float(np.quantile(milliseconds,.99)), 'total':sum(milliseconds)} if milliseconds else None,
               'rssDeltaBytes':after-before}
        if name == 'near_only' and method != 'raw':
            corr = correlate(clean, mic, method='fft')
            lags = correlation_lags(len(clean),len(mic))
            indices = np.flatnonzero((lags >= 0) & (lags < 2048))
            best = indices[np.argmax(abs(corr[indices]))]
            row['observedOutputLagSamples'] = int(lags[best])
        write(private / f'{name}-{method}.wav', clean)
        rows.append(row)
        save(out / 'RESULTS.json', rows)
        print(json.dumps(row), flush=True)
save(private / 'OUTPUT_INDEX.json', [{'privatePath':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in private.glob('*.wav')])
save(out / 'COMPLETE.json', {'exit':'normal','rows':len(rows),'numpy':np.__version__,'runtime':sys.executable,'sourceChanged':False,'runtimePromoted':False,'physicalAcceptance':False})
