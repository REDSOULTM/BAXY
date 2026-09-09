"""Normal BAXY chat after removing knowledge-to-observation reinterpretation."""
from pathlib import Path
import hashlib, json, os, sys, time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler
BASE=ROOT/'artifacts/comprobaciones/C03';OUT=BASE/'astra-knowledge-owner-live';OUT.mkdir(exist_ok=False)
cases=json.loads((BASE/'astra-real-dialogue-system-layers/PREREG.json').read_text(encoding='utf-8'))['cases']
register=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json';config=json.loads(register.read_text(encoding='utf-8-sig'))
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):del os.environ[key]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
prereg={'cases':cases,'method':'Same six consumed literal requests, normal standalone knowledge chat, source sampler unchanged at temperature 0, all wrapper checks/retries. Change: a knowledge turn no longer becomes observation_ack because of an adverb/noun prefix. No PC effects, no fresh acceptance.', 'registrationSha256':hashlib.sha256(register.read_bytes()).hexdigest(),'sourceSha256':hashlib.sha256((ROOT/'src/baxy_mind/llm.py').read_bytes()).hexdigest()}
(OUT/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'probe.py').write_bytes(Path(__file__).read_bytes())
class Client(LlmRuntime):
    case=None
    def _post(self,payload,*args,**kwargs):
        result=super()._post(payload,*args,**kwargs)
        with (OUT/'posts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'case':self.case,'payload':payload,'response':result},ensure_ascii=False)+'\n')
        return result
client=Client();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid());gpu.start();ram.start();started=time.monotonic()
try:
    client.start_warmup();assert client.wait_warmup(90)
    for case in cases:
        client.case=case['id'];client.begin_request(40);answer=None;error=None
        try:answer=client.chat(case['text'],history=[],conversation_kind='knowledge',response_language='es',temperature=0.0)[0]
        except Exception as exc:error=f'{type(exc).__name__}: {exc}'
        finally:client.end_request()
        row={**case,'answer':answer,'error':error}
        with (OUT/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps(row,ensure_ascii=False),flush=True)
        assert gpu.peak_mib is None or gpu.peak_mib<=4096
finally:
    client.close();gpu.stop();ram.stop();result={'elapsedSeconds':round(time.monotonic()-started,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'registrationUnchanged':hashlib.sha256(register.read_bytes()).hexdigest()==prereg['registrationSha256']}
    (OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
