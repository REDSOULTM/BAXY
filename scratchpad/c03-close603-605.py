"""Adjudicate both product runs and each actually verified survey requirement."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


registry = local / 'C03-survey-requirements336-private/requirements.jsonl'
private605 = local / 'C03-conversation-regression605-private'
backup = private605 / 'requirements-before603605.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
requirements = rows(registry)
by_id = {row['case_id']: row for row in requirements}
thanks = {'H0115', 'H0200', 'H0218', 'H0298'}
newly_verified = {'H0120', 'H0145', 'H0502', 'H0517', 'H0657', 'H0717', 'H0032', 'H0241'}
assert Counter(row['verification_status'] for row in requirements) == {'covered': 16, 'open': 726}
for number, source in [(603, 602), (605, 604)]:
    name = f'conversation-regression{number}'
    out = base / ('astra-' + name)
    private = local / ('C03-' + name + '-private')
    assert not (out / 'RESULT.json').exists()
    assert read(out / 'EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
    panel = read(private / 'panel.json')
    finals = [row for row in rows(private / 'capture/events.jsonl') if row.get('type') == 'terminal']
    assert len(panel) == len(finals) == 35
    failures = {'H0012': 'incorrect_interpretation_failure', 'greeting-variant-3': 'unsupported_user_name_attribution'}
    if number == 603:
        failures['thanks-variant-3'] = 'english_sentence_in_spanish_answer'
    adjudication = []
    report = []
    for ordinal, (case, terminal) in enumerate(zip(panel, finals), 1):
        assert terminal['kind'] == 'published_final' and not terminal['timedOut']
        verdict = failures.get(case['case_id'], 'correct')
        row = {**case, 'ordinal': ordinal, 'verdict': verdict, 'terminal': terminal}
        adjudication.append(row)
        report += [f"## {ordinal} · {case['case_id']}", case['text'], terminal['final'], verdict]
    audit = rows(private / 'compose-audit.jsonl')
    report += ['## Composición y progreso: candidatos conservados, no prueba de UI',
               '```json\n' + json.dumps(audit, ensure_ascii=False, indent=2) + '\n```',
               'Los progresos aceptados por el compositor aún usan tercera persona y describen el idioma o análisis interno; esa calidad de la ruta de progreso sigue abierta. published en este audit es aceptación del compositor, no evidencia de visibilidad en la UI. El conteo de finales no se convierte en aceptación completa del turno ni del goal.']
    write(private / 'adjudication.json', adjudication)
    (private / 'RESULT.md').write_text('\n\n'.join(report) + '\n', encoding='utf-8', newline='\n')
    stamp = datetime.now(timezone.utc).isoformat()
    for case in adjudication:
        if not case['case_id'].startswith('H'):
            continue
        requirement = by_id[case['case_id']]
        requirement['verification_evidence'].append({
            'campaign': 'astra-' + name, 'source': str(source) + '; hashes in PREREG',
            'private_adjudication': str(private / 'adjudication.json'),
            'ordinal': case['ordinal'], 'literal_verdict': case['verdict'],
            'group': case['group'], 'ui_or_voice_credit': False,
        })
    for case_id in thanks:
        by_id[case_id].update(
            verification_status='open' if number == 603 else 'covered',
            generalization_status='wrong_language_variant603' if number == 603 else 'all_three_preregistered_variants_verified605',
            verification_reason='603 reopens gratitude: English sentence in Spanish variant. Literal success does not cover failed generalization.' if number == 603 else '605 verifies this literal plus all three ES/EN/mixed gratitude variants;602/604 repairs the603 language regression. No UI/voice or complete C03 progress-route credit.',
            verification_updated_at=stamp,
        )
    if number == 605:
        for case_id in newly_verified:
            measured = next(row for row in adjudication if row['case_id'] == case_id)
            variants = [row for row in adjudication if case_id in row.get('supports', [])]
            assert measured['verdict'] == 'correct' and variants and all(row['verdict'] == 'correct' for row in variants)
            by_id[case_id].update(
                verification_status='covered', generalization_status='literal_and_all_declared_variants_verified605',
                verification_reason=f"605: literal independently correct and all{len(variants)} preregistered ES/EN/mixed variants correct. No credit from another literal's success. H0012 and the Atlas greeting remain separate open failures; broader C03 progress/UI/voice acceptance remains open.",
                verification_updated_at=stamp,
            )
            by_id[case_id]['verification_evidence'][-1]['generalization_cases'] = [row['case_id'] for row in variants]
    status = Counter(row['verification_status'] for row in requirements)
    assert status == ({'covered': 12, 'open': 730} if number == 603 else {'covered': 24, 'open': 718})
    write(private / 'requirements-after-adjudication.json', requirements)
    correct = 35 - len(failures)
    resources = read(out / 'resources.json')
    result = {'source': source, 'finals': 35, 'correct_finals': correct, 'failed_cases': failures,
              'survey': {'covered': status['covered'], 'open': status['open'], 'not_applicable': 0},
              'no_hooks': True, 'manifest_changed': False, 'ui_or_voice_credit': False,
              'progress_route_acceptance': 'open; compose candidates are not proof of UI visibility or adequate final product style',
              'resources': resources, 'private_hashes': {name: sha(private / name) for name in ['RESULT.md', 'adjudication.json', 'requirements-after-adjudication.json']}}
    write(out / 'RESULT.json', result)
    note = f"# Producto{number}: {correct}/35 finales correctos\n\nFuente{source}, modelo/backend registrados sin override ni hooks. Fallos conservados: {failures}. {('Las dos identidades inglesas y los dos casos gramaticales mejoran; aparece una frase inglesa tras un comienzo español en agradecimiento. Se reabren cuatro requisitos:12/730/0.' if number == 603 else 'La guarda por frases y traducción del borrador corrigen esa regresión. Se restauran los cuatro agradecimientos y se verifican individualmente seis identidades y dos conversaciones breves con sus variantes. Encuesta24/718/0. H0021 no se acredita sin repetir su propio literal; H0012 y los saludos con otra identidad permanecen abiertos.')}\n\nGPU{resources['gpu_peak_mib']:.3f}MiB/RAM{resources['ram_peak_mib']:.3f}MiB, {resources['seconds']:.3f}s del escenario. No acredita UI, voz ni recursos conjuntos. Los candidatos de progreso aún requieren mejor prosa y verificación de visibilidad: este conteo es de finales, no aceptación completa de los35turnos ni cierreC03.\n"
    (out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
    write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
    with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(f'/artifacts/comprobaciones/C03/astra-{name}/** -text\n')
    with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write('\n\n' + note)
registry.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in requirements), encoding='utf-8', newline='\n')
summary = read(base / 'SURVEY_REQUIREMENTS336.json')
summary.update(requirements_sha256=sha(registry), validated_current=24,
               verification_counts={'covered':24,'open':718,'not_applicable':0}, updated_at=datetime.now(timezone.utc).isoformat())
write(base / 'SURVEY_REQUIREMENTS336.json', summary)
print('60332/35;60533/35. Survey16→12→24 covered,718 open; original742/rev1248 unchanged.')
