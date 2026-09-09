"""Freeze exact source waveforms and native streaming signals for offline contrasts."""
from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-sidecar187'
out.mkdir(exist_ok=False)
prior=json.loads((base/'astra-sidecar183/PREREG.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in prior['sourceFiles'].items())
prior.update(method='Same full sidecar sequence183 and DTLN128. Freeze generated Piper PCM and bounded preallocated trace of exact mic/reference/clean/VAD/guard states. Writes after shutdown. Diagnostic observation may change scheduling; do not credit fewer barge events as causal improvement. No thresholds/source/runtime changed.',
             reason='183 cut firstES,185 no cuts; post-decision snapshot185 absent. Exact signals are needed for repeatable offline comparison and to separate generated-wave variability from algorithm behavior. Same four texts, no new prompt or gain sweep.',
             tapSha256=hashlib.sha256((root/'scratchpad/c03_tap187.py').read_bytes()).hexdigest())
(out/'PREREG.json').write_text(json.dumps(prior,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ['c03-capture183.py','c03-sidecar183.py','c03-sidecar183-entry.py']:
    content=(root/'scratchpad'/name).read_text(encoding='utf-8').replace('183','187')
    if name.endswith('-entry.py'):
        begin=content.index('import baxy_mind.voice as voice_module')
        end=content.index('\n\nprivate=',begin)
        content=content[:begin]+'import c03_tap187\nfrom datetime import datetime, timezone'+content[end:]
        content=content.replace("{'time':time.monotonic(), 'speaking':speaking", "{'time':time.monotonic(), 'utc':datetime.now(timezone.utc).isoformat(), 'speaking':speaking")
        content=content.replace('faulthandler.cancel_dump_traceback_later()', 'faulthandler.cancel_dump_traceback_later()\n        c03_tap187.save()')
    elif name=='c03-sidecar183.py':
        content=content.replace('    indexes=[]', "    names.extend(name for name in ['tap187.npz','tap187.json','generated187.npz','generated187.json'] if (private/name).is_file())\n    indexes=[]")
    with (root/'scratchpad'/name.replace('183','187')).open('x',encoding='utf-8') as handle:
        handle.write(content)
print('187 prepared; bounded trace and original generated PCM only; source172 unchanged.')
