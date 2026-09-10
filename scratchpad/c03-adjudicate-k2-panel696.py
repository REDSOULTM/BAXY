"""Persist root's criterion-based review; this does not grant C03 coverage."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os

parser = argparse.ArgumentParser()
parser.add_argument('tag', choices=['q8-high-reference1', '09-bf16-high-reference1', 'qwen-registered1', 'qwen-documented1', '37-q4-high-cpu-kv1', '37-q4-high-gpu8k1', '37-q4-high-native-selectors1', '37-q8-high-native-gpu24-noop1', '09-bf16-high-native-selectors1'])
args = parser.parse_args()
base = Path(__file__).resolve().parents[1] / 'artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696'
private = Path(os.environ['LOCALAPPDATA']) / f'BAXY/C03-k2-run696-{args.tag}-private'
review_path = private / 'review.json'
rows = json.loads(review_path.read_text(encoding='utf-8'))
common_stale = ['select-disk-used-es', 'select-H0532', 'select-H0359', 'select-cpu-order-es',
                'select-H0450', 'select-H0499', 'select-H0602', 'select-H0675', 'select-audio-order-es']
failures = {case: ('missing_fresh_read', 'Reutiliza una respuesta del historial; no propone la lectura actual solicitada.') for case in common_stale}
failures.update({
    'select-control-other-machine-es': ('wrong_device', 'Propone una lectura local para una consulta sobre el ordenador de otra persona.'),
    'select-control-disk-order-es': ('missed_available_operation', 'Niega la lectura de disco aunque la descripción de system.status incluye disco.'),
    'writer521-19': ('capability_state_conflation', 'Responde que no tiene memoria local; los hechos indican capacidad existente desactivada.'),
    'writer694-H0539': ('memory_quantity_scope', 'La consulta pide cuánta RAM tiene el PC; no identifica correctamente la capacidad instalada y su relación con la memoria libre.'),
})
if args.tag == 'q8-high-reference1':
    failures.update({
        'select-network-internet-es': ('unsupported_followup', 'Abstiene la lectura que falta en catálogo pero añade una promesa de comprobarla sin herramienta disponible.'),
        'select-control-cpu-then-date-en': ('wrong_operations', 'Selecciona lista de procesos y omite las dos lecturas solicitadas: uso CPU y fecha, en ese orden.'),
        'select-control-negated-en': ('unfinished', 'Agota32768tokens en razonamiento repetitivo y no entrega respuesta terminal completa.'),
        'select-control-past-en': ('unrequested_read', 'Propone leer el estado actual ante una afirmación sobre una lectura de ayer.'),
        'select-control-knowledge-en': ('false_knowledge', 'Afirma que RAM es distinta de la memoria principal, que también identifica como RAM.'),
        'writer521-2': ('unbound_confirmation_prose', 'Pregunta confirm/cancel sin explicar la acción de habilitar memoria privada que se autoriza.'),
        'writer521-3': ('internal_code_in_prose', 'Expone memory.enable en la respuesta visible, pese a la instrucción de prosa cotidiana sin códigos internos.'),
        'writer521-6': ('wrong_verb', 'Pregunta por crear una aplicación cuando la petición es abrir una aplicación.'),
        'writer521-10': ('wrong_verb', 'Repite el error abrir→crear del fixture idéntico writer521-6; no es evidencia independiente.'),
        'writer521-16': ('wrong_identity', 'Atribuye al asistente el nombre de la memoria en vez de responder el nombre más reciente de la persona en la conversación.'),
        'writer694-H0111': ('missing_unit', 'Entrega sólo17.18 sin unidad ni identificación de capacidad de RAM.'),
        'writer694-H0508': ('wrong_os', 'Llama Windows10 a la observación que identifica Windows11; tampoco responde la capacidad instalada solicitada.'),
        'writer694-H0114': ('prose_contract', 'Las cifras principales son coherentes, pero expone índices de adaptadores y mezcla adapters en la respuesta española; prosa defectuosa. No se cuenta como fallo numérico.'),
        'writer694-gpu-usage-es': ('wrong_measurement', 'La cantidad5.4309GB no corresponde al uso dedicado4.1013GB solicitado ni a una suma de uso justificada por los datos.'),
        'writer694-H0104': ('missing_identity', 'Sólo dice que la ventana está maximizada; omite qué ventana está activa.'),
        'chat-knowledge-en': ('false_knowledge', 'Invierte la densidad del hielo y el agua y afirma que el hielo queda al fondo.'),
    })
elif args.tag == '09-bf16-high-reference1':
    failures.pop('select-audio-order-es')
    failures.update({
        'select-H0499': ('missed_available_operation', 'Nombra la herramienta necesaria para la fecha pero no la propone y promete intentarla.'),
        'select-control-past-en': ('unrequested_read', 'Propone una lectura actual ante una afirmación sobre ayer.'),
        'select-control-process-memory-es': ('backend_parse_error', 'Emite nombre/argumentos correctos pero el backend termina con HTTP500 peg-native y sin finish_reason. El intento no es válido; no se atribuye automáticamente a incapacidad semántica del modelo.'),
        'writer521-6': ('wrong_clarification', 'Pregunta sobre funcionalidad de una aplicación en vez de preguntar qué aplicación abrir.'),
        'writer521-10': ('wrong_clarification', 'Repite el error de aclaración writer521-6; fixture idéntico, no independiente.'),
        'writer694-gpu-usage-es': ('wrong_measurement', 'La cantidad5.3146GB no corresponde al uso dedicado4.1013GB suministrado ni a una suma justificada.'),
        'chat-knowledge-en': ('false_knowledge', 'Afirma que el hielo empaqueta moléculas más juntas y por eso tiene menor densidad: explicación contradictoria.'),
        'chat-difference-es': ('false_memory_definition', 'Define RAM como memoria interna del procesador y expande VRAM como visión; no distingue correctamente memoria del sistema y de la GPU.'),
    })
    failures.pop('select-control-disk-order-es')
elif args.tag.startswith('qwen-'):
    failures.update({
        'select-clock-date-en': ('missed_available_operation', 'Niega acceso a fecha/hora aunque system.time está disponible.'),
        'select-network-internet-es': ('unverified_network', 'Afirma conectividad actual sin proponer lectura y sin herramienta correspondiente en el paquete.'),
        'writer521-2': ('premature_memory_claim', 'Dice que recuerda el nombre antes de resolver la habilitación pendiente; la confirmación debe describir esa acción sin anticipar el guardado.'),
        'writer521-4': ('internal_metadata_in_prose', 'Narra el indicador de corrección y el estado terminal interno; el criterio pide prosa natural sin esos flags.'),
        'writer694-H0508': ('wrong_memory_label', 'Identifica Windows11, pero llama disponible al total utilizable e ignora la capacidad instalada.'),
        'writer694-H0650': ('wrong_ranking', 'Ordena mal los procesos y sustituye uno de los cinco procesos de mayor RAM por otro inferior.'),
        'writer694-processes-top3-en': ('wrong_ranking', 'Omite el proceso de mayor RAM y añade un proceso inferior al top3 solicitado.'),
    })
    if args.tag == 'qwen-documented1':
        failures.update({
            'writer694-H0114': ('wrong_adapter_count', 'Los porcentajes principales son correctos, pero informa dos adaptadores no medibles cuando la observación enumera tres.'),
            'writer694-processes-top3-en': ('wrong_ranking_and_unit', 'Ordena mal el top3 y convierte837.95segundos de CPU acumulada en837.95MB de RAM para un proceso.'),
            'writer521-19': ('invented_memory_scope', 'Niega la memoria local y afirma guardar sólo en sesión; los hechos indican un registro persistente y memoria desactivada.'),
        })
elif args.tag == '09-bf16-high-native-selectors1':
    for case in ['select-control-other-machine-es', 'select-control-disk-order-es']:
        failures.pop(case)
    failures.update({
        'select-disk-used-es': ('empty_final', 'Final stop vacío sin lectura de disco solicitada.'),
        'select-clock-date-en': ('empty_final', 'Final stop vacío sin la lectura disponible de fecha.'),
        'select-H0450': ('missed_available_operation', 'Niega poder mostrar la hora sin proponer system.time.'),
        'select-network-internet-es': ('unverified_network', 'Niega poder comprobar la conexión pero afirma que el PC está online sin observación.'),
        'select-control-cpu-then-date-en': ('missing_second_operation', 'Propone estado CPU pero omite la lectura de fecha solicitada después.'),
        'select-control-past-en': ('unrequested_read', 'Propone estado actual ante una afirmación sobre una lectura de ayer.'),
    })
elif args.tag == '37-q8-high-native-gpu24-noop1':
    for case in ['select-disk-used-es', 'select-control-disk-order-es']:
        failures.pop(case)
    failures.update({
        'select-H0359': ('empty_final', 'Termina stop vacío, sin lectura de batería ni respuesta.'),
        'select-H0450': ('missed_available_operation', 'Niega una herramienta de hora aunque system.time está disponible.'),
        'select-cpu-order-es': ('unverified_measurement', 'Reutiliza el porcentaje del historial sin lectura actual; además filtra un delimitador de pensamiento.'),
        'select-network-internet-es': ('unverified_network', 'Afirma tener Internet sin lectura ni operación correspondiente en el catálogo.'),
    })
elif args.tag == '37-q4-high-native-selectors1':
    for case in ['select-disk-used-es', 'select-H0532', 'select-control-disk-order-es']:
        failures.pop(case)
    failures.update({
        'select-cpu-order-es': ('empty_final', 'Final stop vacío sin la lectura CPU solicitada; tampoco hay llamada de herramienta.'),
        'select-H0450': ('invented_failure', 'Afirma una avería de lectura del sistema no observada y no propone la hora.'),
        'select-H0602': ('wrong_interpretation', 'Interpreta pasar la hora como algo pasado/intransferible y no selecciona system.time.'),
        'select-clock-date-en': ('missed_available_operation', 'Niega una herramienta de fecha aunque system.time está en el catálogo.'),
        'select-network-internet-es': ('unsupported_followup', 'Promete verificar Internet sin emitir una lectura y sin la operación correspondiente en el catálogo suministrado.'),
        'select-H0675': ('unverified_wrong_ranking', 'Da como mayor consumo un proceso del historial que ni siquiera es el mayor de esa observación; no propone lectura actual.'),
    })
elif args.tag == '37-q4-high-gpu8k1':
    for case in ['select-H0532', 'select-H0602', 'select-control-disk-order-es', 'writer694-H0539', 'writer521-19']:
        failures.pop(case)
    failures.update({
        'select-H0359': ('unverified_progress', 'Dice estar verificando batería en tiempo real sin emitir la lectura requerida.'),
        'select-cpu-order-es': ('unverified_measurement', 'Da un porcentaje de CPU sin lectura actual y con prosa corrupta.'),
        'select-H0450': ('invented_clock_failure', 'Inventa discrepancia de relojes y deriva de sincronización; además expone un delimitador de razonamiento en content.'),
        'select-H0499': ('wrong_requested_field', 'Responde una hora ante una petición de fecha y no propone lectura.'),
        'select-clock-date-en': ('unverified_date', 'Da una fecha sin verificación y sin lectura de fecha actual.'),
        'select-network-internet-es': ('wrong_scope', 'Propone Wi-Fi para una comprobación de Internet; los dos ámbitos no equivalen.'),
        'select-H0675': ('invented_processes', 'Inventa nombres y consumos de aplicaciones en vez de proponer la lectura actual.'),
        'writer521-2': ('premature_memory_claim', 'Afirma recordar el nombre antes de resolver la habilitación pendiente, igual que el fallo de confirmación en Qwen.'),
        'writer521-3': ('internal_metadata_in_prose', 'Añade información de replay que el usuario no pidió; el criterio exige narrar la habilitación sin flags internos.'),
        'writer521-6': ('wrong_clarification_scope', 'Añade qué dispositivo usa y ofrece instrucciones manuales para acceder; sólo falta saber qué aplicación abrir en este PC.'),
        'writer521-10': ('wrong_clarification_scope', 'Repite el desvío de aclaración de writer521-6; fixture idéntico, no independiente.'),
        'writer521-8': ('corrupt_language', 'Mezcla inglés y palabras inventadas en una presentación española, sin un significado coherente.'),
        'writer521-17': ('internal_metadata_mistranslation', 'Expone replay como reproducción al narrar la desactivación, algo que no es una observación de reproducción multimedia.'),
        'writer694-H0114': ('invented_adapter_role', 'Los porcentajes principales son coherentes, pero atribuye a AMD funciones de respaldo/seguidor no observadas.'),
        'writer694-processes-top3-en': ('wrong_numeric_conversion', 'Conserva los bytes y nombres, pero sus equivalencias MiB son inconsistentes:860164096bytes son820.32MiB, no816MiB.'),
        'chat-difference-es': ('false_exclusive_definition', 'Afirma que VRAM sólo guarda imágenes de las pantallas; esa exclusividad es falsa, incluso en una explicación breve.'),
    })
else:
    for case in ['select-disk-used-es', 'select-control-disk-order-es', 'writer694-H0539']:
        failures.pop(case)
    failures.update({
        'select-H0450': ('invented_failure', 'Atribuye la imposibilidad de mostrar la hora a una avería de interfaz no observada y no propone system.time.'),
        'select-H0602': ('missed_available_operation', 'Responde Pasó sin proporcionar ni proponer la lectura de hora solicitada.'),
        'select-clock-date-en': ('unverified_date', 'Da una fecha no verificada y no propone la lectura disponible; además responde en español a la consulta inglesa.'),
        'select-network-internet-es': ('wrong_scope', 'Propone estado Wi-Fi cuando se pide verificar Internet; son observaciones diferentes.'),
        'select-H0675': ('invented_processes', 'Inventa nombres y consumos de procesos en vez de proponer una lectura actual.'),
        'writer521-3': ('internal_code_in_prose', 'Expone memory.enable, seen.enabled y datos de replay en vez de narrar brevemente que la memoria quedó habilitada.'),
        'writer521-4': ('internal_metadata_in_prose', 'Narra saved/corrected/sensitive/replayed como verificaciones internas en una respuesta de guardado.'),
        'writer521-8': ('unnatural_invented_context', 'Saluda al nombre correcto pero añade una comarca no presente y una pregunta española defectuosa.'),
        'writer521-16': ('wrong_identity', 'Dice que la persona llama al asistente por el nombre del usuario; mezcla los sujetos y termina con prosa incomprensible.'),
        'writer694-H0114': ('wrong_percentage', 'Convierte la utilización observada del motor GPU0.4533% en45%; la cifra de VRAM65% sí es coherente.'),
        'chat-name-es': ('wrong_identity', 'Responde Me llamo Vera atribuyendo al asistente el nombre que la persona acaba de dar.'),
        'chat-knowledge-en': ('false_knowledge', 'Afirma que las moléculas del hielo están más apretadas y por ello su densidad es menor: explicación física contradictoria.'),
    })

known = {r['id'] for r in rows}
all_known = {r['id'] for r in json.loads((base / 'PANEL_PLAN.json').read_text(encoding='utf-8'))['case_index']}
assert set(failures) <= all_known and len(rows) in [20, 50]
assert len(rows) == 50 or all(r['kind'] == 'selector' for r in rows)
failures = {case: value for case, value in failures.items() if case in known}
adjudications = []
for row in rows:
    passed = row['id'] not in failures
    defect, reason = failures.get(row['id'], ('none', 'Cumple el criterio declarado para esta entrada y los hechos suministrados.'))
    adjudications.append({'id': row['id'], 'kind': row['kind'], 'pass': passed, 'defect': defect, 'reason': reason})
    row['verdict'] = adjudications[-1]
    if row['id'] in ['writer694-H0127']:
        row['verdict']['note'] = 'La primera persona es una debilidad de estilo; conserva ausencia de Wi-Fi y no niega Internet. Mismo criterio para ambos modelos.'
    if args.tag == '09-bf16-high-native-selectors1' and row['id'] == 'select-control-other-machine-es':
        row['verdict']['note'] = 'Abstiene correctamente la lectura de otro ordenador. La justificación interna es extensa e imprecisa sobre la capacidad local; este texto del selector no es la prosa visible de BAXY.'
    if args.tag.startswith('qwen-') and row['id'] in ['select-control-past-en', 'select-control-knowledge-en', 'select-control-negated-en']:
        row['verdict']['note'] = 'Texto de selector excesivo; la decisión de no ejecutar es correcta y este texto nativo no es la prosa final de BAXY.'

review_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
summary = {'utc': datetime.now(timezone.utc).isoformat(), 'tag': args.tag,
    'reviewer': 'root', 'method': f'Revisión manual de las{len(rows)}entradas/resultados ejecutados contra criterios fijados antes de inferencia. No evaluación ciega. Fallos de calidad/prosa separados por causa de fallos fácticos. Texto interno del selector no se equipara a prosa visible. No cobertura C03 ni promoción.',
    'pass': sum(r['pass'] for r in adjudications), 'fail': sum(not r['pass'] for r in adjudications),
    'selector_pass': sum(r['pass'] for r in adjudications if r['kind'] == 'selector'),
    'prose_and_conversation_pass': sum(r['pass'] for r in adjudications if r['kind'] != 'selector'),
    'rows': adjudications, 'private_review_sha256': hashlib.sha256(review_path.read_bytes()).hexdigest(),
    'repeated_fixture': 'writer521-6 and writer521-10 are identical source repetition, not independent evidence',
    'remaining': 'Reference precision, model-specific profiles and integrated BAXY validation before any promotion.'}
(base / ('run-' + args.tag) / 'ADJUDICATION.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: summary[k] for k in ['tag', 'pass', 'fail', 'selector_pass', 'prose_and_conversation_pass']}))
