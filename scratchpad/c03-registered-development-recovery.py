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

out = ROOT / 'artifacts/comprobaciones/C03/astra-registered-development-recovery-qwen'
model = Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf')
manifest_path = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
def sha(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
files = ['tests/data/turn_evidence_runtime.v1.jsonl', 'src/baxy_mind/data/turn_evidence_abstention_policy.v1.json', 'src/baxy_mind/planner.py', 'src/Baxy.Providers.Windows/Windows/WindowsWindowControlProvider.cs', 'src/Baxy.Providers.Windows/Windows/WindowControlContracts.cs', 'src/Baxy.Core/Operations/WindowControlHandlers.cs', 'src/Baxy.Kernel/Operations/ProductCatalog.cs', 'src/Baxy.Core/bin/Release/net10.0-windows10.0.19041.0/win-x64/publish/baxy-core.exe', 'src/baxy_mind/llm.py', 'src/baxy_mind/__main__.py',
         'src/baxy_mind/request_reading.py', 'src/baxy_mind/effect_intent.py', 'src/Baxy.App/PendingModelMessageQueue.cs', 'src/Baxy.App/MindSidecarClient.cs',
         'src/Baxy.App/MainWindowViewModel.cs', 'src/Baxy.App/MissionNarration.cs', 'src/Baxy.App/MindPlanSession.cs', 'src/Baxy.App/UserMessagePolicy.cs',
         'artifacts/comprobaciones/C03/astra-registered-development-recovery-qwen.turns.jsonl',
         'scratchpad/c03-registered-development-recovery.py']
manifest_hash = sha(manifest_path)
assert not (out/'PREREG.json').exists()
prereg={'kind':'qwen-base-integrated-diagnostic-not-acceptance','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'method':'Registered Qwen runtime with no model/KV/PythonPath/sampling overrides or sitecustomize instrumentation. Existing 21 consumed development requests, then separate reject/timeout/exhaust injections each followed by restore and a normal request in the SAME process/profile/session. Recovery requests do not count as normal acceptance. Existing own empty window fixture; no user windows are closed. Conductor inherently disables wake; this run cannot prove simultaneous voice budget or graphical UI.',
 'registrationSha256':manifest_hash,'model':str(model),'modelSha256':sha(model),'files':{name:sha(ROOT/name) for name in files}}
(out/'PREREG.json').write_text(json.dumps(prereg,indent=2),encoding='utf-8')
env = os.environ.copy()
for name in list(env):
    if name.startswith(('BAXY_MIND_', 'BAXY_VOICE_', 'BAXY_C03_', 'BAXY_FIELD_')) or name in {'BAXY_ASSET_DESCRIPTOR', 'PYTHONPATH'}:
        env.pop(name,None)
env.update(BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(out/'compose-audit.jsonl'),
           BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
           BAXY_MIND_TURN_AUDIT_PATH=str(out/'turn-audit.jsonl'),
           BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(out/'raw-replies.jsonl'),
           BAXY_APP_TRACE=str(out/'shell-trace.jsonl'))
app=ROOT/'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe'
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
command=[str(app),'--conductor','--profile='+str(Path(env['LOCALAPPDATA'])/'BAXY/comprobaciones-c03-registered-development-recovery-qwen'), '--timeout-ms=120000','--commit='+commit,'--capture='+str(out)]
prereg['preparation']='Hold stdin for 50 seconds to allow normal warmup, no readiness instrumentation or runtime overrides. Warm development and recovery, not cold-start latency or fresh acceptance.'
(out/'PREREG.json').write_text(json.dumps(prereg,indent=2),encoding='utf-8')
released=False
import win32gui
assert not win32gui.FindWindow(None, "Ventana C03 de prueba"), "Existing fixture title must be inspected, not reused blindly"
fixture=subprocess.Popen([str(ROOT/'scratchpad/C03TitleFixture.exe')],cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
(out/'FIXTURE.json').write_text(json.dumps({'pid':fixture.pid,'path':str(ROOT/'scratchpad/C03TitleFixture.exe'),'sha256':sha(ROOT/'scratchpad/C03TitleFixture.exe')}),encoding='utf-8')
time.sleep(1)
assert fixture.poll() is None


gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
process = None
stopped = None
started = time.monotonic()
try:
    with (out/'conductor.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'PROCESS.json').write_text(json.dumps({'monitor': os.getpid(), 'launcher': process.pid}), encoding='utf-8')
        while process.poll() is None:
            if not released:
                ready_components = set()
                if time.monotonic()-started > 50:
                    commands=(ROOT/'artifacts/comprobaciones/C03/astra-registered-development-recovery-qwen.turns.jsonl').read_bytes()
                    process.stdin.write(commands); process.stdin.close(); released=True
                    (out/'COMMAND_RELEASE.json').write_text(json.dumps({'seconds':time.monotonic()-started, 'readyComponents':sorted(ready_components)}),encoding='utf-8')
            if gpu.peak_mib is not None and gpu.peak_mib > 4096:
                stopped = 'attributed_gpu_exceeds_4096_mib'; break
            if time.monotonic()-started > 900:
                stopped = 'diagnostic_deadline_900s'; break
            time.sleep(1)
finally:
    if process is not None and process.poll() is None:
        # Only descendants of the launcher created above are stopped.
        owned = psutil.Process(process.pid)
        children = owned.children(recursive=True)
        for child in reversed(children):
            try: child.terminate()
            except psutil.NoSuchProcess: pass
        process.terminate()
        process.wait(timeout=10)
    fixture_closed_by_product = fixture.poll() is not None
    fixture_cleanup_needed = not fixture_closed_by_product
    if fixture_cleanup_needed:
        fixture.terminate(); fixture.wait(timeout=10)
    gpu.stop(); ram.stop()
    result = {'exitCode': process.returncode if process else None, 'fixtureClosedBeforeCleanup': fixture_closed_by_product, 'fixtureCleanupNeeded': fixture_cleanup_needed, 'stopReason': stopped,
              'elapsedSeconds': round(time.monotonic()-started, 2),
              'gpuPeakMiB': gpu.peak_mib, 'gpuAttributionAvailable': gpu.telemetry_available,
              'ramPeakMiB': ram.peak_mib, 'registrationUnchanged': sha(manifest_path)==manifest_hash}
    (out/'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
