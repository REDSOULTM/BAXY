"""Adjudicate complete battery-category774 and preserve individual evidence."""
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
OUT = BASE / 'STATUS_BATCH774'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
RUN = PRIVATE / 'C03-status-batch774-private'
SOURCE = '481c2f411aa7eaaf00cc78665953bfdf7bd01586'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == SOURCE
assert not (OUT / 'RESULT.json').exists()
done = read(OUT / 'EXIT.json')
assert done['exit_code'] == 0
assert all(done[k] for k in ['manifest_unchanged', 'sources_unchanged', 'source773_unchanged',
                            'source764_unchanged', 'runner_unchanged', 'app_dll_unchanged'])
rows = read(RUN / 'review.json')
assert len(rows) == 17
assert all(row['core_calls'] == ['system.status'] for row in rows)
verdicts = []
md = ['# Adjudicación774', 'Categoría batería completa: siete casos originales y diez variantes de desarrollo.']
for row in rows:
    correct = row['case_id'] != 'H0665'
    reason = ('Porcentaje o estado de carga fiel a la lectura fresca, con sujeto y lenguaje apropiados.' if correct else
              'Tengo el100% de batería atribuye al asistente una propiedad observada del PC; el porcentaje es fiel pero el sujeto no.')
    verdict = {k: row[k] for k in ['case_id', 'group', 'turn_id']}
    verdict.update(correct=correct, category='verified_answer' if correct else 'wrong_actor', reason=reason)
    verdicts.append(verdict)
    md += [f"## {row['turn_id']} · {row['case_id']}", '**Entrada:** ' + row['text'],
           '**Criterio:** ' + row['criterion'], '**Respuesta:** ' + row['terminal']['final'],
           '**Adjudicación:** ' + ('PASS. ' if correct else 'FAIL. ') + reason]
assert sum(v['correct'] for v in verdicts) == 16
now = datetime.now(timezone.utc).isoformat()
resources = read(OUT / 'RESOURCES.json')
assert not resources['violations']
result = {'utc': now, 'source_commit': SOURCE, 'status': 'complete_battery_category_adjudicated',
          'cases': 17, 'original_category_cases': 7, 'added_development_variants': 10,
          'correct': 16, 'failed': 1, 'fresh_reads': 17, 'coverage_added': 0,
          'method': 'Root manually compared every full reply with this turn\'s fresh battery payload and frozen criterion.',
          'resources': resources, 'verdicts': verdicts,
          'survey': {'covered': 26, 'open': 716, 'not_applicable': 0},
          'limits': 'All observations were100%,present,true AC/not charging. No changed-value or absent-battery evidence, UI/voice credit or model ranking.',
          'diagnosis': 'H0359 now invokes fresh battery read and answers faithfully in433.305ms. H0665 receives fresh data but says Tengo, a separate output-actor defect.',
          'evidence_sha256': {n: sha(RUN / n) for n in ['review.json', 'compose-audit.jsonl', 'turn-audit.jsonl', 'shell-trace.jsonl']}}
write(OUT / 'RESULT.json', result)
write(RUN / 'adjudication.json', result)
(RUN / 'ADJUDICACION.md').write_bytes(('\n\n'.join(md) + '\n').encode('utf-8'))
registry = PRIVATE / 'C03-survey-requirements336-private/requirements.jsonl'
before_sha = sha(registry)
assert before_sha == '728ea559efbbe511e6af5d9210569fe3b58393750d7230378b1b7f31710071b4'
backup = RUN / 'requirements-before774.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
before = [json.loads(line) for line in backup.open(encoding='utf-8-sig')]
after = copy.deepcopy(before)
human = {v['case_id']: v for v in verdicts if v['case_id'].startswith('H')}
assert len(human) == 5
for row in after:
    verdict = human.get(row['case_id'])
    if verdict is None:
        continue
    row.setdefault('verification_evidence', []).append({'campaign': 'STATUS_BATCH774',
        'source_commit': SOURCE, 'case_id': row['case_id'], 'turn_id': verdict['turn_id'],
        'literal_diagnostic_correct': verdict['correct'], 'category': verdict['category'],
        'private_adjudication': str(RUN / 'adjudication.json'), 'registered_runtime': True,
        'no_hooks': True, 'coverage_credit': False, 'ui_or_voice_credit': False,
        'development_variants_in_same_family': [v['case_id'] for v in verdicts if not v['case_id'].startswith('H')]})
    row['verification_reason'] = '774: literal ' + ('acreditado' if verdict['correct'] else 'sin acreditar') + '; ' + verdict['category'] + '. Pendientes valores/carga/ausencia variados; sin crédito UI/voz/conjunto.'
    row['verification_updated_at'] = now
