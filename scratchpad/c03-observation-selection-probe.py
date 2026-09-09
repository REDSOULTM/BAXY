"""Compare inherited weak identity checks with contextual native AUTO selection."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / 'src'), str(root)]
from baxy_mind.llm import LlmRuntime, _prepare_turn_candidates
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-observation-selection'
out.mkdir(exist_ok=True)
assert not (out / 'PREREG.json').exists()
prior = json.loads((base / 'astra-real-context-ablation/PREREG.json').read_text(encoding='utf-8'))
wanted = {'system.time', 'web.search', 'audio.status'}
found = {candidate['name']: candidate for case in prior['cases'] for candidate in case['candidates']
         if candidate['name'] in wanted}
assert set(found) == wanted, set(found)
names, _, contracts = _prepare_turn_candidates(list(found.values()))
definition = [{'role': 'user', 'content': 'What is an SSID?'},
              {'role': 'assistant', 'content': 'An SSID is the name of a Wi-Fi network.'}]
clock = [{'role': 'user', 'content': 'dime la hora'}, {'role': 'assistant', 'content': '20:54'}]
cases = [
    {'text': '¿y para qué sirve?', 'history': definition, 'expected': []},
    {'text': 'What is an SSID?', 'history': [], 'expected': []},
    {'text': 'no me molesta, dime la hora', 'history': definition, 'expected': ['system.time']},
    {'text': "I don't mind, tell me the time", 'history': clock, 'expected': ['system.time']},
    {'text': 'no abras Steam, dime la hora', 'history': clock, 'expected': ['system.time']},
    {'text': 'no uses herramientas, dime la hora', 'history': clock, 'expected': []},
    {'text': '¿Qué volumen tiene el audio ahora?', 'history': definition, 'expected': ['audio.status']},
    {'text': 'no me digas la hora', 'history': clock, 'expected': []},
]
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'],
                  BAXY_MIND_NGL=str(config['ngl']))
prereg = {'cases': cases, 'candidates': list(found.values()),
          'method': 'Eight consumed or synthetic controls; no fresh acceptance. Compare per-candidate operation_is_the_requested_effect without context (current recovery probe) with existing native AUTO selection with supplied dialogue. Same catalog subset, model, backend, template and temperature. No execution. This compares interpretation mechanisms as used, not a claim that token budget or context alone causes a difference. Existing identity verifier rejects only21/84 wrong proposals in its historical measurement; here it can wrongly turn knowledge into a clarification.',
          'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')

class Client(LlmRuntime):
    case = ''
    stage = ''

    def _post(self, payload, *args, **kwargs):
        response = super()._post(payload, *args, **kwargs)
        with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'case': self.case, 'stage': self.stage, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
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
    for case in cases:
        client.case = case['text']
        client.begin_request(60)
        try:
            client.stage = 'weak_identity'
            weak = [name for name in names if client.operation_is_the_requested_effect(case['text'], name, contracts[name])]
            client.stage = 'native_contextual'
            native = client._post_native_tool_selection(case['text'], names, contracts, case['history'])
        finally:
            client.end_request()
        row = {'text': case['text'], 'expected': case['expected'], 'weak_identity': weak, 'native_contextual': native}
        with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(json.dumps(row, ensure_ascii=False), flush=True)
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
