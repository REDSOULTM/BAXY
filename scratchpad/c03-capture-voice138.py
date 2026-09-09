"""Bounded local microphone/loopback observation; restore the exact endpoint."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import sys
import threading
import time
import wave

import numpy as np
import sounddevice as sd
import pyaudiowpatch as pa

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind.voice_aec import AudioDucker, _com_apartment

assert '--physical-output' in sys.argv
out = root / 'artifacts/comprobaciones/C03/astra-voice138'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-voice138-private'
private.mkdir(exist_ok=False)
stop = threading.Event()
started = time.monotonic()
records = {}

def capture(name):
    record = {'kind':name, 'startedUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'frames':0, 'overflows':0, 'peak':0.0, 'sumSquares':0.0}
    records[name] = record
    try:
        path = private / (name + '.wav')
        if name == 'microphone':
            device = sd.query_devices(kind='input')
            rate, channels = 16000, 1
            record.update(device=device, rate=rate, channels=channels)
            with wave.open(str(path), 'wb') as wav:
                wav.setnchannels(channels); wav.setsampwidth(2); wav.setframerate(rate)
                with sd.InputStream(device=device['index'], samplerate=rate, channels=channels,
                                    dtype='int16', blocksize=1024) as stream:
                    record['streamReadyUtc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    while not stop.is_set():
                        if stream.read_available < 1024:
                            stop.wait(0.01)
                            continue
                        data, overflow = stream.read(1024)
                        record['overflows'] += int(overflow)
                        wav.writeframes(data.tobytes())
                        count(data, record)
        else:
            with pa.PyAudio() as backend:
                device = backend.get_default_wasapi_loopback()
                rate, channels = int(device['defaultSampleRate']), int(device['maxInputChannels'])
                record.update(device=device, rate=rate, channels=channels)
                with wave.open(str(path), 'wb') as wav:
                    wav.setnchannels(channels); wav.setsampwidth(2); wav.setframerate(rate)
                    stream = backend.open(format=pa.paInt16, channels=channels, rate=rate,
                        input=True, input_device_index=device['index'], frames_per_buffer=1024)
                    try:
                        record['streamReadyUtc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                        while not stop.is_set():
                            if stream.get_read_available() < 1024:
                                stop.wait(0.01)
                                continue
                            data = stream.read(1024, exception_on_overflow=True)
                            wav.writeframes(data)
                            count(np.frombuffer(data, dtype=np.int16).reshape(-1, channels), record)
                    finally:
                        stream.stop_stream(); stream.close()
        record['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        record['privatePath'] = str(path)
    except Exception as error:
        record['error'] = f'{type(error).__name__}: {error}'
        stop.set()
    finally:
        record['finishedUtc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()

def count(data, record):
    samples = data.astype(np.float64) / 32768
    record['frames'] += int(data.shape[0])
    record['peak'] = max(record['peak'], float(np.max(np.abs(samples))))
    record['sumSquares'] += float(np.sum(samples ** 2))

with _com_apartment():
    endpoint = AudioDucker._endpoint()
    before = {'levelScalar':float(endpoint.GetMasterVolumeLevelScalar()), 'muted':bool(endpoint.GetMute())}
    setup = {'monitor':os.getpid(), 'before':before, 'testLevelScalar':0.30,
             'privateDirectory':str(private), 'maximumSeconds':300,
             'startedUtc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (out / 'AUDIO_SETUP.json').write_text(json.dumps(setup, indent=2), encoding='utf-8')
    threads = [threading.Thread(target=capture, args=(name,), daemon=False) for name in ['microphone','loopback']]
    reason = 'capture_failed'
    try:
        endpoint.SetMasterVolumeLevelScalar(0.30, None)
        endpoint.SetMute(0, None)
        for thread in threads:
            thread.start()
        while not stop.is_set():
            if all(records.get(name, {}).get('streamReadyUtc') for name in ['microphone','loopback']):
                ready_path = out / 'AUDIO_READY.json'
                if not ready_path.exists():
                    ready_path.write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'streams':list(records)}, indent=2), encoding='utf-8')
                    print('Microphone and loopback capture ready; endpoint at0.30/unmuted; restore in finally.', flush=True)
            if (out / 'STOP_AUDIO').exists():
                reason = 'operator_finished'; break
            if time.monotonic() - started >= 300:
                reason = 'deadline_300s'; break
            time.sleep(0.1)
    finally:
        stop.set()
        for thread in threads:
            if thread.ident is not None:
                thread.join(timeout=10)
        endpoint.SetMasterVolumeLevelScalar(before['levelScalar'], None)
        endpoint.SetMute(int(before['muted']), None)
        after = {'levelScalar':float(endpoint.GetMasterVolumeLevelScalar()), 'muted':bool(endpoint.GetMute())}
        result = {'reason':reason, 'seconds':round(time.monotonic()-started, 2), 'before':before,
                  'after':after, 'restoredExactly':before == after, 'streams':records,
                  'threadsStopped':all(not thread.is_alive() for thread in threads)}
        (out / 'AUDIO_RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False), flush=True)
