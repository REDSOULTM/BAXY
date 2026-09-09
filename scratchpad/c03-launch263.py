"""Launch the actual desktop, sample its process tree, restore volume on exit."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler
from baxy_mind.voice_aec import AudioDucker, _com_apartment

BASE = ROOT/'artifacts/comprobaciones/C03'
OUT = BASE/'astra-ui263'
PRIVATE = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui263-private'
OUT.mkdir(exist_ok=False)
PRIVATE.mkdir(exist_ok=False)
def save(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
snapshot = json.loads((BASE/'astra-source263-snapshot/FILES.json').read_text(encoding='utf-8'))
assert all(sha(ROOT/name)==expected for name,expected in snapshot.items())
model = Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
assert sha(model) == '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
expected_app = ROOT/'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe'
def apps():
    found=[]
    for process in psutil.process_iter(['exe']):
        try:
            if process.info['exe'] and os.path.normcase(process.info['exe'])==os.path.normcase(str(expected_app)):
                found.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return found
assert not apps(), 'Existing user App must not be used'
save('PREREG.json', {'utc':datetime.now(timezone.utc).isoformat(), 'model':str(model),
    'method':'Actual py main.py, source262 and installed lock60; Qwen3.5 override remains unpromoted. Input through desktop Computer Use or owner typing, record provenance. main.py determines the effective data profile; do not assume BAXY_DATA_DIR override survives it. Read-only voice/Piper/AEC and local logical HTTP observers; no injected inputs/responses, no replaced algorithms. Owned process-tree GPU/RAM sampling and volume restoration.',
    'criteria':'UI truthfulness and spoken results, direct microphone available through actual UI, concurrent UI/LLM/voice within4096MiB attributed dedicated GPU memory. Existing missing wake must remain honest, no bypass.',
    'plannedDevelopmentInputs':['abre steam','Tengo en mente que abras steam','Si, abre steam','mhhhhh, porque no?, cuales son tus capacidades?'],
    'limitations':'Development controls, not fresh human reserve. Generated Piper audio alone does not prove sound reaching a microphone. No C08 certification.',
    'sourceFiles':snapshot, 'hookSha256':sha(ROOT/'scratchpad/c03-ui263-hook/sitecustomize.py'),
    'launcherSha256':sha(Path(__file__)), 'maximumSeconds':600})
env=os.environ.copy()
for name in list(env):
    if name.startswith(('BAXY_MIND_','BAXY_VOICE_','BAXY_C03_','BAXY_FIELD_')) or name in {'BAXY_ASSET_DESCRIPTOR','PYTHONPATH','BAXY_DATA_DIR'}:
        env.pop(name,None)
env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_VOICE_WAKE_ON_START='0',
    BAXY_APP_TRACE=str(OUT/'shell-trace.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(OUT/'compose-audit.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
    BAXY_MIND_TURN_AUDIT_PATH=str(OUT/'turn-audit.jsonl'),
    BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(OUT/'raw-replies.jsonl'),
    BAXY_MIND_PYTHONPATH=str(ROOT/'scratchpad/c03-ui263-hook')+os.pathsep+str(ROOT/'src'),
    BAXY_DATA_DIR=str(Path(env['LOCALAPPDATA'])/'BAXY/C03-ui263-profile'))
launcher=app=gpu=ram=None
reason='startup_failed'
started=time.monotonic()
with _com_apartment():
    endpoint=AudioDucker._endpoint()
    before={'levelScalar':float(endpoint.GetMasterVolumeLevelScalar()), 'muted':bool(endpoint.GetMute())}
    save('AUDIO_SETUP.json',{'before':before,'testLevelScalar':.30})
    try:
        endpoint.SetMasterVolumeLevelScalar(.30,None)
        endpoint.SetMute(0,None)
        with (OUT/'launch.log').open('w',encoding='utf-8') as log:
            launcher=subprocess.Popen(['py','main.py'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            while not (owned:=apps()):
                if time.monotonic()-started>180:
                    raise RuntimeError('App startup deadline exceeded')
                time.sleep(.25)
            assert len(owned)==1
            app=owned[0]
            created=app.create_time()
            gpu,ram=ProcessTreeGpuSampler(app.pid),RamSampler(app.pid)
            gpu.start(); ram.start()
            save('PROCESS.json',{'monitor':os.getpid(),'launcher':launcher.pid,'app':app.pid,'appCreateTime':created})
            print(f'Owned App {app.pid}; UI/voice resource observation active.',flush=True)
            reason='app_exited'
            while app.is_running():
                if (OUT/'STOP_APP').exists():
                    reason='operator_finished'; break
                if gpu.peak_mib is not None and gpu.peak_mib>4096:
                    reason='vram_cap_exceeded'; break
                if time.monotonic()-started>600:
                    reason='deadline_600s'; break
                time.sleep(.25)
    finally:
        if gpu is not None: gpu.stop()
        if ram is not None: ram.stop()
        cleanup=None
        if app is not None and app.is_running():
            assert app.create_time()==created and os.path.normcase(app.exe())==os.path.normcase(str(expected_app))
            cleanup=subprocess.run(['taskkill','/PID',str(app.pid),'/T','/F'],capture_output=True)
        if launcher is not None:
            if app is None and launcher.poll() is None:
                subprocess.run(['taskkill','/PID',str(launcher.pid),'/T','/F'],capture_output=True)
            try: launcher.wait(timeout=15)
            except subprocess.TimeoutExpired: launcher.terminate(); launcher.wait(timeout=5)
        endpoint.SetMasterVolumeLevelScalar(before['levelScalar'],None)
        endpoint.SetMute(int(before['muted']),None)
        after={'levelScalar':float(endpoint.GetMasterVolumeLevelScalar()),'muted':bool(endpoint.GetMute())}
        result={'reason':reason,'seconds':round(time.monotonic()-started,2),'gpuPeakMiB':gpu.peak_mib if gpu else None,
            'gpuAttributionAvailable':gpu.telemetry_available if gpu else False,'ramPeakMiB':ram.peak_mib if ram else None,
            'launcherExit':launcher.poll() if launcher else None,'cleanupExit':cleanup.returncode if cleanup else None,
            'volumeBefore':before,'volumeAfter':after,'volumeRestoredExactly':before==after}
        save('RESOURCES.json',result)
        print(json.dumps(result),flush=True)
