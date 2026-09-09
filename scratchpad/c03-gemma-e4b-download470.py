"""Download one justified, pinned E4B GGUF without altering the runtime."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-gemma-e4b-download470'
asset = Path('D:/BAXYRuntime/experiments/models/gemma4-e4b-q4-bfc15c38')
out.mkdir(exist_ok=False)
asset.mkdir(exist_ok=False)
repo = 'unsloth/gemma-4-E4B-it-GGUF'
revision = 'bfc15c382204943c3a8fff0c750b94ae2364d7a3'
filename = 'gemma-4-E4B-it-Q4_K_M.gguf'
expected_size = 4977171584
expected_sha = '85a896a047553e842f25297ee5b031d64ff30147d9c4af17b1e4b394cd1fab87'
url = f'https://huggingface.co/{repo}/resolve/{revision}/{filename}'
manifest = Path(os.environ['LOCALAPPDATA']) / 'BAXYRuntime/mind-runtime-v1.json'
initial = hashlib.sha256(manifest.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


metadata = json.load(urllib.request.urlopen(f'https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true', timeout=30))
entry = next(s for s in metadata['siblings'] if s['rfilename'] == filename)
assert metadata['sha'] == revision and entry['size'] == expected_size and entry['lfs']['sha256'] == expected_sha
write(out / 'MODEL_METADATA.json', metadata)
write(out / 'PREREG.json', {
    'utc': datetime.now(timezone.utc).isoformat(),
    'rationale': 'One new candidate justified by measured lazy PLE support462/464, not an arbitrary model collection. Official Gemma4 report/model card gives E4B4.5B effective vsE2B2.3B and stronger instruction/agentic-related benchmarks; these are not GGUF/BAXY guarantees. TextGGUF4.98GB contains large PLE that can remain CPU-mapped under --lazy-mode on, so file size is not VRAM demand. Need actual <=3800MiB diagnostic guard before quality runs. Existing E2B profiles465/467 and Qwen468/469 do not meet all confirmations.',
    'inheritance': 'biblioteca/carter/docs/investigaciones/investigaciones/investigacionesopus/02_Gemma4_E2B_E4B_evaluacion.md lines4-6/47-54/201-205 concerns Ollama0.20.4 package with multimodal encoders, old backend and other GPU; does not measure current textGGUF with new lazy PLE. 12_OPT_GEMMA4_DOSSIER.md concerns E4BUD-IQ2_M/b9090/4060Ti16GB. Existing model assets under D:/BAXYRuntime/experiments/models and assets/models contain no E4BGGUF (bounded filename inventory). No changes to legacy repos.',
    'sources': ['https://huggingface.co/google/gemma-4-E4B-it', 'https://arxiv.org/html/2607.02770v1', 'https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF', 'https://github.com/ggml-org/llama.cpp/pull/27794', 'https://github.com/ggml-org/llama.cpp/pull/27837'],
    'plan': 'Download and verify one exactQ4_K_M artifact. No adapter, mmproj or ASR replacement. Qualify actual buffers/VRAM/RAM on RTX3060Laptop using b10809 stable, no-mmap/cache0/lazyon,4096x3,KVq8,b2048/ub256 initially. Official sampler T1/p.95/k64/min0/neutralpenalties; test no-thinking and thinking distinctly with adequate recorded budget. Adjust allocation/batch if measured need without changing precision/context silently. First two local development cases, then existing memory/confirmation controls if hardware fits. No promotion before integrated quality/allroles/resources.',
    'repo': repo, 'revision': revision, 'filename': filename, 'url': url,
    'size': expected_size, 'sha256': expected_sha, 'destination': str(asset / filename),
    'manifest_sha256': initial, 'source_state': '466 validated1404owners/0skips/Fast3.66s, no later product edits',
})
for label, source in {
    'OFFICIAL_README.md': 'https://huggingface.co/google/gemma-4-E4B-it/raw/main/README.md',
    'GENERATION_CONFIG.json': 'https://huggingface.co/google/gemma-4-E4B-it/raw/main/generation_config.json',
    'QUANTIZER_README.md': f'https://huggingface.co/{repo}/raw/{revision}/README.md',
}.items():
    (out / label).write_bytes(urllib.request.urlopen(source, timeout=30).read())
partial = asset / (filename + '.partial')
final = asset / filename
digest = hashlib.sha256()
size = 0
started = time.monotonic()
next_mark = 0
with urllib.request.urlopen(url, timeout=90) as response, partial.open('xb') as handle:
    while chunk := response.read(8 * 1024 * 1024):
        handle.write(chunk)
        digest.update(chunk)
        size += len(chunk)
        percent = int(100 * size / expected_size)
        if percent >= next_mark:
            print(json.dumps({'download_percent': percent, 'bytes': size, 'seconds': round(time.monotonic() - started, 1)}), flush=True)
            next_mark = (percent // 10 + 1) * 10
assert size == expected_size and digest.hexdigest() == expected_sha
assert not final.exists()
partial.replace(final)
result = {'downloaded': True, 'size': size, 'sha256': digest.hexdigest(), 'seconds': round(time.monotonic() - started, 3), 'path': str(final), 'manifest_unchanged': hashlib.sha256(manifest.read_bytes()).hexdigest() == initial, 'hardware_quality_tested': False}
assert result['manifest_unchanged']
write(asset / 'DOWNLOAD.json', {'repo': repo, 'revision': revision, 'filename': filename, 'size': size, 'sha256': expected_sha})
write(asset / 'VERIFIED.json', result)
write(out / 'RESULT.json', result)
write(out / 'PINS.json', {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name != 'PINS.json'})
print(json.dumps(result), flush=True)
