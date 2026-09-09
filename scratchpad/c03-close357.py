"""Record the actual greeting publication, not only a unit-test result."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03'
base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private = base / 'C03-memory-product357-private'
target = out / 'astra-memory-product357'
events = [json.loads(line) for line in (private / 'capture/events.jsonl').open(encoding='utf-8-sig')]
terminals = [row for row in events if row.get('type') == 'terminal']
assert len(terminals) == 7 and all(not row['timedOut'] and row['admissionStatus'] == 200 for row in terminals)
reasons = [
    'Útil: pregunta el nombre faltante.',
    'Útil: saluda, limita el fallo a guardar y explica qué activación se confirma.',
    'Útil: activa y guarda con resultados verificados, y ahora publica Hola Emmanuel. La respuesta nativa pedida atraviesa la App; no se recompone un resultado anterior.',
    'Útil: reconoce Emmanuel en la referencia Yo soy el. La oferta adicional no contradice.',
    'Fallo: system.identity informa usuario, la cuenta de Windows, en vez de responder al referente personal Emmanuel ya declarado. La selección sigue incorrecta.',
    'Útil: distingue ambas identidades correctamente.',
    'Útil: recuerda Emmanuel desde memory.recall verificado.',
]
lines = ['# Producto357 — saludo publicado; 6/7 turnos completos, cero silencios', '',
    'Mismos siete pedidos y overrideQwen3.5 de355; sólo fuente356 difiere. Exit0, '
    'admisiones200, sin timeout. Cinco literales humanos conocidos y dos controles '
    'sintéticos declarados. Desarrollo, no reserva fresca, UI gráfica ni voz física.', '']
index = -1
turn_messages = []
for row in events:
    if row.get('type') == 'event' and row['event'].get('type') == 'activity':
        entry = row['event']['entry']
        if entry['src'] == 'YOU':
            index += 1
            turn_messages.append([])
            lines.extend([f'## Turno {index+1}', '', entry['msg'], ''])
        elif entry['src'] == 'BAXY':
            turn_messages[index].append(entry['msg'])
            lines.extend(['> ' + entry['msg'], ''])
    elif row.get('type') == 'terminal':
        lines.extend([reasons[index], ''])
assert 'Hola Emmanuel.' in turn_messages[2]
journal_path = base / 'C03-memory-profile357/journal/missions.jsonl'
journal = [json.loads(line)['payload'] for line in journal_path.open(encoding='utf-8-sig')]
completed = [row for row in journal if row.get('response')]
for operation in ['memory.enable', 'memory.save', 'memory.recall']:
    assert any(row['operation'] == operation and row['response']['status'] == 'completed' and row['response']['verified'] for row in completed)
saves = [row for row in completed if row['operation'] == 'memory.save']
assert len(saves) == 2 and saves[0]['response']['status'] == 'failed'
assert saves[0]['invocationId'] != saves[1]['invocationId']
lines.extend(['## Decisión', '',
    'Mantener356: el saludo correcto ya no se descarta. El recuento global sigue '
    '6/7; no inflar el resultado por reparar un defecto interno de un turno que '
    'ya cumplía con el saludo anterior. Qwen3.5 permanece candidato diagnóstico. '
    'El siguiente bloqueo es la selección contextual de identidad, no generación '
    'del saludo ni transporte del nombre. El modelo registrado sigue2507.'])
(target / 'RESULT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
pins = {}
for path in [private / 'capture/events.jsonl', private / 'http-posts.jsonl', private / 'compose-audit.jsonl', private / 'turn-audit.jsonl', journal_path]:
    with path.open('rb') as stream:
        pins[str(path)] = hashlib.file_digest(stream, 'sha256').hexdigest()
(target / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = out / name
    text = path.read_text(encoding='utf-8').replace('checkpoint356', 'checkpoint357/358')
    text = text.replace('fuente356 validada; producto357 preparado y pendiente de ejecutar. Handles de pruebas cerrados.',
        'producto357 terminó; selector358 en curso, handle89363. Pruebas356 cerradas.')
    start = text.index('Ejecutar scratchpad/c03-product357.py')
    end = text.index('## Resto íntegro pendiente')
    text = text[:start] + '''Producto357 completó6/7,0silencios; Hola Emmanuel se publica enT3. RESULT/PINS
escritos, journal acredita enable/nuevo save/recall, registro intacto. Única falla
del panel: quien soy devuelve cuentaWindows usuario. BAXY cerrado tras el conductor.
Selector358 en curso, handle89363: recoger. Compara sólo last6 frente al historial
ya acotado12mensajes/6000chars, mismo payload real35520 y siete controles de
desarrollo. Baseline objetoHTTP y últimos6 reconstruidos de eventos se verifican
idénticos. Sin efectos, edición de fuente, roles/prompt ni promoción. Paths:
scratchpad/c03-context-selector358.py, astra-context-selector358, privado
LOCALAPPDATA/BAXY/C03-context-selector358-private. Fuente356 aún última adoptada.
Herencia R1–R4 de Carter_v2, experimentos316/317/65 y docs de modelo/formato ya
consultados. No repetir eliminación de historia ni cambios de roles rechazados.

''' + text[end:]
    path.write_text(text, encoding='utf-8')
state_path = out / 'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='357:6/7,0silence, requested greeting now published; source356 validated. Selector358 diagnostic running handle89363.',
    continuation='Collect358 native last6 versus bounded-history comparison; only then decide source. Full C03 active.')
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('357: greeting published,6/7,0silence,journal verified;358 running.')
