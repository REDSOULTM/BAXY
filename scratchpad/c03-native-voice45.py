"""Bounded native diagnostic of the registered voice stack, not acceptance."""
from pathlib import Path
import faulthandler
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/comprobaciones/C03/astra-native-voice45'

if '--child' in sys.argv:
    faulthandler.enable(all_threads=True)
    faulthandler.dump_traceback_later(50, repeat=True)
    sys.path.insert(0, str(ROOT / 'src'))
    from baxy_mind.voice import VoiceEngine

    def record(kind, value):
        print(json.dumps({'seconds': round(time.monotonic()-started, 3), 'kind': kind, 'value': value}, ensure_ascii=False), flush=True)

    started = time.monotonic()
    voice = VoiceEngine(lambda text: record('transcript', text), lambda event: record('event', event))
    record('status.before', voice.status())
    record('speak', voice.speak('¡Hola! ¿Cómo estás?'))
    time.sleep(5)
    record('start.wake', voice.start('wake'))
    record('status.ready', voice.status())
    time.sleep(15)
    voice.cancel_speech()
    record('cancel', True)
    time.sleep(15)
    record('status.after', voice.status())
    record('stop', voice.stop())
    faulthandler.cancel_dump_traceback_later()
    sys.exit(0)

OUT.mkdir(exist_ok=False)
manifest_path = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
manifest_bytes = manifest_path.read_bytes()
manifest = json.loads(manifest_bytes)
env = os.environ.copy()
for key in list(env):
    if key.startswith(('BAXY_MIND_', 'BAXY_VOICE_')) or key == 'PYTHONPATH':
        del env[key]
env.update(PYTHONUTF8='1', HF_HUB_OFFLINE='1', BAXY_MIND_STT_DIR=manifest['stt_dir'],
           BAXY_VOICE_WAKE_MANIFEST=manifest['wake_manifest'], BAXY_VOICE_WAKE_CASCADE_MANIFEST=manifest['wake_manifest'],
           BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED='1', BAXY_VOICE_WAKE_ON_START='1')
(OUT / 'PREREG.json').write_text(json.dumps({'method': 'VoiceEngine alone, registered STT/wake and default TTS asset resolution; greeting, wake start, wait, cancel, wait, stop. Same voice calls as UI; no LLM or shell. faulthandler on stderr, 120-second bound. Development failure isolation only.', 'registrationSha256': hashlib.sha256(manifest_bytes).hexdigest(), 'scriptSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2), encoding='utf-8')
started = time.monotonic()
with (OUT / 'events.jsonl').open('w', encoding='utf-8') as stdout, (OUT / 'native-stderr.log').open('w', encoding='utf-8') as stderr:
    process = subprocess.Popen([manifest['python'], '-X', 'utf8', str(Path(__file__)), '--child'], cwd=ROOT, env=env, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        code = process.wait(timeout=120)
        timed_out = False
    except subprocess.TimeoutExpired:
        process.kill()
        code = process.wait(timeout=10)
        timed_out = True
result = {'exitCode': code, 'timedOut': timed_out, 'seconds': round(time.monotonic()-started, 3), 'registrationUnchanged': manifest_path.read_bytes() == manifest_bytes}
(OUT / 'RESULT.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result), flush=True)
