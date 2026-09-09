"""Measure the existing contextual responder on the actual owner319 dialogue."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
import psutil

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from baxy_mind import llm

out = root / 'artifacts/comprobaciones/C03/astra-context320'
out.mkdir(exist_ok=False)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-memory-product319-private'
events = [json.loads(line) for line in (private / 'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
posts = [json.loads(line) for line in (private / 'http-posts.jsonl').read_text(encoding='utf-8').splitlines()]
welcome = next(row['response']['choices'][0]['message']['content'] for row in posts if row['stage'] == 'response')
history = [{'role': 'assistant', 'content': welcome}]
cases = []
for row in events:
    if row['type'] != 'event' or row['event']['type'] != 'activity':
        continue
    entry = row['event']['entry']
    message = {'role': 'user' if entry['src'] == 'YOU' else 'assistant', 'content': entry['msg']}
    if entry['src'] == 'YOU' and entry['msg'] in ['Yo soy el', 'quien soy', 'nono, te pregunte quien soy yo, no tu, dime quien eres tu y quien soy yo']:
        cases.append({'request': entry['msg'], 'history': copy.deepcopy(history)})
    history.append(message)
transcript = json.loads((private.parent / 'C03-owner264-heap280/TRANSCRIPT282.json').read_text(encoding='utf-8'))
cases.append({'request': transcript[110]['body'], 'history': copy.deepcopy(history), 'new_topic_control': True})

model = Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf')
binary = Path('D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe')
assert not any(process.info['name'] == 'llama-server.exe' for process in psutil.process_iter(['name']))
args = [str(binary), '-m', str(model), '--host', '127.0.0.1', '--port', '57485',
    '-ngl', '99', '-c', '12288', '-b', '2048', '-ub', '256', '-fa', 'on',
    '-ctk', 'q8_0', '-ctv', 'q8_0', '-np', '3', '--jinja', '--reasoning', 'off',
    '--reasoning-budget', '0', '--cont-batching']
with model.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
assert digest == '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
(out / 'PREREG.json').write_text(json.dumps({
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Use existing LlmRuntime._resolve_contextual_answer, no new prompt or grammar, on actual319 user/assistant dialogue. Three identity/reference requests plus the next actual owner110 HDMI/VGA new-topic control. This changes the presentation path as a diagnostic, not production selection/authorization. Same registered model/backend/KV profile, standalone hidden server, no desktop UI or effects. Native replies319 remain baseline.',
    'criteria': 'Recognize Emmanuel from the supplied user turn, distinguish BAXY and person, keep the new topic free of name/memory contamination. Preserve pending failures and no unverified memory claim. Existing resolver can be considered only after contextual and new-topic regression; no adoption on one phrase.',
    'modelSha256': digest, 'args': args, 'cases': cases,
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

tree = ast.parse((root / 'scratchpad/c03-account-subject303.py').read_text(encoding='utf-8'))
adapter = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Runtime')
source = ast.unparse(adapter).replace('58916', '57485')
exec(compile(source, '<inherited-transport303>', 'exec'))
log = (out / 'server.log').open('wb')
process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
(out / 'PROCESS.json').write_text(json.dumps({'pid': process.pid, 'createTime': psutil.Process(process.pid).create_time()}) + '\n', encoding='utf-8')
results = []
try:
    deadline = time.monotonic() + 75
    while True:
        assert process.poll() is None
        try:
            with urllib.request.urlopen('http://127.0.0.1:57485/health', timeout=1) as response:
                if response.status == 200:
                    break
        except Exception:
            if time.monotonic() > deadline:
                raise TimeoutError('Server readiness')
            time.sleep(.25)
    for case in cases:
        runtime = Runtime()
        started = time.monotonic()
        result = {'request': case['request']}
        try:
            result['answer'] = runtime._resolve_contextual_answer(history=case['history'], current=case['request'])
        except Exception as error:
            result['error'] = repr(error)
        result['seconds'] = round(time.monotonic() - started, 3)
        result['posts'] = runtime.posts
        results.append(result)
        (out / 'RESULT.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({key: value for key, value in result.items() if key != 'posts'}, ensure_ascii=True), flush=True)
finally:
    process.terminate()
    process.wait(timeout=10)
    log.close()
    (out / 'STOP.json').write_text(json.dumps({'pid': process.pid, 'exit': process.returncode}) + '\n', encoding='utf-8')
