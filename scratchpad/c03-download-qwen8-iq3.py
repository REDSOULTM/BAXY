from pathlib import Path
import hashlib
import json
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
revision = '0b69f75b7472688e6808490aa2b85efdb81b5ce7'
name = 'Qwen_Qwen3-8B-IQ3_XXS.gguf'
expected_sha = '11a2ba2a7970f621c03e05bce111df2cb7c04880ffec2cdd03445d7b5e8b8514'
expected_size = 3369633312
target = Path('D:/BAXYRuntime/experiments/models/qwen3-8b-iq3-xxs-0b69f75b') / name
out = root/'artifacts/comprobaciones/C03/astra-qwen8-iq3-candidate'
out.mkdir(parents=True, exist_ok=True)
target.parent.mkdir(parents=True, exist_ok=True)
url = f'https://huggingface.co/bartowski/Qwen_Qwen3-8B-GGUF/resolve/{revision}/{name}'
record = {'kind': 'single-quant-candidate-not-promotion', 'revision': revision,
          'url': url, 'target': str(target), 'expectedSha256': expected_sha,
          'expectedBytes': expected_size,
          'hypothesis': 'Inherited Qwen8 Q4 composition is better natively but partial CPU loading causes 4s composition and 17s interpretation timeouts. A single IQ3_XXS with ngl30 and q4_0 KV may keep the same 8B mostly on GPU within total4096MiB. No quant sweep; reject if resource or semantic quality fails.',
          'profileToMeasure': {'ngl': 30, 'kv': 'q4_0', 'maxGpuMiB': 4096,
                               'sampling': {'temperature': .7, 'top_p': .8, 'top_k': 20, 'min_p': 0}},
          'status': 'downloading'}
(out/'DOWNLOAD.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
started = time.monotonic()
if target.exists():
    digest = hashlib.file_digest(target.open('rb'), 'sha256').hexdigest()
    assert target.stat().st_size == expected_size and digest == expected_sha
    record['status'] = 'reused_verified'
else:
    partial = target.with_suffix('.gguf.part')
    digest = hashlib.sha256()
    count = 0
    with urllib.request.urlopen(url, timeout=45) as response, partial.open('wb') as stream:
        while chunk := response.read(4 * 1024 * 1024):
            stream.write(chunk)
            digest.update(chunk)
            count += len(chunk)
    assert count == expected_size, (count, expected_size)
    assert digest.hexdigest() == expected_sha, digest.hexdigest()
    partial.replace(target)
    record['status'] = 'downloaded_verified'
record['elapsedSeconds'] = round(time.monotonic() - started, 2)
(out/'DOWNLOAD.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record), flush=True)
