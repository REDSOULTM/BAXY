"""Same Spanish ONNX voice; isolate eSpeak language for real English responses."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import sys
import time
import wave

import numpy as np
import psutil
from scipy.signal import resample_poly
import sherpa_onnx

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind.voice_output import _PiperOnnxEngine, resolve_neural_tts_model
out=root/'artifacts/comprobaciones/C03/astra-native-tts113'
out.mkdir(exist_ok=False)
assert not any(p.info['name'] in {'Baxy.exe','llama-server.exe'} for p in psutil.process_iter(['name']))
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
manifest_path=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
model=resolve_neural_tts_model()
assert model is not None and sha(model)==manifest['tts_sha256']
cases=['It is 07:14.', 'The file read failed because the content is invalid UTF-8.',
       "I couldn't read the file because it wasn't found in the sandbox."]
prereg={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'method':'Source112 with correct PAD, same registered es_MX-claude-high ONNX voice, '
 'CPU/default inference scales. Three consumed English responses from audio110/UI104. '
 'Compare configured es-419 phonemizer against en-us only; no new model, source '
 'language classifier or playback. Transcribe PCM with same registered Parakeet CPU '
 'without expected-text prompt/hotwords. Native evidence cannot certify physical audio.',
 'cases':cases,'voices':['es-419','en-us'],'model':str(model),'modelSha256':sha(model),
 'configSha256':sha(model.with_suffix('.onnx.json')),
 'sourceSha256':sha(root/'src/baxy_mind/voice_output.py'),'registrationSha256':sha(manifest_path)}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
tts=_PiperOnnxEngine(model)
stt=Path(manifest['stt_dir'])
recognizer=sherpa_onnx.OfflineRecognizer.from_transducer(
 encoder=str(stt/'encoder.int8.onnx'),decoder=str(stt/'decoder.int8.onnx'),
 joiner=str(stt/'joiner.int8.onnx'),tokens=str(stt/'tokens.txt'),num_threads=6,
 model_type='nemo_transducer',decoding_method='modified_beam_search',max_active_paths=8)
rows=[]
for index,text in enumerate(cases):
    for voice in prereg['voices']:
        tts._voice=voice
        phonemes=tts._phonemes(text)
        start=time.monotonic()
        pcm=tts.generate(text)
        seconds=time.monotonic()-start
        path=out/f'{index:02d}-{voice}.wav'
        with wave.open(str(path),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(tts.sample_rate)
            wav.writeframes((pcm*32767).astype('<i2').tobytes())
        stream=recognizer.create_stream()
        stream.accept_waveform(16000,resample_poly(pcm,16000,tts.sample_rate).astype(np.float32))
        recognizer.decode_stream(stream)
        row={'index':index,'text':text,'phonemizerVoice':voice,'phonemes':phonemes,
            'unknownPhonemes':sorted(set(phonemes)-set(tts._id_map)),
            'seconds':pcm.size/tts.sample_rate,'generationSeconds':seconds,
            'transcript':str(stream.result.text or '').strip(),'wavSha256':sha(path)}
        rows.append(row)
        (out/'RESULTS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(row,ensure_ascii=False),flush=True)
assert sha(root/'src/baxy_mind/voice_output.py')==prereg['sourceSha256']
