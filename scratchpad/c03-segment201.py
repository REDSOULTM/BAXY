"""Use product capture segmentation on unchanged198 PCM, without device effects."""
from pathlib import Path
import hashlib
import json
import os
import queue
import sys
import threading
import numpy as np

root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
import baxy_mind.voice as voice
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-segment201-retry';out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-segment201-retry-private';private.mkdir(exist_ok=False)
inputs=json.loads((base/'astra-human-aec198/RESULTS.json').read_text(encoding='utf-8'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save(out/'PREREG.json',{'method':'All24 fixed198 signals through actual VoiceEngine._capture_loop and actual SileroVad. Explicit direct mode, already-processed PCM source, speakingFalse; finite stream replaces only device reads. Collect actual _DecodeRequest PCM via sink. No duplicate segmentation implementation, AEC reprocessing, changed silence/pre-roll/threshold, recognition hint or hardware effect.',
 'isolation':'TTS factory and ducker replaced with inert diagnostics; hardware health probe returns empty metadata. No start(), decoder/model/UI or microphone/loopback opened. This isolates endpointing and VAD resets, not acoustic wake or barge-in. Initial201 harness failed before frames because inert output lacked available; retained separately.',
 'constants':{'preRoll':voice.PRE_ROLL_S,'trailingSilence':voice.TRAILING_SILENCE_S,'minUtterance':voice.MIN_UTTERANCE_S,'maxUtterance':voice.MAX_UTTERANCE_S,'speechThreshold':voice.SPEECH_THRESHOLD},
 'sourceSha256':hashlib.sha256((root/'src/baxy_mind/voice.py').read_bytes()).hexdigest(),'inputs':inputs})
class InertOutput:
    speaking=False
    available=False
class InertDucker:
    def duck(self):return True
    def restore(self):return True
class FiniteStream:
    device=None
    def __init__(self,audio,event):self.audio,self.event,self.reads=audio,event,0
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def read(self,samples):
        assert samples==512
        if self.reads>=len(self.audio):
            self.event.set();return np.zeros((512,1),np.float32),False
        frame=self.audio[self.reads];self.reads+=1
        return frame.reshape(-1,1),False
voice.create_speech_output=lambda callback:InertOutput()
vad=voice.SileroVad();results=[]
for case,row in enumerate(inputs):
    path=Path(row['privateOutput']);assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    with np.load(path) as values:audio=values['clean'].copy()
    event=threading.Event();stream=FiniteStream(audio,event);requests=[];events=[]
    class Sink:
        def put_nowait(self,request):requests.append((stream.reads,request))
    voice._PcmCaptureStream=lambda inbox,stop:stream
    engine=voice.VoiceEngine(lambda text:None,on_event=events.append)
    engine.probe=lambda:{}
    engine._ducker=InertDucker();engine._mode='direct';engine._vad=vad
    engine._pcm_inbox=queue.Queue();vad.reset()
    engine._capture_loop(stop_event=event,decode_queue=Sink(),capture_ready_event=threading.Event())
    assert not any(e.get('event')=='error' for e in events),events
    assert stream.reads==len(audio)
    segments=[];signals={}
    for i,(end_frame,request) in enumerate(requests):
        samples=request.audio
        assert len(samples)%512==0
        first=end_frame*512-len(samples);last=end_frame*512
        assert np.array_equal(samples,audio.ravel()[first:last]),'Segment differs from contiguous original PCM'
        signals[f'segment{i}']=samples
        segments.append({'index':i,'firstSample':first,'lastSample':last,'seconds':len(samples)/16000,'origin':request.origin})
    target=private/f'case{case}.npz';np.savez(target,**signals)
    record={k:row[k] for k in ['human','config','id','condition','engine']}
    record.update(case=case,segments=segments,privateOutput=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    results.append(record);save(out/'RESULTS.json',results)
    print(json.dumps({'case':case,'segments':len(segments),'ranges':[(r['firstSample'],r['lastSample']) for r in segments]}),flush=True)
save(out/'COMPLETE.json',{'cases':len(results),'segments':sum(len(r['segments']) for r in results),'sourceChanged':False})
