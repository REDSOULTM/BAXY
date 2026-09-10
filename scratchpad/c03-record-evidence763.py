"""Seal completed761-763 diagnostics and append survey evidence, without coverage credit."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
sys.path.insert(0, str(ROOT / 'src'))
from baxy_mind.window_prose_facts import window_fact_defect


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def markdown(path, value):
    path.write_bytes(value.encode('utf-8'))


now = datetime.now(timezone.utc).isoformat()
source = '438bcddee678e4bca4e07bc6e72bb3a9d9231b8c'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == source
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
pins = read(BASE / 'SEMANTIC_INVENTORY760/SOURCE_PINS.json')
assert all(sha(ROOT / path) == digest for path, digest in pins.items())
batch = read(BASE / 'STATUS_BATCH761/RESULT.json')
assert (batch['cases'], batch['correct'], batch['substantive_failures']) == (73, 51, 22)
for directory in ['STATUS_BATCH761', 'COMPOSE_BOUNDARY762']:
    assert read(BASE / directory / 'EXIT.json')['exit_code'] == 0
    assert not read(BASE / directory / 'RESOURCES.json')['violations']

# This is an append to diagnostic evidence, never a reclassification of the owner survey.
registry = PRIVATE / 'C03-survey-requirements336-private/requirements.jsonl'
before_sha = sha(registry)
backup = PRIVATE / 'C03-status-batch761-private/requirements-before761.jsonl'
receipt_path = BASE / 'STATUS_BATCH761/REGISTRY_UPDATE.json'
expected_before = 'f6f2b1ac779c767b59740c3a2da2532b53e1044596eac329597f9b8c1c20ebff'
if receipt_path.exists():
    receipt = read(receipt_path)
    assert before_sha == receipt['after_sha256'] and sha(backup) == expected_before
    now, before_sha = receipt['utc'], expected_before
else:
    assert before_sha == expected_before and not backup.exists()
    backup.write_bytes(registry.read_bytes())
before = [json.loads(line) for line in backup.open(encoding='utf-8-sig')]
after = copy.deepcopy(before)
verdicts = {r['case_id']: r for r in batch['verdicts'] if r['case_id'].startswith('H')}
assert len(verdicts) == 50
for row in after:
    verdict = verdicts.get(row['case_id'])
    if verdict is None:
        continue
    row.setdefault('verification_evidence', []).append({
        'campaign': 'STATUS_BATCH761', 'source_commit': source,
        'private_adjudication': str(PRIVATE / 'C03-status-batch761-private/adjudication.json'),
        'case_id': row['case_id'], 'turn_id': verdict['turn_id'],
        'literal_diagnostic_correct': verdict['correct'], 'category': verdict['category'],
        'development_variants_in_same_family': [r['case_id'] for r in batch['verdicts']
            if r['group'] == verdict['group'] and not r['case_id'].startswith('H')],
        'registered_runtime': True, 'no_hooks': True, 'ui_or_voice_credit': False, 'coverage_credit': False,
    })
    row['verification_reason'] = ('761: diagnóstico con fuente760 y runtime registrados; '
        + ('literal acreditado' if verdict['correct'] else 'literal sin acreditar')
        + ': ' + verdict['category'] + '. Evidencia y variantes por familia conservadas; '
        'generalización completa pendiente. Sin crédito de UI/voz/consumo conjunto ni cierre automático por familia.')
    row['verification_updated_at'] = now
allowed = {'verification_evidence', 'verification_reason', 'verification_updated_at'}
assert len(after) == 742
assert all({k:v for k,v in a.items() if k not in allowed} ==
           {k:v for k,v in b.items() if k not in allowed} for a,b in zip(before, after))
counts = dict(Counter(r['verification_status'] for r in after))
assert counts == {'open': 716, 'covered': 26}
assert sum(a != b for a,b in zip(before, after)) == 50
registry.write_bytes((''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in after)).encode('utf-8'))
write(BASE / 'STATUS_BATCH761/REGISTRY_UPDATE.json', {
    'utc': now, 'changed_rows': 50, 'fields_changed': sorted(allowed), 'counts': counts, 'coverage_added': 0,
    'before_sha256': before_sha, 'after_sha256': sha(registry), 'snapshot_private': str(backup),
    'authorship_expectations_literals_source_references_and_statuses_unchanged': True,
    'fresh_reserve_credit': False,
})

http_path = PRIVATE / 'C03-compose762-private/http-posts.jsonl'
http = [json.loads(line) for line in http_path.open(encoding='utf-8-sig')]
compose_path = PRIVATE / 'C03-compose762-private/compose-boundary.jsonl'
compose = [json.loads(line) for line in compose_path.open(encoding='utf-8-sig')]
inventory_ids = [3, 5, 9, 11, 13, 15]
latencies = []
for request_id in inventory_ids:
    start = next(r for r in http if r['id'] == request_id and r['stage'] == 'request')
    failure = next(r for r in http if r['id'] == request_id and r['stage'] == 'failure')
    assert failure['errorType'] == 'TimeoutError'
    latencies.append(failure['time'] - start['time'])
construction = [next(r for r in http if r['id'] == i and r['stage'] == 'request')['time']
                - next(r for r in compose if r['id'] == i - 1 and r['stage'] == 'input')['time']
                for i in inventory_ids]
write(BASE / 'COMPOSE_BOUNDARY762/DIAGNOSIS.json', {
    'utc': now, 'inventory_http_calls': len(inventory_ids), 'errors': 'TimeoutError',
    'http_call_seconds': latencies, 'compose_before_post_seconds': construction,
    'http_posts_sha256': sha(http_path), 'compose_boundary_sha256': sha(compose_path),
    'projection_reached_request': True, 'windows': 20, 'selected_total': 24,
    'interpretation': 'Every inventory call exhausted the4s budget. The final retry stack may mask the first wire timeout; it does not prove slow startup or no HTTP request. Exact output observed separately in763.',
    'product_or_survey_credit': False,
})
planned_path = PRIVATE / 'C03-inventory-output763-private/planned.json'
results_path = PRIVATE / 'C03-inventory-output763-private/results.json'
planned, results = read(planned_path), read(results_path)
assert len(planned) == len(results) == read(BASE / 'INVENTORY_OUTPUT763/PREREG.json')['calls'] == 1
captured = next(r['payload'] for r in http if r['id'] == 3 and r['stage'] == 'request')
assert planned[0]['payload'] == captured
user_text, situation = captured['messages'][-1]['content'].split('\nsituation: ', 1)
facts, _ = json.JSONDecoder().raw_decode(situation)
response = results[0]['response']
reply = response['choices'][0]['message']['content']
defect = window_fact_defect(reply, facts, user_text)
assert defect == '' and response['choices'][0]['finish_reason'] == 'stop'
assert not results[0]['within4s']
write(BASE / 'INVENTORY_OUTPUT763/ADJUDICATION.json', {
    'utc': now, 'actual_calls_planned': 1, 'actual_calls_completed': 1,
    'erratum': 'Original RESULT.calls_planned=2 is a stale driver constant. PREREG.calls, planned payloads and results all contain1; original bytes remain unchanged.',
    'payload_exactly_matches762_request3': True, 'planned_sha256': sha(planned_path),
    'results_sha256': sha(results_path), 'content_correct': True, 'current_window_validator_defect': defect,
    'manual_criterion': 'All20 returned identities and repeated entries in observed order, partial20/24 scope, no unobserved chronology. Localized explorer process names retain identity; no title data published.',
    'seconds': results[0]['seconds'], 'finish_reason': 'stop', 'usage': response['usage'],
    'timings': response['timings'], 'within_original4s': False, 'product_pass': False, 'coverage_added': 0,
    'limits': 'One frozen local request, not repeated-seed or end-to-end performance.15s observation changes no product deadline; cwd matches the registered interpreter, other inherited environment not certified identical.',
})
markdown(BASE / 'STATUS_BATCH761/REPORT.md', '''# Estado del PC: regresión con fuente760

Los mismos73 casos completos (50 humanos y23 de desarrollo) produjeron51 respuestas acreditadas y22 fallos sustantivos. Cada respuesta se adjudicó contra sus propias lecturas frescas y el criterio congelado689/729. Las dos acreditaciones adicionales respecto de752B no demuestran una mejora causada por760: cambiaron los valores observados y la redacción. El bloqueo de inventario sigue abierto. RESULT.json conserva decisiones por caso y sensibilidades semánticas; no se impone una frase literal a un modelo.

Los fallos se reparten entre inventario sin entregar (2), interpretación del inventario (3), foco correcto vetado (1), lectura fresca ausente (2), etiquetas de RAM (2), lectura admitida no seleccionada (7), Internet no observado (1), alcance WLAN ampliado (1), métrica y miembros CPU (2) y orden de RAM (1). Los18 rechazos del borrador de foco pertenecen a un solo caso.

El árbol del producto conducido alcanzó3499,56MiB de VRAM y2503,35MiB de RAM residente sumada, sin cortes de recursos. Duración273,344s; mediana de traza por turno0,956s y máximo27,473s, incluidos los reintentos. No acredita interfaz, voz ni consumo conjunto final. Fuente, manifiesto, runner y DLL permanecieron intactos.

Se añadieron referencias de evidencia a50 filas de la encuesta, conservando literalmente su procedencia, expectativas y estados. Siguen26 cubiertos/716 abiertos/0 no aplicables. Preguntas, respuestas y hechos completos permanecen en el directorio privado C03-status-batch761-private, en RESPUESTAS.md y ADJUDICACION.md. Los diagnósticos762–763 aíslan la composición que aún falla; no cambian esta puntuación.
''')
markdown(BASE / 'COMPOSE_BOUNDARY762/REPORT.md', '''# Dónde se corta la lista

El observador pasivo confirmó que la proyección760 llega a la petición:20 identidades, alcance parcial20/24 y ausencia de fechas de apertura. Construir esa petición consume como máximo unas centésimas de segundo. Las seis llamadas de inventario agotan el presupuesto de cuatro segundos; no se entrega una lista final.

El último traceback aparece al preparar un reintento con el presupuesto agotado. El transporte puede haber ocultado el primer timeout de HTTP: ese traceback no demuestra que arrancar el servidor sea lento ni que no se haya enviado nada. El observador preserva argumentos, resultados y excepciones; su preflight está conservado. EXIT.json verifica que no cambió la fuente ni el observador durante la corrida.

763 observa la misma petición más allá de ese límite para ver la salida censurada. Este diagnóstico no añade cobertura ni modifica el producto, el modelo o su receta.
''')
markdown(BASE / 'INVENTORY_OUTPUT763/REPORT.md', '''# Lista completa observada después del corte

La petición exacta capturada en762 termina en4,141s con20 entradas y alcance20/24, sin inventar fechas de apertura. Son727 tokens de entrada y174 de salida, stop normal:407ms de prefill y3717ms de generación (46,81tokens/s). La lectura manual y el verificador de ventanas actual aceptan su contenido. Sigue siendo un fallo frente al límite original de cuatro segundos; no se transforma en un éxito de producto.

Se permitió observar15s, conservando payload, sampler y límite256 de salida. El directorio del servidor coincide con el del intérprete registrado; el resto del entorno heredado no se certifica idéntico. Una muestra no acredita estabilidad de latencia. El servidor alcanzó3495,56MiB de VRAM y718,11MiB de RAM residente, sin guarda activada; no es BAXY con UI/voz.

La selección de tiempo en MindSidecarClient ya reserva nueve segundos al modelo para respuestas densas, pero sólo cuenta requiredFacts. Este inventario llega dentro de situation y recibe cuatro. Siguiente reparación: reconocer ese volumen observado con la política existente, validar y medir la entrega real antes de acreditarla. No ampliar el límite global ni cambiar el modelo.

Errata conservada: RESULT.json dice calls_planned=2 por una constante heredada; PREREG, planned.json, resultados y petición ejecutada muestran exactamente una llamada. ADJUDICATION.json deja la corrección sin reescribir los bytes originales. Encuesta26/716/0; C03 activo.
''')
checkpoint = ('761–763 terminados y adjudicados:761=51/73 acreditadas,22fallos; sin ganancia causal atribuida a760. '
    '50filas encuesta reciben evidencia conservando26/716/0.762seis HTTP agotan4s; construcción0–0,016s. '
    '763misma petición termina correcta20/24 en4,141s/174tokens/stop; fuera4s, no pass producto. '
    'Errata calls_planned=2 conservada/corregida enADJUDICATION; ejecución real1. '
    'No procesos activos. Siguiente: clasificar inventario verificado en presupuesto dense existente, MindSidecarClient.cs:170. '
    'No cambiar modelo/prompt/timeoutglobal. RegistroSHA=' + sha(registry) + '. C03 activo.\n\n')
cp = BASE / 'CHECKPOINT.md'
if not cp.read_bytes().startswith(checkpoint.encode('utf-8')):
    pending_checkpoint = cp.with_suffix('.pending.md')
    pending_checkpoint.write_bytes(checkpoint.encode('utf-8') + cp.read_bytes())
    pending_checkpoint.replace(cp)
markdown(BASE / 'HANDOFF.md', '''# Handoff C03 — diagnósticos761–763 — 2026-09-10

Goal íntegro activo en Goal-c03, main intacto. Fuente760 publicada438bcddee678e4bca4e07bc6e72bb3a9d9231b8c. Encuesta742/rev1248:26 cubiertos/716 abiertos/0NA, sin pregunta pendiente. BAXY manual cerrado. No inferencia/gate activo;16332 y21610 terminal0 recogidos,763 terminó directamente.

761:73casos originales689/729,51 acreditados/22fallos;2 diferencias respecto752B por valores/redacción, no ganancia causal. H0655 distingue total/free/installed en respuesta completa; H0114 redondea correctamente. Audio H0383/audio-status-en conserva criterio752B. Sensibilidades enRESULT. Se añadieron50 referencias privadas de evidencia sin tocar estados/procedencia/expectativas; SHA y respaldo enREGISTRY_UPDATE.

762:proyección760 efectiva20/24,2702caracteres de mensajes,256tokens de salida. Seis llamadas agotan4s; construir payload0–0,016s. El último traceback del reintento no identifica el primer error HTTP ni prueba arranque lento. 763:misma petición aislada correcta4,141s,727prompt/174output,stop,46,81t/s, validador actual acepta. No pass4s/producto. Errata original calls_planned=2 documentada: sólo1planeada/ejecutada.

Siguiente: src/Baxy.App/MindSidecarClient.cs:170 SelectMessageCompositionTimeout. Clasifica dense sólo por requiredFacts>=8/>=512caracteres o partialMission; window.resolve20 llega en situation JSON string, no requiredFacts. Usar política dense existente(10sApp/9smodelo) para inventario sustancial verificado, con contrastes dueños PlannerAppBoundaryTests.cs:371–462. No timeoutglobal/prompt/modelo nuevo. Root implementa; revisión acotada sólo lectura ya recibida.

Otros bloqueos: inventario H0209/H0663/EN vetado, foco fiel rechazado18veces, lecturas ausentes/frescura, RAM mal etiquetada, interfaz-up confundida con Internet, CPU acumulada presentada como uso actual y orden de RAM incorrecto. Reparar primera capa, categorías completas73 tras cambio validado.

760:950pass finales ventana,474pass/1skip ambiental integridad;4303pass+121subtests previos solapados. Fastexit0/Release25,13s/0warnings/errors. Programa407=7fbbf3a59f96fdcf799dc50583bb846792908866f990e3443c2b0f33448fd6c9, tres raíces experiments/voice_latency+scripts+src/baxy_mind. No tocar SOURCE_PINS751 ni sellos históricos. Full7 histórico4574.NETpass/1skip agregado+16omisiones opt-in;11399Pythonpass/3skips+466subtests. Full siguiente adopción conjunta C#+Python y Full final obligatorios.

Preocupación del dueño preservada:699aisló50tareas completas×6perfiles sinBAXY;737aisló57paresK2 de prompt,14sóloBAXY/3sólo directo. Ningún ganador universal/promoción. Recursos761=3499,56MiBGPU/2503,35MiBRSS producto conducido sinUI/voz;763sólo servidor. Faltan cobertura completa, reserva,UI/loopback/AEC, recursos conjuntos≤4GiB, matriz/continuidad y Full final. Preservar WIP ajeno.
''')
relevo_path = BASE / 'RELEVO_ACTIVO.json'
relevo = read(relevo_path)
relevo.update(confirmedAtUtc=now, workStatus='diagnostics763_adjudicated_pending_publication',
    checkpoint=checkpoint.strip(), activeValidation=None, activeReadOnlyAgent=None,
    continuation='Publish evidence761-763; repair existing dense composition classification with owners and registered regression.',
    previousGoalTurnClassification='progress',
    previousGoalTurnClassificationReason='Adjudicated73 registered turns and isolated4s cutoff from complete4.141s output; next source repair identified.',
    latestProductRun={'name':'product761','sessionId':16332,'exitCode':0,'turns':73,
        'manifestUnchanged':True,'adjudication':'51accredited/22substantive failures; no automatic coverage'},
    surveyRegistrySha256=sha(registry))
write(relevo_path, relevo)
paths = []
for directory, names in {
    'STATUS_BATCH761': ['PREREG.json','PROCESS.json','RESOURCES.json','EXIT.json','RESULT.json','REGISTRY_UPDATE.json','REPORT.md'],
    'COMPOSE_BOUNDARY762': ['PREREG.json','PROCESS.json','RESOURCES.json','EXIT.json','OBSERVER_PREFLIGHT.json','DIAGNOSIS.json','REPORT.md'],
    'INVENTORY_OUTPUT763': ['PREREG.json','PROCESS.json','RESULT.json','ADJUDICATION.json','REPORT.md'],
}.items():
    paths.extend(BASE / directory / name for name in names)
paths.extend(ROOT / 'scratchpad' / name for name in [
    'c03-adjudicate-status761.py','c03-review-status761.py','c03-compose-boundary762.py',
    'c03-compose762-hook/sitecustomize.py','c03-observer-preflight762.py','c03-inventory-output763.py',
    'c03-record-evidence763.py'])
paths.append(BASE / 'SEMANTIC_INVENTORY760/PUBLICATION.json')
assert all(path.is_file() for path in paths)
normalization = {}
for path in paths:
    raw = path.read_bytes()
    canonical = raw.replace(b'\r\n', b'\n')
    if raw == canonical:
        continue
    assert path.suffix == '.json', 'Executed drivers must retain their original bytes'
    original = PRIVATE / 'C03-evidence763-originals' / path.relative_to(BASE)
    original.parent.mkdir(parents=True, exist_ok=True)
    if original.exists():
        assert original.read_bytes() == raw
    else:
        original.write_bytes(raw)
    path.write_bytes(canonical)
    normalization[path.relative_to(ROOT).as_posix()] = {
        'original_sha256': hashlib.sha256(raw).hexdigest(), 'public_lf_sha256': sha(path),
        'original_private': str(original),
    }
normalization_path = BASE / 'INVENTORY_OUTPUT763/PUBLICATION_PREPARATION.json'
write(normalization_path, {'public_json_line_endings': normalization,
    'intermediate_failures': [
        'Checkpoint direct write returned OSError22 before modifying it; resumed with atomic replacement.',
        'Git LF conversion caused the first pin verification to reject6public JSON files. Original bytes are preserved privately, public JSON canonicalized and pins rechecked.',
    ], 'source_changed': False})
paths.append(normalization_path)
artifact_pins = {path.relative_to(ROOT).as_posix(): sha(path) for path in paths}
write(BASE / 'INVENTORY_OUTPUT763/PINS.json', artifact_pins)
paths.extend(BASE / name for name in ['INVENTORY_OUTPUT763/PINS.json','CHECKPOINT.md','HANDOFF.md','RELEVO_ACTIVO.json'])
subprocess.run(['git','add','--',*[p.relative_to(ROOT).as_posix() for p in paths]], check=True)
for path, digest in artifact_pins.items():
    assert hashlib.sha256(subprocess.check_output(['git','show',':'+path])).hexdigest() == digest, path
print(json.dumps({'staged':len(paths),'artifact_pins':len(artifact_pins),'counts':counts,'registry_sha256':sha(registry)}))
