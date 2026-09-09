"""Record every published message and operation result in product345."""
from pathlib import Path
import os
import json
import hashlib

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-memory-product345'
base=Path(os.environ['LOCALAPPDATA'])/'BAXY'
private=base/'C03-memory-product345-private'
events=[json.loads(line) for line in (private/'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
terminals=[row for row in events if row.get('type')=='terminal']
assert len(terminals)==7
adjudication=[
    'Útil: pide el nombre que falta.',
    'Útil: saluda y explica que confirmar activa la memoria local privada. La causa previa de memoria desactivada es cierta.',
    'Fallo en el turno completo: enable y nuevo save verificados, saludo final correcto; pero los mensajes intermedios exponen memory configuration, inventan que el sistema fue revisado/está funcionando y afirman que no hubo cambios. El terminal solo no acredita utilidad.',
    'Fallo: contesta con otro saludo a una referencia de identidad.',
    'Fallo: Tú eres tú no responde con la identidad ya aportada.',
    'Útil: distingue BAXY de Emmanuel y dice que habla conmigo. La frase eres tú mismo es redundante; no invierte el interlocutor como342.',
    'Fallo: el valor recuperado llega completo, pero Me llamo Emmanuel lo atribuye a BAXY. No es olvido ni fallo del store; es atribución del sujeto al componer.',
]
lines=['# Producto345 — 3/7 completos, cero silencios','',
    'Mismos siete pedidos de342, con confirmar y cómo me llamo declarados como controles sintéticos. '
    'Exit0, admisiones200, ningún timeout, manifiesto sin cambios. No aceptación fresca/UI gráfica/voz física. '
    'Se adjudica cada turno completo, incluidos resultados intermedios.','']
index=-1
for row in events:
    if row.get('type')=='event' and row['event'].get('type')=='activity':
        entry=row['event']['entry']
        if entry['src']=='YOU':
            index+=1
            lines.extend([f'## Turno {index+1}', '', entry['msg'], ''])
        elif entry['src']=='BAXY':
            lines.extend(['> '+entry['msg'], ''])
    elif row.get('type')=='terminal':
        lines.extend([adjudication[index],''])
journal=[json.loads(line)['payload'] for line in (base/'C03-memory-profile345/journal/missions.jsonl').read_text(encoding='utf-8-sig').splitlines()]
lines.extend(['## Diagnóstico', '',
    '344 recupera los registros en seen y explica la confirmación. Se mantiene como reparación de transporte, '
    'sin afirmar que cierre la narración privada. La composición de resultados usa kind=status/outcome=completed '
    'y añade Report the verified results. Completing a request does not imply changing the PC. '
    'Enable/save repiten metadatos e inventan verificaciones ajenas; recall invierte el sujeto. '
    'Contrastar la representación con el resultado tipado kind=operation, ya usado por otras operaciones, '
    'sin añadir un veto de frase ni un nombre al prompt. Historial contextual105/107 sigue separado.',''])
(out/'RESULT.md').write_text('\n'.join(lines),encoding='utf-8')
pins={}
for path in [private/'capture/events.jsonl',private/'compose-audit.jsonl',private/'http-posts.jsonl',base/'C03-memory-profile345/journal/missions.jsonl']:
    with path.open('rb') as stream: pins[str(path)]=hashlib.file_digest(stream,'sha256').hexdigest()
(out/'PINS.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'result':'3/7 complete, 0silence','journal':[{'operation':r.get('operation'),'phase':r.get('phase'),'status':r.get('status')} for r in journal]},ensure_ascii=True))
