"""One native TTS difference: model PAD ids, same phonemes/config/runtime."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import sys
import time
import wave

import numpy as np
import onnxruntime as ort
import psutil
from scipy.signal import resample_poly
import sherpa_onnx

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from baxy_mind.voice_output import _PiperOnnxEngine, resolve_neural_tts_model
out=root/'artifacts/comprobaciones/C03/astra-native-tts111'
out.mkdir(exist_ok=False)
assert not any(p.info['name'] in {'Baxy.exe','llama-server.exe'} for p in psutil.process_iter(['name']))
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
model=resolve_neural_tts_model()
assert model is not None
manifest_path=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
assert sha(model)==manifest['tts_sha256']
cases=['¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?','Son las 07:13.','It is 07:14.','Son las 07:15.']
prereg={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'method':'Native CPU ONNX TTS only, no playback, UI, microphone or LLM. Same four '
  'literal visible responses from audio110, same registered ONNX voice/config, '
  'espeak CLI phonemes and inference scales. Compare current ids without PAD '
  'against official Piper framing with PAD after each mapped phoneme, same BOS/EOS. '
  'Independently transcribe raw PCM with registered offline STT on CPU, no expected '
  'text prompt/hotwords. Keep both raw WAVs/phonemes/ids/durations/decodes. No source edits.',
 'cases':cases,'model':str(model),'modelSha256':sha(model),
 'configSha256':sha(model.with_suffix('.onnx.json')),
 'sourceSha256':sha(root/'src/baxy_mind/voice_output.py'),
 'registrationSha256':sha(manifest_path),
 'source':'https://raw.githubusercontent.com/rhasspy/piper/master/src/python_run/piper/voice.py',
 'sourceConsulted':'2026-09-07; phonemes_to_ids adds mapped PAD after each known phoneme',
 'runtime':{'onnxruntime':ort.__version__}}
(out/'PREREG.json').write_text(json.dumps(prereg,ensure_ascii=False,indent=2),encoding='utf-8')
tts=_PiperOnnxEngine(model)
stt=Path(manifest['stt_dir'])
recognizer=sherpa_onnx.OfflineRecognizer.from_transducer(
 encoder=str(stt/'encoder.int8.onnx'),decoder=str(stt/'decoder.int8.onnx'),
 joiner=str(stt/'joiner.int8.onnx'),tokens=str(stt/'tokens.txt'),num_threads=6,
 model_type='nemo_transducer',decoding_method='modified_beam_search',max_active_paths=8)
rows=[]
for index,text in enumerate(cases):
    phonemes=tts._phonemes(text)
    for variant in ['without_pad','with_pad']:
        ids=list(tts._id_map['^'])
        for character in phonemes:
            if character not in tts._id_map:
                continue
            ids.extend(tts._id_map[character])
            if variant=='with_pad':
                ids.extend(tts._id_map['_'])
        ids.extend(tts._id_map['$'])
        started=time.monotonic()
        pcm=np.asarray(tts._session.run(None,{'input':np.array([ids],dtype=np.int64),
            'input_lengths':np.array([len(ids)],dtype=np.int64),
            'scales':np.array([tts._noise_scale,tts._length_scale,tts._noise_w],dtype=np.float32)})[0],dtype=np.float32).reshape(-1)
        peak=float(np.max(np.abs(pcm))) if pcm.size else 0.0
        if peak>1:
            pcm=pcm/peak
        seconds=time.monotonic()-started
        path=out/f'{index:02d}-{variant}.wav'
        with wave.open(str(path),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(tts.sample_rate)
            wav.writeframes((pcm*32767).astype('<i2').tobytes())
        samples=resample_poly(pcm,16000,tts.sample_rate).astype(np.float32)
        stream=recognizer.create_stream()
        stream.accept_waveform(16000,samples)
        recognizer.decode_stream(stream)
        row={'index':index,'text':text,'variant':variant,'phonemes':phonemes,'ids':ids,
             'unknownPhonemes':sorted(set(phonemes)-set(tts._id_map)),
             'sampleRate':tts.sample_rate,'seconds':pcm.size/tts.sample_rate,'generationSeconds':seconds,
             'peak':peak,'rms':float(np.sqrt(np.mean(pcm**2))) if pcm.size else 0,
             'transcript':str(stream.result.text or '').strip(),'wavSha256':sha(path)}
        rows.append(row)
        (out/'RESULTS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in row.items() if k not in {'ids','phonemes'}},ensure_ascii=False),flush=True)
assert sha(root/'src/baxy_mind/voice_output.py')==prereg['sourceSha256']
assert sha(manifest_path)==prereg['registrationSha256']
