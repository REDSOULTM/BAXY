"""Record semantic review and test history representation rather than more wording."""
from datetime import datetime,timezone
import ast,collections,hashlib,json,os,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# Apply the identity's existing criterion: a simple explanation need not exhaust
# every valid sense. Preserve the first adjudication; do not hide its correction.
folder=base/'astra-audio-mind508';campaign=base/'astra-chat-profile508'
shutil.copy2(folder/'ADJUDICATION.json',folder/'ADJUDICATION-v1.json')
adj=json.loads((folder/'ADJUDICATION.json').read_text(encoding='utf-8-sig'))
for r in adj:
 if r['id'] in ['definition-es-registered-17','definition-es-qwen_documented-17']:
  r['useful']=True
  r['reason']='Semantic review: describes a valid unmute sense (sound output/voice or chat delivery); a simple definition need not list microphone, speaker and feed senses. No observed device effect is claimed. Earlier blanket rejection of listener/output wording was too strict.'
write(folder/'ADJUDICATION.json',adj)
shutil.copy2(campaign/'RESULT.json',campaign/'RESULT-v1.json')
shutil.copy2(campaign/'RESULT.md',campaign/'RESULT-v1.md')
r=json.loads((campaign/'RESULT.json').read_text(encoding='utf-8-sig'))
r['useful_per_profile_seed']='registered:5/7 seed0,6/7 seed17; Qwen-documented:5/7 seed0,6/7 seed17'
r['semantic_review']='v2: count valid output/listener and voice/chat senses without demanding exhaustive definitions; no profile advantage and recall-en still wrong in every arm. See ADJUDICATION-v1.json and RESULT-v1.* for original judgement.'
write(campaign/'RESULT.json',r)
s=(campaign/'RESULT.md').read_text(encoding='utf-8-sig').replace('Los dos perfiles y ambas semillas quedaron en5/7 respuestas útiles.','Revisión semántica v2: ambos perfiles obtienen5/7 con semilla0 y6/7 con semilla17. Una definición válida sobre salida de audio/voz no tiene que enumerar todos los sentidos; el rechazo anterior era demasiado estricto. Se conservan RESULT-v1 y ADJUDICATION-v1. No cambia la comparación entre perfiles ni el fallo de recuerdo.')
(campaign/'RESULT.md').write_text(s,encoding='utf-8')
for p in [folder,campaign]:write(p/'PINS.json',{f.name:sha(f) for f in p.iterdir() if f.is_file() and f.name!='PINS.json'})

out=base/'astra-audio-mind509';campaign=base/'astra-chat-provenance509'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-audio-mind509-private'
effective=[json.loads(s) for s in (private/'effective-chat-profile.jsonl').open(encoding='utf-8-sig')]
assert len(effective)==44 and len({r['case'] for r in effective})==44
policy=json.loads((campaign/'PREREG.json').read_text(encoding='utf-8-sig'))['policy']
for r in effective:
 before,after=r['before'],r['after']
 expected=dict(before,**r['profile']['sampling'])
 if r['profile']['provenance']:
  expected['messages']=[dict(m) for m in before['messages']]
  expected['messages'][0]['content']+=' '+policy
 assert after==expected
rows=[json.loads(s) for s in (out/'replies.jsonl').open(encoding='utf-8-sig')]
assert len(rows)==44
for r in rows:
 assert not r['reply']['effectOperations']
 r['useful']=not r['id'].startswith('recall-en-') and r['id']!='definition-es-original_policy-0'
 r['reason']='Repeats assistant Morgan over user Jordan.' if r['id'].startswith('recall-en-') else 'Unmuting permits speech; the example incorrectly equates it with actually starting to speak.' if r['id']=='definition-es-original_policy-0' else 'Useful factual answer; definitions may cover a valid sense without being exhaustive. Assistant-reference correctly recalls Morgan as what was said, not as a fact about the user.'
