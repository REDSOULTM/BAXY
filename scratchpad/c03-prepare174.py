"""Isolate one AEC3 candidate; retain downloads and update completed evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import tarfile
import urllib.request
import zipfile

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-webrtc174'
out.mkdir(exist_ok=False)
target = Path('D:/BAXYRuntime/experiments/voice/webrtc174')
target.mkdir(exist_ok=False)
def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

save(out / 'PREREG.json', {
    'createdUtc': datetime.now(timezone.utc).isoformat(),
    'purpose': 'Offline comparison of AEC3 against current Speex on previously consumed native capture arrays. No playback, human acceptance, source or registered runtime changes.',
    'candidate': 'pywebrtc-audio==0.2.0, CPython312 Windows x64; isolated extraction, no dependency installation',
    'configuration': 'AEC only; 16kHz mono; stream_delay_ms=0 internal estimator; no NS/AGC; automatic HPF intrinsic to AEC. Same raw signals; persistent 10ms blocks, no per512 zero padding.',
    'controls': 'Echo recording149 with exact native input/reference, cold silence and synthetic near voice alone/mixed from existing131. Evaluate residual VAD/interruption, preservation and CPU processing time; synthetic near speech does not certify human input.',
    'prohibitedConclusions': 'Do not infer repair of173 from149 alone; no changed thresholds or playback timing; no runtime promotion.'
})
with urllib.request.urlopen('https://pypi.org/pypi/pywebrtc-audio/0.2.0/json', timeout=30) as response:
    meta = json.load(response)
chosen = [x for x in meta['urls'] if x['filename'] in (
    'pywebrtc_audio-0.2.0-cp312-cp312-win_amd64.whl', 'pywebrtc_audio-0.2.0.tar.gz')]
assert len(chosen) == 2
downloads = []
for item in chosen:
    path = target / item['filename']
    urllib.request.urlretrieve(item['url'], path)
    assert sha(path) == item['digests']['sha256']
    downloads.append({'filename': path.name, 'path': str(path), 'url': item['url'], 'bytes': path.stat().st_size, 'sha256': sha(path)})
    if path.suffix == '.whl':
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                assert (target / 'python' / name).resolve().is_relative_to((target / 'python').resolve())
            archive.extractall(target / 'python')
    else:
        with tarfile.open(path) as archive:
            archive.extractall(target / 'source', filter='data')
save(out / 'DOWNLOADS.json', downloads)

snapshot = base / 'astra-source172-snapshot'
fast = Path(os.environ['TEMP']) / 'c03-source172-fast.log'
assert 'source_quality_gate_passed: mode=Fast' in fast.read_text(encoding='utf-8-sig')
copy = snapshot / fast.name
copy.write_bytes(fast.read_bytes())
index = json.loads((snapshot / 'INDEX.json').read_text(encoding='utf-8'))
index.append({'source': str(fast), 'copy': str(copy.relative_to(root)), 'sha256': sha(copy)})
save(snapshot / 'INDEX.json', index)
note = '''# Actualización 173–174 — audio todavía falla; comparación AEC3 aislada

Fuente172: 130 pruebas pasan, 0 skips, 7,36 s. Fast55364 terminó exit0,
Release2,73 s, cero avisos/errores; log copiado al snapshot172.
Ensayo173 terminó: dos eventos de interrupción, saludo y primera hora ES
cortados; inglés y última hora ES sin evento. No prueba de contenido completo.
Driver41212 y captura20590 terminaron exit0; no sesiones propias pendientes.
El contador corregido no resuelve los cortes. No alterar umbrales ni repetir UI.
174 descarga aislada pywebrtc-audio0.2.0 para comparar AEC3 con grabaciones
conservadas y controles de voz cercana sintética. No runtime ni fuente cambiados.
Turno anterior: informe de estado, sin progreso de producto; esta continuación
reanuda experimento seguro. Goal activo y alcance completo conservado.
'''
for name in ('CHECKPOINT.md', 'HANDOFF.md'):
    p = base / name
    old = p.read_text(encoding='utf-8')
    # Preserve former text while removing only the superseded top update.
    old = old[old.index('# ', 2):] if old.startswith('# Actualización172') else old
    p.write_text(note + '\n' + old, encoding='utf-8')
p = base / 'ASTRA-TRAMO-172.md'
p.write_text(p.read_text(encoding='utf-8') + '\n## Resultado posterior\n\nFast55364 exit0, Release2,73 s, 0 avisos/errores. 173 terminado: dos cortes en cuatro salidas; contador reparado, separación acústica aún insuficiente. Ver astra-sidecar173 y nuevo experimento174.\n', encoding='utf-8')
p = base / 'RELEVO_ACTIVO.json'
state = json.loads(p.read_text(encoding='utf-8'))
state.update(goalStatus='active', confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
             checkpoint='Fuente172 pruebas130/Fast verdes;173 terminado:2/4 cortes, no aceptación física.',
             continuation='174 AEC3 aislado sobre señales existentes y controles; no cambio de umbral, promoción ni Full. Resto C03 íntegro.')
save(p, state)
print(json.dumps({'downloads': downloads, 'sourceTopFiles': [str(p.relative_to(target)) for p in (target / 'source').glob('*/*') if p.is_file()]}, indent=2))
