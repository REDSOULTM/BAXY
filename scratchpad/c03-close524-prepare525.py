"""Record Qwen3.5 controls and isolate re-interpretation of already resolved reads."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,os

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out=base/'astra-native-compose-profile524';private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-native-compose-profile524-private'
rows=list(map(json.loads,(private/'responses.jsonl').open(encoding='utf-8-sig')));assert len(rows)==33
review=[]
for r in rows:
    c=r.get('response',{}).get('choices',[]);assert len(c)==1 and c[0]['finish_reason']=='stop'
    issue=None
    if r['case']=='stored-name-es':issue='Answers as the assistant identity instead of reporting the stored entry; documented seed0 also replaces Jordan with BAXY.'
    elif r['case']=='memory-capability-disabled':issue='Denies local memory capability despite an existing disabled store; documented replies invent broader reset/no-persistence claims.'
    elif r['case']=='enable-confirmation' and r['profile']=='documented-seed0':issue='Claims already enabled before asking the pending confirmation.'
    elif r['case']=='disable-result' and r['profile']=='documented-seed17':issue='Adds private-data playback claim not observed; replayed=false is protocol metadata, not playback.'
    review.append({'case':r['case'],'profile':r['profile'],'text':c[0]['message']['content'],'useful_native':issue is None,'issue':issue,'finish_reason':'stop','completion_tokens':r['response']['usage']['completion_tokens'],'seconds':r['seconds']})
samplers=[{'line':n,'parameters':line.strip()} for n,line in enumerate((private/'server.log').open(encoding='utf-8-sig',errors='replace'),1) if 'top_k = ' in line and 'temp = ' in line]
assert len(samplers)==33
counts=Counter('documented' if 'temp = 0.700' in r['parameters'] and 'top_k = 20' in r['parameters'] and 'top_p = 0.800' in r['parameters'] and 'min_p = 0.000' in r['parameters'] else 'greedy' if 'temp = 0.000' in r['parameters'] else 'unexpected' for r in samplers);assert counts=={'documented':22,'greedy':11}
profile_counts={p:sum(r['useful_native'] for r in review if r['profile']==p) for p in {r['profile'] for r in review}}
resources=json.loads((out/'RESOURCES.json').read_text(encoding='utf-8-sig'));assert resources['completed'] and resources['manifest_unchanged'] and not resources['violations']
write(out/'ADJUDICATION.json',{'rows':review,'effective_samplers':samplers})
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'session':78100,'script_exit':0,'responses':33,'finish_stop':33,'native_useful_by_profile':profile_counts,'denominator_per_profile':11,'resources':resources,'adopted':False,'findings':'Qwen3.5 produces useful save/progress with all profiles. Stored-name ES and disabled-memory capability fail with all three. Documented seed0 falsely completes enable before consent; seed17 invents private playback in disable. Greedy is best observed here (9/11), after testing a proper documented profile rather than assuming defaults are optimal.','limits':'Native only, no full guard/product path, physical UI/voice, acceptance or global optimum. Captured clock from521 is static test evidence. Existing memory ES subject issue437 explicitly rechecked, not hidden.','next':'525 tests omission of the already resolved raw question for only completed memory read results, preserving exact returned records/status and language/output contracts. No schema additions, prompt wording sweep, output edits or source adoption yet.'})
(out/'RESULT.md').write_text('''# Qwen3.5-4B: mejor redacción, dos fallos de lectura pendientes

33 salidas nativas por EOS. Greedy9/11 útiles; receta documentada8/11 en cada semilla0/17. Se conservaron el error, la decisión, la lectura, la hora y los dos controles de nombre del fallo437. El log acredita11 muestreos greedy y22 documentados. El perfil recomendado no garantiza mejor resultado: una muestra confirma un efecto antes del consentimiento y otra confunde replayed=false con reproducción de datos privados.

El guardado y el progreso se expresan de manera útil con los tres perfiles. Pero la pregunta española de nombre almacenado se convierte en identidad del asistente, y la pregunta de capacidad produce negación de tener memoria. Ambos nacen ya en el modelo nativo. Los datos son lecturas resueltas por el flujo privado; la pregunta natural vuelve a inducir otra interpretación del sujeto o de la capacidad.525 comparará omitir sólo esa pregunta redundante del generador de esas lecturas, conservando datos, idioma y contratos. No modifica preguntas abiertas, decisiones, efectos ni la petición usada por el producto para elegir la operación.

RAM1124,449MiB/GPU3174,539MiB16,469s sólo servidor. Sin violaciones y registro intacto. Sesión78100exit0; servidor terminado deliberadamente al acabar. No promoción, UI/voz ni aceptación fresca. El perfil greedy se considera por sus mediciones frente al recomendado, no por ser el default.
''',encoding='utf-8')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
script=(root/'scratchpad/c03-native-compose-profile524.py').read_text(encoding='utf-8-sig').replace('524','525')
start=script.index('ids={');end=script.index('\nrows=',start)
script=script[:start]+"ids={7:'stored-name-en',11:'stored-name-es',19:'memory-capability-disabled'}"+script[end:]
script=script.replace('assert len(cases)==11','assert len(cases)==3')
point="write(private/'cases.json',cases)"
treatment='''
original_cases=copy.deepcopy(cases)
for case in cases:
    messages=case['payload']['messages']
    assert len(messages)==2 and messages[-1]['role']=='user'
    content=messages[-1]['content'];request,separator,rest=content.partition('\\n')
    assert separator and rest.startswith('situation: ')
    situation=json.loads(rest.splitlines()[0].removeprefix('situation: '))
    assert situation.get('kind')=='status' and situation.get('outcome')=='completed'
    assert situation.get('operation') in {'memory.recall','memory.status'}
    messages[-1]['content']=rest
    append(private/'input-treatment.jsonl',{'case':case['case'],'removed_raw_question':request,'situation_unchanged':True,'before_sha256':hashlib.sha256(content.encode()).hexdigest(),'after_sha256':hashlib.sha256(rest.encode()).hexdigest()})
write(private/'original-cases.json',original_cases)
'''
script=script.replace(point,treatment+'\n'+point)
start=script.index("write(out/'PREREG.json',");end=script.index('\noriginal_cases=',start)
script=script[:start]+'''write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cause':'524 exact resolved private reads are reinterpreted as assistant identity or generic chatbot memory capability. _compose_user_content already separates request from situation/language; its existing include_request control can scope generation without changing the real input used for routing/guards. Prior code comment about account-read identity warns against broad changes: this test is only memory.recall/status completed data, not account queries or welcome.','method':'Three original524 payloads, same Qwen3.5/b10865 and three sampling profiles. Remove only the first raw natural-question line before situation, retaining all system text, JSON fields and values, language and literal contracts. No replacement words, role/provenance guesses, value extraction, output editing or source changes. Compare each of9responses against its exact524 baseline counterpart.','profiles':profiles,'sources':['https://huggingface.co/Qwen/Qwen3.5-4B','src/baxy_mind/llm.py:_compose_user_content','524 exact payloads and responses'],'criteria':'Stored EN/ES entry must report Jordan without claiming it is the assistant identity; disabled store must be described from observed facts without false loss of capability, erasure, playback or resets. Preserve explicit language and literal data. Any promising change needs bounded source guards, preservation of original request/readers/format requirements, and full product before adoption. No general deletion of user requests.','server_command':command,'model_sha256':sha(command[command.index('-m')+1]),'server_sha256':sha(command[0]),'manifest_sha256':manifest_sha,'capture_sha256':sha(previous/'http-posts.jsonl'),'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60},'exclusions':'Native consumed synthetic data only. No actual status/effects, source/runtime promotion, physicalUI/voice or acceptance. Native prototype removes one known frame line; production, if adopted, must operate on typed composition inputs.'})
''' +script[end:]
script=script.replace('33 native writer requests','9 native writer requests')
target=root/'scratchpad/c03-native-compose-profile525.py';assert not target.exists();target.write_text(script,encoding='utf-8')
note='\n524 cerrado78100exit0:33EOS, Qwen3.5greedy9/11 vsdocumentado8/11cada seed. Guardado/progreso mejoran; lecturaESnombreycapacidadfallan3/3;documentadoañadeprematuroenable(seed0)/reproduccióninventada(seed17). RAM1124,449/GPU3174,539MiB16,469s sólo servidor.525 preparado: treslecturasprivadasresueltas × mismos3perfiles, únicamenteomitirpreguntanatural redundante; conservarJSON/idioma/contratos. No borrarcuentas/bienvenidas/pedidosabiertos ni adoptarfuentetodavía.\n'
for name in ['CHECKPOINT.md','HANDOFF.md']:
    with (base/name).open('a',encoding='utf-8') as f:f.write(note)
rp=base/'RELEVO_ACTIVO.json';r=json.loads(rp.read_text(encoding='utf-8-sig'));r.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='524 cerrado9/11greedy8/11doc, no promoción; fuente520/C#516 validadas.',continuation='525 probar marco de lecturas ya resueltas,9nativos. Respetar cuenta/welcome/idioma/formatos antes de eventual fuente. C03 íntegro activo.');write(rp,r)
print('524 closed;525 prepared, no source or runtime registration changes.')
