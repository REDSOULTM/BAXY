"""Revisit the inherited native AUTO selector on the failing scope controls."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root/'src'),str(root)]
from baxy_mind.llm import LlmRuntime,_prepare_turn_candidates
from scripts.measure_mind_budget import ProcessTreeGpuSampler,RamSampler
base=root/'artifacts/comprobaciones/C03';out=base/'astra-native-scope';out.mkdir(exist_ok=False)
prior=json.loads((base/'astra-real-context-ablation/PREREG.json').read_text(encoding='utf-8'))
wanted={'system.time','audio.volume','audio.volume.adjust','audio.status','audio.mute','app.open'}
found={c['name']:c for case in prior['cases'] for c in case['candidates'] if c['name'] in wanted}
names,_,contracts=_prepare_turn_candidates(list(found.values()))
cases=json.loads((base/'astra-negative-contract/PREREG.json').read_text(encoding='utf-8'))['cases']
reg=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json';config=json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'],BAXY_MIND_LLAMA_SERVER=config['llama_server'],BAXY_MIND_NGL=str(config['ngl']))
prereg={'cases':cases,'candidates':list(found.values()),'method':'Eleven consumed/synthetic controls, existing native selector with tool_choice AUTO inherited from tranche35. Restricted diagnostic candidate universe, not real product retrieval. No parser/guard bypass in product, no execution or promotion. Earlier AUTO failures (contextual date and standalone audio prohibition) predate their upstream fixes; scope controls have not been measured with AUTO. Capture raw prose/tool calls as well as adapter result. Not the historically rejected forced REQUIRED selection.', 'registrationSha256':hashlib.sha256(reg.read_bytes()).hexdigest()}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
class Client(LlmRuntime):
    case=''
    def _post(self,payload,*args,**kwargs):
        payload={**payload,'tool_choice':'auto'}
        response=super()._post(payload,*args,**kwargs)
        with (out/'posts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'case':self.case,'payload':payload,'response':response},ensure_ascii=False)+'\n')
        return response
client=Client();gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid());gpu.start();ram.start();started=time.monotonic()
try:
    client.start_warmup();assert client.wait_warmup(90)
    for case in cases:
        client.case=case['text'];client.begin_request(35)
        try:answer=client._post_native_tool_selection(case['text'],names,contracts,[])
        finally:client.end_request()
        row={'text':case['text'],'answer':answer}
        with (out/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps(row,ensure_ascii=False),flush=True)
        assert gpu.peak_mib is None or gpu.peak_mib<=4096
finally:
    client.close();gpu.stop();ram.stop()
    result={'elapsedSeconds':round(time.monotonic()-started,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'registrationUnchanged':hashlib.sha256(reg.read_bytes()).hexdigest()==prereg['registrationSha256']}
    (out/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
