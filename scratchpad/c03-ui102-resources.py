from pathlib import Path
import datetime
import json
import os
import sys
import time
import psutil

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler

out = root / 'artifacts/comprobaciones/C03/astra-ui102'
pid = int(sys.argv[1])
app = psutil.Process(pid)
expected = root / 'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe'
assert os.path.normcase(app.exe()) == os.path.normcase(str(expected))
created = app.create_time()
(out / 'RESOURCE_PROCESS.json').write_text(json.dumps({'monitor': os.getpid(), 'app': pid,
    'appCreateTime': created, 'startedUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope': 'App and child processes after main.py launch; startup build and pre-monitor interval excluded'}, indent=2), encoding='utf-8')
gpu = ProcessTreeGpuSampler(pid); ram = RamSampler(pid)
gpu.start(); ram.start(); started = time.monotonic(); reason = 'app_exited'
try:
    while app.is_running() and app.create_time() == created:
        if (out / 'STOP_RESOURCE_MONITOR').exists():
            reason = 'monitor_stop_requested'
            break
        if gpu.peak_mib is not None and gpu.peak_mib > 4096:
            reason = 'vram_cap_exceeded'
            break
        if time.monotonic() - started > 1800:
            reason = 'monitor_time_limit'
            break
        time.sleep(0.5)
except psutil.NoSuchProcess:
    pass
finally:
    gpu.stop(); ram.stop()
    result = {'elapsedSeconds': round(time.monotonic() - started, 2), 'gpuPeakMiB': gpu.peak_mib,
        'gpuAttributionAvailable': gpu.telemetry_available, 'ramPeakMiB': ram.peak_mib, 'stopReason': reason}
    (out / 'RESOURCES.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
