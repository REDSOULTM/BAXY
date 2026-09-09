from pathlib import Path
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / 'src'), str(root)]
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

sys.stdout.reconfigure(encoding='utf-8')
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-progress-pipeline99'
out.mkdir(exist_ok=False)
source = base / 'astra-progress-stages97/posts.jsonl'
cases = [json.loads(s) for s in source.read_text(encoding='utf-8').splitlines()]
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
model = 'D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf'
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=model, BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(out / 'compose-audit.jsonl'), BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1')
prereg = {'method': 'Actual Python compose_user_message pipeline after source98 with exact eight97 phase/language '
    'fixtures. App now supplies phase via FieldBridgeContract; this test supplies the same typed shape, but '
    'does not claim observed UI/phase transitions. All original user texts reach public API/policy/language; '
    'narrator receives only actual activity. Capture actual first/retry packets, accepted return or error, '
    'time/resources. No source/model/prompt/sampler changes, functions/audio/reserve or promotion.',
    'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'model': model,
    'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest(),
    'files': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in (
        'src/baxy_mind/llm.py', 'src/Baxy.App/MainWindowViewModel.cs', 'src/Baxy.App/UserMessagePolicy.cs',
        'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll')}}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
current = None

class RecordedRuntime(LlmRuntime):
    def _post(self, payload, *args, **kwargs):
        response = super()._post(payload, *args, **kwargs)
        if current is not None:
            row = {'case': current, 'payload': payload, 'response': response}
            with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        return response

client = RecordedRuntime(); gpu = ProcessTreeGpuSampler(os.getpid()); ram = RamSampler(os.getpid())
gpu.start(); ram.start(); started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for case in cases:
        current = case['turn'] + '/' + case['variant']
        phase = 'acting' if case['variant'] == 'step_two_of_three' else case['variant']
        situation = {'kind': 'status', 'cause': 'acting', 'polarity': 'success', 'phase': phase}
        if case['variant'] == 'step_two_of_three':
            situation.update(step=2, totalSteps=3)
        facts = {'situation': situation, 'traceId': current}
        client.begin_request(40); case_started = time.monotonic()
        result = {'case': current, 'request': case['text'], 'facts': facts}
        try:
            result['final'] = client.compose_user_message(case['text'], 'status', facts)
        except Exception as exc:
            result['error'] = type(exc).__name__ + ': ' + str(exc)
        finally:
            client.end_request()
        result['seconds'] = round(time.monotonic() - case_started, 3)
        with (out / 'finals.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + '\n')
        print(json.dumps(result, ensure_ascii=False), flush=True)
        assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
        'ramPeakMiB': ram.peak_mib, 'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
