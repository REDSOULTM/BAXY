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

out = root / 'artifacts/comprobaciones/C03/astra-recall-policy382'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-recall-policy382-private'
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
hook_source = (root / 'scratchpad/c03-owner370-hook/sitecustomize.py').read_text(encoding='utf-8').replace('C03-memory-product370-private', 'C03-recall-policy382-private')
hook_source += '\n' + (root / 'scratchpad/c03-native-reply382-hook.py').read_text(encoding='utf-8')
(hook / 'sitecustomize.py').write_text(hook_source, encoding='utf-8')
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
    'method': 'Same five development inputs/history371 through actual sidecar turn.decide with authenticated current Core catalog. Core starts only for its read-only catalog hello, no operation request. Mind can propose actions but this diagnostic never executes them. Same five cases and authenticated catalog as375, now source379. Follow-up382 restricts forwarding to the native response made inside the primary decide_turn, never the secondary catalogue probe. Match the current request ignoring only surrounding question punctuation; the original turn request still reaches every chat guard. This models returning a draft alongside the primary decision without runtime cross-request caching. Sole diagnostic replacement: when a native selection has actually returned text with no calls, finished stop, same exact current request, and the final decision remains knowledge with no authenticated operations, pass that actual native response into the existing chat guards instead of issuing its first redundant completion. The hook records every forwarded response and replaced chat payload; all retries/final checks remain production. No invented response, prompt change, effect, or source adoption. Other cases still run normal chat. No private dispatch/parser change, runtime promotion, fresh human acceptance, UI or voice.',
    'reason': '375 HTTP5 answers Te llamas Álvaro; later HTTP6 rewrites it with a false private-memory limitation. Native Qwen3.5 template itself tells the model to answer normally when no function is needed; BAXY currently discards that content. Official template bbaaae1, inspected2026-09-08, https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/chat_template.jinja and backend https://github.com/ggml-org/llama.cpp/blob/b9980/docs/function-calling.md. This diagnostic tests the consequence of retaining the actual upstream answer before any architecture adoption. Private visibility376 remains rejected3/5; do not remove the memory planning boundary. Error history371/372 unchanged and rejected. Generic personal questions are forced by the private parser to memory.recall before the mind sees them. Test the earlier decision owner; preserve private sealing and exact confirmation before any future source adoption.',
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
    configure = {'id': 'catalog382', 'type': 'catalog.configure', 'capabilities': capabilities}
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
    client.close(graceful_message={'id': 'close375', 'type': 'shutdown'}, timeout=15)
    (private / 'stderr-tail.json').write_text(json.dumps(client._stderr_tail, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert sha(manifest) == prereg['manifest_sha256']
(out / 'EXIT.json').write_text(json.dumps({'completed': True, 'manifest_unchanged': True}) + '\n', encoding='utf-8')
