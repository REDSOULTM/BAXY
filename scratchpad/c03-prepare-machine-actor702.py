"""Pin the shared machine-subject repair candidate before product validation."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
out=base/'astra-machine-actor-source702'
out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files={p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency','scripts','src/baxy_mind']
       for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest=hashlib.sha256()
for name in sorted(files):
    digest.update(name.encode()+b'\n'+sha(files[name]).encode()+b'\n')
tree=digest.hexdigest()
old=json.loads((base/'astra-shared-status-source693/RESULT.json').read_text(encoding='utf-8'))
paths=['src/baxy_mind/llm.py','tests/test_c03_network_actor_recovery.py']
for name in ['audit_fresh_postweight_stt_sources.py','evaluate_reserved_stt.py']:
    path=root/'experiments/stt_quality'/name
    data=path.read_bytes()
    assert data.count(old['python_tree_sha256'].encode()) == 1
    path.write_bytes(data.replace(old['python_tree_sha256'].encode(),tree.encode()))
    paths.append(path.relative_to(root).as_posix())
path=root/'tests/test_price_v8_veto_damage_by_cause.py'
data=path.read_bytes()
assert data.count(old['sources']['src/baxy_mind/llm.py'].encode())==1
path.write_bytes(data.replace(old['sources']['src/baxy_mind/llm.py'].encode(),sha(root/'src/baxy_mind/llm.py').encode()))
paths.append(path.relative_to(root).as_posix())
for suffix in ['focal','focal-failure','focal2']:
    (out/(suffix.upper()+'.log')).write_bytes((Path(os.environ['TEMP'])/('c03-machine-actor701-'+suffix+'.log')).read_bytes())
assert '79 passed' in (out/'FOCAL2.log').read_text(encoding='utf-8-sig')
record={'utc':datetime.now(timezone.utc).isoformat(),'adopted':False,
        'parent_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'sources':{p:sha(root/p) for p in paths},'python_tree_sha256':tree,'python_files':len(files),
        'design':'Reuse the existing draft-aware CPU machine-actor recovery for non-capability wrong_actor with a typed connectivity Boolean. Preserve the original request, observed scope, polarity and latest rejected draft. No new retry, first prompt, validator, model or backend. Remove the generic online correction for this actor error.',
        'inheritance':'579/580 qualified the existing recovery for CPU.694WLAN correctly detects the wrong actor, but old retry loses Wi-Fi scope and third retry requests First person.694cause-group false_composition_rejection is an overbroad historical label: detector is correct; recovery is defective.',
        'focal':{'passed':79,'skipped':0,'initial_failed':2,
                 'initial_test_correction':'Two positive Spanish fixtures copied the entire question and entered extra_claim before actor detection. The scoped transport test now uses a non-echo request and explicitly verifies wrong_actor before checking its recovery; positive/negative states and existing rejection checks remain.'},
        'validation_next':'Fast702/current declarations; same50controls701 and exact73product turns694 with a separate transparent observer.701alone cannot prove WLAN recovery: no baselineWLAN call retried.',
        'goal_complete':False,'survey_coverage_added':0}
(out/'PREREG.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print({'source702_pinned':True,'python_tree':tree,'python_files':len(files)})
