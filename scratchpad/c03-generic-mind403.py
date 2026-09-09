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

out = root / 'artifacts/comprobaciones/C03/astra-generic-mind403'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-generic-mind403-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
prior = json.loads((root / 'artifacts/comprobaciones/C03/astra-recall-dialogue371/PREREG.json').read_text(encoding='utf-8'))
cases_path = root / 'scratchpad/c03-generic-mind403-cases.json'
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
hook_source = (root / 'scratchpad/c03-owner370-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-memory-product370-private', 'C03-generic-mind403-private')
(hook / 'sitecustomize.py').write_text(hook_source, encoding='utf-8')
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
    'method': 'Six fixed development cases through actual full mind source397, with source395 retry retention. Exact402bT6 activity-derived last12 messages including current user request, plus EN, new name, two explicit Windows accounts and a third-party control. Compare actual private-parser402bT6 storedJordan against the existing mind with current dialogue. No new prompt/guard/role/answer injection, operation execution or product source change. This measures whether generic conversational recall can use current dialogue before deciding any App dispatch repair; not fresh acceptance, UI or voice.',
    'case_file_sha256': sha(cases_path),
    'reason': '402bT6 is intercepted by unconditional generic name memory.recall, discarding current human Alvaro in favor of storedJordan.398 with earlier history could answerAlvaro, but402b has different actual replies. Measure this route on the new exact history before changing the dispatch. Explicit stored queries and Windows reads must retain their own owners; no global name cache or reuse of rejected contextual resolver392.',
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
    configure = {'id': 'catalog403', 'type': 'catalog.configure', 'capabilities': capabilities}
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
    client.close(graceful_message={'id': 'close403', 'type': 'shutdown'}, timeout=15)
    (private / 'stderr-tail.json').write_text(json.dumps(client._stderr_tail, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert sha(manifest) == prereg['manifest_sha256']
(out / 'EXIT.json').write_text(json.dumps({'completed': True, 'manifest_unchanged': True}) + '\n', encoding='utf-8')
