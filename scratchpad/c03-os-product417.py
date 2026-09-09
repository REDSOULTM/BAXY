"""Synthetic ES/EN name, confirmation and cancellation controls in a private profile."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03/astra-os-product417'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-os-product417-private'
out.mkdir(exist_ok=True)
private.mkdir(exist_ok=True)
assert not (out/'PREREG.json').exists() and not (out/'PROCESS.json').exists()
assert not (private/'http-posts.jsonl').exists()
cases = ['What is my Windows username?', '¿Con qué cuenta de Windows se está ejecutando BAXY?', 'Which Windows account is running BAXY?', 'Dime la cuenta actual de Windows.', 'Which Windows version am I running?', '¿Qué es una cuenta de Windows?'] + ['¿Qué versión de Windows tengo?', 'How much RAM does this computer have?', '¿Qué procesador tiene este PC?']

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
    'method':'Nine synthetic development turns through real hidden conductor in a new isolated profile, source416. Same six411 turns in their original order, followed by Spanish OS, English RAM and Spanish CPU controls. Only source416 OS provider/typed fact transport changed. Keep the original English username first;411 already passed it cold; do not wait or inject readiness. Capture all real effects, observations and prose. No response/prompt/decision/catalog override; only same diagnostic local model and read-only HTTP observer. Not fresh acceptance, UI or physical voice.',
    'profile_inheritance':'New dedicated LOCALAPPDATA/BAXY child; memory remains disabled and no persistence requested. Only authorized read-only identity/OS observations and conceptual conversation. Actual Windows identity values remain in private capture; public adjudication may redact them.',
    'criteria':'Four account requests perform verified system.identity and describe the effective Windows account, not a human name or OS/resource summary. OS version uses system.status and agrees with independent CIM observed caption; RAM/CPU remain correct; concept is useful explanation without an unsolicited reading. Cold limitation, omitted literals, wrong subject, false access denial or silent composition fail individually; admission200 does not prove success.',
    'cases':cases,
    'manifest_sha256':sha(manifest),
    'diagnostic_model_override':{'path':str(model),'sha256':sha(model),'promotion':False},
    'sources':{name:sha(root/name) for name in ['src/Baxy.Providers.Windows/SystemStatus/WindowsSystemStatusProbe.cs','src/Baxy.Providers.Windows/SystemStatus/WindowsSystemStatusProvider.cs','src/Baxy.Providers.Windows/SystemStatus/SystemStatusContracts.cs','src/Baxy.Core/Operations/SystemStatusHandler.cs','src/Baxy.Core/Operations/CoreOperationModels.cs','src/Baxy.Kernel/Operations/ProductCatalog.cs','src/baxy_mind/__main__.py','src/baxy_mind/request_reading.py','src/baxy_mind/effect_intent.py','src/baxy_mind/llm.py','src/Baxy.App/MainWindowViewModel.cs','src/Baxy.App/UserMessagePolicy.cs','src/Baxy.App/MemoryTurnSession.cs','src/Baxy.App/NaturalMemoryRequestParser.cs','src/Baxy.App/PrivateOperationNarration.cs','src/Baxy.App/MemoryOperationResponseProjection.cs','src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll']},
    'private':str(private),
}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
env=os.environ.copy()
for name in list(env):
    if name.startswith(('BAXY_MIND_','BAXY_VOICE_','BAXY_C03_','BAXY_FIELD_')) or name in {'PYTHONPATH','BAXY_DATA_DIR','BAXY_ASSET_DESCRIPTOR','BAXY_APP_TRACE'}:
        env.pop(name,None)
env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_PYTHONPATH=str(root/'scratchpad/c03-owner417-hook')+os.pathsep+str(root/'src'), BAXY_VOICE_WAKE_ON_START='0',
    BAXY_APP_TRACE=str(private/'shell-trace.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private/'compose-audit.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
    BAXY_MIND_TURN_AUDIT_PATH=str(private/'turn-audit.jsonl'),
    BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(private/'raw-replies.jsonl'))
command=['py','main.py','--conductor','--profile',str(private.parent/'C03-os-profile417'),
    '--capture',str(private/'capture'),'--turns-file',str(turns),'--timeout-ms','120000']
with (private/'launch.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen(command,cwd=root,env=env,stdin=subprocess.DEVNULL,
        stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'PROCESS.json').write_text(json.dumps({'launcher':process.pid,'command':command},indent=2)+'\n',encoding='utf-8')
    code=process.wait()
(out/'EXIT.json').write_text(json.dumps({'exitCode':code,'manifest_unchanged':sha(manifest)==prereg['manifest_sha256']},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'exitCode':code,'private':str(private)}),flush=True)
raise SystemExit(code)




