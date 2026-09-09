"""Record unchanged native observation and every resulting identity final."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
out = base / 'astra-observe-identity593'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-observe-identity593-private'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


assert not (out / 'RESULT.json').exists()
assert read(out / 'EXIT.json') == {'exitCode': 0, 'manifest_unchanged': True}
panel = read(private / 'panel.json')
finals = [row for row in rows(private / 'capture/events.jsonl') if row.get('type') == 'terminal']
assert len(panel) == len(finals) == 11
failed = {'H0012', 'identity-variant-1', 'identity-variant-2'}
adjudication = []
report = []
for case, terminal in zip(panel, finals):
    assert terminal['kind'] == 'published_final' and not terminal['timedOut']
    verdict = 'failed' if case['case_id'] in failed else 'correct'
    adjudication.append({**case, 'verdict': verdict, 'terminal': terminal})
    report += [f"## {case['case_id']}", case['text'], terminal['final'], verdict]
write(private / 'adjudication.json', adjudication)
boundaries = rows(private / 'boundaries.jsonl')
assert boundaries[0]['result'] == ['not_complete', 'one']
assert boundaries[1]['kwargs']['conversation_kind'] == 'unsupported'
english = [row for row in boundaries if row['kind'] == 'chat_input' and row['text'] in {'What is your name?', 'Tell me who you are.'}]
assert len(english) >= 2 and all(row['kwargs']['response_language'] == 'en' and row['kwargs']['conversation_kind'] == 'knowledge' for row in english)
report += ['## Fronteras nativas', '```json\n' + json.dumps(boundaries, ensure_ascii=False, indent=2) + '\n```']
(private / 'RESULT.md').write_text('\n\n'.join(report) + '\n', encoding='utf-8', newline='\n')
note = '''# Observación593: dos causas confirmadas, ninguna reparación aún

Los once turnos de identidad repiten exactamente592:8 finales correctos y3 fallidos. La observación delega sin modificar payloads ni respuestas; añade trazas de HTTP, retorno de la guarda y entrada de chat. No es una medición limpia de latencia.

H0012: el selector nativo conserva conocimiento, pero la guarda semántica devuelve `incomplete_effect/one`; su retorno real es `not_complete/one`. `apply_conversation_effect_presentation` convierte entonces la presentación en unsupported. El usuario no pidió un efecto. Falta distinguir una expresión conversacional ruidosa de una acción a la que le falte un argumento; no basta eliminar palabras iniciales por literal.

Las dos preguntas inglesas llegan a chat como knowledge y `response_language=en`. La historia se conserva con sus autores como datos, conforme a fuente512; tanto el borrador como su reintento JSON copian la respuesta española anterior. El reintento habla de respuesta vacía/eco aunque el defecto observado es idioma. No se elimina historia ni se relaja el veto de idioma sin una prueba comparativa.

Base Qwen2507/b9980, sin adaptador ni cambio de registro. GPU3499,559MiB/RAM2400,297MiB,64,469s de escenario con observación. Sin UI/voz. Encuesta16/726/0, sin nuevos requisitos acreditados. C03 sigue activo.
'''
(out / 'RESULT.md').write_text(note, encoding='utf-8', newline='\n')
write(out / 'RESULT.json', {'utc': datetime.now(timezone.utc).isoformat(), 'finals': 11, 'correct': 8, 'failed': sorted(failed), 'source': '122c490f2f93b71de21756c269607c5b25024f04', 'observer_only': True, 'private_hashes': {name: sha(private / name) for name in ['RESULT.md', 'adjudication.json', 'boundaries.jsonl', 'http-posts.jsonl', 'effective-server-command.json']}, 'ui_or_voice_credit': False, 'survey': {'covered': 16, 'open': 726, 'not_applicable': 0}})
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
with (root / '.gitattributes').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('/artifacts/comprobaciones/C03/astra-observe-identity593/** -text\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
print('593 sealed:8 correct/3 failed, both causal boundaries observed.')
