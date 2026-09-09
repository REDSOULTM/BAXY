"""Seal completed native diagnostics without promoting a model or changing coverage."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
private_base = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
campaigns = {
    'gemma-current-writer557': ('18 respuestas completas. Perfil Gemma462 thinking/lazy heredado. Mejora sujeto de CPU y estado de memoria, pero transforma los bytes de GPU en 6287,26 GB por tarjeta y llama núcleos a los procesadores lógicos en español. No se promociona.', 18),
    'native-cpu-owner558': ('Ocho respuestas completas. Renombrar el porcentaje como uso de todo el equipo no impide Estoy usando en español ni corrige núcleos frente a procesadores lógicos. No se adopta.', 8),
    'native-cpu-subject559': ('Ocho respuestas completas. La instrucción explícita sobre el sujeto conserva Estoy usando en español. Segunda comparación de esta línea sin mejora suficiente: no continuar barriendo instrucciones equivalentes.', 8),
    'inherited-lora560': ('Preflight detenido antes de inferencia por discrepancia en el estado inicial del adaptador. No se guardó la respuesta de la API: no atribuir un valor concreto a este ensayo. Recursos son de arranque, no de calidad. Recuperación documentada en561.', 0),
    'inherited-lora561': ('54 respuestas completas: 18 entradas actuales por base registrada, base con muestreo documentado y ese mismo muestreo con LoRA piloto4 heredado. No se entrenó nada nuevo. El adaptador corrige el sujeto de CPU y simplifica guardado, pero se presenta con el nombre del usuario en una confirmación, niega capacidad de memoria y conserva metanarración del progreso. No se promociona. API inicial devolvió escala1; POST y GET comprobaron escala0 antes de inferencia; cada petición fijó escala explícita. Sin cambio de manifiesto.', 54),
    'mutation-view562': ('Ocho respuestas completas: cuatro recibos por dos brazos. Omitir indicadores falsos y restaurar un supuesto label reduce afirmaciones sobre esos indicadores, pero persiste narración mecánica y duplicada. El campo probado era selector: NO equivale necesariamente a Label. No se adopta ni se autoriza exponer identificadores internos.', 8),
    'mutation-cause563': ('Ocho respuestas completas. Quitar la causa redundante mejora tres recibos; el nombre sigue narrado mecánicamente. Hereda la identificación incorrecta selector como Label de562. La proyección actual y su test excluyen selector deliberadamente. No se adopta. Faltan español, estados verdaderos y privacidad antes de cualquier cambio de contrato.', 8),
    'bound-save-request564': ('Ocho respuestas completas. Sustituir confirm por el pedido de guardado original mejora algunos recibos pero mantiene redundancia y metadatos en la preferencia de entrega. Jordan procede de521; los otros tres pedidos son contrafactuales explícitos, sin efectos reales. No se adopta sin vincular el contexto a la invocación exacta y preservar privacidad.', 8),
}

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

for name, (conclusion, expected) in campaigns.items():
    out = base / ('astra-' + name)
    private = private_base / ('C03-' + name + '-private')
    responses = private / 'responses.jsonl'
    rows = [json.loads(s) for s in responses.read_text(encoding='utf-8-sig').splitlines()] if responses.exists() else []
    assert len(rows) == expected, (name, len(rows), expected)
    assert all(r.get('response', {}).get('choices', [{}])[0].get('finish_reason') == 'stop' for r in rows)
    lines = [f'# Diagnóstico {name}', '', conclusion, '', '## Capturas completas', '']
    for i, row in enumerate(rows, 1):
        lines += [f'### {i} · {row.get("case", row.get("selector", "caso"))} · {row.get("profile", row.get("arm", ""))}', '', json.dumps(row, ensure_ascii=False, indent=2), '']
    request_path = private / 'requests.jsonl'
    if request_path.exists():
        lines += ['## Payloads nativos', '', request_path.read_text(encoding='utf-8-sig')]
    report = private / 'RESULT.md'
    report.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    result = {'conclusion': conclusion, 'response_count': len(rows), 'adopted': False, 'new_training': False,
              'survey_counts': {'covered': 8, 'open': 734, 'not_applicable': 0},
              'resources': read(out / 'RESOURCES.json'), 'private_report': str(report), 'private_report_sha256': sha(report),
              'limits': 'Desarrollo nativo local. No acredita producto integrado, interfaz, voz, reserva ciega ni cobertura adicional de encuesta.'}
    write(out / 'RESULT.json', result)
    (out / 'RESULT.md').write_text(f'# {name}\n\n{conclusion}\n\n' + result['limits'] + '\n', encoding='utf-8', newline='\n')
    write(out / 'PINS.json', {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})

attributes = root / '.gitattributes'
text = attributes.read_text(encoding='utf-8')
for name in campaigns:
    rule = f'/artifacts/comprobaciones/C03/astra-{name}/** -text'
    if rule not in text:
        text += rule + '\n'
attributes.write_text(text, encoding='utf-8', newline='\n')

note = '''# Handoff C03 — 564

Objetivo activo, sin decisión pendiente del dueño. Fuente555 publicada8027c2220997ee9407f04aac94b383e0647225c4; sin fuente posterior. Producto556 confirma reintento contextual y cubre H0078. Encuesta8 cubiertos/734 abiertos/0 no aplicables; original742/rev1248 intacto. BAXY manual cerrado.

557–564 cerrados documentalmente: Gemma18 EOS rechazada por unidades GPU; dos variantes CPU558/559 sin mejora; LoRA560 preflight falló y561 recuperó escala0 verificada por API antes de54 EOS con escala por petición. LoRA mejora CPU/recibo pero cambia actor de nombre y niega capacidad de memoria: no promoción ni entrenamiento nuevo. Recursos561 GPU3735,563 MiB/RAM1084,434 MiB; nativo, no conjunto final. No procesos pendientes de esas campañas.

562/563 simplifican recibos pero llaman Label a selector, que el almacén mantiene distinto y el test de proyección excluye deliberadamente. No adoptar ni exponer selector.564 cambia sólo confirm por pedido original; reduce algunos fallos, no todos. Cualquier conservación del contexto necesita enlace exacto a PreparedOperation y privacidad. Primera pérdida localizada: MemoryOperationResponseProjection.cs descarta selector deliberadamente; MemoryTurnSession publica resultado sin pedido original. No asumir que recuperar selector sea reparación correcta.

Próximo trabajo: cambiar de estrategia respecto a barridos de instrucciones/renombrados. Reparar la primera transformación demostrada o evaluar una alternativa heredada sobre fallos actuales, sin promover por una respuesta. CPU: uso total mal atribuido a BAXY; capacidad memoria deshabilitada confundida con inexistencia; procesadores lógicos y unidades GPU incorrectos. Quedan encuesta restante, ocho rutas, UI real, loopback completo/AEC como supresión y Full final verde. C08 humano sólo evidencia, no cierre ajeno. Full526 rojo reparado en dueñas528–531; no Full final aún.

Validación fuente555:1936 pass+121 subtests,0 skips; STT12 pass/1 skip ambiental; Fast verde, Release21,57s. Árbol STT5a3d37d79c0e4b7366c3d7857b699a32c9d6e1b84df9d794f89bc3dea890415d/403 archivos. No cambiar sellos históricos. Main5f572ee1b48cb5e2543ee5e06510e51057c9c845 intacto. Informes privados incluyen todas las respuestas y payloads; PINS conserva los públicos.
'''
(base / 'HANDOFF.md').write_text(note, encoding='utf-8', newline='\n')
with (base / 'CHECKPOINT.md').open('a', encoding='utf-8', newline='\n') as stream:
    stream.write('\n\n' + note)
state = read(base / 'RELEVO_ACTIVO.json')
state.update(checkpoint='564: diagnostics557–564 adjudicated, no promotion. Survey8/734/0; source555 published, product556 verified.',
             continuation='Repair remaining C03 behavior using demonstrated ownership; no equivalent CPU/prompt sweeps. Then survey, desktop, loopback/AEC, joint resources and final Full.',
             confirmedAtUtc=datetime.now(timezone.utc).isoformat())
write(base / 'RELEVO_ACTIVO.json', state)
matrix = root / 'documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md'
text = matrix.read_text(encoding='utf-8')
old = 'Fuente adoptada HEAD=origin/Goal-c03=1d08cc297547ebc1d38d98492a41973816423416 al publicar545; sin fuente propia pendiente después. Main intacto5f572ee. Incluye control892c506 y correcciones528–545. Dueñas545:3699 pass+121 subtests,0 skips; Fast verde, Release21,23s sin advertencias/errores;'
new = 'Fuente adoptada HEAD=origin/Goal-c03=8027c2220997ee9407f04aac94b383e0647225c4 al publicar555; sin fuente propia pendiente después. Main intacto5f572ee. Incluye control892c506 y correcciones528–555. Dueñas555:1936 pass+121 subtests,0 skips; Fast verde, Release21,57s sin advertencias/errores;'
assert text.count(old) == 2
matrix.write_text(text.replace(old, new), encoding='utf-8', newline='\n')
print('Closed557–564; no source promotion, no survey change.')
