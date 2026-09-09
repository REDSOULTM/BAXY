"""Record model comparison and actual product limits; advance compact handoff."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03'
base=Path(os.environ['LOCALAPPDATA'])/'BAXY'
model=out/'astra-model-memory350'
rows=[json.loads(line) for line in (model/'replies.jsonl').read_text(encoding='utf-8').splitlines()]
lines=['# 350 — candidato nativo mejora, sin promoción','',
    '13 controles idénticos:2507 registrado6/13 útiles; Qwen3.5 disponible10/13. '
    'El alternativo repara el nombre del usuario, el guardado y el chat contextual. '
    'Siguen mal las dos preguntas por el nombre del asistente con recuerdos ajenos '
    'como evidencia y enable añade una vista no observada. Primera respuesta nativa, '
    'sin guardas ni ejecución del producto: no aceptación integrada.','',
    'GPU pico2507:3497,56MiB; Qwen3.5:3173,56MiB. RAM:2845,06MiB y3723,29MiB, '
    'respectivamente. Son procesos nativos aislados, no el mínimo ni voz/GUI. '
    'Mismo backend b9980/KV/contexto/sampling, modelos secuenciales, registro intacto.','']
for row in rows:lines.extend([f"## {row['id']} — {row['model']}",'','> '+row['answer'],''])
lines.extend(['## Decisión','',
    'Comprobar producto351 con override declarado; no promover por este resultado. '
    'Reutilizar el activo y la investigación75–77, no descargar ni cambiar defaults. '
    'El nuevo conjunto de fallos justifica esta revisión; no borra regresiones históricas.'])
(model/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')

product=out/'astra-memory-product351'
private=base/'C03-memory-product351-private'
events=[json.loads(line) for line in (private/'capture/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
assert len([row for row in events if row.get('type')=='terminal'])==7
reasons=[
    'Útil: pide el nombre faltante.',
    'Fallo del turno completo: la confirmación explica la activación, pero antes dice no poder saludar por memoria deshabilitada. El fallo sólo afecta memory.save, no saludar; además ya saluda en esa misma frase.',
    'Fallo: nuevo save verificado y narrado, pero enable inventa una vista habilitada. Hola Emmanuel sí existe como borrador nativo de la continuación, pero no se publica; hay que localizar ese descarte, no pedir al modelo otro saludo.',
    'Útil como reconocimiento contextual: saluda a Emmanuel al afirmar Yo soy el. Añade una oferta innecesaria, sin cambiar la identidad.',
    'Fallo: ejecuta system.identity y publica la cuenta Windows usuario en vez del nombre Emmanuel aportado para esta conversación.350 sólo probaba el chat fijo y no cubría esta selección.',
    'Útil: BAXY y Emmanuel correctamente diferenciados.',
    'Útil: Tu nombre es Emmanuel, fiel al recuerdo verificado.',
]
lines=['# Producto351 — 4/7 completos, cero silencios','',
    'Mismos siete pedidos345, Qwen3.5-4B-Q4_K_M como único override de modelo. '
    'Exit0, admisiones200, ningún timeout; registro intacto. Cinco literales humanos '
    'y dos controles sintéticos ya declarados. Conductor no prueba UI/voz.','']
index=-1
for row in events:
    if row.get('type')=='event' and row['event'].get('type')=='activity':
        entry=row['event']['entry']
        if entry['src']=='YOU':
            index+=1;lines.extend([f'## Turno {index+1}','',entry['msg'],''])
        elif entry['src']=='BAXY':lines.extend(['> '+entry['msg'],''])
    elif row.get('type')=='terminal':lines.extend([reasons[index],''])
lines.extend(['## Decisión','',
    'No promoción. Mejora real del recuerdo y del reconocimiento frente a345, '
    'pero no cierre del recorrido. La App conserva operation en resultados/errores '
    'privados; Python lo descarta del payload de composición. En error, eso permite '
    'atribuir memory_disabled a saludar; en enable, enabled carece de ámbito. '
    'Siguiente352: medir preservación de esa identidad de operación con los HTTP '
    'exactos antes de editar. También quedan el descarte del saludo corto válido '
    'y la selección de identidad Windows con contexto personal explícito.'])
(product/'RESULT.md').write_text('\n'.join(lines),encoding='utf-8')
for directory,paths in [
    (model,[base/'C03-model-memory350-private/posts.jsonl',root/'scratchpad/c03-model-memory350.py']),
    (product,[private/'capture/events.jsonl',private/'compose-audit.jsonl',private/'http-posts.jsonl',private/'raw-replies.jsonl',base/'C03-memory-profile351/journal/missions.jsonl']),
]:
    pins={}
    for path in paths:
        with path.open('rb') as stream:pins[str(path)]=hashlib.file_digest(stream,'sha256').hexdigest()
    (directory/'PINS.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8')
archive=model/'PREVIOUS_CHECKPOINT.md'
if not archive.exists():archive.write_bytes((out/'CHECKPOINT.md').read_bytes())
checkpoint='''# C03 — checkpoint351 — EN_CURSO — 2026-09-08

Goal completo activo; rama Goal-c03, HEAD2bf3d4c. WIP/main/evidencia conservados;
sin agentes, commit/push ni Full durante reparación. BAXY cerrado manual y sin
procesos de diagnóstico activos. Encuesta1248/742 intacta, servidor101140 disponible.
16 mensajes directos consolidados en INSTRUCCIONES_CONSOLIDADAS_2026-09-08.md;
excluir órdenes automáticas de otra tarea. AGENTS e identidad vigentes.

## Estado demostrado

340 habilita sólo con confirmación exacta y luego nuevo save; cancelar descarta
continuación.343/343b conserva el dato requerido hasta publicar preguntas válidas.
344 última fuente adoptada: MemoryOperationResponseProjection emite observed
para resultados privados; PrivateOperationNarration añade pendingAction inicial/
recuperación. Schemas, secretos y replay preservados; prosa fija reemplazada.
Focal9pass/0skip122ms; dueñas .NET1913pass/0skip5m19s; Python compositor85pass/
0skip0,65s; Fast verde build18,77s,0warnings/errors. Logs en astra-private-projection344.

345 con2507:3/7 turnos completos,0silencios. Confirmación ahora explica activar;
recall recibe el nombre, pero se lo atribuye al asistente. Enable/save inventan
afirmaciones.346/347/349 no reparan el sujeto: ninguna variante adoptada.348
diálogo nativo conserva8/8 atribuciones,7/8 útiles por un idioma. Ver REVIEW.md
de cada panel; no repetir etiquetas/retornos/annotations de esas tandas.

350:13 mismos payloads,2507 nativo6/13 útiles frente a Qwen3.5 disponible10/13.
GPU3497,56/3173,56MiB; RAM2845,06/3723,29MiB. Aislado, no voz/mínimo.
351 producto con override3.5:4/7 completos,0silencios. Recuerda Tu nombre es
Emmanuel y distingue ambas identidades. Fallos: error atribuye memoria desactivada
a saludar; enable inventa una vista habilitada; saludo corto nativo Hola Emmanuel
no se publica; quien soy elige system.identity y responde cuenta usuario. RESULT/
PINS350/351 escritos. Registro2507 intacto; no promover3.5. Todos handles cerrados.

## Siguiente acción concreta

352: estudiar src/baxy_mind/llm.py:_compose_situation_payload. La App conserva
operation en éxito/fallo privado, pero el payload lo omite. Comparar esos mismos
HTTP351 con operation preservada para acotar el fallo a memory.save y enabled a
memoria; no editar antes de evidencia. Luego localizar descarte del saludo corto
ya correcto y la selección Windows que pierde el referente personal. Privado:
LOCALAPPDATA/BAXY/C03-memory-product351-private. Captura de350 previa incluye
13payloads y modelo alternativo pinneado00fe7986; template/normalización77 vigente.

## Resto íntegro pendiente

Memoria integrada aún incompleta. Otras ocho rutas/errores, preguntas durante
confirmación (MemoryTurnSession Invalid aún omite pendingAction),100humanos frescos
(0certificados/0congelados;204 por auditar335), averías/recuperación, UI escritorio/
voz física/ASR/recursos conjuntos, runtime/instalación, contratos C04–C09 sin ejecutar
esos goals, Full final verde y publicación fuera de main. Sin bloqueo externo ni
porcentaje demostrado. Anterior íntegro: astra-model-memory350/PREVIOUS_CHECKPOINT.md.
'''
for name in ['CHECKPOINT.md','HANDOFF.md']:(out/name).write_text(checkpoint,encoding='utf-8')
state_path=out/'RELEVO_ACTIVO.json'
state=json.loads(state_path.read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='351 finished4/7 complete0silence with diagnostic3.5;350native6/13 vs10/13.344last source,1913NET/85Python/Fastgreen. All processes closed; no promotion.',continuation='352 isolate missing operation scope in private narration using actual351 payloads; then short-greeting publication and contextual identity selection. Full C03 active.')
state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('350 comparison,351 all messages/adjudication/pins and compact current handoff saved; C03 active.')
