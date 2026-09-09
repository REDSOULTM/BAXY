"""Locate speaker/addressee errors across native model and conversation layers."""
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
sys.path[:0] = [str(root), str(root / 'src')]
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler
from baxy_mind.llm import LlmRuntime, SYSTEM_PROMPT

base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-native-subject612'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-native-subject612-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

def append(path, value):
    with path.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')

manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
manifest_sha = sha(manifest)
assert manifest_sha == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
config = json.loads(manifest.read_text(encoding='utf-8-sig'))
assert sha(config['gguf']) == '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
history = [{'role':'assistant','content':'¡Hola! ¿Cómo estás?'}]
cases = [
    ('H0012', 'to quien chuta eres.', 'mixed', 'Identify the assistant, not the user.'),
    ('noisy-es', 'che quien carajos sos vos', 'es', 'Identify the assistant, not the user.'),
    ('noisy-en', 'uh who the heck are you', 'en', 'Identify the assistant in English.'),
    ('plain-es', '¿Quién eres tú?', 'es', 'Identify the assistant in Spanish.'),
    ('vocative-es', 'Hola Atlas, ¿cómo estás?', 'es', 'Answer the greeting; Atlas is the addressee, not an introduced user name.'),
    ('vocative-en', 'Hey Morgan, how are you?', 'en', 'Answer the greeting in English; Morgan is the addressee, not an introduced user name.'),
    ('user-name-es', 'Me llamo Vera. ¿Cómo me llamo?', 'es', 'The user is Vera; do not assign the name to the assistant.'),
    ('user-name-en', "My name is Liam. What's my name?", 'en', 'The user is Liam; preserve the named subject and English.'),
]

class Captured(Exception):
    pass

class Builder(LlmRuntime):
    def __init__(self):
        self._gguf = config['gguf']

    def _post(self, payload, **_kwargs):
        self.payload = copy.deepcopy(payload)
        raise Captured()

def builder_payload(text, language, prior):
    client = Builder()
    try:
        client.chat(text, history=prior, temperature=0.0,
                    conversation_kind='knowledge', response_language=language)
    except Captured:
        payload = client.payload
    else:
        raise AssertionError('Expected to capture the first real chat request')
    prefix = []
    for message in payload['messages']:
        if message['role'] != 'system':
            break
        prefix.append(message['content'])
    if len(prefix) > 1:
        payload['messages'] = [{'role':'system','content':'\n\n'.join(prefix)},
                               *payload['messages'][len(prefix):]]
    return payload

panel = []
for case_id, text, language, criterion in cases:
    without_history = builder_payload(text, language, [])
    with_history = builder_payload(text, language, history)
    controls = [
        ('native', [{'role':'user','content':text}]),
        ('identity', [{'role':'system','content':SYSTEM_PROMPT},{'role':'user','content':text}]),
        ('policy', without_history['messages']),
        ('history', with_history['messages']),
        ('greedy', with_history['messages']),
    ]
    for arm, messages in controls:
        payload = {**copy.deepcopy(with_history), 'messages':copy.deepcopy(messages),
                   'max_tokens':512, 'temperature':0.0 if arm == 'greedy' else 0.7,
                   'top_p':0.8, 'top_k':20, 'min_p':0.0, 'seed':0}
        assert 'response_format' not in payload and 'grammar' not in payload
        panel.append({'case_id':case_id,'text':text,'criterion':criterion,'arm':arm,'payload':payload})
write(private / 'panel.json', panel)
command = json.loads((private.parent / 'C03-observe-identity593-private/effective-server-command.json').read_text(encoding='utf-8'))
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0))
    port = sock.getsockname()[1]
