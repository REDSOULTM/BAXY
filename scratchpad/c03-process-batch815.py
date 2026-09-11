"""Frozen 50-case process-read category through the registered product with process narrator814, pending its owners and Fast guards.

Inherits conductor and resource observation mechanics from private-product521.
Narrator814 removes the obligation to recite both cardinalities in the existing
ranking/list paragraph; counts and facts812 are preserved, with no new layer.
No prompt/sampler adapters, no survey credit, no native model comparison.
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

OUT = ROOT / 'artifacts/comprobaciones/C03/PROCESS_BATCH815'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-process-batch815-private'
PROFILE = PRIVATE.parent / 'C03-process-profile815'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    Path(path).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def utc():
    return datetime.now(timezone.utc).isoformat()


assert not any(path.exists() for path in (OUT, PRIVATE, PROFILE))
assert psutil.virtual_memory().available >= 4000 * 2**20, 'preflight free RAM'
busy = [p.info for p in psutil.process_iter(['pid', 'name', 'cmdline'])
        if (p.info['name'] or '').lower() in {'llama-server.exe', 'baxy.exe', 'baxy-core.exe', 'testhost.exe'}
        or any('pytest' in part for part in p.info['cmdline'] or [])]
assert not busy, f'preflight concurrent product/test processes: {busy}'
panel_path = PRIVATE.parent / 'C03-process-panel795-private/panel.json'
plan_path = ROOT / 'artifacts/comprobaciones/C03/PROCESS_CATEGORY795_PLAN.json'
plan = read(plan_path)
# Full804 is the baseline for cumulative Python802 plus C#804, not Full814.
# Python-only narrator814 requires its own owners and Fast before product measurement.
validation_root = ROOT / 'artifacts/comprobaciones/C03/PROCESS_NARRATOR814'
assert read(validation_root / 'VALIDATION_EXIT.json')['exit_code'] == 0
assert read(validation_root / 'VALIDATION_EXIT.json')['source_pins_unchanged'] is True
assert sha(validation_root / 'SOURCE_PINS.json') == read(validation_root / 'VALIDATION_EXIT.json')['source_pins_sha256']
assert read(validation_root / 'OWNERS_PYTHON_EXIT.json')['exit_code'] == 0
baseline_validation_root = ROOT / 'artifacts/comprobaciones/C03/PROCESS_DEADLINE804'
full_validation_root = baseline_validation_root / 'FULL_RETRY1'
assert read(full_validation_root / 'FULL_EXIT.json')['exit_code'] == 0
assert read(full_validation_root / 'FULL_EXIT.json')['source_pins_unchanged'] is True
assert sha(baseline_validation_root / 'SOURCE_PINS.json') == read(full_validation_root / 'FULL_EXIT.json')['source_pins_sha256']
assert sha(panel_path) == plan['panel_sha256']
original = read(ROOT / 'artifacts/comprobaciones/C03/PROCESS_BATCH803/PREREG.json')
assert sha(panel_path) == original['panel_sha256']
assert sha(plan_path) == original['plan_sha256']
panel = read(panel_path)
assert len(panel) == 50 and len({c['case_id'] for c in panel}) == 50
manifest = PRIVATE.parent.parent / 'BAXYRuntime/mind-runtime-v1.json'
config = read(manifest)
assert sha(manifest) == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
model = Path(config['gguf'])
assert sha(model) == '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
pins814 = read(validation_root / 'SOURCE_PINS.json')
assert len(pins814) == 31, 'narrator814 source pin set'
assert all(sha(ROOT / path) == digest for path, digest in pins814.items())
# Use the launcher build path before sealing. This does not start BAXY.
preparation = subprocess.run([sys.executable, '-X', 'utf8', '-c',
    'import main; main.compile_if_needed(force=False)'], cwd=ROOT,
    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NO_WINDOW, check=True)
assert all(sha(ROOT / path) == digest for path, digest in pins814.items())
shutdown = subprocess.run([str(Path.home() / '.dotnet/dotnet.exe'), 'build-server', 'shutdown',
                           '--msbuild', '--vbcscompiler'], cwd=ROOT,
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          creationflags=subprocess.CREATE_NO_WINDOW, check=True)
assert psutil.virtual_memory().available >= 4000 * 2**20, 'post-build free RAM'

paths = subprocess.check_output(
    ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', 'src', 'scripts', 'main.py'],
    cwd=ROOT, text=True, encoding='utf-8').splitlines()
sources = {name: sha(ROOT / name) for name in sorted(set(paths)) if (ROOT / name).is_file()}
app = ROOT / 'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll'
app_sha = sha(app)
OUT.mkdir()
PRIVATE.mkdir()
(PRIVATE / 'build-preparation.log').write_bytes(preparation.stdout)
(PRIVATE / 'build-servers-shutdown.log').write_bytes(shutdown.stdout)
(PRIVATE / 'panel.json').write_bytes(panel_path.read_bytes())
turns = PRIVATE / 'turns.jsonl'
turns.write_text(''.join(json.dumps({'cmd': 'turn', 'text': row['text']}, ensure_ascii=False) + '\n'
                         for row in panel), encoding='utf-8')
env = os.environ.copy()
for name in list(env):
    if name.startswith(('BAXY_MIND_', 'BAXY_VOICE_', 'BAXY_C03_', 'BAXY_FIELD_')) or name in {
        'PYTHONPATH', 'BAXY_DATA_DIR', 'BAXY_ASSET_DESCRIPTOR', 'BAXY_APP_TRACE'}:
        env.pop(name, None)
env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'],
           BAXY_MIND_PYTHONPATH=str(ROOT / 'src'), BAXY_VOICE_WAKE_ON_START='0',
           BAXY_APP_TRACE=str(PRIVATE / 'shell-trace.jsonl'),
           BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(PRIVATE / 'compose-audit.jsonl'),
           BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
           BAXY_MIND_TURN_AUDIT_PATH=str(PRIVATE / 'turn-audit.jsonl'),
           BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(PRIVATE / 'raw-replies.jsonl'))
command = [sys.executable, 'main.py', '--conductor', '--profile', str(PROFILE), '--capture',
           str(PRIVATE / 'capture'), '--turns-file', str(turns), '--timeout-ms', '120000']
prereg = {
    'utc': utc(), 'method': 'Registered50 process-read category with sealed candidate814; nine historical requests and41 variants. Build prepared before sealing DLL; model selection is closed.',
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'private': str(PRIVATE), 'panel_sha256': sha(panel_path), 'turns_sha256': sha(turns),
    'plan_sha256': sha(plan_path), 'cases': [{'case_id': c['case_id'], 'group': c['group']} for c in panel],
    'criteria': plan['criteria'], 'coverage_rule': plan['coverage_rule'],
    'effect_scope': plan['effect_scope'], 'profile': 'Fresh isolated private conductor profile, wake disabled.',
    'validation': 'Full804 retry1 exit0 is the baseline for Python802 plus C#804, verified against SOURCE_PINS804; this is not Full814. PROCESS_NARRATOR814 owners and Fast exit0 are required before launch. Original Full804 seal failure preserved. New real product confirmation; final cumulative Full/adoption remains governed by the goal. No native model comparison or automated coverage credit.',
    'validation_path': str(validation_root / 'VALIDATION_EXIT.json'),
    'validation_sha256': sha(validation_root / 'VALIDATION_EXIT.json'),
    'owners_python_path': str(validation_root / 'OWNERS_PYTHON_EXIT.json'),
    'owners_python_sha256': sha(validation_root / 'OWNERS_PYTHON_EXIT.json'),
    'source814_pins_sha256': sha(validation_root / 'SOURCE_PINS.json'),
    'full_baseline_source_pins_path': str(baseline_validation_root / 'SOURCE_PINS.json'),
    'full_baseline_source_pins_sha256': sha(baseline_validation_root / 'SOURCE_PINS.json'),
    'full_validation_path': str(full_validation_root / 'FULL_EXIT.json'),
    'full_validation_sha256': sha(full_validation_root / 'FULL_EXIT.json'),
    'source814_pins': pins814, 'sources': sources, 'runner_sha256': sha(__file__),
    'manifest_sha256': sha(manifest), 'model': {'path': str(model), 'sha256': sha(model)},
    'backend': {'path': config['llama_server'], 'sha256': sha(config['llama_server'])},
    'build_preparation_sha256': sha(PRIVATE / 'build-preparation.log'), 'build_prepared_before_seal': True,
    'app_dll_sha256': app_sha, 'sampler_or_prompt_overrides': [],
    'limits': {'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768, 'wall_seconds': 900,
               'per_turn_timeout_ms': 120000, 'inherited': 'Registered category runner772, original per-turn budget retained'},
    'survey_counts_before': {'covered': 28, 'open': 714, 'not_applicable': 0},
}
write(OUT / 'PREREG.json', prereg)
stop = threading.Event()
violations, processes = [], {}
started = time.monotonic()
with (PRIVATE / 'launch.log').open('w', encoding='utf-8') as log:
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                               stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    write(OUT / 'PROCESS.json', {'utc': utc(), 'launcher': process.pid, 'runner': os.getpid(), 'command': command})
    print(json.dumps({'started': True, 'launcher': process.pid, 'registered_turns': 50}), flush=True)
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
           'source814_unchanged': all(sha(ROOT / path) == digest for path, digest in pins814.items()),
           'runner_unchanged': sha(__file__) == prereg['runner_sha256'],
           'app_dll_unchanged': sha(app) == app_sha, 'quality_adjudicated': False}
write(OUT / 'EXIT.json', outcome)
print(json.dumps(outcome), flush=True)
raise SystemExit(code)
