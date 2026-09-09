"""Compare lookup-scope facts before changing the product result contract."""
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
mode = sys.argv[1] if len(sys.argv) > 1 else 'scope'
assert mode in {'scope', 'unsupported'}
out = base / ('astra-files-scope59' if mode == 'scope' else 'astra-files-path62')
out.mkdir(exist_ok=False)
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'],
                  BAXY_MIND_NGL=str(config['ngl']))
turns = json.loads((base / 'astra-files58-modal/paired.json').read_text(encoding='utf-8'))
selected = [turn for turn in turns if turn['turnId'] in {'t1', 't4'}]
prereg = {'method': 'Two consumed outside-path requests and their actual recorded failure situations from files58. '
          'Reconstruct the first HTTP payload with the current compose API, no conversation history and mustNotAskFollowUp=true '
          'as in the App error route. Native completions retain BAXY prompts, template, sampler and 256-token limit; '
          'no visible validation or retries. Compare baseline with only scope=sandbox added to the completed filesystem.search '
          'observation, a fact justified by the current provider/catalog. No product source or catalog change yet. '
          'No file effects, UI/audio or human reserve claim. This is not an identity-free raw-model test.',
          'texts': [turn['request'] for turn in selected],
          'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
if mode == 'unsupported':
    prereg['method'] = ('Counterfactual native comparison before a provider validation change. Current filesystem.search '
                       'declares filename search inside a sandbox; absolute paths can never match a Windows filename. '
                       'Compare captured current empty-search failure with a typed absolute_path_search_unsupported '
                       'failure before lookup, no completed steps. Same two literal technical requests, model, '
                       'BAXY prompts, sampler, limits; no guards/retries or product source change. '
                       'This is proposed validation behavior, not an observed provider error. No UI/audio/human reserve.')
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')

class Captured(BaseException):
    pass

class Capture(LlmRuntime):
    def __init__(self):
        self._gguf = config['gguf']
        self.payload = None

    def _post(self, payload, *args, **kwargs):
        self.payload = copy.deepcopy(payload)
        raise Captured()

client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for turn in selected:
        original = next(row for row in turn['compose'] if row.get('stage') == 'first' and row.get('intent') == 'error')
        for variant in ('baseline', mode):
            situation = json.loads(original['situation'])
            if variant == 'scope':
                for index, step in enumerate(situation['steps']):
                    parsed = json.loads(step)
                    if parsed.get('operation') == 'filesystem.search':
                        assert parsed['verified'] and parsed['observed']['count'] == 0
                        parsed['observed']['scope'] = 'sandbox'
                        situation['steps'][index] = json.dumps(parsed, ensure_ascii=False)
            elif variant == 'unsupported':
                situation = {'kind': 'failure', 'cause': 'mission_failed', 'polarity': 'failure',
                             'steps': [], 'stepCount': 0,
                             'reason': {'kind': 'operation', 'operation': 'filesystem.search',
                                        'polarity': 'failure', 'verified': False, 'succeeded': False,
                                        'error': 'absolute_path_search_unsupported'}}
            capture = Capture()
            try:
                capture.compose_user_message(turn['request'], 'error',
                                             {'situation': situation, 'mustNotAskFollowUp': True})
            except Captured:
                pass
            assert capture.payload is not None
            client.begin_request(40)
            try:
                response = client._post(capture.payload)
            finally:
                client.end_request()
            with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'turn': turn['turnId'], 'text': turn['request'], 'variant': variant,
                                         'payload': capture.payload, 'response': response}, ensure_ascii=False) + '\n')
            choice = response['choices'][0]
            print(json.dumps({'turn': turn['turnId'], 'variant': variant,
                              'raw': choice['message'].get('content'), 'finish_reason': choice.get('finish_reason')},
                             ensure_ascii=False), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
              'ramPeakMiB': ram.peak_mib,
              'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
