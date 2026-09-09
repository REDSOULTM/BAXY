"""Seal the installed AEC integration and leave the full C03 continuation."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'astra-integration257'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))
def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

for log in ('lock257','install257','retire257','tests257','owner-tests257','fast257','parity257','product258','voice259'):
    shutil.copyfile(Path(os.environ['TEMP']) / f'c03-{log}.log', OUT / f'{log}.log')
assert '138 passed' in (OUT / 'tests257.log').read_text()
assert '33 passed' in (OUT / 'owner-tests257.log').read_text()
assert 'source_quality_gate_passed: mode=Fast' in (OUT / 'fast257.log').read_text(errors='replace')
assert read(BASE / 'astra-product258/COMPLETE.json')['allExactlyMatch253']
physical = read(BASE / 'astra-voice259/RESULTS.json')
assert physical['bargeInCount'] == physical['transcriptCount'] == 0
assert physical['restoredExactly'] and not any(physical['workersAlive'].values()) and not physical['outputWorkerAlive']
assert not physical['voiceErrors'] and not physical['driverErrors']
save(OUT / 'VALIDATION.json', {
    'pytest': {'ownerPass':138, 'additionalPass':33, 'totalPass':171, 'skips':0, 'secondsEach':[6.18,6.18]},
    'fast': {'passed':True, 'releaseSeconds':3.30, 'warnings':0, 'errors':0},
    'dspParity':read(BASE / 'astra-parity257/PARITY_COMPLETE.json'),
    'captureAsrParity':read(BASE / 'astra-product258/COMPLETE.json'),
    'physical':{'frames':physical['frames'], 'seconds':physical['audioSeconds'], 'tts':4, 'falseInterruptions':0, 'transcripts':0, 'volumeRestored':True, 'workersClosed':True},
    'terminalHandles':{'96205':0,'12196':0,'59049':0}, 'activeOwnProcesses':[],
    'fullRun':False, 'remaining':'C03 all eight routes, fresh100/100, faults/recovery, real UI/voice/LLM/resources, runtime promotion/installation, C04-C09 continuity, finalFull/publication outside main.'
})

snapshot = BASE / 'astra-source257-snapshot'
snapshot.mkdir(exist_ok=False)
owners = set(read(BASE / 'astra-source242-snapshot/FILES.json'))
owners.update(read(OUT / 'PREREG.json')['before'])
owners.update(['src/baxy_mind/webrtc_aec.py','tests/test_webrtc_aec.py','tests/test_webrtc_runtime_package.py',
    'scripts/build_webrtc_runtime.py','runtime_wheels/webrtc-linear-output.patch',
    'runtime_wheels/pywebrtc_audio-0.2.0+baxy.1-cp312-cp312-win_amd64.whl'])
owners = sorted(name for name in owners if (ROOT / name).is_file())
for name in owners:
    target = snapshot / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / name, target)
save(snapshot / 'FILES.json', {name:sha(ROOT/name) for name in owners})
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
assert sha(manifest) == '13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'

checkpoint = '''# C03 — checkpoint259 — EN_CURSO — 2026-09-07

257 integra AEC3: webrtc_aec.py entrega reconocimiento/confirmación/pareja cruda
alineados a256 muestras. voice.py usa2 VAD independientes en captura acústica,
conserva prefijo y admisión253, y no admite por terminar TTS. DTLN retirado del
producto (módulo, instalador, licencia, tests y descriptor); modelos/evidencia
externos conservados. Lock60 instalado: 59 paquetes anteriores idénticos, tres
dependencias DTLN retiradas, pywebrtc-audio0.2.0+baxy.1 añadido. pip check verde.
Wheel a23633725342f1ca3425c81a0927e3d6ef7d050452415e24b6a4cabe540416eb;
nativo3679265e7761c1a77e51f598ebb33e819f11e9a6e53a4d0f95b0da6f83382ef2.
Registro LLM intacto (13b971b3…), Qwen3.5 sigue override, no promoción.

Fuente actual: astra-source257-snapshot/FILES.json (con copias). Antes:
astra-integration257/before. INTEGRACION_AEC257_259.md documenta decisiones.
Paridad AEC instalado: 13.433 bloques/12 grabaciones, dos señales exactas.
258 captura real SIN copiar método/SIN sustituir AEC o guarda: once recorridos,
nueve segmentos ASR, límites/PCM/textos/cancelaciones idénticos a253. Ocho
ventanas fijas verificadas/reutilizadas, no decodificadas otra vez.

259 física instalada: 1.315 bloques/42,08s, cuatro TTS, cero barge/transcripciones
y errores. Mic/referencia presentes; VAD confirmación máximo0,390. DSP medio
0,673ms/p99 1,105ms. Volumen0/muted=true restaurado; workers cerrados.
Sin persona simultánea ni UI/LLM/recursos conjuntos; wake sigue unavailable,
wake_verifier_manifest_missing, sin bypass. No certificación C08 ni ASR perfecto:
persisten pudier, world/given y otras diferencias de desarrollo253.

Pruebas: 138+33=171 pass,0 skips (6,18s cada tanda); Fast verde, Release3,30s,
0 advertencias/errores. Smoke confirmación19,89dB >=6 vigente. Primer test nuevo
contó22 bloques de cola en vez de21 existentes; expectativa corregida, producto
sin cambio de pausa, intento conservado. No Full durante reparación.
Handles96205(258),12196(tests/Fast),59049(259) terminales exit0 recogidos.
Ningún proceso propio activo. Sellos TRAMO257_259_PINS.json.

Siguiente260: aplicación real py main.py, UI/LLM/voz y presupuesto conjunto,
regresiones de las ocho rutas y perfil/registro antes de promover. Heredar
PRUEBAS_UI194.md/astra-ui194/PREREG.json (su hook es sintético: no aceptarlo como
voz humana). Después reserva fresca: 742 únicos/239 revisados, cien aún sin
congelar; tres turnos ingleses ya validados por dueño, no preguntar otra vez.

Alcance íntegro pendiente: ocho rutas y100/100 humanos frescos útiles/fieles,
averías/recuperación, UI/voz/LLM con4GB conjuntos, runtime/instalación,
continuidad C04–C09, Full y publicación fuera main. C03 formal88–92/133–135
conserva certificación acústica propia de C08, sin ejecutar toda su campaña ni
añadir un requisito FLEURS literal perfecto. No elimina pruebas físicas pedidas
ni permite dejar un fallo que bloquee respuestas. Goal activo, sin bloqueo externo.

'''
path = BASE / 'CHECKPOINT.md'
path.write_text(checkpoint + path.read_text(encoding='utf-8'), encoding='utf-8')
(BASE / 'HANDOFF.md').write_text(checkpoint, encoding='utf-8')
relevo = BASE / 'RELEVO_ACTIVO.json'
data = read(relevo)
data.update(goalStatus='active', confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='259 AEC3 instalado, lock60, 171 tests/0 skips y Fast verde; captura/ASR igual253 y física42s sin falsos turnos; sin procesos',
    continuation='260 UI/LLM/voz y4GB conjuntos, ocho rutas, perfil/registro, reserva100/100, averías, instalación/continuidad, Full/publicación. Conservar alcance completo.')
save(relevo,data)
public = [BASE / 'INTEGRACION_AEC257_259.md', snapshot / 'FILES.json']
public += [ROOT/name for name in owners]
public += [ROOT/'scratchpad'/name for name in ('c03-integrate257.py','c03-retire-dtln257.py','c03-prepare-parity257.py','c03-parity257.py','c03-product258.py','c03-prepare259.py','c03-voice259.py','c03-metrics259.py','c03-checkpoint259.py')]
for folder in (OUT, BASE/'astra-parity257', BASE/'astra-product258', BASE/'astra-voice259'):
    public += [p for p in folder.iterdir() if p.is_file()]
private = {row['path']:row['sha256'] for row in physical['privateFiles']}
private.update({row['privatePath']:row['sha256'] for row in read(BASE/'astra-product258/RESULTS.json')})
save(BASE/'TRAMO257_259_PINS.json', {'public':{str(p.relative_to(ROOT)):sha(p) for p in public},'private':private})
print(json.dumps({'checkpoint':259,'sourceFiles':len(owners),'publicPins':len(public),'privatePins':len(private),'goal':'active','next':260}))
