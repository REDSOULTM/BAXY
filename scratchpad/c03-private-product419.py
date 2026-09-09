"""Synthetic ES/EN name, confirmation and cancellation controls in a private profile."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import psutil

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from scripts.measure_mind_budget import ProcessTreeGpuSampler, RamSampler
out = root/'artifacts/comprobaciones/C03/astra-private-product419'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-private-product419-private'
out.mkdir(exist_ok=True)
private.mkdir(exist_ok=True)
assert not (out/'PREREG.json').exists() and not (out/'PROCESS.json').exists()
assert not (private/'http-posts.jsonl').exists()
cases = [
    "My name is Jordan. Remember my name.",
    "confirm",
    "Abre una aplicación.",
    "What name have you saved in private memory?",
    "Me llamo Álvaro.",
    "Abre una aplicación.",
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
    'method': 'Eight synthetic development turns in a new isolated real conductor profile. Same404b name/enable/store/read/conversation sequence, with an underspecified application request inserted before each explicit stored-name read. Source418 gives the already typed private request precedence over the pending public clarification, preserving exact private confirmation. Source416 OS fix also present but no OS requests. No prompt/model/sampler/decision injection. Record whether each inserted request really leaves clarification pending; only then claim the targeted scenario was exercised. Not fresh acceptance, UI or physical voice.',
    'profile_inheritance':'New dedicated LOCALAPPDATA/BAXY child with persistence initially disabled. A synthetic Jordan save is explicitly requested; the exact product enable confirmation is accepted and its bound name save may resume. Later Alvaro declaration does not authorize overwriting that persisted name. All effects and journal remain inside the diagnostic profile; owner memory is outside scope.',
    'criteria': 'T1 honestly requests enabling, T2 accepts exact pending enable and resumes authorized synthetic save. T3/T6 clarify the missing application without inventing a target; T4/T7 perform a private recall despite that pending public clarification. Stored name is Jordan, current conversational name is Alvaro, with correct human subject and no unrequested overwrite. Prose failure is separate from successful private dispatch. Check every final, operation and native call; admission200 is not acceptance.',
    'cases':cases,
    'manifest_sha256':sha(manifest),
    'diagnostic_model_override':{'path':str(model),'sha256':sha(model),'promotion':False},
    'sources':{name:sha(root/name) for name in ['src/baxy_mind/__main__.py','src/baxy_mind/request_reading.py','src/baxy_mind/effect_intent.py','src/baxy_mind/llm.py','src/Baxy.App/MainWindowViewModel.cs','src/Baxy.App/UserMessagePolicy.cs','src/Baxy.App/MemoryTurnSession.cs','src/Baxy.App/NaturalMemoryRequestParser.cs','src/Baxy.App/PrivateOperationNarration.cs','src/Baxy.App/MemoryOperationResponseProjection.cs','src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll']},
    'private':str(private),
    'resource_limits':{'gpu_stop_mib':3800, 'minimum_free_ram_mib':768, 'scope':'owned hidden diagnostic process tree, no physical voice; stop only that tree on bound'},
}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
env=os.environ.copy()
for name in list(env):
    if name.startswith(('BAXY_MIND_','BAXY_VOICE_','BAXY_C03_','BAXY_FIELD_')) or name in {'PYTHONPATH','BAXY_DATA_DIR','BAXY_ASSET_DESCRIPTOR','BAXY_APP_TRACE'}:
        env.pop(name,None)
env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_PYTHONPATH=str(root/'scratchpad/c03-owner419-hook')+os.pathsep+str(root/'src'), BAXY_VOICE_WAKE_ON_START='0',
    BAXY_APP_TRACE=str(private/'shell-trace.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private/'compose-audit.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
    BAXY_MIND_TURN_AUDIT_PATH=str(private/'turn-audit.jsonl'),
    BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(private/'raw-replies.jsonl'))
command=['py','main.py','--conductor','--profile',str(private.parent/'C03-private-profile419'),
    '--capture',str(private/'capture'),'--turns-file',str(turns),'--timeout-ms','120000']
with (private/'launch.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen(command,cwd=root,env=env,stdin=subprocess.DEVNULL,
        stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'PROCESS.json').write_text(json.dumps({'launcher':process.pid,'command':command},indent=2)+'\n',encoding='utf-8')
    gpu, ram = ProcessTreeGpuSampler(process.pid), RamSampler(process.pid)
    stop = threading.Event()
    violations = []
    started = time.monotonic()
    def watch_resources():
        while not stop.wait(0.25):
            if gpu.peak_mib is not None and gpu.peak_mib >= 3800:
                violations.append('owned_gpu_bound')
            if psutil.virtual_memory().available < 768 * 2**20:
                violations.append('system_free_ram_bound')
            if violations:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW, check=False)
                return
    guard = threading.Thread(target=watch_resources, daemon=True)
    try:
        gpu.start()
        ram.start()
        guard.start()
        code=process.wait()
    finally:
        stop.set()
        guard.join(timeout=5)
        gpu.stop()
        ram.stop()
        (out/'resources.json').write_text(json.dumps({'violations':violations,
            'gpu_peak_mib':gpu.peak_mib, 'gpu_telemetry_available':gpu.telemetry_available,
            'ram_peak_mib':ram.peak_mib, 'seconds':round(time.monotonic()-started,3)},indent=2)+'\n',encoding='utf-8')
(out/'EXIT.json').write_text(json.dumps({'exitCode':code,'manifest_unchanged':sha(manifest)==prereg['manifest_sha256']},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'exitCode':code,'private':str(private)}),flush=True)
raise SystemExit(code)



