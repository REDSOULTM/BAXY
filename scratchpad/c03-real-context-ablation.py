"""Local diagnostic of real input interpretation, reconstructed transcript context."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from baxy_mind.llm import LlmRuntime, _build_turn_policy_payload, _prepare_turn_candidates
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler, current_core_catalog_snapshot

OUT = ROOT / 'artifacts/comprobaciones/C03/astra-real-context-ablation'
OUT.mkdir(exist_ok=False)
BASE = ROOT / 'artifacts/comprobaciones/C03/astra-real-users-development20'
paired = json.loads((BASE / 'paired.json').read_text(encoding='utf-8-sig'))
audit = [json.loads(line) for line in (BASE / 'turn-audit.jsonl').read_text(encoding='utf-8-sig').splitlines()]
catalog, _, _ = current_core_catalog_snapshot(ROOT / 'src/Baxy.Core/bin/Release/net10.0-windows10.0.19041.0/win-x64/publish/baxy-core.exe')
by_name = {row['name']: row for row in catalog}
# IDs are from the immutable baseline audit, not the newer replay.
selected = {3: '12', 8: '28', 17: '70', 18: '74', 20: '78'}
cases = []
history = []
for number, row in enumerate(paired, 1):
    if number in selected:
        observed = next(r for r in audit if r.get('request_id') == selected[number] and r.get('phase') == 'raw_attempt')
        candidates = [{'name': name, 'description': by_name[name]['description'], 'arguments_schema': by_name[name]['argumentsSchema']} for name in observed['candidate_operations']]
        cases.append({'id': row['turnId'], 'text': row['request'], 'history': copy.deepcopy(history[-6:]), 'candidates': candidates})
    history += [{'role': 'user', 'content': row['request']}, {'role': 'assistant', 'content': row['final']}]
register = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(register.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
prereg = {'cases': cases, 'stages': ['primary_without_history', 'primary_with_history', 'guarded_with_history'],
          'method': 'Five previously consumed literal real-log inputs. Reconstruct last six public transcript messages; not an exact capture of original wire history/pending state. Same authenticated candidate names as original raw_attempt; descriptions/schemas from current Core. Direct primary JSON interpretation with/without history, then existing decision wrapper with history. Registered model and source default KV/sampling. No PC actions, no fabricated responses, no new acceptance.',
          'sourceSha256': hashlib.sha256((ROOT / 'src/baxy_mind/llm.py').read_bytes()).hexdigest(),
          'registrationSha256': hashlib.sha256(register.read_bytes()).hexdigest()}
(OUT / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')

class Client(LlmRuntime):
    stage = None
    case_id = None
    def _post(self, payload, *args, **kwargs):
        response = super()._post(payload, *args, **kwargs)
        with (OUT / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'stage': self.stage, 'case': self.case_id, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
        return response

client = Client()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start(); started = time.monotonic()
try:
    client.start_warmup()
    assert client.wait_warmup(90)
    for stage in prereg['stages']:
        client.stage = stage
        for case in cases:
            client.case_id = case['id']; client.begin_request(40)
            answer = None; error = None
            try:
                if stage == 'guarded_with_history':
                    answer = client.decide_turn(case['text'], case['candidates'], history=case['history'])
                else:
                    names, descriptions, _ = _prepare_turn_candidates(case['candidates'])
                    payload = _build_turn_policy_payload(case['text'], names, descriptions, case['history'] if stage.endswith('with_history') else [])
                    answer = client._post(payload)['choices'][0]['message']
            except Exception as exc:
                error = f'{type(exc).__name__}: {exc}'
            finally:
                client.end_request()
            result = {'stage': stage, 'id': case['id'], 'text': case['text'], 'answer': answer, 'error': error}
            with (OUT / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(result, ensure_ascii=False) + '\n')
            print(json.dumps(result, ensure_ascii=False), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib, 'ramPeakMiB': ram.peak_mib,
              'registrationUnchanged': hashlib.sha256(register.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (OUT / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
