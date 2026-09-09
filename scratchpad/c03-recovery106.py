"""Revalidate inherited R07 failures/restoration with the current local candidate."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

out = ROOT / 'artifacts/comprobaciones/C03/astra-recovery106'
out.mkdir(exist_ok=False)
prior = json.loads((ROOT / 'artifacts/comprobaciones/C03/astra-ui104/PREREG.json').read_text(encoding='utf-8'))
registration = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

assert sha(registration) == prior['registrationSha256']
assert sha(prior['model']) == prior['modelSha256']
old_commands = [json.loads(line) for line in (ROOT / 'artifacts/comprobaciones/C03/astra-routes-regression46.turns.jsonl').open(encoding='utf-8')]
first = next(i for i, command in enumerate(old_commands) if command['cmd'] == 'inject')
commands = old_commands[first:]
assert len(commands) == 12
profile = Path(os.environ['LOCALAPPDATA']) / 'BAXY/comprobaciones-c03-recovery106'
assert not profile.exists()
prereg = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'method': 'Same twelve inherited R07 commands (six turns) as tranche46: reject, '
        'timeout and exhaust, each restored and followed by the same normal request '
        'in one process/profile/session. Current source103/Qwen3.5 override, no new '
        'prompts, fake drafts or wire hook. Product conductor, no UI/audio acceptance '
        'or human reserve. Expect honest failure state and useful post-restore answers; '
        'injected failures do not count as normal turns. Host initializes and checks '
        'readiness before reading commands; no additional fixed warmup delay.',
    'commands': commands, 'profile': str(profile), 'model': prior['model'],
    'modelSha256': prior['modelSha256'], 'registrationSha256': prior['registrationSha256'],
    'files': {p: sha(ROOT / p) for p in [
        'src/baxy_mind/llm.py', 'src/baxy_mind/__main__.py',
        'src/Baxy.App/ProductConductorHost.cs', 'src/Baxy.App/MainWindowViewModel.cs',
        'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll',
        'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/baxy-core.exe',
        'scratchpad/c03-recovery106.py']}}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
env = os.environ.copy()
for name in list(env):
    if name.startswith(('BAXY_MIND_', 'BAXY_VOICE_', 'BAXY_C03_', 'BAXY_FIELD_')) or name in {'BAXY_ASSET_DESCRIPTOR', 'PYTHONPATH'}:
        env.pop(name, None)
env.update(BAXY_MIND_LLM_GGUF=prior['model'], BAXY_VOICE_WAKE_ON_START='0',
    BAXY_APP_TRACE=str(out / 'shell-trace.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(out / 'compose-audit.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
    BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(out / 'raw-replies.jsonl'))
app = ROOT / 'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe'
gpu, ram = ProcessTreeGpuSampler(os.getpid()), RamSampler(os.getpid())
gpu.start(); ram.start()
process = None
stop = None
started = time.monotonic()
try:
    with (out / 'conductor.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(app), '--conductor', '--profile=' + str(profile),
            '--timeout-ms=120000', '--capture=' + str(out)], cwd=ROOT, env=env,
            stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        (out / 'PROCESS.json').write_text(json.dumps({'monitor': os.getpid(), 'launcher': process.pid}), encoding='utf-8')
        process.stdin.write(('\n'.join(json.dumps(c, ensure_ascii=False) for c in commands) + '\n').encode('utf-8'))
        process.stdin.close()
        while process.poll() is None:
            if gpu.peak_mib is not None and gpu.peak_mib > 4096:
                stop = 'attributed_gpu_exceeds_4096_mib'; break
            if time.monotonic() - started > 600:
                stop = 'diagnostic_deadline_600s'; break
            time.sleep(0.5)
finally:
    if process is not None and process.poll() is None:
        owned = psutil.Process(process.pid)
        for child in reversed(owned.children(recursive=True)):
            try: child.terminate()
            except psutil.NoSuchProcess: pass
        process.terminate(); process.wait(timeout=10)
    gpu.stop(); ram.stop()
    result = {'exitCode': process.returncode if process else None, 'stopReason': stop,
        'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
        'gpuAttributionAvailable': gpu.telemetry_available, 'ramPeakMiB': ram.peak_mib,
        'registrationUnchanged': sha(registration) == prior['registrationSha256']}
    (out / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
