"""Bounded server fault; never touches the desktop or unrelated process trees."""
from pathlib import Path
import datetime
import json
import os
import sys
import time
import psutil

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-ui107'
app = psutil.Process(int(sys.argv[1]))
server = psutil.Process(int(sys.argv[2]))
assert os.path.normcase(app.exe()) == os.path.normcase(str(root / 'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe'))
assert os.path.normcase(server.exe()) == os.path.normcase('D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe')
assert server.pid in [p.pid for p in app.children(recursive=True)]
started = time.monotonic()
record = {'helper': os.getpid(), 'app': app.pid, 'server': server.pid,
    'serverCreateTime': server.create_time(), 'psutilVersion': psutil.__version__,
    'startedUtc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
suspended = False
try:
    server.suspend(); suspended = True
    record['statusAfterSuspend'] = server.status()
    (out / 'SUSPEND.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps(record), flush=True)
    while server.is_running() and app.is_running() and time.monotonic() - started < 300:
        if (out / 'RESUME_SERVER').exists():
            record['resumeReason'] = 'requested_after_observation'; break
        time.sleep(0.5)
    else:
        record['resumeReason'] = 'watchdog_or_process_exit'
finally:
    if suspended and server.is_running():
        server.resume()
        record['statusAfterResume'] = server.status()
    else:
        record['statusAfterResume'] = 'original_server_no_longer_running'
    record['finishedUtc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record['elapsedSeconds'] = round(time.monotonic() - started, 2)
    (out / 'RESUMED.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps(record), flush=True)
