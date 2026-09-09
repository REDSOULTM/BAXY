"""Record source633, update current-source declarations, preserve consumed pins."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03'
out = base/'astra-window-source633'
out.mkdir(exist_ok=False)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
files = {p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency','scripts','src/baxy_mind'] for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest=hashlib.sha256()
for relative in sorted(files): digest.update(relative.encode()+b'\n'+sha(files[relative]).encode()+b'\n')
tree=digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py','evaluate_reserved_stt.py']:
    p=root/'experiments/stt_quality'/name
    old=b'92d8fd81f3189ac96fbbb8750413da2cadac900b279ea2660eb1ff076eab7370'
    data=p.read_bytes();assert data.count(old)==1
    p.write_bytes(data.replace(old,tree.encode()))
p=root/'tests/test_price_v8_veto_damage_by_cause.py'
old=b'e03aa7836e20b88b50b773c2c6ad914152be8db2c1aa39a20824d4d6c12ed1c3'
data=p.read_bytes();assert data.count(old)==1
p.write_bytes(data.replace(old,sha(root/'src/baxy_mind/__main__.py').encode()))
for suffix,dest in [('red','RED.log'),('targeted','TARGETED.log'),('owners','OWNERS.log')]:
    (out/dest).write_bytes((Path(os.environ['TEMP'])/f'c03-window633-{suffix}.log').read_bytes())
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'source':633,
    'sources':{name:sha(root/name) for name in ['src/baxy_mind/effect_intent.py','src/baxy_mind/__main__.py']},
    'python_tree_sha256':tree,'python_files':len(files),
    'test_first':'46 failed/4 passed, including missing helper import;50 passed after implementation. Added4scope and8schema controls before owners.',
    'owners':{'passed':3425,'subtests':121,'skipped':0,'seconds':64.10},
    'cause':'632: foreground snapshot falsely used for named application absence. Use existing window.application.status with authenticated identity and exact schema; visible alone no longer authorizes foreground.',
    'criteria':'Fast and current-pin owners green. Product634: real installed app names, open/closed observations, ES/EN/order, foreground controls, no write operation. No model/profile change or UI/voice credit. Record all outcomes, no survey coverage inferred from parser.'})
state=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),
    checkpoint='633 candidato Python:3425pass+121subtests/0skips;Fast y producto634 pendientes.25/717/0.',
    continuation='Verificar633 con Fast y634 con lecturas reales. No afirmar cobertura por tests. Ninguna decisión pendiente.',
    previousGoalTurnClassification='no_progress',
    previousGoalTurnClassificationReason='The interrupted continuation only revalidated published630 and owner authorization. Current continuation implements and tests633.')
write(base/'RELEVO_ACTIVO.json',state)
with (base/'CHECKPOINT.md').open('a',encoding='utf-8',newline='\n') as stream:
    stream.write('\n\n## Candidato633 — alcance de ventanas por aplicación\n\n632 identifica la primera transformación errónea.633 reutiliza window.application.status con el catálogo autenticado y su schema; una ventana visible no implica foco.50focales iniciales verdes; dueñas3425pass+121subtests/0skips en64,10s, incluidos12controles añadidos de alcance/schema. Fast y producto634 pendientes. Sin cambio de modelo, provider o prosa fija.25cubiertos/717abiertos/0NA.\n')
print({'tree':tree,'source':633})
