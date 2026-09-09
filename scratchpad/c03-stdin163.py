"""Bounded Windows reproduction: CRT reader versus native pipe reader."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

if len(sys.argv) > 1:
    import threading
    import msvcrt
    import _winapi
    import numpy

    mode, probe = sys.argv[1:]
    handle = msvcrt.get_osfhandle(0)
    def receive():
        print('reading', flush=True)
        if mode == 'crt':
            os.read(0, 1024)
        else:
            _winapi.ReadFile(handle, 1024)
    threading.Thread(target=receive, daemon=True).start()
    time.sleep(0.2)
    print('probing', flush=True)
    started = time.monotonic()
    if probe == 'isatty':
        result = os.isatty(0)
    else:
        from scipy.signal import resample_poly
        result = resample_poly(numpy.zeros(1536), 1, 3).size
    print(json.dumps({'result': result, 'seconds': time.monotonic()-started}), flush=True)
    os._exit(0)

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03/astra-stdin163'
out.mkdir(exist_ok=False)
(out/'PREREG.json').write_text(json.dumps({'method': 'Four small child processes, numpy imported before blocking stdin reader. Compare os.read CRT versus _winapi.ReadFile native with same anonymous pipe. Probe os.isatty(0) separately from scipy.signal import/resampling. No audio or LLM;10 s bounded per process. Parent keeps stdin open and sends no bytes.', 'criterion': 'Determine whether the descriptor CRT lock itself can explain cold native import stalling. Child os._exit is experimental cleanup, not product shutdown.'}, indent=2), encoding='utf-8')
rows=[]
for probe in ('isatty', 'scipy'):
    for mode in ('crt', 'native'):
        p = subprocess.Popen([sys.executable, '-u', __file__, mode, probe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        started=time.monotonic()
        timed_out=False
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            timed_out=True
            p.kill()
            p.wait(timeout=5)
        stdout=p.stdout.read()
        stderr=p.stderr.read()
        p.stdin.close()
        p.stdout.close()
        p.stderr.close()
        row={'reader':mode, 'probe':probe, 'timeout':timed_out, 'exitCode':p.returncode, 'seconds':time.monotonic()-started, 'stdout':stdout, 'stderr':stderr}
        rows.append(row)
        (out/'RESULTS.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
        print(json.dumps(row),flush=True)
