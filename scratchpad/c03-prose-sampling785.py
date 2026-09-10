"""Paired50-case first-draft sampler diagnostic; immutable product,150calls."""
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler
from baxy_mind.llm import LlmRuntime, _compose_situation_payload

BASE = ROOT / 'artifacts/comprobaciones/C03'
SOURCE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-status-batch772-private'
PRIVATE = SOURCE.parent / 'C03-prose-sampling785-private'
OUT = BASE / 'PROSE_SAMPLING785'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not OUT.exists() and not PRIVATE.exists()
assert not any((p.info['name'] or '').lower() in {'llama-server.exe', 'baxy.exe', 'baxy-core.exe', 'testhost.exe'}
               for p in psutil.process_iter(['name']))
assert psutil.virtual_memory().available >= 2700 * 2**20
prior = read(BASE / 'STATUS_BATCH772/PREREG.json')
assert sha(prior['model']['path']) == prior['model']['sha256']
assert sha(prior['backend']['path']) == prior['backend']['sha256']
source_pins = {**read(BASE / 'NAMED_CLOCK783/PUBLICATION_SOURCE_PINS.json'),
               **read(BASE / 'DENSE_INVENTORY764/SOURCE_PINS.json')}
assert all(sha(ROOT / p) == h for p,h in source_pins.items())
panel = []
for case_id in ['H0023', 'H0103', 'H0539', 'H0655', 'H0508', 'clock-variant779-31']:
    private_source = (SOURCE.parent / 'C03-status-batch782-private' if case_id.startswith('clock-') else SOURCE)
    case = next(r for r in read(private_source / 'review.json') if r['case_id'] == case_id)
    draft = next(d for d in case['compose'] if d.get('stage') == 'first' and isinstance(d.get('payload'), dict))
    raw = draft['situation']
    reconstructed = False
    try:
        situation = json.loads(raw) if isinstance(raw, str) else copy.deepcopy(raw)
    except json.JSONDecodeError:
        observed = copy.deepcopy(draft['payload']['seen'])
        observed.pop('returnedPageScope', None)
        situation = {'kind':'operation','operation':'window.resolve','polarity':'success',
                     'verified':True,'succeeded':True,'observed':observed}
        reconstructed = True
    projected = _compose_situation_payload(situation, 'es', case['text'])
    assert projected == draft['payload'], (case_id, projected, draft['payload'])
    panel.append({'id':case_id, 'origin':'historical development', 'source':str(private_source / 'review.json'),
                  'request':case['text'], 'situation':situation, 'criterion':case['criterion'],
                  'projected_facts':projected, 'reconstructed_envelope':reconstructed})

layouts = [(0,0,True),(2,7,True),(7,7,True),(12,20,True),(20,25,True),(20,25,False)]
for layout, (count,total,complete) in enumerate(layouts):
    for lang, question in enumerate(['Lista las ventanas.', 'Dime qué ventanas tengo abiertas.',
                                     'List all open windows.', 'Mostrame my open windows.']):
        windows = [{'title':f'Órbita {layout}-{index % 5}', 'processName':f'Viewer{index % 3}',
                    'windowId':f'synthetic_{index}', 'foreground':index == 0,
                    'x':0,'y':0,'width':600,'height':400,'state':'normal'} for index in range(count)]
        situation = {'kind':'operation','operation':'window.resolve','polarity':'success','verified':True,'succeeded':True,
            'observed':{'windows':windows,'count':count,'observedCount':total,'offset':0,'limit':50,
                'complete':complete,'totalCount':total if complete else None,'hasMore':count < total,
                'nextOffset':count if count < total else None,'observationScope':'visible_top_level_windows',
                'pageConsistency':'fresh_enumeration_per_request'}}
        panel.append({'id':f'inventory785-{layout+1}-{lang+1}', 'origin':'declared synthetic inventory',
            'request':question, 'situation':situation,
            'criterion':'Every returned title/process identity and its exact multiplicity; faithful known/unknown total and page scope. No invented opening chronology or process state. A grouped answer may preserve exact multiplicity; vague several or omitted instances fails.'})
