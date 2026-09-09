from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
root=Path(__file__).resolve().parents[1]
out=root/'artifacts/comprobaciones/C03/astra-context-answer555'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
assert not (out/'PREREG.json').exists()
for name in ('src/baxy_mind/llm.py','tests/test_turn_policy.py'):
    (out/(Path(name).name+'.before')).write_bytes(subprocess.run(['git','show','HEAD:'+name],cwd=root,capture_output=True,check=True).stdout)
files={p.relative_to(root).as_posix():p for directory in ('experiments/voice_latency','scripts','src/baxy_mind') for p in (root/directory).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest=hashlib.sha256()
for name in sorted(files):digest.update(name.encode()+b'\n'+sha(files[name]).encode()+b'\n')
tree=digest.hexdigest()
old='399e73203f5eafca73a8573083703cd2e10756b2c8544e992c8c40cb24b80138'
for relative in ('experiments/stt_quality/evaluate_reserved_stt.py','experiments/stt_quality/audit_fresh_postweight_stt_sources.py'):
    p=root/relative
    text=p.read_text(encoding='utf-8')
    assert old in text
    p.write_text(text.replace(old,tree,1).replace('# C03 545: current program tree preserves coordinated measurement questions.','# C03 555: contextual interpretation is not a visible-answer fallback.'),encoding='utf-8',newline='\n')
write(out/'CURRENT_TREE.json',{'sha256':tree,'files':len(files),'before':old,'historical_campaign_pins_unchanged':True})
write(out/'PREREG.json',{'utc':datetime.now(timezone.utc).isoformat(),'registration_stage':'After test-first reproduction and focal success, before broad owner/Fast/product validation; not claimed as blinded preregistration.',
 'cause':'Actual543 native27 returns direct_answer identical to the user closing, with resolved_meaning an internal third-person interpretation. _resolve_contextual_answer rejects the echo then publishes resolved_meaning. First faulty application transformation is demonstrated, not inferred as generic model/prose failure.',
 'change':'Use only direct_answer as public candidate. If invalid, preserve existing bounded direct_retry and honest ValueError if retry is also unusable. Never promote resolved_meaning to final answer. No new layer, phrase list, fixed reply or model configuration.',
 'baseline':'5 failed,1 passed,1026 deselected in2.25s','focal':'6 passed,1026 deselected in0.67s',
 'controls':'ES/EN closings, referential correction, question paraphrase, schema recovery, repeated invalid retry fails honestly. Existing direct-answer and literal recall paths remain under broad owners.',
 'publication':'Only Python source; current-tree STT attestations refreshed, historical pins unchanged. Product556 and source-quality gate required before claiming observed behavior fixed. No survey credit yet.'})
print(json.dumps({'tree':tree,'files':len(files)}))
