"""Six recovered owner turns through the complete shared product route."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03/astra-memory-product334'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-memory-product334-private'
out.mkdir(exist_ok=False)
private.mkdir(exist_ok=False)
transcript_path = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-owner264-heap280/TRANSCRIPT282.json'
transcript = json.loads(transcript_path.read_text(encoding='utf-8'))
indices = [99, 101, 103, 105, 107, 109]
assert all(transcript[index]['index'] == index and transcript[index]['isUser'] for index in indices)
cases = [transcript[index]['body'] for index in indices]
commands = [{'cmd':'turn','text':request} for request in cases]
turns = private/'turns.jsonl'
turns.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in commands),encoding='utf-8')
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
manifest = Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
prereg = {
    'utc':datetime.now(timezone.utc).isoformat(),
    'method':'py main.py --conductor, default registered2507, actual source321/324/326/330/333 and current Release; full shared product admission/classification/chat/publication. Six exact human requests from owner264 transcript282 indices99,101,103,105,107,109 in their original order, one continuous session. Old assistant failures are not injected; current product generates replies. Dedicated private profile. No classifier/model injection or sampling override. The inherited human request explicitly asks to remember the name; any persistence stays in a dedicated private test profile, never owner data. This is development replay, not fresh acceptance. Conductor is not graphical UI or physical voice evidence.',
    'profile_inheritance':'Same isolation as319/322: dedicated direct child of LOCALAPPDATA/BAXY. Compared with331, only source333 shares a question-scope detector instead of swallowing content before a final question; registered model/configuration unchanged.',
    'criteria':'Honor the explicit request to remember a name, preserve Emmanuel as the person supplied it, distinguish BAXY from the person on the final two questions, and never claim a memory write without verified persistence. The fresh who-am-I Windows account criterion from314 is not the criterion for this context. Read every terminal/progress response; do not equate publication with correctness.',
    'cases':cases,
    'manifest_sha256':sha(manifest),
    'sources':{name:sha(root/name) for name in ['src/baxy_mind/__main__.py','src/baxy_mind/request_reading.py','src/baxy_mind/effect_intent.py','src/baxy_mind/llm.py','src/Baxy.App/MainWindowViewModel.cs','src/Baxy.App/UserMessagePolicy.cs','src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll']},
    'private':str(private),
}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
env=os.environ.copy()
for name in list(env):
    if name.startswith(('BAXY_MIND_','BAXY_VOICE_','BAXY_C03_','BAXY_FIELD_')) or name in {'PYTHONPATH','BAXY_DATA_DIR','BAXY_ASSET_DESCRIPTOR','BAXY_APP_TRACE'}:
        env.pop(name,None)
env.update(BAXY_MIND_PYTHONPATH=str(root/'scratchpad/c03-owner334-hook')+os.pathsep+str(root/'src'), BAXY_VOICE_WAKE_ON_START='0',
    BAXY_APP_TRACE=str(private/'shell-trace.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private/'compose-audit.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
    BAXY_MIND_TURN_AUDIT_PATH=str(private/'turn-audit.jsonl'),
    BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(private/'raw-replies.jsonl'))
command=['py','main.py','--conductor','--profile',str(private.parent/'C03-memory-profile334'),
    '--capture',str(private/'capture'),'--turns-file',str(turns),'--timeout-ms','120000']
with (private/'launch.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen(command,cwd=root,env=env,stdin=subprocess.DEVNULL,
        stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'PROCESS.json').write_text(json.dumps({'launcher':process.pid,'command':command},indent=2)+'\n',encoding='utf-8')
    code=process.wait()
(out/'EXIT.json').write_text(json.dumps({'exitCode':code,'manifest_unchanged':sha(manifest)==prereg['manifest_sha256']},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'exitCode':code,'private':str(private)}),flush=True)
raise SystemExit(code)