command[command.index('--port')+1] = str(port)
command[command.index('--log-file')+1] = str(private / 'server.log')
write(out / 'PREREG.json', {
    'utc':datetime.now(timezone.utc).isoformat(), 'cases':8, 'arms':5, 'calls':40,
    'method':'Native local server only, no turn classifier, retries, prose validators, kernel or UI. Add identity, then conversation/fact/language policies, then the same observed welcome history. Final arm changes only sampling from the documented Qwen2507 profile to greedy. All40 first drafts have512-token headroom and no forced answer JSON; this is not an exact product replay or acceptance campaign.',
    'criteria':'Judge every draft for subject attribution, truthful identity, language, naturalness and finish_reason. Native arm may identify its actual model family; BAXY identity is required once the product identity is supplied. Do not pick one lucky answer or equate removal of a prior error with success. Each subsequent layer is compared with the preceding one; sampling profile is a separate comparison.',
    'inheritance':'593 actual H0012 chat args: temperature0, mixed, welcome history.609 projection rejected after610/611: classification knowledge still produces the wrong subject. Atlas is an independent observed vocative error. Prior language retries594–601 and role-history509/510 remain evidence, not a reason to sweep prompts again.',
    'research_reused':'Official Qwen3-4B-Instruct-2507 card checked2026-09-09: non-thinking, recommended temperature0.7/top_p0.8/top_k20/min_p0. Native template and b9980 preserved.512tokens distinguishes cuts from wrong complete drafts. Earlier508 profiles do not establish optimality for this subject-attribution population. No global model ranking is inferred.',
    'sources':['https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507','https://github.com/ggml-org/llama.cpp/blob/b9980/grammars/README.md'],
    'command':command,'manifest_sha256':manifest_sha,'model_sha256':sha(config['gguf']),
    'server_sha256':sha(command[0]),'source_sha256':sha(root / 'src/baxy_mind/llm.py'),
    'panel_sha256':sha(private / 'panel.json'), 'source_modified':False,
    'limits':{'gpu_mib':3800,'minimum_free_ram_mib':768,'seconds':240},
})
log = (private / 'launch.log').open('w',encoding='utf-8')
process = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
write(out / 'PROCESS.json',{'pid':process.pid})
gpu,ram = ProcessTreeGpuSampler(process.pid),RamSampler(process.pid)
stop = threading.Event()
violations = []
started = time.monotonic()
complete = False

def guard():
    while not stop.wait(.25):
        if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
            violations.append('gpu_bound')
        if psutil.virtual_memory().available < 768*2**20:
            violations.append('free_ram_bound')
        if time.monotonic()-started > 240:
            violations.append('time_bound')
        if violations:
            if process.poll() is None:
                process.terminate()
            return

thread = threading.Thread(target=guard,daemon=True)
url = f'http://127.0.0.1:{port}'
try:
    gpu.start(); ram.start(); thread.start()
    while time.monotonic()-started < 90:
        assert process.poll() is None and not violations
        try:
            with urllib.request.urlopen(url+'/health',timeout=2) as response:
                if json.load(response).get('status') == 'ok':
                    break
        except (urllib.error.URLError,TimeoutError):
            pass
        time.sleep(.25)
    else:
        raise TimeoutError('readiness')
    for row in panel:
        append(private / 'requests.jsonl',row)
        begin = time.monotonic()
        request=urllib.request.Request(url+'/v1/chat/completions',data=json.dumps(row['payload'],ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=30) as response:
            result=json.load(response)
        append(private / 'responses.jsonl',{'case_id':row['case_id'],'arm':row['arm'],'seconds':time.monotonic()-begin,'response':result})
        assert not violations
        print(row['case_id']+' / '+row['arm'],flush=True)
    complete=True
finally:
    stop.set()
    if process.poll() is None:
        process.terminate()
    process.wait(timeout=20)
    thread.join(timeout=5)
    gpu.stop(); ram.stop(); log.close()
    write(out / 'RESOURCES.json',{'complete':complete,'violations':violations,'gpu_peak_mib':gpu.peak_mib,'ram_peak_mib':ram.peak_mib,'seconds':time.monotonic()-started,'manifest_unchanged':sha(manifest)==manifest_sha})
print('Collected40 native subject-attribution drafts; adjudication pending.',flush=True)
