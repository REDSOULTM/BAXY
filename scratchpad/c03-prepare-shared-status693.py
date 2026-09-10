"""Record the shared status candidate before the C#/Python Full gate."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-shared-status-source693'
out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files={p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency','scripts','src/baxy_mind']
       for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest=hashlib.sha256()
for name in sorted(files): digest.update(name.encode()+b'\n'+sha(files[name]).encode()+b'\n')
tree=digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py','evaluate_reserved_stt.py']:
    path=root/'experiments/stt_quality'/name
    before=path.read_bytes()
    old=b'50f0fb6bf6bd81210a800b72be09bf2a9544c7b9e482a54629c2141344ca1439'
    assert before.count(old)==1
    path.write_bytes(before.replace(old,tree.encode()))
path=root/'tests/test_price_v8_veto_damage_by_cause.py'
before=path.read_bytes();old=b'f2a938f32eafdfca72123f2563ab2f9b2a6c15f3834aba82aab25bdd51f5ca4c'
assert before.count(old)==1
path.write_bytes(before.replace(old,sha(root/'src/baxy_mind/llm.py').encode()))
changed=subprocess.check_output(['git','diff','--name-only'],cwd=root,text=True).splitlines()
changed+=['src/baxy_mind/measurement_prose_projection.py','tests/test_system_measurement_prose_projection.py']
record={'utc':datetime.now(timezone.utc).isoformat(),'adopted':False,
 'parent_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
 'sources':{name:sha(root/name) for name in changed},'python_tree_sha256':tree,'python_files':len(files),
 'design':'Shared narrator projection of typed memory/disk/GPU quantities in decimal GB, used=total-available, separate engine and dedicated VRAM percentages; preserve canonical snapshots and unknown measurements. Independent Windows SMBIOS installed RAM propagates through provider/Core typed results. wifi.status is read-only: no effects, credentials or SSID exposed, same double-read verifier.',
 'inheritance':'542 identified GPU conversion defect; full73-case batch689 isolated numeric errors and wifi confirmation cascade; native690 and691 compare numeric representation on all30 fixtures with fixed local runtime. Windows GetPhysicallyInstalledSystemMemory distinguishes installed from GlobalMemoryStatusEx usable capacity.',
 'sources_primary':['https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getphysicallyinstalledsystemmemory'],
 'validation':'Python focal29 passed. Run Full because this candidate touches C# and Python. Rerun same frozen73 product inputs689 after green validation. No model/profile change or new survey credit without adjudication/generalization.',
 'remaining_shared_causes':'Fresh read interpretation, window enumeration and descriptive window identity rejection remain outside this candidate; preserve failures and investigate together after paired product comparison.'}
(out/'PREREG.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
state=json.loads((base/'RELEVO_ACTIVO.json').read_text(encoding='utf-8'))
state.update(confirmedAtUtc=record['utc'],checkpoint='Candidato693 integrado: cantidades/RAM instalada/Wi-Fi lectura;29tests focales verdes. Full pendiente.690/691 completos sin sellar; tablero742 en692.',
 continuation='Recoger Full693 en TEMP/c03-shared-status693-full.log; no adoptar rojo. Sellar690/691/692, evaluar producto73 con mismo panel689 tras gate. Encuesta26/716/0 intacta.',
 activeValidation={'name':'Full693','log':'TEMP/c03-shared-status693-full.log'},pendingOwnerClarification=None)
(base/'RELEVO_ACTIVO.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
note='\n\n# 693 — reparación compartida candidata\n\nCantidades RAM/disco/GPU con unidades y aritmética explícitas, capacidad RAM instalada independiente y wifi.status de lectura.29pruebas focales Python verdes; Full C#+Python requerido y pendiente antes de adoptar. Sin cambios de modelo ni cobertura:26cubiertos/716abiertos/0NA. Tablero692 planifica los742, no adjudica automáticamente.690/691 completados; sus comparaciones y el error de preparación690 se conservarán sin afirmar que el modelo recibió JSON truncado.\n'
with (base/'CHECKPOINT.md').open('a',encoding='utf-8') as stream:stream.write(note)
with (base/'HANDOFF.md').open('a',encoding='utf-8') as stream:stream.write(note+'\nCandidato693 sin publicar. Full en TEMP/c03-shared-status693-full.log; próxima evaluación exacta73casos689 tras verde.\n')
print(json.dumps({'tree':tree,'files':len(files),'sources':len(changed),'adopted':False}))
