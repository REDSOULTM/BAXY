"""Pin current candidate declarations and the exact owner test scope."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-focus-coverage-source676'
out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prereg=json.loads((root/'artifacts/comprobaciones/C03/astra-compositor-focus-coverage677/PREREG.json').read_text(encoding='utf-8'))
assert prereg['source_sha256']==sha(root/'src/baxy_mind/llm.py')
assert prereg['window_fact_source_sha256']==sha(root/'src/baxy_mind/window_prose_facts.py')
files={p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency','scripts','src/baxy_mind']
       for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest=hashlib.sha256()
for name in sorted(files): digest.update(name.encode()+b'\n'+sha(files[name]).encode()+b'\n')
tree=digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py','evaluate_reserved_stt.py']:
    path=root/'experiments/stt_quality'/name
    data=path.read_bytes()
    old=b'f59d75eef59e777ce8288c74630198576bad062b4a398ac229fee3aa341f9c0d'
    assert data.count(old)==1
    path.write_bytes(data.replace(old,tree.encode()))
path=root/'tests/test_price_v8_veto_damage_by_cause.py'
data=path.read_bytes()
old=b'61c9da7e0975dabd54f0698f20eef06ade160988b4d8b64b8621516cdd454300'
assert data.count(old)==1
path.write_bytes(data.replace(old,sha(root/'src/baxy_mind/llm.py').encode()))
owners=set(subprocess.check_output(['git','grep','-l','-E','(baxy_mind.*llm|baxy_mind.*window_prose_facts)','--','tests/test_*.py'],cwd=root,text=True).splitlines())
owners.update(p.relative_to(root).as_posix() for p in (root/'tests').glob('test_c03*.py'))
owners=sorted(owners)
for suffix,name in [('baseline','API_BASELINE'),('behavior-baseline','BASELINE'),('focal','FOCAL')]:
    (out/(name+'.log')).write_bytes((Path(os.environ['TEMP'])/f'c03-focus-coverage676-{suffix}.log').read_bytes())
assert '50 failed, 14 passed' in (out/'BASELINE.log').read_text(encoding='utf-8-sig')
assert '733 passed' in (out/'FOCAL.log').read_text(encoding='utf-8-sig')
record={'utc':datetime.now(timezone.utc).isoformat(),'source':676,'adopted':False,
        'sources':{name:sha(root/name) for name in ['src/baxy_mind/llm.py','src/baxy_mind/window_prose_facts.py','tests/test_c03_window_focus_coverage.py','tests/test_c03_window_state_facts.py','tests/test_c03_window_prose_projection.py']},
        'python_tree_sha256':tree,'python_files':len(files),'owner_tests':owners,
        'design':'Bounded explicitly requested single-window focus coverage, preserving incidental active-window identifiers and untyped focus. Missing-answer feedback is distinct from contradiction. Existing retry only; canonical observations and first request unchanged.',
        'baseline':'First64 API failures retained separately. Once optional user_text argument existed but was unused, actual behavioral baseline50fail14pass. All64 new controls then pass; integrated733pass.677 actual compositor same17cases all reviewed correct; not adoption until owners/declarations/Fast/product.',
        'next':'Run declared owners and declaration tests, Fast, then exact24 product669 regression678. Full at final closure under Python-only objective rule.'}
(out/'PREREG.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print({'owner_files':len(owners),'tree':tree,'adopted':False})
