"""Record root's manual full-output review, including unsuccessful backend profiles."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os

REASONS = {
    'fresh': 'Responde desde el historial u omite la lectura actual disponible solicitada.',
    'empty': 'Termina sin contenido ni propuesta válida; no cumple el resultado terminal solicitado.',
    'boundary': 'La salida queda en reasoning_content; el perfil no entrega respuesta/herramienta válida. No se atribuye automáticamente a conocimiento del modelo.',
    'other': 'Propone una lectura de este PC para una consulta sobre otro ordenador.',
    'internet': 'Confunde una observación Wi-Fi con conectividad a Internet.',
    'order': 'Omite una de las operaciones solicitadas en secuencia.',
    'past': 'Propone una lectura actual ante una afirmación sobre una lectura pasada.',
    'language': 'La prosa visible tiene palabras o construcciones corruptas que impiden una respuesta natural coherente.',
    'tool_prose': 'Emite marcado interno de herramientas en el canal de prosa que debía pedir confirmación.',
    'identity': 'No identifica a la persona según la fuente solicitada o atribuye su nombre al asistente.',
    'disabled': 'Contradice la memoria desactivada o confunde ese estado con ausencia de la capacidad.',
    'ram_scope': 'No distingue correctamente capacidad instalada, total utilizable y memoria disponible solicitada.',
    'gpu_number': 'La cifra de memoria/uso GPU no corresponde a los hechos proporcionados.',
    'ranking': 'Inventa valores o no conserva el orden de procesos y el top solicitado.',
    'clarification': 'Pregunta por crear o por la funcionalidad de una aplicación cuando sólo falta saber cuál abrir.',
    'physics': 'Añade una explicación física incorrecta sobre por qué flota el hielo.',
    'memory_definition': 'Define incorrectamente RAM o VRAM.',
    'internal': 'Expone códigos/indicadores internos o afirma un recuerdo/guardado que la observación no acredita.',
    'leaked_marker': 'El cierre de razonamiento se filtra en la respuesta visible con el backend anterior.',
    'unsupported_promise': 'Promete una lectura sin proponerla y sin operación correspondiente en el catálogo.',
    'scope': 'Añade otro dispositivo e instrucciones manuales cuando sólo falta desambiguar qué aplicación abrir.',
    'adapter_role': 'Atribuye a los adaptadores funciones no observadas en los hechos.',
    'numeric_conversion': 'Los bytes y las conversiones de memoria no concuerdan.',
    'exclusive': 'Afirma que la VRAM sólo guarda imágenes de las pantallas, una exclusividad incorrecta.',
    'wrong_operation': 'Selecciona el estado general en vez de la lista de procesos solicitada.',
    'missing_cause': 'No conserva la causa observada del fallo: memoria desactivada.',
    'address': 'Afirma que RAM no requiere espacio de direcciones físicas; explicación factual incorrecta.',
    'network_fact': 'Afirma conectividad actual sin una observación correspondiente.',
    'wrong_disk': 'Selecciona lista de procesos para una petición de lectura de disco.',
    'negated': 'Propone una lectura que la persona pidió no realizar.',
    'missing_window': 'Describe geometría/estado de la ventana pero omite su identidad solicitada.',
    'gpu_scope': 'Añade límites, roles o interpretaciones de capacidad GPU no sustentadas por las observaciones.',
    'parse_error': 'El servidor falla al analizar la salida y no entrega final válido; no se da crédito a una llamada parcial.',
    'unrequested_connection': 'Propone asegurar/cambiar la conexión Wi-Fi ante una consulta de estado de Internet; excede la lectura solicitada.',
}

LOW37 = {
    'fresh': ['select-disk-used-es', 'select-H0532', 'select-H0359', 'select-cpu-order-es',
              'select-H0499', 'select-H0675', 'select-audio-order-es'],
    'other': ['select-control-other-machine-es'],
    'internet': ['select-network-internet-es', 'writer694-H0127'],
    'language': ['writer521-0'], 'tool_prose': ['writer521-2'],
    'identity': ['writer521-16', 'chat-name-es'], 'disabled': ['writer521-19'],
    'ram_scope': ['writer694-H0508'], 'empty': ['writer694-gpu-usage-es'],
    'ranking': ['writer694-H0650'],
}
BF16 = {
    'fresh': ['select-disk-used-es', 'select-H0532', 'select-H0359', 'select-cpu-order-es',
              'select-H0450', 'select-H0499', 'select-H0602', 'select-H0675'],
    'order': ['select-control-cpu-then-date-en'], 'past': ['select-control-past-en'],
    'other': ['select-control-other-machine-es'],
    'clarification': ['writer521-6', 'writer521-10'], 'ram_scope': ['writer694-H0539'],
    'gpu_number': ['writer694-gpu-usage-es'], 'physics': ['chat-knowledge-en'],
    'memory_definition': ['chat-difference-es'],
}
DECISIONS = {
    '37-q4-low-native-gpu8k1': LOW37,
    '37-q4-low-parser697-1': LOW37,
    '37-q4-low-parser698-1': LOW37,
    '37-q4-high-parser698-1': {
        'fresh': ['select-H0359', 'select-cpu-order-es', 'select-H0450', 'select-H0499',
            'select-H0602', 'select-clock-date-en', 'select-H0675', 'select-audio-order-es'],
        'unsupported_promise': ['select-network-internet-es'], 'other': ['select-control-other-machine-es'],
        'internal': ['writer521-2', 'writer521-3', 'writer521-17'],
        'scope': ['writer521-6', 'writer521-10'], 'language': ['writer521-8'],
        'adapter_role': ['writer694-H0114'], 'numeric_conversion': ['writer694-processes-top3-en'],
        'exclusive': ['chat-difference-es'],
    },
    '09-bf16-high-practical-parser697-1': BF16,
    '09-q8-low-parser698-1': {
        'fresh': ['select-disk-used-es', 'select-H0532', 'select-H0359', 'select-cpu-order-es',
            'select-H0450', 'select-H0499', 'select-H0602', 'select-clock-date-en',
            'select-H0675', 'select-audio-order-es', 'select-control-battery-es'],
        'network_fact': ['select-network-internet-es'], 'order': ['select-control-cpu-then-date-en'],
        'negated': ['select-control-negated-en'], 'other': ['select-control-other-machine-es'],
        'wrong_disk': ['select-control-disk-order-es'], 'address': ['select-control-knowledge-en'],
        'missing_cause': ['writer521-1'], 'disabled': ['writer521-19'],
        'ram_scope': ['writer694-H0111', 'writer694-H0342', 'writer694-H0539', 'writer694-H0508'],
        'gpu_scope': ['writer694-H0114'], 'gpu_number': ['writer694-gpu-usage-es'],
        'ranking': ['writer694-H0650', 'writer694-processes-top3-en'],
        'missing_window': ['writer694-H0104'], 'identity': ['chat-identity-es'],
        'physics': ['chat-knowledge-en'],
    },
    '37-q4-medium-parser697-1': {
        'boundary': ['select-disk-used-es', 'select-H0532', 'select-H0359', 'select-cpu-order-es',
            'select-H0450', 'select-H0499', 'select-H0602', 'select-clock-date-en',
            'select-network-internet-es', 'select-H0675', 'select-audio-order-es',
            'select-control-date-en', 'select-control-battery-es', 'select-control-cpu-then-date-en',
            'select-control-negated-en', 'select-control-past-en', 'select-control-knowledge-en',
            'select-control-other-machine-es', 'select-control-process-memory-es', 'select-control-disk-order-es',
            'writer521-1', 'writer521-3', 'writer521-6', 'writer521-7', 'writer521-8', 'writer521-10',
            'writer521-11', 'writer521-16', 'writer521-17', 'writer521-18',
            'writer694-H0111', 'writer694-H0342', 'writer694-H0539', 'writer694-H0508',
            'writer694-H0114', 'writer694-gpu-usage-es', 'writer694-H0650',
            'writer694-processes-top3-en', 'writer694-H0104', 'writer694-H0127'],
        'disabled': ['writer521-19'], 'language': ['chat-vocative-mixed'],
    },
    '09-q8-medium-parser697-1': {
        'boundary': ['select-disk-used-es', 'select-H0532', 'select-H0359', 'select-cpu-order-es',
            'select-H0450', 'select-H0499', 'select-H0602', 'select-clock-date-en',
            'select-network-internet-es', 'select-audio-order-es'],
        'order': ['select-control-cpu-then-date-en'], 'other': ['select-control-other-machine-es'],
        'internal': ['writer521-1', 'writer521-19'], 'clarification': ['writer521-6', 'writer521-10'],
        'identity': ['writer521-16'], 'ram_scope': ['writer694-H0508'],
        'gpu_number': ['writer694-H0114', 'writer694-gpu-usage-es'],
        'ranking': ['writer694-H0650'], 'physics': ['chat-knowledge-en'],
    },
}

# The complete698 medium review recovered these calls through the official
# implicit boundary. Visible prose and the other empty finals were unchanged.
DECISIONS['37-q4-medium-parser698-1'] = {
    key: list(value) for key, value in DECISIONS['37-q4-medium-parser697-1'].items()
}
recovered_medium_calls = ['select-disk-used-es', 'select-cpu-order-es', 'select-H0450',
    'select-clock-date-en', 'select-network-internet-es', 'select-H0675', 'select-control-date-en',
    'select-control-battery-es', 'select-control-cpu-then-date-en', 'select-control-other-machine-es',
    'select-control-process-memory-es', 'select-control-disk-order-es']
DECISIONS['37-q4-medium-parser698-1']['boundary'] = [case for case in
    DECISIONS['37-q4-medium-parser698-1']['boundary'] if case not in recovered_medium_calls]
DECISIONS['37-q4-medium-parser698-1'].update({
    'internet': ['select-network-internet-es'], 'other': ['select-control-other-machine-es'],
    'wrong_operation': ['select-control-process-memory-es'],
})
DECISIONS['09-q8-medium-parser698-1'] = {
    key: list(value) for key, value in DECISIONS['09-q8-medium-parser697-1'].items()
    if key != 'boundary'
}
DECISIONS['09-q8-medium-parser698-1'].update({
    'boundary': ['select-H0532', 'select-H0499', 'select-H0602'],
    'parse_error': ['select-H0359', 'select-cpu-order-es'],
    'unrequested_connection': ['select-network-internet-es'],
})

p = argparse.ArgumentParser()
p.add_argument('tag', choices=DECISIONS)
args = p.parse_args()
base = Path(__file__).resolve().parents[1] / 'artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696'
private = Path(os.environ['LOCALAPPDATA']) / f'BAXY/C03-k2-run696-{args.tag}-private'
review = private / 'review.json'
rows = json.loads(review.read_text(encoding='utf-8'))
assert len(rows) == 50
failures = {}
for defect, ids in DECISIONS[args.tag].items():
    for case in ids:
        assert case not in failures
        failures[case] = defect
if args.tag == '37-q4-low-native-gpu8k1':
    for row in rows:
        if row['kind'] != 'selector':
            assert '</ifm|think_faster>' in row['response']['content']
            failures[row['id']] = 'leaked_marker'
assert set(failures) <= {r['id'] for r in rows}
adjudications = []
for row in rows:
    code = failures.get(row['id'])
    if code == 'boundary':
        assert not row['response']['content'] and not row['calls']
    if row['response'].get('error'):
        assert code == 'parse_error', 'A failed response cannot receive credit.'
    verdict = {'id': row['id'], 'kind': row['kind'], 'pass': code is None,
        'defect': code or 'none', 'reason': REASONS[code] if code else 'Cumple el criterio declarado para la entrada y los hechos suministrados.'}
    row['verdict'] = verdict
    if args.tag == '09-q8-low-parser698-1' and row['id'] == 'select-control-past-en':
        verdict['note'] = 'La selección efectiva vacía respeta no actuar ante la referencia al pasado. La promesa interna de una lectura futura es incongruente, pero no es la prosa visible ni una ejecución; no se concede cobertura de producto.'
    adjudications.append(verdict)
review.write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
summary = {'utc': datetime.now(timezone.utc).isoformat(), 'tag': args.tag, 'reviewer': 'root',
    'method': 'Revisión manual de las50 entradas/resultados. Misma base congelada y criterios; separación entre error de protocolo y error semántico. Ninguna cobertura C03 ni promoción. No evaluación ciega.',
    'pass': sum(r['pass'] for r in adjudications), 'fail': sum(not r['pass'] for r in adjudications),
    'selector_pass': sum(r['pass'] for r in adjudications if r['kind'] == 'selector'),
    'prose_and_conversation_pass': sum(r['pass'] for r in adjudications if r['kind'] != 'selector'),
    'rows': adjudications, 'private_review_sha256': hashlib.sha256(review.read_bytes()).hexdigest(),
    'repeated_fixture': 'writer521-6 and writer521-10 are identical, not independent evidence'}
(base / ('run-'+args.tag) / 'ADJUDICATION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k: summary[k] for k in ['tag','pass','fail','selector_pass','prose_and_conversation_pass']}))
