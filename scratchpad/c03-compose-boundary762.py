"""Single inventory compose diagnostic through the registered product.

Inherits conductor and resource observation mechanics from private-product521.
Passive compose/HTTP observer; no prompt/sampler adapter or survey/model credit.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import threading
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

OUT = ROOT / 'artifacts/comprobaciones/C03/COMPOSE_BOUNDARY762'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-compose762-private'
PROFILE = PRIVATE.parent / 'C03-compose-profile762'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def utc():
    return datetime.now(timezone.utc).isoformat()


assert not any(path.exists() for path in (OUT, PRIVATE, PROFILE))
assert psutil.virtual_memory().available >= 2700 * 2**20, 'preflight free RAM'
busy = [p.info for p in psutil.process_iter(['pid', 'name', 'cmdline'])
        if (p.info['name'] or '').lower() in {'llama-server.exe', 'baxy.exe', 'baxy-core.exe', 'testhost.exe'}
        or any('pytest' in part for part in p.info['cmdline'] or [])]
assert not busy, f'preflight concurrent product/test processes: {busy}'
panel_path = PRIVATE.parent / 'C03-status-batch729-private/panel.json'
plan_path = ROOT / 'artifacts/comprobaciones/C03/STATUS_BATCH689_PLAN.json'
plan = read(plan_path)
assert sha(panel_path) == plan['panel_sha256']
panel = read(panel_path)
assert len(panel) == 73 and len({c['case_id'] for c in panel}) == 73
source_panel_sha = sha(panel_path)
panel = [row for row in panel if row['case_id'] == 'H0023']
assert len(panel) == 1
manifest = PRIVATE.parent.parent / 'BAXYRuntime/mind-runtime-v1.json'
config = read(manifest)
assert sha(manifest) == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
model = Path(config['gguf'])
assert sha(model) == '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
pins760 = read(ROOT / 'artifacts/comprobaciones/C03/SEMANTIC_INVENTORY760/SOURCE_PINS.json')
assert all(sha(ROOT / path) == digest for path, digest in pins760.items())
paths = subprocess.check_output(
    ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', 'src', 'scripts', 'main.py'],
    cwd=ROOT, text=True, encoding='utf-8').splitlines()
sources = {name: sha(ROOT / name) for name in sorted(set(paths)) if (ROOT / name).is_file()}
app = ROOT / 'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll'
app_sha = sha(app)
OUT.mkdir()
PRIVATE.mkdir()
write(PRIVATE / 'panel.json', panel)
import importlib.util
observer_check = ROOT / 'scratchpad/c03-observer-preflight762.py'
check_spec = importlib.util.spec_from_file_location('observer_preflight762', observer_check)
check_module = importlib.util.module_from_spec(check_spec)
check_spec.loader.exec_module(check_module)
observer = ROOT / 'scratchpad/c03-compose762-hook/sitecustomize.py'
write(OUT / 'OBSERVER_PREFLIGHT.json', check_module.verify_hook(observer, PRIVATE))
turns = PRIVATE / 'turns.jsonl'
turns.write_text(''.join(json.dumps({'cmd': 'turn', 'text': row['text']}, ensure_ascii=False) + '\n'
                         for row in panel), encoding='utf-8')
env = os.environ.copy()
for name in list(env):
    if name.startswith(('BAXY_MIND_', 'BAXY_VOICE_', 'BAXY_C03_', 'BAXY_FIELD_')) or name in {
        'PYTHONPATH', 'BAXY_DATA_DIR', 'BAXY_ASSET_DESCRIPTOR', 'BAXY_APP_TRACE'}:
        env.pop(name, None)
env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'],
           BAXY_MIND_PYTHONPATH=str(observer.parent) + os.pathsep + str(ROOT / 'src'), BAXY_VOICE_WAKE_ON_START='0',
           BAXY_APP_TRACE=str(PRIVATE / 'shell-trace.jsonl'),
           BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(PRIVATE / 'compose-audit.jsonl'),
           BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
           BAXY_MIND_TURN_AUDIT_PATH=str(PRIVATE / 'turn-audit.jsonl'),
           BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(PRIVATE / 'raw-replies.jsonl'))
command = ['py', 'main.py', '--conductor', '--profile', str(PROFILE), '--capture',
           str(PRIVATE / 'capture'), '--turns-file', str(turns), '--timeout-ms', '120000']
prereg = {
    'utc': utc(), 'method': 'Reproduce H0023 inventory composition failure with passive boundary observer; one diagnostic turn, no scoring/coverage/model comparison.',
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'private': str(PRIVATE), 'panel_sha256': sha(PRIVATE / 'panel.json'), 'source_panel_sha256': source_panel_sha, 'turns_sha256': sha(turns),
    'plan_sha256': sha(plan_path), 'cases': [{'case_id': c['case_id'], 'group': c['group']} for c in panel],
    'criteria': plan['criteria'], 'coverage_rule': plan['coverage_rule'],
    'effect_scope': plan['effect_scope'], 'profile': 'Fresh isolated private conductor profile, wake disabled.',
    'validation': 'Published760 owner tests, current pins and Fast; no source edits after760; Full7 historical.',
    'source760_pins': pins760, 'sources': sources, 'runner_sha256': sha(__file__),
    'manifest_sha256': sha(manifest), 'model': {'path': str(model), 'sha256': sha(model)},
    'backend': {'path': config['llama_server'], 'sha256': sha(config['llama_server'])},
    'app_dll_sha256': app_sha, 'sampler_or_prompt_overrides': [], 'observer_sha256': sha(observer), 'observer_preflight_sha256': sha(observer_check),
    'limits': {'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768, 'wall_seconds': 900,
               'per_turn_timeout_ms': 120000, 'inherited': '73-case registered category runner694'},
    'survey_counts_before': {'covered': 26, 'open': 716, 'not_applicable': 0},
}
write(OUT / 'PREREG.json', prereg)
stop = threading.Event()
violations, processes = [], {}
started = time.monotonic()
with (PRIVATE / 'launch.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                               stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    write(OUT / 'PROCESS.json', {'utc': utc(), 'launcher': process.pid, 'runner': os.getpid(), 'command': command})
    print(json.dumps({'started': True, 'launcher': process.pid, 'registered_turns': 1}), flush=True)
    gpu, ram = ProcessTreeGpuSampler(process.pid), RamSampler(process.pid)

    def guard_resources():
        with (PRIVATE / 'memory-samples.jsonl').open('w', encoding='utf-8') as samples:
            while not stop.wait(0.25):
                rows = []
                try:
                    parent = psutil.Process(process.pid)
                    for child in [parent, *parent.children(recursive=True)]:
                        try:
                            key = str(child.pid)
                            if key not in processes:
                                processes[key] = {'pid': child.pid, 'parent': child.ppid(),
                                                  'name': child.name(), 'command': child.cmdline()}
                            info = child.memory_info()
                            rows.append({'pid': child.pid, 'rss_mib': info.rss / 2**20,
                                         'private_mib': getattr(info, 'private', 0) / 2**20})
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                except psutil.NoSuchProcess:
                    pass
                elapsed = time.monotonic() - started
                available = psutil.virtual_memory().available / 2**20
                samples.write(json.dumps({'elapsed': round(elapsed, 3), 'available_mib': available,
                                          'processes': rows}) + '\n')
                if elapsed > 900:
                    violations.append('scenario_wall_time_bound')
                if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
                    violations.append('owned_gpu_bound')
                if available < 768:
                    violations.append('system_free_ram_bound')
                if violations:
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW, check=False)
                    return

    guard = threading.Thread(target=guard_resources, daemon=True)
    try:
        gpu.start()
        ram.start()
        guard.start()
        code = process.wait()
    finally:
        stop.set()
        guard.join(timeout=5)
        gpu.stop()
        ram.stop()
        write(PRIVATE / 'processes.json', processes)
        write(OUT / 'RESOURCES.json', {'utc': utc(), 'violations': violations,
              'gpu_peak_mib': gpu.peak_mib, 'gpu_telemetry_available': gpu.telemetry_available,
              'ram_peak_mib': ram.peak_mib, 'seconds': round(time.monotonic() - started, 3),
              'scope': 'Owned conductor product process tree; no voice or visible desktop UI credit.'})
outcome = {'utc': utc(), 'exit_code': code, 'manifest_unchanged': sha(manifest) == prereg['manifest_sha256'],
           'sources_unchanged': all(sha(ROOT / path) == digest for path, digest in sources.items()),
           'source760_unchanged': all(sha(ROOT / path) == digest for path, digest in pins760.items()),
           'runner_unchanged': sha(__file__) == prereg['runner_sha256'],
           'observer_unchanged': sha(observer) == prereg['observer_sha256'],
           'app_dll_unchanged': sha(app) == app_sha, 'quality_adjudicated': False}
write(OUT / 'EXIT.json', outcome)
print(json.dumps(outcome), flush=True)
raise SystemExit(code)
