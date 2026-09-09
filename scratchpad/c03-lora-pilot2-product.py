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

out = ROOT / 'artifacts/comprobaciones/C03/astra-lora-pilot2-product'
model = Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf')
manifest_path = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
def sha(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
files = ['tests/data/turn_evidence_runtime.v1.jsonl', 'src/baxy_mind/data/turn_evidence_abstention_policy.v1.json', 'src/baxy_mind/planner.py', 'src/Baxy.Providers.Windows/Windows/WindowsWindowControlProvider.cs', 'src/Baxy.Providers.Windows/Windows/WindowControlContracts.cs', 'src/Baxy.Core/Operations/WindowControlHandlers.cs', 'src/Baxy.Kernel/Operations/ProductCatalog.cs', 'src/Baxy.Core/bin/Release/net10.0-windows10.0.19041.0/win-x64/publish/baxy-core.exe', 'src/baxy_mind/llm.py', 'src/baxy_mind/__main__.py',
         'src/baxy_mind/request_reading.py', 'src/baxy_mind/effect_intent.py', 'src/Baxy.App/PendingModelMessageQueue.cs', 'src/Baxy.App/MindSidecarClient.cs',
         'src/Baxy.App/MainWindowViewModel.cs', 'src/Baxy.App/MissionNarration.cs', 'src/Baxy.App/MindPlanSession.cs', 'src/Baxy.App/UserMessagePolicy.cs',
         'artifacts/comprobaciones/C03/astra-lora-pilot2-product.turns.jsonl',
         'artifacts/comprobaciones/C03/astra-lora-pilot2-product/profile/sitecustomize.py',
         'scratchpad/c03-lora-pilot2-product.py']
manifest_hash = sha(manifest_path)
assert not (out/'PREREG.json').exists()
adapter = Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f/c03-pilot-lora-v2-f32.gguf')
prereg = {'kind': 'integrated-development-diagnostic-not-promotion',
          'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'hypothesis': 'Pilot2 improved direct compound facts and some mixed replies. Measure its effect across the existing integrated development requests and all LLM roles, including exact confirmation, cancellation and own fixture close. Add only the diagnostic LoRA; source, registry and validators unchanged. Correct the observer to read the actual SkillRegistry encoder.',
          'expected': 'Same prior knowledge, Spanish/English/mixed, clock, audio and personal-task cases, with the close request now addressed by explicit title (own empty C03TitleFixture). Confirm/cancel/reconfirm remains exact. Assess every reply, including summary naturalness; not acceptance or promotion.',
          'profile': {'model': str(model), 'sha256': sha(model), 'adapter': str(adapter), 'adapterSha256': sha(adapter), 'ngl': 99,
                      'kv': 'q8_0', 'hostCompositionBudgetProfile': 'unchanged GPU 5/10s', 'sampling': {'temperature': 0.7, 'top_p': 0.8, 'top_k': 20, 'min_p': 0},
                      'source': 'https://huggingface.co/Qwen/Qwen3-8B#best-practices',
                      'limits': 'Existing product budgets and validators unchanged; stop if attributed GPU exceeds 4096 MiB.'},
          'registrationSha256': manifest_hash,
          'files': {name: sha(ROOT/name) for name in files}}
(out/'PREREG.json').write_text(json.dumps(prereg, indent=2), encoding='utf-8')
env = os.environ.copy()
env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_NGL='99', BAXY_MIND_KV_CACHE_TYPE='q8_0',
           BAXY_MIND_PYTHONPATH=os.pathsep.join((str(out/'profile'), str(ROOT/'src'))),
           BAXY_C03_SAMPLING_AUDIT=str(out/'sampling.jsonl'),
           BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(out/'compose-audit.jsonl'),
           BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
           BAXY_MIND_TURN_AUDIT_PATH=str(out/'turn-audit.jsonl'),
           BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(out/'raw-replies.jsonl'),
           BAXY_APP_TRACE=str(out/'shell-trace.jsonl'))
env.update(BAXY_ASSET_DESCRIPTOR=str(ROOT/'assets.manifest.json'), BAXY_VOICE_WAKE_ON_START='0')
app=ROOT/'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe'
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
command=[str(app),'--conductor','--profile='+str(Path(env['LOCALAPPDATA'])/'BAXY/comprobaciones-c03-lora-pilot2-product'), '--timeout-ms=120000','--commit='+commit,'--capture='+str(out)]
prereg['preparation']='Hold the documented stdin command stream open until both semantic catalog and skill registry constructors finish, or 150 seconds. Warm diagnostic, not cold-start latency or acceptance. Product source unchanged.'
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
                readiness=out/'resource-readiness.jsonl'
                try:
                    rows=[json.loads(line) for line in readiness.read_text(encoding='utf-8').splitlines()]
                except (OSError, json.JSONDecodeError):
                    rows=[]
                ready_components={r.get('component') for r in rows if r.get('encoderSupplied') and r.get('error') is None}
                if {'planner_catalog','skill_registry'} <= ready_components or time.monotonic()-started > 150:
                    commands=(ROOT/'artifacts/comprobaciones/C03/astra-lora-pilot2-product.turns.jsonl').read_bytes()
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
