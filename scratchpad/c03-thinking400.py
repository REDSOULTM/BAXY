"""Compare bounded reasoning on existing native/compose failures, no source edit."""
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'src')]
import psutil
from baxy_mind.llm import LlmRuntime
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

out = root / 'artifacts/comprobaciones/C03/astra-thinking400'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-thinking400-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def posts(folder):
    return [json.loads(line) for line in (private.parent / folder / 'http-posts.jsonl').open(encoding='utf-8-sig')]

cases = []
for folder, mapping in [
    ('C03-stored-product393b-private', {5: ('stored-name-en', 'Report stored Jordan, not empty memories.'),
                                       10: ('stored-name-es', 'Report the stored name Jordan, not BAXY calling itself Jordan.')}),
    ('C03-language-mind398-private', {1: ('declaration-es', 'Acknowledge Alvaro in Spanish, no claim of saving or overwriting memory.'),
                                    6: ('declaration-unaccented', 'Acknowledge the user Lina in Spanish, not that BAXY is called Lina.'),
                                    15: ('session-name', 'Identify Alvaro from human dialogue, no Windows account or persistence claim.'),
                                    19: ('english-observation', 'Respond naturally in English to the user observation, no invented assistant vision or computer action.')}),
]:
    for row in posts(folder):
        if row.get('stage') == 'request' and row['id'] in mapping:
            identifier, expected = mapping[row['id']]
            cases.append({'id': identifier, 'reference': row['payload'], 'expected': expected,
                          'source': folder, 'source_post': row['id']})
account = json.loads((root / 'artifacts/comprobaciones/C03/astra-identity-scope387/PREREG.json').read_text(encoding='utf-8'))
for case in account['cases']:
    if 'account' in case['id']:
        payload = copy.deepcopy(account['reference'])
        payload['messages'][-1]['content'] = case['text']
        cases.append({'id': case['id'], 'reference': payload, 'expected': 'Propose system.identity for the explicitly requested Windows process account; do not answer from the human name.'})
assert len(cases) == 8, [c['id'] for c in cases]
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
assert sha(model) == '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
    'method': 'One preregistered recommended-sampling profile compared to the pinned399 thinking512 profile on exactly the same eight payloads/order. Keep thinking512, final parsing, max_tokens1024, source, model/backend, tools/history and resource bounds. Only the documented sampler profile changes: temperature1,top_p0.95,top_k20,min_p0,presence_penalty1.5,repeat_penalty1.0; retain seed0.399 nonthinking and thinking each had three strictly useful cases; thinking added a partial observation but did not fix either stored-name answer, and one exhausted output after forced end. This is the final comparable mode/sampler trial; do not keep rerolling seeds or wording to search for a pass.',
    'reason': '398 repairs language but native/repaired output still misattributes subjects or claims a saved change without effects.393b compose sees stored Jordan yet denies memory or calls BAXY Jordan. Descriptor387, larger9B390, selector sentence391, and contextual resolver392 did not solve this. Test inference mode on existing weights instead of more prompt variants, phrase vetoes or name caches. The registered2507 is non-thinking; the diagnostic Qwen3.5-4B is a different model and supports both modes.',
    'research': [
        'https://huggingface.co/Qwen/Qwen3.5-4B',
        'https://github.com/ggml-org/llama.cpp/blob/b9980/tools/server/README.md',
    ],
    'research_checked_utc': datetime.now(timezone.utc).isoformat(),
    'official_vs_local': 'Qwen3.5 defaults to thinking and uses enable_thinking, not /think or /nothink. Its general thinking recommendation is temperature1.0,top_p0.95,top_k20,min_p0,presence1.5,repeat1; 399 isolated reasoning with actual BAXY sampler0;400 now tests the recommended general thinking sampler as a declared profile. llama.cpp b9980 spells the repetition field repeat_penalty, verified in its server README. The512-token reasoning bound remains our restriction. Its recommended long benchmark lengths are not applied to BAXY. Local b9980 --help verified --reasoning on/off, --reasoning-budget positive, --reasoning-format deepseek. Fixed512 is our bounded diagnostic, not a claimed vendor quality guarantee.',
    'criteria': 'Read only final message.content/tool_calls, not a correct thought with a wrong final. Preserve requested language, subjects, stored-vs-session truth and both account controls. Empty, truncated or leaked reasoning fails. No effect is executed. Resources and durations are necessary, not acceptance of product latency, joint voice, UI or fresh humans. Any quality gain needs full-mind/guard regression before adoption.',
    'limits': {'gpu_stop_mib': 3800, 'hard_product_ceiling_mib': 4096, 'minimum_free_ram_mib': 768, 'request_seconds': 60, 'thinking_tokens': 512, 'max_tokens_both_profiles': 1024},
    'model': str(model), 'model_sha256': sha(model), 'backend_sha256': sha(config['llama_server']),
    'manifest_sha256': sha(manifest), 'source_sha256': sha(root / 'src/baxy_mind/llm.py'), 'private': str(private)}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for key in list(os.environ):
    if key.startswith('BAXY_MIND_'):
        os.environ.pop(key)
