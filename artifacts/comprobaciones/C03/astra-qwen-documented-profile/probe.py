"""Registered local server: documented sampling and layer comparison, no PC effects."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from baxy_mind.llm import LlmRuntime, _build_turn_policy_payload, _prepare_turn_candidates
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'astra-qwen-documented-profile'
OUT.mkdir(exist_ok=False)
register = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(register.read_text(encoding='utf-8-sig'))
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        del os.environ[key]
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))
posts = [json.loads(line) for line in (BASE / 'astra-real-dialogue-system-layers/posts.jsonl').read_text(encoding='utf-8-sig').splitlines()]
chats = {}
for post in posts:
    if post['variant'] == 'baseline' and post['case'] not in chats:
        chats[post['case']] = post['payload']
contexts = json.loads((BASE / 'astra-real-context-ablation/PREREG.json').read_text(encoding='utf-8-sig'))['cases']
profiles = [
    {'name': 'current_greedy', 'params': {'temperature': 0.0}, 'seeds': [0]},
    {'name': 'qwen_documented', 'params': {'temperature': 0.7, 'top_p': 0.8, 'top_k': 20, 'min_p': 0.0, 'presence_penalty': 0.0}, 'seeds': [0, 17]},
]
prereg = {
    'method': 'Raw loopback HTTP to same registered model/server; LlmRuntime owns startup/cleanup only. No BAXY chat wrapper, validators, recovery or PC effects. Consumed literal real-log inputs. Compare user-only 512, BAXY messages 512, BAXY messages original budget; then primary structured policy with prior reconstructed context. All raw outputs retained. This is development, not fresh acceptance. Seed 0 for greedy, fixed seeds 0 and 17 for documented sampling. No selection of favorable seeds.',
    'profiles': profiles, 'chatPayloads': chats, 'contextCases': contexts,
    'registrationSha256': hashlib.sha256(register.read_bytes()).hexdigest(),
    'sourceSha256': hashlib.sha256((ROOT / 'src/baxy_mind/llm.py').read_bytes()).hexdigest(),
    'source': 'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507#best-practices',
}
(OUT / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'probe.py').write_bytes(Path(__file__).read_bytes())

def write_json(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start(); started = time.monotonic()
count = 0

def call(path, payload=None):
    body = None if payload is None else json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(client._endpoint.rstrip('/') + path, data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)

def measure(layer, case_id, profile, seed, payload):
    global count
    payload = copy.deepcopy(payload)
    payload.update(profile['params'], seed=seed)
    t0 = time.monotonic()
    response = None; error = None
    try:
        response = call('/v1/chat/completions', payload)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    record = {'layer': layer, 'id': case_id, 'profile': profile['name'], 'seed': seed, 'payload': payload, 'response': response, 'error': error, 'seconds': round(time.monotonic()-t0, 3)}
    with (OUT / 'posts.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
    count += 1
    assert gpu.peak_mib is None or gpu.peak_mib <= 4096
    if count % 12 == 0:
        print(json.dumps({'completed': count, 'gpuPeakMiB': gpu.peak_mib}), flush=True)

try:
    client.start_warmup(); assert client.wait_warmup(90)
    write_json('COMMAND.json', client._server_command())
    props = call('/props'); write_json('PROPS.json', props)
    for layer in ['user_only_512', 'baxy_messages_512', 'baxy_messages_original_budget']:
        for case_id, original in chats.items():
            payload = copy.deepcopy(original)
            if layer == 'user_only_512':
                payload['messages'] = [payload['messages'][-1]]
            if layer != 'baxy_messages_original_budget':
                payload['max_tokens'] = 512
            if case_id == next(iter(chats)):
                write_json(f'TEMPLATE-{layer}.json', call('/apply-template', {'messages': payload['messages'], 'add_generation_prompt': True}))
            for profile in profiles:
                for seed in profile['seeds']:
                    measure(layer, case_id, profile, seed, payload)
    for case in contexts:
        names, descriptions, _ = _prepare_turn_candidates(case['candidates'])
        payload = _build_turn_policy_payload(case['text'], names, descriptions, case['history'])
        for profile in profiles:
            for seed in profile['seeds']:
                measure('primary_structured', case['id'], profile, seed, payload)
finally:
    client.close(); gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic()-started, 2), 'gpuPeakMiB': gpu.peak_mib, 'ramPeakMiB': ram.peak_mib, 'calls': count, 'registrationUnchanged': hashlib.sha256(register.read_bytes()).hexdigest() == prereg['registrationSha256']}
    write_json('RESULT.json', result)
    print(json.dumps(result), flush=True)
