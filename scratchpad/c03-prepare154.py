from pathlib import Path
import datetime
import hashlib
import json

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-voice154'
out.mkdir(exist_ok=False)
capture=(root/'scratchpad/c03-capture-voice152.py').read_text(encoding='utf-8')
(root/'scratchpad/c03-capture-voice154.py').write_text(capture.replace('152','154'),encoding='utf-8')
source=(root/'scratchpad/c03-voice152.py').read_text(encoding='utf-8').replace('152','154')
source=source.replace("engine.speak(prereg['text'])", "engine.speak(prereg['texts'][phase])")
(root/'scratchpad/c03-voice154.py').write_text(source,encoding='utf-8')
prior=json.loads((root/'artifacts/comprobaciones/C03/astra-voice152/PREREG.json').read_text(encoding='utf-8'))
cases=json.loads((root/'artifacts/comprobaciones/C03/astra-native-voice120/PREREG.json').read_text(encoding='utf-8'))['cases']
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==digest for p,digest in prior['sources'].items())
prior.pop('text')
prior.update(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    phases=[f'direct-{i}' for i in range(len(cases))],texts={f'direct-{i}':c['text'] for i,c in enumerate(cases)},
    method='Six consumed development fixtures from native120, alternating ES/EN, now physical output/direct microphone with source147. Tap152 records unchanged AEC/VAD/guard outputs and generated PCM. Stop/start capture each case, one loaded engine. No live clock facts or human-reserve claims: these are pronunciation/echo regression fixtures.',
    criteria='Assess varied phrase/language/voice rather than repeat one English sentence. Keep all outcomes and exact signal at failures. Complete physical content verified separately with local ASR; observer presence precludes final acceptance.')
(out/'PREREG.json').write_text(json.dumps(prior,ensure_ascii=False,indent=2),encoding='utf-8')
print(out)
