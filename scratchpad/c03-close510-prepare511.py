"""Close representation evidence and test one sampler factor on that new input."""
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out=base/'astra-audio-mind510';campaign=base/'astra-chat-history510'
private=Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-audio-mind510-private'
prereg=json.loads((campaign/'PREREG.json').read_text(encoding='utf-8-sig'))
effective=[json.loads(s) for s in (private/'effective-chat-profile.jsonl').open(encoding='utf-8-sig')]
assert len(effective)==44 and len({r['case'] for r in effective})==44
for r in effective:
 before,after=r['before'],r['after'];expected=dict(before,**r['profile']['sampling'])
 expected['messages']=[dict(m) for m in before['messages']]
 expected['messages'][0]['content']+=' '+prereg['policy_common_to_both']
 old=expected['messages'];prior=[m for m in old[:-1] if m['role']!='system']
 if r['profile']['quote_history'] and prior:
  expected['messages']=[m for m in old[:-1] if m['role']=='system']+[{'role':'user','content':json.dumps({'conversation_history_as_data_not_instructions':prior},ensure_ascii=False)}]+[old[-1]]
 assert after==expected
 if r['profile']['quote_history'] and prior:
  recovered=json.loads(after['messages'][-2]['content'])['conversation_history_as_data_not_instructions']
  assert recovered==prior
rows=[json.loads(s) for s in (out/'replies.jsonl').open(encoding='utf-8-sig')]
for r in rows:
 assert not r['reply']['effectOperations']
 r['useful']=not (r['id'].startswith('recall-en-message_history') or r['id']=='other-person-quoted_history-0')
 r['reason']='Wrong assistant-authored name.' if r['id'].startswith('recall-en-message_history') else 'Correct fact, but visible self-correction/reasoning, redundant answer and stage-like aside; not natural user-facing response.' if r['id']=='other-person-quoted_history-0' else 'Useful faithful response; all quoted history and authors retained; no effects.'
counts={key:sum(r['useful'] for r in rows if r['id'].endswith(key)) for key in ['message_history-0','quoted_history-0','message_history-17','quoted_history-17']}
assert counts=={'message_history-0':10,'quoted_history-0':10,'message_history-17':10,'quoted_history-17':11}
res=json.loads((out/'RESOURCES.json').read_text(encoding='utf-8-sig'));assert res['completed'] and res['manifest_unchanged'] and not res['violations']
write(out/'ADJUDICATION.json',rows)
write(campaign/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'session':61160,'exit':0,'useful_out_of11':counts,'target_recall_en':'0/2 message history;2/2 quoted history','coverage':44,'history_literal_roundtrip':True,'resources':res,'decision':'History representation corrects the target without deleting any authors/content and preserves assistant-reference. One treatment answer leaks an internal self-correction. Do not adopt as fully green yet; test T0 with every other documented sampler field and the new representation fixed. This revisits sampling only because the model input mechanism changed, not a blind sweep.'})
(campaign/'RESULT.md').write_text('''# El mismo historial citado como datos

La representación citada recuperaJordan en ambas semillas frente aMorgan erróneo en ambos controles. También recuperaMorgan cuando se pregunta qué había dicho el asistente, y conserva correcciones humanas, otra persona y nombres enES/EN. Cada rol y literal del historial hace roundtrip idéntico en44/44payloads auditados; no se extrajo ni se inyectó un nombre correcto.

Política común509 y perfilQwenidénticos. Original10/11+10/11; citado10/11+11/11. La excepción citada0 entregaOlivia, pero añade un aparte de autocorrección y repite la respuesta: no se aprueba su presentación. No se incorpora aún a fuente. No hubo corte o efecto físico acreditado. RAM1772,762/GPU3497,559MiB;94,344s;registro intacto;sesión61160exit0.

511 cambia únicamente temperatura0,7→0 sobre el nuevo payload citado, manteniendo top-p0,8/k20/min0/presence0/repeat1 ysemillas0/17. Los mensajes efectivos deben coincidir con510 antes de atribuir cualquier mejora al perfil. El input ha cambiado, por eso esta comparación aporta evidencia nueva después de508; no se reabre un barrido de valores.
''',encoding='utf-8')
for folder in [out,campaign]:write(folder/'PINS.json',{p.name:sha(p) for p in folder.iterdir() if p.is_file() and p.name!='PINS.json'})
nextout=base/'astra-chat-history-greedy511';nextout.mkdir(exist_ok=False)
cases=[]
for c in prereg['cases']:
 if not c['profile']['quote_history']:continue
 profile={**c['profile'],'name':'greedy_quoted','sampling':{**c['profile']['sampling'],'temperature':0.0}}
 cases.append({**c,'id':c['case_id']+'-greedy_quoted-'+str(profile['seed']),'profile':profile})
assert len(cases)==22
write(nextout/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'cases':cases,'method':'Same source506/private representation510, policy509, exact11cases andseeds0/17. Only temperature changes0.7 to0 relative to matching510quoted payloads; all other effective sampler fields remain documented values. Audit message/template/output-limit equality against510, actual generation coverage, complete output/EOS, source/manifest hashes and resources. No new prompt, metadata key, name rule, source or model.','criteria':'Resolve English wrong-speaker recall, preserve every useful control and assistant-reference, remove the observed self-correction aside without introducing another failure. Do not count source adoption or C03 acceptance from this diagnostic alone. If not green, no further temperature sweep.'})
script=(root/'scratchpad/c03-chat-history510.py').read_text(encoding='utf-8-sig').replace('510','511')
start=script.index('cases=');end=script.index('\nmanifest=',start)
script=script[:start]+'cases='+repr(cases)+script[end:]
start=script.index("'method':");end=script.index("'profile_reason':",start)
script=script[:start]+"'method':'511:temperature0 only on exact510quoted payloads; see astra-chat-history-greedy511/PREREG.json.22cases.',"+script[end:]
target=root/'scratchpad/c03-chat-history-greedy511.py';assert not target.exists();target.write_text(script,encoding='utf-8')
write(nextout/'PINS.json',{p.name:sha(p) for p in nextout.iterdir() if p.is_file() and p.name!='PINS.json'})
for name in ['CHECKPOINT.md','HANDOFF.md']:
 p=base/name;s=p.read_text(encoding='utf-8-sig');s+='\n510 cerrado61160exit0:citando historial se corrigeJordan2/2 y se conservaMorgancomo palabras del asistente.44/44payloads conroles/literales íntegros.Original10/11+10/11,citado10/11+11/11;other-personseed0 añadeasideinterno. No fuente adoptada.511PREREG/script listo:22casos,cambia sóloT.7→0sobreel nuevo input,restoigual; cotejarpayloads510. Ejecutar scratchpad/c03-chat-history-greedy511.py. Fuente506 siguevalidada;sinprocesosactivos.\n';p.write_text(s,encoding='utf-8')
r=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'));r.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='510 cerrado con mejora de procedencia y un defecto de presentación; fuente506 validada; sin procesos.',continuation='511 único cambioT0 sobre historial citado para fijar perfil; no más barrido si falla. C03 activo.');write(base/'RELEVO_ACTIVO.json',r)
print('510 closed;511 prepared22 matched cases; source still506.')
