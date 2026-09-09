from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
local=Path(os.environ['LOCALAPPDATA'])/'BAXY'
out=base/'astra-introduction-context429';private=local/'C03-introduction-context429-private'
rows=[json.loads(l) for l in (out/'replies.jsonl').open(encoding='utf-8')]
report='''# 429 — conversación recupera4/4 saludos; fuente aún no adoptada

Baseline428status igualado offline/live. Misma información; sólo se usa el
evento/intención de conversación existente en lugar de estado de tarea.
2/4→4/4útiles: ES saluda usando el nombre humano; EN «Nice to meet you» con nombre.
No cuentaWindows, cambio de nombre de BAXY ni persistencia afirmada.
7,984s,GPU3173,56MiB/RAM1100,05MiB,sinviolaciones,manifiesto intacto.
No prueba el dispatch de producto ni los límites de reconocimiento del mensaje.

La posible reutilización de DeclaredNameInputPattern necesita cautela: su valor
admite cualquier secuencia de letras/espacios, no demuestra que un nombre
seguido de una orden sin puntuación sea una sola declaración. No se adopta un
atajo de C# que pueda tragarse una petición añadida. Ninguna fuente nueva.

Antes de añadir gramática,430 contrasta el identificador nativo de la operación:
baxy_system__identity frente baxy_system__windows_account. Sólo cambia el nombre
en el esquema tools, conservando la operación canónica/descripcion/contrato y
payload restante. El formato ya usa un mapa reversible entre identificadores
de función y catálogo. No hay propuesta de renombrar kernel/journal ni añadir
operaciones. Si no mejora sin regresiones, descartar; no cadena de alias.
Primaria b9980/docs/function-calling.md confirma el mecanismo de nombres y
tools; efecto semántico es hipótesis local. Fuente410 ya aclaró descripción y
mejoró recuperación, pero426/427 muestran que aún se confunde persona/cuenta.
Esta prueba mide ese dato nuevo, no repite el texto del catálogo.
'''
for r in rows:report+=f"\n- {r['variant']} | {r['request']} | {r['answer']}\n"
(out/'RESULT.md').write_text(report,encoding='utf-8',newline='\n')
paths=[out/n for n in ['PREREG.json','RESULT.md','resources.json','replies.jsonl','command.json']]+[private/'posts.jsonl']
(out/'PINS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n',newline='\n')

# Preserve original428 raw replies privately, then make the public projection explicit.
p=base/'astra-introduction-context428/replies.jsonl';raw=p.read_bytes()
raw_private=local/'C03-introduction-context428-private/raw-replies-public-origin.jsonl'
assert not raw_private.exists();raw_private.write_bytes(raw)
redacted=[]
for r in [json.loads(l) for l in raw.decode('utf-8').splitlines()]:
    if r['variant']=='baseline' and r.get('answer'):
        r['answer']='[Windows account details redacted; full response in private raw file]'
        r['private_raw_reference']=str(raw_private)
    redacted.append(r)
