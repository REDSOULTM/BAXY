"""Close the ineffective Qwen2507 writer profile; fairly revisit Qwen3.5-4B."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,os,re

root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out=base/'astra-native-compose-profile523';private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-native-compose-profile523-private'
rows=list(map(json.loads,(private/'responses.jsonl').open(encoding='utf-8-sig')));assert len(rows)==27
samplers=[]
for n,line in enumerate((private/'server.log').open(encoding='utf-8-sig',errors='replace'),1):
    if 'top_k = ' in line and 'temp = ' in line:samplers.append({'line':n,'parameters':line.strip()})
assert len(samplers)==27
settings=Counter('documented' if 'temp = 0.700' in r['parameters'] and 'top_k = 20' in r['parameters'] and 'top_p = 0.800' in r['parameters'] and 'min_p = 0.000' in r['parameters'] else 'registered' if 'temp = 0.000' in r['parameters'] else 'unexpected' for r in samplers)
assert settings=={'documented':18,'registered':9}
review=[]
for r in rows:
    choices=r.get('response',{}).get('choices',[])
    assert len(choices)==1 and choices[0]['finish_reason']=='stop'
    text=choices[0]['message']['content'];case=r['case']
    issue={'save-result':'Same internal correction/completion metadata narration with both profiles; critical target not repaired.','memory-capability-disabled':'Denies having local memory while the observed store exists but is disabled; critical target not repaired.','progress':'First-person verb but refers to the user in third person and asserts result absence from the progress instruction; no improvement.','enable-result':'Still a configuration/operation receipt, with redundant completion language; no improvement in voice.'}.get(case)
    if case=='enable-confirmation' and r['profile'].startswith('documented'):
        issue='Still asks a decision, but names a memory enable action with less clear private/local scope and internal phrasing; not a quality improvement.'
    review.append({'case':case,'profile':r['profile'],'text':text,'finish_reason':'stop','critical_target_fixed':False if case in {'save-result','memory-capability-disabled'} else None,'issue':issue,'control_result':None if issue else 'Factual useful control retained; acceptable variation in clarification. Captured clock is replayed evidence, not live time.','seconds':r['seconds'],'completion_tokens':r['response']['usage']['completion_tokens']})
write(out/'ADJUDICATION.json',{'rows':review,'effective_sampler_counts':dict(settings),'effective_sampler_log':samplers})
resources=json.loads((out/'RESOURCES.json').read_text(encoding='utf-8-sig'));assert resources['completed'] and resources['manifest_unchanged'] and not resources['violations']
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'session':99282,'script_exit':0,'native_responses':27,'all_finished_stop':True,'maximum_completion_tokens':max(r['completion_tokens'] for r in review),'effective_sampling_verified':dict(settings),'save_target_fixed':0,'save_target_attempts':3,'capability_target_fixed':0,'capability_target_attempts':3,'adopted':False,'resources':resources,'limits':'Native writer replay only, no guards/Core/product/voice/UI or actual clock reading. Captured facts retained. Driver intentionally terminates owned server after collection (server exit15, not a generation failure). No global model incapacity conclusion from these controls.','next':'Try Qwen3.5-4B with its documented non-thinking profile and compatible previously evaluated b10865. Include its old private-name speaker failure as two additional exact521 payloads. No more Qwen2507 sampler/wording sweep without a new mechanism.'})
(out/'RESULT.md').write_text('''# Perfil documentado de Qwen2507 para el redactor

Se recogieron27 respuestas nativas: nueve payloads exactos521 con el perfil registrado y la receta documentada a semillas0/17. Las27 terminaron por EOS, sin cortes. El log de llama.cpp acredita9 llamadas a temperatura0 y18 a0,7/top_p0,8/top_k20/min_p0; no se presume aplicación sólo porque HTTP devolvió200.

Guardado y capacidad siguen fallando con los tres perfiles: el primero conserva prosa de metadatos y el segundo niega tener memoria local al verla desactivada. Progreso conserva la referencia al usuario y la ausencia de resultados. La aclaración admite variaciones válidas y la deshabilitación conserva la corrección520. No se adopta el perfil ni se inicia otro barrido de palabras o temperaturas.

RAM720,629MiB/GPU3497,559MiB10,921s sólo del servidor y descendientes, no de BAXY completo. Registro intacto, sin violaciones; driver99282exit0, servidor terminado deliberadamente al recoger todo. No son casos frescos ni prueba de UI/voz.

524 retoma Qwen3.5-4B porque437 usó el perfil determinista genérico y el código de composición anterior. Ahora se comparará con su receta oficial no pensante, conservando sus controles de nombre que entonces fallaron. La revisión usa backend compatibleb10865 y no modifica el registro. Es una comparación por candidato, no obligación de darle parámetros idénticos a Qwen2507.
''',encoding='utf-8')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
script=(root/'scratchpad/c03-native-compose-profile523.py').read_text(encoding='utf-8-sig').replace('523','524')
script=script.replace('Qwen sampling.','Qwen3.5 sampling.').replace("assert len(cases)==9", "assert len(cases)==11")
script=script.replace("6:'app-clarification',12:'progress'", "6:'app-clarification',7:'stored-name-en',11:'stored-name-es',12:'progress'")
point="command=json.loads((previous/'effective-server-command.json').read_text(encoding='utf-8-sig'))"
script=script.replace(point,point+"\ncommand[0]='D:/BAXYRuntime/assets/llama-b10865-cuda12.4/llama-server.exe'\ncommand[command.index('-m')+1]='D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf'")
script=script.replace('38a9d28ea414442590486459a7d1f5e32655db83148b7a114b79cd1ad242946e','16eac28198d6218a9892f08dac0f0c81612a72872b4dd9741c4c6c36f88c4fd7')
script=script.replace('3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597','00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4')
script=script.replace('registered-seed0','production-greedy-seed0').replace("'presence_penalty':0.0", "'presence_penalty':1.5")
start=script.index("write(out/'PREREG.json',");end=script.index("\nwrite(private/'cases.json'",start)
script=script[:start]+'''write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'method':'Eleven exact captured521 writer payloads: nine523 cases plus both protected stored-name controls associated with the old437 wrong-speaker failure. Qwen3.5-4B Q4, compatible b10865; compare generic production greedy with its official non-thinking profile at seeds0/17. No prompt/data/output edits or Core effects.','source':'https://huggingface.co/Qwen/Qwen3.5-4B','profile_rationale':'Qwen3.5 non-thinking general tasks: temperature0.7,top_p0.8,top_k20,min_p0,presence_penalty1.5,neutral repetition1. Greedy is the existing composition baseline, not claimed to be optimal. Explicit enable_thinking=false and server reasoning off retained. Max256 for brief native replies, every length finish is a failure.','profiles':profiles,'cases':[{'id':c['id'],'case':c['case'],'payload_sha256':hashlib.sha256(json.dumps(c['payload'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()} for c in cases],'criteria':'Review all outputs for fact/cause/decision/language/voice. Save metadata and disabled-capability errors must improve; both stored-name results must keep the human subject and literal value. Read-only clock, disable, clarification, progress and confirmation remain controls. No success just from one fluent sample orHTTP200. No promotion before full path and guards.','server_command':command,'model_sha256':sha(command[command.index('-m')+1]),'server_sha256':sha(command[0]),'manifest_sha256':manifest_sha,'capture_sha256':sha(previous/'http-posts.jsonl'),'limits':{'gpu_stop_mib':3800,'free_ram_mib':768,'total_seconds':360,'request_seconds':60},'exclusions':'All consumed synthetic development; no fresh acceptance, physicalUI/voice or global model ranking. Same local resources ceiling, but model and compatible backend deliberately differ from523. Compare common9 separately; extra2 recover known Qwen3.5 defect. No blind replay of437: native composition payload/source520 and per-model sampling now tested.'})''' +script[end:]
script=script.replace('27 native writer requests','33 native writer requests')
target=root/'scratchpad/c03-native-compose-profile524.py';assert not target.exists();target.write_text(script,encoding='utf-8')
note='\n523 cerrado99282script exit0:27nativeEOS, muestreo efectivo9greedy/18documentado acreditado. Guardado0/3 ycapacidad0/3 reparados; progreso/metanarraciónsiguen. No adopción. RAM720,629/GPU3497,559MiB10,921s sólo servidor.524 preparado: Qwen3.5-4B,b10865,11payloads521(nueve523+dosnombres del fallo437), greedy/recetaoficialno-thinking seeds0/17,presencia1,5. No source/registrocambiados; ejecutar unaGPU, comprobar sampler ycalidad de33salidas.\n'
for name in ['CHECKPOINT.md','HANDOFF.md']:
    with (base/name).open('a',encoding='utf-8') as f:f.write(note)
rp=base/'RELEVO_ACTIVO.json';r=json.loads(rp.read_text(encoding='utf-8-sig'));r.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='520 validado/521producto9/11;523perfilQwen2507 cerrado sin adopción;524 preparado.',continuation='Ejecutar524 Qwen3.5-4B con receta propia y controles del fallo antiguo. No repetir Qwen2507 sin mecanismo nuevo. C03 activo, reserva y pruebas reales pendientes.');write(rp,r)
print('523 closed,524 prepared; source520 and runtime registration unchanged.')
