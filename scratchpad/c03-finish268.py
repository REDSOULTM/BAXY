"""Record questionnaire delivery without modifying owner judgments."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import urllib.request
import psutil

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-questionnaire268'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-owner-questionnaire-20260907'
now = datetime.now(timezone.utc).isoformat()
qa = json.loads((private / 'qa/answers.json').read_text(encoding='utf-8'))
answer = qa['answers']['technical-qa-1']
assert answer['authorship'] is True and answer['capability'] is False
assert answer['note'] == 'Prueba técnica: dos criterios independientes.'
with urllib.request.urlopen('http://127.0.0.1:63179/data.json', timeout=5) as response:
    data = json.load(response)
qa_stopped = False
try:
    process = psutil.Process(65100)
    expected = str((private / 'qa/server.py').resolve()).casefold()
    assert expected in [str(Path(arg).resolve()).casefold() for arg in process.cmdline()[1:] if arg.endswith('.py')]
    process.terminate()
    process.wait(timeout=10)
    qa_stopped = True
except psutil.NoSuchProcess:
    qa_stopped = True
result = {'utc': now, 'qaStoredAnswer': answer, 'qaRevision': qa['revision'],
          'browserReloadVerified': True, 'literalScriptRenderedAsText': True,
          'ownerDatasetHttpStatus': 200, 'qaServerStopped': qa_stopped,
          'ownerAnswersModifiedByAgent': False,
          'ownerServer': {'pid': 101140, 'url': 'http://127.0.0.1:63179/', 'automaticClose': False}}
(out / 'QA.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
snapshot = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-owner264-snapshot268'
snapshot.mkdir(exist_ok=False)
original = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-owner264-private'
files = {}
for name in ('compose-audit.jsonl', 'turn-audit.jsonl', 'raw-replies.jsonl', 'LAUNCH.json', 'launch.log', 'shell-trace.jsonl'):
    shutil.copy2(original / name, snapshot / name)
    content = (snapshot / name).read_bytes()
    files[name] = {'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
(out / 'SESSION_SNAPSHOT.json').write_text(json.dumps({'utc': now, 'privateDirectory': str(snapshot),
    'ownerAuthorizedReview': True, 'files': files, 'completeUiTranscript': False}, indent=2) + '\n', encoding='utf-8')
report = '''# C03 — cuestionario del dueño, tramo268

Se entregaron los 742 textos literales distintos recuperados hasta ahora, con
5476 referencias a registros de origen (hay copias solapadas; no son 5476
interacciones humanas distintas). Todos sus hashes coinciden con el pool.
No se afirma haber agotado el historial del PC. Los textos quedan privados.

URL local: http://127.0.0.1:63179/ . Servidor del dueño PID101140, sin cierre
automático. Datos y respuestas: %LOCALAPPDATA%/BAXY/C03-owner-questionnaire-20260907/.
answers.json persiste las marcas de forma atómica. No regenerar ni sobrescribir.

Cada fila distingue «Lo envié yo» y «BAXY debería responderlo bien», ambos con
sí/no/sin marcar, y comentario opcional. Incluye búsqueda, filtros, paginación,
origen y descargas de mensajes y marcas. Una expectativa no acredita autoría;
una marca de texto no atribuye automáticamente todas sus ocurrencias.
La admisión anterior del dueño de tres turnos ingleses sigue vigente. Estas
marcas no convierten por sí solas un caso en fresco para aceptación.

Verificación: una copia técnica con un único registro sintético, separada del
pool, conservó autoría=true, capacidad=false y comentario tras recarga real
del navegador. Un texto con etiqueta script se mostró literalmente. QA.json
registra el resultado; su servidor se cerró. La página real se abrió visible;
el agente no introdujo marcas en ella. No hay cambio de fuente de producto.

El dueño terminó su prueba y autorizó revisar la sesión264. Se preservó una
copia privada de sus seis logs con hashes en SESSION_SNAPSHOT.json. No es
todavía una transcripción completa de la UI. BAXY sigue vivo, oculto a bandeja;
la ventana397256 ya no es un objetivo disponible. No reiniciar antes de
recuperar la conversación en memoria. El cuestionario permanece disponible.

C03 EN_CURSO: fuente266/267 aún pendiente de modelo/UI; recuperación de
operaciones, afirmaciones sin evidencia y capacidades sin resolver. Reserva100
sin congelar/ejecutar; voz/UI/recursos/runtime/instalación/Full/publicación finales
pendientes. No se convierte la entrega del cuestionario en cierre de producto.
'''
(base / 'CUESTIONARIO_DUENO268.md').write_text(report, encoding='utf-8')
previous = (base / 'CHECKPOINT.md').read_text(encoding='utf-8')
(out / 'CHECKPOINT267.md').write_text(previous, encoding='utf-8')
checkpoint = '''# C03 — checkpoint268 — EN_CURSO

Última petición: dueño terminó de probar BAXY y AUTORIZÓ revisar sesión264.
La prohibición temporal anterior de leer sus mensajes ya no aplica.
Antes de reiniciar PID84328 recuperar conversación en memoria; ventana397256
ya no está disponible (oculta a bandeja). Logs privados preservados en
%LOCALAPPDATA%/BAXY/C03-owner264-snapshot268; hashes SESSION_SNAPSHOT.json.
No se ha recuperado aún toda la transcripción UI.

Cuestionario ENTREGADO, todos742 mensajes literales recuperados, dos criterios
independientes con ✓/✕: autoría y capacidad esperada. No atribuir procedencia
por capacidad. Mantener admisión previa de tres ingleses. No atribuir todas
las ocurrencias de un mismo literal ni frescura automáticamente.
URL http://127.0.0.1:63179/ PID101140, propiedad del dueño, SIN cierre automático.
Directorio %LOCALAPPDATA%/BAXY/C03-owner-questionnaire-20260907; answers.json
contiene marcas del dueño: NO sobrescribir ni borrar ni rellenar por él.
Servidor QA65100 cerrado después de verificar marcas independientes y recarga
en copia sintética. CUESTIONARIO_DUENO268.md; TRAMO268_PINS.json. No fuente de
producto modificada en268. Último checkpoint267 archivado en astra-questionnaire268.

Fuente266: afirmación seguida de petición usa gramática existente, corrige
«Si, abre steam»;2597pass0skip/ruff. Fuente267: contexto anterior fuera de
situation verificada,999pass0skip/ruff. PAYLOAD_COMPARISON es antes de HTTP,
NO inferencia. Falta modelo/UI/Fast para ambos. ÚltimoFast262 verde.
«Ya he abierto Steam.» sin operación aún pasa validadores Python/C#.
«Tengo en mente que abras steam» pierde app.open en shortlist28 (rank116).
Capacidades263 falla por catálogo incompleto/length/timeout/extra_claim.
Siguiente: revisar sesión264 autorizada, comparar nativo267 y corregir primera
frontera errónea. No otro barrido genérico ni Full repetido durante reparación.

Goal-c03, HEAD2bf3d4c; preservar WIP/main. Registro13b971… sin promover;
Qwen3.5 override. Recursos260 conjuntos3516,66MiBGPU/4822,60MiBRAM, sin ASR
humano;2633504,71MiBGPU/5624,86MiBRAM sin captura. Wake no certificado.
Ocho rutas útiles,100/100humanos frescos aún sin congelar, averías/recuperación,
UI/voz/ASR/recursos finales, perfil/runtime/instalación, continuidadC04–C09,
Full verde y publicación fuera main: pendientes íntegros. Sin bloqueo externo.
'''
for name in ('CHECKPOINT.md', 'HANDOFF.md'):
    (base / name).write_text(checkpoint, encoding='utf-8')
relevo_path = base / 'RELEVO_ACTIVO.json'
relevo = json.loads(relevo_path.read_text(encoding='utf-8'))
relevo.update(confirmedAtUtc=now, checkpoint='268: all742 questionnaire delivered; owner264 review authorized; goal active.',
    continuation='Preserve/recover owner264 conversation, then native comparison and product repair; keep questionnaire available.')
relevo['userOwnedInstance']['instruction'] = 'Owner finished testing and authorized review. Preserve conversation before restart. Old window397256 is hidden/unavailable.'
relevo['ownerQuestionnaire'] = {'pid': 101140, 'url': 'http://127.0.0.1:63179/',
    'directory': str(private), 'answers': str(private / 'answers.json'), 'automaticClose': False,
    'instruction': 'Keep available; never overwrite owner judgments.'}
relevo_path.write_text(json.dumps(relevo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
names = ['scratchpad/c03-questionnaire.html', 'scratchpad/c03-questionnaire-server.py',
         'scratchpad/c03-build-questionnaire268.py', 'scratchpad/c03-finish268.py',
         'artifacts/comprobaciones/C03/CUESTIONARIO_DUENO268.md']
names += [str((out / name).relative_to(root)).replace('\\', '/') for name in
          ('MANIFEST.json', 'QA.json', 'SESSION_SNAPSHOT.json', 'CHECKPOINT267.md')]
pins = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}
(base / 'TRAMO268_PINS.json').write_text(json.dumps({'utc': now, 'publicFiles': pins,
    'productSourceChanged': False, 'goalStatus': 'active'}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'pins': len(pins), 'qaStopped': qa_stopped, 'snapshotFiles': len(files), 'status': 'EN_CURSO'}))
