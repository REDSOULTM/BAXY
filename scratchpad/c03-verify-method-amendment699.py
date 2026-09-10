"""Check amended historical pins and new preregistration without changing measurements."""
from pathlib import Path
import hashlib
import json
import py_compile

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'K2_HORIZON_NATIVE699'
old=base/'K2_HORIZON_LATENCY697'
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))
pins=read(old/'PINS698.json')
for name,record in pins['files'].items():
    p=root/name
    assert p.stat().st_size==record['bytes'] and sha(p)==record['sha256'],name
receipt=read(out/'AMENDMENT_RECEIPT.json')
for name,h in receipt['before'].items():
    assert sha(out/('PRE_ACLARACION_'+name))==h
for name,h in receipt['after'].items():
    assert sha(old/name)==h
prior=read(out/'PRE_ACLARACION_SUMMARY698.json')
current=read(old/'SUMMARY698.json')
assert prior['records']==current['records']
assert current['decision']['decision']=='provisional_pending_independent_and_paired_comparison'
assert read(base/'RELEVO_ACTIVO.json')['surveyVerificationCounts']=={'covered':26,'open':716,'not_applicable':0}
panel=read(out/'PANEL.json')
assert len(panel)==50 and len({r['id'] for r in panel})==50
assert sha(out/'PANEL.json')==read(out/'PLAN.json')['panel_sha256']
assert all(set(r['payload'])=={'messages'} for r in panel)
assert all(m['role'] in ['user','assistant'] and 'BAXY' not in m['content'].upper() for r in panel for m in r['payload']['messages'])
scripts=['c03-amend-methodology699.py','c03-prepare-neutral699.py','c03-k2-smoke696.py',
    'c03-review-neutral699.py','c03-native699-checkpoint.py','c03-verify-method-amendment699.py',
    'c03-adjudicate-native699.py','c03-response-timing699.py','c03-report-native699.py',
    'c03-prepare-selector-ablation700.py','c03-review-k2-panel696.py','c03-prepare-prompt-layer699.py']
for name in scripts:
    py_compile.compile(str(root/'scratchpad'/name),doraise=True)
result=dict(public_pins_verified=len(pins['files']),archived_pre_amendment_files=len(receipt['before']),
    old_measurements_unchanged=True,neutral_cases=50,diagnostic_scripts_compiled=len(scripts),
    panel_sha256=sha(out/'PANEL.json'),scope='Evidence/method checks only; not a product Full or model-quality grade.')
(out/'METHOD_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
