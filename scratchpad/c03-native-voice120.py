"""Actual source119 voice queue and Piper, with an explicit PCM sink instead of a device."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import sys
import threading
import time
from types import SimpleNamespace
import wave

import numpy as np
import psutil
from scipy.signal import resample_poly
import sherpa_onnx

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
sys.stdout.reconfigure(encoding='utf-8')
from baxy_mind.voice_output import NeuralSpeechOutput
from baxy_mind.piper_tts import PiperEngine, resolve_neural_tts_model, resolve_piper_executable
out = root / 'artifacts/comprobaciones/C03/astra-native-voice120'
out.mkdir(exist_ok=False)
assert not any(p.info['name'] in {'Baxy.exe', 'llama-server.exe', 'piper.exe'} for p in psutil.process_iter(['name']))
def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
manifest_path = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
assert sha(manifest_path) == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
models = {lang: resolve_neural_tts_model(lang) for lang in ('es', 'en')}
exe = resolve_piper_executable()
assert exe is not None and all(models.values())
cases = [
    {'language': 'es', 'text': '¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?'},
    {'language': 'en', 'text': 'It is 07:14.'},
    {'language': 'es', 'text': 'Son las 07:13.'},
    {'language': 'en', 'text': 'The file read failed because the content is invalid UTF-8.'},
    {'language': 'es', 'text': 'Son las 07:15.'},
    {'language': 'en', 'text': "I couldn't read the file because it wasn't found in the sandbox."},
]
sources = ['src/baxy_mind/piper_tts.py', 'src/baxy_mind/voice_output.py',
           'src/baxy_mind/request_reading.py', 'src/baxy_mind/voice.py', 'assets.manifest.json']
prereg = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'method': 'Source119 actual NeuralSpeechOutput queue, language selection, identity and Piper '
                    'provider. Only sounddevice.OutputStream is replaced by explicit PCM sink, '
                    'no physical playback, mic, UI, LLM or human reserve. Six consumed118 texts in '
                    'alternating ES/EN order; same registered Parakeet CPU/no hints. Measure ready '
                    'PCM time, not physical playback time. After content, cancel a real owned Piper '
                    'child during synthesis, observe its PID, require reaping. No registered promotion.',
          'cases': cases, 'sources': {p: sha(root / p) for p in sources},
          'registrationSha256': sha(manifest_path),
          'models': {lang: {'path': str(p), 'sha256': sha(p), 'configSha256': sha(p.with_suffix('.onnx.json'))} for lang, p in models.items()},
          'runtime': str(exe), 'runtimeSha256': sha(exe)}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2), encoding='utf-8')
for p in sources:
    target = out / 'source' / p
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((root / p).read_bytes())
finished = threading.Event()
captured = {}
class Sink:
    def __init__(self, **options):
        captured.clear()
        captured.update(rate=options['samplerate'], chunks=[], owner=threading.get_ident(), closed=False)
    def __enter__(self):
        return self
    def write(self, pcm):
        assert threading.get_ident() == captured['owner']
        captured['chunks'].append(pcm.copy())
    def abort(self):
        captured['aborted'] = True
    def __exit__(self, *_):
        captured['closed'] = True
sys.modules['sounddevice'] = SimpleNamespace(OutputStream=Sink)
stt = Path(manifest['stt_dir'])
recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=str(stt / 'encoder.int8.onnx'), decoder=str(stt / 'decoder.int8.onnx'),
    joiner=str(stt / 'joiner.int8.onnx'), tokens=str(stt / 'tokens.txt'), num_threads=6,
    model_type='nemo_transducer', decoding_method='modified_beam_search', max_active_paths=8)
output = NeuralSpeechOutput(lambda speaking: finished.set() if not speaking else None)
rows = []
try:
    for index, case in enumerate(cases):
        finished.clear()
        start = time.monotonic()
        assert output.speak(case['text'])
        assert finished.wait(35), output.last_error
        ready = time.monotonic() - start
        assert output.last_error is None and captured['closed'] and not captured.get('aborted')
        assert output.voice_sha256 == prereg['models'][case['language']]['sha256']
        pcm = np.concatenate(captured['chunks'])
        rate = captured['rate']
        path = out / f'{index:02d}-queue.wav'
        with wave.open(str(path), 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate)
            wav.writeframes((pcm * 32768).astype('<i2').tobytes())
        stream = recognizer.create_stream()
        stream.accept_waveform(16000, resample_poly(pcm, 16000, rate).astype(np.float32))
        recognizer.decode_stream(stream)
        row = {'index': index, **case, 'voice': output.voice_name, 'voiceSha256': output.voice_sha256,
               'pcmReadySeconds': ready, 'audioSeconds': len(pcm) / rate,
               'transcript': str(stream.result.text or '').strip(), 'wavSha256': sha(path)}
        rows.append(row)
        (out / 'RESULTS.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(row, ensure_ascii=False), flush=True)
finally:
    assert output.stop(timeout=5)

cancel = threading.Event()
outcome = {}
engine = PiperEngine(models['en'])
def synthesize():
    try:
        engine.generate('A technical cancellation probe. ' * 120, cancelled=cancel.is_set)
        outcome['result'] = 'completed_before_cancel'
    except BaseException as error:
        outcome['result'] = type(error).__name__
worker = threading.Thread(target=synthesize)
worker.start()
owned = None
deadline = time.monotonic() + 5
while time.monotonic() < deadline and worker.is_alive():
    for child in psutil.Process().children():
        if Path(child.exe()).resolve() == exe.resolve():
            owned = {'pid': child.pid, 'created': child.create_time()}
            break
    if owned is not None:
        break
    time.sleep(0.01)
start = time.monotonic()
cancel.set()
worker.join(5)
outcome.update(observedChild=owned, cancelAndJoinSeconds=time.monotonic() - start, workerStopped=not worker.is_alive())
if owned is not None:
    try:
        still_owned = psutil.Process(owned['pid']).create_time() == owned['created']
    except psutil.NoSuchProcess:
        still_owned = False
    outcome['childReaped'] = not still_owned
(out / 'CANCELLATION.json').write_text(json.dumps(outcome, indent=2), encoding='utf-8')
assert owned and outcome['result'] == 'InterruptedError' and outcome['workerStopped'] and outcome['childReaped'], outcome
assert sha(manifest_path) == prereg['registrationSha256']
assert all(sha(root / p) == digest for p, digest in prereg['sources'].items())
print(json.dumps(outcome), flush=True)
