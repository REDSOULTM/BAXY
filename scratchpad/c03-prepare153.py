from pathlib import Path
import datetime
import hashlib
import json

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-voice153'
out.mkdir(exist_ok=False)
capture=(root/'scratchpad/c03-capture-voice152.py').read_text(encoding='utf-8')
(root/'scratchpad/c03-capture-voice153.py').write_text(capture.replace('152','153'),encoding='utf-8')
source=(root/'scratchpad/c03-voice152.py').read_text(encoding='utf-8').replace('152','153')
first=source.index('import numpy as np')
last=source.index('from baxy_mind.piper_tts import PiperEngine',first)
source=source[:first]+'import numpy as np\n'+source[last:]
first=source.index("np.savez(private/'tap153.npz'")
last=source.index('generated_index=[]',first)
source=source[:first]+source[last:]
(root/'scratchpad/c03-voice153.py').write_text(source,encoding='utf-8')
prior=json.loads((root/'artifacts/comprobaciones/C03/astra-voice152/PREREG.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==digest for p,digest in prior['sources'].items())
prior.update(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    method='Same three capture starts152 with all per-frame AEC/VAD/guard/anchor taps removed. Only copy returned Piper waveform once per synthesis, return original unchanged. Physical output and independent observers unchanged. New generated PCM is retained; no claim identical to152.',
    criteria='Record every outcome and generated PCM without per-frame observation; do not accept favorable run as resolving148. Native AEC states recreated per capture; Silero object belongs to loaded engine and may retain state between capture starts.')
(out/'PREREG.json').write_text(json.dumps(prior,indent=2),encoding='utf-8')
print(out)
