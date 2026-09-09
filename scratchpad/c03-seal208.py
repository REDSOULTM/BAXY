"""Seal the integrated runtime repair, preserving source and failed packaging attempts."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
import shutil

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))
def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
prior = read(base/'TRAMO205_206_PINS.json')
assert all(sha(root/row['path']) == row['sha256'] for row in prior['public'])
assert all(sha(Path(row['privatePath'])) == row['sha256'] for row in prior['private'])
result = read(base/'astra-product208/COMPLETE.json')
assert result['pcmReadings'] == result['identicalTo203'] == 47
assert result['directRecovered'] == 4 and result['registrationUnchanged']
installed = {dist.metadata['Name']: dist.version for dist in importlib.metadata.distributions()}
before = read(base/'astra-install207/PREREG.json')['before']
changes = {key: {'before': before.get(key), 'after': installed.get(key)}
    for key in before.keys() | installed.keys() if before.get(key) != installed.get(key)}
assert len(changes) == 1, changes
assert next(iter(changes)).replace('_','-') == 'sherpa-onnx'
assert next(iter(changes.values())) == {'before':'1.13.4','after':'1.13.4+baxy.1'}
save(base/'astra-install207/AFTER.json', {'changes': changes, 'versions': installed})
snapshot = base/'astra-source207-snapshot'
snapshot.mkdir(exist_ok=False)
paths = ['src/baxy_mind/voice.py','src/baxy_mind/requirements-voice.txt',
    'scripts/build_sherpa_runtime.py','scripts/verify_python_runtime_lock.py',
    'scripts/lock_python_dependencies.ps1','constraints-runtime-win-x64.txt',
    'pylock.runtime-win-x64.toml','tests/test_mind_voice_runtime.py',
    'tests/test_python_runtime_lock.py','tests/test_sherpa_runtime_package.py',
    'runtime_wheels/sherpa-nemo-stream-decoder.patch','runtime_wheels/README.md',
    'docs/AI_CONTEXT_MAP.md']
public = []
source_hashes = {}
for name in paths:
    destination = snapshot/name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root/name, destination)
    source_hashes[name] = sha(destination)
    public.append(destination)
save(snapshot/'FILES.json', source_hashes)
public.append(snapshot/'FILES.json')
logs = snapshot/'logs'
logs.mkdir()
log_names = ['c03-wheel207-build.log','c03-wheel207-build-retry.log',
    'c03-lock207.log','c03-lock207-retry.log','c03-lock207-inspect.log',
    'c03-lock207-portable.log','c03-lock207-check.log','c03-source207-owner.log',
    'c03-source207-tests.log','c03-lock207-tests-final.log','c03-source207-fast.log',
    'c03-install207.log','c03-product208.log']
for name in log_names:
    destination = logs/name
    shutil.copy2(Path(os.environ['TEMP'])/name, destination)
    public.append(destination)
assert '103 passed' in (logs/'c03-source207-tests.log').read_text(encoding='utf-8-sig')
assert '12 passed' in (logs/'c03-lock207-tests-final.log').read_text(encoding='utf-8-sig')
assert 'source_quality_gate_passed: mode=Fast' in (logs/'c03-source207-fast.log').read_text(encoding='utf-8-sig')
assert 'python_dependency_lock_current: profile=Runtime' in (logs/'c03-lock207-check.log').read_text(encoding='utf-8-sig')
report = '''# C03 — reconocimiento integrado, 207–208

## Resultado

La dependencia corregida ya está instalada mediante el lock con hashes.
VoiceEngine.transcribe_pcm reproduce las47 lecturas greedy203 y cuatro segmentos
antes erróneos (3/0,15/0,21/0,23/0) llegan completos al callback real de
_decode_utterance. TTS inerte y callback de diagnóstico: no efectos, UI ni audio
físico acreditados. Las47 paridades no convierten errores menores de ASR en pases.

_decode_offline_text solicita greedy sólo sin hotwords y verifica el método
efectivamente aplicado. La primera carga lo comprueba antes de publicar el
reconocedor. Beam sigue en las verificaciones wake y en el apoyo contextual.
Ambas entradas comparten _correct_transcript con el corrector conservador existente.
No cambian AEC, KWS, umbrales, GGUF, modelos acústicos ni manifiesto registrado.

## Dependencia e instalación

La inspección de RECORD corrigió el plan206: la extensión .pyd pertenece al
paquete sherpa-onnx, no al core. Versión instalada sherpa-onnx1.13.4+baxy.1;
sherpa-onnx-core sigue oficial1.13.4. AFTER.json demuestra que ésta fue la única
distribución cambiada. Wheel SHA256:
2ee49c501c97ad69be14449ecc739b37d856e33f9065ddf7565ffa6b626d7ee0.
Extensión SHA25649c696327587214eda554b9d621cb95f4aec259f817373bbd684ae654ad343b8,
idéntica a la probada206. Fuente/parche/licencias/procedencia/RECORD conservados.

runtime_wheels/README.md documenta la receta scripts/build_sherpa_runtime.py.
El script comprueba commit y diff exactos, compila y empaqueta; rechaza sustituir
un wheel existente por bytes distintos. Se exige revisar/versionar otro build;
no se promete igualdad binaria entre compiladores/rutas diferentes.
El wheel se instala sin compilador desde pylock.runtime-win-x64.toml con SHA256.
El verificador admite exclusivamente rutas runtime_wheels/<nombre> sin escapes,
además del origen PyPI anterior. No se desactiva verificación ni se relajan hashes.
El generador convierte sólo file-URLs del directorio autorizado a wheels.path.
Regeneración -Check exit0: lock idéntico. Core y resto del grafo no cambian.

Fallos conservados: primer wheel tenía versión original en METADATA por CRLF;
resolver lo rechazó. Está fuera del producto como wheel207-invalid-metadata.whl.
El builder se corrigió y el test de paquete comprueba identidad y todos los hashes.
Primer lock portable falló porque pip emitió URL file absoluta; se corrigió la
conversión en el generador y se mantuvo el rechazo del verificador. Un intento de
ruff en el Python de runtime falló por módulo ausente; se usó el entorno de calidad
existente, sin instalar herramientas allí. Ruff y Fast posteriores verdes.

## Validación

- pytest tests/test_mind_voice_runtime.py:91 pass,0 skips (8,05s inicialmente).
- Combinación voz/lock/paquete:103 pass,0 skips (6,16s).
- Tras añadir el rechazo de nombre con ruta, test_python_runtime_lock:12 pass,
  0 skips (0,63s); test_sherpa_runtime_package:1 pass,0 skips (0,26s).
- test_voice_corrector:6 pass,0 skips (0,26s), salida observada en la herramienta.
- test_source_quality.ps1:Fast exit0; Release9,61s,0 avisos/errores.
- lock_python_dependencies.ps1 -Profile Runtime -Check:exit0, idéntico.
- astra-product208:47 paridades de PCM,4 callbacks recuperados; proceso3087 exit0.

Carga VoiceEngine5,641s, RSS1168,04MiB en el diagnóstico; no coste combinado final.
VAD cargado; streaming es opt-in y no se activó. Wake sigue unavailable con
wake_verifier_manifest_missing; no presentar estas pruebas como calibración.
Manifiesto del runtime sigue SHA13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed.
Qwen3.5 continúa siendo override experimental y Speex el AEC del producto.

## Siguiente

Todos los procesos de este tramo terminaron y se recogieron. Fuente vigente207,
no192. Las corridas antiguas que fijan fuente192/172 o el sherpa original son
históricas; no reutilizarlas sin prereg nuevo. No editar evidencia sellada.
Retomar fallo físico183: interrupción falsa por eco, independiente del ASR ahora
corregido. Usar la evidencia física ya capturada antes de otra repetición. La
activación/calibración sigue abierta; pregunta opcional sobre Grabación(2) pendiente.
También siguen pendientes ocho rutas finales, reserva100 humana congelada y
100/100, averías/recuperación, UI y audio físico finales, recursos/runtime,
instalación/continuidadC04–C09, Full íntegro y publicación fuera main. C03 EN_CURSO.
'''
(base/'PRUEBAS_RUNTIME207_208.md').write_text(report, encoding='utf-8')
public.append(base/'PRUEBAS_RUNTIME207_208.md')
for folder in ['astra-install207','astra-product208']:
    public.extend(path for path in (base/folder).iterdir() if path.is_file())
public.extend(root/'scratchpad'/name for name in ['c03-install207.py','c03-product208.py','c03-seal208.py'])
public.append(root/'runtime_wheels/sherpa_onnx-1.13.4+baxy.1-cp312-cp312-win_amd64.whl')
private = [Path('D:/BAXYRuntime/experiments/voice/sherpa205')/name for name in
    ['wheel207-invalid-metadata.whl','sherpa_onnx-1.13.4-cp312-cp312-win_amd64.whl']]
save(base/'TRAMO207_208_PINS.json', {
    'public': [{'path': path.relative_to(root).as_posix(), 'sha256': sha(path), 'bytes': path.stat().st_size} for path in public],
    'private': [{'privatePath': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size} for path in private],
})
relevo = read(base/'RELEVO_ACTIVO.json')
relevo.update({'confirmedAtUtc': datetime.now(timezone.utc).isoformat(),
    'checkpoint': '208: fuente207 y sherpa-onnx1.13.4+baxy.1 instalados.47 PCM/4 callbacks recuperados; owners y Fast verdes. Registro/modelos intactos.',
    'continuation': 'Retomar fallo acústico183 y wake no disponible. No procesos activos. Mantener alcance completo; PRUEBAS_RUNTIME207_208 y snapshot207 sellados.'})
save(base/'RELEVO_ACTIVO.json', relevo)
print(json.dumps({'public': len(public), 'private': len(private), 'changedDistributions': changes}))
