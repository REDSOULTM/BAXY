"""Synthetic ES/EN name, confirmation and cancellation controls in a private profile."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03/astra-memory-product380'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-memory-product380-private'
out.mkdir(exist_ok=True)
private.mkdir(exist_ok=True)
assert not (out/'PREREG.json').exists() and not (out/'PROCESS.json').exists()
assert not (private/'http-posts.jsonl').exists()
cases = [
    "My name is Jordan. Remember my name.",
    "What would I be confirming?",
    "cancel",
    "Who am I?",
    "What is my name?",
    "Me llamo Álvaro y quiero que guardes mi nombre.",
    "¿Qué vas a activar?",
    "cancelar",
    "quién soy ahora",
    "¿Cómo me llamo?",
]
commands = [{'cmd':'turn','text':request} for request in cases]
turns = private/'turns.jsonl'
turns.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in commands),encoding='utf-8')
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
manifest = Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
model=Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')
assert sha(model)=='00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
prereg = {
    'utc':datetime.now(timezone.utc).isoformat(),
    'method':'Ten explicitly synthetic development controls in one continuous private profile: namesJordan/Álvaro, ES/EN, ask what confirmation would authorize, cancel, then reference the session name without having enabled persistence. Same modelQwen3.5 and ten controls370; source374 corrects the personal-fact observation veto,377 recognizes decision verb language,379 transports the specific withdrawn private operation and outcome cancellation. No prompt, sampler, authority, private name parser or runtime registration change; no runtime promotion, no classifier or response injection. These are not historical human messages or fresh acceptance. No graphical UI or physical voice evidence.',
    'profile_inheritance':'Dedicated LOCALAPPDATA/BAXY child, starts with persistence disabled. Only the typed product pipeline may change it. Requests expressly ask to remember a synthetic name but later cancel both enable challenges. No authorisation to affect owner memory; all journal/state are in the diagnostic profile. Model/sampling/template unchanged366.',
    'criteria':'Each request is answered in its language; confirmation explanation identifies enabling local memory and why needed, not an unspecified action. Cancel does not enable memory or save the name. Subsequent who-am-I and what-is-my-name can use the current conversation without falsely claiming persistence or substituting a Windows account. A newly declared name replaces the earlier conversational self-reference, without inventing a persistent update. Assess every terminal and journal; emitted text alone is not usefulness.',
    'cases':cases,
    'manifest_sha256':sha(manifest),
    'diagnostic_model_override':{'path':str(model),'sha256':sha(model),'promotion':False},
    'sources':{name:sha(root/name) for name in ['src/baxy_mind/__main__.py','src/baxy_mind/request_reading.py','src/baxy_mind/effect_intent.py','src/baxy_mind/llm.py','src/Baxy.App/MainWindowViewModel.cs','src/Baxy.App/UserMessagePolicy.cs','src/Baxy.App/MemoryTurnSession.cs','src/Baxy.App/NaturalMemoryRequestParser.cs','src/Baxy.App/PrivateOperationNarration.cs','src/Baxy.App/MemoryOperationResponseProjection.cs','src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll']},
    'private':str(private),
}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
env=os.environ.copy()
for name in list(env):
    if name.startswith(('BAXY_MIND_','BAXY_VOICE_','BAXY_C03_','BAXY_FIELD_')) or name in {'PYTHONPATH','BAXY_DATA_DIR','BAXY_ASSET_DESCRIPTOR','BAXY_APP_TRACE'}:
        env.pop(name,None)
env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_PYTHONPATH=str(root/'scratchpad/c03-owner380-hook')+os.pathsep+str(root/'src'), BAXY_VOICE_WAKE_ON_START='0',
    BAXY_APP_TRACE=str(private/'shell-trace.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private/'compose-audit.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
    BAXY_MIND_TURN_AUDIT_PATH=str(private/'turn-audit.jsonl'),
    BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(private/'raw-replies.jsonl'))
command=['py','main.py','--conductor','--profile',str(private.parent/'C03-memory-profile380'),
    '--capture',str(private/'capture'),'--turns-file',str(turns),'--timeout-ms','120000']
with (private/'launch.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen(command,cwd=root,env=env,stdin=subprocess.DEVNULL,
        stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'PROCESS.json').write_text(json.dumps({'launcher':process.pid,'command':command},indent=2)+'\n',encoding='utf-8')
    code=process.wait()
(out/'EXIT.json').write_text(json.dumps({'exitCode':code,'manifest_unchanged':sha(manifest)==prereg['manifest_sha256']},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'exitCode':code,'private':str(private)}),flush=True)
raise SystemExit(code)




