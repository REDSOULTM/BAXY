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
out = root/'artifacts/comprobaciones/C03/astra-private-product515-base'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-private-product515-base-private'
out.mkdir(exist_ok=True)
private.mkdir(exist_ok=True)
assert not (out/'PREREG.json').exists() and not (out/'PROCESS.json').exists()
assert not (private/'http-posts.jsonl').exists()
cases = ['My name is Jordan. Remember my name.', 'confirm', 'Abre una aplicación.', 'What name have you saved in private memory?', 'Me llamo Álvaro.', 'Abre una aplicación.', '¿Qué nombre tienes guardado en tu memoria privada?', '¿Cómo me llamo?', 'Desactiva la memoria privada.']

commands = [{'cmd':'turn','text':request} for request in cases]
turns = private/'turns.jsonl'
turns.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in commands),encoding='utf-8')
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
manifest = Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
config=json.loads(manifest.read_text(encoding='utf-8-sig'))
assert sha(manifest)=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
model=Path(config['gguf'])
assert sha(model)=='3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
assert not (private.parent/'C03-private-profile515-base').exists()
prereg = {
    'utc':datetime.now(timezone.utc).isoformat(),
    'production_verification': '515 base: source512 actual product, registered runtime, same9cases; see astra-memory-view515/PREREG.json. Only treatment mutates the writer view, never replies or source.',
    'method': 'Compare actual memory narration and preserve private/core/confirmation behavior; no profile tuning or model ranking.',
    'profile_inheritance':'New dedicated LOCALAPPDATA/BAXY child with persistence initially disabled. A synthetic Jordan save is explicitly requested; the exact product enable confirmation is accepted and its bound name save may resume. Later Alvaro declaration does not authorize overwriting that persisted name. All effects and journal remain inside the diagnostic profile; owner memory is outside scope.',
    'criteria': 'T1 honestly requests enabling, T2 accepts exact pending enable and resumes authorized synthetic save. T3/T6 clarify the missing application without inventing a target; T4/T7 perform a private recall despite that pending public clarification. Stored name is Jordan, current conversational name is Alvaro, with correct human subject and no unrequested overwrite. Prose failure is separate from successful private dispatch. Check every final, operation and native call; admission200 is not acceptance.',
    'cases':cases,
    'source_sha256':{name:sha(root/name) for name in ['src/baxy_mind/effect_intent.py','src/baxy_mind/__main__.py','src/baxy_mind/llm.py']},
    'manifest_sha256':sha(manifest),
    'registered_model':{'path':str(model),'sha256':sha(model)},
    'registered_backend':{'path':config['llama_server'],'sha256':sha(Path(config['llama_server']))},
    'sources':{name:sha(root/name) for name in ['src/baxy_mind/__main__.py','src/baxy_mind/request_reading.py','src/baxy_mind/effect_intent.py','src/baxy_mind/llm.py','src/Baxy.App/MainWindowViewModel.cs','src/Baxy.App/UserMessagePolicy.cs','src/Baxy.App/MemoryTurnSession.cs','src/Baxy.App/NaturalMemoryRequestParser.cs','src/Baxy.App/PrivateOperationNarration.cs','src/Baxy.App/MemoryOperationResponseProjection.cs','src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll']},
    'private':str(private),
    'resource_limits':{'gpu_stop_mib':3800, 'minimum_free_ram_mib':768, 'wall_time_seconds':240, 'scope':'owned hidden diagnostic process tree, no physical voice; stop only that tree on bound'},
}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
env=os.environ.copy()
for name in list(env):
    if name.startswith(('BAXY_MIND_','BAXY_VOICE_','BAXY_C03_','BAXY_FIELD_')) or name in {'PYTHONPATH','BAXY_DATA_DIR','BAXY_ASSET_DESCRIPTOR','BAXY_APP_TRACE'}:
        env.pop(name,None)
env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_PYTHONPATH=str(root/'scratchpad/c03-owner515-base-hook')+os.pathsep+str(root/'src'), BAXY_VOICE_WAKE_ON_START='0',
    BAXY_APP_TRACE=str(private/'shell-trace.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH=str(private/'compose-audit.jsonl'),
    BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT='1',
    BAXY_MIND_TURN_AUDIT_PATH=str(private/'turn-audit.jsonl'),
    BAXY_MIND_RAW_REPLY_AUDIT_PATH=str(private/'raw-replies.jsonl'))
command=['py','main.py','--conductor','--profile',str(private.parent/'C03-private-profile515-base'),
    '--capture',str(private/'capture'),'--turns-file',str(turns),'--timeout-ms','120000']
with (private/'launch.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen(command,cwd=root,env=env,stdin=subprocess.DEVNULL,
        stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'PROCESS.json').write_text(json.dumps({'launcher':process.pid,'command':command},indent=2)+'\n',encoding='utf-8')
    gpu, ram = ProcessTreeGpuSampler(process.pid), RamSampler(process.pid)
    stop = threading.Event()
    violations = []
    memory_samples = []
    started = time.monotonic()
    def watch_resources():
        while not stop.wait(0.25):
            rows = []
            try:
                owned = psutil.Process(process.pid)
                for child in [owned, *owned.children(recursive=True)]:
                    try:
                        info = child.memory_info()
                        rows.append({'pid':child.pid, 'parent':child.ppid(), 'name':child.name(),
                            'command':child.cmdline(), 'rss_mib':info.rss/2**20, 'private_mib':getattr(info,'private',0)/2**20})
                    except (psutil.NoSuchProcess,psutil.AccessDenied):
                        pass
            except psutil.NoSuchProcess:
                pass
            memory_samples.append({'elapsed':round(time.monotonic()-started,3),
                'available_mib':psutil.virtual_memory().available/2**20, 'processes':rows})
            if time.monotonic()-started>240:
                violations.append('scenario_wall_time_bound')
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
        (private/'memory-samples.json').write_text(json.dumps(memory_samples,indent=2)+'\n',encoding='utf-8')
        gpu.stop()
        ram.stop()
        (out/'resources.json').write_text(json.dumps({'violations':violations,
            'gpu_peak_mib':gpu.peak_mib, 'gpu_telemetry_available':gpu.telemetry_available,
            'ram_peak_mib':ram.peak_mib, 'seconds':round(time.monotonic()-started,3)},indent=2)+'\n',encoding='utf-8')
(out/'EXIT.json').write_text(json.dumps({'exitCode':code,'manifest_unchanged':sha(manifest)==prereg['manifest_sha256']},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'exitCode':code,'private':str(private)}),flush=True)
raise SystemExit(code)



