"""Exercise the existing full mind decision before forcing a private recall."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'src')]
from scripts.measure_mind_budget import JsonLineProcess, current_core_catalog_snapshot, discover_core

out = root / 'artifacts/comprobaciones/C03/astra-retrieval-startup407'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-retrieval-startup407-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
prior = json.loads((root / 'artifacts/comprobaciones/C03/astra-recall-dialogue371/PREREG.json').read_text(encoding='utf-8'))
cases_path = root / 'scratchpad/c03-account-scope405-cases.json'
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
hook_source = (root / 'scratchpad/c03-owner370-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-memory-product370-private', 'C03-retrieval-startup407-private')
hook_source += '\nfrom baxy_mind import effect_intent\nif os.environ.get(\'BAXY_C03_SCOPE405\') == \'identity-scope\':\n    prior_scope = effect_intent._machine_status_is_the_whole_clause\n    def identity_scope(text):\n        return prior_scope(text) and not effect_intent._has(\n            text, r"\\b(?:cuentas?|usuarios?|accounts?|user(?:name)?s?|identidad|identity)\\b")\n    effect_intent._machine_status_is_the_whole_clause = identity_scope\n'
hook_source += (root / 'scratchpad/c03-observe407-hook.py').read_text(encoding='utf-8')
(hook / 'sitecustomize.py').write_text(hook_source, encoding='utf-8')
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
    'method': 'Same nine fixed cases405, same source397/404 and scope-only diagnostic hook405, same model/catalog/sampler. Read-only startup observers record actual E5 readiness, corpus build and semantic resources. Wait for semantic resources or 195s terminal deadline before deciding the nine cases; no fake readiness, forced tools, descriptor change, effects or promotion. Distinguish cold-start lexical from loaded retrieval behavior.',
    'case_file_sha256': sha(cases_path),
    'reason': '405 audit explicitly records lexical retrieval.406b real CPU E5 loads in20.234s and builds resources in3.547s: accountES rank1 (lexical absent), two username variants still absent. Diagnose actual startup ordering before adopting any source change.',
    'criteria': 'Correct requested operation for all account and resource scopes; conceptual/prohibited requests make no PC reading. Every final decision and all HTTP drafts preserved. No gain counted by merely removing a string or by silence. If native selection still fails, do not hardcode a replacement or adopt on parser tests alone.',
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
for variant in ['identity-scope']:
    env['BAXY_C03_SCOPE405'] = variant
    client = JsonLineProcess([config['python'], '-u', '-X', 'utf8', '-m', 'baxy_mind'], environment=env, cwd=root)
    (out / f'PROCESS-{variant}.json').write_text(json.dumps({'pid': client.pid}) + '\n', encoding='utf-8')
    try:
        hello = client.next_message(90)
        (private / 'hello.json').write_text(json.dumps(hello, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        assert hello.get('type') == 'hello' and 'llm' in (hello.get('models') or {})
        configure = {'id': 'catalog407', 'type': 'catalog.configure', 'capabilities': capabilities}
        if applications is not None:
            configure['applicationCatalog'] = applications
        if games is not None:
            configure['gameCatalog'] = games
        ready = client.request(configure, 90)
        assert ready.get('type') == 'catalog.ready' and ready.get('count') == len(capabilities)
        evidence_status = client.request({'id': 'evidence407-initial', 'type': 'turn.evidence.status'}, 10)
        (out / 'evidence-initial.json').write_text(json.dumps(evidence_status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        wait_start = time.monotonic()
        while time.monotonic() - wait_start < 195:
            telemetry = private / 'startup-observer.jsonl'
            observed = [json.loads(s) for s in telemetry.read_text(encoding='utf-8').splitlines()] if telemetry.exists() else []
            if any(r['event'] == 'resources_built' and r.get('semantic') for r in observed):
                break
            if any(r['event'] in {'router_failed', 'resources_failed'} for r in observed):
                break
            time.sleep(0.25)
        (out / 'wait.json').write_text(json.dumps({'seconds': time.monotonic() - wait_start, 'observed': observed}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        evidence_status = client.request({'id': 'evidence407-after', 'type': 'turn.evidence.status'}, 10)
        (out / 'evidence-after.json').write_text(json.dumps(evidence_status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
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
        client.close(graceful_message={'id': 'close407', 'type': 'shutdown'}, timeout=15)
        (private / f'stderr-tail-{variant}.json').write_text(json.dumps(client._stderr_tail, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert sha(manifest) == prereg['manifest_sha256']
(out / 'EXIT.json').write_text(json.dumps({'completed': True, 'manifest_unchanged': True}) + '\n', encoding='utf-8')
