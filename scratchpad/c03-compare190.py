"""Compare frozen generated187 PCM to physical loopback and blinded ASR."""
from pathlib import Path
import hashlib
import json
import os
import wave
import numpy as np
from scipy.signal import correlate, resample_poly
import sherpa_onnx

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar187-private'
index=json.loads((base/'astra-sidecar187/INDEX.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256(Path(r['privatePath']).read_bytes()).hexdigest()==r['sha256'] for r in index)
capture=json.loads((base/'astra-sidecar187/AUDIO_RESULT.json').read_text(encoding='utf-8'))
loop_path=Path(capture['streams']['loopback']['privatePath'])
assert hashlib.sha256(loop_path.read_bytes()).hexdigest()==capture['streams']['loopback']['sha256']
with wave.open(str(loop_path),'rb') as wav:
    assert wav.getframerate()==48000 and wav.getnchannels()==2
    signal=np.frombuffer(wav.readframes(wav.getnframes()),'<i2').astype(np.float32).reshape(-1,2).mean(axis=1)/32768
loop=resample_poly(signal,1,3).astype(np.float32)
generated=np.load(private/'generated187.npz')
metadata=json.loads((private/'generated187.json').read_text(encoding='utf-8'))
windows=[r for r in json.loads((base/'astra-observe189/PREREG.json').read_text(encoding='utf-8'))['windows'] if r['channel']=='loopback']
out=base/'astra-compare190';out.mkdir(exist_ok=False)
(out/'PREREG.json').write_text(json.dumps({'method':'Use exact generated187 PCM, correlate complete resampled waveform with unchanged189 loopback window. Compare full waveform and200ms active blocks, then Parakeet CPU6beam8 without hints on original and fitted loopback-gain source with1s zero padding. No synthesis/playback/source edit.',
 'reason':'189 English not recovered beyond It is ten despite zero cancellation events. Separate source pronunciation, playback truncation and ASR sensitivity using frozen exact waveform.',
 'inputs':index,'loopbackSha256':capture['streams']['loopback']['sha256'],'windows':windows,
 'limitation':'Digital loopback proves device signal only, not human audibility. Correlation/gain do not prove semantic fidelity or perfect resampling; ASR remains an observer.'},indent=2),encoding='utf-8')
manifest=json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json').read_text(encoding='utf-8'))
stt=Path(manifest['stt_dir'])
recognizer=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=str(stt/'encoder.int8.onnx'),decoder=str(stt/'decoder.int8.onnx'),joiner=str(stt/'joiner.int8.onnx'),tokens=str(stt/'tokens.txt'),num_threads=6,model_type='nemo_transducer',decoding_method='modified_beam_search',max_active_paths=8)
rows=[]
for i,(meta,window) in enumerate(zip(metadata,windows)):
    assert meta['sampleRate']==22050
    original=resample_poly(generated[f'audio{i}'],320,441).astype(np.float32)
    first,last=window['samples'];captured=loop[first:last]
    assert len(captured)>=len(original)
    products=correlate(captured.astype(np.float64),original.astype(np.float64),mode='valid',method='fft')
    position=int(np.argmax(products))
    matched=captured[position:position+len(original)].astype(np.float64)
    target=original.astype(np.float64)
    gain=float(np.dot(matched,target)/np.dot(target,target))
    corr=float(np.dot(matched,target)/(np.linalg.norm(matched)*np.linalg.norm(target)))
    active=np.flatnonzero(np.abs(target)>.005)
    blocks=[]
    for start in range(0,len(target),3200):
        x=target[start:start+3200];y=matched[start:start+3200]
        if np.sqrt(np.mean(x*x))<.005:continue
        blocks.append({'startSeconds':start/16000,'gain':float(np.dot(x,y)/np.dot(x,x)),
                       'correlation':float(np.dot(x,y)/(np.linalg.norm(x)*np.linalg.norm(y))) if np.linalg.norm(y) else 0.0})
    transcripts=[]
    for label,scale in [('source_original',1.0),('source_fitted_loopback_gain',gain)]:
        audio=np.r_[np.zeros(16000,np.float32),original*scale,np.zeros(16000,np.float32)]
        stream=recognizer.create_stream();stream.accept_waveform(16000,audio)
        recognizer.decode_stream(stream)
        transcripts.append({'condition':label,'scale':scale,'text':str(stream.result.text or '').strip()})
    row={'output':i+1,'generatedSeconds':len(original)/16000,'windowSamples':[first,last],
         'matchedOffsetSamples':position,'completeWaveformFitsWindow':position+len(original)<=len(captured),
         'activeSourceRangeSeconds':[int(active[0])/16000,int(active[-1])/16000] if len(active) else None,
         'wholeWaveCorrelation':corr,'fittedGain':gain,'activeBlocks200ms':blocks,'sourceTranscripts':transcripts}
    rows.append(row);(out/'RESULTS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in row.items() if k!='activeBlocks200ms'},ensure_ascii=False),flush=True)
(out/'COMPLETE.json').write_text(json.dumps({'outputs':4,'readings':8,'exit':'complete'}),encoding='utf-8')
