from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
out=base/'astra-memory-gemma-base445'
(out/'RESULT.md').write_text('''# 445 — la base pierde la atribución; no sustituir el adaptado

Los tres nombres ES vuelven a atribuirse a BAXY:5/8 básicos útiles frente a8/8
del publicado444. Desaparecen las herramientas inventadas en redactadoES y la
eliminación inventadaEN; aun así las frases no explican la protección y ES
copia la etiqueta inglesa secret. Mixto llama «redactado» a un dato oculto,
traducción ambigua que no acredita explicación de protección. No11/11 ni
promoción. Todos stop; recursos en resources.json, registro intacto, cerrado.

446 mide una sola interacción relevante: representación tipada443 con el
checkpoint publicado444.443 no mejoró Qwen, pero444 ya resolvió los8 básicos;
sus nuevos errores sólo aparecen ante el sentinel. No repite feedback/nombres
ni descarga modelos. Si no resuelve los3 protegidos sin alterar los8 básicos,
no se adopta la proyección ni se promueve modelo.
''',encoding='utf-8',newline='\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
(out/'PINS.json').write_text(json.dumps({p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'},indent=2)+'\n',encoding='utf-8',newline='\n')
source=(root/'scratchpad/c03-memory-gemma444.py').read_text(encoding='utf-8')
source=source.replace('astra-memory-gemma444','astra-memory-gemma-redaction446').replace('C03-memory-gemma444-private','C03-memory-gemma-redaction446-private')
start=source.index(" 'method':");end=source.index(" 'cases':",start)
source=source[:start]+''' 'method':'Eleven current444 native baselines, with a second variant only for the3 protected/mixed payloads. Replace exact[REDACTED] sentinel by redacted:true and omit value as443; preserve all actual visible data and every other message/setting. Eight normal controls are regenerated once unchanged, not repaired. Fourteen calls max. Published Gemma already verified, no adapter/source/tools/effects/manifest change.',
 'new_evidence':'444 published Gemma uniquely resolves8/8 current basic memory cases, but misreads redaction sentinel.445 standard base regresses3names, so no replacement.443 typed redaction failed onQwen; this one interaction comparison has a new model and distinct native failures, not another variant under the same rejected profile. Require measured result, not assumed transfer.',
 'criteria':'All11 useful, especially3protected/mixed explain hidden value and preserve visible data; no invented tools/effects/deletion, no access denial or assistant-name transfer. Exactly identical eight normal payloads to444 and inspect their semantics again. If targets fail no source/projection adoption, no promotion. Guarded composer/product/regression/resources still mandatory after a native pass.',
''' +source[end:]
start=source.index("        for variant in ['published-gemma']:");end=source.index("            before=time.monotonic()",start)
source=source[:start]+'''        initial=json.loads(fact_line(case['payload']).removeprefix('situation: '))
        protected=any(r.get('value')=='[REDACTED]' for r in initial.get('seen',{}).get('records',[]))
        for variant in (['baseline','typed-redaction'] if protected else ['baseline']):
            payload=copy.deepcopy(case['payload'])
            if variant=='typed-redaction':
                old=fact_line(payload);situation=json.loads(old.removeprefix('situation: '))
                for record in situation['seen']['records']:
                    if record.get('value')=='[REDACTED]':record.pop('value');record['redacted']=True
                payload['messages'][-1]['content']=payload['messages'][-1]['content'].replace(old,'situation: '+json.dumps(situation,ensure_ascii=False))
            else:assert payload==case['payload']
''' +source[end:]
target=root/'scratchpad/c03-memory-gemma-redaction446.py';assert not target.exists()
target.write_text(source,encoding='utf-8',newline='\n')
for name in ['CHECKPOINT.md','HANDOFF.md']:
 path=base/name;content=path.read_text(encoding='utf-8')
 start=content.index('## Siguiente acción');end=content.index('## Pendientes completos',start)
 content=content[:start]+'''## Siguiente acción
444publicado9/11 (básicos8/8);445base regresa nombres5/8; no promover.446
preparado: publicado444 + representación tipada443 sólo en3protegidos, ocho
básicos idénticos.14calls max; si falla no proyección nueva. No feedback/roles/
colección. Ejecutar c03-memory-gemma-redaction446.py, no fuente mientrascorra.
Todos anteriorescerrados; fuente436 vigente. Mensaje18 incorporado conid
01a081bf-b744-77b1-ada9-9ab23885bd47 ytexto literal/JSON;18consolidados.

''' +content[end:]
 content=content.replace('4449/11; diagnóstico445 preparado','445 rechazado; diagnóstico446 preparado').replace('No editar fuente durante445.','No editar fuente durante446.')
 path.write_text(content,encoding='utf-8',newline='\n')
path=base/'RELEVO_ACTIVO.json';record=json.loads(path.read_text(encoding='utf-8-sig'))
record.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),continuation='445 base loses3names, rejected.446 published444 plus typed redaction443 only3targets/8normal identical, prepared. Source436 unchanged/fullgoalactive; owner18 saved.')
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
path=base/'ESTADO_PARA_DUENO_2026-09-08.md';content=path.read_text(encoding='utf-8').replace('tus17 mensajes','tus18 mensajes')
start=content.index('La prueba438');end=content.index('## Qué falta',start)
content=content[:start]+'''Las pruebas438–443 no dieron una corrección segura: se descartaron cambios que
intercambiaban errores. Qwen9B también falló y costó más RAM. Gemma publicado444
resolvió los ocho casos básicos con1,65GiB de VRAM y2,75GiB de RAM **en el
diagnóstico del modelo**, pero falló dos casos protegidos. Su base445 volvió a
fallar los nombres.446 contrasta representación de datos ocultos con ese
Gemma publicado; aún no se ha promovido modelo ni cambiado la fuente436.
Estos consumos nativos no son directamente el consumo de BAXY entero.

''' +content[end:]
path.write_text(content,encoding='utf-8',newline='\n')
print('445 recorded;446 prepared; owner report current')
