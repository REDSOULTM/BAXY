"""Offline SpeexDSP comparison; existing physical capture and labelled PCM controls."""
from pathlib import Path
import ctypes as c
import datetime as dt
import hashlib
import json
import os
import sys
import time
import wave
import numpy as np
from scipy.signal import resample_poly

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
sys.stdout.reconfigure(encoding='utf-8')
from baxy_mind.voice import SileroVad

out = root / 'artifacts/comprobaciones/C03/astra-speex132'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-speex132-private'
private.mkdir(exist_ok=False)
source = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-voice125-private'
dll = Path('D:/BAXYRuntime/experiments/voice/speexdsp129/build/speexdsp.dll')
lib = c.CDLL(str(dll))
ptr = c.POINTER(c.c_int16)
for name, arguments, result in [
    ('speex_echo_state_init', [c.c_int, c.c_int], c.c_void_p),
    ('speex_echo_state_destroy', [c.c_void_p], None),
    ('speex_echo_cancellation', [c.c_void_p, ptr, ptr, ptr], None),
    ('speex_echo_ctl', [c.c_void_p, c.c_int, c.c_void_p], c.c_int),
    ('speex_preprocess_state_init', [c.c_int, c.c_int], c.c_void_p),
    ('speex_preprocess_state_destroy', [c.c_void_p], None),
    ('speex_preprocess_run', [c.c_void_p, ptr], c.c_int),
    ('speex_preprocess_ctl', [c.c_void_p, c.c_int, c.c_void_p], c.c_int),
]:
    function = getattr(lib, name)
    function.argtypes, function.restype = arguments, result

def read(path):
    with wave.open(str(path), 'rb') as wav:
        rate = wav.getframerate()
        audio = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').reshape(-1, wav.getnchannels()).mean(axis=1) / 32768
    return resample_poly(audio, 16000, rate) if rate != 16000 else audio

capture = json.loads((root / 'artifacts/comprobaciones/C03/astra-voice125/AUDIO_RESULT.json').read_text(encoding='utf-8'))
mic, loop = read(source / 'microphone.wav'), read(source / 'loopback.wav')
origins = {k: dt.datetime.fromisoformat(v['streamReadyUtc']).timestamp() for k, v in capture['streams'].items()}
offset = round((origins['microphone'] - origins['loopback']) * 16000)
reference = np.zeros_like(mic)
for first in range(0, mic.size, 512):
    indices = np.arange(first, min(first + 512, mic.size)) + offset
    valid = (indices >= 0) & (indices < loop.size)
    reference[first:first + indices.size][valid] = loop[indices[valid]]
events = [json.loads(line) for line in (root / 'artifacts/comprobaciones/C03/astra-voice125/EVENTS.jsonl').read_text(encoding='utf-8').splitlines()]
started = next(e for e in events if e.get('speaking') and e['phase'] == 'direct')
speech_start = round((dt.datetime.fromisoformat(started['utc']).timestamp() - origins['microphone']) * 16000)

ready = next(e for e in events if e['event'] == 'ready' and e['phase'] == 'direct')
ended = next(e for e in events if e.get('speaking') is False and e['monotonic'] > started['monotonic'])
crop_first = max(0, round((dt.datetime.fromisoformat(ready['utc']).timestamp() - origins['microphone']) * 16000))
crop_last = min(mic.size, round((dt.datetime.fromisoformat(ended['utc']).timestamp() - origins['microphone'] + 1) * 16000))
mic, reference = mic[crop_first:crop_last], reference[crop_first:crop_last]
speech_start -= crop_first
near = np.zeros_like(mic)
near_source = root / 'artifacts/comprobaciones/C03/astra-native-voice120/00-queue.wav'
voice = read(near_source)
voice *= .03 / np.max(np.abs(voice))
near_start = speech_start + 16000
near[near_start:near_start + voice.size] = voice[:near.size - near_start]
prereg = {'source': 'Existing failed125 direct microphone/loopback; crop from ready to speaking-end+1s, excludes off-before adaptation; no playback',
          'dll': str(dll), 'dllSha256': hashlib.sha256(dll.read_bytes()).hexdigest(),
          'frameSamples': 512, 'tailSamples': 3200, 'sampleRate': 16000,
          'alignment': 'Capture streamReadyUtc, approximate; no best-lag tuning',
          'nearControl': 'Known synthetic Piper ES greeting120, peak0.03, inserted1s after speaking; not human/physical acceptance',
          'nearSha256': hashlib.sha256(near_source.read_bytes()).hexdigest(),
          'cases': ['physical_echo', 'near_only', 'physical_echo_plus_synthetic_near'],
          'methods': ['raw', 'aec_residual'],
          'preprocessor': 'Echo state linked; Default denoise enabled as upstream testecho.c; AGC off; echo suppression defaults unchanged.129 disabled all spectral gain unintentionally.',
          'criteria': 'Diagnose remaining voiced/energetic echo and preserve near words; no runtime adoption from ERLE alone'}
