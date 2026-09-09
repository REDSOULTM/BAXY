"""Launch py main.py normally; observe only the owned real app and its resources."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
import psutil

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler
OUT=ROOT/'artifacts/comprobaciones/C03/astra-scoped-reader-ui45'
OUT.mkdir(exist_ok=False)
APP=ROOT/'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe'
def apps():
    found=[]
    for p in psutil.process_iter(['exe']):
        try:
            if p.info['exe'] and os.path.normcase(p.info['exe'])==os.path.normcase(str(APP)):
                found.append(p)
        except (psutil.NoSuchProcess,psutil.AccessDenied): pass
    return found
assert not apps(), 'Do not attach to an existing user process'
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
digest=hashlib.sha256(manifest.read_bytes()).hexdigest()
env=os.environ.copy()
for key in list(env):
    if key.startswith(('BAXY_MIND_','BAXY_VOICE_','BAXY_C03_','BAXY_FIELD_')) or key in {'BAXY_ASSET_DESCRIPTOR','PYTHONPATH','BAXY_DATA_DIR'}:
        del env[key]
env.update(BAXY_APP_TRACE=str(OUT/'shell-trace.jsonl'),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(OUT/'compose-audit.jsonl'),BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',BAXY_MIND_TURN_AUDIT_PATH=str(OUT/'turn-audit.jsonl'),BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(OUT/'raw-replies.jsonl'))
(OUT/'PREREG.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':['py','main.py'],'sourcePins':json.loads((ROOT/'artifacts/comprobaciones/C03/TRAMO44_PINS.json').read_text(encoding='utf-8')),'registrationSha256':digest,'method':'Normal real-window launch, registered model/KV/voice/Python defaults. Manual Windows skill input and inspection. Observe current real UI with the source validated in tranche44. Request the consumed negative-state question, both clock/independent-prohibition controls and conversation. If an old recovery appears, inspect it; do not assume prior pending state. No data deletion or external messaging. Development only, not fresh acceptance. Existing audit sinks only; resource sampler attaches exclusively to the newly launched exact Baxy.exe.'},indent=2),encoding='utf-8')
with (OUT/'launch.log').open('w',encoding='utf-8') as log:
    launcher=subprocess.Popen(['py','main.py'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    start=time.monotonic()
    while not (owned:=apps()):
        if time.monotonic()-start>180: raise RuntimeError('No BAXY after launch')
        time.sleep(.5)
    assert len(owned)==1
    app=owned[0]
    gpu,ram=ProcessTreeGpuSampler(app.pid),RamSampler(app.pid)
    gpu.start();ram.start()
    (OUT/'PROCESS.json').write_text(json.dumps({'monitor':os.getpid(),'launcher':launcher.pid,'app':app.pid}),encoding='utf-8')
    stop=None
    known={}
    try:
        while app.is_running():
            for p in [app]+app.children(recursive=True):
                try: known[p.pid]={'pid':p.pid,'name':p.name(),'command':p.cmdline()}
                except (psutil.NoSuchProcess,psutil.AccessDenied): pass
            (OUT/'PROCESSES.json').write_text(json.dumps(list(known.values()),indent=2),encoding='utf-8')
            (OUT/'LIVE.json').write_text(json.dumps({'seconds':round(time.monotonic()-start,2),'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib}),encoding='utf-8')
            if (OUT/'STOP').exists(): stop='operator_finished_observation';break
            if gpu.peak_mib is not None and gpu.peak_mib>4096: stop='attributed_gpu_exceeds_4096_mib';break
            if time.monotonic()-start>1800: stop='deadline_1800s';break
            time.sleep(1)
    finally:
        gpu.stop();ram.stop()
        if app.is_running():
            for p in reversed(app.children(recursive=True)):
                try:p.terminate()
                except psutil.NoSuchProcess:pass
            app.terminate();app.wait(timeout=10)
        result={'stopReason':stop,'gpuPeakMiB':gpu.peak_mib,'ramPeakMiB':ram.peak_mib,'gpuAttributionAvailable':gpu.telemetry_available,'registrationUnchanged':hashlib.sha256(manifest.read_bytes()).hexdigest()==digest,'seconds':round(time.monotonic()-start,2)}
        (OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