allowed = {'verification_evidence', 'verification_reason', 'verification_updated_at'}
assert len(after) == 742 and Counter(r['verification_status'] for r in after) == {'open': 716, 'covered': 26}
assert all({k: v for k, v in a.items() if k not in allowed} == {k: v for k, v in b.items() if k not in allowed} for a, b in zip(before, after))
assert sum(a != b for a, b in zip(before, after)) == 5
registry.write_bytes(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in after).encode('utf-8'))
write(OUT / 'REGISTRY_UPDATE.json', {'utc': now, 'before_sha256': before_sha, 'after_sha256': sha(registry),
    'snapshot_private': str(backup), 'changed_rows': 5, 'fields_changed': sorted(allowed),
    'coverage_added': 0, 'counts': result['survey'], 'all_protected_fields_unchanged': True})
(OUT / 'REPORT.md').write_bytes('''# Batería: la lectura antes bloqueada ya llega al modelo

La categoría completa contiene siete casos originales y diez variantes declaradas de desarrollo. Las 17 consultas invocaron una lectura fresca de batería; 16 respuestas fueron fieles y una falló por el sujeto. Todas las guardas de fuente, runtime y DLL permanecieron intactas. Sesión21331 terminó0 y fue recogida.

H0359 ahora responde correctamente al porcentaje observado en433,305ms. Las variantes de determinante, nombre del equipo, español, inglés y mezcla también llegan al dato correcto. H0665 dice «Tengo el100% de batería»: el dato es verdadero para el PC, pero se atribuye a BAXY. Es una falla de salida diferente de la interpretación ya reparada, y se conserva como fallo.

Todas las lecturas físicas observaron100%, batería presente, alimentación externa y sin carga activa. Falta comprobar generalización ante otros porcentajes, estados de carga y ausencia de batería con fixtures claramente identificados; no se otorga cobertura todavía. Se añadieron cinco referencias de evidencia, sin cambiar estados ni procedencia:26cubiertos/716abiertos/0NA.

La corrida duró35,25s incluyendo arranque. Pico3495,56MiB VRAM y2151,49MiB RAM residente sumada en el árbol del conductor, sin violaciones. No acredita UI/voz simultáneas ni el consumo conjunto final. Modelo, configuración e instrucciones permanecieron iguales. C03 sigue activo.
'''.encode('utf-8'))
note = ('774 terminada0/21331 recogida,17 consultas con lectura fresca:16pass/1wrong_actor H0665(Tengo). '
        'H0359 correcto433,305ms; todas guardas intactas.3495,56MiB/2151,49MiB/35,25s. '
        'Registro5referencias,SHA=' + sha(registry) + ',26/716/0. '
        'Siguiente aislar sujeto bateria reutilizando reparación CPU573–582 y medir valores/carga/ausencia en fixtures declarados. No inferencia activa.\n\n')
cp = BASE / 'CHECKPOINT.md'
pending = cp.with_suffix('.pending.md')
pending.write_bytes(note.encode('utf-8') + cp.read_bytes())
pending.replace(cp)
state = read(BASE / 'RELEVO_ACTIVO.json')
state.update(checkpoint=note.strip(), confirmedAtUtc=now, activeValidation=None,
             workStatus='battery774_adjudicated_actor_and_value_generalization_pending',
             continuation='Reuse existing CPU wrong-actor detection/correction for battery only after locating cause; prepare declared synthetic percentage/charging/absence generalization. No model promotion or coverage yet.')
write(BASE / 'RELEVO_ACTIVO.json', state)
handoff = BASE / 'HANDOFF.md'
text = handoff.read_text(encoding='utf-8')
text = text.replace('728ea559efbbe511e6af5d9210569fe3b58393750d7230378b1b7f31710071b4', sha(registry))
start = text.index('773 adoptado, pendiente publicación:')
end = text.index('\n\nCambiar estrategia', start)
text = text[:start] + ('773 publicada481c2f411aa7eaaf00cc78665953bfdf7bd01586; HEAD=origin=remoto,6fuentes/15artefactos verificados. '
    '2121pass/1skipSTT/79,73s,55nuevos; Fast0/Release21,94s. Programa407=7862ae1effb430cff9cbb057fa83912786bca493faba55b5c9636b5cd7181b18. '
    '774 categoría batería7+10variantes:17lecturasfrescas,16pass/1wrong_actor H0665(Tengo). H0359 correcto433,305ms; '
    '3495,56MiB/2151,49MiB/35,25s, todasguardastrue,21331terminal0 recogida. STATUS_BATCH774/RESULT y privado ADJUDICACION. '
    'No crédito encuesta todavía: todasobservaciones100%/presente/AC/sincargar. '
    'Siguiente775: agenteRO k2_parser737 localiza por qué detección/corrección de actor CPU no cubre batería. '
    'Heredar573/580/582; nuevos fixtures reales de modelo, explícitamente sintéticos en datos, variando valores/carga/ausencia antes de cobertura. No inferencia activa.') + text[end:]
handoff.write_bytes(text.encode('utf-8'))
print(json.dumps({'correct': 16, 'failed': 1, 'fresh_reads': 17, 'registry_sha256': sha(registry)}))
