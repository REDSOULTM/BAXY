"""Read-only sealing audit; require restoration of validated source660."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
home=Path(os.environ['LOCALAPPDATA'])/'BAXY'
sha=lambda data:hashlib.sha256(data).hexdigest()
read=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
staged='--staged' in sys.argv
verified=0
for name in ['native-schema-prose662','native-literal-contract663','literal-source664','literal-product665','conversation-regression666']:
    out=base/('astra-'+name)
    for filename,digest in read(out/'PINS.json').items():
        path=out/filename
        assert sha(path.read_bytes())==digest,path
        if staged: assert sha(subprocess.check_output(['git','show',':'+path.relative_to(root).as_posix()],cwd=root))==digest,path
        verified+=1
    for filename,digest in read(out/'RESULT.json')['private_hashes'].items():
        assert sha((home/('C03-'+name+'-private')/filename).read_bytes())==digest
for name in ['src/baxy_mind/llm.py','tests/test_price_v8_veto_damage_by_cause.py','experiments/stt_quality/audit_fresh_postweight_stt_sources.py','experiments/stt_quality/evaluate_reserved_stt.py']:
    assert (root/name).read_bytes().replace(b'\r\n',b'\n')==subprocess.check_output(['git','show','HEAD:'+name],cwd=root).replace(b'\r\n',b'\n')
assert sha((root/'src/baxy_mind/llm.py').read_bytes())=='61c9da7e0975dabd54f0698f20eef06ade160988b4d8b64b8621516cdd454300'
assert sha((home/'C03-survey-requirements336-private/requirements.jsonl').read_bytes())=='237c14900a9e36e2e5f6071f132ad916a234ecb39a77e0dd497ef2565eceb2b7'
assert sha((home.parent/'BAXYRuntime/mind-runtime-v1.json').read_bytes())=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
assert subprocess.check_output(['git','rev-parse','main'],cwd=root,text=True).strip()=='5f572ee1b48cb5e2543ee5e06510e51057c9c845'
print({'public_pins':verified,'staged':staged,'source660_restored':True,'manifest_survey_main_unchanged':True})
