from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-voice149'
out.mkdir(exist_ok=False)
source = (root / 'scratchpad/c03-capture-voice148.py').read_text(encoding='utf-8')
(root / 'scratchpad/c03-capture-voice149.py').write_text(source.replace('voice148', 'voice149'), encoding='utf-8')
source = (root / 'scratchpad/c03-voice148.py').read_text(encoding='utf-8').replace('voice148', 'voice149')
tap = '''
import numpy as np
import baxy_mind.voice as voice_module
from baxy_mind.speex_aec import EchoCanceller
from baxy_mind.voice_aec import LoopbackReference

tap_rows, tap_mic, tap_ref, tap_clean, tap_anchor = [], [], [], [], []
original_process = EchoCanceller.process
original_vad = voice_module.SileroVad.process
original_index = LoopbackReference.sample_index
original_guard = voice_module._looks_like_echo

def observed_process(self, mic, reference):
    begin = time.perf_counter()
    result = original_process(self, mic, reference)
    tap_mic.append(mic.copy())
    tap_ref.append(reference.copy())
    tap_clean.append(result[0].copy())
    tap_rows.append({'time': begin, 'aecEnd': time.perf_counter()})
    return result

def observed_vad(self, frame):
    result = original_vad(self, frame)
    tap_rows[-1]['probability'] = float(result)
    return result

def observed_index(self, adc, event, **kwargs):
    result = original_index(self, adc, event, **kwargs)
    tap_anchor.append({'micAdc': adc, 'loopOrigin': self._origin_time,
                       'cursorStart': result, 'written': self._written})
    return result

def observed_guard(mic, reference):
    result = original_guard(mic, reference)
    if tap_rows:
        tap_rows[-1]['echoGuard'] = bool(result)
    return result

EchoCanceller.process = observed_process
voice_module.SileroVad.process = observed_vad
LoopbackReference.sample_index = observed_index
voice_module._looks_like_echo = observed_guard
'''
source = source.replace('engine = VoiceEngine(transcript, event)', tap + '\nengine = VoiceEngine(transcript, event)')
source += '''
np.savez(private/'tap149.npz', microphone=np.asarray(tap_mic), reference=np.asarray(tap_ref), clean=np.asarray(tap_clean))
(private/'tap149.json').write_text(json.dumps({'anchor': tap_anchor, 'frames': tap_rows}, indent=2), encoding='utf-8')
index = [{'privatePath': str(private/name), 'sha256': sha(private/name)} for name in ['tap149.json', 'tap149.npz']]
(out/'OBSERVATION_INDEX.json').write_text(json.dumps(index, indent=2), encoding='utf-8')
'''
(root / 'scratchpad/c03-voice149.py').write_text(source, encoding='utf-8')
prior = json.loads((root / 'artifacts/comprobaciones/C03/astra-voice148/PREREG.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((root / p).read_bytes()).hexdigest() == digest for p, digest in prior['sources'].items())
prior.update(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    method='Source147 observational tap only: original AEC/VAD/guard outputs returned unchanged, mic/reference/clean copies and initial cursor recorded privately, no second VAD or shadow branch. Same physical phrase/direct/0.30. Observation overhead may change timing; not acceptance.',
    criteria='Locate actual mic/reference delay, clean speech/VAD/guard at interruption; diagnose148 without attributing unrecorded frames to it. No source mutation/threshold change.')
(out / 'PREREG.json').write_text(json.dumps(prior, indent=2), encoding='utf-8')
print(out)
