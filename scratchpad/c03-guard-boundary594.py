"""Paired native classifier probe: missing effect arguments vs noisy conversation."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
import psutil

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-guard-boundary594'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-guard-boundary594-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
previous = private.parent / 'C03-observe-identity593-private'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def append(path, value):
    with path.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')


capture = [json.loads(line) for line in (previous / 'http-posts.jsonl').read_text(encoding='utf-8').splitlines()]
original = next(row['payload'] for row in capture if row['stage'] == 'request' and row['id'] == 3)
old = 'incomplete_effect si sólo hay una referencia o falta un objetivo o valor humano esencial para external_read o environment_change.'
new = ('incomplete_effect sólo cuando se solicita una lectura externa o un cambio y falta '
       'su objetivo, referencia o valor esencial. Una pregunta sobre la identidad del '
       'asistente, una explicación o una reacción siguen siendo stable_conversation, '
       'aunque incluyan muletillas, insultos, errores de escritura o un fragmento ambiguo; '
       'eso por sí solo no implica una acción pendiente.')
assert original['messages'][0]['content'].count(old) == 1
candidate = original['messages'][0]['content'].replace(old, new)
cases = [
    ('H0012', 'to quien chuta eres.', 'stable_conversation'),
    ('identity-noisy-es', 'che quien carajos sos vos', 'stable_conversation'),
    ('identity-noisy-en', 'uh who the heck are you', 'stable_conversation'),
    ('identity-mixed', 'oye, who are you pues', 'stable_conversation'),
    ('identity-discourse', 'a ver, dime quién eres tú', 'stable_conversation'),
    ('knowledge-discourse', 'bueno eh qué es la fotosíntesis', 'stable_conversation'),
    ('reaction', 'Me alegro de verte.', 'stable_conversation'),
    ('negative-constraint', 'No abras ninguna ventana.', 'stable_conversation'),
    ('missing-app', 'Abre una aplicación.', 'incomplete_effect'),
    ('missing-value', 'Pon el volumen a...', 'incomplete_effect'),
    ('missing-reference-en', 'Please send it.', 'incomplete_effect'),
    ('live-app', '¿Está Spotify abierto?', 'external_read'),
    ('live-cpu-en', "What is my computer's CPU usage?", 'external_read'),
    ('external-effect', 'Compra dos entradas para el cine.', 'environment_change'),
    ('physical-effect', 'Regá las plantas.', 'environment_change'),
    ('multiple-effects', 'Abre Steam y sube el volumen al 40%.', 'environment_change'),
]
write(private / 'panel.json', cases)
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
manifest_sha = sha(manifest)
assert manifest_sha == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
command = json.loads((previous / 'effective-server-command.json').read_text(encoding='utf-8'))
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
command[command.index('--port') + 1] = str(port)
command[command.index('--log-file') + 1] = str(private / 'server.log')
assert sha(command[command.index('-m') + 1]) == '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(), 'cases': len(cases), 'arms': 2,
    'method': 'Exact native grammar/sampling/template593, paired original vs replacing only incomplete-effect definition.16 preregistered cases, first owner literal and15 development contrasts. Alternate arm order. No classifier bypass, output rewriting, effects, model or registration change.',
    'hypothesis': 'Ambiguous wording classifies conversational noise as an incomplete effect. Require an actual request for external reading/change before missing arguments can imply incomplete_effect.',
    'criteria': 'Every response must finish normally and match its preregistered request_type. Stable conversation must count zero; two requested effects must count multiple. No adoption from fixing H0012 while losing real effects. Final product and more generalization remain mandatory.',
    'inheritance': 'Observed593, apply_conversation_effect_presentation; tests/test_turn_policy.py one-sided guard. Source512 fact-role history retained. Historical minimum-live-safe audit distinguishes turn classification and effect authority; no legacy allowlist restored.',
    'sources_checked_20260909': ['https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507', 'https://github.com/ggml-org/llama.cpp/blob/b9980/grammars/README.md'],
    'profile_rationale': 'Keep the deployed greedy grammar classifier to isolate prompt semantics, not rank Qwen globally; official general sampling already measured508, same exact revision. Grammar constrains output syntax, not semantic correctness.',
    'old_definition': old, 'candidate_definition': new, 'command': command,
    'model_sha256': sha(command[command.index('-m') + 1]), 'server_sha256': sha(command[0]),
    'capture_sha256': sha(previous / 'http-posts.jsonl'), 'panel_sha256': sha(private / 'panel.json'),
    'manifest_sha256': manifest_sha, 'limits': {'gpu_mib': 3800, 'free_ram_mib': 768, 'seconds': 240},
})
log = (private / 'launch.log').open('w', encoding='utf-8')
process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
write(out / 'PROCESS.json', {'pid': process.pid})
gpu, ram = ProcessTreeGpuSampler(process.pid), RamSampler(process.pid)
stop = threading.Event()
violations = []
started = time.monotonic()
complete = False


def guard():
    while not stop.wait(.25):
        if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
            violations.append('gpu_bound')
        if psutil.virtual_memory().available < 768 * 2**20:
            violations.append('free_ram_bound')
        if time.monotonic() - started > 240:
            violations.append('wall_time_bound')
        if violations:
            if process.poll() is None:
                process.terminate()
            return


guard_thread = threading.Thread(target=guard, daemon=True)
url = f'http://127.0.0.1:{port}'
try:
    gpu.start()
    ram.start()
    guard_thread.start()
    while time.monotonic() - started < 90:
        assert process.poll() is None and not violations
        try:
            with urllib.request.urlopen(url + '/health', timeout=2) as response:
                if json.load(response).get('status') == 'ok':
                    break
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(.25)
    else:
        raise TimeoutError('readiness')
    for index, (case_id, text, expected) in enumerate(cases):
        arms = ['original', 'candidate'] if index % 2 == 0 else ['candidate', 'original']
        for arm in arms:
            payload = copy.deepcopy(original)
            payload['messages'][-1]['content'] = 'Mensaje actual:\n' + text
            if arm == 'candidate':
                payload['messages'][0]['content'] = candidate
            append(private / 'requests.jsonl', {'case_id': case_id, 'arm': arm, 'payload': payload})
            begin = time.monotonic()
            request = urllib.request.Request(url + '/v1/chat/completions', data=json.dumps(payload, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
            append(private / 'responses.jsonl', {'case_id': case_id, 'arm': arm, 'expected': expected, 'seconds': time.monotonic() - begin, 'response': result})
            assert not violations
        print('Collected ' + case_id, flush=True)
    complete = True
finally:
    stop.set()
    if process.poll() is None:
        process.terminate()
    process.wait(timeout=20)
    guard_thread.join(timeout=5)
    gpu.stop()
    ram.stop()
    log.close()
    write(out / 'RESOURCES.json', {'complete': complete, 'violations': violations, 'gpu_peak_mib': gpu.peak_mib, 'ram_peak_mib': ram.peak_mib, 'seconds': time.monotonic() - started, 'manifest_unchanged': sha(manifest) == manifest_sha})
print('32 native classifications collected; adjudication pending.', flush=True)
