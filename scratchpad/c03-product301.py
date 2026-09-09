"""Three existing development inputs through the complete shared product route."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03/astra-memory-product301'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-memory-product301-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
cases = ['me llamo emmanuel, dime hola emmanuel', 'me llamo Albeda', 'my favorite city is Lima']
commands = []
for index, request in enumerate(cases):
    if index:
        commands.append({'cmd':'session.new'})
    commands.append({'cmd':'turn','text':request})
turns = private/'turns.jsonl'
turns.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in commands),encoding='utf-8')
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
manifest = Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
prereg = {
    'utc':datetime.now(timezone.utc).isoformat(),
    'method':'py main.py --conductor, default registered2507, actual source298/299 and current Release; full shared product admission/classification/chat/publication. Three unchanged development requests296; new session between controls. Dedicated private profile. No classifier/model injection, sampling override, persistence request, or effects. Conductor is not graphical UI or physical voice evidence.',
    'prior_failure':'300 never reached a turn: nested profile rejected by WindowsPrivateStorage direct-child policy.301 changes only profile location to an owned direct child of LOCALAPPDATA/BAXY; no product source/config change.',
    'criteria':'Serve requested greeting and acknowledge other personal context without irrelevant storage clarification, false storage claims or unrequested memory writes. Read every terminal/progress response; do not equate publication with correctness.',
    'cases':cases,
    'manifest_sha256':sha(manifest),
    'sources':{name:sha(root/name) for name in ['src/baxy_mind/llm.py','src/Baxy.App/MainWindowViewModel.cs','src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll']},
    'private':str(private),
}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
env=os.environ.copy()
for name in list(env):
    if name.startswith(('BAXY_MIND_','BAXY_VOICE_','BAXY_C03_','BAXY_FIELD_')) or name in {'PYTHONPATH','BAXY_DATA_DIR','BAXY_ASSET_DESCRIPTOR','BAXY_APP_TRACE'}:
        env.pop(name,None)
env.update(BAXY_VOICE_WAKE_ON_START='0',
    BAXY_APP_TRACE=str(private/'shell-trace.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private/'compose-audit.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
    BAXY_MIND_TURN_AUDIT_PATH=str(private/'turn-audit.jsonl'),
    BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(private/'raw-replies.jsonl'))
command=['py','main.py','--conductor','--profile',str(private.parent/'C03-memory-profile301'),
    '--capture',str(private/'capture'),'--turns-file',str(turns),'--timeout-ms','120000']
with (private/'launch.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen(command,cwd=root,env=env,stdin=subprocess.DEVNULL,
        stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'PROCESS.json').write_text(json.dumps({'launcher':process.pid,'command':command},indent=2)+'\n',encoding='utf-8')
    code=process.wait()
(out/'EXIT.json').write_text(json.dumps({'exitCode':code,'manifest_unchanged':sha(manifest)==prereg['manifest_sha256']},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'exitCode':code,'private':str(private)}),flush=True)
raise SystemExit(code)
