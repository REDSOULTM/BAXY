from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-memory-gemma-redaction446'
(out/'RESULT.md').write_text('''# 446 — redacción tipada intercambia errores en Gemma

Los8 controles normales siguen correctos. En3protegidos/mixtos,1/3→1/3:
EN mejora y deja de inventar una eliminación; el mixto ahora emite fake tools
y afirma un save no pedido. ES mantiene fake tools. No adopción de proyección
ni promoción de modelo. Todos stop;10,188s/GPU1719,5703125MiB/RAM2836,23046875MiB,
sin violaciones, manifiesto intacto, cliente cerrado. No repetir la representación.

447 conserva444 exactamente y contrasta formato de salida: un objeto con
message:string, sin contenido predefinido, frente a texto libre. La fase debe
redactar, no proponer herramientas. Hereda response_format/json_schema y el
transporte existente, no añade otro modelo, juez, reintento ni parche de nombres.
Se conserva la advertencia de INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md:
gramática válida no implica semántica correcta. Las fuentes LetMeSpeakFreely y
la reproducción de dotTXT allí contrastadas justifican controlar el formato
con mensajes/sampler idénticos; no son una garantía para este checkpoint.
El resultado requerido es utilidad11/11, no sólo JSON válido o ausencia de tools.
''',encoding='utf-8',newline='\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
(out/'PINS.json').write_text(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'},indent=2)+'\n',encoding='utf-8',newline='\n')
source=(root/'scratchpad/c03-memory-gemma444.py').read_text(encoding='utf-8')
source=source.replace('astra-memory-gemma444','astra-memory-output447').replace('C03-memory-gemma444-private','C03-memory-output447-private')
start=source.index(" 'method':");end=source.index(" 'cases':",start)
source=source[:start]+''' 'method':'Eleven paired native first completions from444. Only output format differs: free text versus json_schema with one required message:string and no other properties. Input messages/data/model/sampler/output token limit identical. Parse that generated field for adjudication; no rewriting its contents or fixed visible text. No secondary model, validation/retry, source edits, offered tools/effects or runtime promotion.',
 'new_evidence':'444 resolves8basic but produces fake tool syntax on protectedES and false deletion onEN;446 representation trades failures. Test the actual final-message response contract via existing structured transport. Reuse INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md and its primary-source comparison warnings: constrain syntax without assuming semantics or changing prompts in the same test.',
 'criteria':'All11 useful with correct subject/values/protection and no effects/deletion/access denial or tool syntax. Strict JSON alone does not pass. Compare each case, raw content, parsed message, finish_reason and resources. No source unless targeted failures resolve without regressions; then guarded composer/product and ownership validation required.',
''' +source[end:]
start=source.index("        for variant in ['published-gemma']:");end=source.index("            before=time.monotonic()",start)
source=source[:start]+'''        for variant in ['baseline','message-schema']:
            payload=copy.deepcopy(case['payload'])
            if variant=='message-schema':
                payload['response_format']={'type':'json_schema','json_schema':{'name':'visible_message','strict':True,'schema':{'type':'object','properties':{'message':{'type':'string'}},'required':['message'],'additionalProperties':False}}}
            else:assert payload==case['payload']
''' +source[end:]
needle="row={'id':case['id'],'variant':variant,'answer':choice['message'].get('content'),'finish_reason':choice.get('finish_reason')}"
replacement=needle+'''
                row['raw_content']=row['answer']
                if variant=='message-schema':
                    try:
                        parsed=json.loads(row['answer'])
                        assert isinstance(parsed,dict) and set(parsed)=={'message'} and isinstance(parsed['message'],str)
                        row['answer']=parsed['message']
                    except (ValueError,TypeError,AssertionError) as error:
                        row['parse_error']=type(error).__name__;row['answer']=None'''
assert needle in source;source=source.replace(needle,replacement)
target=root/'scratchpad/c03-memory-output447.py';assert not target.exists()
target.write_text(source,encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
 path=base/name;content=path.read_text(encoding='utf-8')
 start=content.index('## Siguiente acción');end=content.index('## Pendientes completos',start)
 content=content[:start]+'''## Siguiente acción
446 tipada1/3→1/3 intercambiafallos/fake save, rechazada;8normales correctos.
447 preparado: mismos11payloads444, sólo response_format objeto message:string
sin frase obligatoria;22primeras llamadas nativas. Formato no acredita semántica.
Ejecutar c03-memory-output447.py; nofuente mientrasmodelo. Si11/11 luego
guarded/producto/owners antes de promover. Fuente436, anteriorescerrados.
Modelo candidatoGemmapublicado9d4a5a65, no promoción ni adapter separado.
Mensaje18 dueño enconsolidado yOWNER_MESSAGE18.json;18directos.

''' +content[end:]
 content=content.replace('445 rechazado; diagnóstico446 preparado','446 rechazado; diagnóstico447 preparado').replace('No editar fuente durante446.','No editar fuente durante447.')
 path.write_text(content,encoding='utf-8',newline='\n')
path=base/'RELEVO_ACTIVO.json';record=json.loads(path.read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),continuation='446 redaction trades failures, rejected.447 one-field output JSON vs free text on11samepublishedGemma payloads, prepared. Source436 unchanged, no promotion, fullgoalactive.')
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('446 recorded;447 prepared; source436 unchanged')
