"""Acquire a pinned public candidate; never alter the registered runtime."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-qwen9b388'
out.mkdir(exist_ok=False)
directory = Path('D:/BAXYRuntime/experiments/models/qwen35-9b-03b74727')
directory.mkdir(exist_ok=True)
model = directory / 'Qwen3.5-9B-Q4_K_M.gguf'
partial = model.with_suffix('.gguf.part')
assert not model.exists() and not partial.exists()
revision = '3885219b6810b007914f3a7950a8d1b469d598a5'
expected_hash = '03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8'
size = 5680522464
url = f'https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/{revision}/{model.name}'
prereg = {'utc': datetime.now(timezone.utc).isoformat(), 'action': 'download candidate only',
    'repository': 'unsloth/Qwen3.5-9B-GGUF', 'base_model': 'Qwen/Qwen3.5-9B',
    'revision': revision, 'url': url, 'sha256': expected_hash, 'bytes': size,
    'license': 'apache-2.0', 'model': str(model),
    'reason': 'Current4B still fails human/Windows identity and private/session distinctions in frozen386.387 precise account description did not improve2/4; no source adoption. Compare a more capable member of the same family with partial GPU offload, never assume more parameters help. Prior Qwen3-8B IQ3 failed native ceiling59.18% on a different model/quantization/corpus (REGISTRO1261-1286); do not repeat it or infer9B quality from it.',
    'research': ['https://huggingface.co/Qwen/Qwen3.5-9B', 'https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/blob/main/Qwen3.5-9B-Q4_K_M.gguf', 'https://github.com/ggml-org/llama.cpp/blob/b9980/docs/function-calling.md'],
    'documented_profile': 'Non-thinking via enable_thinking=false. Official general non-thinking recommendation temp0.7/top_p0.8/top_k20/min_p0/presence1.5/repetition1.0; do not silently change the baseline sampler. No /nothink soft switch. First comparison should preserve actual387 sampling and distinguish any later profile trial.',
    'resource_plan': 'No model launch in this script. Later start with conservative partial offload (planned ngl14, not measured) and monitor owned GPU/RAM, with 4GB VRAM stop bound before corpus. Machine has about15.4GiB visible RAM and6.1GiB free at preparation, D has173GB free. Candidate weights5.68GB do not fit wholly under4GB VRAM; additional RAM is essential. No joint-voice or minimum-VRAM claim.',
    'next': 'After hash verification, inspect GGUF/template/backend compatibility and launch a bounded resources/native test on frozen387. Only expand to17cases385 if resources and native quality justify. No runtime promotion, source/prompt change, App/UI/voice or fresh-human acceptance.'}
(out / 'PREREG.json').write_text(json.dumps(prereg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
start = time.monotonic()
total = 0
digest = hashlib.sha256()
next_report = 256 * 1024 * 1024
with urllib.request.urlopen(url, timeout=60) as response, partial.open('xb') as stream:
    while chunk := response.read(8 * 1024 * 1024):
        stream.write(chunk)
        digest.update(chunk)
        total += len(chunk)
        if total >= next_report:
            print(json.dumps({'downloaded': total, 'total': size, 'seconds': round(time.monotonic() - start, 1)}), flush=True)
            next_report += 256 * 1024 * 1024
assert total == size, (total, size)
assert digest.hexdigest() == expected_hash, digest.hexdigest()
with partial.open('rb') as stream:
    assert stream.read(4) == b'GGUF'
assert not model.exists()
partial.replace(model)
(out / 'DOWNLOAD.json').write_text(json.dumps({'completed': True, 'path': str(model), 'bytes': total,
    'sha256': digest.hexdigest(), 'seconds': round(time.monotonic() - start, 3)}, indent=2) + '\n', encoding='utf-8')
print('Pinned candidate downloaded and SHA256 verified; not launched or registered.', flush=True)
