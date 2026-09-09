"""Record the integrated panel and isolate documented sampling in conversation."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out=base/'astra-audio-mind507'
prereg=json.loads((out/'PREREG.json').read_text(encoding='utf-8-sig'))
cases={c['id']:c for c in prereg['cases']}
rows=[json.loads(s) for s in (out/'replies.jsonl').read_text(encoding='utf-8-sig').splitlines()]
bindings=[json.loads(s) for s in (out/'bindings.jsonl').read_text(encoding='utf-8-sig').splitlines()]
assert len(rows)==20 and len(bindings)==11
for r in rows:
 assert r['reply']['effectOperations']==cases[r['id']]['expected']
 r['useful']=r['id'] not in ['word-meaning','recall-en']
 r['reason']={'word-meaning':'Internal selector wording removed; social-mute explanation still reverses who hears messages.','recall-en':'Assistant-authored Morgan is repeated over user-authored Jordan.'}.get(r['id'],'Correct proposal/clarification or factual conversation; no effect execution credit.')
for b in bindings:
 r=b['reply'];c=cases[b['id']]
 if b['type']=='plan':
  assert [s['operation'] for s in r['steps']]==c['expected']
  args={k:v for step in r['steps'] for k,v in step['arguments'].items()}
 else:
  assert r['ok'];args=r['arguments']
 assert args==c['arguments']
resources=json.loads((out/'RESOURCES.json').read_text(encoding='utf-8-sig'))
assert resources['completed'] and resources['manifest_unchanged'] and not resources['violations']
write(out/'ADJUDICATION.json',rows)
write(out/'RESULT.json',{'session':15347,'exit':0,'useful':18,'total':20,'bindings_correct':11,'bindings':11,'resources':resources,'source':'effect_intent503,__main__506,llm506','limits':'Development mind only; no UI, provider effects, audio, voice or acceptance.'})
(out/'RESULT.md').write_text('''# Fuente506 en el protocolo real

18 de20 propuestas/aclaraciones o respuestas útiles y11 de11 bindings correctos. Se mantienen todas las selecciones de audio504. Owner46 selecciona desilenciar en0,031s; owner51 conserva volumen100+statefalse en0,407s de decisión. La fuente reproduce el tratamiento505: no prosa del selector y correcto actor deJordan. Persisten la definición social inexacta yMorgan tomado del asistente.

Sesión15347exit0;48,921s; RAM1778,320MiB/GPU3497,559MiB, sin violaciones, registro intacto. No efectos/UI/voz ni aceptación.508 contrastará sólo el sampler de conversación con la recomendación exacta del modelo y dos semillas, sin cambiar mensajes ni fuente.
''',encoding='utf-8')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
campaign=base/'astra-chat-profile508';campaign.mkdir(exist_ok=False)
panel=json.loads((base/'astra-chat-draft505/PREREG.json').read_text(encoding='utf-8-sig'))['cases']
profiles=[{'name':name,'seed':seed,'sampling':({'seed':seed} if name=='registered' else {'temperature':.7,'top_p':.8,'top_k':20,'min_p':0.0,'presence_penalty':0.0,'repeat_penalty':1.0,'seed':seed})} for seed in [0,17] for name in ['registered','qwen_documented']]
expanded=[{**c,'id':c['id']+'-'+p['name']+'-'+str(p['seed']),'case_id':c['id'],'profile':p} for p in profiles for c in panel]
write(campaign/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'model':'Qwen3-4B-Instruct-2507 Q4_K_M registered/b9980','source':'506','cases':expanded,'profiles':profiles,'source_url':'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507','method':'Same seven consumed cases, full mind with one process and explicit independent histories, two profiles at seeds0/17. A private hook changes only sampling on unstructured chat generation whose first system is exact SYSTEM_PROMPT. Selection, semantic classifier, structured repair, prompts, history, guards, backend, precision and memory parameters unchanged. The private driver sets profile only between completed requests; record before/after payloads and effective profile for every affected post. Verify actual profile coverage; a cached answer without a corresponding generation does not prove sampler quality.','output_limit':'Keep the existing256 tokens for brief answers to isolate sampling; inspect finish_reason/usage. Any length stop is failure, never silent truncation. Official16384 recommendation is not applied to these short requests inside the4096 slot; existing outputs ended naturally, so truncation is not the observed cause.','criteria':'Definition faithful, speaker attribution and user fact over wrong assistant fact correct, language natural; compare all controls and both seeds. No quality claim from empty operation selection, no optimization guarantee from recommendations, no default-only rejection. No source or runtime promotion; same4GiB ceiling.'})
script=(root/'scratchpad/c03-audio-mind504.py').read_text(encoding='utf-8-sig').replace('504','508')
start=script.index('cases=[');end=script.index('\nmanifest=',start)
script=script[:start]+'cases='+repr(expanded)+script[end:]
start=script.index("'method':");end=script.index("'profile_reason':",start)
script=script[:start]+"'method':'508: see astra-chat-profile508/PREREG.json for the exact28cases and paired chat-only sampling. No effects or model promotion.',"+script[end:]
start=script.index("'criteria':");end=script.index("'model':",start)
script=script[:start]+"'criteria':'Factual natural conversation and correct fact speaker across two seeds; actual HTTP profile coverage/EOS/resources required. No reserve, physical or acceptance credit.',"+script[end:]
hook='''
from baxy_mind.llm import LlmRuntime as _ChatProfileRuntime, SYSTEM_PROMPT as _ChatProfileSystem
_chat_profile_post = _ChatProfileRuntime._post
def _post_with_chat_profile(self, payload, *args, **kwargs):
    import json as _j
    from pathlib import Path as _P
    _private = _P(os.environ['LOCALAPPDATA']) / 'BAXY/C03-audio-mind508-private'
    _active = _private / 'active-profile.json'
    _messages = payload.get('messages', [])
    if (_active.exists() and _messages and _messages[0].get('content') == _ChatProfileSystem
            and not payload.get('response_format') and not payload.get('tools')):
        _case = _j.loads(_active.read_text(encoding='utf-8'))
        _before = payload
        payload = dict(payload, **_case['profile']['sampling'])
        with (_private / 'effective-chat-profile.jsonl').open('a', encoding='utf-8') as _f:
            _f.write(_j.dumps({'case': _case['id'], 'profile': _case['profile'], 'before': _before, 'after': payload}, ensure_ascii=False) + '\\n')
    return _chat_profile_post(self, payload, *args, **kwargs)
_ChatProfileRuntime._post = _post_with_chat_profile
'''
marker="(hook/'sitecustomize.py').write_text(hook_source,encoding='utf-8')"
script=script.replace(marker,'hook_source += '+repr(hook)+'\n'+marker)
script=script.replace(' for case in cases:\n'," for case in cases:\n  write(private/'active-profile.json',{'id':case['id'],'profile':case['profile']})\n")
target=root/'scratchpad/c03-chat-profile508.py';assert not target.exists();target.write_text(script,encoding='utf-8')
write(campaign/'PINS.json',{p.name:sha(p) for p in campaign.iterdir() if p.is_file() and p.name!='PINS.json'})
for name in ['CHECKPOINT.md','HANDOFF.md']:
 p=base/name;s=p.read_text(encoding='utf-8-sig')
 s+='\n507 cerrado:18/20útiles y11/11bindings; sesiones15347exit0. Fuente506 integrada conserva audio y corrige actor/prosa; definición/recall falsos pendientes. RAM1778,320/GPU3497,559MiB48,921s. Siguiente508 ya PREREG/script:28turnos (7×perfilregistrado/documentado×semillas0/17), sólo sampler del payload real de conversación. No fuente ni registro nuevos. Ejecutar scratchpad/c03-chat-profile508.py; no procesos activos todavía.\n'
 p.write_text(s,encoding='utf-8')
r=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'));r.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='507 cerrado18/20 y11/11bindings; fuente506 validada; ningún proceso activo.',continuation='508 perfil de conversación documentado vs registrado, semillas0/17; C03 activo.');write(base/'RELEVO_ACTIVO.json',r)
print('507 closed18/20 and11/11;508 prepared with exact documented profile,28turns.')
