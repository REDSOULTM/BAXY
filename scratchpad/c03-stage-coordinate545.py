from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-coordinate-queries545'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
assert not (out/'PREREG.json').exists()
write(out/'PREREG.json',{
 'utc':datetime.now(timezone.utc).isoformat(),
 'registration_stage':'Recorded after test-first diagnosis and owner validation; not falsely labelled as sealed before initial reproduction.',
 'finding':'Product541/543 H0079 fails clear time+battery reads in ES/EN. ES did not split quantity question; EN split but whole-request speech-act guard rejected it. Regional decime clock head and English how much/many were absent from shared query readers.',
 'change':'Extend existing quantity-question boundary and speech-act/clock heads. Compose only independently direct clauses; existing global denials, unavailable operations and full-clause conservation remain. Preserve the old single-read boundary for closed CPU/RAM and OS/RAM combined scopes.',
 'validation':{'baseline':'6failed,103passed,1734deselected in1.38s',
               'initial_focal':'2failed,107passed in1.27s; found missing shared heads',
               'focal_after':'109passed,1734deselected in0.94s',
               'first_owners':'1failed,3698passed+121subtests in56.21s; combined OS/RAM unnecessarily split',
               'owners_after':'3699passed+121subtests,0skips in56.21s'},
 'owners':['test_effect_intent.py','test_system_status_scope_grounding.py','test_machine_status_scope.py','test_turn_policy.py','test_generalization_product_r6_development.py','test_planner.py','test_llm_plan_execution_gate_cases.py'],
 'preserved_controls':'Hypothetical/past readings, other device, unknown fridge contents, independent RAM, incomplete catalog and quantity question inside quoted note content. The old historical H0079 abstention expectation is replaced by explicit preservation of both reads, not by accepting a subset.',
 'scope':'Python only; actual product confirmation remains to be collected546; no new model/profile/visible reply. Full final still required.'})
for relative in ('src/baxy_mind/effect_intent.py','tests/test_effect_intent.py'):
    before=subprocess.run(['git','show','HEAD:'+relative],cwd=root,capture_output=True,check=True).stdout
    (out/(Path(relative).name+'.before')).write_bytes(before)
files={}
for directory in ('experiments/voice_latency','scripts','src/baxy_mind'):
    for path in (root/directory).rglob('*.py'):
        if path.is_file() and not path.is_symlink():files[path.relative_to(root).as_posix()]=path
digest=hashlib.sha256()
for relative in sorted(files):
    digest.update(relative.encode()+b'\n')
    digest.update(sha(files[relative]).encode()+b'\n')
tree=digest.hexdigest()
old='69586e40ec78f1ac4b183575f110f36371633b02b17d3bc52516a92cf4952086'
for relative in ('experiments/stt_quality/evaluate_reserved_stt.py','experiments/stt_quality/audit_fresh_postweight_stt_sources.py'):
    path=root/relative
    text=path.read_text(encoding='utf-8')
    assert old in text
    text=text.replace(old,tree,1).replace(
        '# C03 542: current program tree distinguishes GPU video memory from RAM.',
        '# C03 545: current program tree preserves coordinated measurement questions.')
    path.write_text(text,encoding='utf-8',newline='\n')
write(out/'CURRENT_TREE.json',{'sha256':tree,'files':len(files),'before':old,'historical_campaign_pins_unchanged':True})
assets=root/'artifacts/comprobaciones/C03/astra-e5-assets544'
(assets/'RESULT.md').write_text('''# E5 ONNX544 — adquisición verificada

Se descargaron los dos grafos oficiales del mismo checkpoint614241f622f53c4eeff9890bdc4f31cfecc418b3: FP32(470268510bytes) e INT8(118346824bytes). Tamaños y SHA256 coinciden con los objetos LFS del autor. Permanecen en D:/BAXYRuntime/experiments/models/e5-onnx-614241f6; no se añadió nada al snapshot E5 firmado de10 archivos.

El modelo generador, runtime registrado, encoder de producción y cachés siguen intactos. Falta comparar valores, ranking, RAM y latencia. El grafo INT8 publicado lleva perfil AVX512_VNNI; no se presupone que sea la mejor configuración para Ryzen AVX2 ni se descarta cuantización por ese perfil. Fuentes primarias, límites e hipótesis enPREREG.json. Sólo se solicitaron assets públicos: ninguna conversación salió del PC.
''',encoding='utf-8',newline='\n')
write(assets/'PINS.json',{p.name:sha(p) for p in assets.iterdir() if p.is_file() and p.name!='PINS.json'})
print(json.dumps({'tree':tree,'files':len(files)}))
