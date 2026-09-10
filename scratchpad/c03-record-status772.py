"""Record independently reviewed full772; do not infer quality from terminals."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'STATUS_BATCH772'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
RUN = PRIVATE / 'C03-status-batch772-private'
SOURCE = '098bfd06bc0a7e428675d7a563fe160fd730fe27'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == SOURCE
assert not (OUT / 'RESULT.json').exists()
finished = read(OUT / 'EXIT.json')
assert finished['exit_code'] == 0
assert all(finished[k] for k in ['manifest_unchanged', 'sources_unchanged', 'source771_unchanged',
                              'source764_unchanged', 'runner_unchanged', 'app_dll_unchanged'])
review = read(RUN / 'review.json')
assert len(review) == 73
failures = {}


def fail(ids, category, reason):
    for case_id in ids.split():
        assert case_id not in failures
        failures[case_id] = (category, reason)


fail('H0023', 'inventory_draft_rejected',
     'Fresh20/25 inventory reaches composition but no final list is delivered. Unobserved recency remains in drafts; no generalization gain from the fixed770 observation.')
fail('H0103', 'inventory_draft_rejected',
     'Fresh20/25 inventory reaches composition but no final list is delivered. Grouped drafts lose identities and exact multiplicity, and use a processName as a window title; repeated invented veto.')
fail('H0209 H0663 windows-all-en', 'global_inventory_interpretation',
     'No inventory read; clarification does not fulfill the available explicit read. windows-all-en additionally changes language and narrows scope to foreground.')
fail('H0532 H0675', 'no_fresh_read', 'A current machine fact is asserted without a fresh Core observation.')
fail('H0539 H0655 H0508', 'memory_total_labelled_available',
     'The reply calls16.54GB available although that is total_usable; fresh available is about1.98GB. H0508 has a faithful Windows version but the RAM claim remains wrong.')
fail('H0359 H0450 H0499 H0602 clock-date-en audio-order-es', 'supported_read_not_selected',
     'The available requested read is not invoked; rejection, clarification or failed composition does not fulfill it.')
fail('H0732', 'internet_not_observed', 'The observed network online field reflects interface availability, not a verified Internet connection.')
fail('network-wifi-en', 'wifi_scope_expanded', 'A disconnected Wi-Fi observation is expanded to absence of any network connection.')
fail('network-internet-es', 'no_fresh_read', 'No read is made, but the reply asserts no Internet and an invented failed connection attempt.')
fail('H0364 processes-top2-es', 'cpu_process_metric_and_membership',
     'Lifetime totalProcessorSeconds is presented as current CPU consumption; grouping distinct process instances also changes the requested ranking.')
assert len(failures) == 21
verdicts = []
for row in review:
    category, reason = failures.get(row['case_id'], ('verified_answer',
        'The complete reply fulfills its frozen criterion against this turn\'s fresh observation, with faithful scope, values and language.'))
    verdicts.append({k: row[k] for k in ['case_id', 'group', 'turn_id']} |
                    {'correct': row['case_id'] not in failures, 'category': category, 'reason': reason})
now = datetime.now(timezone.utc).isoformat()
resources = read(OUT / 'RESOURCES.json')
assert not resources['violations']
result = {'utc': now, 'source_commit': SOURCE, 'status': 'complete_registered_regression_adjudicated',
          'cases': 73, 'correct': 52, 'not_accredited': 21, 'substantive_failures': 21,
          'coverage_added': 0, 'survey': {'covered': 26, 'open': 716, 'not_applicable': 0},
          'method': 'Fresh manual review of all73: bounded read-only agents t1-25/t26-50 and root t51-73; all frozen criteria retained.',
          'comparison_limit': 'Same73 panel/runtime but live observations differ;52/73 equals769 without causal improvement. Mixed focus now passes with another wording; H0655 now fails available/usable labeling.',
          'resources': resources, 'panel_sha256': read(OUT / 'PREREG.json')['panel_sha256'],
          'failure_categories': dict(Counter(v['category'] for v in verdicts if not v['correct'])),
          'verdicts': verdicts,
          'evidence_sha256': {n: sha(RUN / n) for n in ['review.json', 'compose-audit.jsonl', 'turn-audit.jsonl', 'shell-trace.jsonl']}}
write(OUT / 'RESULT.json', result)
write(RUN / 'adjudication.json', result)
md = ['# Adjudicación772', '52 respuestas acreditadas y21fallos. Hechos y borradores completos en review.json.']
for row, verdict in zip(review, verdicts):
    md += [f"## {row['turn_id']} · {row['case_id']}", '**Entrada:** ' + row['text'],
           '**Criterio:** ' + row['criterion'], '**Respuesta:** ' + row['terminal']['final'],
           '**Adjudicación:** ' + ('PASS. ' if verdict['correct'] else 'FAIL. ') + verdict['reason']]
(RUN / 'ADJUDICACION.md').write_bytes(('\n\n'.join(md) + '\n').encode('utf-8'))
registry = PRIVATE / 'C03-survey-requirements336-private/requirements.jsonl'
before_sha = sha(registry)
assert before_sha == '85f9ef743313dd906eaece95204dc46f3c644d3f8ba9db307b1bcc8c208899f6'
backup = RUN / 'requirements-before772.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
before = [json.loads(line) for line in backup.open(encoding='utf-8-sig')]
after = copy.deepcopy(before)
humans = {v['case_id']: v for v in verdicts if v['case_id'].startswith('H')}
assert len(humans) == 50
for row in after:
    verdict = humans.get(row['case_id'])
    if verdict is None:
        continue
    row.setdefault('verification_evidence', []).append({'campaign': 'STATUS_BATCH772',
        'source_commit': SOURCE, 'case_id': row['case_id'], 'turn_id': verdict['turn_id'],
        'literal_diagnostic_correct': verdict['correct'], 'category': verdict['category'],
        'private_adjudication': str(RUN / 'adjudication.json'), 'registered_runtime': True,
        'no_hooks': True, 'coverage_credit': False, 'ui_or_voice_credit': False,
        'development_variants_in_same_family': [v['case_id'] for v in verdicts
            if v['group'] == verdict['group'] and not v['case_id'].startswith('H')]})
    row['verification_reason'] = '772: literal ' + ('acreditado' if verdict['correct'] else 'sin acreditar') + '; ' + verdict['category'] + '. Generalización completa pendiente; sin crédito de UI/voz/consumo conjunto.'
    row['verification_updated_at'] = now
allowed = {'verification_evidence', 'verification_reason', 'verification_updated_at'}
assert len(after) == 742 and Counter(r['verification_status'] for r in after) == {'open': 716, 'covered': 26}
assert all({k: v for k, v in a.items() if k not in allowed} == {k: v for k, v in b.items() if k not in allowed} for a, b in zip(before, after))
assert sum(a != b for a, b in zip(before, after)) == 50
registry.write_bytes(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in after).encode('utf-8'))
write(OUT / 'REGISTRY_UPDATE.json', {'utc': now, 'before_sha256': before_sha, 'after_sha256': sha(registry),
    'snapshot_private': str(backup), 'changed_rows': 50, 'fields_changed': sorted(allowed),
    'coverage_added': 0, 'counts': result['survey'], 'all_protected_fields_unchanged': True})
(OUT / 'REPORT.md').write_bytes('''# Tanda772: sin mejora global de entrega

Los73casos completos se revisaron contra sus propias observaciones y criterios congelados:52respuestas acreditadas y21fallos. Todas las guardas de fuente, runtime, conductor y DLL permanecieron intactas. Sesión5226 terminó0 y fue recogida. Pico3499,56MiB de VRAM y2476,46MiB de RAM residente sumada;268,719s, sin violaciones. La medida corresponde al árbol del conductor y no acredita interfaz ni voz simultáneas.

771 permite aceptar las respuestas correctas C/D de770, pero los dos inventarios reales772 todavía fallan. El nuevo contenido observado es diferente y vuelve a aparecer recencia no medida. No se acredita generalización a partir del éxito sobre una entrada fija. El foco mixto pasa esta vez con otra forma de redacción; H0655 vuelve a llamar disponible a la RAM utilizable. El52/73 no demuestra una mejora causal respecto de769.

Las21fallas se distribuyen entre interpretación que impide lecturas, hechos inventados o desactualizados, confusión de magnitudes y entrega de inventarios. La siguiente reparación localizada es una falsa clasificación de hardware ajeno: la preposición española «a» seguida de determinante se interpreta como artículo indefinido inglés. La comprobación determinística de H0359 confirma request=true, scope=battery, pero knowledge_or_diagnosis=true y grounding=false. Es un error de integración independiente del modelo.

Se añadieron50referencias al registro privado manteniendo procedencia, expectativas, literales y estados:26cubiertos/716abiertos/0NA. Las respuestas, payloads y adjudicación legible están en C03-status-batch772-private. C03 sigue activo. No repetir otro ajuste de prompt de inventario como siguiente paso tras dos tandas sin mejora; conservar el defecto para aislar representación de hechos en una comparación controlada posterior.
'''.encode('utf-8'))
note = ('772 terminada0/5226 recogida,73 adjudicados:52 pass/21 fallos; todas guardas true. '
        '3499,56MiB VRAM/2476,46MiB RSS/268,719s. Sin mejora global; inventarios siguen fallando con otra observación. '
        'Registro50 referencias,26/716/0; SHA=' + sha(registry) + '. '
        'Siguiente773: corregir falso hardware ajeno por a+determinante español; diagnóstico de H0359 confirmado, no request-head. No inferencia activa.\n\n')
cp = BASE / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
pending.write_bytes(note.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(checkpoint=note.strip(), confirmedAtUtc=now, activeValidation=None,
             workStatus='status772_adjudicated_next_input_scope773',
             continuation='Publish772 evidence, repair Spanish preposition versus English indefinite article in existing hardware-scope veto; validate generalized positive/negative cases before product regression.')
write(BASE / 'RELEVO_ACTIVO.json', state)
print(json.dumps({'correct': 52, 'failed': 21, 'registry_sha256': sha(registry)}))