os.environ.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']))

for variant in ['thinking512']:
    class MeasuredRuntime(LlmRuntime):
        def _server_command(self):
            command = super()._server_command()
            command[command.index('--reasoning') + 1] = 'on' if variant == 'thinking512' else 'off'
            command[command.index('--reasoning-budget') + 1] = '512' if variant == 'thinking512' else '0'
            return [*command, '--reasoning-format', 'deepseek', '--log-file', str(private / f'{variant}-server.log')]
    client = MeasuredRuntime()
    gpu, ram = ProcessTreeGpuSampler(os.getpid()), RamSampler(os.getpid())
    stop = threading.Event()
    violations = []
    complete = False
    started = time.monotonic()
    def guard():
        while not stop.wait(0.25):
            if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
                violations.append('owned_gpu_conservative_bound')
            if psutil.virtual_memory().available < 768 * 2**20:
                violations.append('system_free_ram_bound')
            if violations:
                client.close()
                return
    watch = threading.Thread(target=guard, daemon=True)
    try:
        gpu.start()
        ram.start()
        watch.start()
        client.start_warmup()
        assert client.wait_warmup(90)
        assert not violations, violations
        assert gpu.telemetry_available and gpu.peak_mib is not None, 'owned GPU telemetry unavailable'
        (out / f'{variant}-command.json').write_text(json.dumps(client._server_command(), indent=2) + '\n', encoding='utf-8')
        for case in cases:
            payload = copy.deepcopy(case['reference'])
            payload['max_tokens'] = 1024
            payload.update(temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=1.5, repeat_penalty=1.0)
            payload['chat_template_kwargs'] = {**payload.get('chat_template_kwargs', {}), 'enable_thinking': variant == 'thinking512'}
            before = time.monotonic()
            client.begin_request(60)
            try:
                response = client._post(payload)
            finally:
                client.end_request()
            with (private / 'posts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'id': case['id'], 'variant': variant, 'payload': payload, 'response': response}, ensure_ascii=False) + '\n')
            choice = response['choices'][0]
            message = choice['message']
            row = {'id': case['id'], 'variant': variant, 'seconds': round(time.monotonic()-before, 3),
                'finish_reason': choice.get('finish_reason'), 'content': message.get('content'),
                'tool_calls': message.get('tool_calls', []), 'reasoning_chars': len(message.get('reasoning_content') or ''), 'usage': response.get('usage')}
            with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(json.dumps(row, ensure_ascii=True), flush=True)
        complete = True
    finally:
        stop.set()
        client.close()
        watch.join(timeout=5)
        gpu.stop()
        ram.stop()
        resources = {'variant': variant, 'completed': complete, 'violations': violations,
            'gpu_peak_mib': gpu.peak_mib, 'gpu_telemetry_available': gpu.telemetry_available,
            'ram_peak_mib': ram.peak_mib, 'seconds': round(time.monotonic()-started, 3),
            'manifest_unchanged': sha(manifest) == prereg['manifest_sha256']}
        (out / f'{variant}-resources.json').write_text(json.dumps(resources, indent=2) + '\n', encoding='utf-8')
    assert complete and not violations
assert sha(manifest) == prereg['manifest_sha256']
