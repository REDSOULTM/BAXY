"""Record the first complete seven-turn memory/identity replay."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03'
base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private = base / 'C03-memory-product363-private'
target = out / 'astra-memory-product363'
events = [json.loads(line) for line in (private / 'capture/events.jsonl').open(encoding='utf-8-sig')]
terminals = [row for row in events if row.get('type') == 'terminal']
assert len(terminals) == 7 and all(not row['timedOut'] and row['admissionStatus'] == 200 for row in terminals)
reasons = [
    'Útil: solicita el nombre que falta.',
    'Útil: saluda, explica que no pudo guardar con memoria deshabilitada y precisa la activación que requiere confirmar.',
    'Útil: confirma activación y guardado reales; publica el saludo pedido.',
    'Útil: reconoce Emmanuel en la referencia Yo soy el; la oferta adicional es innecesaria pero no contradice.',
    'Útil: responde Emmanuel, el nombre declarado, sin sustituirlo por la cuentaWindows.',
    'Útil: diferencia la identidad de BAXY y la persona.',
    'Útil: recuerda Emmanuel desde memory.recall verificado.',
]
lines = ['# Producto363 — 7/7 completos, cero silencios', '',
    'Mismos siete pedidos/modelo/perfil aislado de360; sólo362 cambia los roles del '
    'selector nativo. Exit0, admisiones200, sin timeout. Cinco literales humanos '
    'de desarrollo más confirmar y cómo me llamo sintéticos declarados. Ninguno '
    'cuenta como reserva fresca; no UI gráfica ni voz física.', '']
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
journal_path = base / 'C03-memory-profile363/journal/missions.jsonl'
journal = [json.loads(line)['payload'] for line in journal_path.open(encoding='utf-8-sig')]
completed = [row for row in journal if row.get('response')]
for operation in ['memory.enable', 'memory.save', 'memory.recall']:
    assert any(row['operation'] == operation and row['response']['status'] == 'completed' and row['response']['verified'] for row in completed)
saves = [row for row in completed if row['operation'] == 'memory.save']
assert len(saves) == 2 and saves[0]['response']['status'] == 'failed'
assert saves[0]['invocationId'] != saves[1]['invocationId']
assert all(row['operation'].startswith('memory.') for row in completed)
lines.extend(['## Decisión y límites', '',
    'Mantener362 junto con el historial acotado359: corrige la regresión3603/7 y '
    'alcanza7/7 frente a3576/7. No hay lecturaWindows ni escritura de archivos '
    'ajena a memoria en el journal. Se conservan fracaso360 y preparación fallida '
    '363 antes del lanzamiento. Registro2507 intacto; Qwen3.5 continúa candidato '
    'diagnóstico, pendiente de todas las rutas y recursos conjuntos.', '',
    'C03 sigue abierto: ampliar desarrollo con nombres/idiomas/cancelación y '
    'preguntas durante confirmación; otros fallos de la sesión264 y requisitos '
    'de encuesta;100humanos frescos, averías, escritorio/voz física/runtime, '
    'contratos futuros, Full final y publicación. Este panel no representa '
    'los742 registros de la encuesta ni las ocho rutas completas.'])
(target / 'RESULT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
pins = {}
for path in [private / 'capture/events.jsonl', private / 'http-posts.jsonl', private / 'turn-audit.jsonl', private / 'compose-audit.jsonl', journal_path]:
    with path.open('rb') as stream:
        pins[str(path)] = hashlib.file_digest(stream, 'sha256').hexdigest()
(target / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = out / name
    previous = path.read_text(encoding='utf-8')
    (target / ('PREVIOUS_' + name)).write_text(previous, encoding='utf-8')
    start = previous.index('## Estado demostrado')
    end = previous.index('## Resto íntegro pendiente')
    text = '''# C03 — checkpoint363 — EN_CURSO — 2026-09-08

Goal completo activo; ramaGoal-c03, HEAD2bf3d4c. Preservar WIP/main/evidencia.
Sin agentes, commit/push ni Full durante reparación. BAXY cerrado para uso manual;
producto363 terminado, todos los handles cerrados. Encuesta1248/742 intacta,
servidor101140 disponible.16mensajes directos consolidados en
INSTRUCCIONES_CONSOLIDADAS_2026-09-08.md; excluir órdenes automáticas de otra tarea.
AGENTS e identidad vigentes. No reiniciar campaña ni reducir alcance a memoria.

## Estado demostrado

340 activa memoria sólo tras confirmación exacta y nuevo save; cancelar descarta
continuación.343/343b conserva dato requerido hasta publicar la pregunta.344
proyecta resultados privados observados y la acción pendiente inicial/recovery;
schemas/secretos/replay preservados. .NET1913pass0skip5m19s, Fast18,77s de344.
354 conserva operation al componer, acotando error y éxito a la operación real.
356 permite el saludo exacto pedido en App/Python sin aceptar pregunta copiada;
App225pass0skip15s, Python1044pass0skip5,14s, Fast18,00s. Producto3576/7:
saludo publicado, fallo quien soy devuelve cuentaWindows. RESULT/PINS escritos.

358 nativo con historial completo mejora selección6/8→7/8, pero359 solo regresó
en producto3606/7→3/7: viejo pedido de guardar domina Yo soy el y propone archivo.
La compatibilidad lo veta; no efectos ajenos. El sondeo secundario del catálogo
también revierte una abstención válida a identity. No adoptar359 solo.
361 conserva el contenido en roles nativos y mejora9/11→11/11. Variabilidad de
una referencia sintética declarada; seed no garantiza salidaidéntica. GPU3175,56MiB,
RAM4599,84MiB18,34s aislado; no voz/UI/mínimo. No repetir envoltorios/etiquetas
rechazados346/347/349/316/317; diferencias de modelo/input361 están documentadas.

362 última fuente: selector nativo system propio + historial saneado/acotado
user/assistant + petición actual user literal, reemplaza JSON de referencia.
12mensajes/6000chars, sin otro prompt/catálogo/sampler/modelo/límite. Baseline4fail;
Python turn_policy+compose+transport1091pass0skip5,32s, Fastverde1,40s0warnings/errors.
RESULT/PINS362 escritos. No Full. CódigoC# sigue356. Registro2507 intacto;
Qwen3.5 sigue override diagnóstico, no promoción ni prueba de mejora2507.

## Producto363 y siguiente acción

363 completó7/7 turnos,0silencios,adm200,sin timeout; mismos siete pedidos360,
sólo362 diferente. Pregunta nombre, explica memoria desactivada, confirma activar,
guarda en invocación nueva y saluda. Yo soy el reconoce Emmanuel; quien soy
responde Eres Emmanuel; ambas identidades correctas; recall Tu nombre es Emmanuel.
Journal acredita enable/nuevo save/recall, sin cuentaWindows ni archivoajeno.
RESULT/PINS363 escritos.362+359 retenidos como mejora integrada de ese panel.
Preparación363 tuvo sustitución accidental del hash literal por replace360→363;
assert frenó antes dePREREG/inferencia, se restableció el hash original y se
conservó PREPARATION_ERROR.md. Evitar sustituciones globales de IDs en huellas.

Siguiente: ampliar desarrollo a idiomas/nombres distintos, preguntas durante
confirmación y cancelar. MemoryTurnSession.cs:138–155 todavía publica Invalid/
cannot_withdraw_uncertain sin pendingAction; PrivateOperationNarration.cs:90
ya construye ese dato seguro (op/target, sin argumentos). Medir primero en
producto aislado: confirmar qué se confirma, cancelar sin activar/guardar,
y reconocer un dato de conversación aunque no se haya persistido. No editar
sin distinguir contexto de sesión de memoria persistente. Después otros fallos
de sesión264 y encuesta, no más repetir el mismo panel si no hay cambios.

''' + previous[end:]
    path.write_text(text, encoding='utf-8')
path = out / 'RELEVO_ACTIVO.json'
state = json.loads(path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='363 passes7/7 whole turns0silence after362 native dialogue; journal verifies enable/new save/recall.1091pass/Fast1.40s. All handles complete, registered2507 unchanged.',
    continuation='Broaden development: different names/languages, questions during confirmation, cancel and conversation-only name recall. Preserve survey/full C03 and fresh acceptance obligations.')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('3637/7,0silence,journal verified; full C03 remains active.')
