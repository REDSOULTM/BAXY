from pathlib import Path
import hashlib
import json
import os
import time
os.environ['HF_HUB_OFFLINE'] = '0'
from huggingface_hub import hf_hub_download

root = Path('D:/BAXYRuntime/experiments/models/baxy-gemma4-e2b-published-f9b84ecd')
root.mkdir(parents=True, exist_ok=True)
metadata = {'repo': 'REDSOULTM/baxy-gemma4-E2B-GGUF',
            'revision': 'f9b84ecdcd4ffdc112a5baa21b86d553a9360c71',
            'filename': 'gemma-4-E2B-it-Q4_K_M.gguf', 'size': 3427879072,
            'expectedSha256': '9d4a5a653f2733a5faeb5f58a0e30bc064dfd569b0059cabb2547dbc4ba0f4b7',
            'source': 'README.md of local Probando Gemma 4, lines 223-260; remote public metadata verified before download.'}
(root/'DOWNLOAD.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
print(json.dumps(metadata), flush=True)
start = time.monotonic()
path = Path(hf_hub_download(repo_id=metadata['repo'], revision=metadata['revision'],
                            filename=metadata['filename'], local_dir=root))
with path.open('rb') as stream:
    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
assert actual == metadata['expectedSha256'] and path.stat().st_size == metadata['size']
result = {'phase': 'verified', 'path': str(path), 'sha256': actual,
          'elapsedSeconds': round(time.monotonic()-start, 2)}
(root/'VERIFIED.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result), flush=True)
