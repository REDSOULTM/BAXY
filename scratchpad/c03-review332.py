"""Record completed product331 and join final owner review with old audit45."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
out = root / 'artifacts/comprobaciones/C03'
private = base / 'C03-memory-product331-private'
events = [json.loads(line) for line in (private / 'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
terminals = [row for row in events if row.get('type') == 'terminal']
prereg = json.loads((out / 'astra-memory-product331/PREREG.json').read_text(encoding='utf-8'))
reasons = [
    'Útil como petición del dato faltante; no guarda ni propone memory.save.',
    'Inútil: la reacción se convierte en unsupported; el reintento estructurado se trunca.',
    'Inútil: HTTP23/27 sí saluda; el guard de explicación rechaza el seguimiento interrogativo sin punto anterior.',
    'Inútil: pide un nombre que ya tiene en el historial y en su propia respuesta.',
    'Inútil para el contexto: consulta la cuenta de Windows en lugar del nombre declarado.',
    'Inútil: vuelve a preguntar si debe contestar ambas identidades.',
]
lines = ['# Producto331 — 1/6 útil, cero silencios, cierre NO aceptado', '',
    'Proceso exit0, seis admisiones200 y seis terminales publicados sin timeout. '
    'La fuente330 repara99, pero el conjunto retrocede frente a327 (2/6). '
    'No promover como solución integrada sin corregir las regresiones. Desarrollo; no reserva, UI gráfica ni voz física.', '',
    'La única diferencia de fuente prevista es330; al cambiar la primera respuesta cambia también la historia de los turnos siguientes. '
    'No atribuir sus diferencias a una modificación directa del modelo ni llamar a esto control de historia idéntica.', '']
for index, question, terminal, reason in zip([99,101,103,105,107,109], prereg['cases'], terminals, reasons, strict=True):
    lines.extend([f'## Turno {index}', '', question, '', '> ' + terminal['final'], '', reason, ''])
lines.extend(['## Análisis causal y decisión', '',
    '99: parser privado sin ruta; selector sin memory.*; chat pide nombre. Falta estado de dato pendiente y continuidad privada. '
    '101: verificador sin historia dice incomplete_effect; apply_conversation_effect_presentation lo trata como unsupported. '
    'HTTP10/14 niegan memoria por instrucción previa, HTTP11/15 finish_reason=length. No ampliar tokens como solución de la clasificación errónea. '
    '103: saludo válido descartado en __main__.py:6457; guard basado en punto/exclamación confunde pregunta final con respuesta entera interrogativa. '
    '105: error ya en chat, con nombre/historia presentes. '
    '107: selector elige system.identity, dato real de cuenta pero referente equivocado. '
    '109: selector pasa de ninguna operación a system.identity; frontera de observación pide confirmación, no contesta.', '',
    'Decisión de razonamiento xhigh: separar reparación del guard demostrado de continuidad privada y ambigüedad de identidad. '
    'No adoptar más cambios de prompt ni heurísticas por nombre. Memoria exige intención explícita, dato de la persona, '
    'protección existente y postlectura persistente; recordar por historial no prueba un guardado. '
    'Próximo cambio acotado: validar la forma de respuesta interrogativa; luego repetir los seis casos. '
    'El paso de continuidad privada sigue requiriendo xhigh; implementación/tests mecánicos high.', '',
    'Fuentes contrastadas2026-09-08: [parámetros requeridos](https://docs.cloud.google.com/dialogflow/cx/docs/concept/parameter) '
    'distinguen dato pendiente de formulario completo; [Qwen2507 oficial](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) '
    'y la investigación local vigente conservan el modelo exacto, sin extrapolar Thinking. '
    'Herencia: biblioteca/carter/legacy/Carter_v2/LLM_CONTEXT_MEMORY_REPORT.md:12–40 exige procedencia humana y separa cuenta de identidad declarada.', ''])
(out / 'astra-memory-product331/RESULT.md').write_text('\n'.join(lines), encoding='utf-8')
pins = {str(p.relative_to(private)): hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()
        for p in [private/'capture/events.jsonl', private/'http-posts.jsonl', private/'turn-audit.jsonl', private/'raw-replies.jsonl']}
(out / 'astra-memory-product331/PINS.json').write_text(json.dumps(pins, indent=2)+'\n', encoding='utf-8')
a = base / 'C03-real-user-pool-20260906/reserve-audit-tranche45/review.jsonl'
b = base / 'C03-owner-review328-private/reviewed-records.jsonl'
audit = {r['id']: r for r in map(json.loads, a.read_text(encoding='utf-8-sig').splitlines())}
review = list(map(json.loads, b.read_text(encoding='utf-8-sig').splitlines()))
assert len(review) == len(audit) == 742 and all(r['id'] in audit for r in review)
remaining = [dict(id=r['id'], displayId=r['displayId'], status='requires_updated_exposure_context_and_language_audit')
    for r in review if r['ownerReview']['authorship'] is True and r['ownerReview']['capability'] is True
    and audit[r['id']]['freshness_review'] == 'not_disproved_by_this_audit']
assert len(remaining) == 227
private_out = base / 'C03-reserve-preflight332-private'
private_out.mkdir(exist_ok=False)
(private_out/'candidate-ids.json').write_text(json.dumps(remaining, indent=2)+'\n', encoding='utf-8')
public_out = out / 'astra-reserve-preflight332'
public_out.mkdir(exist_ok=False)
(public_out/'RESULT.json').write_text(json.dumps(dict(
    utc=datetime.now(timezone.utc).isoformat(), joined=742, both_positive=711,
    known_exposure_with_both_positive=484, requires_updated_audit=227,
    certified_fresh=0, acceptance_frozen=False,
    sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [a,b]},
    private_ids=str(private_out/'candidate-ids.json'),
    limitations='Audit45 predates subsequent development; no new candidate execution, translation, freshness claim or quota selection. Preserve literal contexts and semantic language review.'
),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'product331':'1/6 useful; no integrated acceptance', 'preflight_ids':len(remaining)}))
