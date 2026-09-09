"""Reproduce App158 voice startup environment with timed native thread traces."""
from pathlib import Path
import faulthandler
import hashlib
import json
import os
import sys
import time

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-start159'
out.mkdir(exist_ok=False)
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-start159-private'
private.mkdir(exist_ok=False)
processes=json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-audio158-private/process158.json').read_text(encoding='utf-8'))
observed=next(p for p in processes if p['name']=='python.exe' and p['cmdline'][-1]=='baxy_mind')
for name,value in observed['selectedEnvironment'].items():
    os.environ[name]=value
os.environ['HF_HUB_OFFLINE']='1'
events=[]
def event(payload):
    events.append({k:v for k,v in payload.items() if k in {'event','code','mode','listening','speaking','aec','lastError','wakeWordError'}})

(out/'PREREG.json').write_text(json.dumps({'method':'Exact observed App158 selected voice env including preexisting uncalibrated wake seam, diagnostic only. VoiceEngine.start(wake) without preloading. No playback/volume mutation/App/LLM/Core or transcript routing. faulthandler dumps after12s to private log; inspect blocking stack before changes.',
    'acceptance':False,'sourceFiles':json.loads((base/'astra-voice148/PREREG.json').read_text(encoding='utf-8'))['sources']},indent=2),encoding='utf-8')
from baxy_mind.voice import VoiceEngine
engine=VoiceEngine(lambda _:None,event)
start=time.monotonic()
with (private/'stacks159.log').open('w',encoding='utf-8') as log:
    faulthandler.dump_traceback_later(12,repeat=True,file=log)
    try:
        ready=engine.start('wake')
        result={'ready':ready,'elapsedSeconds':time.monotonic()-start,'status':engine.status(),'events':events}
        print(json.dumps(result),flush=True)
        (out/'RESULTS.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    finally:
        engine.shutdown()
        faulthandler.cancel_dump_traceback_later()
(out/'TRACE_INDEX.json').write_text(json.dumps({'privatePath':str(private/'stacks159.log'),'sha256':hashlib.sha256((private/'stacks159.log').read_bytes()).hexdigest()},indent=2),encoding='utf-8')
print('Startup159 and shutdown finished.',flush=True)
