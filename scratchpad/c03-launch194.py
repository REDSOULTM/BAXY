"""Own py main.py launch and measure its new App tree; no desktop automation."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
import psutil

root = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler
out = root / 'artifacts/comprobaciones/C03/astra-ui194'
prereg = json.loads((out / 'PREREG.json').read_text(encoding='utf-8'))
expected = root / 'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe'
def apps():
    found=[]
    for proc in psutil.process_iter(['exe']):
        try:
            if proc.info['exe'] and os.path.normcase(proc.info['exe']) == os.path.normcase(str(expected)):
                found.append(proc)
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            pass
    return found
assert not apps(), 'Do not attach to an existing user App'
env=os.environ.copy()
for name in list(env):
    if name.startswith(('BAXY_MIND_','BAXY_VOICE_','BAXY_C03_','BAXY_FIELD_')) or name in {'BAXY_ASSET_DESCRIPTOR','PYTHONPATH','BAXY_DATA_DIR'}:
        env.pop(name,None)
env.update(BAXY_MIND_LLM_GGUF=prereg['model'], BAXY_VOICE_WAKE_ON_START='1',
    BAXY_APP_TRACE=str(out / 'shell-trace.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(out / 'compose-audit.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
    BAXY_MIND_TURN_AUDIT_PATH=str(out / 'turn-audit.jsonl'),
    BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(out / 'raw-replies.jsonl'))
env.update(BAXY_MIND_PYTHONPATH=str(root/'scratchpad/c03-ui194-hook')+os.pathsep+str(root/'src'), BAXY_DATA_DIR=str(Path(env['LOCALAPPDATA'])/'BAXY/C03-ui194-profile'))
with (out / 'launch.log').open('w', encoding='utf-8') as log:
    launcher=subprocess.Popen(['py','main.py'], cwd=root, env=env, stdout=log,
        stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    started=time.monotonic()
    while not (owned:=apps()):
        if time.monotonic()-started>180:
            raise RuntimeError('No App after launch')
        time.sleep(0.25)
    assert len(owned)==1
    app=owned[0]
    gpu,ram=ProcessTreeGpuSampler(app.pid),RamSampler(app.pid)
    gpu.start(); ram.start()
    (out / 'PROCESS.json').write_text(json.dumps({'monitor':os.getpid(),'launcher':launcher.pid,
        'app':app.pid,'appCreateTime':app.create_time(),'secondsAfterLaunch':time.monotonic()-started},indent=2), encoding='utf-8')
    print(f'Owned App{app.pid}; resource sampling active.',flush=True)
    reason='app_exited'
    try:
        while app.is_running():
            if (out / 'STOP_APP').exists():
                reason='operator_finished'; break
            if gpu.peak_mib is not None and gpu.peak_mib>4096:
                reason='vram_cap_exceeded'; break
            if time.monotonic()-started>600:
                reason='deadline_600s'; break
            time.sleep(0.25)
    finally:
        gpu.stop(); ram.stop()
        if app.is_running():
            assert os.path.normcase(app.exe()) == os.path.normcase(str(expected))
            cleanup=subprocess.run(['taskkill','/PID',str(app.pid),'/T','/F'],capture_output=True)
        else:
            cleanup=None
        result={'reason':reason,'seconds':round(time.monotonic()-started,2),
            'gpuPeakMiB':gpu.peak_mib,'gpuAttributionAvailable':gpu.telemetry_available,
            'ramPeakMiB':ram.peak_mib,'launcherExit':launcher.poll(),
            'cleanupExit':cleanup.returncode if cleanup else None}
        (out / 'RESOURCES.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
