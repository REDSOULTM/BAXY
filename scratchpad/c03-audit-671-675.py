"""Read-only source/evidence audit, including the staged sealed bytes."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import psutil

root=Path(__file__).resolve().parents[1]
base=root/'artifacts/comprobaciones/C03'
home=Path(os.environ['LOCALAPPDATA'])/'BAXY'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
pairs=[('astra-window-state-facts671',None),
       ('astra-compositor-window-states672','C03-compositor-window-states672-private'),
       ('astra-native-focus-feedback673','C03-native-focus-feedback673-private'),
       ('astra-focus-feedback-source674',None),
       ('astra-compositor-focus-feedback675','C03-compositor-focus-feedback675-private')]
count=0
for public,private in pairs:
    out=base/public
    for name,value in read(out/'PINS.json').items():
        assert sha(out/name)==value,(public,name)
        relative=(out/name).relative_to(root).as_posix()
        assert hashlib.sha256(subprocess.check_output(['git','show',':'+relative],cwd=root)).hexdigest()==value,relative
        count+=1
    if private:
        for name,value in read(out/'RESULT.json')['private_hashes'].items():
            assert sha(home/private/name)==value,(private,name)
source671=read(base/'astra-window-state-facts671/RESULT.json')
for campaign in ['astra-compositor-window-states672','astra-native-focus-feedback673']:
    prereg=read(base/campaign/'PREREG.json')
    assert prereg['source_sha256']==source671['source_sha256']
    assert prereg['window_fact_source_sha256']==source671['factual_source_sha256']
source674=read(base/'astra-focus-feedback-source674/RESULT.json')
for name,value in source674['sources'].items(): assert sha(root/name)==value,name
prereg=read(base/'astra-compositor-focus-feedback675/PREREG.json')
assert prereg['source_sha256']==source674['sources']['src/baxy_mind/llm.py']
assert prereg['window_fact_source_sha256']==source674['sources']['src/baxy_mind/window_prose_facts.py']
assert sha(Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json')=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
assert sha(home/'C03-survey-requirements336-private/requirements.jsonl')=='237c14900a9e36e2e5f6071f132ad916a234ecb39a77e0dd497ef2565eceb2b7'
assert subprocess.check_output(['git','rev-parse','main'],cwd=root,text=True).strip()=='5f572ee1b48cb5e2543ee5e06510e51057c9c845'
assert subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip()=='Goal-c03'
running=[p.info['name'] for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() in ('baxy.app.exe','llama-server.exe')]
assert not running,running
print({'public_and_index_pins':count,'private_hashes':'verified','source674':'WIP preserved','source671':'historical snapshot verified','main_runtime_survey':'unchanged','product_processes':running})
