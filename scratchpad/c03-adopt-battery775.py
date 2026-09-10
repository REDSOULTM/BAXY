"""Adopt775 after real actor recovery in777; retain unresolved776 findings."""
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
OUT = BASE / 'BATTERY_ACTOR775'
PRODUCT = BASE / 'STATUS_BATCH777'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
RUN = PRIVATE / 'C03-status-batch777-private'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert not (OUT / 'ADOPTION.json').exists()
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only']).strip()
pins = read(OUT / 'SOURCE_PINS.json')
assert all(sha(ROOT / p) == h for p, h in pins.items())
exit777 = read(PRODUCT / 'EXIT.json')
assert exit777['exit_code'] == 0 and all(exit777[k] for k in ['manifest_unchanged', 'sources_unchanged',
    'source775_unchanged', 'source764_unchanged', 'runner_unchanged', 'app_dll_unchanged'])
rows = read(RUN / 'review.json')
assert len(rows) == 17 and all(r['core_calls'] == ['system.status'] for r in rows)
repaired = [r for r in rows if any(c.get('reason') for c in r['compose'])]
assert [r['case_id'] for r in repaired] == ['H0665']
assert repaired[0]['compose'][0]['draft'] == 'Tengo el 100% de batería.'
assert repaired[0]['compose'][0]['reason'] == 'wrong_machine_actor'
assert repaired[0]['terminal']['final'] == 'Tiene el 100% de batería.'
now = datetime.now(timezone.utc).isoformat()
verdicts = []
md = ['# Adjudicación777', 'Los17casos cumplen su criterio frente a su lectura fresca. No cubre los cuatro hallazgos causales de776.']
for row in rows:
    reason = ('Primera persona de BAXY detectada y reparada conservando100%; sujeto de la respuesta ligado al equipo de la consulta.'
              if row['case_id'] == 'H0665' else 'Respuesta fiel a porcentaje/estado de carga/alimentación observados y al idioma solicitado.')
    verdict = {k: row[k] for k in ['case_id', 'turn_id', 'group']}
    verdict.update(correct=True, category='verified_actor_repair' if row['case_id'] == 'H0665' else 'verified_answer', reason=reason)
    verdicts.append(verdict)
    md += [f"## {row['turn_id']} · {row['case_id']}", '**Entrada:** ' + row['text'],
           '**Respuesta:** ' + row['terminal']['final'], '**Criterio:** ' + row['criterion'], '**Adjudicación:** PASS. ' + reason]
result = {'utc': now, 'source_parent_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          'source_pins': 'BATTERY_ACTOR775/SOURCE_PINS.json', 'source_adoption': 'Containing commit',
          'cases': 17, 'correct': 17, 'failed': 0, 'fresh_reads': 17, 'real_actor_repairs': 1,
          'method': 'Root reviewed all17 complete replies against their fresh payloads, including actual first/retry H0665.',
          'resources': read(PRODUCT / 'RESOURCES.json'), 'verdicts': verdicts,
          'coverage_added': 0, 'survey': {'covered': 26, 'open': 716, 'not_applicable': 0},
          'limits': 'Same seven original battery cases plus ten existing development variants as774, all physical observations100%/AC/not charging. '
                    'No UI/voice/reserve credit; four unsupported causal relations remain in synthetic776.',
          'private_pins': {n: sha(RUN / n) for n in ['review.json', 'compose-audit.jsonl', 'turn-audit.jsonl', 'shell-trace.jsonl']}}
