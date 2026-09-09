from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
base = root / 'artifacts/comprobaciones/C03'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-private-product420-private'
out = base / 'astra-private-product420'
events = [json.loads(line) for line in (private/'capture/events.jsonl').open(encoding='utf-8-sig')]
counts = {}
for row in events:
    key = row['type'] + (':' + str(row['event'].get('type')) if row['type'] == 'event' else '')
    counts[key] = counts.get(key, 0) + 1
resources = json.loads((out/'resources.json').read_text())
report = f'''# 420 — vuelve el corte por RAM sin compilación

Mismos ocho casos y fuente418 que419. El arranque no compiló ni publicó AOT,
pero el margen de RAM libre de768 MiB volvió a disparar el cierre del árbol
diagnóstico. Eliminar trabajadores de build no resolvió la presión de RAM.
Eventos conservados: `{json.dumps(counts)}`. No se interpreta una admisión
como una respuesta útil ni como validación de418. Exit1, manifiesto intacto.
GPU propia máxima3177,5625 MiB; RAM del árbol4730,1171875 MiB;29,297s.
No acredita voz conjunta. Los registros privados y el intento fallido se conservan.

Siguiente experimento421: sólo cambiar la carga del mismo modelo a --no-mmap.
Herencia local:390 midió este mecanismo con9B; su mala calidad no lo promovió
y no se traslada ese modelo. La ayuda del binario exacto b9980 admite --no-mmap.
El reporte upstream https://github.com/ggml-org/llama.cpp/issues/14187 es de
b5662, cerrado sin confirmar: apoya una hipótesis, no demuestra un bug actual.
Mismos límites, casos, perfil aislado nuevo, parámetros y fuente. Si pasa,
comparar RAM y evaluar cada respuesta; no declarar optimización por arrancar.
'''
(out/'RESULT.md').write_text(report, encoding='utf-8', newline='\n')
paths = [out/n for n in ['PREREG.json','PROCESS.json','EXIT.json','resources.json','RESULT.md']]
paths += [private/n for n in ['launch.log','capture/events.jsonl']]
(out/'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2)+'\n', newline='\n')

target = root/'scratchpad/c03-private-product421.py'
assert not target.exists()
source = (root/'scratchpad/c03-private-product420.py').read_text(encoding='utf-8').replace('420','421')
source = source.replace("'method': 'Eight", "'load_change': '--no-mmap only; inherited390 mechanism on the same 4B model, not a promotion. Exact b9980 help supports this flag. Record effective command. All remaining parameters and resource limits unchanged.',\n    'method': 'Eight")
source = source.replace('No prompt/model/sampler/decision injection.', 'No prompt/weights/sampler/decision injection; native loading only disables mmap.')
compile(source, str(target), 'exec')
target.write_text(source, encoding='utf-8', newline='\n')
hook = root/'scratchpad/c03-owner421-hook'
hook.mkdir(exist_ok=False)
observer = (root/'scratchpad/c03-owner420-hook/sitecustomize.py').read_text(encoding='utf-8').replace('420','421')
observer += '''
original_command = LlmRuntime._server_command
def no_mmap_command(self):
    command = [*original_command(self), '--no-mmap', '--log-file', str(private/'server.log')]
    (private/'effective-server-command.json').write_text(json.dumps(command, indent=2)+'\\n', encoding='utf-8')
    return command
LlmRuntime._server_command = no_mmap_command
'''
compile(observer, str(hook/'sitecustomize.py'), 'exec')
(hook/'sitecustomize.py').write_text(observer, encoding='utf-8', newline='\n')

message = 'Ok, necesito que me expliques lo que estás haciendo y lo que vas a hacer. Me pregunto qué estás haciendo porque no entiendo muy bien lo que haces y cuánto te falta para terminar el goal, qué son las cosas que faltan por cerrarse. Por ejemplo, me interesa mucho la VRAM y la RAM de Vaxi, cuánto usa. Bueno, son 4 GB de VRAM y sé que estás usando alrededor de 5 de RAM, pero recuerda que siempre intenta ocupar el mínimo posible, pero aún así manteniendo la calidad. Si es que es posible. Y nada, solamente completa y sigue trabajando en este goal y ciérralo. Sigue trabajando hasta cerrarlo, por favor.\n'
p = base/'MENSAJES_DUENO_2026-09-08.json'
data = json.loads(p.read_text(encoding='utf-8'))
assert data['count'] == 16
data['messages'].append({'turnId':'01a07f77-edf6-7671-a8d5-fc33e1298029','type':'userMessage','id':'01a0814a-b385-7212-b362-03a7fab1a405','content':[{'type':'text','text':message}]})
data['count'] = 17
data['retrieval'] += '; appended latest direct owner message verified with read_thread on 2026-09-08'
p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
p = base/'INSTRUCCIONES_CONSOLIDADAS_2026-09-08.md'
text = p.read_text(encoding='utf-8').replace('**16 mensajes directos recuperados**','**16 mensajes directos recuperados inicialmente, más el mensaje17 posterior**')
text = text.replace('- Responder con mediciones separadas de RAM y VRAM.', '- Prioridad reiterada en el mensaje17: minimizar tanto RAM como VRAM conservando calidad. No hay obligación de consumir4 GB ni aceptación de5 GB como mínimo. Responder con mediciones separadas de RAM y VRAM.')
text += '\n### 17 — 01a0814a-b385-7212-b362-03a7fab1a405\n\n> ' + message.rstrip() + '\n'
p.write_text(text,encoding='utf-8',newline='\n')

checkpoint = '''# C03 — fuente418 validada;420 corte RAM;421 preparado — EN_CURSO

Goal completo activo, Goal-c03/HEAD2bf3d4c. Preservar WIP/main/evidencia.
Sin agentes/commit/push/Full durante reparación. BAXY manual cerrado; encuesta
PID101140/padre29800 intacta. No modelo/producto activo al preparar421.
17 mensajes directos +742 respuestas/rev1248 consolidados; automáticos excluidos.
Prioridad del dueño: mínimo RAM/VRAM compatible con calidad;4GB es techo conjunto.

## Fuente y validación
-410 cuenta/recursos y descripción catálogo:2260 Python+121subtests,Kernel140,
  turn_policy967;Fast verde. Benchmark explícito omitido no cuenta.
-416 Caption OS via CIM local/runner existente,5s/cancelación, contrato obligatorio.
 36provider+193integration pass/0skips;Fast verde/build18,76s. Producto417:8/9
 útiles, Windows11 ES/EN corregido;RAM/CPU correctos; cuenta T3 aún pide permiso.
 9 finales/200,sin silencio. Sólo206MiB libres en T8: no certifica recursos/voz.
-418 petición privada reconocida reemplaza aclaración pública;NoRoute/AskToSave
 siguen mente.6focales pass/0skips26s;2007owners pass/0skips reportados6m51,
 runtime físico Explicit omitido(no pass);Fast verde/build18,01s. Prueba modelo
 aún pendiente. RESULT/PINS en astra-private-precedence418. No fuente419–421.
-402 preserva valor memoria;404 separa nombre conversación de guardado;395/397
 conservan contexto/reparan límites ES. Heredar sus RESULT, no repetir pruebas.

## Evidencia que decide
415 sólo observed.os.caption:1/4→4/4 composición, llevó416.4178/9producto.
419 corte RAM<768MiB antes de turnos trasAOT;GPU3167,56/RAM3543,67MiB.
420 repite sin build y vuelve a cortar:GPU3177,56/RAM4730,12MiB29,297s.
No conclusión semántica de esos cortes. RESULT/PINS419/420 conservados.
421 preparado con mismos8casos/modelo4B/guards y sólo --no-mmap; herencia390
(9B descartado por calidad). Ayuda exacta b9980 confirma flag; issue14187 de
b5662 no confirmado es hipótesis. Hook registra comando efectivo y log nativo.
Revisar recursos y finales antes de adoptar configuración; no promover modelo.

Descartes:412 no reprodujo historia(welcome faltaba).41313/15→14/15,corrige
cold pero recita warm;41414/15→14/15 intercambia fallo. No combinar pases.
Actor first-person no impuesto en recall(RequiredBaxyActions devuelve[]).
349provenance source=user no corrigió sujeto; no repetir. Parser nombres/color
tiene brazos literales y patrones genéricos; comprobar reachability antes de tocar.

## Pendientes de cierre
CuentaT3, memoria con sujeto equivocado/silencio404b/falsa persistencia,8rutas,
encuesta742/fallosmanuales264.0requisitos finales y0/100humanos frescos certificados.
204posibles335 reservados; no consumir hasta candidato listo. Averías/recuperación,
UI real/voz física/ASR/wake/≤4GBconjunto, runtime/instalación/contratosC04–C09,
Full final entero verde y publicación. Sin bloqueo externo/porcentaje/ETA.

Siguiente: runtime Python -X utf8 scratchpad/c03-private-product421.py.
No fuente mientras corre. Leer resources/EXIT y capture/events del perfil privado.
'''
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p = base/name
    archive = base/(name.removesuffix('.md')+'_420_ANTES_421.md')
    assert not archive.exists()
    archive.write_bytes(p.read_bytes())
    p.write_text(checkpoint,encoding='utf-8',newline='\n')
p = base/'RELEVO_ACTIVO.json'
relay = json.loads(p.read_text(encoding='utf-8'))
relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='418 source validated;420 repeats RAM cutoff without build;421 prepared --no-mmap same 4B.',continuation='Run421 once, verify effective native loading, compare resources and adjudicate every final. Full C03 remains active; no source edits while model runs.')
p.write_text(json.dumps(relay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'420_counts':counts,'421':'prepared','owner_messages':17}))
