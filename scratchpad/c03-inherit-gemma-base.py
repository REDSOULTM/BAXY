from pathlib import Path
import hashlib,json,time,os
os.environ['HF_HUB_OFFLINE']='0'
from huggingface_hub import HfApi,hf_hub_download
root=Path('D:/BAXYRuntime/experiments/models/gemma4-e2b-inherited-d3b0fed4')
repo='unsloth/gemma-4-E2B-it-GGUF'; rev='0314792d7f1f7e229411f620751375812bb9faf2'; name='gemma-4-E2B-it-Q4_K_M.gguf'
info=HfApi().model_info(repo,revision=rev,files_metadata=True)
entry=next(item for item in info.siblings if item.rfilename==name)
expected=entry.lfs.sha256
(root/'BASE_DOWNLOAD.json').write_text(json.dumps({'repo':repo,'revision':rev,'filename':name,'size':entry.size,'expectedSha256':expected},indent=2),encoding='utf-8')
print(json.dumps({'phase':'download','size':entry.size,'sha256':expected}),flush=True)
start=time.monotonic()
path=Path(hf_hub_download(repo_id=repo,filename=name,revision=rev,local_dir=root/'base-gguf'))
with path.open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
assert actual==expected
result={'phase':'verified','path':str(path),'sha256':actual,'elapsedSeconds':round(time.monotonic()-start,2)}
(root/'BASE_VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
