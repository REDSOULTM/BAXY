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

out = root / 'artifacts/comprobaciones/C03/astra-recall-policy376'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-recall-policy376-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
prior = json.loads((root / 'artifacts/comprobaciones/C03/astra-recall-dialogue371/PREREG.json').read_text(encoding='utf-8'))
cases = [{key: case[key] for key in ['id', 'request', 'history', 'expected']} for case in prior['cases']]
cases[2]['expected'] = 'Do not call the user Morgan. A targeted question or memory.recall proposal is legitimate when no human name is supplied; Windows account is not the requested personal identity.'
cases[4]['expected'] = 'Propose memory.recall for the explicitly stored name; do not claim a saved value from conversational context.'
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
hook_source = (root / 'scratchpad/c03-owner370-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-memory-product370-private', 'C03-recall-policy376-private')
hook_source += '\n# Diagnostic only: retain private operation descriptors for turn selection.\n# There is no plan or operation execution in this process.\nimport inspect\nimport textwrap\nfrom baxy_mind import planner as _planner\n_constructor_source = textwrap.dedent(inspect.getsource(_planner.PlannerCatalog.__init__))\n_exclusion = \'            or name.startswith("memory.")\\n\'\nassert _constructor_source.count(_exclusion) == 1\n_constructor_source = _constructor_source.replace(_exclusion, \'\', 1)\n_patched = {}\nexec(_constructor_source, _planner.__dict__, _patched)\n_planner.PlannerCatalog.__init__ = _patched[\'__init__\']\n'
(hook / 'sitecustomize.py').write_text(hook_source, encoding='utf-8')
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
    'method': 'Same five development inputs/history371 through actual sidecar turn.decide with authenticated current Core catalog. Core starts only for its read-only catalog hello, no operation request. Mind can propose actions but this diagnostic never executes them. Same five cases and source374 as375. Sole diagnostic change: the sidecar hook removes the PlannerCatalog constructor exclusion of memory.*; all descriptors still come from the current authenticated Core catalog. Only turn.decide is exercised; no plan request or operation is executed. No production source, private dispatch/parser or confirmation change, runtime promotion, fresh human acceptance, UI or voice.',
    'reason': 'PlannerCatalog.__init__:302 explicitly discards all memory.* although Core exposes11 private operations. The planning catalog is reused by the turn selector;375 explicit persistence receives a shortlist with no memory tool and falsely denies capability. This probe isolates descriptor visibility before choosing an implementation. The private planning boundary remains required: Kernel MissionPlanProposal69 and App PlannerExecutionSupport295/321 reject unsealed private steps. Do not turn this hook into a blanket production removal. Generic personal questions are forced by the private parser to memory.recall before the mind sees them. Test the earlier decision owner; preserve private sealing and exact confirmation before any future source adoption.',
    'criteria': 'Answer available session names from the actual human statement. Do not use third-party names, assistant errors, or Windows identity. Explicit persistence needs a verified private operation, never a claim based on conversation. Record every final decision and HTTP request to locate any later override. This probe only establishes mind behavior; it does not by itself justify removing private parser or changing effect authority.',
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
client = JsonLineProcess([config['python'], '-u', '-X', 'utf8', '-m', 'baxy_mind'], environment=env, cwd=root)
(out / 'PROCESS.json').write_text(json.dumps({'pid': client.pid}) + '\n', encoding='utf-8')
try:
    hello = client.next_message(90)
    (private / 'hello.json').write_text(json.dumps(hello, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert hello.get('type') == 'hello' and 'llm' in (hello.get('models') or {})
    configure = {'id': 'catalog376', 'type': 'catalog.configure', 'capabilities': capabilities}
    if applications is not None:
        configure['applicationCatalog'] = applications
    if games is not None:
        configure['gameCatalog'] = games
    ready = client.request(configure, 90)
    assert ready.get('type') == 'catalog.ready' and ready.get('count') == len(capabilities)
    for case in cases:
        start = time.monotonic()
        request = {'id': case['id'], 'type': 'turn.decide', 'text': case['request'], 'history': case['history'], 'pendingClarification': False, 'uiLanguage': 'es'}
        reply = client.request(request, 60)
        result = {'id': case['id'], 'seconds': round(time.monotonic() - start, 3), 'reply': reply}
        with (out / 'replies.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + '\n')
        print(json.dumps(result, ensure_ascii=True), flush=True)
finally:
    client.close(graceful_message={'id': 'close376', 'type': 'shutdown'}, timeout=15)
    (private / 'stderr-tail.json').write_text(json.dumps(client._stderr_tail, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert sha(manifest) == prereg['manifest_sha256']
(out / 'EXIT.json').write_text(json.dumps({'completed': True, 'manifest_unchanged': True}) + '\n', encoding='utf-8')