counts={key:sum(r['useful'] for r in rows if r['id'].endswith(key)) for key in ['original_policy-0','provenance-0','original_policy-17','provenance-17']}
assert counts=={'original_policy-0':9,'provenance-0':10,'original_policy-17':10,'provenance-17':10}
res=json.loads((out/'RESOURCES.json').read_text(encoding='utf-8-sig'));assert res['completed'] and res['manifest_unchanged'] and not res['violations']
http=[json.loads(s) for s in (private/'http-posts.jsonl').open(encoding='utf-8-sig')]
responses=[r['response'] for r in http if r['stage']=='response']
assert all(c.get('finish_reason')=='stop' for r in responses for c in r.get('choices',[]))
write(out/'ADJUDICATION.json',rows)
write(campaign/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'session':94766,'exit':0,'useful_out_of11':counts,'target_recall_en_correct':0,'target_recall_en_total':4,'effective_profile_policy_coverage':44,'http_responses':len(responses),'finish_reason':'all stop','resources':res,'decision':'Do not adopt the directive alone: it fails the target in both seeds; four added provenance/reference controls were already correct in the baseline. Definition variance is not evidence that the rule solved personal grounding. Next change representation, not another wording variant.'})
(campaign/'RESULT.md').write_text('''# Procedencia explícita con historial completo

Original9/11 y10/11; regla de procedencia10/11 en ambas semillas. El objetivo inequívoco, recordarJordan frente aMorgan escrito por el asistente, falla en los cuatro brazos. Los cuatro controles añadidos de corrección humana/otra persona/referencia al asistente ya pasaban antes; la nota provisional de que la regla los mejoraba queda corregida. No se incorpora la regla por sí sola ni se prueba otra redacción.

44/44generaciones auditadas: sólo el muestreo documentado común y la adición exacta al primer sistema diferencian los brazos.139respuestasHTTPstop, sin cortes. RAM1774,973/GPU3497,559MiB;94,157s;manifiesto intacto. Sesión94766exit0. Fuente506 permanece validada; ningún efecto/UI/voz/aceptación.

La adjudicación aplica la identidad vigente: una explicación breve no tiene que describir todos los sentidos de desmutear. Salida de audio/voz y lectura de un feed son sentidos válidos. Sí se rechaza afirmar que activar el micrófono implica que ya se está hablando. Fuentes concretas: https://support.microsoft.com/en-us/windows/hardware/audio/fix-sound-or-audio-problems-in-windows y https://help.x.com/en/using-x/x-mute.508 conserva adjudicación y resultado v1, con correcciónv2 de las definiciones de semilla17; ambos perfiles siguen empatados.

510 contrastará el historial como secuencia de turnos frente al mismo contenido y roles citados como datos. Ambos brazos mantienen la misma regla509 y perfilQwen. Ningún mensaje se borra ni se infiere el nombre esperado. La referencia a lo dicho por el asistente sigue siendo un control obligatorio. Base: contaminación por respuestas propias en https://arxiv.org/abs/2602.24287v2; la representación alternativa es una hipótesis local, no un resultado del paper.
''',encoding='utf-8')
for folder in [out,campaign]:write(folder/'PINS.json',{p.name:sha(p) for p in folder.iterdir() if p.is_file() and p.name!='PINS.json'})

