"""Record generalization failures and the next owner-parser baseline365."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03'
base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
private = base / 'C03-memory-product364-private'
target = out / 'astra-memory-product364'
events = [json.loads(line) for line in (private / 'capture/events.jsonl').open(encoding='utf-8-sig')]
terminals = [row for row in events if row.get('type') == 'terminal']
assert len(terminals) == 10 and all(not row['timedOut'] and row['admissionStatus'] == 200 for row in terminals)
reasons = [
    'Fallo: promete recordar sin iniciar la ruta de guardado solicitada ni explicar que persistencia está deshabilitada. No hubo save/enable.',
    'Fallo: dice qué se está confirmando sin una confirmación pendiente real; no explica ninguna activación.',
    'Fallo: cancelar se responde como fuera de catálogo y en español dentro del intercambio inglés.',
    'Útil: reconoce Jordan desde la conversación.',
    'Fallo: silencio. Terminal composition_failed; no_response;recovery:no_response;retry_exhausted.',
    'Fallo: convierte el guardado explícito del nombre en una pregunta de nota privada; no inicia memoria ni identifica la activación necesaria.',
    'Fallo: repite la pregunta de nota y no responde qué se activaría.',
    'Útil: cancela la aclaración existente; no se habilita memoria ni se guarda.',
    'Útil: reconoce la nueva declaración Álvaro.',
    'Fallo: atribuye no poder decir el nombre a memoria deshabilitada, aunque Álvaro está en la conversación reciente.',
]
lines = ['# Producto364 — generalización:3/10 completos, un silencio', '',
    'Diez controles sintéticos ES/EN, nuevos nombres y cancelaciones. Fuente362 '
    'y Qwen3.5 de363 sin cambios; no comparación numérica con su panel distinto. '
    'Exit0, admisiones200, sin timeout. No mensajes humanos frescos, UI ni voz física.', '']
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
journal_path = base / 'C03-memory-profile364/journal/missions.jsonl'
journal = [json.loads(line)['payload'] for line in journal_path.open(encoding='utf-8-sig')]
completed = [row for row in journal if row.get('response')]
assert [(row['operation'], row['response']['status']) for row in completed] == [
    ('memory.status', 'completed'), ('memory.recall', 'failed'), ('memory.recall', 'failed')]
lines.extend(['## Siguiente causa, sin ocultar el resto', '',
    'Primero la interpretación privada del nombre y guardado en una frase. '
    'NaturalMemoryRequestParser.Classify:250, MissingNameSavePattern:1651 y '
    'DeclaredNameInputPattern:1669 ya tienen las piezas separadas. TryBindSaveInput '
    'sólo une el dato después de una pregunta previa y no este turno completo. '
    '365 añade baseline positivo/negativo para combinar dato con su permiso '
    'explícito, sin nombres fijos, permiso inferido ni nota alternativa. '
    'T5/T10 sobre memoria deshabilitada y contexto siguen pendientes por separado. '
    'El control de preguntas durante confirmación no se alcanzó en364: nunca hubo '
    'un enable pendiente. No presentar el examen de esa rama como realizado.'])
(target / 'RESULT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
pins = {}
for path in [private / 'capture/events.jsonl', private / 'http-posts.jsonl', private / 'compose-audit.jsonl', private / 'turn-audit.jsonl', journal_path]:
    with path.open('rb') as stream:
        pins[str(path)] = hashlib.file_digest(stream, 'sha256').hexdigest()
(target / 'PINS.json').write_text(json.dumps(pins, indent=2) + '\n', encoding='utf-8')
for name in ['CHECKPOINT.md', 'HANDOFF.md']:
    path = out / name
    text = path.read_text(encoding='utf-8').replace('checkpoint363', 'checkpoint364/365')
    text = text.replace('producto363 terminado, todos los handles cerrados.',
        'producto364 terminado; baseline365 en curso, handle85875. No fuente365 aún.')
    start = text.index('Siguiente: ampliar desarrollo a idiomas/nombres distintos,')
    end = text.index('## Resto íntegro pendiente')
    text = text[:start] + '''364:10controles sintéticos ES/EN, nombresJordan/Álvaro y cancelación.3/10 útiles,
1silencio. No comparación de porcentaje con363 por panel diferente. RESULT/PINS
escritos. Journal:status completado,2recall fallidos; nunca save ni enable.
T1My name is Jordan. Remember my name. promete memoria sin iniciarla. T6Me llamo
Álvaro y quiero que guardes mi nombre. pregunta por nota privada. T2confirmación
inventada, T3cancel fuera de catálogo/en idioma ajeno;T5What is my name? silencio
composition_failed/no_response/retry_exhausted;T7repite aclaración;T10atribuye no
conocer el nombre a memoria deshabilitada pese a conversación. T4/T9reconocen
nombres;T8cancela aclaración. No se alcanzó ninguna confirmación memory.enable.

365baseline en cursohandle85875: nuevos tests DeclarationAndExplicitNameSaveBindTheSamePrivateDatum
(5positivos) y ADeclarationAloneOrAnUnrelatedClauseDoesNotAuthorizeNamePersistence
(6negativos) en NaturalMemoryRequestParserTests.cs. PREREG astra-declared-memory365.
Todavía NO cambios de producción365; última fuente362, Fast/dueñas previas verdes,
tests365 WIP. Recogerbaseline; luego unir declaración y petición explícita sobre
el mismo dato reutilizando piezas existentes, no otra respuesta/prompt del modelo.
Classify:250, MissingNameSavePattern:1651, DeclaredNameInputPattern:1669;
TryBindSaveInput:442 sólo une dato tras pregunta anterior. Sus patrones actuales
no admiten punto+segunda frase ni y+quiero ni nombres compuestos con espacios.
Preservar negaciones/secretos/autoridad/privacidad y resto de objetivos públicos.

Después de esa primera pérdida, resolver conversación reciente con persistencia
desactivada (T5/T10). La inspección pendiente de MemoryTurnSession:138–155 Invalid/
cannot_withdraw_uncertain sin pendingAction sigue sin editar: PrivateOperationNarration
ya lo construye seguro; no confundir rama no alcanzada364 con fallo medido suyo.
Sin Full/promoción, BAXY manual cerrado, encuesta intacta. Mantener C03 completo.

''' + text[end:]
    path.write_text(text, encoding='utf-8')
path = out / 'RELEVO_ACTIVO.json'
state = json.loads(path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='364 generalization3/10,1silence; never reached memory-enable confirmation.363 remains7/7 on distinct panel.365 parser baseline running85875; no source365 edit.',
    continuation='Collect365 baseline; repair one-turn name declaration plus explicit persistence using existing private parser/binding; then disabled-memory conversational recall and remaining C03.')
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('3643/10+1silence recorded;365 baseline running, full C03 active.')
