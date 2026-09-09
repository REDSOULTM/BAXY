"""Offline, local inspection of the four outputs captured from desktop166."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import wave

import numpy as np
from scipy.signal import resample_poly
import sherpa_onnx

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
source=base/'astra-audio166'
out=base/'astra-analysis167'
out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-audio166-private'
audio=json.loads((source/'AUDIO_RESULT.json').read_text(encoding='utf-8'))
trace=[json.loads(line) for line in (source/'shell-trace.jsonl').read_text(encoding='utf-8').splitlines()]
compositions=[json.loads(line) for line in (source/'compose-audit.jsonl').read_text(encoding='utf-8').splitlines() if json.loads(line).get('published')]
def event(turn,stage):
    return next(r for r in trace if r['id']==turn and r['stage']==stage)
origins=[]
for row in compositions:
    situation=json.loads(row['situation'])
    if 'observed' in situation:
        utc=dt.datetime.fromisoformat(situation['observed']['utc']).timestamp()
        midpoint=(event(row['trace'],'core.call.start')['ms']+event(row['trace'],'core.call.end')['ms'])/2000
        origins.append(utc-midpoint)
origin=sum(origins)/len(origins)
(out/'PREREG.json').write_text(json.dumps({'method':'Local registered Parakeet CPU6/modified_beam8, raw and peak-normalized mic/loopback. Four output windows: voice.speak request minus0.5s through plus15s. No transcript hints, playback, new capture or source mutation. Trace clock anchored by three Core observations; approximate observer times, not runtime ADC.', 'traceOrigins':origins,'traceOriginUsed':origin,'source':166},indent=2),encoding='utf-8')
manifest=json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json').read_text(encoding='utf-8'))
stt=Path(manifest['stt_dir'])
recognizer=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=str(stt/'encoder.int8.onnx'),decoder=str(stt/'decoder.int8.onnx'),joiner=str(stt/'joiner.int8.onnx'),tokens=str(stt/'tokens.txt'),num_threads=6,model_type='nemo_transducer',decoding_method='modified_beam_search',max_active_paths=8)
def transcribe(samples):
    stream=recognizer.create_stream()
    stream.accept_waveform(16000,samples.astype(np.float32))
    recognizer.decode_stream(stream)
    return str(stream.result.text or '').strip()
signals={}
for kind,metadata in audio['streams'].items():
    p=Path(metadata['privatePath'])
    with p.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()==metadata['sha256']
    with wave.open(str(p),'rb') as wav:
        rate=wav.getframerate()
        samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)/32768
        samples=samples.reshape(-1,wav.getnchannels()).mean(axis=1)
    signals[kind]=resample_poly(samples,16000,rate) if rate!=16000 else samples
rows=[]
for composition in compositions:
    turn=composition['trace']
    speak=next(e for e in trace if e['id']==turn and e['stage']=='mind.request.start' and e['detail'].startswith('voice.speak.'))
    request_time=origin+speak['ms']/1000
    row={'turn':turn,'published':composition['draft'],'language':composition['language'],'requestUtc':dt.datetime.fromtimestamp(request_time,dt.timezone.utc).isoformat(),'tracks':{}}
    if turn!='t0':
        row['submitToVisibleMs']=event(turn,'visible.text')['ms']-event(turn,'submit.received')['ms']
    for kind,signal in signals.items():
        start=dt.datetime.fromisoformat(audio['streams'][kind]['streamReadyUtc']).timestamp()
        first=max(0,round((request_time-.5-start)*16000))
        last=min(len(signal),round((request_time+15-start)*16000))
        segment=signal[first:last]
        peak=float(np.max(np.abs(segment)))
        row['tracks'][kind]={'firstSample':first,'lastSample':last,'peak':peak,'rms':float(np.sqrt(np.mean(segment**2))),'raw':transcribe(segment),'normalized':transcribe(segment*(.8/peak)) if peak else ''}
    rows.append(row)
    print(json.dumps(row,ensure_ascii=False),flush=True)
target=private/'analysis167.json'
with target.open('x',encoding='utf-8') as f:
    json.dump({'rows':rows,'sttDirectory':str(stt)},f,ensure_ascii=False,indent=2)
(out/'RESULT_INDEX.json').write_text(json.dumps({'privatePath':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()},indent=2),encoding='utf-8')
