"""Native current composer for structured voice feedback; no playback/effects."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time
import psutil

root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'src'),str(root)]
sys.stdout.reconfigure(encoding='utf-8')
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

base=root/'artifacts/comprobaciones/C03';out=base/'astra-feedback193';out.mkdir(exist_ok=False)
assert not any(p.info['name'] in {'Baxy.exe','llama-server.exe','piper.exe'} for p in psutil.process_iter(['name']))
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
registry=json.loads(manifest.read_text(encoding='utf-8'))
processes=json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-audio158-private/process158.json').read_text(encoding='utf-8'))
observed=next(p for p in processes if p['name']=='python.exe' and p['cmdline'][-1]=='baxy_mind')
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):del os.environ[key]
os.environ.update({k:v for k,v in observed['selectedEnvironment'].items() if k.startswith('BAXY_MIND_')})
os.environ.update(BAXY_MIND_LLM_GGUF='D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf',BAXY_MIND_LLAMA_SERVER='D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe',BAXY_MIND_NGL='99')
cases=[('wake','conversation','voice_wake_listening','success'),('uncertain','clarification','voice_transcript_uncertain','pending')]
prereg={'method':'Current192 LlmRuntime.compose_user_message on exactly the two new structured causes; empty user text as App enqueues. Normal composition guards/recovery stay enabled; capture actual HTTP requests/responses. Native composer only: not proof of App queue publication, UI, voice, reserve or full criterion.',
 'cases':cases,'sourceFiles':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['src/baxy_mind/llm.py','src/baxy_mind/voice.py','src/Baxy.App/MainWindowViewModel.cs','src/Baxy.App/TurnVisibleFacts.cs']},
 'runtimeManifestSha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'modelOverride':os.environ['BAXY_MIND_LLM_GGUF']}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
active_case=None
class Observed(LlmRuntime):
    def _post(self,payload,*args,**kwargs):
        result=super()._post(payload,*args,**kwargs)
        with (out/'posts.jsonl').open('a',encoding='utf-8') as handle:
            handle.write(json.dumps({'case':active_case,'payload':payload,'response':result},ensure_ascii=False)+'\n')
        return result
client=Observed();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid())
gpu.start();ram.start();rows=[];started=time.monotonic()
try:
    client.start_warmup();assert client.wait_warmup(90)
    for active_case,intent,cause,polarity in cases:
        facts={'situation':json.dumps({'kind':intent,'polarity':polarity,'cause':cause}),'voiceFeedback':True,'traceId':'t0'}
        begin=time.monotonic()
        try:
            result=client.compose_user_message('',intent,facts,timeout=30)
            row={'case':active_case,'intent':intent,'facts':facts,'text':result,'seconds':time.monotonic()-begin}
        except Exception as error:
            row={'case':active_case,'intent':intent,'facts':facts,'error':repr(error),'seconds':time.monotonic()-begin}
        rows.append(row);(out/'RESULTS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(row,ensure_ascii=False),flush=True)
finally:
    client.close();gpu.stop();ram.stop()
    result={'seconds':time.monotonic()-started,'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'runtimeManifestUnchanged':hashlib.sha256(manifest.read_bytes()).hexdigest()==prereg['runtimeManifestSha256']}
    (out/'CLEANUP.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)
