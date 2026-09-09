from pathlib import Path
import datetime
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-audio166'
out.mkdir(exist_ok=False)
for kind in ('capture','launch'):
    source=root/f'scratchpad/c03-{kind}-audio158.py'
    target=root/f'scratchpad/c03-{kind}-audio166.py'
    with target.open('x',encoding='utf-8') as f:
        f.write(source.read_text(encoding='utf-8').replace('audio158','audio166'))
prior=json.loads((base/'astra-audio158/PREREG.json').read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()
manifest=Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json'
assert sha(manifest)==prior['registrationSha256']
paths=set(prior['sourceFiles'])-{'scratchpad/c03-capture-audio158.py','scratchpad/c03-launch-audio158.py'}
paths.update({'scratchpad/c03-capture-audio166.py','scratchpad/c03-launch-audio166.py','tests/test_sidecar_lifecycle.py'})
prior.update(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    sourceFiles={p:sha(root/p) for p in sorted(paths)},
    method='Actual py main.py desktop on source164; sole product difference from158 prepares existing DSP before JSONL receiver. Same Qwen3.5 override, startup wake and three consumed ES/EN/mixed clock prompts via Computer Use. Physical mic/loopback capture300s and exact endpoint restore. No waveform/AEC/VAD wrappers, injection, PythonPath hooks or simulated device. App tree GPU/RAM and owned cleanup.',
    criteria='Clock facts useful/current in UI, complete physical output, no stalled voice/sidecar restart and App tree VRAM<=4096MiB. Preserve any failure. Existing unapproved wake seam not accepted; no human reserve or human-input acceptance.',
    heritage=['ASTRA-TRAMO-158_161.md','ASTRA-TRAMO-162_165.md','PRUEBAS_CAPTURA143_157.md'])
(out/'PREREG.json').write_text(json.dumps(prior,ensure_ascii=False,indent=2),encoding='utf-8')
with (base/'ASTRA-TRAMO-162_165.md').open('a',encoding='utf-8') as f:
    f.write('\n165 producto164 sin precarga diagnóstica: catálogo5,140s/status4,094s/speak0,110s/start4,281s; listening/AEC/ttsReady true. Exit0/cierre17,110s, stderr vacío; sin procesos propios pendientes. Wake no aprobado sigue fuera de aceptación.\n')
print('166 preregistered; source164 and unchanged registered manifest.')