(out / 'PREREG.json').write_text(json.dumps(prereg, indent=2), encoding='utf-8')

def process(audio, playback, residual):
    state = lib.speex_echo_state_init(512, 3200)
    assert state
    rate = c.c_int(16000)
    assert lib.speex_echo_ctl(state, 24, c.byref(rate)) == 0
    pre = lib.speex_preprocess_state_init(512, 16000) if residual else None
    if pre:
        zero = c.c_int(0)
        # Default denoise enables all spectral gain, including echo suppression.
        assert lib.speex_preprocess_ctl(pre, 2, c.byref(zero)) == 0
        assert lib.speex_preprocess_ctl(pre, 24, state) == 0
    result = []
    times = []
    try:
        for first in range(0, audio.size, 512):
            recorded = np.clip(np.pad(audio[first:first+512], (0, max(0, first+512-audio.size))) * 32768, -32768, 32767).astype(np.int16)
            played = np.clip(np.pad(playback[first:first+512], (0, max(0, first+512-playback.size))) * 32768, -32768, 32767).astype(np.int16)
            clean = np.empty(512, dtype=np.int16)
            begin = time.perf_counter()
            lib.speex_echo_cancellation(state, recorded.ctypes.data_as(ptr), played.ctypes.data_as(ptr), clean.ctypes.data_as(ptr))
            if pre:
                lib.speex_preprocess_run(pre, clean.ctypes.data_as(ptr))
            times.append(time.perf_counter() - begin)
            result.append(clean.astype(np.float32)/32768)
    finally:
        if pre:
            lib.speex_preprocess_state_destroy(pre)
        lib.speex_echo_state_destroy(state)
    return np.concatenate(result)[:audio.size], {'meanFrameMs': 1000 * float(np.mean(times)), 'p99FrameMs': 1000 * float(np.quantile(times, .99))}

vad = SileroVad()
rows = []
for name, audio, playback in [('physical_echo', mic, reference), ('near_only', near, np.zeros_like(near)), ('physical_echo_plus_synthetic_near', mic + near, reference)]:
    for method in ['raw', 'aec_residual']:
        clean, cost = (audio, {}) if method == 'raw' else process(audio, playback, method == 'aec_residual')
        vad.reset()
        active = []
        floor = .002
        count = longest = 0
        first_three = None
        for first in range(0, clean.size - 511, 512):
            frame = clean[first:first + 512].astype(np.float32)
            probability = vad.process(frame)
            rms = float(np.sqrt(np.mean(frame ** 2)))
            if probability < .5:
                floor = .98 * floor + .02 * rms
            qualifies = probability >= .5 and rms >= max(.004, floor * 1.8)
            count = count + 1 if qualifies else 0
            longest = max(longest, count)
            if count == 3 and first_three is None:
                first_three = round((first - speech_start) / 16000, 3)
            if qualifies:
                active.append(first)
        segment = clean[speech_start:speech_start + 6*16000]
        baseline = audio[speech_start:speech_start + 6*16000]
        target = private / f'{name}-{method}.wav'
        with wave.open(str(target), 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
            wav.writeframes(np.clip(clean * 32768, -32768, 32767).astype('<i2').tobytes())
        row = {'case': name, 'method': method, **cost,
               'energyReductionDb': float(10 * np.log10((np.mean(baseline**2)+1e-20)/(np.mean(segment**2)+1e-20))),
               'qualifiedFrames': len(active), 'longestConsecutiveFrames': longest,
               'firstThreeRelativeToSpeechSeconds': first_three,
               'privatePath': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
        rows.append(row)
        print(json.dumps(row), flush=True)
        (out / 'RESULTS.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
