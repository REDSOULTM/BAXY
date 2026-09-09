from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-introduction427'
rows=[json.loads(l) for l in (out/'replies.jsonl').open(encoding='utf-8')]
passed=sum((r.get('guard') or [None])[0]==r['expected_guard'] for r in rows)
assert passed==9 and len(rows)==13
report='''# 427 — se reproduce el error AUTO; guardia genérica descartada

El payload nativo exacto426T5 vuelve a seleccionar system.identity para
«Me llamo Álvaro.». También ocurre con Nina y Ana María. El clasificador de
acto sin catálogo devuelve no_effect en los tres; no basta para adoptarlo:
acierta9/13controles y falla aplicaciones incompletas(complete) y guardar/leer
memoria privada(no_effect). Reintroducirlo como filtro general queda descartado.
Esto coincide con la advertencia de llm._decide_turn:7215 de pérdida de lecturas
y conocimiento al reinterpretar AUTO con el clasificador antiguo. La prueba
aporta una reproducción nueva, no permiso para ignorar esos contraejemplos.

NativeAUTO usa el mismo catálogo426T5 en todas las variantes; faltan operaciones
de otros dominios, por lo que las selecciones window.active/media.status de los
controles de app/volumen no describen una recuperación normal del producto.
«No guardes mi nombre» obtiene un falso borrado en la prosa nativa: guardia0no
valida veracidad de esa prosa. No usar conteo del acto como adjudicación de frase.
No efectos reales.13pares,16,906s,GPU3175,56MiB/RAM1349,19MiB,sinviolaciones,
manifiesto intacto. No nueva fuente ni aceptación. Modelos cerrados.

428 estudia otra vía: el parser privado ya reconoce una declaración de nombre
con DeclaredNameInputPattern y separa la cláusula pública. Reutilizar ese dato
sólo si ocupa todo el mensaje, sin guardar nombre ni saltarse pedidos compuestos.
Primero composición aislada con el estado ya existente session_context_only,
frente al payload erróneo426T5. Si funciona, validar límites con nombres Unicode,
terceras personas, guardado explícito, preguntas y acciones añadidas antes de fuente.
No regex nueva por nombre ni caché de identidad ni nuevo prompt/operación.
Llama b9980 documenta tools nativas y --jinja; capacidad de formato no acredita
que AUTO elija bien el acto: https://github.com/ggml-org/llama.cpp/blob/b9980/docs/function-calling.md
Herencia inmediata: NaturalMemoryRequestParser.TryBindSaveInput/DeclaredNameInputPattern
y MainWindow.SessionContextOnly. Fuente actual425 y comportamiento418 se conservan.
'''
for r in rows:report+=f"\n- {r['text']} — guardia {r.get('guard')}, esperado {r['expected_guard']}.\n"
(out/'RESULT.md').write_text(report,encoding='utf-8',newline='\n')
paths=[out/n for n in ['PREREG.json','RESULT.md','resources.json','replies.jsonl','command.json']]
(out/'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n',newline='\n')

source=(root/'scratchpad/c03-os-caption415.py').read_text(encoding='utf-8')
start=source.index("out = root /");end=source.index('\ndef sha(path):',start)
prefix='''out = root / 'artifacts/comprobaciones/C03/astra-introduction-context428'
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-introduction-context428-private'
source = private.parent / 'C03-private-product426-private'
audit = [json.loads(line) for line in (source/'compose-audit.jsonl').open(encoding='utf-8-sig')]
wire = [json.loads(line) for line in (source/'http-posts.jsonl').open(encoding='utf-8-sig')]
row = next(r for r in audit if r['trace']=='t5' and r['stage']=='first')
payload = next(r['payload'] for r in wire if r.get('stage')=='request'
    and r['payload']['messages'][-1].get('content','').startswith('Me llamo Álvaro.\\nsituation:'))
cases = [{'id':'actual426-t5','request':'Me llamo Álvaro.','situation':json.loads(row['situation']),
    'reference':payload,'origin':'synthetic development426T5; captured wrong Windows-account composition'}]
for identifier,request in [('name-en','My name is Nina.'),('compound-name','Mi nombre es Ana María.'),('hyphenated-name','My name is Jean-Luc.')]:
    case=copy.deepcopy(cases[0]);case.pop('reference');case.update(id=identifier,request=request,origin='synthetic standalone declaration under existing declared-name grammar');cases.append(case)
'''
source=source[:start]+prefix+source[end:]
start=source.index('def facts(case, variant):');end=source.index('\n\nfor key in',start)
source=source[:start]+'''def facts(case, variant):
    situation = copy.deepcopy(case['situation']) if variant=='baseline' else {
        'kind':'status','polarity':'success','cause':'session_context_only'}
    return {'situation':json.dumps(situation,ensure_ascii=False)}
''' +source[end:]
start=source.index("prereg = {'utc':");end=source.index("assert prereg['model_sha256']",start)
source=source[:start]+'''prereg = {'utc':datetime.now(timezone.utc).isoformat(),
    'cases':[{'id':c['id'],'request':c['request'],'origin':c['origin']} for c in cases],
    'method':'Existing guarded composition: wrong426 Windows-account facts vs existing session_context_only status for four standalone synthetic declarations. Actual baseline must equal captured426 payload offline and live. Only situation changes; no prompt/weights/sampler/source change. Proposed state assumes the existing typed parser proves an entire standalone declaration; this assumption requires boundary tests before implementation. No product effects or persistence.',
    'criteria':'Acknowledge the human name/current conversation, no Windows account, no claim to change persistent memory or rename BAXY. All four variants useful before source; baseline errors remain preserved. No fresh human acceptance/UI/voice.',
    'inheritance':'DeclaredNameInputPattern and public-clause split/TryBindSaveInput already exist; SessionContextOnly already emits this fact in MainWindow. No new name pattern or response.427 blanket semantic guard rejected9/13,413/414earlyread also rejected; neither reintroduced.',
    'limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'request_seconds':40},
    'model':str(model),'model_sha256':sha(model),'backend_sha256':sha(config['llama_server']),
    'source_sha256':sha(root/'src/baxy_mind/llm.py'),'manifest_sha256':sha(manifest),'private':str(private)}
''' +source[end:]
source=source.replace("['baseline', 'caption']","['baseline', 'session-context']")
source=source.replace('captured411','captured426')
target=root/'scratchpad/c03-introduction-context428.py';assert not target.exists();compile(source,str(target),'exec');target.write_text(source,encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name;text=p.read_text(encoding='utf-8').replace('427 preparado','427descartado;428preparado')
    text=text.replace('scratchpad/c03-introduction427.py','scratchpad/c03-introduction-context428.py')
    text += '''
427reproduceAUTOselfintro→Windows en3nombres;guardiasin catálogo9/13, fallaapps
incompletas/privatesave/read. No blanketguard: fuente7215yaexplicarechazoprevio.
428preparado:composiciónstatussession_context_only existente vs426T5facts erróneos,
4nombres. HeredarDeclaredNameInputPattern(sin public clause)si funciona;sinfuente
hasta probar límites compuestos/guardar/pregunta/tercero. No extra regex/prompt.
''';p.write_text(text,encoding='utf-8',newline='\n')
p=base/'RELEVO_ACTIVO.json';relay=json.loads(p.read_text(encoding='utf-8'));relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='427 reproduces AUTO name/account error; existing guard9/13 rejected, no source change.',continuation='Run428 compose existing session_context_only state for standalone names, exact baseline426. Then boundary tests for reuse of existing declared-name parser if useful. Source425 current; full C03 active.')
p.write_text(json.dumps(relay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('427 recorded;428 prepared')
