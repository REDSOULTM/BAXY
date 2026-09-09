from pathlib import Path
import datetime
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-audio158'
out.mkdir(exist_ok=False)
for kind in ['capture','launch']:
    source=root/f'scratchpad/c03-{kind}-audio121.py'
    target=root/f'scratchpad/c03-{kind}-audio158.py'
    with target.open('x',encoding='utf-8') as f:
        f.write(source.read_text(encoding='utf-8').replace('audio121','audio158'))
prior=json.loads((base/'astra-audio121/PREREG.json').read_text(encoding='utf-8'))
def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
assert sha(manifest)==prior['registrationSha256']
paths=set(prior['sourceFiles'])-{'scratchpad/c03-capture-audio121.py','scratchpad/c03-launch-audio121.py'}
paths.update(json.loads((base/'astra-voice148/PREREG.json').read_text(encoding='utf-8'))['sources'])
paths.update({'scratchpad/c03-capture-audio158.py','scratchpad/c03-launch-audio158.py'})
prior.update(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    sourceFiles={p:sha(root/p) for p in sorted(paths)},
    method='Actual py main.py desktop on source147, same Qwen3.5 override and startup wake setting as121. Same three consumed ES/EN/mixed clock prompts via Computer Use, physical mic/loopback private capture300s, exact endpoint restore. No waveform/AEC/VAD wrappers, injection, PythonPath hooks or simulated device. App tree GPU/RAM sampled and owned cleanup. Staged Piper/John/Speex not promoted.',
    criteria='Useful truthful clock answers in actual UI, complete physical output and combined App tree VRAM<=4096MiB. Preserve failure if any;148 intermittent cutoff remains unresolved by earlier passes. No human reserve or human-input acceptance. App existing allow-uncalibrated wake seam is recorded, not accepted as calibrated wake.',
    heritage=['PRUEBAS_CAPTURA143_157.md','PRUEBAS_VOZ119_125.md'])
(out/'PREREG.json').write_text(json.dumps(prior,ensure_ascii=False,indent=2),encoding='utf-8')
print('158 preregistered. No launch/capture yet.')
