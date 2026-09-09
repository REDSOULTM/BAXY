"""Keep the complete baseline608 including clarification and grammar failures."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-effect-controls608'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-effect-controls608-private'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def rows(path):
    with path.open(encoding='utf-8-sig') as stream:
        return list(map(json.loads, stream))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

assert not (out / 'RESULT.json').exists()
assert read(out / 'EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
panel = read(private / 'panel.json')
finals = [row for row in rows(private / 'capture/events.jsonl') if row.get('type') == 'terminal']
assert len(panel) == len(finals) == 12
failures = {
    'H0012': 'Identity question is replaced by an interpretation failure.',
    'missing-app': 'Asks the necessary application, but the preposition in the published question is ungrammatical. Correct clarification intent; prose defect retained.',
    'missing-value': 'No useful final: missing_literal_fact in original and recovery. Missing volume value should elicit a clarification.',
    'missing-reference-en': 'Declares an unsupported capability instead of clarifying missing content, recipient or reference.',
    'knowledge-discourse': 'Correct scientific content, but gender agreement in ciertos bacterias is wrong; naturalness defect retained.',
}
adjudication = [{**case, 'ordinal': i, 'terminal': terminal,
                 'verdict': 'failed' if case['case_id'] in failures else 'correct',
                 'reason': failures.get(case['case_id'], 'Meets the declared semantic, language and naturalness criterion.')}
                for i, (case, terminal) in enumerate(zip(panel, finals), 1)]
audit = rows(private / 'turn-audit.jsonl')
assert all(not row.get('final', {}).get('effect_operations') for row in audit if row.get('phase') == 'final')
write(private / 'adjudication.json', adjudication)
report = ['# Línea base608: 7 de 12 finales correctos',
          'Cinco fallos conservados, distinguiendo dos errores gramaticales de las tres conductas incorrectas. No se interpreta terminal publicado como respuesta correcta. Sin operaciones de efecto en los finales del audit; no acredita UI ni voz.']
for row in adjudication:
    report += [f"## {row['ordinal']} · {row['case_id']}", row['text'], row['terminal']['final'],
               row['verdict'] + ': ' + row['reason']]
report += ['## Composición y progreso: candidatos, no prueba de pantalla',
           '```json\n' + json.dumps(rows(private / 'compose-audit.jsonl'), ensure_ascii=False, indent=2) + '\n```']
(private / 'RESULT.md').write_text('\n\n'.join(report) + '\n', encoding='utf-8', newline='\n')
result = {'utc': datetime.now(timezone.utc).isoformat(), 'source': 606,
          'finals':12, 'correct_finals':7, 'failed_cases':failures,
          'survey':{'covered':24,'open':718,'not_applicable':0},
          'resources':read(out / 'resources.json'), 'no_effect_operations_in_final_audit':True,
          'ui_or_voice_credit':False, 'private_hashes':{name:sha(private / name) for name in ['adjudication.json','RESULT.md','capture/events.jsonl','turn-audit.jsonl','compose-audit.jsonl']}}
write(out / 'RESULT.json', result)
(out / 'RESULT.md').write_text('''# Línea base608: contraste antes de la reparación de presentación

7 de 12 finales correctos. Persisten la pregunta de identidad H0012, la aclaración del valor de volumen y la referencia inglesa incompleta. Se conservan también dos defectos gramaticales, en la pregunta de aplicación y la explicación de fotosíntesis. Ningún fallo se elimina del resultado por ser una causa distinta.

El literal H0021 y las tres variantes de identidad ES/EN/mixta responden correctamente. No se modifica aún su cobertura de encuesta: 24 cubiertos / 718 abiertos / 0 no aplicables. El contraste posterior debe repetir exactamente el panel y mantener todos los controles antes de adoptar la proyección607. Fuente606, runtime registrado sin modificaciones, sin hooks ni crédito de interfaz o voz. Informes literales privados y sus huellas en RESULT.json.
''', encoding='utf-8', newline='\n')
write(out / 'PINS.json', {p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
print(json.dumps({'correct':7,'total':12,'failed_cases':list(failures)}))
