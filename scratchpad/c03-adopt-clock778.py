"""Publish verified clock-scope improvement while retaining both779 defects."""
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
OUT = BASE / 'CLOCK_SCOPE778'
PRODUCT = BASE / 'STATUS_BATCH779'
VALUES = BASE / 'CLOCK_VALUES780'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
RUN = PRIVATE / 'C03-status-batch779-private'
VALUE_RUN = PRIVATE / 'C03-clock-values780-private'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rows = lambda p: [json.loads(line) for line in p.read_text(encoding='utf-8-sig').splitlines()]


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not (OUT / 'ADOPTION.json').exists()
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
pins = read(OUT / 'SOURCE_PINS.json')
assert all(sha(ROOT / p) == h for p, h in pins.items())
exit779 = read(PRODUCT / 'EXIT.json')
assert exit779['exit_code'] == 0 and all(v for k, v in exit779.items() if k.endswith('_unchanged'))
product = read(RUN / 'review.json')
assert len(product) == 50
assert sum(r['core_calls'] == ['system.time'] for r in product) == 49
assert product[45]['terminal']['final'] == 'Marka las 16 horas y 13 minutos.'
assert product[49]['terminal']['final'] == 'No sé la hora exacta.'
assert product[49]['core_calls'] == []
assert not any(c.get('reason') for r in product for c in r['compose'])
now = datetime.now(timezone.utc).isoformat()
counts = {'covered': 26, 'open': 716, 'not_applicable': 0}
verdicts, markdown = [], ['# Adjudicación779', 'Revisión de las50respuestas completas frente a sus hechos frescos.']
for index, row in enumerate(product, 1):
    correct = index not in {46, 50}
    category = 'spelling_naturalness' if index == 46 else 'missing_fresh_read_chained_ellipsis' if index == 50 else 'verified_answer'
    reason = ('La hora coincide, pero Marka es una falta de ortografía en la salida; se conserva como defecto de naturalidad, sin filtro literal.'
              if index == 46 else 'Tras hora explícita→fecha elíptica, la segunda elipsis pierde la lectura fresca; la incertidumbre publicada no satisface una consulta normal al reloj.'
              if index == 50 else 'Respuesta al dato pedido, con fecha/hora fiel a la lectura fresca; se respeta idioma o instrucción explícita de presentación.')
    verdict = {k: row[k] for k in ['case_id', 'turn_id', 'group']}
    verdict.update(correct=correct, category=category, reason=reason)
    verdicts.append(verdict)
    markdown += [f"## {row['turn_id']} · {row['case_id']}", '**Entrada:** ' + row['text'],
                 '**Respuesta:** ' + row['terminal']['final'], '**Criterio:** ' + row['criterion'],
                 ('**PASS:** ' if correct else '**FAIL:** ') + reason]
latencies = [r['trace_duration_ms'] for r in product]
result = {'utc': now, 'source_parent_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'source_pins': 'CLOCK_SCOPE778/SOURCE_PINS.json', 'source_adoption': 'Containing commit',
    'cases': 50, 'correct': 48, 'failed': 2, 'original_category_correct': 15, 'original_category_total': 15,
    'baseline772_original_correct': 11, 'fresh_reads': 49, 'real_retries': 0,
    'method': 'Root read all50 complete replies and projected facts; retained typo and second-ellipsis missing read. Development, not native model ranking.',
    'resources': read(PRODUCT / 'RESOURCES.json'), 'latency_ms': {'p50': statistics.median(latencies), 'max': max(latencies)},
    'verdicts': verdicts, 'coverage_added': 0, 'survey': counts,
    'limits': 'No visible UI, voice, reserve or final combined resource credit. All observed dates/times are one real local minute/date. Values780 is separate synthetic composer evidence.',
    'private_pins': {n: sha(RUN / n) for n in ['review.json', 'compose-audit.jsonl', 'turn-audit.jsonl', 'shell-trace.jsonl']}}
assert not result['resources']['violations']
write(PRODUCT / 'RESULT.json', result)
write(RUN / 'adjudication.json', result)
(RUN / 'ADJUDICACION.md').write_bytes(('\n\n'.join(markdown) + '\n').encode('utf-8'))

