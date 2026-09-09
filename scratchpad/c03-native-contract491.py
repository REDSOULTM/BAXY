"""Native-only ablation of actual argument schemas; no product or provider changes."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import sys
import threading
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'src')]
import psutil
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = base / 'astra-native-contract491'
private = local / 'C03-native-contract491-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def append(path, value):
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')

prior = local / 'C03-native-profile490-private'
posts = [json.loads(line) for line in (prior / 'http-posts.jsonl').open(encoding='utf-8-sig')]
originals = {}
for row in posts:
    if row['stage'] == 'request' and row['payload'].get('tools'):
        payload = row['payload']
        if any(text in payload['messages'][-1]['content'] for text in ['dessilencies', 'Al 100, pero']):
            originals.setdefault((payload['messages'][-1]['content'], payload['seed']), payload)
assert len(originals) == 4
capabilities = json.loads((prior / 'catalog.json').read_text(encoding='utf-8-sig'))['capabilities']
schemas = {'baxy_' + cap['name'].replace('.', '__'): cap['argumentsSchema'] for cap in capabilities}
zero_statement = ('Function arguments are extracted and validated in a later stage, '
                  'so the declared functions take no arguments here. ')

def typed(payload):
    result = copy.deepcopy(payload)
    assert zero_statement in result['messages'][0]['content']
    result['messages'][0]['content'] = result['messages'][0]['content'].replace(zero_statement, '')
    for tool in result['tools']:
        tool['function']['parameters'] = copy.deepcopy(schemas[tool['function']['name']])
    return result

cases = []
for (text, seed), payload in originals.items():
    cases.append({'id': ('owner46' if 'dessilencies' in text else 'owner51') + '-seed' + str(seed),
                  'variant': 'typed', 'payload': typed(payload), 'reference': payload,
                  'baseline': 'Exact matching native request in490; baseline not rerun.'})
reference = next(payload for (text, seed), payload in originals.items() if text.startswith('Al 100') and seed == 0)
controls = [
    ('clitic-alone', 'Desmutéalo'),
    ('volume-unmute', 'Pon el volumen al 37 y desmutéalo'),
    ('unmute-volume', 'Desmutéalo y pon el volumen al 37'),
    ('negative-unmute', 'Pon el volumen al 37 pero no quites el silencio'),
    ('word-meaning', '¿Qué significa desmutear?'),
    ('negative-only', 'No desmutees el audio'),
]
for case_id, text in controls:
    payload = copy.deepcopy(reference)
    payload['messages'] = [payload['messages'][0], {'role': 'user', 'content': text}]
    for variant in ['zero', 'typed']:
        cases.append({'id': case_id, 'variant': variant,
                      'payload': payload if variant == 'zero' else typed(payload)})
assert len(cases) == 16
write(private / 'cases.json', cases)
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
manifest_sha = sha(manifest)
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=config['gguf'], BAXY_MIND_LLAMA_SERVER=config['llama_server'],
                  BAXY_MIND_NGL=str(config['ngl']))
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Native requests only. Four exact contextual payloads490 with official Qwen2507 profile/seeds0,17; six synthetic consumed controls compare zero-argument versus actual typed schemas with same28 candidates and no history. Typed interface replaces only zero schemas with authenticated current schemas and removes the now-false zero-argument sentence. No forced tools, examples, descriptor edits or expected tool names in requests. No BAXY semantic guards, ranking, argument extraction, providers, UI or voice in this isolated test.',
    'hypothesis': 'Removing native boolean/level argument schemas may hide postcondition information useful to select unmute and both effects. Restore true tool contracts to inspect native understanding before changing production.',
    'heritage': 'Native AUTO scoped tests35/native-scope already distinguish protocol success from semantic validation. Current model research and toolcalling inheritance reviewed; no measured comparison of actual schemas for these contextual cases found.',
    'sources': ['https://qwen.readthedocs.io/en/stable/framework/function_call.html',
                'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507',
                'https://arxiv.org/abs/2408.02442', 'https://blog.dottxt.ai/say-what-you-mean.html'],
    'limits': {'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768, 'request_seconds': 90},
    'criteria': 'Preserve requested operation set/order, level100/37 and muted=false without invented success or effects on knowledge/negation. Record finish reasons and any context overflow; do not narrow candidates/increase resources to disguise failure. Native success alone is not adoption or product acceptance.',
    'model': config['gguf'], 'model_sha256': sha(config['gguf']),
    'server': config['llama_server'], 'server_sha256': sha(config['llama_server']),
    'manifest_sha256': manifest_sha, 'private': str(private), 'cases_sha256': sha(private / 'cases.json'),
    'source_effect_intent_sha256': sha(root / 'src/baxy_mind/effect_intent.py'),
    'source_llm_sha256': sha(root / 'src/baxy_mind/llm.py'),
})
client = LlmRuntime()
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
stop = threading.Event()
violations = []

def watch():
    while not stop.wait(.25):
        if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
            violations.append('gpu_bound')
        if psutil.virtual_memory().available < 768 * 2**20:
            violations.append('free_ram_bound')
        if violations:
            client.close()
            return

guard = threading.Thread(target=watch, daemon=True)
started = time.monotonic()
completed = False
try:
    gpu.start(); ram.start(); guard.start()
    client.start_warmup(); assert client.wait_warmup(90)
    print('Native server ready; no BAXY turn guards or effects', flush=True)
    for case in cases:
        client.begin_request(90)
        before = time.monotonic()
        try:
            response = client._post(copy.deepcopy(case['payload']))
            value = {'response': response}
        except Exception as error:
            value = {'error': type(error).__name__ + ': ' + str(error)}
        finally:
            client.end_request()
        row = {'id': case['id'], 'variant': case['variant'],
               'seconds': round(time.monotonic() - before, 3), **value}
        append(private / 'posts.jsonl', {'payload': case['payload'], **row})
        append(out / 'replies.jsonl', row)
        print(json.dumps({'id': case['id'], 'variant': case['variant'],
                          'seconds': row['seconds'], 'choices': value.get('response', {}).get('choices'),
                          'error': value.get('error')}, ensure_ascii=True), flush=True)
        if violations:
            break
    completed = not violations
finally:
    stop.set(); client.close(); guard.join(timeout=5); gpu.stop(); ram.stop()
    write(out / 'RESOURCES.json', {'completed': completed, 'violations': violations,
                                  'gpu_peak_mib': gpu.peak_mib, 'ram_peak_mib': ram.peak_mib,
                                  'seconds': round(time.monotonic() - started, 3),
                                  'manifest_unchanged': sha(manifest) == manifest_sha})
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
