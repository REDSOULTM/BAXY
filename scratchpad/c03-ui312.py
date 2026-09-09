"""One real WebView form turn using the existing product UI probe."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-ui312'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-ui312-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
(private/'turns.jsonl').write_text(json.dumps({'text':'quien soy'},ensure_ascii=False)+'\n',encoding='utf-8')
prereg={'utc':datetime.now(timezone.utc).isoformat(),
    'method':'py main.py --ui-probe, one original293 request entered into the actual React input and form in desktop WebView; capture visible activity DOM. Current source311 and Fast311green, registered2507, no classification/model/output injection. Probe closes its own instance afterwards; reopen owner instance313 without a probe/timer. Private sitecustomize observes native HTTP requests/responses and delegates unchanged. Its diagnostic I/O can affect timing; no screenshot or acoustic certification from DOM alone.',
    'criteria':'Publication criterion: captured USER literal quien soy followed by a BAXY answer in the actual DOM, with no exhaustion. Separate identity quality criterion: only pass if answer attributes a verified Windows account to the user; generic user description does not meet that criterion. Compare actual Core observation/compose audit. Merely rows>=2 or published=true is insufficient: read the rendered message. No prior owner messages in stopped310; snapshot311 preserved.',
    'source_sha256':hashlib.sha256((root/'src/baxy_mind/llm.py').read_bytes()).hexdigest(),
    'private':str(private)}
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
env['PYTHONPATH']=str(root/'scratchpad/c03-ui312-hook')+os.pathsep+str(root/'src')
command=['py','main.py','--ui-probe',str(private/'turns.jsonl'),'--ui-capture',str(private/'ui.jsonl')]
with (private/'launch.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen(command,cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=log,
        stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'PROCESS.json').write_text(json.dumps({'launcher':process.pid,'command':command},indent=2)+'\n',encoding='utf-8')
    code=process.wait()
(out/'EXIT.json').write_text(json.dumps({'exitCode':code})+'\n',encoding='utf-8')
print(json.dumps({'exitCode':code,'capture':str(private/'ui.jsonl')}),flush=True)
raise SystemExit(code)


