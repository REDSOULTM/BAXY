"""Adopt the qualified recovery only; preserve the failed full product panel."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
home = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = base / 'astra-machine-actor-source702'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')

def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

assert not (out / 'RESULT.json').exists()
prereg = read(out / 'PREREG.json')
assert all(sha(root / p) == expected for p, expected in prereg['sources'].items())
assert read(base / 'astra-status-batch702/RESULT.json')['counts'] == {'failed': 55, 'correct_observed_run': 18}
http = {}
for tag in [694, 702]:
    with (home / f'C03-status-batch{tag}-private/http-posts.jsonl').open(encoding='utf-8-sig') as stream:
        http[tag] = [json.loads(line) for line in stream]

def entry(tag, call, stage):
    return next(r for r in http[tag] if r['id'] == call and r['stage'] == stage)

parity = []
for case_id, old_id, new_id in [('H0127', 208, 121), ('H0433', 227, 123)]:
    first = entry(694, old_id, 'request')['payload']
    assert first == entry(702, new_id, 'request')['payload']
    old_draft = entry(694, old_id, 'response')['response']['choices'][0]['message']['content']
    new_draft = entry(702, new_id, 'response')['response']['choices'][0]['message']['content']
    assert old_draft == new_draft == 'No estoy conectado a ninguna red wifi.'
    retry = entry(702, new_id+1, 'request')['payload']
    assert retry['messages'][:-2] == first['messages']
    assert retry['messages'][-2] == {'role': 'assistant', 'content': new_draft}
    answer = entry(702, new_id+1, 'response')['response']['choices'][0]['message']['content']
    assert answer == 'Este PC no está conectado a ninguna red wifi.'
    parity.append({'case_id': case_id, 'first_request694': old_id, 'first_request702': new_id,
                   'first_request_exactly_equal': True, 'first_request_sha256': canonical_sha(first),
                   'first_draft_sha256': canonical_sha(new_draft), 'retry702': new_id+1,
                   'retry_sha256': canonical_sha(retry), 'published_response': answer,
                   'qualification': 'Same first request and draft; the recovery uses the existing CPU helper, including its qualified Qwen sampling. This does not isolate feedback text from that existing recovery sampler.'})
write(out / 'WLAN_PAIRED.json', parity)
for suffix, marker in [('owners', '392 passed in 4.86s'), ('fast', 'source_quality_gate_passed: mode=Fast')]:
    path = Path(os.environ['TEMP']) / f'c03-machine-actor702-{suffix}.log'
    assert marker in path.read_text(encoding='utf-8-sig')
    (out / (suffix.upper()+'.log')).write_bytes(path.read_bytes())

note = '''# Adopción limitada702: recuperación del sujeto del PC

Se reutiliza la recuperación existente de CPU cuando el borrador confunde al asistente con el PC y existe un Boolean de conectividad observado. Se conservan petición, hechos, alcance Wi-Fi/red y último borrador rechazado. No se añaden reintentos, reglas por frase del dueño, respuestas prefabricadas ni otro modelo; no se relajan validadores. El helper conserva su muestreo cualificado para Qwen2507 y no lo impone a otros modelos.

La entrada HTTP completa y el primer borrador de H0127/H0433 son exactamente iguales en694 y702. Antes se repetía el actor incorrecto hasta agotar; ahora un reintento produce «Este PC no está conectado a ninguna red wifi.». El cambio es el mecanismo existente de recuperación, incluyendo su muestreo: no se atribuye la mejora sólo a una frase de feedback. El progreso previo de H0127 describe trabajo en curso, sin afirmar éxito.

Validación:79focales,392dueñas yFast exit0,0advertencias/errores. Los50controles701 por brazo conservan51peticiones y50finales idénticos,44correctos/6fallos en ambos. No activaron recuperación WLAN y no se presentan como una mejora. Las declaraciones STT actualizan sólo el árbol ejecutado; no certifican audio. Full693 anterior sigue de línea base; no se ejecutó Full702 y el Full final continúa pendiente.

El producto completo702 falla:18correctos/55fallos de73. Una selección equivocada y confirmación pendiente absorbieron39preguntas posteriores antes de llegar a la recuperación editada. Cambiaron estados Windows e historial entre corridas; no se atribuyen automáticamente todas las diferencias al parche. Esta adopción reconoce únicamente la mejora causalmente delimitada y sus controles; no aprueba la tanda, las familias de red/procesos ni C03. Permanecen el alcance falso Wi-Fi/Internet, las lecturas históricas, títulos y continuidad. La reparación de la confirmación es el siguiente bloqueo común.

Encuesta26cubiertos/716abiertos/0NA. Picos de producto702:3499,5586MiB GPU/2442,5938MiB RAM, sin UI/voz. Cero cobertura añadida y ningún modelo promovido. Se conserva la comparación699/700 que separa modelos originales de transformaciones BAXY.
'''
(out / 'ADOPTION_NOTE.md').write_text(note, encoding='utf-8', newline='\n')
result = {**prereg, 'utc': datetime.now(timezone.utc).isoformat(), 'adopted': True,
          'validation': {'focal_passed': 79, 'owners_passed': 392, 'owner_skips': 0, 'fast_exit': 0, 'full702_run': False},
          'product702': {'correct': 18, 'failed': 55, 'whole_batch_accepted': False},
          'qualified_gain': ['H0127', 'H0433'], 'private_hashes': {}, 'goal_complete': False}
write(out / 'RESULT.json', result)
write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
attributes = root / '.gitattributes'
existing = attributes.read_text(encoding='utf-8')
lines = [f'/artifacts/comprobaciones/C03/{name}/** -text' for name in
         ['astra-machine-actor-source702', 'astra-machine-actor701-baseline', 'astra-machine-actor701-candidate', 'astra-status-batch702']]
lines.append('/artifacts/comprobaciones/C03/STATUS_BATCH702_PLAN.json -text')
with attributes.open('a', encoding='utf-8', newline='\n') as stream:
    for line in lines:
        if line not in existing:
            stream.write(line+'\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n'+(base / 'astra-status-batch702/RESULT.md').read_text(encoding='utf-8')+'\n'+note)
state = read(base / 'RELEVO_ACTIVO.json')
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(), workStatus='machine_actor702_adopted_awaiting_publication',
             activeValidation=None, checkpoint='702adoptada de forma limitada:79focales/392dueñas/Fast0; WLAN2casos recuperados con entrada inicial idéntica. Producto73:18correctos/55fallos,39capturados por confirmación. Encuesta26/716/0.',
             continuation='Publicar fuente702 y evidencia701/702 tras auditoría de índice. Después reparar continuidad de confirmaciones que absorbe nuevos pedidos. No permitir Sensitive/External en bloque ni aplicar prototype695. Mantener binding exacto y privacidad.',
             previousGoalTurnClassification='progress',
             previousGoalTurnClassificationReason='Se adjudicaron los73turnos702, se delimitó gananciaWLAN por igualdadHTTP y se preservó el fallo de continuidad; source702 validada sin relajar criterios.')
state['latestProductRun'] = {'name': 'product702', 'sessionId': 25749, 'exitCode': 0, 'turns': 73, 'manifestUnchanged': True,
                             'adjudication': 'completed:18correct,55failed; RESULT.json sealed',
                             'result': 'artifacts/comprobaciones/C03/astra-status-batch702/RESULT.json'}
write(base / 'RELEVO_ACTIVO.json', state)
print({'adopted_limited_recovery': True, 'product_batch_failed': True, 'publication_pending': True})
