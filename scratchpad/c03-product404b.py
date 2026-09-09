"""Synthetic ES/EN name, confirmation and cancellation controls in a private profile."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03/astra-stored-product404b'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-stored-product404b-private'
out.mkdir(exist_ok=True)
private.mkdir(exist_ok=True)
assert not (out/'PREREG.json').exists() and not (out/'PROCESS.json').exists()
assert not (private/'http-posts.jsonl').exists()
cases = [
    "My name is Jordan. Remember my name.",
    "confirm",
    "What name have you saved in private memory?",
    "Me llamo Álvaro.",
    "¿Qué nombre tienes guardado en tu memoria privada?",
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
    'method':'Six explicitly synthetic development turns through the real conductor in a new isolated private profile. Source402 transports the short single projected read value via existing requiredFacts and enforces it in App acceptance; source395 retains retry history and397 fixes the accented-name language guard. Cases and profile setup are unchanged from393b. Source404 now lets generic name recall use the current role-bounded human self-naming context; explicit stored reads and a session without that context retain private dispatch. No name extraction/cache or model wording is added. Compare same six-turn402b profile. This is actual source, not injected facts or decisions. No model/prompt/sampler change or injection. This is not fresh human acceptance, a graphical UI or physical voice measurement.',
    'profile_inheritance':'New dedicated LOCALAPPDATA/BAXY child with persistence initially disabled. A synthetic Jordan save is explicitly requested; the exact product enable confirmation is accepted and its bound name save may resume. Later Alvaro declaration does not authorize overwriting that persisted name. All effects and journal remain inside the diagnostic profile; owner memory is outside scope.',
    'criteria':'T1 honestly reports disabled persistence and offers enabling. T2 confirms the actual pending enable and bound save, reporting only verified effects. T3 reads stored Jordan. T4 acknowledges conversational Alvaro without saving. T5 must still read stored Jordan, not confuse current conversation with saved name. T6 asks the conversational name and should answer Alvaro; this last control diagnoses the still-open generic-name routing, not an expected success claimed by393. All visible messages and journal adjudicated individually. A nonempty final or admission200 is not correctness.',
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
env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_PYTHONPATH=str(root/'scratchpad/c03-owner404b-hook')+os.pathsep+str(root/'src'), BAXY_VOICE_WAKE_ON_START='0',
    BAXY_APP_TRACE=str(private/'shell-trace.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private/'compose-audit.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
    BAXY_MIND_TURN_AUDIT_PATH=str(private/'turn-audit.jsonl'),
    BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(private/'raw-replies.jsonl'))
command=['py','main.py','--conductor','--profile',str(private.parent/'C03-stored-profile404b'),
    '--capture',str(private/'capture'),'--turns-file',str(turns),'--timeout-ms','120000']
with (private/'launch.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen(command,cwd=root,env=env,stdin=subprocess.DEVNULL,
        stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'PROCESS.json').write_text(json.dumps({'launcher':process.pid,'command':command},indent=2)+'\n',encoding='utf-8')
    code=process.wait()
(out/'EXIT.json').write_text(json.dumps({'exitCode':code,'manifest_unchanged':sha(manifest)==prereg['manifest_sha256']},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'exitCode':code,'private':str(private)}),flush=True)
raise SystemExit(code)




