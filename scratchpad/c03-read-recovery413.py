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

out = root / 'artifacts/comprobaciones/C03/astra-read-recovery413'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-read-recovery413-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
prior = json.loads((root / 'artifacts/comprobaciones/C03/astra-recall-dialogue371/PREREG.json').read_text(encoding='utf-8'))
cases_path = Path('C:\\Users\\usuario\\AppData\\Local\\BAXY\\C03-read-recovery413-cases-private\\cases.json')
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
hook_source = (root / 'scratchpad/c03-owner370-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-memory-product370-private', 'C03-read-recovery413-private')
hook_source += (root / 'scratchpad/c03-observe407-hook.py').read_text(encoding='utf-8').replace("Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-retrieval-startup407-private/startup-observer.jsonl'", "Path(os.environ['BAXY_C03_STARTUP_AUDIT'])")
hook_source += (root / 'scratchpad/c03-early-read413-hook.py').read_text(encoding='utf-8')
(hook / 'sitecustomize.py').write_text(hook_source, encoding='utf-8')
reference_path = cases_path.with_name('reference411.json')
reference = json.loads(reference_path.read_text(encoding='utf-8'))
prereg = {'reference411_sha256': sha(reference_path), 'utc': datetime.now(timezone.utc).isoformat(), 'case_ids': [c['id'] for c in cases], 'private_case_file': str(cases_path),
    'method': 'Fourteen fixed development cases: actual411T3 with exact native411 history including its initial welcome plus13controls409. Source410 and current authenticated catalog, same model/template/sampler, two sequential sidecars: actual411T3 first immediately after catalog.ready, then the14cases after semantic readiness (15requests per arm). Audit must confirm lexical mode for the initial target before attributing its comparison to the real411 boundary. Unlike412, assert byte-value equality of the first cold primary payload with411 for both arms before continuing. Diagnostic-only variant runs a second existing native decision over the first4 offered candidates when the primary is knowledge/social without effects, and retains it only if all proposed operations have authenticated read_only risk. The normal information/domain/compound/action/grounding/confirmation guards still run. No injected answers, fixed identity operation, effect execution, source change or promotion. Original late fallback remains in this diagnostic; successful adoption must move the existing repair rather than add duplicate passes.',
    'case_file_sha256': sha(cases_path),
    'reason': '411T3 native primary recites account from prior prose; actual existing later AUTO picks identity. observation_not_recital unconditionally asks permission for that already requested read. Test whether preserving a native read proposal before ordinary guards avoids the extra clarification. The earlier rejected expansion for unsupported turns is excluded; only knowledge/social with catalog candidates. Native tool mechanics/one-sided veto research already documented.',
    'criteria': 'Actual repeat-account read becomes identity; all four account controls and three resource controls remain correct; concept/prohibition and four names remain useful no-effect. No write operation is promoted by the diagnostic. Compare drafts/final/stages, latency and native-call count. This is full mind without effects, not acceptance or UI.',
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
for variant in ['baseline', 'early-read']:
    env['BAXY_C03_EARLY_READ412'] = variant
    env['BAXY_C03_STARTUP_AUDIT'] = str(private / f'startup-{variant}.jsonl')
    current_capabilities = copy.deepcopy(capabilities)
    (private / f'catalog-{variant}.json').write_text(json.dumps(current_capabilities, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    client = JsonLineProcess([config['python'], '-u', '-X', 'utf8', '-m', 'baxy_mind'], environment=env, cwd=root)
    (out / f'PROCESS-{variant}.json').write_text(json.dumps({'pid': client.pid}) + '\n', encoding='utf-8')
    try:
        hello = client.next_message(90)
        (private / f'hello-{variant}.json').write_text(json.dumps(hello, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        assert hello.get('type') == 'hello' and 'llm' in (hello.get('models') or {})
        configure = {'id': 'catalog413', 'type': 'catalog.configure', 'capabilities': current_capabilities}
        if applications is not None:
            configure['applicationCatalog'] = applications
        if games is not None:
            configure['gameCatalog'] = games
        ready = client.request(configure, 90)
        assert ready.get('type') == 'catalog.ready' and ready.get('count') == len(capabilities)
        cold_case = cases[0]
        started_cold = time.monotonic()
        cold_reply = client.request({'id': cold_case['id'] + '-cold', 'type': 'turn.decide', 'text': cold_case['request'], 'history': cold_case['history'], 'pendingClarification': False, 'uiLanguage': 'es'}, 60)
        cold_result = {'id': cold_case['id'], 'phase': 'cold', 'variant': variant, 'seconds': round(time.monotonic() - started_cold, 3), 'reply': cold_reply}
        with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(cold_result, ensure_ascii=False) + '\n')
        print(json.dumps(cold_result, ensure_ascii=True), flush=True)
        cold_primary = next(row['payload'] for line in (private / 'http-posts.jsonl').open(encoding='utf-8-sig')
                            if (row := json.loads(line)).get('stage') == 'request'
                            and len(row['payload'].get('tools', [])) == 28
                            and row['payload']['messages'][-1].get('content') == cold_case['request'])
        exact = cold_primary == reference
        (out / f'payload-match-{variant}.json').write_text(json.dumps({'equal_to411': exact, 'reference_sha256': sha(reference_path)}, indent=2) + '\n', encoding='utf-8')
        assert exact, 'cold primary does not reproduce411 payload; stop before claiming a repair'
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
            result = {'id': case['id'], 'phase': 'warm', 'variant': variant, 'seconds': round(time.monotonic() - start, 3), 'reply': reply}
            with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(result, ensure_ascii=False) + '\n')
            print(json.dumps(result, ensure_ascii=True), flush=True)
    finally:
        client.close(graceful_message={'id': 'close413', 'type': 'shutdown'}, timeout=15)
        (private / f'stderr-tail-{variant}.json').write_text(json.dumps(client._stderr_tail, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert sha(manifest) == prereg['manifest_sha256']
(out / 'EXIT.json').write_text(json.dumps({'completed': True, 'manifest_unchanged': True}) + '\n', encoding='utf-8')
