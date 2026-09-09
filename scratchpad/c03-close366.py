"""Adjudicate the completed 366 run without changing its evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03'
base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private = base / 'C03-memory-product366-private'
target = out / 'astra-memory-product366'
events = [json.loads(line) for line in (private / 'capture/events.jsonl').open(encoding='utf-8-sig')]
terminals = [row for row in events if row.get('type') == 'terminal']
assert len(terminals) == 10 and all(not row['timedOut'] and row['admissionStatus'] == 200 for row in terminals)
assert terminals[4]['kind'] == 'composition_failed'
reasons = [
    'Útil: el conjunto del turno explica que guardar falló por memoria deshabilitada y pide confirmar su activación. «I remember» sólo es cierto en esta conversación; no acredita persistencia.',
    'Fallo: no explica la acción cuya confirmación está pendiente.',
    'Fallo: cancelación real, pero respuesta en español durante el intercambio inglés y sin alcance.',
    'Útil: reconoce Jordan desde la conversación; añade un comentario pasado innecesario pero cierto.',
    'Fallo: silencio; composition_failed, no_response;recovery:no_response;retry_exhausted.',
    'Útil: explica por qué no guardó y ofrece activar memoria mediante confirmación.',
    'Fallo: repite la pregunta sin explicar qué se activaría.',
    'Fallo: se canceló la activación pendiente, pero «Se ha cancelado la memoria» no identifica esa acción. El estado real sí conserva memoria deshabilitada sin guardar.',
    'Fallo: reconoce Álvaro pero afirma que no está en su contexto actual, pese a que la declaración humana está presente en el payload.',
    'Fallo: memoria persistente deshabilitada no impide responder con el nombre declarado en la conversación.',
]
lines = ['# Producto366 — 3/10 útiles completos; un silencio', '',
    'Mismos diez controles sintéticos de364, candidato Qwen3.5 y perfil limpio; sólo fuente365 cambia. Exit0, todas las admisiones200, ningún timeout. Sin promoción, humanos frescos, UI ni voz física.', '',
    'La ruta privada ahora intenta guardar ambos nombres y ofrece activación con consentimiento. No aumenta el total de turnos útiles: permanecen errores de explicación/recuerdo y cambian algunas respuestas. No sustituir adjudicación por suites verdes.', '']
index = -1
for row in events:
    if row.get('type') == 'event' and row['event'].get('type') == 'activity':
        entry = row['event']['entry']
        if entry['src'] == 'YOU':
            index += 1
            lines.extend([f'## Turno {index + 1}', '', entry['msg'], ''])
        elif entry['src'] == 'BAXY':
            lines.extend(['> ' + entry['msg'], ''])
    elif row.get('type') == 'terminal':
        lines.extend([reasons[index], ''])
journal_path = base / 'C03-memory-profile366/journal/missions.jsonl'
journal = [json.loads(line)['payload'] for line in journal_path.open(encoding='utf-8-sig')]
completed = [row for row in journal if row.get('response')]
assert [(r['operation'], r['response']['status']) for r in completed] == [
    ('memory.status', 'completed'), ('memory.save', 'failed'), ('memory.recall', 'failed'),
    ('memory.save', 'failed'), ('memory.recall', 'failed')]
lines += ['## Primera pérdida localizada', '',
    'T2/T7: MemoryTurnSession.HandleConfirmationAsync Invalid produce confirm_or_cancel sin pendingAction. La narración inicial ya dispone del helper seguro; sólo debe transmitir operación y destino público, nunca argumentos, tokens o IDs. Cancelación/idioma y recall siguen separados.', '',
    'Se comprobó además HTTP34: la declaración humana «Me llamo Álvaro y quiero que guardes mi nombre.» sí llega como role=user al selector para «quién soy ahora». Se descarta la hipótesis de que365 ocultara esa declaración antes del historial. El problema de T9 no puede atribuirse a esa supuesta pérdida.', '',
    'BAXY y llama-server ausentes al cerrar. Handles finalizados; encuesta intacta. Últimas dueñas365:1926pass0skip, Fast18,06s verde. C03 íntegro sigue EN_CURSO.']
(target / 'RESULT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
pins = {}
for path in [private / 'capture/events.jsonl', private / 'http-posts.jsonl', private / 'compose-audit.jsonl', private / 'turn-audit.jsonl', journal_path]:
    with path.open('rb') as stream:
        pins[str(path)] = hashlib.file_digest(stream, 'sha256').hexdigest()
(target / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = out / name
    old = path.read_text(encoding='utf-8')
    notice = ('## Actualización366 — ejecución cerrada\n\n'
        'Producto366 completó exit0; handle50133 cerrado. RESULT/PINS366 escritos:3/10 útiles,1silencio. '
        'Ahora ambos guardados alcanzan fallo real memory_disabled y oferta de enable; cancelaciones no ejecutan ni guardan. '
        'T2/T7 no explican acción pendiente; T3 idioma erróneo; T8 cancelación sin alcance; T5 silencio; T9 contradice contexto; T10 confunde persistencia y conversación. '
        'HTTP34 confirma declaración Álvaro presente como user: hipótesis de ocultación365 descartada. '
        'Ningún producto/modelo en curso. Siguiente: contraste nativo367 del pendingAction omitido en Invalid, sin fuente nueva todavía. '
        'Las menciones a366 en curso más abajo son el estado anterior, sustituido por esta actualización.\n\n')
    path.write_text(notice + old, encoding='utf-8')
path = out / 'RELEVO_ACTIVO.json'
state = json.loads(path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='366 closed0,3/10 useful,1silence; RESULT/PINS written. Last source365, owners1926pass/Fast green. No running product/model.',
    continuation='Native contrast367 for missing pendingAction in invalid confirmation reply. Disabled-memory conversational recall, cancellation scope/language and full C03 remain open.')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('366 recorded; current source365, no product/model running, C03 active.')
