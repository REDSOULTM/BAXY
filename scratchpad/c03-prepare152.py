from pathlib import Path
import datetime
import hashlib
import json

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-voice152'
out.mkdir(exist_ok=False)
capture=(root/'scratchpad/c03-capture-voice149.py').read_text(encoding='utf-8')
(root/'scratchpad/c03-capture-voice152.py').write_text(capture.replace('149','152'),encoding='utf-8')
source=(root/'scratchpad/c03-voice149.py').read_text(encoding='utf-8').replace('149','152')
source=source.replace("if phase == 'direct':", "if phase.startswith('direct'):")
source=source.replace("tap_rows.append({'time': begin,", "tap_rows.append({'phase': phase, 'time': begin,")
source=source.replace("tap_anchor.append({'micAdc': adc,", "tap_anchor.append({'phase': phase, 'frameIndex': len(tap_rows), 'micAdc': adc,")
source=source.replace("engine = VoiceEngine(transcript, event)", '''
from baxy_mind.piper_tts import PiperEngine
original_generate = PiperEngine.generate
generated = []
def observed_generate(self, text, cancelled=None):
    result = original_generate(self, text, cancelled)
    generated.append((phase, self.sample_rate, result.copy()))
    return result
PiperEngine.generate = observed_generate
engine = VoiceEngine(transcript, event)''')
source=source.replace("        rows.append(row)", "        assert engine.stop(timeout=10), engine.last_error\n        rows.append(row)")
source += '''
generated_index=[]
for label, rate, pcm in generated:
    target=private/(label+'-generated.npy')
    np.save(target,pcm)
    generated_index.append({'phase':label,'sampleRate':rate,'samples':len(pcm),'seconds':len(pcm)/rate,
                            'privatePath':str(target),'sha256':sha(target)})
(out/'GENERATED_INDEX.json').write_text(json.dumps(generated_index,indent=2),encoding='utf-8')
'''
(root/'scratchpad/c03-voice152.py').write_text(source,encoding='utf-8')
prior=json.loads((root/'artifacts/comprobaciones/C03/astra-voice149/PREREG.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==digest for p,digest in prior['sources'].items())
prior.update(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),phases=['direct-0','direct-1','direct-2'],
    method='Three preregistered cold capture starts in one loaded VoiceEngine, stop after every phase. Source147 unchanged, observational AEC/VAD/guard/anchor tap149 plus full returned Piper PCM copy. Every original output returned unchanged. Physical mic/speaker/loopback0.30, restore in finally.',
    criteria='Keep all three outcomes and exact generated/captured PCM. Seek a recorded failure and distinguish synthesis variation from observation scheduling. Diagnostic only; no best-run selection, source mutation or threshold change.')
(out/'PREREG.json').write_text(json.dumps(prior,indent=2),encoding='utf-8')
print(out)
