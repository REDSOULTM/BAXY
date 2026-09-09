"""Bind both protocol endpoints and preregister full and product validation."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03';out=base/'astra-objective-continuity630'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
assert not (out/'PREREG.json').exists()
p=root/'tests/test_price_v8_veto_damage_by_cause.py';data=p.read_bytes();old=b'f5799ceda0288d30bbdf911957a2de5591bba252d5f8b4eeb8ec2a15c805b3a1'
assert data.count(old)==1;p.write_bytes(data.replace(old,sha(root/'src/baxy_mind/__main__.py').encode()))
files={p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency','scripts','src/baxy_mind'] for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest=hashlib.sha256()
for relative in sorted(files):digest.update(relative.encode()+b'\n'+sha(files[relative]).encode()+b'\n')
tree=digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py','evaluate_reserved_stt.py']:
 p=root/'experiments/stt_quality'/name;data=p.read_bytes();old=b'ad6066f740c94999a16a2cc47da6796c5989e6e1fb23c704c28454ab6ae5bc03'
 assert data.count(old)==1;p.write_bytes(data.replace(old,tree.encode()))
paths=['src/baxy_mind/__main__.py','src/baxy_mind/effect_intent.py','src/Baxy.App/MindSidecarClient.cs','src/Baxy.App/UserMessagePolicy.cs']
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'source':630,'source_sha256':{p:sha(root/p) for p in paths},'python_tree_sha256':tree,'python_files':len(files),
 'method':'Mind marks new recognized incomplete commands using existing request-head authority; optional startsNewObjective false by default. Shell keeps the new objective for its next slot without appending it to the previous one. No effect authority, model, prompt or sampling changed.',
 'required_validation':'Python owners, .NET PlannerAppBoundaryTests114, Full630, then product631 same20cases629 after all builds complete. Keep original failures and zero effects. Full required for both-language source adoption.',
 'survey':{'covered':25,'open':717,'not_applicable':0}})
state=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
state.update(confirmedAtUtc=datetime.now(timezone.utc).isoformat(),checkpoint='62911/20:628 mejora lectura pero shell concatena nuevo pedido a anterior.630 candidato separa startsNewObjective de PreserveObjective:12testsPython/114.NETverdes. Full y631 pendientes.',continuation='Recoger dueñas630; Full630 obligatorio por C#+Python. Sin producto mientras compila. Después631 mismo20panel629, adjudicar y publicar sólo si mejora verificada.25/717/0; ninguna decisión pendiente.')
write(base/'RELEVO_ACTIVO.json',state)
(base/'HANDOFF.md').write_text('# C03 — candidato630: continuidad de aclaraciones\n\n626 es la fuente publicada;628/629 no adoptados todavía.629 se selló11/20: lector628 devuelve clarify26, pero shell une el pedido a la aclaración anterior y cambia a unsupported27.630 añade indicador startsNewObjective opcional false; sólo pedido directo reconocido, sin efectos. Shell evita la unión y conserva PreserveObjective para el siguiente fragmento.12focalesPython/114.NETpass.\n\nSiguiente: recoger dueñas630, Full630 (C#+Python); después631 mismos20casos629. No ejecutar producto durantebuild. Archivos/pines actuales en astra-objective-continuity630/PREREG.json. Mantener todos los fallos629. BAXY manual cerrado, main intacto, sin agentes, autorización536.25cubiertos/717abiertos/0NA. No cerrarC03: UI/voz/recuperación/recursos conjuntos, restantes conductas y Fullfinal pendientes.\n',encoding='utf-8',newline='\n')
print({'source':630,'tree_sha256':tree})
