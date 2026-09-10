"""Record full manual selector review and the paired instruction comparison."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03/K2_HORIZON_SELECTOR700'
old = root / 'artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696'
private_root = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
plan = read(base / 'PLAN.json')
fresh = 'No propone la lectura actual disponible; responde desde historia o datos no observados.'
manual = {
    'qwen-without-policy700': {
        **{k: fresh for k in ['select-disk-used-es','select-H0532','select-H0359','select-cpu-order-es','select-H0450','select-H0499','select-H0602','select-H0675','select-audio-order-es']},
        'select-clock-date-en': 'Niega una operación de fecha que sí está disponible.',
        'select-network-internet-es': 'Afirma conexión a Internet sin observación ni herramienta disponible.',
        'select-control-past-en': 'Propone leer este PC ante una afirmación sobre ayer, sin petición actual.',
        'select-control-other-machine-es': 'Propone leer este PC para una pregunta sobre otro equipo.',
        'select-control-process-memory-es': 'Elige estado general en vez de la lista de procesos solicitada.',
        'select-control-disk-order-es': 'Niega poder leer disco pese a disponer de system.status.',
    },
    'k2-without-policy700': {
        **{k: fresh for k in ['select-disk-used-es','select-cpu-order-es','select-H0602','select-H0675','select-audio-order-es']},
        'select-H0532': 'Final vacío sin propuesta de lectura disponible; posible fallo de protocolo, no conocimiento probado.',
        'select-H0359': 'Reutiliza batería del historial sin lectura y filtra un marcador de razonamiento.',
        'select-H0499': 'Final vacío sin propuesta de fecha disponible; posible fallo de protocolo.',
        'select-clock-date-en': 'Inventa una fecha desde la hora y no propone la lectura disponible.',
        'select-control-past-en': 'Propone una lectura actual sin petición, ante una afirmación sobre ayer.',
        'select-control-other-machine-es': 'Propone leer este PC para una pregunta sobre otro equipo.',
        'select-control-process-memory-es': 'Añade system.status a process.list aunque sólo se pidió la lista de procesos.',
    },
}
records = []
for tag, failures in manual.items():
    family = 'qwen' if tag.startswith('qwen') else 'k2'
    baseline = plan['baselines'][family]
    folder = base / ('run-' + tag)
    private = private_root / f'C03-k2-ablation700-{tag}-private'
    review = read(private / 'review.json')
    metrics = read(folder / 'MEASUREMENTS.json')
    prereg = read(folder / 'PREREG.json')
    parity = [json.loads(line) for line in (folder / 'PAYLOAD_PARITY.jsonl').read_text(encoding='utf-8').splitlines()]
    baseline_grade_path = old / ('run-' + baseline['tag']) / 'ADJUDICATION.json'
    assert sha(baseline_grade_path) == baseline['existing_adjudication_sha256']
    before = {r['id']: r for r in read(baseline_grade_path)['rows'] if r['kind'] == 'selector'}
    assert len(review) == len(before) == len(parity) == metrics['responses'] == 20
    assert all(r['equal_except_removed_system'] for r in parity)
    assert [r['id'] for r in review] == prereg['cases']
    assert set(failures) <= set(before)
    assert metrics['results_sha256'] == sha(private / 'results.jsonl')
    assert not metrics['errors'] and not metrics['resources']['violations'] and metrics['resources']['manifest_unchanged']
    rows = []
    report = [f'# Revisión privada emparejada: {tag}', '', 'Contiene historia privada. No publicar este archivo en Git.', '']
    for r in review:
        passed = r['id'] not in failures
        if passed:
            assert [c['name'] for c in r['calls']] == r['expected_functions'], r['id']
            assert all(json.loads(c['arguments']) == {} for c in r['calls'])
            assert r['calls'] or r['response']['content'].strip(), r['id']
        if r['response'].get('error') or r['response'].get('finish_reason') == 'length':
            assert not passed
        unavailable = bool(r.get('requested_functions_missing_from_supplied_catalog'))
        reason = failures.get(r['id'], 'Cumple selección y límites declarados; no acredita ejecución.')
        if passed and unavailable:
            reason = 'Abstiene sin inventar herramienta ni observación. No satisface la capacidad de Internet ausente del catálogo.'
        row = dict(id=r['id'], passed=passed, before_passed=before[r['id']]['pass'],
            reason=reason, capability_unavailable=unavailable)
        rows.append(row)
        report += [f"## {r['id']} — {'cumple' if passed else 'falla'}", '', '**Conversación completa enviada:**', '']
        for m in r['input']:
            report += [f"**{m['role']}:** {m['content']}", '']
        report += ['**Propuestas recibidas:**', '', '```json', json.dumps(r['calls'], ensure_ascii=False, indent=2), '```', '',
                   '**Texto devuelto por el selector:**', '', r['response']['content'] or '*(Vacío)*', '',
                   '**Criterio:** ' + r['criterion'], '', '**Adjudicación:** ' + reason, '']
    (private / 'RESPUESTAS700_PRIVADO.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    grade = dict(utc=datetime.now(timezone.utc).isoformat(), tag=tag, cases=20,
        passed=sum(r['passed'] for r in rows), failed=sum(not r['passed'] for r in rows),
        before_passed=sum(r['before_passed'] for r in rows), rows=rows,
        gains=[r['id'] for r in rows if r['passed'] and not r['before_passed']],
        regressions=[r['id'] for r in rows if not r['passed'] and r['before_passed']],
        raw_results_sha256=metrics['results_sha256'], measurements_sha256=sha(folder / 'MEASUREMENTS.json'),
        baseline_adjudication_sha256=sha(baseline_grade_path), payload_parity_sha256=sha(folder / 'PAYLOAD_PARITY.jsonl'),
        private_review_sha256=sha(private / 'review.json'), private_report_sha256=sha(private / 'RESPUESTAS700_PRIVADO.md'),
        scope='Manual review of all20 complete inputs and outputs; same frozen criteria and histories. Internal selector prose is not user-visible product prose. Only the first system message was removed. Historical single-seed control, not randomized replication; no C03 coverage or model promotion.')
    (folder / 'ADJUDICATION.json').write_text(json.dumps(grade, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    records.append(dict(family=family, grade=grade, measurements=metrics))
(base / 'SUMMARY700.json').write_text(json.dumps(dict(records=records, cases_per_model=20, new_outputs=40), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
text = ['# Efecto de quitar una instrucción de BAXY', '',
    'En esta categoría, quitar la política del selector empeoró el recuento de ambos perfiles: Qwen pasó de 7/20 a 5/20 y K2 grande high de 10/20 a 8/20. El efecto fue mixto: K2 recuperó una selección de hora y una abstención correcta, pero perdió cuatro casos. Es evidencia de que una instrucción puede perjudicar casos concretos; quitarla no fue una solución general. No demuestra que todas las instrucciones de BAXY ayuden ni que ninguna favorezca a Qwen.', '',
    'Se reutilizaron los20 controles completos de cada perfil y se hicieron40 nuevas llamadas. El runner verificó pesos, backend y paquetes por hash, comando idéntico salvo puerto/log y cuerpo enviado idéntico salvo eliminar el primer system de1056caracteres. Muestreo propio documentado y K2 high; mismo orden/seed. El catálogo y las historias siguen presentes. Estos son controles históricos de una semilla; no una réplica aleatorizada ni una prueba de todo el producto.', '',
    '| Modelo | Con política | Sin política | Mejoras | Regresiones |', '|---|---:|---:|---:|---:|']
for r in records:
    g = r['grade']
    text.append(f"| {r['family']} | {g['before_passed']}/20 | {g['passed']}/20 | {len(g['gains'])} | {len(g['regressions'])} |")
text += ['',
    'La pérdida compartida más clara es seleccionar una lectura actual cuando la persona sólo habla de lo que hizo ayer. En K2, quitar la política también recuperó una selección de hora, pero perdió lecturas de disco/RAM y añadió una operación no solicitada a la lista de procesos. IDs y razones de cada pareja en SUMMARY700.json.', '',
    'Uno de los20 casos pide Internet pero el catálogo suministrado carece de esa operación. K2 sin política se abstiene sin inventar datos: eso cuenta como respetar el límite, no como comprobar Internet. Su8/20 incluye esa abstención; entre los19 con capacidad disponible cumple7/19. Qwen sin política inventa conexión y falla ese caso.', '',
    'Las llamadas usan argumentos vacíos porque se trata de selección; no prueban extracción, autorización, efectos de Windows, GUI o voz. Los finales vacíos de K2 H0532/H0499 no se convierten en respuestas extrayendo razonamiento. Las respuestas completas y las historias quedan en RESPUESTAS700_PRIVADO.md de cada corrida en LOCALAPPDATA; los archivos públicos contienen IDs, adjudicación y hashes.', '',
    'Esto se une a las300 respuestas originales699. Qwen sigue como candidato de trabajo: K2 no ha demostrado una mejora conjunta de calidad, español, latencia y recursos que justifique sustituirlo en estos perfiles locales. Esa decisión no acepta a Qwen para C03 ni descarta universalmente la familia K2. El trabajo de producto debe continuar reparando los fallos compartidos y midiendo cada transformación antes de adoptar cambios.', '',
    'Acoplamientos reales aún pendientes de probar si se promueve otro modelo: llm.py5847–5896 fusiona prefijos system por compatibilidad Qwen3.5; el arranque productivo configura reasoning off. Las APIs aisladas no ejercitan esa fusión, shortlist, reanálisis, argumentos, kernel/providers ni salida de escritorio/voz. No se debe cambiar sólo el GGUF y trasladar sin verificar esas decisiones al nuevo modelo.', '',
    'C03 permanece activo. Encuesta742/rev1248:26cubiertos,716abiertos,0noaplicables. Esta comparación no suma cobertura.',
]
(base / 'REPORTE700.md').write_text('\n'.join(text) + '\n', encoding='utf-8')
print(json.dumps([{k:r['grade'][k] for k in ['tag','passed','failed','before_passed','gains','regressions']} for r in records]))
