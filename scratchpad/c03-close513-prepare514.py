"""Close integrated knowledge/audio and move to the actual desktop product path."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
out=base/'astra-audio-mind513'
prereg=json.loads((out/'PREREG.json').read_text(encoding='utf-8-sig'));cases={c['id']:c for c in prereg['cases']}
rows=[json.loads(s) for s in (out/'replies.jsonl').open(encoding='utf-8-sig')]
bindings=[json.loads(s) for s in (out/'bindings.jsonl').open(encoding='utf-8-sig')]
assert len(rows)==24 and len(bindings)==11
for r in rows:
 assert r['reply']['effectOperations']==cases[r['id']]['expected']
 r['useful']=True
 r['reason']='Correct proposal/clarification, or faithful natural conversation with human/assistant attribution preserved. All definition senses adjudicated under the existing non-exhaustiveness criterion. No visible JSON/selector prose or claimed execution.'
for b in bindings:
 value=b['reply'];case=cases[b['id']]
 if b['type']=='plan':
  assert [s['operation'] for s in value['steps']]==case['expected']
  args={k:v for s in value['steps'] for k,v in s['arguments'].items()}
 else:
  assert value['ok'];args=value['arguments']
 assert args==case['arguments']
res=json.loads((out/'RESOURCES.json').read_text(encoding='utf-8-sig'));assert res['completed'] and res['manifest_unchanged'] and not res['violations']
write(out/'ADJUDICATION.json',rows)
write(out/'RESULT.json',{'utc':datetime.now(timezone.utc).isoformat(),'session':37979,'exit':0,'useful':24,'total':24,'bindings_correct':11,'bindings':11,'resources':res,'source':'effect_intent503,__main__506,llm512','limits':'Actual mind protocol/current registeredT0 without private treatment. No C# shell, provider effect, physical UI/voice or acceptance. Next514 actual product conductor in an isolated profile.'})
(out/'RESULT.md').write_text('''# Fuente512 en el runtime registrado

24/24 propuestas, aclaraciones o respuestas útiles y11/11 bindings correctos. Se conservan las secuencias de volumen/silencio, negaciones, nivel pendiente y continuación numérica. Los nombres humanos, correcciones y otras personas se recuerdan correctamente; cuando se pregunta qué dijoBAXY, identifica sus propias palabras como tales. La definición es una explicación válida de quitar el silencio, sin prosa del selector ni ficción de ejecución.

Sin hooks de tratamiento ni campos de sampling promovidos: registro actual yT0deproducto. Sesión37979exit0;53,812s;RAM1788,973MiB/GPU3497,559MiB;sinviolaciones/manifiestointacto. Esta tanda no acredita el shellC#, efectos físicos, voz ni100humanos.514 pasa a las confirmaciones y memoria reales del producto en un perfil privado limpio, con el conductor existente y sin modificaciones de respuesta.
''',encoding='utf-8')
write(out/'PINS.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='PINS.json'})
script=(root/'scratchpad/c03-private-product437.py').read_text(encoding='utf-8-sig').replace('437','514')
script=script.replace("model=Path('D:/BAXYRuntime/experiments/models/qwen35-4b-e87f1764/Qwen3.5-4B-Q4_K_M.gguf')\nassert sha(model)=='00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'", "config=json.loads(manifest.read_text(encoding='utf-8-sig'))\nassert sha(manifest)=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'\nmodel=Path(config['gguf'])\nassert sha(model)=='3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'\nassert not (private.parent/'C03-private-profile514').exists()")
start=script.index("    'production_verification':");end=script.index("    'profile_inheritance':",start)
script=script[:start]+"    'production_verification': 'Source512 actual product conductor, current registeredQwen2507Q4/b9980 and current production sampler. Python knowledge history changes are integrated; C# memory/confirmation and actual isolated persistence are not mocked. Observation logs only; no composition/thinking/requiredFacts treatment.',\n    'method': 'Same eight consumed development turns437/464, new clean private profile. This is current-product regression and first-boundary diagnosis, not a model-ranking based on defaults. Model-specific profile evidence448-511 retained. Only synthetic memory effects in this dedicated profile; no owner memory, visible UI, physical voice or acceptance credit. Check all final responses and real memory state; no admission200-as-pass.',\n"+script[end:]
script=script.replace("    'diagnostic_model_override':{'path':str(model),'sha256':sha(model),'promotion':False},", "    'registered_model':{'path':str(model),'sha256':sha(model)},\n    'registered_backend':{'path':config['llama_server'],'sha256':sha(Path(config['llama_server']))},")
script=script.replace("env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_PYTHONPATH=", "env.update(BAXY_MIND_LLM_GGUF=str(model), BAXY_MIND_LLAMA_SERVER=config['llama_server'], BAXY_MIND_PYTHONPATH=")
script=script.replace("            if gpu.peak_mib is not None and gpu.peak_mib >= 3800:","            if time.monotonic()-started>240:\n                violations.append('scenario_wall_time_bound')\n            if gpu.peak_mib is not None and gpu.peak_mib >= 3800:")
script=script.replace("'minimum_free_ram_mib':768, 'scope':", "'minimum_free_ram_mib':768, 'wall_time_seconds':240, 'scope':")
target=root/'scratchpad/c03-private-product514.py';assert not target.exists();target.write_text(script,encoding='utf-8')
hook=root/'scratchpad/c03-owner514-hook';hook.mkdir(exist_ok=False)
(hook/'sitecustomize.py').write_text((root/'scratchpad/c03-owner437-hook/sitecustomize.py').read_text(encoding='utf-8-sig').replace('437','514'),encoding='utf-8')
for name in ['CHECKPOINT.md','HANDOFF.md']:
 p=base/name;s=p.read_text(encoding='utf-8-sig');s+='\n513cerrado37979exit0:24/24útiles+11/11bindingsconregistroactualysintratamiento. RAM1788,973/GPU3497,559MiB53,812s.514script/hookdeobservación listos: ocho turnosproducto437/464, peroahoraregistroQwenactualyfuente512;sin overrides de composición/thinking/requiredFacts. PerfilC03-private-profile514nuevo;únicos efectosmemoriasintéticaaislada. ConductorC#real,noUI/voz;límitesGPU3800/RAMlibre768/tiempototal240s. Ejecutar scratchpad/c03-private-product514.py. Sinprocesosactivos.\n';p.write_text(s,encoding='utf-8')
r=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8-sig'));r.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='513cerrado24/24y11/11bindings;fuente512validada;sinprocesos.',continuation='514productoC#conconfirmación/memoriasintéticaaislada,registroactualsintratamiento.C03activo.');write(base/'RELEVO_ACTIVO.json',r)
print('513closed24/24 and11/11;514 product regression prepared, original profile protected.')
