"""Verify exact measured payload parity and pin the Spanish policy candidate."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root),str(root/'src')]
from baxy_mind.llm import LlmRuntime
home = Path(os.environ['LOCALAPPDATA'])/'BAXY'
panel = json.loads((home/'C03-native-literal-contract663-private/panel.json').read_text(encoding='utf-8'))
config = json.loads((Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json').read_text(encoding='utf-8-sig'))
class Captured(Exception): pass
class Builder(LlmRuntime):
    def __init__(self): self._gguf=config['gguf']
    def _post(self,payload,**kwargs):
        self.payload=copy.deepcopy(payload)
        raise Captured()
count=0
for row in panel:
    if row['arm'] != 'literal_contract': continue
    client=Builder()
    try: client.compose_user_message(row['text'],'status',row['facts'])
    except Captured: pass
    else: raise AssertionError('No first request')
    assert client.payload == row['payload'],row['case_id']
    count+=1
assert count==10
out=root/'artifacts/comprobaciones/C03/astra-literal-source664'
out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files={p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency','scripts','src/baxy_mind']
       for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest=hashlib.sha256()
for name in sorted(files): digest.update(name.encode()+b'\n'+sha(files[name]).encode()+b'\n')
tree=digest.hexdigest()
for name in ['audit_fresh_postweight_stt_sources.py','evaluate_reserved_stt.py']:
    path=root/'experiments/stt_quality'/name
    data=path.read_bytes(); old=b'f59d75eef59e777ce8288c74630198576bad062b4a398ac229fee3aa341f9c0d'
    assert data.count(old)==1
    path.write_bytes(data.replace(old,tree.encode()))
path=root/'tests/test_price_v8_veto_damage_by_cause.py'
data=path.read_bytes(); old=b'61c9da7e0975dabd54f0698f20eef06ade160988b4d8b64b8621516cdd454300'
assert data.count(old)==1
llm=sha(root/'src/baxy_mind/llm.py')
path.write_bytes(data.replace(old,llm.encode()))
record={'utc':datetime.now(timezone.utc).isoformat(),'source':664,'adopted':False,
    'llm_sha256':llm,'python_tree_sha256':tree,'python_files':len(files),'measured_payload_parity':count,
    'design':'Replace ambiguous Spanish contract-literal exemption with preservation of names/titles/paths and Spanish state descriptions. English/mixed contracts unchanged. No field projection, extra rule, inference or fixed response.',
    'evidence':'662 added system instruction and sampling failed9/10.663 same current9/10; policy replacement10/10 and independent field rename10/10. Choose smaller existing-policy edit with original schema intact; no universal conclusion.',
    'next':'Owner suites/current declarations/Fast then product665 exact24 window queries and666 exact35 conversation regression. Inspect all outputs before adoption. No Full needed per Python-only rule until final closure.'}
(out/'PREREG.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(record)
