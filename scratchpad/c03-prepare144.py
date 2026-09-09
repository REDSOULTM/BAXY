from pathlib import Path
import datetime
import hashlib
import json

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-voice144'
out.mkdir(exist_ok=False)
for name in ('c03-voice138.py', 'c03-capture-voice138.py'):
    source = (root / 'scratchpad' / name).read_text(encoding='utf-8')
    (root / 'scratchpad' / name.replace('138', '144')).write_text(source.replace('voice138', 'voice144'), encoding='utf-8')
prior = json.loads((root / 'artifacts/comprobaciones/C03/astra-voice138/PREREG.json').read_text(encoding='utf-8'))
paths = [*prior['sources'], 'src/baxy_mind/voice_capture.py']
prior.update(
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    sources={p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
    method='Integrated source143, no wrappers/shadow VAD/PCM injection. Same phrase/direct mode and physical volume0.30 as138. Product WASAPI microphone with native ADC and continuous loopback cursor; independent observer remains MME microphone plus WASAPI loopback as138. No App/LLM/Core or transcript routing. Private captures, exact endpoint restore in finally.',
    criteria='Complete physical phrase, zero own barge-in, zero capture errors, AEC active with staged native hash at ready, stopped after shutdown. Compare138. This is a mechanism measurement, not final UI/human-input/long-session acceptance.',
)
(out / 'PREREG.json').write_text(json.dumps(prior, ensure_ascii=False, indent=2), encoding='utf-8')
print(out)
