"""Record360 regression and the first changed native decision faithfully."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03'
base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private = base / 'C03-memory-product360-private'
target = out / 'astra-memory-product360'
events = [json.loads(line) for line in (private / 'capture/events.jsonl').open(encoding='utf-8-sig')]
terminals = [row for row in events if row.get('type') == 'terminal']
assert len(terminals) == 7 and all(not row['timedOut'] and row['admissionStatus'] == 200 for row in terminals)
reasons = [
    'Útil: pide el nombre faltante.',
    'Útil: saluda, explica el fallo al guardar y pregunta por activar memoria.',
    'Útil: confirma activación y guardado verificados; publica el saludo.',
    'Fallo: una referencia personal se transforma en solicitud de escritura de archivo y termina en error de interpretación. La compatibilidad veta la escritura antes de ejecutarla.',
    'Fallo: niega poder responder por falta de claridad; el nombre estaba en el contexto.',
    'Fallo: pregunta si se desea exactamente lo que ya se pidió. El selector primario abstuvo correctamente; el segundo sondeo lo cambió a system.identity.',
    'Fallo: repite la aclaración anterior y no recupera el nombre.',
]
lines = ['# Producto360 — regresión:3/7 completos, cero silencios', '',
    'Mismos siete pedidos/modelo de357; sólo359 conserva el historial nativo '
    'completo ya acotado. Exit0, admisiones200, sin timeout. La mejora aislada358 '
    'no se sostiene en producto.359 NO está aceptado como solución integrada. '
    'No UI gráfica, voz física ni aceptación humana fresca.', '']
index = -1
for row in events:
    if row.get('type') == 'event' and row['event'].get('type') == 'activity':
        entry = row['event']['entry']
        if entry['src'] == 'YOU':
            index += 1
            lines.extend([f'## Turno {index+1}', '', entry['msg'], ''])
        elif entry['src'] == 'BAXY':
            lines.extend(['> ' + entry['msg'], ''])
    elif row.get('type') == 'terminal':
        lines.extend([reasons[index], ''])
journal_path = base / 'C03-memory-profile360/journal/missions.jsonl'
journal = [json.loads(line)['payload'] for line in journal_path.open(encoding='utf-8-sig')]
completed = [row for row in journal if row.get('response')]
assert all(row['operation'] in {'memory.status', 'memory.save', 'memory.enable'} for row in completed)
lines.extend(['## Primera divergencia y siguiente prueba', '',
    'HTTP13 propone filesystem.write.text para Yo soy el al leer los pedidos '
    'anteriores de guardar el nombre. HTTP14 declara incompatible; no se ejecuta '
    'escritura. HTTP24 después propone note.read para quien soy y no logra '
    'fundamentar argumentos. HTTP29 abstiene correctamente para ambas identidades; '
    'HTTP31, sondeo redundante de catálogo4, vuelve a proponer system.identity. '
    'La App acaba reteniendo una aclaración inútil. Journal contiene sólo memoria.', '',
    'No ampliar descripciones de identidad para tratar una selección de archivos '
    'causada por contexto.361 compara el mismo contenido en roles nativos frente '
    'a envoltorioJSON, sobre11payloads fijos.316 rechazó esa forma con2507 y un '
    'saludo sin esta declaración; se declara la diferencia de modelo/input. '
    'Si no mejora, cambiar estrategia sin otra variante textual. Fuente359 sigue '
    'como WIP de reparación, no promoción;356 es la última mejora integrada.'])
(target / 'RESULT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
pins = {}
for path in [private / 'capture/events.jsonl', private / 'http-posts.jsonl', private / 'turn-audit.jsonl', journal_path]:
    with path.open('rb') as stream:
        pins[str(path)] = hashlib.file_digest(stream, 'sha256').hexdigest()
(target / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = out / name
    text = path.read_text(encoding='utf-8').replace('checkpoint359/360', 'checkpoint360/361')
    text = text.replace('producto357 y selector358 terminados. Fuente359 validada, producto360 preparado.',
        'producto360 terminó con regresión. Diagnóstico361 en curso, handle34499.')
    start = text.index('Siguiente: ejecutar scratchpad/c03-product360.py')
    end = text.index('## Resto íntegro pendiente')
    text = text[:start] + '''360 terminó3/7 completos0silencios frente a3576/7. RESULT/PINS360 escritos;
journal sólo enable/save, no escritura de archivo. Fuente359 pasa tests/Fast
pero NO es solución integrada;356 sigue siendo la última mejora integrada.
Primera divergencia360 HTTP13: Yo soy el propone filesystem.write.text al leer
viejos pedidos de guardar el nombre; HTTP14 lo veta incompatible. DespuésHTTP24
propone note.read sin argumentos para quien soy. HTTP29 abstiene correctamente
para ambas identidades; sondeo secundarioHTTP31 de4candidatos revierte a identity.
__main__.py:6282 _catalog_answers_the_request repite sondeo después de abstención;
su rama nativa2054 vuelve a llamar al mismo selector. No editar descriptores para
el fallo de archivo ni otra respuesta prefabricada.

361 en curso handle34499: scratchpad/c03-native-context361.py, out
astra-native-context361, privadoLOCALAPPDATA/BAXY/C03-native-context361-private.
11payloads fijos (8de358 y reales36013/29/31), sólo JSON referencia frente a roles
nativos con el mismo texto y modeloQwen3.5.316 ensayó2507 y otro contexto; diferencia
declarada en PREREG. Sin efectos, fuente, prompt ni promoción. Recoger resultado;
si falla, cambiar estrategia y no otra variante de prosa. BAXY manual cerrado.

''' + text[end:]
    path.write_text(text, encoding='utf-8')
state_path = out / 'RELEVO_ACTIVO.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='360 regresses6/7to3/7;359 is unaccepted integrated WIP despite1091pass/Fast.356 remains last integrated improvement.361 running handle34499.',
    continuation='Collect361 native role comparison on11fixed payloads; first divergence36013 selects file-write from historical save request. No descriptor/prompt sweep; full C03 active.')
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('360 regression3/7 pinned;361 running, C03 active.')
