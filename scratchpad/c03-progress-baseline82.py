"""One causal progress-role comparison; preserve actual BAXY payload and sampler."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / 'src'), str(root)]
from baxy_mind.llm import LlmRuntime, _PROGRESS_MESSAGE_INSTRUCTION
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-progress-baseline82'
out.mkdir(exist_ok=False)
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
config['gguf'] = 'D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf'
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'],
                  BAXY_MIND_NGL=str(config['ngl']))
extra = (' Describe only the work in progress. Do not infer properties, contents or problems '
         'of the target from its name or from the wording of the request.')
texts = [
    'Read the file "c03-invalid-utf8.txt" in the sandbox.',
    'Lee el archivo "informe-corrupto.txt" del sandbox.',
    'Read the file "disk-full.txt" in the sandbox.',
    'Dime la hora y el uso de CPU.',
    'Pon el volumen al 20%.',
    'Why couldn\'t you read that file?',
]
prereg = {'method': 'Current source81 and isolated Qwen3.5 override. First actual compose payload for six technical progress requests, with existing role/sampler and no added instruction, guards or retries. Source64 prepared comparison was never run and is not a baseline. No file/audio effects, human reserve, UI or acoustic claim. Judge whether wording infers target properties or claims a new read for a why question.',
          'texts': texts, 'model': config['gguf'], 'addedInstruction': None,
          'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest(),
          'sourceSha256': hashlib.sha256((root / 'src/baxy_mind/llm.py').read_bytes()).hexdigest()}
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
    for index, user_text in enumerate(texts, 1):
        capture = Capture()
        try:
            capture.compose_user_message(user_text, 'status',
                {'situation': {'kind': 'status', 'polarity': 'success', 'cause': 'acting'}})
        except Captured:
            pass
        assert capture.payload is not None
        for variant in ('baseline',):
            payload = copy.deepcopy(capture.payload)
            if variant == 'inference':
                system = payload['messages'][0]
                assert _PROGRESS_MESSAGE_INSTRUCTION in system['content']
                system['content'] = system['content'].replace(_PROGRESS_MESSAGE_INSTRUCTION,
                    _PROGRESS_MESSAGE_INSTRUCTION + extra, 1)
            client.begin_request(40)
            try:
                response = client._post(payload)
            finally:
                client.end_request()
            with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'turn': f't{index}', 'text': user_text, 'variant': variant,
                    'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
            print(json.dumps({'turn': index, 'variant': variant,
                'raw': response['choices'][0]['message']['content']}, ensure_ascii=False), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
        'ramPeakMiB': ram.peak_mib,
        'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
