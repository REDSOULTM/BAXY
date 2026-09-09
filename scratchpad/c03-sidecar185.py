"""Full JSONL/LLM sidecar voice startup with the observed App configuration."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time

import psutil

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from scripts.measure_mind_budget import JsonLineProcess, current_core_catalog_snapshot, default_core_candidates

base=root/'artifacts/comprobaciones/C03'
out=base/'astra-sidecar185'
assert (out/'AUDIO_READY.json').exists()
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-sidecar185-private'
assert private.is_dir()
assert not any(p.info['name'] in {'Baxy.exe','llama-server.exe','piper.exe'} for p in psutil.process_iter(['name']))
processes=json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-audio158-private/process158.json').read_text(encoding='utf-8'))
observed=next(p for p in processes if p['name']=='python.exe' and p['cmdline'][-1]=='baxy_mind')
env=os.environ.copy()
for key in list(env):
    if key.startswith(('BAXY_MIND_','BAXY_VOICE_','BAXY_C03_','BAXY_FIELD_')):
        env.pop(key)
env.update(observed['selectedEnvironment'])
env.update(BAXY_MIND_LLAMA_SERVER='D:/BAXYRuntime/assets/llama-b9980-cuda12.4/llama-server.exe',
    BAXY_MIND_NGL='99',BAXY_MIND_STT_DIR='D:/BAXYRuntime/assets/stt/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8',HF_HUB_OFFLINE='1')
capabilities,_,_=current_core_catalog_snapshot(next(p for p in default_core_candidates() if p.is_file()))
(private/'catalog.json').write_text(json.dumps(capabilities),encoding='utf-8')
(out/'RUNTIME_CONFIG.json').write_text(json.dumps({'method':'Product source172 with experimental DTLN128 binding182, no source modification. Actual current Core catalog169, Qwen3.5 override/profile and observed App voice env. Sequence hello/catalog/status/speak greeting/start wake. Only timed faulthandler entry and protocol observation; no App/UI/volume changes. Same existing uncalibrated wake seam, not acceptance.',
    'capabilities':len(capabilities),'criterion':'Locate first stalled operation and native/Python thread stack. Do not enlarge product timeouts or reinterpret uncalibrated wake as approved.'},indent=2),encoding='utf-8')

class ObservedProcess(JsonLineProcess):
    def _read_stdout(self):
        try:
            with (private/'messages.jsonl').open('w',encoding='utf-8') as log:
                for line in self._process.stdout:
                    if not line.strip():
                        continue
                    value=json.loads(line)
                    log.write(json.dumps({'time':time.monotonic(),'message':value},ensure_ascii=False)+'\n')
                    log.flush()
                    self._messages.put(value)
            self._messages.put(EOFError('sidecar_stdout_closed'))
        except BaseException as error:
            self._messages.put(error)

    def _read_stderr(self):
        with (private/'stderr.log').open('w',encoding='utf-8') as log:
            for line in self._process.stderr:
                log.write(line)
                log.flush()

client=ObservedProcess([observed['cmdline'][0],'-u','-X','utf8',str(root/'scratchpad/c03-sidecar185-entry.py')],environment=env,cwd=root)
texts=json.loads((out/'PREREG.json').read_text(encoding='utf-8'))['texts']
rows=[]
started=time.monotonic()
try:
    hello=client.next_message(30)
    assert hello['type']=='hello'
    rows.append({'stage':'hello','elapsed':time.monotonic()-started})
    sequence=[({'type':'catalog.configure','id':'catalog','capabilities':capabilities},120),
        ({'type':'voice.status','id':'status'},10),
        ({'type':'voice.speak','id':'speak','text':texts[0]},10),
        ({'type':'voice.start','id':'start','mode':'wake'},60)]
    sequence.extend(({'type':'voice.speak','id':f'speak{index}','text':value},10) for index,value in enumerate(texts[1:],1))
    for message,timeout in sequence:
        first=time.monotonic()
        reply=client.request(message,timeout)
        row={'stage':message['type'],'seconds':time.monotonic()-first,'reply':reply}
        rows.append(row)
        (out/'RESULTS.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
        print(json.dumps({'stage':row['stage'],'seconds':row['seconds'],'type':reply.get('type'),'mode':reply.get('mode'),'status':reply.get('status')}),flush=True)
        if message['type']=='voice.start' or str(message.get('id','')).startswith('speak1') or str(message.get('id','')).startswith('speak2') or str(message.get('id','')).startswith('speak3'):
            time.sleep(10)
except Exception as error:
    (out/'FAILURE.json').write_text(json.dumps({'error':repr(error),'elapsed':time.monotonic()-started},indent=2),encoding='utf-8')
    raise
finally:
    try:
        owned=[(p,p.create_time()) for p in psutil.Process(client.pid).children(recursive=True)]
    except psutil.Error:
        owned=[]
    if client._process.poll() is None:
        try:
            client.send({'type':'shutdown','id':'shutdown'})
            client._process.wait(timeout=10)
        except (OSError,subprocess.TimeoutExpired):
            subprocess.run(['taskkill','/PID',str(client.pid),'/T','/F'],capture_output=True)
            client._process.wait(timeout=10)
    for proc,creation in owned:
        try:
            if proc.is_running() and proc.create_time()==creation:
                proc.kill()
                proc.wait(timeout=5)
        except psutil.NoSuchProcess:
            pass
    (out/'CLEANUP.json').write_text(json.dumps({'exitCode':client._process.returncode,'seconds':time.monotonic()-started}),encoding='utf-8')
    names=['messages.jsonl','stderr.log','stacks185.log','catalog.json','tts-state.jsonl']
    names.extend(name for name in ['barge185.npz','barge185.json'] if (private/name).is_file())
    indexes=[]
    for name in names:
        p=private/name
        with p.open('rb') as f:
            sha=hashlib.file_digest(f,'sha256').hexdigest()
        indexes.append({'privatePath':str(p),'sha256':sha,'bytes':p.stat().st_size})
    (out/'INDEX.json').write_text(json.dumps(indexes,indent=2),encoding='utf-8')
    (out/'STOP_AUDIO').touch(exist_ok=True)

(out/'STOP_AUDIO').touch(exist_ok=True)
