"""Reintroduce registered mind around the successful native voice control."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.measure_mind_budget import JsonLineProcess, current_core_catalog_snapshot, ProcessTreeGpuSampler, RamSampler
from scripts.baxy_runtime_config import resolve_runtime

OUT = ROOT / 'artifacts/comprobaciones/C03/astra-native-sidecar45'
OUT.mkdir(exist_ok=False)
manifest_path = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
manifest_bytes = manifest_path.read_bytes()
manifest = json.loads(manifest_bytes)
runtime = resolve_runtime(manifest_path=manifest_path)
capabilities, applications, games = current_core_catalog_snapshot(ROOT / 'src/Baxy.Core/bin/Release/net10.0-windows10.0.19041.0/win-x64/publish/baxy-core.exe')
env = os.environ.copy()
for key in list(env):
    if key.startswith(('BAXY_MIND_', 'BAXY_VOICE_')) or key == 'PYTHONPATH':
        del env[key]
env.update(PYTHONPATH=str(runtime.python_path), PYTHONUTF8='1', PYTHONFAULTHANDLER='1', HF_HUB_OFFLINE='1',
           BAXY_MIND_LLM_GGUF=str(runtime.gguf), BAXY_MIND_LLAMA_SERVER=str(runtime.llama_server), BAXY_MIND_NGL=str(runtime.gpu_layers),
           BAXY_MIND_STT_DIR=manifest['stt_dir'], BAXY_VOICE_WAKE_MANIFEST=manifest['wake_manifest'], BAXY_VOICE_WAKE_CASCADE_MANIFEST=manifest['wake_manifest'],
           BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED='1', BAXY_VOICE_WAKE_ON_START='1')
(OUT / 'PREREG.json').write_text(json.dumps({'method': 'Authenticated core catalog, registered sidecar, voice status/speak/wake, wait40s, cancel and conversational turn, status and shutdown. Adds real mind to voice-only control; no UI or fresh acceptance. Native faulthandler stderr capture.', 'registrationSha256': hashlib.sha256(manifest_bytes).hexdigest(), 'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2), encoding='utf-8')

class DiagnosticClient(JsonLineProcess):
    def _read_stderr(self):
        with (OUT / 'native-stderr.log').open('w', encoding='utf-8') as log:
            for line in self._process.stderr:
                log.write(line)
                log.flush()

started = time.monotonic()
client = DiagnosticClient([str(runtime.python), '-X', 'utf8', '-m', 'baxy_mind'], environment=env, cwd=ROOT)
gpu, ram = ProcessTreeGpuSampler(client.pid), RamSampler(client.pid)
gpu.start(); ram.start()
events = (OUT / 'events.jsonl').open('w', encoding='utf-8')

def record(kind, value):
    events.write(json.dumps({'seconds': round(time.monotonic()-started, 3), 'kind': kind, 'value': value}, ensure_ascii=False) + '\n')
    events.flush()

def request(kind, **kwargs):
    message = {'type': kind, 'id': str(time.monotonic_ns()), **kwargs}
    record('request', message)
    reply = client.request(message, 90)
    record('reply', reply)
    return reply

failure = None
try:
    record('hello', client.next_message(120))
    request('catalog.configure', capabilities=capabilities, applicationCatalog=applications, gameCatalog=games)
    request('voice.status')
    request('voice.speak', text='¡Hola! ¿Cómo estás?')
    time.sleep(5)
    request('voice.start', mode='wake')
    time.sleep(40)
    request('voice.cancel')
    request('turn.decide', text='hola quien eres', history=[])
    request('voice.status')
except Exception as error:
    failure = type(error).__name__ + ':' + str(error)
    record('failure', failure)
finally:
    children = []
    try:
        children = psutil.Process(client.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        pass
    client.close(graceful_message={'type': 'shutdown', 'id': 'stop'}, timeout=20)
    for child in reversed(children):
        try:
            if child.is_running():
                child.terminate()
        except psutil.NoSuchProcess:
            pass
    gpu.stop(); ram.stop(); events.close()
result = {'exitCode': client._process.returncode, 'failure': failure, 'seconds': round(time.monotonic()-started, 3), 'gpuPeakMiB': gpu.peak_mib, 'ramPeakMiB': ram.peak_mib, 'registrationUnchanged': manifest_path.read_bytes() == manifest_bytes}
(OUT / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result), flush=True)
