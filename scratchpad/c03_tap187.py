"""Bounded in-memory observation of exact DTLN inputs/output; diagnostic only."""
from pathlib import Path
import json
import os
import threading
import time
import numpy as np
import baxy_mind.voice as voice_module
from baxy_mind.piper_tts import PiperEngine
from baxy_mind.voice_output import NeuralSpeechOutput
from dtln_stream182 import EchoCanceller

private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar187-private'
active=None
speaking=False
generated=[]

class TracedCanceller(EchoCanceller):
    def __init__(self):
        super().__init__(128)
        global active
        assert active is None
        self.count=0
        self.capacity=3750  # 120seconds, above bounded driver sequence.
        self.near=np.empty((self.capacity,512),np.float32)
        self.reference=np.empty((self.capacity,4512),np.int16)
        self.clean=np.empty((self.capacity,512),np.float32)
        # time, DSPms, copyms, speaking, VADprobability, echoGuard(-1 not called)
        self.rows=np.full((self.capacity,6),np.nan,np.float64)
        active=self

    def process(self,microphone,reference):
        begin=time.perf_counter()
        result=super().process(microphone,reference)
        after=time.perf_counter()
        i=self.count
        if i>=self.capacity:
            raise RuntimeError('diagnostic_capture_capacity_exceeded')
        self.near[i]=microphone
        self.reference[i]=reference
        self.clean[i]=result[0]
        self.rows[i]=[time.monotonic(),(after-begin)*1000,0,float(speaking),np.nan,-1]
        self.count+=1
        self.rows[i,2]=(time.perf_counter()-after)*1000
        return result

voice_module.EchoCanceller=TracedCanceller
voice_module.resolve_echo_canceller_library=lambda:Path('D:/BAXYRuntime/experiments/voice/dtln179')
original_vad=voice_module.SileroVad.process
original_guard=voice_module._looks_like_echo
original_state=NeuralSpeechOutput._set_speaking
original_generate=PiperEngine.generate

def observe_vad(self,frame):
    result=original_vad(self,frame)
    if active is not None and active.count and threading.get_ident()==active._owner:
        active.rows[active.count-1,4]=float(result)
    return result

def observe_guard(microphone,reference):
    result=original_guard(microphone,reference)
    if active is not None and active.count and threading.get_ident()==active._owner:
        active.rows[active.count-1,5]=float(result)
    return result

def observe_state(self,value):
    global speaking
    original_state(self,value)
    speaking=value

def observe_generate(self,text,cancelled=None):
    result=original_generate(self,text,cancelled)
    generated.append((result.copy(),{'text':text,'sampleRate':self.sample_rate,
                                    'model':str(self.model_path),'time':time.monotonic()}))
    return result

voice_module.SileroVad.process=observe_vad
voice_module._looks_like_echo=observe_guard
NeuralSpeechOutput._set_speaking=observe_state
PiperEngine.generate=observe_generate

def save():
    if active is not None:
        n=active.count
        np.savez(private/'tap187.npz',microphone=active.near[:n],reference=active.reference[:n],clean=active.clean[:n],observations=active.rows[:n])
        (private/'tap187.json').write_text(json.dumps({'frames':n,'seconds':n*.032,'aecSha256':active.sha256,
            'columns':['monotonic','dspMs','copyMs','speaking','vadProbability','echoGuard'],
            'limitation':'Per-frame observation changes scheduling. Exact signals retained for offline parity/analysis; cannot infer observer caused any difference from183/185.'},indent=2),encoding='utf-8')
    np.savez(private/'generated187.npz',**{f'audio{i}':value[0] for i,value in enumerate(generated)})
    (private/'generated187.json').write_text(json.dumps([value[1] for value in generated],ensure_ascii=False,indent=2),encoding='utf-8')