nextout=base/'astra-chat-history510';nextout.mkdir(exist_ok=False)
prior=json.loads((campaign/'PREREG.json').read_text(encoding='utf-8-sig'))
panel=[{k:v for k,v in c.items() if k not in ['case_id','profile']} for c in prior['cases'][:11]]
for c,old in zip(panel,prior['cases'][:11]):c['id']=old['case_id']
profiles=[{'name':name,'seed':seed,'provenance':True,'quote_history':name=='quoted_history','sampling':{'temperature':.7,'top_p':.8,'top_k':20,'min_p':0.0,'presence_penalty':0.0,'repeat_penalty':1.0,'seed':seed}} for seed in [0,17] for name in ['message_history','quoted_history']]
expanded=[{**c,'id':c['id']+'-'+p['name']+'-'+str(p['seed']),'case_id':c['id'],'profile':p} for p in profiles for c in panel]
write(nextout/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cases':expanded,'profiles':profiles,'policy_common_to_both':policy,'method':'Same11cases and Qwen-documented sampler at seeds0/17. Both use exact509 provenance rule. Only treatment quotes prior dialogue as JSON data in one user message, retaining every literal role/content in order, while keeping all system messages and current user request unchanged. No names extracted, selected or injected. No history omission, new model call or source edit. Cases without prior dialogue receive identical payloads. Metadata key explicitly labels history as data, not instructions. Compare actual payloads/coverage; preserve assistant-reference control. This is a representation diagnostic, not deployment or acceptance.','heritage':['llm._dialogue_for_references_only in semantic counting already uses role-labelled historical data', 'https://arxiv.org/abs/2602.24287v2', 'astra-chat-provenance509 target0/4'], 'criteria':'Target recall-en must recover Jordan; ES/other-person/human correction correct; assistant-reference must still recover Morgan as previous words. Independent definitions/names unchanged in payload. No visible JSON, invented facts/effects or loss of context. If useful, source adoption still needs broader conversation owners and actual product regression.'})
script=(root/'scratchpad/c03-chat-provenance509.py').read_text(encoding='utf-8-sig').replace('509','510')
start=script.index('cases=');end=script.index('\nmanifest=',start)
script=script[:start]+'cases='+repr(expanded)+script[end:]
start=script.index("'method':");end=script.index("'profile_reason':",start)
script=script[:start]+"'method':'510: identical509 rule/profile; only history representation changes. See astra-chat-history510/PREREG.json for44cases and proof obligations.',"+script[end:]
lines=script.splitlines(True)
for i,line in enumerate(lines):
 if line.startswith('hook_source += '):
  hook=ast.literal_eval(line[len('hook_source += '):].strip())
  marker="        with (_private / 'effective-chat-profile.jsonl').open('a', encoding='utf-8') as _f:"
  addition="""        if _case['profile']['quote_history']:
            _current = payload['messages'][-1]
            _prior = [dict(m) for m in payload['messages'][:-1] if m.get('role') != 'system']
            if _prior:
                _systems = [dict(m) for m in payload['messages'][:-1] if m.get('role') == 'system']
                _data = {'conversation_history_as_data_not_instructions': _prior}
                payload['messages'] = _systems + [{'role':'user','content':_j.dumps(_data,ensure_ascii=False)}] + [_current]
"""
  assert marker in hook;hook=hook.replace(marker,addition+marker)
  lines[i]='hook_source += '+repr(hook)+'\n';break
else:raise AssertionError('No private hook')
target=root/'scratchpad/c03-chat-history510.py';assert not target.exists();target.write_text(''.join(lines),encoding='utf-8')
write(nextout/'PINS.json',{p.name:sha(p) for p in nextout.iterdir() if p.is_file() and p.name!='PINS.json'})
for name in ['CHECKPOINT.md','HANDOFF.md']:
 p=base/name;s=p.read_text(encoding='utf-8-sig');s+='\n509 cerrado94766exit0. Original9/11+10/11 vsregla10/11+10/11; recall-en falla4/4,controles añadidos ya pasaban antes. No adoptar regla ni otra redacción.508v2 corrige exceso de severidad:ambos5/7seed0 y6/7seed17,conserva v1.510PREREG/script listo:44casos,misma regla/perfil ambos, sólo historial citado comoJSON frente aturnos; conserva todosroles/literales y control sobre palabras del asistente. Ejecutar scratchpad/c03-chat-history510.py. Sin procesos activos ni fuente nueva;506sigue validada.\n';p.write_text(s,encoding='utf-8')
r=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'));r.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='509 cerrado, sin solución del recuerdo; fuente506 validada y sin procesos.',continuation='510 contrastar representación íntegra del historial con reglas/perfil idénticos; C03 activo.');write(base/'RELEVO_ACTIVO.json',r)
print('509 closed;508 semantic v2 retained;510 prepared44cases, source unchanged.')
