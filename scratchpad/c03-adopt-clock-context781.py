"""Record measured781/782 and adjudicate the two date requirements explicitly."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import os
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'CLOCK_CONTEXT781'
PRODUCT = BASE / 'STATUS_BATCH782'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
RUN = PRIVATE / 'C03-status-batch782-private'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not (OUT / 'ADOPTION.json').exists()
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
pins = read(OUT / 'SOURCE_PINS.json')
assert all(sha(ROOT / p) == h for p, h in pins.items())
exit782 = read(PRODUCT / 'EXIT.json')
assert exit782['exit_code'] == 0 and all(v for k, v in exit782.items() if k.endswith('_unchanged'))
product = read(RUN / 'review.json')
prior = read(PRIVATE / 'C03-status-batch779-private/review.json')
assert len(product) == 74
assert all((a['case_id'], a['text'], a['criterion']) == (b['case_id'], b['text'], b['criterion']) for a, b in zip(product[:50], prior))
assert all(r['core_calls'] == ['system.time'] for r in product)
assert product[45]['terminal']['final'] == 'Marka las 16:34.'
assert product[49]['terminal']['final'] == 'Son las 16:34.'
assert not any(c.get('reason') for r in product for c in r['compose'])
assert all(r['terminal']['kind'] == 'published_final' for r in product)
now = datetime.now(timezone.utc).isoformat()
counts = {'covered': 28, 'open': 714, 'not_applicable': 0}
verdicts, markdown = [], ['# Adjudicación 782', 'Root revisó las 74 respuestas completas y las observaciones frescas; no se infiere corrección del estado terminal.']
for index, row in enumerate(product, 1):
    correct = index != 46
    reason = ('Hora correcta; Marka es una falta de ortografía retenida como fallo, sin reemplazo ni veto literal.' if not correct
              else 'Respuesta fiel al dato pedido y a su lectura fresca; respeta el idioma o presentación explícita. Las continuaciones conservan el antecedente humano.')
    verdict = {k: row[k] for k in ['case_id', 'turn_id', 'group']}
    verdict.update(correct=correct, category='verified_answer' if correct else 'spelling_naturalness', reason=reason)
    verdicts.append(verdict)
    markdown += [f"## {row['turn_id']} · {row['case_id']}", '**Entrada:** ' + row['text'],
                 '**Respuesta:** ' + row['terminal']['final'], '**Criterio:** ' + row['criterion'],
                 ('**PASS:** ' if correct else '**FAIL:** ') + reason]
latencies = [r['trace_duration_ms'] for r in product]
result = {'utc': now, 'source_parent_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'source_pins': 'CLOCK_CONTEXT781/SOURCE_PINS.json', 'source_adoption': 'Containing commit',
    'cases': 74, 'correct': 73, 'failed': 1, 'original_category_correct': 15, 'original_category_total': 15,
    'preserved779_panel_correct': 49, 'preserved779_panel_total': 50, 'new_chained_correct': 24,
    'fresh_reads': 74, 'real_retries': 0, 'method': 'Root reviewed all complete replies against fresh observations. Same50 cases/order/criteria as779 plus24 declared chained turns. Development, not native model ranking.',
    'resources': read(PRODUCT / 'RESOURCES.json'), 'latency_ms': {'p50': statistics.median(latencies), 'max': max(latencies)},
    'fixed_t50': {'before779_ms': prior[49]['trace_duration_ms'], 'after782_ms': product[49]['trace_duration_ms'],
                 'before_fresh_read': False, 'after_fresh_read': True},
    'verdicts': verdicts, 'coverage_added': 2, 'survey': counts,
    'limits': 'No UI, voice, reserve or final combined resource credit. Real clock crosses16:34 to16:35 at t57. Values780 is separate synthetic composer evidence, not repeated after781; llm.py unchanged.',
    'private_pins': {n: sha(RUN / n) for n in ['review.json', 'compose-audit.jsonl', 'turn-audit.jsonl', 'shell-trace.jsonl']}}
assert not result['resources']['violations']
write(PRODUCT / 'RESULT.json', result)
write(RUN / 'adjudication.json', result)
(RUN / 'ADJUDICACION.md').write_bytes(('\n\n'.join(markdown) + '\n').encode('utf-8'))

registry = PRIVATE / 'C03-survey-requirements336-private/requirements.jsonl'
before_sha = sha(registry)
assert before_sha == '7b60937e2a3b22d9d887d4e01849b3d0cb6225d0bf4fb78b9ccbde1eaf372d32'
backup = RUN / 'requirements-before782.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
before = [json.loads(line) for line in backup.read_text(encoding='utf-8-sig').splitlines()]
after = copy.deepcopy(before)
humans = {v['case_id']: v for v in verdicts if v['case_id'].startswith('H')}
assert len(humans) == 12 and all(v['correct'] for v in humans.values())
covered = {'H0180', 'H0499'}
for row in after:
    if row['case_id'] not in humans:
        continue
    credit = row['case_id'] in covered
    row.setdefault('verification_evidence', []).append({'campaign': 'STATUS_BATCH782',
        'source_parent_commit': result['source_parent_commit'], 'candidate_source_pins': str(OUT / 'SOURCE_PINS.json'),
        'source_adoption': str(OUT / 'ADOPTION.json'), 'case_id': row['case_id'], 'turn_id': humans[row['case_id']]['turn_id'],
        'literal_diagnostic_correct': True, 'registered_runtime': True, 'no_hooks': True,
        'private_adjudication': str(RUN / 'adjudication.json'),
        'synthetic_generalization': str(BASE / 'CLOCK_VALUES780/ADJUDICATION.json'),
        'coverage_credit': credit, 'ui_or_voice_credit': False})
    row['verification_reason'] = ('Fecha local: originales correctos779/782; variantes ES/EN/mezcla, modalidad y orden, idioma explícito y referencias encadenadas con lecturas frescas. 25fechas sintéticas780 cambian mes, año, día, bisiesto y UTC/offset con el mismo compositor llm.py, inalterado781. Root acredita conducta de fecha, no toda la categoría hora: Marka y veto de mediodía permanecen abiertos.' if credit
        else '782:15/15 originales y73/74 total;74lecturas frescas,24/24 nuevas continuaciones. Persiste ortografía Marka y veto falso de mediodía780. Sin crédito de cobertura de hora.')
    row['verification_updated_at'] = now
    if credit:
        assert row['verification_status'] == 'open' and row['expected_capability'] is True
        row['verification_status'] = 'covered'
        row['generalization_status'] = 'verified_product_variants'
allowed = {'verification_evidence', 'verification_reason', 'verification_updated_at', 'verification_status', 'generalization_status'}
assert len(after) == 742 and Counter(r['verification_status'] for r in after) == {'open': 714, 'covered': 28}
assert all({k:v for k,v in a.items() if k not in allowed} == {k:v for k,v in b.items() if k not in allowed} for a,b in zip(before, after))
assert {a['case_id'] for a,b in zip(before, after) if a['verification_status'] != b['verification_status']} == covered
assert sum(a != b for a,b in zip(before, after)) == 12
registry.write_bytes(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in after).encode('utf-8'))
write(PRODUCT / 'REGISTRY_UPDATE.json', {'utc': now, 'before_sha256': before_sha, 'after_sha256': sha(registry),
    'snapshot_private': str(backup), 'changed_rows': 12, 'new_covered_case_ids': sorted(covered),
    'fields_changed': sorted(allowed), 'all_protected_fields_unchanged': True, 'coverage_added': 2, 'counts': counts,
    'decision': 'Conscious root sufficiency adjudication for date-only requirements, using779/780/782 and owner boundary tests. Remaining hour defects do not contradict either date requirement.'})
for name in ['final', 'fast']:
    raw = (Path(os.environ['TEMP']) / f'c03-clock781-{name}.log').read_bytes()
    (OUT / (name + '.log')).write_bytes(('\n'.join(l.rstrip() for l in raw.decode('utf-8-sig').splitlines()) + '\n').encode('utf-8'))
assert b'3403 passed, 1 skipped in 67.45s' in (OUT / 'final.log').read_bytes()
assert b'source_quality_gate_passed: mode=Fast' in (OUT / 'fast.log').read_bytes()
write(OUT / 'VALIDATION.json', {'utc': now, 'passed': 3403, 'failed': 0, 'environmental_skips': 1,
    'skip': 'Private STT campaign inputs absent; no voice pass.', 'seconds': 67.45, 'new_controls': 62,
    'command': 'registered Python -X utf8 -m pytest tests/test_c03_clock_context.py tests/test_turn_policy.py tests/test_effect_intent.py tests/test_c03_local_clock_scope.py tests/test_c03_request_preservation.py tests/test_price_v8_veto_damage_by_cause.py tests/test_stt_quality_evaluators.py tests/test_validate_physical_wake_v17_program.py -q',
    'fast_command': 'scripts/test_source_quality.ps1 -Mode Fast', 'fast_exit_code': 0, 'session': 47671,
    'terminal_collected': True, 'release_seconds': 18.82, 'warnings': 0, 'errors': 0,
    'source_pins_unchanged': True, 'full_new': False, 'full_reason': 'Python-only change; authority requires new Full for combined C#+Python adoption and final closure.',
    'product_session': 81959, 'product_terminal_collected': True, 'product_exit_code': 0})
write(OUT / 'ADOPTION.json', {'utc': now, 'status': 'adopted_contiguous_human_clock_context',
    'commit': 'Containing commit', 'source_pins': 'SOURCE_PINS.json', 'coverage_added': 2,
    'evidence': 't50 now reads fresh clock and answers; all24 new chained turns correct, original50 now49/50.',
    'open': 'Marka spelling persists in t46; noon780-35 false missing_name veto remains. No whole-category or C03 closure.'})
(OUT / 'REPORT.md').write_bytes('''# BAXY conserva el contexto de las consultas encadenadas al reloj

Tras una pregunta explícita de hora, «¿y la fecha?» y «¿y la hora?», BAXY perdía el antecedente humano y dejaba de consultar el reloj. Ahora recorre únicamente la cadena contigua de preguntas nominales de fecha/hora y se detiene al cambiar de tema. No toma la prosa del asistente ni una hora recordada como autorización. Las demás consultas conservan el último texto humano inmediato. Modelo, prompt, muestreo y validador de valores no cambian.

La regresión dueña pasó 3.403 pruebas, con una omisión ambiental de STT, en 67,45 s. Fast terminó en verde; Release en 18,82 s, sin advertencias ni errores. Incluye 62 controles nuevos de continuidad, cambios de tema y límites de autoridad. No se ejecutó un nuevo Full para este cambio exclusivamente Python; sigue pendiente el Full final exigido por el objetivo.

782 repite los mismos 50 casos de779 y añade 24 turnos encadenados: 73/74 correctos y 74 lecturas frescas, sin reintentos. El turno que antes decía desconocer la hora ahora la consulta y responde en 375,295 ms. Los 24 nuevos turnos pasan y recogen el cambio real de minuto. Persiste «Marka» en t46: dato correcto, ortografía incorrecta. Tampoco se ha corregido todavía el veto de780 a «las 12 del mediodía»; es un defecto separado del validador de BAXY. No se añaden filtros literales para ocultar ninguno.

Se acreditan H0180 y H0499, consultas de fecha local: variantes del producto en español, inglés y mezcla, modalidad, orden y referencias; más 25 fechas sintéticas780 con distintos valores y offsets, sobre el compositor que permanece intacto. La decisión es individual y explícita: los defectos pendientes de hora no invalidan la conducta de fecha. Registro: 28 cubiertos, 714 abiertos, 0 no aplicables de742; expectativas y procedencia preservadas.

La comparación nativa699 y el contraste de instrucciones737 siguen separados.737 observó tres aciertos directos de K2 que empeoraron al añadir el prompt de BAXY, en una pasada por caso. No es una comparación completa de modelos ni prueba de causalidad de una regla individual. Qwen sigue provisional; los fallos de integración no descartan K2.
'''.encode('utf-8'))
(PRODUCT / 'REPORT.md').write_bytes('''# Reloj real782: continuidad recuperada

73/74 respuestas correctas, 74 lecturas frescas y cero reintentos. Los 15 originales y los 24 nuevos turnos encadenados pasan; el panel50 de779 mejora de48 a49. Sólo t46 conserva la falta de ortografía «Marka». La mediana fue429,5955ms y el máximo1734,108ms; el turno50 reparado tarda375,295ms.

La campaña duró55,563s con pico3497,56MiB de VRAM y2470,38MiB de RAM residente sumada del árbol del conductor. Todas las guardas permanecieron intactas; sesión81959 recogida con exit0. Estas cifras no acreditan UI visible, voz, reserva ni el consumo conjunto final del producto. Respuestas, observaciones y adjudicación completas permanecen en el registro privado local.
'''.encode('utf-8'))
note = ('781 adoptada, publicación pendiente:3403pass/1skipSTT/67,45s;Fast0/Release18,82s. '
        '782:73/74correctos,74lecturas,24/24continuaciones; t50 reparado375,295ms, t46Marka persiste. '
        'H0180/H0499 fecha acreditados explícitamente con779/780/782;28/714/0, registroSHA=' + sha(registry) + '. '
        'Sesiones47671/81959 recogidas0; ningún proceso activo. Siguiente publicar781/782 y reparar falso veto de mediodía en llm.py.\n\n')
cp = BASE / 'CHECKPOINT.md'
cp.write_bytes(note.encode('utf-8') + cp.read_bytes())
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(checkpoint=note.strip(), confirmedAtUtc=now, activeValidation=None,
    surveyVerificationCounts=counts, surveyRegistrySha256=sha(registry),
    workStatus='clock_context781_adopted_pending_publication', previousGoalTurnClassification='progress',
    previousGoalTurnClassificationReason='Context regression repaired,74 complete product turns adjudicated, two date requirements explicitly covered.',
    continuation='Publish781+782, then repair shared clock value extraction for noon/midnight false veto. Preserve typo; no literal filter. Inventory strategy must change after768/771.')
write(BASE / 'RELEVO_ACTIVO.json', state)
print(json.dumps({'adopted':781, 'result':'73/74', 'survey':counts, 'registry_sha256':sha(registry)}))
