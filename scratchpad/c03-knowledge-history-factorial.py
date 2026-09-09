"""Inherited local probe; isolate policy and actual published history, not new prompts."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / 'src'), str(root)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-knowledge-history-factorial'
out.mkdir(exist_ok=False)
rows = json.loads((base / 'astra-native-budget13/paired.json').read_text(encoding='utf-8'))
cases = []
for index in (2, 3, 4):
    history = []
    for row in rows[:index]:
        history.extend([{'role': 'user', 'content': row['request']},
                        {'role': 'assistant', 'content': row['final']}])
    cases.append({'text': rows[index]['request'], 'history': history,
                  'language': 'en' if index == 4 else 'es'})
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'],
                  BAXY_MIND_NGL=str(config['ngl']))
stages = ['product_history', 'product_no_history', 'bare_history', 'bare_no_history']
prereg = {'cases': cases, 'stages': stages,
          'method': 'Twelve calls on three consumed controls. Two factors: current system policies present/absent, captured preceding published conversation present/absent. Literal input and history, same registered model/backend, temperature0 seed0 max_tokens256 and template. Capture the first model completion directly; do not let a retry or validation hide it. No execution, no product promotion, no reserved acceptance. Reuses documented-profile33 and dialogue-system-layers instruments; new evidence isolates actual preceding history after native integration.',
          'sourceSha256': hashlib.sha256((root / 'src/baxy_mind/llm.py').read_bytes()).hexdigest(),
          'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')

class Captured(Exception):
    pass

class Client(LlmRuntime):
    stage = ''
    case = None

    def _post(self, payload, *args, **kwargs):
        payload = copy.deepcopy(payload)
        if self.stage.startswith('bare_'):
            payload['messages'] = [m for m in payload['messages'] if m['role'] != 'system']
        response = super()._post(payload, *args, **kwargs)
        record = {'stage': self.stage, 'text': self.case['text'], 'payload': payload, 'response': response}
        with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
        choice = response['choices'][0]
        print(json.dumps({'stage': self.stage, 'text': self.case['text'],
                          'answer': choice['message'].get('content'),
                          'finish_reason': choice.get('finish_reason')}, ensure_ascii=False), flush=True)
        raise Captured

client = Client()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start()
ram.start()
started = time.monotonic()
try:
    client.start_warmup()
    assert client.wait_warmup(90)
    for stage in stages:
        client.stage = stage
        for case in cases:
            client.case = case
            client.begin_request(40)
            try:
                client.chat(case['text'], history=case['history'] if stage.endswith('_history') and not stage.endswith('_no_history') else [],
                            conversation_kind='knowledge', response_language=case['language'], temperature=0.0)
            except Captured:
                pass
            finally:
                client.end_request()
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close()
    gpu.stop()
    ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
              'ramPeakMiB': ram.peak_mib,
              'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
