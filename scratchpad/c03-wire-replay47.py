"""Replay captured chat payloads with one context difference at a time."""
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
out = base / 'astra-wire-replay47'
out.mkdir(exist_ok=False)
wire = [json.loads(s) for s in (base / 'astra-wire-context47/wire-36612.jsonl').read_text(encoding='utf-8').splitlines()]
failed = json.loads((base / 'astra-routes-volume46/paired.json').read_text(encoding='utf-8'))
cases = []
for index in (7, 8, 9):
    text = failed[index]['request']
    captured = next(r for r in wire if r['payload'].get('messages', [{}])[-1].get('content') == text)
    earlier = [m for r in failed[:index] for m in (
        {'role': 'user', 'content': r['request']}, {'role': 'assistant', 'content': r['final']})]
    # C# takes12 including the current input; chat then removes its duplicate.
    context = (earlier + [{'role': 'user', 'content': text}])[-12:-1]
    cases.append({'text': text, 'capturedPayload': captured['payload'], 'failedPanelContext': context})
reg = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(reg.read_text(encoding='utf-8-sig'))
for name in list(os.environ):
    if name.startswith('BAXY_MIND_'):
        del os.environ[name]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
stages = ['captured', 'failed_panel_context', 'no_context']
prereg = {'cases': cases, 'stages': stages,
    'method': 'Nine direct native server completions. Three exact captured product chat payloads; substitute only preceding dialogue with source46 failed-panel public context following actual C# last12 and Python duplicate-removal semantics; then retain only current user plus unchanged system policies. Same template, temperature0, seed0, budget256, no reply guards/retries or functions. Capture full raw finish reason. Not fresh acceptance, no source/model promotion. Original failed-panel wire was not captured: that middle stage remains a reconstruction, now including its leading orphan assistant.',
    'registrationSha256': hashlib.sha256(reg.read_bytes()).hexdigest()}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
started = time.monotonic()
try:
    client.start_warmup(); assert client.wait_warmup(90)
    for stage in stages:
        for case in cases:
            payload = copy.deepcopy(case['capturedPayload'])
            if stage != 'captured':
                payload['messages'] = [m for m in payload['messages'] if m['role'] == 'system'] + (
                    case['failedPanelContext'] if stage == 'failed_panel_context' else []) + [payload['messages'][-1]]
            client.begin_request(40)
            try:
                response = client._post(payload)
            finally:
                client.end_request()
            record = {'stage': stage, 'text': case['text'], 'payload': payload, 'response': response}
            with (out / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + '\n')
            choice = response['choices'][0]
            print(json.dumps({'stage': stage, 'text': case['text'], 'answer': choice['message'].get('content'),
                              'finish_reason': choice.get('finish_reason')}, ensure_ascii=False), flush=True)
            assert gpu.peak_mib is None or gpu.peak_mib <= 4096
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
              'ramPeakMiB': ram.peak_mib, 'registrationUnchanged': hashlib.sha256(reg.read_bytes()).hexdigest() == prereg['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