cases = read(VALUE_RUN / 'cases.json')
answers = rows(VALUE_RUN / 'replies.jsonl')
posts = rows(VALUE_RUN / 'posts.jsonl')
value_result = read(VALUES / 'RESULT.json')
assert len(cases) == len(answers) == 50 and len(posts) == 51
assert value_result['fatal'] is None and not value_result['violations']
assert all(v for k, v in value_result.items() if k.endswith('_unchanged'))
assert all(a['error'] is None and a['answer'] for a in answers)
assert all(p['payload']['temperature'] == 0 and p['payload']['max_tokens'] == 256 for p in posts)
posts_by_id = {c['id']: [p for p in posts if p['id'] == c['id']] for c in cases}
assert all(posts_by_id[a['id']][-1]['response']['choices'][0]['message']['content'] == a['answer'] for a in answers)
assert sum(posts_by_id[a['id']][0]['response']['choices'][0]['message']['content'] == a['answer'] for a in answers) == 49
assert [key for key, value in posts_by_id.items() if len(value) > 1] == ['clock780-35']
assert posts_by_id['clock780-35'][0]['response']['choices'][0]['message']['content'] == 'Son las 12 del mediodía.'
assert all(p['payload']['cache_prompt'] is False and p['payload']['chat_template_kwargs']['enable_thinking'] is False for p in posts)
assert all(p['response']['choices'][0]['finish_reason'] == 'stop' for p in posts)
value_md = ['# Casos sintéticos780: fecha y hora locales',
    '50fixtures declarados;25valores UTC/offset por dos peticiones. Compositor BAXY local con sus instrucciones, validadores y reintentos activos; no modelo nativo aislado, provider, UI, voz ni reserva humana. Root leyó las50respuestas completas frente al resultado UTC+offset. Todas cumplen.']
for case, answer in zip(cases, answers):
    value_md += [f"## {case['id']} · {case['language']} · PASS", '**Entrada sintética:** ' + case['request'],
        '```json\n' + json.dumps({'observed': case['situation']['observed'], 'expected_clock': case['expected_clock'], 'expected_date': case['expected_date']}, ensure_ascii=False, indent=2) + '\n```',
        '**Respuesta:** ' + answer['answer'], '**Criterio:** ' + case['criterion']]
adjudication780 = {'utc': now, 'correct': 50, 'failed': 0, 'posts': 51, 'raw_equals_final': 49, 'repairs': 1,
    'finish_stop': 51, 'temperature': 0, 'max_tokens': 256, 'source_pins_unchanged': True,
    'method': 'Root semantic review of every final and expected local value, plus independent RO review recalculating all50 UTC+offset values. One pass; all attempts retained.',
    'false_veto': {'case_id': 'clock780-35', 'draft': 'Son las 12 del mediodía.', 'reason': 'missing_name',
                   'expected': '12:00', 'final': 'Son las 12:00.', 'assessment': 'Valid first draft falsely rejected; both drafts correct, integration defect remains open.'},
    'scope': 'BAXY composer with25 UTC/offset fixtures,25time+25date, ES/EN/mixed; no selector/provider/UI/voice/reserve credit.',
    'preflight': 'First pre-server attempt stopped before directories or inference: observed has version in addition to UTC/offset. Retained version1 and changed only UTC/offset before the single executed pass.',
    'max_call_seconds': max(a['seconds'] for a in answers), 'resources': value_result,
    'private_pins': {n: sha(VALUE_RUN / n) for n in ['cases.json', 'replies.jsonl', 'posts.jsonl', 'compose-audit.jsonl']},
    'verdicts': [{'case_id': c['id'], 'correct': True, 'reason': 'Requested local date/time faithful to supplied UTC plus offset.'} for c in cases],
    'coverage_added': 0}
write(VALUES / 'ADJUDICATION.json', adjudication780)
(VALUES / 'CASOS_SINTETICOS.md').write_bytes(('\n\n'.join(value_md) + '\n').encode('utf-8'))

registry = PRIVATE / 'C03-survey-requirements336-private/requirements.jsonl'
before_sha = sha(registry)
assert before_sha == '72fae04c61cdf7d8cdf57fddf86220cce46bc9628014fdc9f383eb450fca750a'
backup = RUN / 'requirements-before779.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
before = rows(backup)
after = copy.deepcopy(before)
humans = {v['case_id']: v for v in verdicts if v['case_id'].startswith('H')}
assert len(humans) == 12 and all(v['correct'] for v in humans.values())
for row in after:
    if row['case_id'] not in humans:
        continue
    row.setdefault('verification_evidence', []).append({'campaign': 'STATUS_BATCH779',
        'source_parent_commit': result['source_parent_commit'], 'candidate_source_pins': str(OUT / 'SOURCE_PINS.json'),
        'source_adoption': str(OUT / 'ADOPTION.json'), 'case_id': row['case_id'], 'turn_id': humans[row['case_id']]['turn_id'],
        'literal_diagnostic_correct': True, 'registered_runtime': True, 'no_hooks': True,
        'private_adjudication': str(RUN / 'adjudication.json'), 'synthetic_generalization': str(VALUES / 'ADJUDICATION.json'),
        'coverage_credit': False, 'ui_or_voice_credit': False})
    row['verification_reason'] = '779:15/15 originales,48/50 total; pendientes naturalidad y segunda elipsis sin lectura.780:50/50 valores sintéticos. No crédito automático de cobertura.'
    row['verification_updated_at'] = now
