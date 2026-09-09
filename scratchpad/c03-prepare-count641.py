"""Pin the count-request repair before repeating product640."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os
root=Path(__file__).resolve().parents[1];base=root/'artifacts/comprobaciones/C03';out=base/'astra-count-source641'
out.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
files={p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency','scripts','src/baxy_mind'] for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest=hashlib.sha256()
for relative in sorted(files):digest.update(relative.encode()+b'\n'+sha(files[relative]).encode()+b'\n')
tree=digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py','evaluate_reserved_stt.py']:
 p=root/'experiments/stt_quality'/name;data=p.read_bytes();old=b'13f076532f82fb157a5423c5dbec885dc620c866b4fa0e91106ef6f52b64900b';assert data.count(old)==1
 p.write_bytes(data.replace(old,tree.encode()))
for suffix,dest in [('red','RED.log'),('targeted','TARGETED.log'),('owners','OWNERS.log')]:
 (out/dest).write_bytes((Path(os.environ['TEMP'])/f'c03-count641-{suffix}.log').read_bytes())
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'source':641,
 'sources':{p:sha(root/p) for p in ['src/baxy_mind/effect_intent.py','tests/test_effect_intent.py','tests/test_turn_policy.py']},
 'python_tree_sha256':tree,'python_files':len(files),'test_first':{'failed':16,'passed':56},'targeted_passed':72,
 'owners':{'passed':3455,'subtests':121,'skipped':0,'seconds':67.64},
 'method':'Preserve bounded quantity questions against dynamic app catalog; the fully matched named-window query supplies its own request act. Do not broaden how generically, invent a count, alter model/prose, or treat closed-window counts as observable.',
 'criteria':'Fast and current-tree declarations green.642 repeats exact20panel640. T20 must perform a fresh typed window.application.status read. Keep reference and focus-language failures unless evidence actually repairs them. No UI/voice or global coverage claim.'})
state=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='641 candidatoPython:16rojos→72focales;3455dueñas+121subpruebas/0omisiones. Fast/producto642 pendientes.25/717/0.',continuation='Completar Fast y642. Hallazgo independiente640: ventana.status ausente de shortlist en t15/request71 y t17/request80; t18 sí la propone antes de perder referencia. _turn_evidence_query usa4mensajes pero shortlist sólo routing_objective. Investigar recuperación contextual sin convertir historia en autorización.',previousGoalTurnClassification='progress')
write(base/'RELEVO_ACTIVO.json',state)
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as f:f.write('\n\n## Candidato641 — cantidades como consulta observable\n\n16variantes fallan antes;72focales y3455dueñas+121subpruebas pasan después. Se conserva la consulta completa y el nombre autenticado; no se amplía how globalmente. Fast/producto642 pendientes. Además,640 demuestra que el shortlist de And Spotify? y Y Steam? no incluye window.application.status; no es todavía una medición de incapacidad del modelo con la operación disponible.25/717/0.\n')
print({'source':641,'tree':tree})
