from pathlib import Path
import datetime
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-ui107'
out.mkdir(exist_ok=False)
prior = json.loads((base / 'astra-ui104/PREREG.json').read_text(encoding='utf-8'))
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
registration = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
assert sha(registration) == prior['registrationSha256']
assert sha(prior['model']) == prior['modelSha256']
fixture = root / 'scratchpad/C03TitleFixture.exe'
assert fixture.is_file()
reg = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'method': 'Source103 real desktop via py main.py, Qwen3.5 override, wake0. '
        'Healthy clock, then suspend only the verified llama-server descendant of '
        'this App and request the same clock. Capture the failure state before '
        'resuming the same server and requesting the same clock again. Suspension '
        'helper resumes on sentinel or within 300s even if observation is interrupted. '
        'No fake drafts, composition injection mode, runtime changes or parallel '
        'models/builds. Then close/cancel/close/confirm an owned empty window fixture '
        'using the same four technical requests as tranche46. Observe exact '
        'confirmation and actual fixture lifetime. No human reserve or audio acceptance.',
    'cases': ['Dime la hora.', 'Dime la hora.', 'Dime la hora.',
        'cierra la ventana titulada Ventana C03 de prueba', 'cancelar',
        'cierra la ventana titulada Ventana C03 de prueba', 'confirmar'],
    'model': prior['model'], 'modelSha256': prior['modelSha256'],
    'registrationSha256': prior['registrationSha256'], 'profile': prior['profile'],
    'fixture': {'path': str(fixture), 'sha256': sha(fixture)},
    'files': {p: sha(root / p) for p in prior['files']},
    'heritage': ['PRUEBAS_RECUPERACION106.md', 'PRUEBAS_RUTAS_C03_TRAMO46.md',
        'PRUEBAS_UI104.md', 'ADR-0008'],
    'primary_source': 'https://psutil.io/api/#psutil.Process.suspend',
    'source_consulted': '2026-09-07; Windows suspend/resume affect all process threads; PID identity checked'}
(out / 'PREREG.json').write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
monitor = (root / 'scratchpad/c03-ui104-resources.py').read_text(encoding='utf-8')
assert monitor.count('astra-ui104') == 1
(root / 'scratchpad/c03-ui107-resources.py').write_text(monitor.replace('astra-ui104', 'astra-ui107'), encoding='utf-8', newline='\n')
print('UI107 preregistered; registration/model/fixture verified; no launch or suspension yet.')
