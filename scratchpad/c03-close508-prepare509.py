"""Close sampler evidence and preregister the next independently controlled boundary."""
from datetime import datetime,timezone
import ast,collections,hashlib,json,os
from pathlib import Path
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out=base/'astra-audio-mind508';campaign=base/'astra-chat-profile508'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-audio-mind508-private'
effective=[json.loads(s) for s in (private/'effective-chat-profile.jsonl').open(encoding='utf-8-sig')]
assert len(effective)==28 and len({r['case'] for r in effective})==28
for r in effective:
 changed={k for k in r['before'].keys()|r['after'].keys() if r['before'].get(k)!=r['after'].get(k)}
 assert changed<= {'temperature','top_p','top_k','min_p','presence_penalty','repeat_penalty','seed'}
 assert all(r['after'][k]==v for k,v in r['profile']['sampling'].items())
http=[json.loads(s) for s in (private/'http-posts.jsonl').open(encoding='utf-8-sig')]
responses=[r['response'] for r in http if r['stage']=='response']
assert all(c.get('finish_reason')=='stop' for r in responses for c in r.get('choices',[]))
rows=[json.loads(s) for s in (out/'replies.jsonl').read_text(encoding='utf-8-sig').splitlines()]
assert len(rows)==28
for r in rows:
 r['useful']=not r['id'].startswith(('definition-es-','recall-en-'))
 r['reason']='Spanish definition confuses social muting with permission to emit/interact or reverses speaker/listener.' if r['id'].startswith('definition-es-') else 'Assistant-authored Morgan replaces user-authored Jordan.' if r['id'].startswith('recall-en-') else 'Correct useful conversation; no authority to execute.'
