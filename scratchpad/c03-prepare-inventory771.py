"""Freeze tested inventory subject/polarity and measured explicit-cause candidate."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/comprobaciones/C03'
OUT=BASE/'INVENTORY_SCOPE771'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def write(path,data):
    path.write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))


assert not (OUT/'SOURCE_PINS.json').exists()
assert not subprocess.check_output(['git','diff','--cached','--name-only']).strip()
replay=read(OUT/'CAPTURED_REPLAY.json')
assert all(sha(ROOT/p)==h for p,h in replay['source_pins'].items())
paths=['src/baxy_mind/llm.py','src/baxy_mind/window_prose_facts.py',
    'tests/test_c03_inventory_scope_polarity.py','experiments/stt_quality/evaluate_reserved_stt.py',
    'experiments/stt_quality/audit_fresh_postweight_stt_sources.py','tests/test_price_v8_veto_damage_by_cause.py']
assert all(b'\r\n' not in (ROOT/p).read_bytes() for p in paths)
sys.path.insert(0,str(ROOT))
from scripts.wake_validation_program_tree import fingerprint_program_tree
prior=read(BASE/'INVENTORY_CORRECTION768/PROGRAM.json')
program=fingerprint_program_tree(repository_root=ROOT,source_roots=[ROOT/p for p in prior['roots']])
assert program['pythonFiles']==407
for relative in paths[3:5]:
    path=ROOT/relative;data=path.read_text(encoding='utf-8')
    assert data.count(prior['sha256'])==1
    path.write_bytes(data.replace(prior['sha256'],program['sha256']).encode('utf-8'))
old=read(BASE/'INVENTORY_CORRECTION768/SOURCE_PINS.json')[paths[0]]
path=ROOT/paths[-1];data=path.read_text(encoding='utf-8');assert data.count(old)==1
path.write_bytes(data.replace(old,sha(ROOT/paths[0])).encode('utf-8'))
write(OUT/'SOURCE_PINS.json',{p:sha(ROOT/p) for p in paths})
write(OUT/'PROGRAM.json',program)
write(OUT/'PLAN.json',{'utc':datetime.now(timezone.utc).isoformat(),
    'source_parent':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'diagnosis':'770C/D contain all20 identities with truthful20/25 scope but fail page-subject and negative-exhaustiveness checks. Explicit cause improves CvsA and DvsB.',
    'changes':['Reuse the existing derived full-page fact in projection and validation; bind lista/list quantity to the page.',
        'Bind the all-windows statement to its explicit negation and known full/partial/unknown scope; a page subject alone does not restrict a global all-windows claim.',
        'Reuse one correction builder for retry/third and add exactly the explicit-cause system clause measured in770C, only for the observed chronology defect.'],
    'no_new_layer_or_model_condition':True,'first_attempt_sampler_budget_unchanged':True,
    'validation_completed':'986 owner tests pass/0skip,6.20s;68 new scope/polarity/composition cases. Exact capturedC/D pass in1stub; reconstructed retry equals measured770C payload byte-for-value.',
    'initial_test_collection_error':'New test used reserved pytest parameter request; renamed user_text before collection. Original error log retained; no product failure.',
    'validation_pending':'Current-pin/window integrity and Fast on sealed source. Publish after green and run prepared772 complete73.',
    'known_open':'770B omitted one repeated window but checker accepted; no acceptance/coverage from that arm. Other global inventory routing/focus issues remain.',
    'coverage_added':0,'survey':{'covered':26,'open':716,'not_applicable':0}})
for source_name,target_name in [('owners-initial','owners-collection-error.log'),('owners','owners-scope.log'),('owners-combined','owners.log')]:
    raw=(Path(os.environ['TEMP'])/('c03-inventory-scope771-'+source_name+'.log')).read_bytes()
    (OUT/target_name).write_bytes(raw.replace(b'\r\n',b'\n'))
driver=(ROOT/'scratchpad/c03-status-batch769.py').read_text(encoding='utf-8')
driver=driver.replace('STATUS_BATCH769','STATUS_BATCH772').replace('batch769','batch772').replace('profile769','profile772')
driver=driver.replace('INVENTORY_CORRECTION768','INVENTORY_SCOPE771').replace('pins768','pins771').replace('source768','source771')
driver=driver.replace('after inventory correction768','after inventory scope and correction771').replace('Published768','Published771')
target=ROOT/'scratchpad/c03-status-batch772.py';assert not target.exists();target.write_bytes(driver.encode('utf-8'))
reviewer=(ROOT/'scratchpad/c03-review-status769.py').read_text(encoding='utf-8')
reviewer=reviewer.replace('769','772').replace('source768_unchanged','source771_unchanged')
target=ROOT/'scratchpad/c03-review-status772.py';assert not target.exists();target.write_bytes(reviewer.encode('utf-8'))
note=('771 candidato: cantidad ligada a lista/página y negación de exhaustividad reparadas; misma causa explícita770C en retry/third. '
    '986owners/0skip/6,20s,68nuevos; replay C/D exactos1stub y retry igual770C.6pins fuente/declaraciones congelados. '
    'Faltan integridad/Fast, publicar y772completo73.770B omisión repetida sigueabierta. No inferenciaactiva.26/716/0.\n\n')
cp=BASE/'CHECKPOINT.md';pending=cp.with_suffix('.pending.md');pending.write_bytes(note.encode()+cp.read_bytes());pending.replace(cp)
r=read(BASE/'RELEVO_ACTIVO.json');r.update(checkpoint=note.strip(),activeValidation=None,
    workStatus='inventory_scope771_validation_pending',continuation='Validate sealed771 current pins/window/Fast; publish then registered73 driver772. No real inference active.')
write(BASE/'RELEVO_ACTIVO.json',r)
print(json.dumps({'source_pins':len(paths),'program':program,'driver772_prepared':True}))
