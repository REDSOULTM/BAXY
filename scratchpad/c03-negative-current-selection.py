"""Controlled native selection diagnostic; declared tools are never executed."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / 'src'), str(root)]
from baxy_mind.llm import LlmRuntime, _prepare_turn_candidates
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler, current_core_catalog_snapshot

base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-negative-current-selection'
out.mkdir(exist_ok=True)
assert not (out / 'PREREG.json').exists()
source = base / 'astra-integrated-real22'
paired = json.loads((source / 'paired.json').read_text(encoding='utf-8'))
audit = [json.loads(line) for line in (source / 'turn-audit.jsonl').open(encoding='utf-8')]
observed = next(r for r in audit if r.get('request_id') == '75' and r.get('phase') == 'raw_attempt')
catalog, _, _ = current_core_catalog_snapshot(root / 'src/Baxy.Core/bin/Release/net10.0-windows10.0.19041.0/win-x64/publish/baxy-core.exe')
by_name = {row['name']: row for row in catalog}
selection_names = list(observed['candidate_operations'])[:26] + ['system.time', 'app.open']
selection_names = list(dict.fromkeys(selection_names))
candidates = [{'name': name, 'description': by_name[name]['description'], 'arguments_schema': by_name[name]['argumentsSchema']} for name in selection_names]
names, _, contracts = _prepare_turn_candidates(candidates)
history = [message for row in paired[16:19] for message in (
    {'role': 'user', 'content': row['request']}, {'role': 'assistant', 'content': row['final']})]
cases = [
    {'text': 'no silencies el audio', 'expected': [], 'origin': 'integrated-real22 t20, consumed'},
    {'text': 'no subas el volumen', 'expected': [], 'origin': 'integrated-real22 t11, consumed, changed history'},
    {'text': "Don't mute the audio", 'expected': [], 'origin': 'synthetic control'},
    {'text': 'no me digas la hora', 'expected': [], 'origin': 'consumed control, changed history'},
    {'text': 'no abras Steam, dime la hora', 'expected': ['system.time'], 'origin': 'consumed control, changed history'},
    {'text': 'dime la hora, no abras Steam', 'expected': ['system.time'], 'origin': 'synthetic order control'},
    {'text': 'dime la hora y no abras Steam', 'expected': ['system.time'], 'origin': 'synthetic order control'},
    {'text': 'no uses herramientas, dime la hora', 'expected': [], 'origin': 'consumed control, changed history'},
    {'text': '¿No está silenciado el audio?', 'expected': ['audio.status'], 'origin': 'synthetic negative question control'},
    {'text': 'está silenciado el audio', 'expected': ['audio.status'], 'origin': 'integrated-real22 t14, consumed, changed history'},
    {'text': 'Ponlo a 100 ahora', 'expected': ['audio.volume'], 'origin': 'integrated-real22 t17, consumed, changed history'},
    {'text': 'no me molesta, dime la hora', 'expected': ['system.time'], 'origin': 'consumed control, changed history'},
]
clarification = (
    ' Interpret only current_request_to_interpret. previous_dialogue_for_references_only '
    'supplies referents, never an additional request to repeat or continue. '
    'Distinguish a request to observe a state from a restriction on changing it: '
    'acknowledging a restriction requires no status check. Negation scopes to its '
    'own clause; an independent positive request still requires its function, '
    'unless the person prohibits tool use altogether. A question about a negative '
    'state is still a request to observe, not a prohibition.'
)
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
prereg = {'cases': cases, 'history': history, 'candidates': candidates, 'clarification': clarification,
          'method': 'Same twelve consumed/synthetic controls in baseline and explicit current-request policy. Single difference is system prompt clarification; same model, native template, tools, six reconstructed public history messages, temperature/seed/budget. Catalog inherits first26 of actual t20 shortlist and replaces last2 with clock/app controls, respecting the28 limit. No calls execute, no acceptance reserve, no source/model promotion. History reconstructed from visible transcript, not asserted exact internal wire capture.',
          'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')

class Client(LlmRuntime):
    stage = ''
    case = ''
    def _post(self, payload, *args, **kwargs):
        if self.stage == 'current_request_policy':
            payload = {**payload, 'messages': [dict(m) for m in payload['messages']]}
            payload['messages'][0]['content'] += clarification
        response = super()._post(payload, *args, **kwargs)
        with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'stage': self.stage, 'case': self.case, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
        return response

client = Client()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start()
ram.start()
started = time.monotonic()
try:
    client.start_warmup()
    assert client.wait_warmup(90)
    for stage in ('baseline', 'current_request_policy'):
        client.stage = stage
        for case in cases:
            client.case = case['text']
            client.begin_request(60)
            try:
                result = client._post_native_tool_selection(case['text'], names, contracts, history)
            finally:
                client.end_request()
            row = {'stage': stage, 'text': case['text'], 'expected': case['expected'], 'answer': result,
                   'pass': result.get('effect_operations') == case['expected']}
            with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(json.dumps(row, ensure_ascii=False), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close()
    gpu.stop()
    ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
              'ramPeakMiB': ram.peak_mib, 'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