assert not result['resources']['violations']
write(PRODUCT / 'RESULT.json', result)
write(RUN / 'adjudication.json', result)
(RUN / 'ADJUDICACION.md').write_bytes(('\n\n'.join(md) + '\n').encode('utf-8'))
(PRODUCT / 'REPORT.md').write_bytes('''# La corrección de sujeto funciona en BAXY

Los17casos de batería cumplen el criterio con lecturas frescas. H0665 vuelve a producir el mismo borrador que falló en774, «Tengo el100% de batería». El nuevo detector activa la corrección existente y publica «Tiene el100% de batería», conservando el dato y el referente del equipo. Traza737,301ms con la corrección incluida; H0359 mantiene lectura y respuesta correctas en439,173ms.

Modelo, primer prompt, sampler inicial y presupuestos siguen iguales; la reparación usa la receta de actor ya medida. Los otros16casos conservan sus respuestas correctas. Duración32,437s incluyendo arranque; pico3497,56MiB VRAM y2167,32MiB RAM residente sumada. Todas las guardas intactas, sin violaciones. Sesión20301 terminó0 y fue recogida.

Esta evidencia demuestra reparación real del sujeto que776 no ejercitó. Los cuatro hallazgos de causalidad añadida en776 siguen sin acreditar; no se relaja su criterio ni se concede cobertura de encuesta.26cubiertos/716abiertos/0NA. UI, voz, reserva y consumo conjunto final siguen pendientes; C03 activo.
'''.encode('utf-8'))
registry = PRIVATE / 'C03-survey-requirements336-private/requirements.jsonl'
before_sha = sha(registry)
assert before_sha == 'e170fc33bdf15b57961588fd33afe3dbbda7dd82f33b56b0178a1a6d59ecb17f'
backup = RUN / 'requirements-before777.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
before = [json.loads(line) for line in backup.open(encoding='utf-8-sig')]
after = copy.deepcopy(before)
humans = {v['case_id']: v for v in verdicts if v['case_id'].startswith('H')}
assert len(humans) == 5
for row in after:
    if row['case_id'] not in humans:
        continue
    verdict = humans[row['case_id']]
    row.setdefault('verification_evidence', []).append({'campaign': 'STATUS_BATCH777',
        'source_parent_commit': result['source_parent_commit'], 'candidate_source_pins': str(OUT / 'SOURCE_PINS.json'),
        'source_adoption': str(OUT / 'ADOPTION.json'), 'case_id': row['case_id'], 'turn_id': verdict['turn_id'],
        'literal_diagnostic_correct': True, 'category': verdict['category'], 'registered_runtime': True,
        'private_adjudication': str(RUN / 'adjudication.json'), 'no_hooks': True, 'coverage_credit': False,
        'ui_or_voice_credit': False, 'synthetic_generalization': str(BASE / 'BATTERY_VALUES776/ADJUDICATION.json')})
    row['verification_reason'] = '777: literal y variantes de categoría correctos; reparación de sujeto real H0665.776 conserva46pass/4relaciones causales sin acreditar. Sin crédito automático de cobertura/UI/voz.'
    row['verification_updated_at'] = now
allowed = {'verification_evidence', 'verification_reason', 'verification_updated_at'}
assert len(after) == 742 and Counter(r['verification_status'] for r in after) == {'open': 716, 'covered': 26}
assert all({k: v for k, v in a.items() if k not in allowed} == {k: v for k, v in b.items() if k not in allowed} for a, b in zip(before, after))
assert sum(a != b for a, b in zip(before, after)) == 5
registry.write_bytes(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in after).encode('utf-8'))
write(PRODUCT / 'REGISTRY_UPDATE.json', {'utc': now, 'before_sha256': before_sha, 'after_sha256': sha(registry),
    'snapshot_private': str(backup), 'changed_rows': 5, 'fields_changed': sorted(allowed), 'coverage_added': 0,
    'all_protected_fields_unchanged': True, 'counts': result['survey']})
for name in ['final', 'fast']:
    raw = (Path(os.environ['TEMP']) / f'c03-battery-actor775-{name}.log').read_bytes()
    (OUT / (name + '.log')).write_bytes(raw.replace(b'\r\n', b'\n'))
validation = read(OUT / 'VALIDATION.json')
validation.update(adoption_pending_real_composer=False, product='77717/17, one actual actor repair; all guards intact.',
                  synthetic='77646/50; four causal relations unaccredited. No repair executed in776.',
                  all_source_pins_unchanged_after_validation=True)
write(OUT / 'VALIDATION.json', validation)
write(OUT / 'ADOPTION.json', {'utc': now, 'status': 'adopted_after_owners_fast_and_real_actor_repair',
    'commit': 'Containing commit', 'source_pins': 'SOURCE_PINS.json', 'coverage_added': 0,
    'real_evidence': 'STATUS_BATCH777 H0665 actual rejected draft and corrected final with unchanged observed percentage.',
    'open': '776 four added causal relations; no battery-category coverage claim.'})
