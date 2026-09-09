"""Record actual355 progress and the remaining publication/identity causes."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03'
base=Path(os.environ['LOCALAPPDATA'])/'BAXY'
private=base/'C03-memory-product355-private'
target=out/'astra-memory-product355'
events=[json.loads(line) for line in (private/'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
terminals=[row for row in events if row.get('type')=='terminal']
assert len(terminals)==7 and all(not row['timedOut'] and row['admissionStatus']==200 for row in terminals)
reasons=[
    'Útil: pide el nombre faltante.',
    'Útil: el fallo se limita a guardar con memoria desactivada; saluda y explica la activación que se confirma. Ya no dice no poder saludar.',
    'Útil: confirmación de activación y nuevo guardado verificados, sin inventar una vista ni cambios globales. El saludo pedido ya se vio en T2. Subsiste un defecto separado: la continuación genera Hola Emmanuel, que la App veta como restates_request y recompone el resultado anterior.',
    'Útil: reconoce a Emmanuel en el saludo frente a la referencia Yo soy el; la oferta adicional es innecesaria pero no contradice.',
    'Fallo: system.identity devuelve la cuenta Windows usuario, que no responde al referente personal Emmanuel ya aportado y guardado. Provider veraz, selección/contexto incorrectos.',
    'Útil: distingue BAXY y Emmanuel.',
    'Útil: devuelve Emmanuel desde memory.recall verificado.',
]
lines=['# Producto355 — 6/7 completos, cero silencios','',
    'Mismos siete pedidos y overrideQwen3.5 de351; única diferencia de fuente354 '
    'conserva operation al componer. Exit0, admisiones200, sin timeout; registro '
    'intacto. Cinco literales humanos más confirmar/recall sintéticos declarados. '
    'No reserva fresca, escritorio gráfico ni voz física.','']
index=-1
for row in events:
    if row.get('type')=='event' and row['event'].get('type')=='activity':
        entry=row['event']['entry']
        if entry['src']=='YOU':index+=1;lines.extend([f'## Turno {index+1}','',entry['msg'],''])
        elif entry['src']=='BAXY':lines.extend(['> '+entry['msg'],''])
    elif row.get('type')=='terminal':lines.extend([reasons[index],''])
journal=[json.loads(line)['payload'] for line in (base/'C03-memory-profile355/journal/missions.jsonl').read_text(encoding='utf-8-sig').splitlines()]
completed=[row for row in journal if row.get('response')]
assert any(row['operation']=='memory.enable' and row['response']['status']=='completed' and row['response']['verified'] for row in completed)
saves=[row for row in completed if row['operation']=='memory.save']
assert len(saves)==2 and saves[0]['response']['status']=='failed' and saves[1]['response']['status']=='completed'
assert saves[0]['invocationId']!=saves[1]['invocationId']
assert any(row['operation']=='memory.recall' and row['response']['status']=='completed' and row['response']['verified'] for row in completed)
lines.extend(['## Decisión y límites','',
    'Mantener354: mejora de3514/7 a3556/7, con los mismos controles y sin relajar '
    'guardas. Mantener Qwen3.5 como candidato no promovido; otras rutas, selector, '
    'recursos conjuntos y runtime siguen necesitando comprobación. El journal '
    'acredita enable, nuevo save distinto del fallido y recall. No equiparar esto '
    'con C03 completo ni con100casos humanos frescos.','',
    'Siguiente causa: RestatesTheRequest trata dime hola emmanuel como una '
    'petición de información y rechaza Hola Emmanuel por coincidir con el resto '
    'tras quitar dime. El objetivo público tras memoria es esa petición de saludo; '
    'el modelo ya la cumple. Corregir sólo ese veto con variantes generales de '
    'saludo/cita solicitados y controles de eco realmente inútil, sin nombre fijo. '
    'Después, contrastar contexto del selector que aún interpreta quien soy como '
    'system.identity. No editar otro prompt para suplir un borrador ya correcto.'])
(target/'RESULT.md').write_text('\n'.join(lines),encoding='utf-8')
for directory,paths in [
    (target,[private/'capture/events.jsonl',private/'compose-audit.jsonl',private/'http-posts.jsonl',private/'raw-replies.jsonl',base/'C03-memory-profile355/journal/missions.jsonl']),
    (out/'astra-operation-scope352',[base/'C03-operation-scope352-private/posts.jsonl',root/'scratchpad/c03-operation-scope352.py']),
    (out/'astra-operation-guarded353',[base/'C03-operation-guarded353-private/posts.jsonl',root/'scratchpad/c03-operation-guarded353.py']),
]:
    pins={}
    for path in paths:
        with path.open('rb') as stream:pins[str(path)]=hashlib.file_digest(stream,'sha256').hexdigest()
    (directory/'PINS.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8')
for name in ['CHECKPOINT.md','HANDOFF.md']:
    path=out/name
    text=path.read_text(encoding='utf-8').replace('checkpoint354/355','checkpoint355')
    text=text.replace('producto355 oculto en curso, handle66634.', 'producto355 terminó; todos los handles de pruebas cerrados.')
    text=text.replace('Recoger producto355, handle66634, privado LOCALAPPDATA/BAXY/C03-memory-product355-private.\nMismos siete pedidos/modelo351; sólo fuente354 difiere. Leer cada mensaje y journal.\nNo editar fuente mientras corre. Después reparar saludo corto:',
        'Producto355 terminó6/7 completos,0silencios; mismo panel/modelo351 y fuente354.\nJournal acredita enable/nuevo save/recall. RESULT/PINS escritos; no promoción.\nSiguiente: reparar saludo corto:')
    path.write_text(text,encoding='utf-8')
state_path=out/'RELEVO_ACTIVO.json'
state=json.loads(state_path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='355finished6/7 complete0silence, source354scope fixes error/enable; Python1035pass/Fast3.39s. All processes closed; Qwen3.5 remains diagnostic override.',continuation='Fix measured C# restates_request veto of dime hola <name> -> Hola <name>; then contextual personal identity vs Windows selection. Full C03 active.')
state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('3556/7, journal verified, evidence pinned; all handles complete, C03 active.')
