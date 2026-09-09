"""Read-only audit of adopted source, declarations and public/private evidence."""
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
pairs=[('astra-focus-coverage-source676',None),
       ('astra-compositor-focus-coverage677','C03-compositor-focus-coverage677-private'),
       ('astra-focus-coverage-product678','C03-focus-coverage-product678-private')]
pins=0
for public,private in pairs:
    out=base/public
    for name,value in read(out/'PINS.json').items():
        assert sha(out/name)==value,(public,name)
        relative=(out/name).relative_to(root).as_posix()
        assert hashlib.sha256(subprocess.check_output(['git','show',':'+relative],cwd=root)).hexdigest()==value,('index',relative)
        pins+=1
    if private:
        for name,value in read(out/'RESULT.json')['private_hashes'].items():
            assert sha(home/private/name)==value,(private,name)
record=read(base/'astra-focus-coverage-source676/RESULT.json')
assert record['adopted'] is True
for name,value in record['sources'].items():
    assert sha(root/name)==value,name
    indexed=subprocess.check_output(['git','show',':'+name],cwd=root)
    assert indexed.replace(b'\r\n',b'\n')==(root/name).read_bytes().replace(b'\r\n',b'\n'),('source index',name)
files={p.relative_to(root).as_posix():p for folder in ['experiments/voice_latency','scripts','src/baxy_mind']
       for p in (root/folder).rglob('*.py') if p.is_file() and not p.is_symlink()}
digest=hashlib.sha256()
for name in sorted(files): digest.update(name.encode()+b'\n'+sha(files[name]).encode()+b'\n')
assert digest.hexdigest()==record['python_tree_sha256']
for name in ['audit_fresh_postweight_stt_sources.py','evaluate_reserved_stt.py']:
    assert (root/'experiments/stt_quality'/name).read_text(encoding='utf-8').count(digest.hexdigest())==1
assert (root/'tests/test_price_v8_veto_damage_by_cause.py').read_text(encoding='utf-8').count(record['sources']['src/baxy_mind/llm.py'])==1
assert sha(Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json')=='13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed'
assert sha(home/'C03-survey-requirements336-private/requirements.jsonl')=='237c14900a9e36e2e5f6071f132ad916a234ecb39a77e0dd497ef2565eceb2b7'
assert subprocess.check_output(['git','rev-parse','main'],cwd=root,text=True).strip()=='5f572ee1b48cb5e2543ee5e06510e51057c9c845'
assert subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip()=='Goal-c03'
running=[p.info['name'] for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() in ('baxy.exe','baxy.app.exe','llama-server.exe')]
assert not running,running
print({'public_and_index_pins':pins,'private_hashes':'verified','source_and_declarations':'verified','main_runtime_survey':'unchanged','product_processes':running})
