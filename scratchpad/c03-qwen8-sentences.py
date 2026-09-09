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

out = ROOT / 'artifacts/comprobaciones/C03/astra-qwen8-sentences'
model = Path('D:/BAXY/experimental_assets_20260801/Qwen3-8B-Q4_K_M.gguf')
manifest_path = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
files = ['src/baxy_mind/llm.py', 'src/baxy_mind/__main__.py',
         'src/baxy_mind/request_reading.py', 'src/Baxy.App/MindSidecarClient.cs',
         'src/Baxy.App/MainWindowViewModel.cs',
         'artifacts/comprobaciones/C03/astra-qwen8-sentences.turns.jsonl',
         'artifacts/comprobaciones/C03/astra-qwen8-sentences/profile/sitecustomize.py',
         'scratchpad/c03-qwen8-sentences.py']
manifest_hash = sha(manifest_path)
prereg = {'kind': 'integrated-development-diagnostic-not-promotion',
          'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'hypothesis': 'Remove the generic one-sentence veto that rejected an otherwise valid model welcome and useful two-sentence explanations. Facts, polarity, language, confirmation and clarification remain checked. Same model, sampling, corpus and budgets as astra-qwen8-purpose. Examine initial welcome and every turn, not only published count.',
          'expected': 'Six useful faithful replies; no unnecessary clarification, invented words, or loss of requested mixed language.',
          'profile': {'model': str(model), 'sha256': sha(model), 'ngl': 20,
                      'kv': 'q8_0', 'sampling': {'temperature': 0.7, 'top_p': 0.8, 'top_k': 20, 'min_p': 0},
                      'source': 'https://huggingface.co/Qwen/Qwen3-8B#best-practices',
                      'limits': 'Existing product budgets and validators unchanged; stop if attributed GPU exceeds 4096 MiB.'},
          'registrationSha256': manifest_hash,
          'files': {name: sha(ROOT/name) for name in files}}
(out/'PREREG.json').write_text(json.dumps(prereg, indent=2), encoding='utf-8')
env = os.environ.copy()
env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_NGL='20', BAXY_MIND_KV_CACHE_TYPE='q8_0',
           BAXY_MIND_PYTHONPATH=os.pathsep.join((str(out/'profile'), str(ROOT/'src'))),
           BAXY_C03_SAMPLING_AUDIT=str(out/'sampling.jsonl'),
           BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(out/'compose-audit.jsonl'),
           BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
           BAXY_MIND_TURN_AUDIT_PATH=str(out/'turn-audit.jsonl'))
command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
           str(ROOT/'scripts/run_baxy_conductor.ps1'), '-Profile',
           str(Path(env['LOCALAPPDATA'])/'BAXY/comprobaciones-c03-qwen8-sentences'),
           '-Capture', str(out), '-TurnsFile',
           str(ROOT/'artifacts/comprobaciones/C03/astra-qwen8-sentences.turns.jsonl')]
gpu = ProcessTreeGpuSampler(os.getpid())
ram = RamSampler(os.getpid())
gpu.start(); ram.start()
process = None
stopped = None
started = time.monotonic()
try:
    with (out/'conductor.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'PROCESS.json').write_text(json.dumps({'monitor': os.getpid(), 'launcher': process.pid}), encoding='utf-8')
        while process.poll() is None:
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
    gpu.stop(); ram.stop()
    result = {'exitCode': process.returncode if process else None, 'stopReason': stopped,
              'elapsedSeconds': round(time.monotonic()-started, 2),
              'gpuPeakMiB': gpu.peak_mib, 'gpuAttributionAvailable': gpu.telemetry_available,
              'ramPeakMiB': ram.peak_mib, 'registrationUnchanged': sha(manifest_path)==manifest_hash}
    (out/'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
