from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-voice134'
out.mkdir(exist_ok=False)
capture = (root / 'scratchpad/c03-capture-voice125.py').read_text(encoding='utf-8').replace('125', '134')
with (root / 'scratchpad/c03-capture-voice134.py').open('x', encoding='utf-8') as f:
    f.write(capture)
driver = (root / 'scratchpad/c03-voice125.py').read_text(encoding='utf-8').replace('125', '134')
observer = '''
import numpy as np
import baxy_mind.voice as voice_module
from speex_stream134 import SpeexStream
original_vad = voice_module.SileroVad.process
original_echo = voice_module._looks_like_echo
pipeline = None
shadow_vad = None
shadow_floor = .002
shadow_count = 0
previous_pair = (np.zeros(512), np.zeros(4512))
current_pair = previous_pair
observations = []
raw_blocks, clean_blocks, references = [], [], []

def process_candidate(self, frame):
    global previous_pair, current_pair, shadow_floor, shadow_count
    raw = frame.copy()
    history = engine._loopback.latest(4512)
    begin = time.perf_counter()
    clean = pipeline.process(raw, history[-512:])
    cost = time.perf_counter() - begin
    probability = original_vad(shadow_vad, raw)
    rms = float(np.sqrt(np.mean(raw**2)))
    if probability < .5:
        shadow_floor = .98*shadow_floor + .02*rms
    shadow_barge = False
    shadow_echo = None
    if probability >= .5 and engine.speaking:
        shadow_echo = original_echo(raw*32768, history)
        if shadow_echo:
            shadow_count = 0
        elif rms >= max(.004, shadow_floor*1.8):
            shadow_count += 1
            shadow_barge = shadow_count == 3
        else:
            shadow_count = 0
    current_pair = previous_pair
    previous_pair = (raw*32768, history)
    frame[:] = clean
    result = original_vad(self, frame)
    observations.append({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         'rawProbability': probability, 'cleanProbability': result,
                         'rawRms': rms, 'cleanRms': float(np.sqrt(np.mean(clean**2))),
                         'shadowEcho': shadow_echo, 'shadowBarge': shadow_barge,
                         'aecSeconds': cost})
    raw_blocks.append(raw); clean_blocks.append(clean); references.append(history)
    return result

def delayed_echo(_microphone, _reference):
    return original_echo(*current_pair)

voice_module.SileroVad.process = process_candidate
voice_module._looks_like_echo = delayed_echo
'''
driver = driver.replace('engine = VoiceEngine(transcript, event)', observer+'\nengine = VoiceEngine(transcript, event)')
driver = driver.replace('    engine.load()\n', '''    engine.load()
    pipeline = SpeexStream('D:/BAXYRuntime/experiments/voice/speexdsp129/build/speexdsp.dll')
    shadow_vad = voice_module.SileroVad()
''')
driver = driver.replace('    engine.shutdown()\n', '''    engine.shutdown()
    voice_module.SileroVad.process = original_vad
    voice_module._looks_like_echo = original_echo
    if pipeline:
        pipeline.close()
    np.savez_compressed(private / 'candidate134.npz', raw=raw_blocks, clean=clean_blocks, reference=references)
    (private / 'candidate134.json').write_text(json.dumps(observations, indent=2), encoding='utf-8')
    print(json.dumps({'frames':len(observations), 'shadowBargeEvents':sum(r['shadowBarge'] for r in observations)}), flush=True)
''')
with (root / 'scratchpad/c03-voice134.py').open('x', encoding='utf-8') as f:
    f.write(driver)
sources = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in [
    'src/baxy_mind/voice.py', 'src/baxy_mind/voice_output.py', 'src/baxy_mind/piper_tts.py',
    'src/baxy_mind/voice_aec.py', 'scratchpad/speex_stream134.py']}
prereg = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'sources': sources, 'phases': ['direct'],
          'text': 'The file read failed because the content is invalid UTF-8.',
          'method': 'Experimental wrapper preprocesses microphone before VAD/energy, Speex130 defaults/frame512/tail3200, using actual latest loopback512; echo guard sees corresponding prior raw microphone/reference because preprocessor delays one frame. Original raw VAD/guard observed in shadow without cancellation. No product source edit or UI acceptance. Existing later utterance NLMS still exists; transcript content is not an acceptance claim here, and transcripts never routed.',
          'hypothesis': 'Offline133 source125 eight frame phases: raw all interrupt around3.8s, AEC+existing guard none. Test actual loopback scheduling before source integration.',
          'criteria': 'Actual full phrase without own barge-in; compare shadow and capture. Do not relax thresholds or infer physical near-voice preservation from this case.'}
(out / 'PREREG.json').write_text(json.dumps(prereg, indent=2), encoding='utf-8')
print('134 prepared; no playback yet.')
