"""Measure existing semantic/contract validators without changing or executing BAXY."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root/'src'), str(root)]
from baxy_mind.llm import LlmRuntime, _prepare_turn_candidates
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

out = root/'artifacts/comprobaciones/C03/astra-negative-contract'
out.mkdir(exist_ok=False)
prior = json.loads((root/'artifacts/comprobaciones/C03/astra-real-context-ablation/PREREG.json').read_text(encoding='utf-8'))
candidate = next(c for case in prior['cases'] for c in case['candidates'] if c['name']=='system.time')
_, _, contracts = _prepare_turn_candidates([candidate])
texts = [
    ('no me molesta, dime la hora', True),
    ("I don't mind, tell me the time", True),
    ('no abras Steam, dime la hora', True),
    ('no me digas la hora', False),
    ("don't tell me the time", False),
    ('no uses herramientas, dime la hora', False),
    ('traduce: no me molesta, dime la hora', False),
    ('no me digas la hora, dime la hora', False),
    ('dime la hora y baja el volumen', False),
    ('ayer me dijiste la hora', False),
    ('El aire es h20?', False),
]
register = Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(register.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'): del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
prereg = {'cases': [{'text':t, 'clock_covers_entire_authorized_request':v, 'kind':'consumed_or_synthetic_regression_control'} for t,v in texts],
          'contract': contracts['system.time'], 'stages':['existing_candidate_free_shape','existing_full_request_compatibility'],
          'method':'Existing validators, no changed prompt, no source change, no tool execution. Full-request compatibility, not the positive-clause verifier whose precondition is not met here. No history. Compare semantic type/count and whether one read covers the full request including restrictions.',
          'sourceSha256':hashlib.sha256((root/'src/baxy_mind/llm.py').read_bytes()).hexdigest(),
          'registrationSha256':hashlib.sha256(register.read_bytes()).hexdigest()}
(out/'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
class Client(LlmRuntime):
    case=''
    stage=''
    def _post(self, payload, *args, **kwargs):
        response = super()._post(payload, *args, **kwargs)
        with (out/'posts.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps({'case':self.case,'stage':self.stage,'payload':payload,'response':response},ensure_ascii=False)+'\n')
        return response
client=Client()
gpu=ProcessTreeGpuSampler(os.getpid());ram=RamSampler(os.getpid())
gpu.start();ram.start();started=time.monotonic()
try:
    client.start_warmup();assert client.wait_warmup(90)
    for text, expected in texts:
        client.case=text;client.begin_request(35)
        try:
            client.stage='shape';shape=client._verify_semantic_effect_shape(text)
            client.stage='full_request_compatibility';compatible=client._operation_is_fully_compatible(text, 'system.time', contracts['system.time'])
            row={'text':text,'shape':shape,'compatible':compatible,'expected':expected}
            with (out/'replies.jsonl').open('a', encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps(row,ensure_ascii=False),flush=True)
        finally:client.end_request()
        assert gpu.peak_mib is None or gpu.peak_mib<=4096
finally:
    client.close();gpu.stop();ram.stop()
    result={'elapsedSeconds':round(time.monotonic()-started,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'registrationUnchanged':hashlib.sha256(register.read_bytes()).hexdigest()==prereg['registrationSha256']}
    (out/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
