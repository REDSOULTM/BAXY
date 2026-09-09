"""Exercise the existing full mind decision before forcing a private recall."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import copy
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'src')]
from scripts.measure_mind_budget import JsonLineProcess, current_core_catalog_snapshot, discover_core

out = root / 'artifacts/comprobaciones/C03/astra-descriptor-mind409'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-descriptor-mind409-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
prior = json.loads((root / 'artifacts/comprobaciones/C03/astra-recall-dialogue371/PREREG.json').read_text(encoding='utf-8'))
cases_path = root / 'scratchpad/c03-descriptor-mind409-cases.json'
cases = json.loads(cases_path.read_text(encoding='utf-8'))['cases']
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
model = Path(prior['model'])
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
assert sha(model) == prior['model_sha256']
capabilities, applications, games = current_core_catalog_snapshot(discover_core(None))
(private / 'catalog.json').write_text(json.dumps({'capabilities': capabilities, 'applicationCatalog': applications, 'gameCatalog': games}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
hook = private / 'hook'
hook.mkdir()
hook_source = (root / 'scratchpad/c03-owner370-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-memory-product370-private', 'C03-descriptor-mind409-private')
hook_source += '\nfrom baxy_mind import effect_intent\nif os.environ.get(\'BAXY_C03_SCOPE405\') == \'identity-scope\':\n    prior_scope = effect_intent._machine_status_is_the_whole_clause\n    def identity_scope(text):\n        return prior_scope(text) and not effect_intent._has(\n            text, r"\\b(?:cuentas?|usuarios?|accounts?|user(?:name)?s?|identidad|identity)\\b")\n    effect_intent._machine_status_is_the_whole_clause = identity_scope\n'
hook_source += (root / 'scratchpad/c03-observe407-hook.py').read_text(encoding='utf-8').replace("Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-retrieval-startup407-private/startup-observer.jsonl'", "Path(os.environ['BAXY_C03_STARTUP_AUDIT'])")
(hook / 'sitecustomize.py').write_text(hook_source, encoding='utf-8')
replacement = json.loads((root / 'artifacts/comprobaciones/C03/astra-identity-scope387/PREREG.json').read_text(encoding='utf-8'))['new_description']
prereg = {'new_description': replacement, 'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
    'method': 'Thirteen fixed synthetic development cases: nine405 plus four personal-name controls403. Two sequential full sidecars with the same scope-abstention405 in both, same model/history/sampler. Only system.identity description differs (exact387). Both wait for their own observed semantic resources. No effects, source edit, forced operation, response injection, model promotion or fresh-human acceptance. Cold usernameEN remains a separately known concern from408; this run tests loaded E5.',
    'case_file_sha256': sha(cases_path),
    'reason': '408 demonstrates descriptor improves four account targets from2/4 to4/4 visible.407 full warm mind is7/9. Compare actual decisions, while retaining four name-context controls to detect account/personal-name confusion. Existing primary native-tool and E5 mechanism research applies.',
    'criteria': 'All four account reads select identity, three resource reads select status, concept/prohibition and four current-name questions remain no-effect and useful; inspect every draft and audit. No gain credited for false refusal, silence, wrong subject, false persistence or mere visibility.',
    'model': str(model), 'model_sha256': sha(model), 'manifest_sha256': sha(manifest), 'backend_sha256': sha(config['llama_server']),
    'catalog_count': len(capabilities), 'catalog_sha256': sha(private / 'catalog.json'),
    'private': str(private)}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
env = os.environ.copy()
for key in list(env):
    if key.startswith(('BAXY_MIND_', 'BAXY_VOICE_', 'BAXY_C03_')) or key in {'PYTHONPATH', 'BAXY_DATA_DIR'}:
        env.pop(key)
env.update(PYTHONPATH=str(hook) + os.pathsep + str(root / 'src'), PYTHONUTF8='1', HF_HUB_OFFLINE='1',
    BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_NGL=str(config['ngl']),
    BAXY_MIND_TURN_AUDIT_PATH=str(private / 'turn-audit.jsonl'), BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(private / 'raw-replies.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private / 'compose-audit.jsonl'), BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
    BAXY_VOICE_WAKE_ON_START='0')
for variant in ['baseline', 'descriptor']:
    env['BAXY_C03_SCOPE405'] = 'identity-scope'
    env['BAXY_C03_STARTUP_AUDIT'] = str(private / f'startup-{variant}.jsonl')
    current_capabilities = copy.deepcopy(capabilities)
    if variant == 'descriptor':
        next(c for c in current_capabilities if c['name'] == 'system.identity')['description'] = replacement
    (private / f'catalog-{variant}.json').write_text(json.dumps(current_capabilities, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    client = JsonLineProcess([config['python'], '-u', '-X', 'utf8', '-m', 'baxy_mind'], environment=env, cwd=root)
    (out / f'PROCESS-{variant}.json').write_text(json.dumps({'pid': client.pid}) + '\n', encoding='utf-8')
    try:
        hello = client.next_message(90)
        (private / f'hello-{variant}.json').write_text(json.dumps(hello, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        assert hello.get('type') == 'hello' and 'llm' in (hello.get('models') or {})
        configure = {'id': 'catalog409', 'type': 'catalog.configure', 'capabilities': current_capabilities}
        if applications is not None:
            configure['applicationCatalog'] = applications
        if games is not None:
            configure['gameCatalog'] = games
        ready = client.request(configure, 90)
        assert ready.get('type') == 'catalog.ready' and ready.get('count') == len(capabilities)
        evidence_status = client.request({'id': 'evidence407-initial', 'type': 'turn.evidence.status'}, 10)
        (out / f'evidence-initial-{variant}.json').write_text(json.dumps(evidence_status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        wait_start = time.monotonic()
        while time.monotonic() - wait_start < 195:
            telemetry = private / f'startup-{variant}.jsonl'
            observed = [json.loads(s) for s in telemetry.read_text(encoding='utf-8').splitlines()] if telemetry.exists() else []
            if any(r['event'] == 'resources_built' and r.get('semantic') for r in observed):
                break
            if any(r['event'] in {'router_failed', 'resources_failed'} for r in observed):
                break
            time.sleep(0.25)
        (out / f'wait-{variant}.json').write_text(json.dumps({'seconds': time.monotonic() - wait_start, 'observed': observed}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        evidence_status = client.request({'id': 'evidence407-after', 'type': 'turn.evidence.status'}, 10)
        (out / f'evidence-after-{variant}.json').write_text(json.dumps(evidence_status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'startup_wait_seconds': round(time.monotonic() - wait_start, 3), 'events': observed}), flush=True)
        for case in cases:
            start = time.monotonic()
            request = {'id': case['id'], 'type': 'turn.decide', 'text': case['request'], 'history': case['history'], 'pendingClarification': False, 'uiLanguage': 'es'}
            reply = client.request(request, 60)
            result = {'id': case['id'], 'variant': variant, 'seconds': round(time.monotonic() - start, 3), 'reply': reply}
            with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(result, ensure_ascii=False) + '\n')
            print(json.dumps(result, ensure_ascii=True), flush=True)
    finally:
        client.close(graceful_message={'id': 'close409', 'type': 'shutdown'}, timeout=15)
        (private / f'stderr-tail-{variant}.json').write_text(json.dumps(client._stderr_tail, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert sha(manifest) == prereg['manifest_sha256']
(out / 'EXIT.json').write_text(json.dumps({'completed': True, 'manifest_unchanged': True}) + '\n', encoding='utf-8')
