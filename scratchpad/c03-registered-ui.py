"""Run the existing real-window probe with the registered runtime, no overrides."""
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

OUT = ROOT / 'artifacts/comprobaciones/C03/astra-runtime-qwen-registered/ui'
OUT.mkdir(exist_ok=False)
registration = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

(OUT/'turns.jsonl').write_text(json.dumps({'text':'Dime la hora y el estado del audio.'}, ensure_ascii=False)+'\n', encoding='utf-8')
env = os.environ.copy()
removed = []
for key in list(env):
    if key.startswith(('BAXY_MIND_', 'BAXY_VOICE_', 'BAXY_C03_', 'BAXY_FIELD_')) or key in {'BAXY_ASSET_DESCRIPTOR', 'PYTHONPATH', 'BAXY_DATA_DIR'}:
        removed.append(key)
        del env[key]
env.update(BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(OUT/'compose-audit.jsonl'),
           BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
           BAXY_MIND_TURN_AUDIT_PATH=str(OUT/'turn-audit.jsonl'),
           BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(OUT/'raw-replies.jsonl'),
           BAXY_APP_TRACE=str(OUT/'shell-trace.jsonl'))
command = ['py', 'main.py', '--ui-probe', str(OUT/'turns.jsonl'), '--ui-capture', str(OUT/'rendered.jsonl')]
prereg = {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'kind':'registered-real-window-development-not-fresh-acceptance',
          'method':'Existing FieldUiProbe sends one consumed development input through the real React composer. Observe the actual window independently with sky; probe row count alone does not prove final response. Wake/STT/TTS use registered defaults. No model, KV, sampling, PythonPath, voice or resource overrides; only existing audit sinks. Native UI will be inspected and may receive further development turns, separately recorded.',
          'command':command,'registrationSha256':sha(registration),'removedEnvironmentKeys':removed,
          'files':{str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__), OUT/'turns.jsonl', ROOT/'src/baxy_mind/llm.py', ROOT/'src/Baxy.App/MainWindowViewModel.cs']}}
(OUT/'PREREG.json').write_text(json.dumps(prereg,indent=2), encoding='utf-8')
gpu, ram = ProcessTreeGpuSampler(os.getpid()), RamSampler(os.getpid())
gpu.start(); ram.start()
start=time.monotonic()
known={}
stop=None
process=None
try:
    with (OUT/'launch.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        (OUT/'PROCESS.json').write_text(json.dumps({'monitor':os.getpid(),'launcher':process.pid}),encoding='utf-8')
        while process.poll() is None:
            for child in psutil.Process(os.getpid()).children(recursive=True):
                try:
                    if child.pid not in known:
                        known[child.pid]={'pid':child.pid,'name':child.name(),'command':child.cmdline()}
                        (OUT/'PROCESSES.json').write_text(json.dumps(list(known.values()),indent=2),encoding='utf-8')
                except psutil.NoSuchProcess:
                    pass
            (OUT/'LIVE.json').write_text(json.dumps({'seconds':round(time.monotonic()-start,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib}),encoding='utf-8')
            if gpu.peak_mib is not None and gpu.peak_mib>4096:
                stop='attributed_gpu_exceeds_4096_mib'; break
            if time.monotonic()-start>1800:
                stop='deadline_1800s'; break
            time.sleep(1)
finally:
    if process is not None and process.poll() is None:
        for child in reversed(psutil.Process(process.pid).children(recursive=True)):
            try: child.terminate()
            except psutil.NoSuchProcess: pass
        process.terminate(); process.wait(timeout=10)
    gpu.stop(); ram.stop()
    result={'exitCode':process.returncode if process else None,'stopReason':stop,'seconds':round(time.monotonic()-start,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'gpuAttributionAvailable':gpu.telemetry_available,'registrationUnchanged':sha(registration)==prereg['registrationSha256']}
    (OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)