for index,(installed,total,available) in enumerate([
    (8_000_000_000,7_600_000_000,1_200_000_000), (16_000_000_000,15_800_000_000,4_500_000_000),
    (32_000_000_000,31_600_000_000,0), (8_000_000_000,7_800_000_000,7_800_000_000),
    (None,12_000_000_000,3_500_000_000),
]):
    for variant,question in enumerate(['¿Cuánta RAM tengo?', '¿Cuánta RAM queda disponible ahora?',
                                     'How much usable RAM does this computer have?', 'Tell me the available memory, por favor.']):
        situation={'kind':'operation','operation':'system.status','polarity':'success','verified':True,'succeeded':True,
                   'observed':{'memory':{'totalBytes':total,'availableBytes':available,'installedBytes':installed}}}
        panel.append({'id':f'memory785-{index+1}-{variant+1}','origin':'declared synthetic memory',
            'request':question,'situation':situation,
            'criterion':'Answer the requested installed/usable/available quantity with correct value, unit and subject. Unknown installed capacity cannot be invented; usable may be reported as such. Decimal GB and binary GiB accepted when accurate. No usable-to-available substitution.'})
assert len(panel) == 50 and len({c['id'] for c in panel}) == 50

class Captured(BaseException):
    pass

class Capture(LlmRuntime):
    def __init__(self):
        self._gguf = prior['model']['path']
        self.payload = None
    def _post(self,payload):
        self.payload = copy.deepcopy(payload)
        raise Captured()

planned=[]
for index,case in enumerate(panel):
    capture=Capture()
    try:
        capture.compose_user_message(case['request'],'status',{'situation':case['situation']})
    except Captured:
        pass
    baseline=capture.payload
    assert baseline and baseline['temperature']==0 and baseline['max_tokens']==256
    assert baseline.get('cache_prompt') is False
    variants=[]
    for arm,seed in [('A_registered_greedy',None),('B_qwen_recommended_seed0',0),('C_qwen_recommended_seed17',17)]:
        payload=copy.deepcopy(baseline)
        if seed is not None:
            payload.update(temperature=0.7,top_p=0.8,top_k=20,min_p=0.0,presence_penalty=0.0,repeat_penalty=1.0,seed=seed)
        assert payload['messages']==baseline['messages'] and payload['max_tokens']==baseline['max_tokens']
        variants.append({'arm':arm,'case_id':case['id'],'payload':payload})
    # Rotate all three arms to avoid assigning one profile a constant position.
    shift=index % 3
    planned.extend(variants[shift:]+variants[:shift])
command=next(p['command'] for p in read(SOURCE/'processes.json').values() if p['name'].lower()=='llama-server.exe')
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
command[command.index('--port')+1]=str(port)
OUT.mkdir();PRIVATE.mkdir()
write(PRIVATE/'cases.json',panel);write(PRIVATE/'planned.json',planned)
plan={'utc':datetime.now(timezone.utc).isoformat(),'calls':len(planned),'cases':len(panel),'command':command,
    'model':prior['model'],'backend':prior['backend'],'source_pins':source_pins,'driver_sha256':sha(__file__),
    'planned_sha256':sha(PRIVATE/'planned.json'),'cases_sha256':sha(PRIVATE/'cases.json'),
    'intervention':'Same first-draft BAXY messages and256-token cap; sampler profile only. A currentT0 versus officialQwen0.7/p0.8/k20/minp0 at seeds0 and17. Greedy keeps original omitted sampler fields; recommended profile explicitly sets neutral penalties.',
    'reference':'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507#best-practices',
    'reference_checked':'2026-09-10; official card suggestsT0.7,p0.8,k20,minp0. Its16384-output reference is not this controlled256-token task-budget probe; native699 remains separate.',
    'inheritance':'579 tested only CPU actor repair;759/770/772 show inventory regressions. No measured first-draft inventory/RAM recipe comparison found in those exact sources.',
    'limits':{'observe_seconds_per_call':15,'max_tokens_unchanged':256,'gpu_stop_mib':3800,'free_ram_min_mib':768,'wall_seconds':900},
    'criterion':'Adjudicate full raw answer against each frozen request/observation, including multiplicity and measurement semantics. Keep cuts/errors and faithful answers rejected by BAXY separate. No best-seed cherry-picking; two sampled passes cannot establish general stability.',
    'scope':'First-draft sampler diagnostic, not model ranking, native baseline, full retry/product/UI/voice/reserve acceptance or automatic survey credit. All user data stays local.',
    'environment_defaults':{'OMP_NUM_THREADS':'4','MKL_NUM_THREADS':'4','TOKENIZERS_PARALLELISM':'false'}}
