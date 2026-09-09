from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-memory-result-scope442'
(out/'RESULT.md').write_text('''# 442 — omitir la pregunta inventa otro actor

No adoptar. Jordan ES pasa de «Mi nombre es Jordan» a «Jordan ha visto la
memoria»: sigue siendo una afirmación falsa. Marta y Ana María quedan como valor
aislado; hermana, lista y controles enable/save siguen útiles. EN «I found Jordan»
pierde el alcance explícito del registro. No certificar8/8 ni introducir el
alcance en fuente. Todos stop;8,984s/GPU3173,5625MiB/RAM1153,65625MiB, sin
violaciones, manifiesto intacto, cliente cerrado. Fuente436 sigue vigente.

No se atribuye el fallo a KV ni se cambia precisión: issue primario20035 de
llama.cpp (consultado2026-09-08) es b8184/Linux/modelos27B/35B, bug no confirmado
cerrado como not planned. Sus diferencias PPL son menores que sus errores y el
autor contempla ruido. No demuestra fallo q8_0 en b9980/CUDA/4B ni mejora f16.
https://github.com/ggml-org/llama.cpp/issues/20035

443 aborda el otro bloqueo privado ya demostrado401: redacción sin valor visible.
La proyección convierte sensibilidad en el literal [REDACTED]; el modelo lo copia
y niega acceso. Probar un estado tipado redacted=true omitiendo value, manteniendo
la protección previa y sin cambiar un solo byte de valor normal. No declara que
todos los recuerdos sean del usuario ni intenta corregir nombres con este cambio.
''',encoding='utf-8',newline='\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
(out/'PINS.json').write_text(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'},indent=2)+'\n',encoding='utf-8',newline='\n')
source=(root/'scratchpad/c03-memory-roles438.py').read_text(encoding='utf-8')
start=source.index("with (local/'C03-private-product437-private")
end=source.index("out=base/",start)
source=source[:start]+'''def fact_line(payload):
    return next(line for line in payload['messages'][-1]['content'].splitlines() if line.startswith('situation: '))
cases=[];seen=set()
with (local/'C03-required-fact401-private/posts.jsonl').open(encoding='utf-8-sig') as f:
    for line in f:
        row=json.loads(line)
        if row['variant']!='retain-value' or row['id'] in seen:continue
        seen.add(row['id'])
        cases.append({'id':row['id'],'payload':row['payload'],'origin':'exact401 first native payload with402 literal retention'})
assert len(cases)==8
redacted=next(c['payload'] for c in cases if c['id']=='redacted-es')
en=copy.deepcopy(next(c['payload'] for c in cases if c['id']=='stored-en'))
body=en['messages'][-1]['content'];old=fact_line(en)
situation=json.loads(old.removeprefix('situation: '))
situation['seen']['records']=[{'label':'secret','value':'[REDACTED]'}]
lines=body.splitlines();lines[0]='What is stored in private memory?'
lines=[('situation: '+json.dumps(situation,ensure_ascii=False)) if line==old else line for line in lines]
lines=[line for line in lines if not line.startswith(('Contrato literal','Acciones:','Palabras:','Hechos:'))]
en['messages'][-1]['content']='\\n'.join(lines)
cases.append({'id':'redacted-en','payload':en,'origin':'synthetic401 EN redacted control'})
mixed=copy.deepcopy(redacted);body=mixed['messages'][-1]['content'];old=fact_line(mixed)
situation=json.loads(old.removeprefix('situation: '));situation['seen'].update(shown=2,total=2,records=[{'label':'favorite color','value':'turquesa'},{'label':'secret','value':'[REDACTED]'}])
mixed['messages'][-1]['content']=body.replace(old,'situation: '+json.dumps(situation,ensure_ascii=False))
cases.append({'id':'mixed-es','payload':mixed,'origin':'synthetic401 mixed visible/protected control'})
''' +source[end:]
source=source.replace('astra-memory-roles438','astra-memory-redaction443').replace('C03-memory-roles438-private','C03-memory-redaction443-private')
start=source.index(" 'method':");end=source.index(" 'cases':",start)
source=source[:start]+''' 'method':'Ten paired first-native completions: eight401 retain-value payloads plus EN redacted and mixed ES controls. Only records with value exactly[REDACTED] become redacted:true with value omitted. All other data/payloads, system, request, language, contract, model and sampler unchanged. No private value is available, no tools/effects/source edits. Native projection diagnostic, not guarded composer or product.',
 'new_evidence':'401 source records mark protected values with a string sentinel. Native first answer copies that sentinel and incorrectly denies access; subsequent guarded attempts exhaust. MemoryOperationResponseProjection already owns the sensitivity boundary. Compare typed visibility of that same protected data, never pass the underlying private value or force a visible replacement.',
 'criteria':'All3 protected/mixed cases must explain protected data, preserve visible mixed value, and not deny the verified access or invent another value. Seven unchanged controls must have byte-identical payloads; existing ES name attribution failures remain failures outside this hypothesis, never counted green. No source unless all targeted cases improve, then require boundary tests and guarded/native product verification.',
''' +source[end:]
start=source.index("        for variant in ['baseline','tool-return']:");end=source.index("            before=time.monotonic()",start)
source=source[:start]+'''        for variant in ['baseline','typed-redaction']:
            payload=copy.deepcopy(case['payload'])
            if variant=='typed-redaction':
                old=fact_line(payload);situation=json.loads(old.removeprefix('situation: '));changed=False
                for record in situation.get('seen',{}).get('records',[]):
                    if record.get('value')=='[REDACTED]':
                        record.pop('value');record['redacted']=True;changed=True
                if changed:payload['messages'][-1]['content']=payload['messages'][-1]['content'].replace(old,'situation: '+json.dumps(situation,ensure_ascii=False))
                else:assert payload==case['payload']
            else:assert payload==case['payload']
''' +source[end:]
target=root/'scratchpad/c03-memory-redaction443.py';assert not target.exists()
target.write_text(source,encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
 path=base/name;content=path.read_text(encoding='utf-8')
 start=content.index('## Siguiente acción');end=content.index('## Pendientes completos',start)
 content=content[:start]+'''## Siguiente acción
438roles,439/440feedback y4419B no corrigen nombres sin intercambiar errores.
442omitepedido pero inventa Jordanhavio memoria; no adoptar. RESULT/PINS438–442.
443 preparado: otro bloqueo401 (redactadoES agota). Compara sentinel[REDACTED]
con redacted=true sin value en misma proyección, 3targets y7controles intactos.
No cambios de fuente ni nuevasguardas. Ejecutar c03-memory-redaction443.py;
si mejora, boundary/guarded/producto antes de adoptar. Nombres siguependiente.
No repetir feedback/roles/9B/omisiónpedido; no cambiarKV por issue20035 sin
evidencia aplicable. Fuente436; modelos/builds anteriores cerrados.

''' +content[end:]
 content=content.replace('440 rechazado; diagnóstico441 preparado','442 rechazado; diagnóstico443 preparado')
 content=content.replace('438–440 recogidos y cerrados; no modelo/producto/build activo. No editar fuente durante441.','438–442 recogidos y cerrados; no modelo/producto/build activo. No editar fuente durante443.')
 path.write_text(content,encoding='utf-8',newline='\n')
path=base/'RELEVO_ACTIVO.json';record=json.loads(path.read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),continuation='438–442 closed/rejected;source436 unchanged.443 prepared: typed redaction with omitted value, targets3 and unchanged controls7. Private-name subject still open; whole C03 active.')
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('442 recorded;443 prepared; source436 unchanged')
