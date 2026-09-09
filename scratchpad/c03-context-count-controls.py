"""Compare existing contracts and contextual representations; no PC operations."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from baxy_mind.llm import LlmRuntime, EFFECT_COUNT_VERIFIER_PROMPT, _build_turn_policy_payload, _prepare_turn_candidates, _native_selection_description
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

OUT = ROOT / 'artifacts/comprobaciones/C03/astra-context-count-controls'
OUT.mkdir(exist_ok=False)
prior = ROOT / 'artifacts/comprobaciones/C03/astra-real-context-ablation/PREREG.json'
inherited = json.loads(prior.read_text(encoding='utf-8'))['cases']
context = next(c for c in inherited if c['id']=='t17')
controls = [
('Ponlo a 100 ahora', 'one'),
('Set it to 45', 'one'),
('Pon el volumen al 40 y silencia el microfono', 'multiple'),
('Set the volume to 45 and tell me the time', 'multiple'),
('Sube el volumen en 10 puntos', 'one'),
('Pon el volumen al 40 sin silenciarlo', 'one'),
('No cambies el volumen', 'zero'),
('Dime la hora y el nivel de volumen', 'multiple'),
]
cases = [{'id': f'control-{i}', 'text': text, 'expected_count': expected, 'provenance': 'synthetic regression control; not real user or acceptance', 'history': context['history'], 'candidates': context['candidates']} for i,(text,expected) in enumerate(controls,1)]

register = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(register.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
prereg = {'cases': cases, 'source': str(prior), 'stages': ['count_current', 'count_scoped_context'],
    'method': 'Five consumed log requests and their previously reconstructed history. Existing primary JSON versus inherited native sibling descriptions versus native template with AUTO, not required. Independent count with no history versus role history versus scoped JSON. All are interpretation diagnostics with registered assets, no actions or product promotion. Native auto is not the previously rejected forced-tool policy.',
    'llmSha256': hashlib.sha256((ROOT/'src/baxy_mind/llm.py').read_bytes()).hexdigest(), 'registrationSha256': hashlib.sha256(register.read_bytes()).hexdigest()}
(OUT/'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')

class Client(LlmRuntime):
    stage = ''
    case_id = ''
    def _post(self, payload, *args, **kwargs):
        payload = copy.deepcopy(payload)
        if self.stage == 'native_auto':
            payload['tool_choice'] = 'auto'
        response = super()._post(payload, *args, **kwargs)
        with (OUT/'posts.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps({'stage': self.stage, 'case': self.case_id, 'payload': payload, 'response': response}, ensure_ascii=False)+'\n')
        return response

client = Client(); gpu = ProcessTreeGpuSampler(os.getpid()); ram = RamSampler(os.getpid())
gpu.start(); ram.start(); started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for stage in prereg['stages']:
        client.stage = stage
        for case in cases:
            client.case_id = case['id']; client.begin_request(40)
            answer = None; error = None
            try:
                candidates = copy.deepcopy(case['candidates'])
                if stage == 'json_inherited_boundaries':
                    for candidate in candidates:
                        candidate['description'] = _native_selection_description(candidate['name'], candidate['description'])
                names, descriptions, contracts = _prepare_turn_candidates(candidates)
                if stage == 'native_auto':
                    answer = client._post_native_tool_selection(case['text'], names, contracts, case['history'])
                elif stage.startswith('count_'):
                    messages = [{'role': 'system', 'content': EFFECT_COUNT_VERIFIER_PROMPT}]
                    if stage == 'count_dialogue':
                        messages.extend(case['history'])
                    text = case['text']
                    if stage == 'count_scoped_context':
                        text = json.dumps({'previous_dialogue_for_references_only': case['history'], 'current_request_to_classify': text}, ensure_ascii=False)
                    messages.append({'role': 'user', 'content': text})
                    payload = {'messages': messages, 'temperature': 0.0, 'seed': 0, 'max_tokens': 24,
                        'chat_template_kwargs': {'enable_thinking': False},
                        'response_format': {'type': 'json_schema', 'json_schema': {'name': 'baxy_effect_count_verification', 'strict': True, 'schema': {'type': 'object', 'properties': {'effect_count': {'type': 'string', 'enum': ['zero', 'one', 'multiple']}}, 'required': ['effect_count'], 'additionalProperties': False}}}}
                    answer = client._post(payload)['choices'][0]['message']
                else:
                    answer = client._post(_build_turn_policy_payload(case['text'], names, descriptions, case['history']))['choices'][0]['message']
            except Exception as exc:
                error = f'{type(exc).__name__}: {exc}'
            finally:
                client.end_request()
            result = {'stage': stage, 'id': case['id'], 'text': case['text'], 'answer': answer, 'error': error}
            with (OUT/'replies.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(result, ensure_ascii=False)+'\n')
            print(json.dumps(result, ensure_ascii=False), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic()-started,2), 'gpuPeakMiB': gpu.peak_mib, 'ramPeakMiB': ram.peak_mib, 'registrationUnchanged': hashlib.sha256(register.read_bytes()).hexdigest()==prereg['registrationSha256']}
    (OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)
