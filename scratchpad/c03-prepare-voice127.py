from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-voice127'
out.mkdir(exist_ok=False)
capture = (root / 'scratchpad/c03-capture-voice125.py').read_text(encoding='utf-8').replace('125', '127')
with (root / 'scratchpad/c03-capture-voice127.py').open('x', encoding='utf-8') as f:
    f.write(capture)
driver = (root / 'scratchpad/c03-voice125.py').read_text(encoding='utf-8').replace('125', '127')
observer = '''
import numpy as np
import baxy_mind.voice as voice_module
vad_rows = []
echo_rows = []
mic_frames = []
echo_microphones = []
echo_references = []
original_vad = voice_module.SileroVad.process
original_echo = voice_module._looks_like_echo

def observe_vad(self, frame):
    probability = original_vad(self, frame)
    vad_rows.append({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     'probability': probability, 'rms': float(np.sqrt(np.mean(frame ** 2)))})
    mic_frames.append(frame.copy())
    return probability

def observe_echo(microphone, reference):
    before = time.perf_counter()
    answer = original_echo(microphone, reference)
    echo_rows.append({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'vadIndex': len(vad_rows) - 1, 'echo': answer,
                      'detectorSeconds': time.perf_counter() - before})
    echo_microphones.append(microphone.copy())
    echo_references.append(reference.copy())
    return answer

voice_module.SileroVad.process = observe_vad
voice_module._looks_like_echo = observe_echo
'''
driver = driver.replace('engine = VoiceEngine(transcript, event)', observer + '\nengine = VoiceEngine(transcript, event)')
driver = driver.replace('    engine.shutdown()\n', '''    engine.shutdown()
    voice_module.SileroVad.process = original_vad
    voice_module._looks_like_echo = original_echo
    np.savez_compressed(private / 'runtime-observations.npz', microphone=mic_frames,
                        echo_microphone=echo_microphones, echo_reference=echo_references)
    (private / 'runtime-observations.json').write_text(
        json.dumps({'vad': vad_rows, 'echo': echo_rows}, indent=2), encoding='utf-8')
''')
with (root / 'scratchpad/c03-voice127.py').open('x', encoding='utf-8') as f:
    f.write(driver)
sources = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in [
    'src/baxy_mind/voice.py', 'src/baxy_mind/voice_output.py',
    'src/baxy_mind/piper_tts.py', 'src/baxy_mind/voice_aec.py']}
prereg = {
    'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'sources': sources, 'phases': ['direct'],
    'text': 'The file read failed because the content is invalid UTF-8.',
    'method': 'Same physical direct-mode case125/source119+124. Observe exact VAD input/probability and echo detector input/reference/result with delegating wrappers; return values unchanged. No source edits, transcript routing, App or LLM. Captures private, volume restoration unchanged. Instrumentation can affect timing; this is diagnostic, not UI acceptance.',
    'hypothesis': 'Analysis126 finds full physical phrase off/off and incomplete direct; inspect actual reference and counted frames before choosing another implementation.',
}
(out / 'PREREG.json').write_text(json.dumps(prereg, indent=2), encoding='utf-8')
print('127 prepared; no playback yet.')