p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in redacted),encoding='utf-8',newline='\n')
pins_path=p.parent/'PINS.json';pins=json.loads(pins_path.read_text());pins[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();pins[str(raw_private)]=hashlib.sha256(raw).hexdigest();pins_path.write_text(json.dumps(pins,indent=2)+'\n',newline='\n')

source=(root/'scratchpad/c03-introduction427.py').read_text(encoding='utf-8')
start=source.index('cases=[');end=source.index("out=base/",start)
source=source[:start]+'''cases=[
    {'id':'actual426-t5','text':'Me llamo Álvaro.','expected':'conversation','payload':reference},
]
for identifier,text in [('name-en','My name is Nina.'),('compound-name-es','Me llamo Ana María.'),('third-person','My brother is called Omar.')]:
    payload=copy.deepcopy(reference);payload['messages'][-1]['content']=text
    cases.append({'id':identifier,'text':text,'expected':'conversation','payload':payload})
wire417=[json.loads(l) for l in (local/'C03-os-product417-private/http-posts.jsonl').open(encoding='utf-8-sig')]
for i,text in enumerate(['What is my Windows username?','Con qué cuenta de Windows se está ejecutando BAXY?','Which Windows account is running BAXY?','Dime la cuenta actual de Windows.'],1):
    payload=next(r['payload'] for r in wire417 if r.get('stage')=='request' and r['payload'].get('tools') and r['payload'].get('tool_choice')=='auto' and r['payload']['messages'][-1].get('content')==text)
    cases.append({'id':f'actual417-account{i}','text':text,'expected':'system.identity','payload':payload})
for identifier,text in [('concept','What is a Windows account?'),('assistant-name','¿Cómo te llamas?'),('hypothetical','If I used another account, would Windows change my name?')]:
    payload=copy.deepcopy(cases[4]['payload']);payload['messages'][-1]['content']=text
    cases.append({'id':identifier,'text':text,'expected':'conversation','payload':payload})
''' +source[end:]
source=source.replace('astra-introduction427','astra-native-identity430').replace('C03-introduction427-private','C03-native-identity430-private')
start=source.index("prereg={'utc':");end=source.index("assert prereg['model_sha256']",start)
source=source[:start]+'''prereg={'utc':datetime.now(timezone.utc).isoformat(),
 'method':'Eleven paired native payloads. Four actual417 account primaries and actual426 introduction are exact captured requests; remaining six are synthetic last-message variations. Baseline vs only tools.function.name baxy_system__identity renamed baxy_system__windows_account. Same descriptions, arguments schema, system prompt/history/roles/weights/context/seed. Function-name mapping is diagnostic only; no source mutation, product effect, second opinion or generated-answer injection. Cold replay is not identical live scheduling; record baseline reproduction.',
 'hypothesis':'Operation description correctly says Windows account after410 but native identifier still says identity, and426/427 map self-introductions to it. Test semantic precision of the existing wire identifier before adding any speech-act grammar. Canonical kernel operation stays system.identity; no catalog/journal rename, new operation, model promotion or phrase alias.',
 'criteria':'Three self introductions and third-person fact yield conversation without claimed persistence/PC reads, four explicit accounts select same canonical read, concept/assistant/hypothetical remain conversation. Compare individual failures, including known baseline417T3 recital. No source adoption on exchanged failures. Native name mechanics in exact b9980 function-calling.md; semantic effect is unproven until measured.',
 'cases':[{'id':c['id'],'text':c['text'],'expected':c['expected']} for c in cases],
 'model':str(model),'model_sha256':sha(model),'backend_sha256':sha(config['llama_server']),'llm_source_sha256':sha(root/'src/baxy_mind/llm.py'),'manifest_sha256':sha(manifest),
 'limits':{'gpu_stop_mib':3800,'minimum_free_ram_mib':768,'request_seconds':40},'private':str(private)}
''' +source[end:]
start=source.index('    for identifier,text,expected in cases:');end=source.index('    complete=not violations',start)
source=source[:start]+'''    for case in cases:
        for role in ['baseline','windows-account-name']:
            payload=copy.deepcopy(case['payload'])
            old_names=[t['function']['name'] for t in payload['tools']]
            assert 'baxy_system__identity' in old_names
            if role!='baseline':
                for tool in payload['tools']:
                    if tool['function']['name']=='baxy_system__identity':tool['function']['name']='baxy_system__windows_account'
            if role=='baseline':assert payload==case['payload']
            row={'id':case['id'],'text':case['text'],'variant':role,'expected':case['expected']}
            client.case=case['id'];client.role=role;before=time.monotonic();client.begin_request(40)
            try:
                response=client._post(payload);result=(response.get('choices') or [{}])[0]
                row['native_message']=result.get('message');row['finish_reason']=result.get('finish_reason')
            except Exception as error:row['error']=type(error).__name__+':'+str(error)
            finally:client.end_request()
            row['seconds']=round(time.monotonic()-before,3)
            with (out/'replies.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\\n')
            print(json.dumps(row,ensure_ascii=True),flush=True)
            if violations:break
        if violations:break
''' +source[end:]
target=root/'scratchpad/c03-native-identity430.py';assert not target.exists();compile(source,str(target),'exec');target.write_text(source,encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
    p=base/name;text=p.read_text(encoding='utf-8').replace('429preparado','4294/4;430identificadornativo preparado').replace('scratchpad/c03-introduction-conversation429.py','scratchpad/c03-native-identity430.py')
    text+='''
429conversationevent2/4→4/4composición; sin fuente. No C#shortcut: DeclaredNameInput
permiteletras/espacios y no prueba ausencia de orden añadida sinpuntuación.
430preparado:11pares nativos, sóloidentificador de función system.identity→
windows_account en esquema model-facing;canonicalkernel intacto.4account417+
4declarativos(426exacto incluido)+3negativos. No nuevo clasificador/regex/prompt.
''';p.write_text(text,encoding='utf-8',newline='\n')
p=base/'RELEVO_ACTIVO.json';relay=json.loads(p.read_text(encoding='utf-8'));relay.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='429 conversation framing4/4; no source dispatch shortcut because generic private name grammar can swallow trailing commands.',continuation='Run430 native function-name precision only,11paired cases/captured payloads. No source/kernel rename; reject exchanged failures. Source425 current; C03 active.')
p.write_text(json.dumps(relay,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('429 recorded;430 prepared')