(OUT / 'REPORT.md').write_bytes('''# El sujeto de la batería pasa por la corrección compartida

El detector de posesión de hardware en primera persona incluye ahora la batería cuando existe esa observación. Reconoce porcentajes, posesivos y carga/descarga en español e inglés; conserva las frases sobre haber leído un dato o no saberlo. Usa la misma ruta de corrección de actor que CPU y conectividad, con su borrador real y hechos originales; no añade respuestas visibles fijas ni otro presupuesto.

56controles nuevos cubren operación/plan, ausencia de batería, sujeto apropiado, falta de observación, conservación de hechos y receta específica del modelo.261dueñas iniciales pasaron; conjunto final483pass/1skip ambiental de datos STT privados ausentes,5,63s. Fast terminó0, Release20,67s, cero advertencias y errores. Cinco pins actuales intactos; programa407 actualizado, sellos históricos y veredicto V8 intactos. El fallo inicial de fixture de idioma está conservado y explicado en PLAN.json.

777 demuestra la reparación en el producto:17/17respuestas fieles y H0665 transforma el borrador real «Tengo el100% de batería» en «Tiene el100% de batería», sin cambiar el dato.776 añade50fixtures sintéticos con modelo real:46cumplen íntegramente, cuatro añaden causalidad no observada y permanecen abiertos. No hubo reintentos en776; no se usa como prueba de reparación del sujeto.

La fuente se adopta para el defecto de actor demostrado, sin declarar cerrada toda la familia ni acreditar UI/voz/reserva. No nuevo Full por esta reparación sóloPython; Full final pendiente. Encuesta26cubiertos/716abiertos/0NA; C03 activo.
'''.encode('utf-8'))
note = ('775 adoptado tras483pass/1skipSTT/5,63s,Fast0/20,67s y77717/17 con reparación real H0665(Tengo→Tiene)737,301ms. '
        '77650fixtures=46pass/4causalidad añadida interpretativamente sensible; todosdatoscorrectos,0reintentos. '
        '777todasguardastrue,3497,56MiB/2167,32MiB/32,437s. RegistroSHA=' + sha(registry) + ';26/716/0. '
        'Sesiones30493/20301 terminal0 recogidas, no procesoactivo. Publicar775/776/777; conservar cuatro hallazgos de causalidad y seguir bloqueos de lectura completos.\n\n')
cp = BASE / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
pending.write_bytes(note.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(checkpoint=note.strip(), confirmedAtUtc=now, activeValidation=None,
    workStatus='battery_actor775_adopted_pending_publication',
    continuation='Publish775 source plus776/777 evidence. Battery actor defect repaired; preserve4 unsupported causal relations in776. '
                 'Next bounded blocker is shared current-date/time request gates; entire clock category, no another inventory prompt tweak.')
write(BASE / 'RELEVO_ACTIVO.json', state)
paths = []
for folder, names in [(OUT, ['SOURCE_PINS.json', 'PROGRAM.json', 'PLAN.json', 'VALIDATION.json', 'ADOPTION.json', 'REPORT.md',
                            'owners-language-fixture-error.log', 'owners.log', 'final.log', 'fast.log']),
                      (BASE / 'BATTERY_VALUES776', ['PREREG.json', 'READY.json', 'RESULT.json', 'ADJUDICATION.json', 'REPORT.md', 'CASOS_SINTETICOS.md']),
                      (PRODUCT, ['PREREG.json', 'PROCESS.json', 'EXIT.json', 'RESOURCES.json', 'REVIEW_CAPTURE.json', 'RESULT.json', 'REGISTRY_UPDATE.json', 'REPORT.md'])]:
    paths.extend(folder / name for name in names)
paths.extend(ROOT / 'scratchpad' / name for name in ['c03-prepare-battery775.py', 'c03-battery-values776.py',
    'c03-record-values776.py', 'c03-status-batch777.py', 'c03-review-status777.py', 'c03-adopt-battery775.py'])
for path in paths:
    path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
artifact_pins = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
write(OUT / 'PINS.json', artifact_pins)
paths += [OUT / 'PINS.json'] + [ROOT / p for p in pins] + [BASE / n for n in ['CHECKPOINT.md', 'RELEVO_ACTIVO.json']]
subprocess.run(['git', 'add', '--', *[p.relative_to(ROOT).as_posix() for p in paths]], check=True)
for p, h in {**pins, **artifact_pins}.items():
    assert hashlib.sha256(subprocess.check_output(['git', 'show', ':' + p])).hexdigest() == h, p
subprocess.run(['git', 'diff', '--cached', '--check'], check=True)
print(json.dumps({'source_pins': len(pins), 'artifact_pins': len(artifact_pins), 'registry_sha256': sha(registry), 'staged': True}))