allowed = {'verification_evidence', 'verification_reason', 'verification_updated_at'}
assert len(after) == 742 and Counter(r['verification_status'] for r in after) == {'open': 716, 'covered': 26}
assert all({k: v for k, v in a.items() if k not in allowed} == {k: v for k, v in b.items() if k not in allowed} for a, b in zip(before, after))
assert sum(a != b for a, b in zip(before, after)) == 12
registry.write_bytes(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in after).encode('utf-8'))
write(PRODUCT / 'REGISTRY_UPDATE.json', {'utc': now, 'before_sha256': before_sha, 'after_sha256': sha(registry),
    'snapshot_private': str(backup), 'changed_rows': 12, 'fields_changed': sorted(allowed),
    'all_protected_fields_unchanged': True, 'coverage_added': 0, 'counts': counts})
for name in ['final', 'fast']:
    raw = (Path(os.environ['TEMP']) / f'c03-clock778-{name}.log').read_bytes()
    normalized = '\n'.join(line.rstrip() for line in raw.decode('utf-8-sig').splitlines()) + '\n'
    (OUT / (name + '.log')).write_bytes(normalized.encode('utf-8'))
assert b'2298 passed, 1 skipped in 62.08s' in (OUT / 'final.log').read_bytes()
assert b'source_quality_gate_passed: mode=Fast' in (OUT / 'fast.log').read_bytes()
write(OUT / 'VALIDATION.json', {'utc': now, 'passed': 2298, 'failed': 0, 'environmental_skips': 1,
    'skip': 'Private blind STT campaign inputs absent; not a voice pass.', 'seconds': 62.08, 'new_controls': 104,
    'command': 'registered Python -X utf8 -m pytest tests/test_c03_local_clock_scope.py tests/test_effect_intent.py tests/test_c03_calendar_date.py tests/test_c03_request_preservation.py tests/test_stt_quality_evaluators.py tests/test_validate_physical_wake_v17_program.py -q',
    'fast_command': 'scripts/test_source_quality.ps1 -Mode Fast', 'fast_exit_code': 0,
    'fast_session': 70616, 'fast_terminal_collected': True, 'release_seconds': 1.77, 'warnings': 0, 'errors': 0,
    'all_current_source_pins_unchanged_after_validation': True, 'full_new': False,
    'product': '77915/15originals,48/50total; two explicit failures retained.', 'synthetic': '78050/50',
    'adoption_scope': 'Input-scope improvement only; no whole clock category or C03 completion.'})
write(OUT / 'ADOPTION.json', {'utc': now, 'status': 'adopted_shared_input_scope_improvement',
    'commit': 'Containing commit', 'source_pins': 'SOURCE_PINS.json', 'coverage_added': 0,
    'evidence': '772 four original clock reads absent;779 all15 originals read fresh and answer correctly.78050 synthetic values preserved.',
    'open': '779 variant31 spelling Marka; variant35 second consecutive nominal follow-up missing fresh read.780-35 valid noon wording falsely rejected missing_name.'})
