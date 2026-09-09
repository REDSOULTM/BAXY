"""Seal the rejected presentation experiment; retain the validated606 source."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
local = Path(os.environ['LOCALAPPDATA']) / 'BAXY'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def rows(path):
    with path.open(encoding='utf-8-sig') as stream:
        return list(map(json.loads, stream))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

for name in ['src/baxy_mind/__main__.py', 'tests/test_turn_policy.py', 'tests/test_price_v8_veto_damage_by_cause.py', 'experiments/stt_quality/audit_fresh_postweight_stt_sources.py', 'experiments/stt_quality/evaluate_reserved_stt.py']:
    committed = subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=root)
    assert committed == (root / name).read_bytes(), name

baseline = read(base / 'astra-effect-controls608/RESULT.json')
failures610 = dict(baseline['failed_cases'])
failures610['H0012'] = 'Classification now remains knowledge, but the model answers Eres tú, compañero instead of identifying itself; still incorrect.'
failures610['physical-effect-en'] = 'A correct capability limit in608 becomes an interpretation failure in610. Observed regression; exact cause still requires native/boundary diagnosis.'
results = {}
for number, name, failures in [
    (610, 'effect-controls610', failures610),
    (611, 'conversation-regression611', {
        'H0012': 'Wrong subject: Eres tú, compañero does not answer who the assistant is.',
        'greeting-variant-3': 'The assistant addresses the user as Atlas, though the user was addressing the assistant; unsupported user-name attribution.',
    }),
]:
    out = base / ('astra-' + name)
    private = local / ('C03-' + name + '-private')
    assert not (out / 'RESULT.json').exists()
    assert read(out / 'EXIT.json') == {'exitCode':0, 'manifest_unchanged':True}
    panel = read(private / 'panel.json')
    finals = [row for row in rows(private / 'capture/events.jsonl') if row.get('type') == 'terminal']
    assert len(panel) == len(finals) == (12 if number == 610 else 35)
    adjudication = [{**case, 'ordinal':index, 'terminal':terminal,
                     'verdict':'failed' if case['case_id'] in failures else 'correct',
                     'reason':failures.get(case['case_id'], 'Meets the declared criterion.')}
                    for index, (case, terminal) in enumerate(zip(panel, finals), 1)]
    write(private / 'adjudication.json', adjudication)
    report = [f'# Producto{number}: {len(panel)-len(failures)}/{len(panel)} finales correctos',
              'Candidato609 rechazado: no mejora la respuesta de identidad y610 pierde un control de capacidad. No se concede cobertura de encuesta a partir de esta fuente.']
    for row in adjudication:
        report += [f"## {row['ordinal']} · {row['case_id']}", row['text'], row['terminal']['final'], row['verdict'] + ': ' + row['reason']]
    report += ['## Candidatos de composición y progreso', '```json\n' + json.dumps(rows(private / 'compose-audit.jsonl'), ensure_ascii=False, indent=2) + '\n```',
               'Este audit no acredita pantalla ni audio. Los finales no son turnos completos aprobados.']
    (private / 'RESULT.md').write_text('\n\n'.join(report) + '\n', encoding='utf-8', newline='\n')
    result = {'source':609, 'finals':len(panel), 'correct_finals':len(panel)-len(failures),
              'failed_cases':failures, 'adopted':False, 'resources':read(out / 'resources.json'),
              'ui_or_voice_credit':False, 'survey_credit_from_this_candidate':0,
              'private_hashes':{file:sha(private / file) for file in ['RESULT.md','adjudication.json','capture/events.jsonl','raw-replies.jsonl','turn-audit.jsonl','compose-audit.jsonl']}}
    write(out / 'RESULT.json', result)
    (out / 'RESULT.md').write_text(f"# Producto{number}: {result['correct_finals']}/{len(panel)} finales correctos\n\nCandidato609 rechazado. H0012 sigue sin respuesta correcta;610 registra además un límite físico inglés que pasa de correcto a fallo de interpretación.611 conserva33/35, con H0012 y atribución Atlas incorrectos. Se restauró exactamente la fuente606 publicada y validada por Full; parche609, tests y todas las salidas se conservan. No se publica el cambio de conducta ni se suma cobertura desde609. Fallos y recursos en RESULT.json; informe literal privado sellado. Sin crédito de UI o voz.\n", encoding='utf-8', newline='\n')
    write(out / 'PINS.json', {p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
    results[number] = result

# H0021 has its own literal and three independently measured identity variants
# on the accepted606 baseline608. Rejected609 supplies no acceptance credit.
registry = local / 'C03-survey-requirements336-private/requirements.jsonl'
private608 = local / 'C03-effect-controls608-private'
backup = private608 / 'requirements-before-H0021.jsonl'
assert not backup.exists()
backup.write_bytes(registry.read_bytes())
requirements = rows(registry)
assert Counter(row['verification_status'] for row in requirements) == {'covered':24, 'open':718}
verified608 = {row['case_id']:row for row in read(private608 / 'adjudication.json')}
support = ['identity-noisy-es','identity-noisy-en','identity-mixed']
assert all(verified608[case]['verdict'] == 'correct' for case in ['H0021',*support])
requirement = next(row for row in requirements if row['case_id'] == 'H0021')
assert requirement['verification_status'] == 'open' and requirement['literal'] == verified608['H0021']['text']
stamp = datetime.now(timezone.utc).isoformat()
requirement.update(verification_status='covered', verification_updated_at=stamp,
                   generalization_status='own_literal_and_three_identity_variants_verified608',
                   verification_reason='Accepted source606 baseline608 independently verifies H0021 and three colloquial ES/EN/mixed identity variants. No credit from rejected609, H0012, or another survey literal. Global progress/UI/voice routes remain open.')
requirement['verification_evidence'].append({'campaign':'astra-effect-controls608','source':606,
    'private_adjudication':str(private608 / 'adjudication.json'), 'ordinal':verified608['H0021']['ordinal'],
    'literal_verdict':'correct','generalization_cases':support,'ui_or_voice_credit':False})
registry.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in requirements),encoding='utf-8',newline='\n')
summary = read(base / 'SURVEY_REQUIREMENTS336.json')
summary.update(requirements_sha256=sha(registry),validated_current=25,
               verification_counts={'covered':25,'open':717,'not_applicable':0},updated_at=stamp)
write(base / 'SURVEY_REQUIREMENTS336.json',summary)

out = base / 'astra-effect-presentation609'
result = read(out / 'IN_PROGRESS.json')
result.update(status='rejected_and_source606_restored',adopted=False,
              product610={'correct':6,'total':12},product611={'correct':33,'total':35},
              product_processes_active=False, survey={'covered':25,'open':717,'not_applicable':0},
              registry_sha256=sha(registry),survey_backup_sha256=sha(backup),
              decision='No final semantic improvement for H0012 and a new capability failure in610. Reject; keep source606. Grammar and missing-argument failures remain independent open causes.')
write(out / 'RESULT.json',result)
note='''# Candidato609 descartado: permanece fuente606

La proyección incompleto→no compatible era una transformación incorrecta para H0012, pero retirarla no bastó:610 y611 responden «Eres tú, compañero», confundiendo el sujeto. El panel608→610 pasa de7/12 a6/12; también falla un límite físico inglés previamente correcto. El panel35 de611 conserva33/35, los mismos dos fallos de identidad. No hay mejora final ni se adopta el candidato.

Se restauraron byte a byte los cinco archivos del parche609 desde la fuente606 publicada. Se conserva candidate609.patch, pruebas1391 pass/1 omisión ambiental/121 subpruebas y Fast0; esos tests no sustituyen la calidad del producto. Full606 sigue correspondiendo exactamente a la fuente vigente; no se reclama Full609. No hay procesos de inferencia ni compuertas activas.

H0021 queda verificado por su propio literal y tres variantes ES/EN/mixta de608, que usó fuente606; no recibe crédito del candidato rechazado. Encuesta25 cubiertos/717 abiertos/0 no aplicables, originales742/rev1248 intactos. H0012, Atlas, aclaraciones de valor/referencia, dos defectos gramaticales y prosa de progreso permanecen abiertos.

Siguiente: aislar atribución de sujeto en el modelo nativo y añadir los componentes de conversación con payload efectivo. No repetir los prompts de guarda594/595 ni promover una clasificación intermedia como respuesta correcta.593 conserva argumentos reales de chat: H0012 tiene temperature0, response_language mixed y saludo previo.610 confirma que, con clasificación knowledge, el borrador invierte el sujeto. Reutilizar investigación Qwen2507/b9980; una comparación controlada no declara inferioridad global del modelo. Perfil registrado, UI/voz conjunta, recursos y resto C03 pendientes.
'''
(out / 'RESULT.md').write_text(note,encoding='utf-8',newline='\n')
write(out / 'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as stream:stream.write('\n\n'+note)
(base/'HANDOFF.md').write_text(note,encoding='utf-8',newline='\n')
state=read(base/'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=stamp,checkpoint='609 rechazado:6106/12 y61133/35. Fuente606 restaurada exacta y publicada bbb3a951; Full606 verde. Encuesta25/717/0, H0021 por608. Sin procesos activos.',continuation='Publicar evidencia608–611, luego aislar sujeto conversacional nativo→instrucciones→historial; H0012 y Atlas abiertos. No promover609. Aclaraciones, gramática, progreso, UI/voz/memoria conjunta y registroCPU pendientes.',surveyVerificationCounts={'covered':25,'open':717,'not_applicable':0})
write(base/'RELEVO_ACTIVO.json',state)
attributes=root/'.gitattributes'
with attributes.open('a',encoding='utf-8',newline='\n') as stream:
    for name in ['astra-effect-controls610','astra-conversation-regression611']:
        stream.write('/artifacts/comprobaciones/C03/'+name+'/** -text\n')
print('609 rejected; source606 exact.6106/12;61133/35. Survey25/717/0; H0021 supported by608 only.')
