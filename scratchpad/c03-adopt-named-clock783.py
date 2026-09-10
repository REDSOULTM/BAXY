"""Adopt verified clock value validation with identical-request composer evidence."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'NAMED_CLOCK783'
VALUES = BASE / 'CLOCK_VALUES784'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
RUN = PRIVATE / 'C03-clock-values784-private'
OLD = PRIVATE / 'C03-clock-values780-private'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
rows = lambda p: [json.loads(l) for l in p.read_text(encoding='utf-8-sig').splitlines()]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not (OUT / 'ADOPTION.json').exists()
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
pins = read(OUT / 'SOURCE_PINS.json')
assert all(sha(ROOT / p) == h for p,h in pins.items())
validation = read(OUT / 'VALIDATION.json')
assert validation['failed'] == 0 and validation['fast_exit_code'] == 0 and validation['terminal_collected']
result = read(VALUES / 'RESULT.json')
assert result['fatal'] is None and not result['violations']
assert all(v for k,v in result.items() if k.endswith('_unchanged'))
cases, answers, posts = read(RUN / 'cases.json'), rows(RUN / 'replies.jsonl'), rows(RUN / 'posts.jsonl')
old_answers, old_posts = rows(OLD / 'replies.jsonl'), rows(OLD / 'posts.jsonl')
assert len(cases) == len(answers) == len(posts) == 50
assert cases == read(OLD / 'cases.json')
assert all(a['error'] is None and a['answer'] for a in answers)
assert all(p['response']['choices'][0]['message']['content'] == a['answer'] for p,a in zip(posts,answers))
assert all(p['payload'] == next(x for x in old_posts if x['id'] == p['id'])['payload'] for p in posts)
assert all(p['payload']['temperature'] == 0 and p['payload']['max_tokens'] == 256 and p['payload']['cache_prompt'] is False for p in posts)
assert all(p['response']['choices'][0]['finish_reason'] == 'stop' for p in posts)
assert not any(r.get('reason') for r in rows(RUN / 'compose-audit.jsonl'))
changed = [a['id'] for a,b in zip(answers,old_answers) if a['answer'] != b['answer']]
assert changed == ['clock780-35']
assert answers[34]['answer'] == 'Son las 12 del mediodía.'
assert next(p for p in old_posts if p['id'] == 'clock780-35')['response']['choices'][0]['message']['content'] == answers[34]['answer']
now = datetime.now(timezone.utc).isoformat()
adjudication = {'utc':now, 'correct':50, 'failed':0, 'posts':50, 'real_retries':0,
    'all_first_http_payloads_identical_to780':True, 'same_cases_ids_values_criteria':True,
    'first_raw_equals_final':50, 'unchanged_finals':49, 'changed_final_ids':changed,
    'noon_repair':{'case_id':'clock780-35','raw_before_and_after':'Son las 12 del mediodía.',
                   'before780':'missing_name then retry Son las 12:00.', 'after784':'Published the first correct raw draft; no repair.'},
    'method':'Root reviewed all50 finals against all expected local values; all inputs and first HTTP payloads compared exactly to780. One pass; no native model ranking.',
    'latency_seconds':{'p50':statistics.median(a['seconds'] for a in answers),'max':max(a['seconds'] for a in answers)},
    'resources':result, 'terminal_session':37453, 'terminal_collected':True, 'exit_code':0,
    'scope':'Local BAXY composer only. No provider, UI, voice, reserve or final combined memory credit. Context781 differs from780 but is not used by this direct composer; first HTTP requests identical.',
    'coverage_added':0, 'survey':{'covered':28,'open':714,'not_applicable':0},
    'private_pins':{n:sha(RUN/n) for n in ['cases.json','replies.jsonl','posts.jsonl','compose-audit.jsonl']},
    'verdicts':[{'case_id':c['id'],'correct':True,'reason':'Complete final preserves requested local date/time and adds no unsupported claim.'} for c in cases]}
write(VALUES/'ADJUDICATION.json',adjudication)
md=['# Fecha y hora: repetición784 de los50casos sintéticos780',
    'Root leyó las50respuestas completas. Mismos casos, valores, criterios y peticiones HTTP iniciales; todos correctos. BAXY conserva ahora el primer borrador correcto de mediodía, antes vetado.']
for c,a in zip(cases,answers):
    md += [f"## {c['id']} · {c['language']} · PASS", '**Entrada sintética:** '+c['request'],
        '```json\n'+json.dumps({'observed':c['situation']['observed'],'expected_clock':c['expected_clock'],'expected_date':c['expected_date']},ensure_ascii=False,indent=2)+'\n```',
        '**Respuesta:** '+a['answer'], '**Criterio:** '+c['criterion']]
(VALUES/'CASOS_SINTETICOS.md').write_bytes(('\n\n'.join(md)+'\n').encode('utf-8'))
write(OUT/'ADOPTION.json',{'utc':now,'status':'adopted_shared_exact_clock_values','commit':'Containing commit',
    'source_pins':'SOURCE_PINS.json','validation':'VALIDATION.json','evidence':'CLOCK_VALUES784/ADJUDICATION.json',
    'coverage_added':0,'open':'Marka spelling in782 remains. Not whole clock category or C03 completion.'})
(OUT/'REPORT.md').write_bytes('''# BAXY deja pasar una hora que el modelo ya había expresado bien

El caso780-35 produjo «Son las 12 del mediodía.» para una observación12:00. BAXY lo rechazó con missing_name y pidió otra respuesta. El parser compartido ahora representa los valores de hora y minuto de formas numéricas, habladas y expresiones exactas de mediodía/medianoche. Los dos validadores usan la misma comprobación; se conserva la detección de valores contradictorios, minutos distintos y12AM/PM. Las nuevas expresiones requieren una afirmación completa: una mención relativa, negada o de un evento no basta. No se añade ninguna respuesta visible fija.

75controles nuevos, incluidos dos recorridos completos de composición con borrador simulado y una sola petición. Regresión final:1.523pass,1skip ambiental de STT,10,23s. Fast0, Release18,99s,0advertencias/errores;81828 recogida0. El primer conjunto tenía siete fixtures en inglés con pregunta española: se corrigió el idioma de las preguntas sin relajar el validador. Las trazas de fallo se conservan. No nuevo Full para esta reparación exclusivamente Python; Full final pendiente.

784 repite50casos sintéticos780: mismos IDs, observaciones, criterios y50peticiones HTTP iniciales byte-equivalentes como objetos JSON. Las50respuestas finales son correctas;49coinciden con el final anterior. El caso35 entrega ahora el mismo primer borrador correcto que780 había rechazado. Se reduce de51a50peticiones; cero reintentos. Modelo, backend, plantilla, prompt, sampler y presupuestos intactos. Esto demuestra una reparación del validador de BAXY, sin atribuir ese fallo al modelo ni promover candidatos.

17,219s incluyendo arranque, pico3497,56MiB VRAM y757,21MiB RSS del árbol del compositor. No son recursos conjuntos finales ni validación de UI/voz/provider/reserva. Todas las guardas intactas;37453 recogida0. Un preflight previo se detuvo antes de inferencia porque encontró la palabra pytest en el comando padre que registraba validación; el mismo ejecutor pasó al lanzarse por separado, sin relajar guardas.

Encuesta28cubiertos/714abiertos/0NA; sin crédito adicional. «Marka» permanece como defecto de ortografía medido en782; no se oculta con reemplazos literales. C03 sigue activo.
'''.encode('utf-8'))
note=('783 adoptada, publicación pendiente:1523pass/1skipSTT/10,23s;Fast0/Release18,99s. '
      '784:50/50correctos,50posts,0retries;50primeros payloads idénticos780,49finalesiguales ycaso35conserva bruto correcto mediodía antes vetado. '
      '3497,56MiB/757,21MiB/17,219s,guardas intactas.81828/37453recogidas0;sinprocesosactivos.28/714/0.\n\n')
p=BASE/'CHECKPOINT.md';p.write_bytes(note.encode()+p.read_bytes())
s=read(BASE/'RELEVO_ACTIVO.json');s.update(checkpoint=note.strip(),activeValidation=None,confirmedAtUtc=now,
    workStatus='named_clock783_adopted_pending_publication',previousGoalTurnClassification='progress',
    previousGoalTurnClassificationReason='Published781/782, covered2date requirements, repaired false noon veto with identical50 first HTTP requests and no retries.',
    continuation='Publish783/784. Remaining clock issue is model raw spelling; attribute without literal veto. Inventory strategy must change after768/771; then whole categories of C03.')
write(BASE/'RELEVO_ACTIVO.json',s)
print(json.dumps({'adopted':783,'correct':50,'identical_first_payloads':50,'retries':0}))
