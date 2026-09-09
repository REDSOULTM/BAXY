"""Offline CPU transcription of bounded captured response windows; no replay."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import sys
import wave

import numpy as np
import psutil
from scipy.signal import resample_poly, correlate
import sherpa_onnx

sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-audio121'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-audio121-private'
assert not any(p.info['name'] in {'Baxy.exe','llama-server.exe'} for p in psutil.process_iter(['name']))
result = json.loads((out / 'AUDIO_RESULT.json').read_text(encoding='utf-8'))
process = json.loads((out / 'PROCESS.json').read_text(encoding='utf-8'))
manifest = json.loads((Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json').read_text(encoding='utf-8'))
stt = Path(manifest['stt_dir'])
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(stt/'encoder.int8.onnx'), decoder=str(stt/'decoder.int8.onnx'),
    joiner=str(stt/'joiner.int8.onnx'), tokens=str(stt/'tokens.txt'), num_threads=6,
    model_type='nemo_transducer', decoding_method='modified_beam_search', max_active_paths=8)
def transcribe(samples):
    stream = recognizer.create_stream()
    stream.accept_waveform(16000, samples.astype(np.float32))
    recognizer.decode_stream(stream)
    return str(stream.result.text or '').strip()
def read(kind):
    with wave.open(str(private/(kind+'.wav')), 'rb') as wav:
        rate = wav.getframerate()
        samples = np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)/32768
        samples = samples.reshape(-1,wav.getnchannels()).mean(axis=1)
        return resample_poly(samples,16000,rate) if rate != 16000 else samples
signals = {kind:read(kind) for kind in ['microphone','loopback']}
origins = {kind:datetime.datetime.fromisoformat(result['streams'][kind]['streamReadyUtc']).timestamp() for kind in signals}
calls=[]
with (out/'shell-trace.jsonl').open(encoding='utf-8') as stream:
    for line in stream:
        row=json.loads(line)
        if row.get('stage')=='mind.request.start' and (row.get('detail') or '').startswith('voice.speak.'):
            calls.append(row)
assert len(calls)==4,len(calls)
rows=[]
for call in calls:
    instant = process['appCreateTime'] + call['ms']/1000
    entry={'turn':call['id'],'estimatedSpeechUtc':datetime.datetime.fromtimestamp(instant,datetime.timezone.utc).isoformat(),
           'timingLimit':'App creation plus relative trace; context windows include1s prior and12s after; not DAC timestamp', 'tracks':{}}
    windows={}
    for kind,samples in signals.items():
        start=max(0,round((instant-origins[kind]-1)*16000))
        end=min(samples.size,start+13*16000)
        window=samples[start:end]
        windows[kind]=window
        peak=float(np.max(np.abs(window))) if window.size else 0
        rms=float(np.sqrt(np.mean(window**2))) if window.size else 0
        raw=transcribe(window) if window.size and peak>1e-6 else ''
        normalized=transcribe(window*(0.8/peak)) if peak>1e-6 else ''
        entry['tracks'][kind]={'seconds':round(window.size/16000,3),'startSample':start,'endSample':end,
            'truncatedByCaptureEnd':end==samples.size,'peak':peak,'rms':rms,
            'rawTranscript':raw,'peakNormalizedTranscript':normalized}
    # Broad spectral/time alignment only; ASR and raw waveforms remain the content evidence.
    mic,loop=windows['microphone'],windows['loopback']
    if mic.size and loop.size and np.linalg.norm(mic)>0 and np.linalg.norm(loop)>0:
        corr=correlate(mic,loop,mode='full',method='fft')
        entry['wholeWindowPeakCorrelation']=float(np.max(np.abs(corr))/(np.linalg.norm(mic)*np.linalg.norm(loop)))
    rows.append(entry)
    print(json.dumps(entry,ensure_ascii=False),flush=True)
report={'sttDirectory':str(stt),'provider':'CPU','method':'Same registered offline transducer; no hotwords/expected-text prompt; raw and peak-normalized reads both reported.',
        'rows':rows}
(private/'transcription121.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'TRANSCRIPTION_INDEX.json').write_text(json.dumps({'privatePath':str(private/'transcription121.json'),
    'sha256':hashlib.sha256((private/'transcription121.json').read_bytes()).hexdigest()},indent=2),encoding='utf-8')