(OUT / 'REPORT.md').write_bytes('''# Las consultas al reloj comparten una sola regla de reconocimiento

La selección directa, la lectura por cláusula y el veto de dominio usaban tres gramáticas distintas. Ahora comparten un lector de petición completa y las mismas formas verbales para separar cláusulas. Se conservan el envoltorio de cortesía, los infinitivos con pronombre y las elipsis contextuales existentes. Las fechas de eventos, otras ciudades, definiciones, pasado, negación y contenido literal no autorizan una lectura local. El cambio reduce20líneas netas de fuente; no cambia modelo, instrucciones del LLM, muestreo ni presupuestos.

104controles nuevos y la regresión dueña:2298pass,1skip ambiental de STT,62,08s. Fast0 y Release1,77s sin advertencias ni errores. El primer candidato y sus fallos están conservados; la revisión previa a779 localizó la ausencia del infinitivo pasarme. Todas las fuentes quedaron selladas antes de repetir la validación.

779 conserva la categoría completa de15casos y añade35variantes. Los15originales pasan, frente a11/15 en772. En el conjunto completo hay48pass/2fail: una falta de ortografía (Marka) y pérdida de una segunda elipsis consecutiva que deja el último turno sin lectura fresca. No se ocultan ni se corrigen con un veto literal.780 añade50fixtures sintéticos de composición: todos conservan fechas/horas en cambios de día, mes, año, año bisiesto y offsets de minutos. Su caso35 demuestra un veto incorrecto: Son las12del mediodía es válido para12:00, pero missing_name pidió un reintento. Ambos borradores son correctos; el defecto de integración queda abierto.

Se adopta la reparación demostrada de comprensión, sin cerrar la categoría. No es una comparación del modelo nativo ni aceptación de UI, voz o reserva. La comparación nativa699 y el contraste737 permanecen separados:737 mostró tres respuestas correctas directas que empeoraron al añadir instrucciones de BAXY. Qwen continúa como candidato local provisional, sin atribuir esos fallos de integración a K2.

Encuesta26cubiertos/716abiertos/0NA. Se añaden referencias para12casos, sin cambiar estados. C03 continúa activo; Full final pendiente conforme a la autoridad vigente.
'''.encode('utf-8'))
(PRODUCT / 'REPORT.md').write_bytes('''# Reloj real779: se recuperan las cuatro lecturas originales

15/15casos originales correctos y48/50en el panel ampliado;49lecturas frescas,0reintentos. Los fallos restantes son la ortografía Marka en una variante y una segunda elipsis consecutiva que publica desconocimiento sin consultar el reloj. Las respuestas completas, payloads y decisiones están conservados en el registro privado. Ninguno se convierte en aprobación por haber llegado a un estado terminal.

Duración52,328s incluyendo arranque; pico3497,56MiB VRAM y2493,90MiB de RAM residente sumada del árbol del conductor. Todas las guardas intactas, sin violaciones; sesión65474 terminal0 recogida. No acredita ventana de escritorio, voz, reserva ni consumo conjunto final. Fuente778 adoptada por la mejora original, sin cobertura nueva de encuesta.
'''.encode('utf-8'))
(VALUES / 'REPORT.md').write_bytes('''# Los50valores de fecha y hora se conservan

25capturas UTC con offsets explícitos producen25respuestas de hora y25de fecha. Las50cumplen: incluyen cambio de año, febrero bisiesto/no bisiesto, cambios de mes, medianoche, mediodía y offsets de30/45minutos. Entradas, observaciones sintéticas, expectativas y respuestas literales figuran en CASOS_SINTETICOS.md.

Es el compositor local de BAXY con instrucciones, validadores y reintentos activos.49borradores iniciales coinciden con sus finales. El caso35 produjo Son las12del mediodía, correcto para12:00, y BAXY lo rechazó como missing_name; el reintento publicó Son las12:00, también correcto. Se retiene el veto falso como defecto de integración.51peticiones reales, todas con T0/max_tokens256, thinking desactivado y cache_prompt false; ninguna truncada o fallida. Modelo y comando del servidor conservados respecto de779. La primera preparación se detuvo antes de inferencia porque el fixture omitía reconocer la clave version: se preservó version1 y sólo se variaron UTC/offset. Hubo una sola pasada de50casos, con el reintento incluido.

16,281s incluyendo arranque;3497,56MiB VRAM y757,52MiB RSS sumada en el árbol del compositor. Todas las guardas intactas, sesión21475 terminal0 recogida. No prueba selector, provider, UI, voz ni reserva; tampoco arregla los dos fallos de779 ni concede cobertura automática.
'''.encode('utf-8'))
note = ('778 adoptada, pendiente de publicación:2298pass/1skipSTT/62,08s,Fast0/Release1,77s;104controles. '
    '77915/15originales,48/50total,49lecturas; fallos t46Marka y t50segundaelipsis sin lectura. '
    '78050/50valores,49raw=final,1reintento por veto falso missing_name a12del mediodía. Guardas intactas;65474/21475 recogidas0, sin procesos activos. '
    'RegistroSHA=' + sha(registry) + ';26/716/0. Siguiente: contexto de cadenas de elipsis y veto falso de mediodía, no filtro literal de ortografía.\n\n')
cp = BASE / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
pending.write_bytes(note.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(checkpoint=note.strip(), confirmedAtUtc=now, activeValidation=None,
    workStatus='clock_scope778_adopted_pending_publication', previousGoalTurnClassification='progress',
    previousGoalTurnClassificationReason='Shared input-scope repair restores four real clock reads;100 declared product/composer turns adjudicated, remaining failures preserved.',
    continuation='Publish778+779+780; then inspect prior clock context for chained nominal follow-up and missing_name false veto of noon wording. Preserve Marka spelling defect without literal filter. Inventory strategy must change after768/771.')
write(BASE / 'RELEVO_ACTIVO.json', state)
print(json.dumps({'adopted_scope': '778clock input', 'product': '48/50', 'synthetic': '50/50', 'registry_sha256': sha(registry)}))
