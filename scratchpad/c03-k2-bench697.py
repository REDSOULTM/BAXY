"""Fixed-token performance controls, distinct from model response quality."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import time

import psutil

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

base = root / 'artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697/bench-fixed'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-k2-bench697-private'
base.mkdir(parents=True, exist_ok=False)
private.mkdir(parents=True, exist_ok=False)
binary = Path('D:/BAXYRuntime/build/llama-k2-horizon-35999d1/build-cuda13-sm86/bin/llama-bench.exe')
models = Path('D:/BAXYRuntime/experiments/models/k2-horizon-20260909')
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(p, v):
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

models_to_run = [('09-q8', models / 'K2-Horizon-0.9B-Q8_0.gguf'),
                 ('09-bf16', models / 'K2-Horizon-1B-BF16.gguf'),
                 ('37-q4', models / 'K2-Horizon-3.7B-Q4_K_M.gguf')]
model_pins = {tag: {'path': str(path), 'sha256': sha(path)} for tag, path in models_to_run}
package = {p.name: sha(p) for p in binary.parent.iterdir() if p.suffix in ['.dll', '.exe']}
before_manifest = sha(manifest)
(private / 'driver.py').write_bytes(Path(__file__).read_bytes())
write(base / 'PREREG.json', {'utc': datetime.now(timezone.utc).isoformat(), 'model_pins': model_pins,
    'backend_files': package, 'driver_sha256': sha(Path(__file__)), 'manifest_sha256': before_manifest,
    'graph_opt_order': [0, 1], 'repetitions': 3, 'prompt_tokens': 512, 'generation_tokens': 128,
    'limits': {'gpu_mib': 3800, 'free_ram_mib': 768, 'per_profile_seconds': 180},
    'scope': 'Fixed-token llama-bench pp512/tg128; warmup enabled, excludes tokenization/sampling/chat/parser. Not response quality or BAXY joint resource acceptance.'})

results = []
for tag, model in models_to_run:
    for opt in [0, 1]:
        key = f'{tag}-graph{opt}'
        command = [str(binary), '-m', str(model), '-p', '512', '-n', '128', '-r', '3',
            '-b', '512', '-ub', '128', '-t', '8', '-ngl', '99', '-fa', 'on',
            '-ctk', 'q8_0', '-ctv', 'q8_0', '-mmp', '0', '-o', 'jsonl', '-v']
        env = os.environ.copy()
        env['GGML_CUDA_GRAPH_OPT'] = str(opt)
        env['PATH'] = 'C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v13.0/bin;' + env['PATH']
        write(base / (key + '-PLAN.json'), {'command': command, 'GGML_CUDA_GRAPH_OPT': opt,
              'inherited_ggml_environment': {k: v for k, v in os.environ.items() if k.startswith('GGML_')}})
        stdout_path, stderr_path = private / (key + '.jsonl'), private / (key + '.log')
        with stdout_path.open('w', encoding='utf-8') as out, stderr_path.open('w', encoding='utf-8') as err:
            proc = subprocess.Popen(command, cwd=binary.parent, env=env, stdout=out, stderr=err,
                                    stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            gpu, ram = ProcessTreeGpuSampler(proc.pid), RamSampler(proc.pid)
            gpu.start()
            ram.start()
            start = time.monotonic()
            violation = None
            hardware = []
            while proc.poll() is None:
                if (gpu.peak_mib or 0) > 3800:
                    violation = 'gpu_limit'
                elif psutil.virtual_memory().available < 768 * 2**20:
                    violation = 'free_ram_limit'
                elif time.monotonic() - start > 180:
                    violation = 'profile_timeout'
                if violation:
                    proc.terminate()
                    break
                sample = subprocess.run(['nvidia-smi', '--query-gpu=pstate,clocks.sm,clocks.mem,power.draw,temperature.gpu,utilization.gpu',
                    '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                hardware.append({'seconds': time.monotonic() - start, 'sample': sample.stdout.strip(), 'exit': sample.returncode})
                time.sleep(.5)
            code = proc.wait(timeout=10)
            gpu.stop()
            ram.stop()
        write(private / (key + '-hardware.json'), hardware)
        rows = [json.loads(line) for line in stdout_path.read_text(encoding='utf-8').splitlines() if line.strip()]
        record = {'tag': key, 'exit': code, 'violation': violation, 'gpu_peak_mib': gpu.peak_mib,
            'ram_peak_mib': ram.peak_mib, 'rows': rows, 'stdout_sha256': sha(stdout_path), 'stderr_sha256': sha(stderr_path),
            'hardware_sha256': sha(private / (key + '-hardware.json')),
            'manifest_unchanged': sha(manifest) == before_manifest}
        write(base / (key + '-RESULT.json'), record)
        results.append(record)
        print(json.dumps({'tag': key, 'exit': code, 'violation': violation, 'gpu_mib': gpu.peak_mib,
                          'rates': [{'pp': r['n_prompt'], 'tg': r['n_gen'], 'avg_ts': r['avg_ts']} for r in rows]}), flush=True)
        if code or violation:
            raise RuntimeError(f'Profile failed: {key}; preserve and inspect before continuing.')
        assert record['manifest_unchanged'] and len(rows) == 2 and all(len(r['samples_ts']) == 3 for r in rows)
write(base / 'RESULTS.json', results)