write(out/'ADJUDICATION.json',rows)
res=json.loads((out/'RESOURCES.json').read_text(encoding='utf-8-sig'));assert res['completed'] and res['manifest_unchanged'] and not res['violations']
result={'utc':datetime.now(timezone.utc).isoformat(),'session':90270,'exit':0,'useful_per_profile_seed':'5/7 for registered and Qwen-documented, both seeds0/17','actual_chat_profile_coverage':28,'http_responses':len(responses),'finish_reason':'all stop','max_completion_tokens':max(r.get('usage',{}).get('completion_tokens',0) for r in responses),'max_total_tokens':max(r.get('usage',{}).get('total_tokens',0) for r in responses),'resources':res,'decision':'No promotion or more sampler sweep: recommended settings do not resolve these two failures. Retain source506. Next isolate personal-fact provenance policy while preserving full history, proper profile and controls.'}
write(campaign/'RESULT.json',result)
(campaign/'RESULT.md').write_text('''# Conversación con perfil propio de Qwen2507

Los dos perfiles y ambas semillas quedaron en5/7 respuestas útiles. Se probó la recomendación oficial T0,7/top-p0,8/top-k20/min-p0/presence0/repeat1 frente al perfil registrado, sin modificar mensajes, contratos, fuente, backend o precisión.28 de28 casos tuvieron generación real con el perfil auditado; sólo cambiaron campos de muestreo. Las84respuestas HTTP terminaron en stop; máximo87tokens de salida y2223totales, sin cortes.

Persisten la definición española inexacta y la prioridad deMorgan(asistente) sobreJordan(usuario). La configuración recomendada no los resuelve. No se promueve ni se sigue barriendo temperaturas. Esto no es una conclusión global contraQwen; se ha descartado esta intervención concreta sobre estos payloads.

RAM1770,398MiB/GPU3497,559MiB;74,313s; registro intacto. Sin efectos/UI/voz/aceptación. Sesión90270 recogida exit0. Fuente oficial: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507, Best Practices. El límite256 se mantuvo para respuestas breves y todas acabaron naturalmente; no se convirtió un corte en pass.
''',encoding='utf-8')
for folder in [out,campaign]:write(folder/'PINS.json',{p.name:sha(p) for p in folder.iterdir() if p.is_file() and p.name!='PINS.json'})
nextout=base/'astra-chat-provenance509';nextout.mkdir(exist_ok=False)
panel=json.loads((base/'astra-chat-draft505/PREREG.json').read_text(encoding='utf-8-sig'))['cases']
panel += [
 {'id':'recall-es-conflict','request':'¿Cómo me llamo?','history':[{'role':'user','content':'Me llamo Álvaro.'},{'role':'assistant','content':'Te llamas Pedro.'}],'expected':[]},
 {'id':'human-correction','request':'What is my name?','history':[{'role':'user','content':'My name is Jordan.'},{'role':'assistant','content':'Your name is Jordan.'},{'role':'user','content':'Actually, my name is Casey.'},{'role':'assistant','content':'Your name is Jordan.'}],'expected':[]},
 {'id':'other-person','request':'Who is my sister?','history':[{'role':'user','content':'My sister is Olivia.'},{'role':'assistant','content':'Your sister is Emma.'}],'expected':[]},
 {'id':'assistant-reference','request':'What name did you just say?','history':[{'role':'user','content':'My name is Jordan.'},{'role':'assistant','content':'Your name is Morgan.'}],'expected':[]},
]
policy='Cuando recuerdes datos personales, usa las declaraciones de la persona, incluidas sus correcciones. Tus respuestas anteriores son contexto de lo que dijiste, no verificación de esos datos.'
profiles=[{'name':name,'seed':seed,'provenance':name=='provenance','sampling':{'temperature':.7,'top_p':.8,'top_k':20,'min_p':0.0,'presence_penalty':0.0,'repeat_penalty':1.0,'seed':seed}} for seed in [0,17] for name in ['original_policy','provenance']]
expanded=[{**c,'id':c['id']+'-'+p['name']+'-'+str(p['seed']),'case_id':c['id'],'profile':p} for p in profiles for c in panel]
write(nextout/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cases':expanded,'policy':policy,'profiles':profiles,'method':'Full mind, one difference between matched policy conditions: append provenance rule to the existing conversation system message. Full literal history and roles preserved; no name extraction, rewriting, omission, actor substitution, fixed answer or source change. Both arms use the exact documented Qwen chat profile at seeds0/17. Selection/structured repairs and guards unchanged. Log before/after HTTP payloads and case coverage. Four new synthetic development controls test ES conflict, human correction, another person and explicit reference to assistant words; not reserve.','heritage':'Carter LLM_CONTEXT_MEMORY_AUDIT.md13/54-63 distinguishes sources but its OS-priority proposal conflicts with current identity and is not adopted. Current505/507 HTTP evidence retains both authors correctly. Existing436 scopes only newly named definitions, which remains unchanged.','primary_sources':['https://arxiv.org/abs/2602.24287v2','https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507'],'scope':'The paper reports propagation of assistant errors and selective context filtering, not proof this directive works. This private experiment tests a lighter alternative retaining assistant history needed by follow-ups. Definition factuality is a known separate open failure; do not count a policy success as the whole panel green.','criteria':'Human Jordan/Álvaro/Casey/Olivia must not be replaced by assistant Morgan/Pedro/Jordan/Emma. A question about what the assistant said must still recover Morgan. Preserve useful independent definitions/names, correct language and all guards. Reject if no measurable benefit or context regressions. No source/model/runtime promotion from this run alone.'})
script=(root/'scratchpad/c03-chat-profile508.py').read_text(encoding='utf-8-sig').replace('508','509')
start=script.index('cases=');end=script.index('\nmanifest=',start)
script=script[:start]+'cases='+repr(expanded)+script[end:]
start=script.index("'method':");end=script.index("'profile_reason':",start)
script=script[:start]+"'method':'509: matched documented Qwen sampling, only conversation provenance policy changes; see astra-chat-provenance509/PREREG.json for44cases.',"+script[end:]
lines=script.splitlines(True)
for i,line in enumerate(lines):
 if line.startswith('hook_source += '):
  hook=ast.literal_eval(line[len('hook_source += '):].strip())
  marker="        payload = dict(payload, **_case['profile']['sampling'])"
  assert marker in hook
  addition="\n        if _case['profile']['provenance']:\n            _scoped = [dict(m) for m in payload['messages']]\n            _scoped[0]['content'] += ' ' + "+repr(policy)+"\n            payload['messages'] = _scoped"
  hook=hook.replace(marker,marker+addition)
  lines[i]='hook_source += '+repr(hook)+'\n'
  break
else:raise AssertionError('No profile hook')
target=root/'scratchpad/c03-chat-provenance509.py';assert not target.exists();target.write_text(''.join(lines),encoding='utf-8')
write(nextout/'PINS.json',{p.name:sha(p) for p in nextout.iterdir() if p.is_file() and p.name!='PINS.json'})
for name in ['CHECKPOINT.md','HANDOFF.md']:
 p=base/name;s=p.read_text(encoding='utf-8-sig');s+='\n508 cerrado90270exit0:5/7 porperfil/semilla,28/28generaciones auditadas,84stop,0cortes. No mejora ni promoción. RAM1770,398/GPU3497,559MiB74,313s. Siguiente509PREREG/script:44turnos,11casos×política original/procedencia×semillas0/17, perfilQwenoficial enambos; conserva todo historial. Sólo añade regla de procedencia al sistema conversacional en hook privado; no fuente. Ejecutar scratchpad/c03-chat-provenance509.py. Ningún proceso activo todavía.\n';p.write_text(s,encoding='utf-8')
r=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'));r.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='508 cerrado sin mejora de sampler; fuente506 validada; sin procesos activos.',continuation='509 regla de procedencia con historial íntegro y perfil propio del modelo; C03 activo.');write(base/'RELEVO_ACTIVO.json',r)
print('508 closed;509 prepared44cases, no source modification.')