write(OUT/'PREREG.json',plan)
stop = threading.Event()
violations, results = [], []
process = gpu = ram = watcher = None
started = time.monotonic()


def guard():
    while not stop.wait(.25):
        if (gpu.peak_mib or 0) >= 3800:
            violations.append('owned_gpu_bound')
        if psutil.virtual_memory().available < 768 * 2**20:
            violations.append('free_ram_bound')
        if time.monotonic() - started > 900:
            violations.append('diagnostic_wall_bound')
        if violations:
            if process.poll() is None:
                process.terminate()
            return


try:
    env = os.environ.copy()
    for name,value in plan['environment_defaults'].items():
        env[name] = value
    with (PRIVATE / 'server.log').open('w', encoding='utf-8') as log:
        runtime = read(PRIVATE.parent.parent / 'BAXYRuntime/mind-runtime-v1.json')
        process = subprocess.Popen(command, cwd=Path(runtime['python']).parent, env=env,
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    write(OUT / 'PROCESS.json', {'runner_pid': os.getpid(), 'server_pid': process.pid})
    gpu, ram = ProcessTreeGpuSampler(process.pid), RamSampler(process.pid)
    gpu.start(); ram.start()
    watcher = threading.Thread(target=guard, daemon=True)
    watcher.start()
    endpoint = f'http://127.0.0.1:{port}'
    while time.monotonic() - started < 90:
        assert process.poll() is None
        try:
            with urllib.request.urlopen(endpoint + '/health', timeout=1) as response:
                if json.load(response).get('status') == 'ok':
                    break
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(.25)
    else:
        raise TimeoutError('backend startup')
    try:
        with urllib.request.urlopen(endpoint + '/props', timeout=2) as response:
            write(PRIVATE / 'server-props.json', json.load(response))
    except (urllib.error.URLError, TimeoutError) as error:
        write(PRIVATE / 'server-props.json', {'unavailable': str(error)})
    slots_available = True
    for row in planned:
        assert not violations, violations
        before = time.monotonic()
        outcome = {'arm': row['arm'], 'case_id': row['case_id']}
        request = urllib.request.Request(endpoint + '/v1/chat/completions',
            data=json.dumps(row['payload']).encode('utf-8'), headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                outcome['response'] = json.load(response)
        except Exception as error:
            outcome.update(error=type(error).__name__, detail=str(error))
        outcome['seconds'] = time.monotonic() - before
        if slots_available:
            try:
                with urllib.request.urlopen(endpoint + '/slots', timeout=2) as response:
                    outcome['slots_after'] = json.load(response)
            except (urllib.error.URLError, TimeoutError) as error:
                outcome['slots_telemetry_unavailable'] = str(error)
                slots_available = False
        results.append(outcome)
        write(PRIVATE / 'results.json', results)
        if len(results) % 10 == 0:
            print(json.dumps({'completed': len(results), 'planned': len(planned)}), flush=True)
finally:
    stop.set()
    if process is not None:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=20)
    if watcher is not None:
        watcher.join(timeout=3)
    if gpu is not None:
        gpu.stop(); ram.stop()
    write(OUT / 'RESULT.json', {'calls_completed': len(results), 'calls_planned': len(planned),
        'seconds': time.monotonic() - started, 'gpu_peak_mib': gpu.peak_mib if gpu else None,
        'ram_peak_mib': ram.peak_mib if ram else None, 'violations': violations,
        'driver_unchanged': sha(__file__) == plan['driver_sha256'],
        'sources_unchanged': all(sha(ROOT / p) == h for p,h in source_pins.items()),
        'quality_adjudicated': False, 'scope': plan['scope']})
