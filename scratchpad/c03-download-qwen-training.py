from pathlib import Path
import hashlib
import json
import os
import time
os.environ['HF_HUB_OFFLINE'] = '0'
from huggingface_hub import HfApi, snapshot_download

root = Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-training-cdbee75f')
root.mkdir(parents=True, exist_ok=True)
repo = 'Qwen/Qwen3-4B-Instruct-2507'
revision = 'cdbee75f17c01a7cc42f958dc650907174af0554'
info = HfApi().model_info(repo, revision=revision, files_metadata=True)
patterns = ['*.json', '*.safetensors', '*.jinja', 'merges.txt', 'vocab.json']
entries = [item for item in info.siblings if any(Path(item.rfilename).match(pattern) for pattern in patterns)]
metadata = {'repo':repo,'revision':revision,'purpose':'Trainable parent for bounded QLoRA viability smoke; no product promotion.',
            'files':[{'name':item.rfilename,'size':item.size,'expectedSha256':item.lfs.sha256 if item.lfs else None} for item in entries]}
(root/'DOWNLOAD.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
print(json.dumps({'phase':'download','files':len(entries),'bytes':sum(item.size or 0 for item in entries)}),flush=True)
start=time.monotonic()
snapshot_download(repo_id=repo,revision=revision,local_dir=root,allow_patterns=patterns,max_workers=3)
verified=[]
for entry in metadata['files']:
    path=root/entry['name']
    with path.open('rb') as stream:
        actual=hashlib.file_digest(stream,'sha256').hexdigest()
    assert path.stat().st_size==entry['size']
    if entry['expectedSha256']:
        assert actual==entry['expectedSha256']
    verified.append({'name':entry['name'],'sha256':actual,'size':path.stat().st_size})
result={'phase':'verified','repo':repo,'revision':revision,'elapsedSeconds':round(time.monotonic()-start,2),'files':verified}
(root/'VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'phase':'verified','files':len(verified),'elapsedSeconds':result['elapsedSeconds']}),flush=True)
