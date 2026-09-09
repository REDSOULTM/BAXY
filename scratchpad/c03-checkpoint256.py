"""Seal native package evidence and leave one-page continuation state."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'astra-integration255'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

for log in ('native255', 'parity255', 'parity256', 'package-tests255', 'native-tests255', 'fast255'):
    shutil.copyfile(Path(os.environ['TEMP']) / f'c03-{log}.log', OUT / f'{log}.log')
rows = json.loads((OUT / 'PARITY_RESULTS.json').read_text())
last = json.loads((BASE / 'astra-parity256/PARITY_COMPLETE.json').read_text())
assert len(rows) == 11 and sum(r['frames'] for r in rows) == 12117 and last['allExact']
assert last['frames'] == 1316
assert 'source_quality_gate_passed: mode=Fast' in (OUT / 'fast255.log').read_text(errors='replace')
assert '6 passed' in (OUT / 'package-tests255.log').read_text()
assert '14 passed' in (OUT / 'native-tests255.log').read_text()
save(OUT / 'VALIDATION.json', {
    'packageTests': {'pass': 6, 'skip': 0, 'seconds': .30},
    'upstreamAecTests': {'pass': 14, 'skip': 0, 'seconds': .24},
    'fast': {'pass': True, 'releaseBuildSeconds': 3.25, 'buildWarnings': 0, 'buildErrors': 0},
    'nativeBuildWarnings': {'C4005': 310, 'C4244': 14, 'C4715': 1},
    'signalParity': {'recordings': 12, 'blocks': 13433, 'bothSignalsExact': True, 'observedPhysicalGuards': 60},
    'terminalHandles': {'53486': 0, '74943': 0}, 'activeOwnProcesses': [],
    'fullRun': False, 'productionSource': 242, 'lockPackages': 62,
    'next': '257 integrate the prepared native package; no product/lock replacement yet',
})

snapshot = BASE / 'astra-package256-snapshot'
snapshot.mkdir(exist_ok=False)
owners = ['scripts/build_webrtc_runtime.py', 'tests/test_webrtc_runtime_package.py',
          'runtime_wheels/webrtc-linear-output.patch', 'runtime_wheels/README.md',
          'runtime_wheels/pywebrtc_audio-0.2.0+baxy.1-cp312-cp312-win_amd64.whl']
save(snapshot / 'FILES.json', {name: sha(ROOT / name) for name in owners})
checkpoint = '''# C03 — checkpoint256 — EN_CURSO — 2026-09-07

255–256 preparan el paquete AEC3; la captura del producto sigue en fuente242,
DTLN512 y lock62, intactos. Wheel pywebrtc-audio0.2.0+baxy.1 (430.727 bytes),
SHA a23633725342f1ca3425c81a0927e3d6ef7d050452415e24b6a4cabe540416eb.
Receta scripts/build_webrtc_runtime.py, parche exporta lineal sin métricas;
DSP original174 intacto. VS2022 /MT; dependencias sólo Python/WINMM/KERNEL32.
Snapshot anterior astra-integration255/before; paquete astra-package256-snapshot.

Paridad: 11 entradas de253, 12.117 bloques, ambas señales y guarda exactas.
Física254: 1.316 bloques, dos señales exactas y 60 guardas observadas exactas.
Total 13.433 bloques/12 grabaciones; impulso lineal/final/raw a256 muestras.
255 falló al convertir centinela de guarda -1 en True; 256 sólo compara0/1.
Primer build falló por CRLF de git apply; receta controla LF/hash exacto.
Ambos fallos e intentos conservados. No cambios a datos, criterios ni umbrales.

Validación: 6 pruebas del paquete pass/0 skips (0,30s), 14 nativas AEC pass/
0 skips (0,24s), Fast verde, Release3,25s/0warnings/0errors. Build nativo
vendorizado sí tiene warnings (ver PAQUETE_AEC255_256.md), no se ocultan.
53486(build) y74943(Fast) terminales exit0 recogidos; ninguno propio activo.
Sin Full durante reparación. No ASR nuevo sobre audio idéntico.

Inventario: no assets.local.json ni override eco. Sólo ai-edge-litert exige
activamente backports.strenum y ml_dtypes; extra quantization de onnxruntime
no solicitado. Al integrar, prever lock60: conserva59, retira3DTLN, añade1AEC.
Siguiente257: sustituir dtln_aec por puente AEC3, conectar2VAD independientes
en voice.py, conservar prefijo/admisión de253, colas/wake/fallos; retirar
instalador/descriptor/deps antiguos, instalar lock, pruebas dueñas/Fast/paridad.
No borrar modelos/evidencia ni usar rutas experimentales en producto.

C03 íntegro: erroresASR y wake abiertos; ocho rutas, cien humanos frescos aún
sin congelar y100/100 útiles/fieles, averías/recuperación, UI/voz/LLM y4GB
conjuntos, runtime/instalación, continuidadC04–C09, Full/publicación fuera main.
Goal activo, sin bloqueo externo; paquete listo no equivale a producto aceptado.

'''
path = BASE / 'CHECKPOINT.md'
path.write_text(checkpoint + path.read_text(encoding='utf-8'), encoding='utf-8')
handoff = BASE / 'HANDOFF.md'
archive = BASE / 'HANDOFF_HISTORICO_HASTA254.md'
assert not archive.exists()
shutil.copyfile(handoff, archive)
handoff.write_text(checkpoint, encoding='utf-8')
relevo = BASE / 'RELEVO_ACTIVO.json'
data = json.loads(relevo.read_text(encoding='utf-8'))
data.update(goalStatus='active', confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='256 paquete AEC3 listo: 13.433 bloques exactos, 6+14 tests/0 skips, Fast verde; fuente242/DTLN/lock intactos, sin procesos',
    continuation='257 integrar paquete y dos vistas en captura, sustituir DTLN y locks/instalación, pruebas/paridad; conservar alcance C03 íntegro.')
save(relevo, data)
public = [ROOT / name for name in owners]
public += [BASE / 'PAQUETE_AEC255_256.md', snapshot / 'FILES.json']
public += [ROOT / 'scratchpad' / name for name in ('c03-prepare255.py','c03-parity255.py','c03-prepare256.py','c03-parity256.py','c03-audit255.py','c03-checkpoint256.py')]
for folder in (OUT, BASE / 'astra-parity256'):
    public += [p for p in folder.iterdir() if p.is_file()]
save(BASE / 'TRAMO255_256_PINS.json', {'public': {str(p.relative_to(ROOT)): sha(p) for p in public},
    'private': {}, 'inputs': 'Private input hashes remain in PARITY_PREREG.json and prior frozen result manifests; no new audio copies.'})
print(json.dumps({'publicPins':len(public), 'checkpoint':256, 'next':257, 'goal':'active'}))
