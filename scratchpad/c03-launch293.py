"""Leave the current BAXY candidate open for the owner, without a test watchdog."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time
import psutil

root=Path(__file__).resolve().parents[1]
out=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui293-private'
out.mkdir(exist_ok=False)
app_path=root/'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe'
def apps():
    rows=[]
    for process in psutil.process_iter(['exe']):
        try:
            if process.info['exe'] and os.path.normcase(process.info['exe'])==os.path.normcase(str(app_path)):
                rows.append(process)
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            pass
    return rows
def save(value):
    (out/'LAUNCH.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
existing=apps()
if existing:
    save({'reusedExisting':True,'app':existing[0].pid,'appCreateTime':existing[0].create_time(),
          'userOwned':True,'automaticClose':False})
    print('Existing BAXY retained.',flush=True)
    raise SystemExit(0)
model=Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf')
with model.open('rb') as stream:
    digest=hashlib.file_digest(stream,'sha256').hexdigest()
assert digest=='3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
env=os.environ.copy()
for name in list(env):
    if name.startswith(('BAXY_MIND_','BAXY_VOICE_','BAXY_C03_','BAXY_FIELD_')) or name in {'PYTHONPATH','BAXY_DATA_DIR','BAXY_ASSET_DESCRIPTOR','BAXY_APP_TRACE'}:
        env.pop(name,None)
env.update(BAXY_VOICE_WAKE_ON_START='0',
    BAXY_APP_TRACE=str(out/'shell-trace.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(out/'compose-audit.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
    BAXY_MIND_TURN_AUDIT_PATH=str(out/'turn-audit.jsonl'),
    BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(out/'raw-replies.jsonl'))
with (out/'launch.log').open('w',encoding='utf-8') as log:
    launcher=subprocess.Popen(['py','main.py'],cwd=root,env=env,stdin=subprocess.DEVNULL,
        stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
started=time.monotonic()
record={'utc':datetime.now(timezone.utc).isoformat(),'launcher':launcher.pid,'userOwned':True,
    'automaticClose':False,'volumeChanged':False,'diagnosticHook':False,
    'modelOverride':None,'modelSha256':digest,'status':'starting'}
save(record)
while not (found:=apps()):
    if launcher.poll() is not None or time.monotonic()-started>180:
        record.update(status='startup_not_observed',launcherExit=launcher.poll())
        save(record)
        raise RuntimeError('Inspect this launch; do not restart or terminate automatically')
    time.sleep(.5)
app=found[0]
record.update(status='app_running',app=app.pid,appCreateTime=app.create_time())
save(record)
print(json.dumps(record),flush=True)
# Deliberately no wait-for-exit, cleanup, deadline or volume mutation.

