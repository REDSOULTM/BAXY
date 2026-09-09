"""Record native decoder evidence and exact next integration step."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))
def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
prior = read(base/'TRAMO200_204_PINS.json')
assert all(sha(root/r['path']) == r['sha256'] for r in prior['public'])
assert all(sha(Path(r['privatePath'])) == r['sha256'] for r in prior['private'])
complete = read(base/'astra-shared206/COMPLETE.json')
assert complete['readings'] == complete['identical'] == 94
assert len(complete['rejections']) == 2 and complete['runtimeUnchanged']
prereg194 = read(base/'astra-ui194/PREREG.json')
assert all(sha(root/path) == expected for path, expected in prereg194['sourceFiles'].items())
assert sha(Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json') == prereg194['registrationSha256']
report = '''# C03 — reparación nativa de decodificación, 205–206

## Decisión demostrada

La PR upstream3657 no arregla los tres segmentos humanos vacíos y deja vacías
cuatro transcripciones humanas antes útiles (16/0,18/0,20/0,22/0). Se descarta.
El cambio de seleccionar greedy por stream, manteniendo beam por defecto y un
solo modelo NeMo, reproduce 94/94 resultados esperados: 47 greedy203 y 47 beam205.
Son paridades del mecanismo, no 94 transcripciones perfectas ni aceptación C03.
La recuperación de los tres vacíos procede de greedy203; quedan sus limitaciones.

## Base y controles

Fuente externa D:/BAXYRuntime/experiments/voice/sherpa205/source,
tag v1.13.4, commit142807252687d81b40d6315f23470a1512a00de3. VS2022/CMake,
Python3.12.10, ONNX Runtime1.27.0 CPU, todos los modelos int8 originales.
Sin parche, la compilación reproduce exactamente las 46 lecturas comparables
de la biblioteca instalada. Su silencio de dos segundos produce «Thank you.».
Se corrigió explícitamente una actualización que había supuesto silencio vacío
sin comprobarlo. El primer informe compare205 falló en esa aserción incorrecta;
no se modificó ninguna transcripción para corregir el informe.

PR3657 head867762892495a6bf1a2b031699906aaa73217e90, abierta/no fusionada.
La prueba repite los mismos47 inputs, sin tocar gain, padding, VAD o modelo.
14 salidas difieren; COMPARISON.md incluye las47 literales. Silencio pasa a vacío,
pero voz humana empeora. No se adopta. Se revirtió sólo ese diff en el checkout
externo antes del206; no se alteraron BAXY ni los bundles conservados.

## Reparación206

Sólo cambia offline-recognizer-transducer-nemo-impl.h en el checkout externo.
La opción de stream decoding_method=greedy_search selecciona un decoder ligero
que usa el mismo model_. El decoder beam original permanece como predeterminado.
No se usa SetConfig ni se recargan/copían pesos. applied_decoding_method comunica
el método efectivo después de decodificar, para que el producto detecte una
biblioteca antigua que ignorase la opción. Batches homogéneos conservan su camino;
uno mixto se divide por stream antes de codificar.

La prueba alterna ambos métodos en una instancia sobre los47 inputs congelados:
94 textos idénticos a sus controles. Rechaza greedy con ContextGraph y un método
desconocido; batch mixto obtiene los dos textos esperados. El script conserva
PREREG/RESULTS/COMPLETE, parche y hashes de ambos binarios en astra-shared206.
RSS final985,87MiB incluye los47 buffers cargados; no es medida combinada del
producto ni comparativa estricta contra204. Construcción2,766s con cachés calientes.

## Integración que falta

El producto sigue en fuente192 y el runtime registrado sigue intacto; no afirmar
que BAXY instalado ya usa206. No hay procesos propios activos. Compilaciones
55343,76842,66577 y corridas36002,12596,82089 recogidas exit0.

Camino propuesto para continuar: empaquetar la extensión corregida como wheel
local identificado (por ejemplo, sherpa-onnx-core1.13.4+baxy.1), con fuente/parche,
licencia, receta y hash; instalar/verificar de forma reproducible. Mantener
wrapper sherpa-onnx1.13.4. No inyectar módulos tardíamente en el producto ni
ocultar modificaciones con la versión original. La inyección sólo fue del arnés.
pylock.runtime-win-x64.toml es PEP751, actualmente sólo permite wheels PyPI;
scripts/verify_python_runtime_lock.py143–173 impone name/url/hash y dominio.
PEP751 admite wheels.path. Si se adopta wheel local, conservar hashes y límites
de ruta; ajustar lock/generador/tests de forma explícita, no omitir el verificador.
scripts/lock_python_dependencies.ps1 genera en subcarpeta temporal: cuidar las
rutas relativas al mover el lock. Archivo dueño de pins: constraints-runtime-win-x64.txt;
requirements-voice.txt fija sherpa-onnx1.13.4, wrapper exige core1.13.4 (una versión
local debe validarse con el resolver). Setup instala pylock con require-hashes.

Después integrar _decode_offline_text: solicitar greedy sólo sin hotwords y
verificar applied_decoding_method. Conservar beam en todas las verificaciones
wake y apoyo contextual. transcribe_pcm hoy siempre aporta hotwords: deberá
tener la misma primera pasada fiable y corrección contextual conservadora que
_decode_utterance; no duplicar esa lógica. Probar rechazo de biblioteca antigua,
conservación wake/contexto y audio humano con el producto. Tests dueños y Fast;
Full únicamente sobre candidato final. Mantener abiertos audio físico183,
calibración wake, reserva100, ocho rutas, runtime/instalación/recursos y cierre.

Fuentes: [PR descartada](https://github.com/k2-fsa/sherpa-onnx/pull/3657),
[fuente original](https://github.com/k2-fsa/sherpa-onnx/tree/v1.13.4),
[formato pylock](https://packaging.python.org/en/latest/specifications/pylock-toml/).
'''
(base/'PRUEBAS_NATIVO205_206.md').write_text(report, encoding='utf-8')
public = [base/'PRUEBAS_NATIVO205_206.md']
private = []
folders = ['astra-sherpa205','astra-native205-baseline','astra-native205-patched','astra-shared206']
for folder in folders:
    public.extend(path for path in (base/folder).iterdir() if path.is_file())
    if folder != 'astra-sherpa205':
        assert read(base/folder/'COMPLETE.json')
        for row in read(base/folder/'PREREG.json')['binaries']:
            path = Path(row['path'])
            assert sha(path) == row['sha256']
            private.append(path)
public.extend(root/'scratchpad'/name for name in ['c03-prepare205.py',
    'c03-native205.py','c03-compare205.py','c03-shared206.py','c03-seal206.py'])
save(base/'TRAMO205_206_PINS.json', {
    'public': [{'path': path.relative_to(root).as_posix(), 'sha256': sha(path), 'bytes': path.stat().st_size} for path in public],
    'private': [{'privatePath': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size} for path in private],
})
relevo = read(base/'RELEVO_ACTIVO.json')
relevo.update({'confirmedAtUtc': datetime.now(timezone.utc).isoformat(),
    'checkpoint': '206: reparación nativa por stream comparte modelo,94/94 paridades; PR3657 rechazada por regresiones. Fuente192/registro intactos.205–206 sellados.',
    'continuation': 'Integrar dependencia corregida y helper de transcripción con wake/contexto conservados. Sin procesos activos. Ver PRUEBAS_NATIVO205_206.md y CHECKPOINT.'})
save(base/'RELEVO_ACTIVO.json', relevo)
print(json.dumps({'public': len(public), 'private': len(private), 'source192Unchanged': True}))
