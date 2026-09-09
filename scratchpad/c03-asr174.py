"""Same local recognizer and prior127 speech window; preserve all readings."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import wave
import numpy as np
import sherpa_onnx

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-webrtc174-private'
index = json.loads((private / 'OUTPUT_INDEX.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256(Path(r['privatePath']).read_bytes()).hexdigest() == r['sha256'] for r in index)
capture = json.loads((base / 'astra-voice127/AUDIO_RESULT.json').read_text(encoding='utf-8'))
origin = dt.datetime.fromisoformat(capture['streams']['microphone']['streamReadyUtc']).timestamp()
events = [json.loads(x) for x in (base / 'astra-voice127/EVENTS.jsonl').read_text(encoding='utf-8').splitlines()]
start = next(e for e in events if e.get('speaking'))
end = next(e for e in events if e.get('speaking') is False and e['monotonic'] > start['monotonic'])
first = round((dt.datetime.fromisoformat(start['utc']).timestamp() - origin)*16000)-8000
last = round((dt.datetime.fromisoformat(end['utc']).timestamp() - origin)*16000)+8000
manifest = json.loads((Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json').read_text(encoding='utf-8'))
stt = Path(manifest['stt_dir'])
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(encoder=str(stt/'encoder.int8.onnx'), decoder=str(stt/'decoder.int8.onnx'), joiner=str(stt/'joiner.int8.onnx'), tokens=str(stt/'tokens.txt'), num_threads=6, model_type='nemo_transducer', decoding_method='modified_beam_search', max_active_paths=8)
rows=[]
for case in ['near_only','physical_echo_plus_synthetic_near']:
    for method in ['raw','speex','webrtc']:
        with wave.open(str(private/f'{case}-{method}.wav'),'rb') as f:
            assert f.getframerate()==16000 and f.getnchannels()==1
            signal=np.frombuffer(f.readframes(f.getnframes()),'<i2').astype(np.float32)/32768
        stream=recognizer.create_stream()
        stream.accept_waveform(16000,signal[max(0,first):min(len(signal),last)])
        recognizer.decode_stream(stream)
        row={'case':case,'method':method,'text':str(stream.result.text or '').strip(),'windowSamples':[first,last]}
        rows.append(row)
        (private/'ASR.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(row,ensure_ascii=False),flush=True)
(base/'astra-webrtc174/ASR_INDEX.json').write_text(json.dumps({'path':str(private/'ASR.json'),'sha256':hashlib.sha256((private/'ASR.json').read_bytes()).hexdigest(),'recognizer':'Registered Parakeet CPU6 beam8, no hints, same131 raw window; synthetic controls, not human acceptance'},indent=2),encoding='utf-8')
