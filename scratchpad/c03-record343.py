"""Record the first native343 failure without confusing sidecar acceptance with publication."""
from pathlib import Path
import os
import json
import hashlib

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03/astra-memory-product343'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-memory-product343-private'
events = [json.loads(l) for l in (private/'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
terminals = [r for r in events if r.get('type') == 'terminal']
assert len(terminals) == 2
prereg = json.loads((out/'PREREG.json').read_text(encoding='utf-8'))
lines = ['# Producto343 — 1/2 útil, un silencio', '',
    'Dos controles sintéticos declarados; no reserva fresca ni humanos recuperados. '
    'Exit0, admisiones200, sin timeout. El final de proceso no implica aceptación.', '']
for request, terminal in zip(prereg['cases'],terminals,strict=True):
    lines.extend([request, '', '> '+terminal['final'], ''])
lines.extend(['Python rechaza el primer borrador que afirma recordar al usuario y acepta '
    'el retry «What’s your name again?». La App lo rechaza después: '
    'ModelMessageComposer aplica ConversationReplyRejectionReason sin dato requerido, '
    'activa knowledge_not_answered y repite el ciclo. La publicación real acaba en '
    'model_response_rejected. Source343b incorpora ese mismo dato tipado a la frontera '
    'de la App; control adverso sin campo o afirmando guardado sigue fallando. '
    'Dueñas App217pass0skip16s; Fast/nativo343b pendientes.'])
(out/'RESULT.md').write_text('\n'.join(lines),encoding='utf-8')
pins = {}
for path in [private/'capture/events.jsonl',private/'compose-audit.jsonl',private/'http-posts.jsonl']:
    with path.open('rb') as stream:
        pins[str(path)] = hashlib.file_digest(stream,'sha256').hexdigest()
(out/'PINS.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8')
print('343 failure recorded; App217 tests passed; native343b still pending.')
