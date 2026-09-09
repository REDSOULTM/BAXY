"""Inherited factorial probe: same model, published context, no effects or promotion."""
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
out = base / 'astra-knowledge-context47'
out.mkdir(exist_ok=False)
sources = {name: json.loads((base / path / 'paired.json').read_text(encoding='utf-8'))
           for name, path in [('old', 'astra-routes-regression46'), ('new', 'astra-routes-volume46')]}
cases = []
for index, language in [(7, 'mixed'), (9, 'mixed'), (12, 'en'), (13, 'es')]:
    contexts = {}
    for name, rows in sources.items():
        contexts[name] = [message for row in rows[max(0, index - 5):index] for message in (
            {'role': 'user', 'content': row['request']}, {'role': 'assistant', 'content': row['final']})]
    cases.append({'text': sources['new'][index]['request'], 'history': contexts, 'language': language})
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
stages = ['product_old', 'product_new', 'bare_old', 'bare_new']
prereg = {'cases': cases, 'stages': stages,
    'method': 'Four consumed technical knowledge controls, each with last five public pairs reconstructed from baseline46 and source46 replay. Cross context old/new with current system policies present/absent. Reuses knowledge-history-factorial instrument; capture first raw completion before validation/retry. Temperature0 seed0 max_tokens256 and registered native template. Bare removes only system messages from the captured chat payload; same token budget/template, not unbounded plain inference. No live effects, no acceptance reserve, no source/model promotion. Public history is reconstruction, not original wire capture. New gravity example is first visible in raw pre_veto, before any answer validation.',
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
        print(json.dumps({'stage': self.stage, 'text': self.case['text'], 'answer': choice['message'].get('content'),
                          'finish_reason': choice.get('finish_reason')}, ensure_ascii=False), flush=True)
        raise Captured

client = Client()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
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
                client.chat(case['text'], history=case['history'][stage.split('_')[1]],
                            conversation_kind='knowledge', response_language=case['language'], temperature=0.0)
            except Captured:
                pass
            finally:
                client.end_request()
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
              'ramPeakMiB': ram.peak_mib, 'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
