"""Download one pinned higher-precision variant of the registered Qwen checkpoint without altering the runtime."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
out = root / 'artifacts/comprobaciones/C03/astra-qwen-q8-download478'
asset = Path('D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-q8-a06e946b')
out.mkdir(exist_ok=False)
asset.mkdir(exist_ok=False)
repo = 'unsloth/Qwen3-4B-Instruct-2507-GGUF'
revision = 'a06e946bb6b655725eafa393f4a9745d460374c9'
filename = 'Qwen3-4B-Instruct-2507-Q8_0.gguf'
expected_size = 4280405600
expected_sha = '391c1e410fd9f4cf2de2b510273b56a84c19ce18f4fa3bfb3774031dac4ef068'
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
    'rationale': 'Isolate weight precision of the exact registeredQwen2507 checkpoint, not another model family. Same quantizer repository/revision as Q4 already verified. All recent Qwen2507 tests used Q4_K_M weights. Earlier files named q8 changed KV cache, not weights (their PREREGISTRO model fields checked). Task-duty/protocol factors472/473/474/476 failed to yield a complete candidate; stop wording changes. Determine whether weight quantization contributes before blaming the full model. Q8 is higher precision, not a presumed optimum or pass.',
    'inheritance': 'biblioteca/carter/docs/investigaciones/investigaciones/investigacionesopus/03_Optimizacion_Ollama_qwen3_ultimo_10_porciento.md:195-215 proposes Q6/Q8 but explicitly forecasts unmeasured benefits on16GB4060Ti/Ollama. Its community opinion is not a reproduction and percentages are not adopted. Current exact GGUF inventory has no2507Q8 in models/assets. Earlier astra-native-probe-q8 and astra-native-qwen35-thinking-q8-natural-stop PREREGISTRO still use Q4_K_M weights.',
    'sources': ['https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507','https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF','https://github.com/QwenLM/Qwen3/blob/main/docs/source/quantization/llama.cpp.md','https://arxiv.org/abs/2505.02214','https://arxiv.org/abs/2601.14277'],
    'source_limits': 'Qwen May2025 paper covers other posttraining/quantization settings and predates2507; Llama January2026 study is another8B model/CPU. Neither proves thisGGUF improves BAXY. Qwen documentation warns mixtures can fail and perplexity data is not instruction-following evaluation. Use matched local semantic comparisons, not perplexity as acceptance.',
    'plan': 'Download one exactQ8_0 artifact with SHA/size verification. On resource qualification start NGL26 for both Q4 and Q8, same b10809, context4096x3/KVq8/b2048/ub256/cache0/no-mmap and official T.7/.8/k20/min0/neutral penalties/seed0,17. This holds CPU/GPU placement policy constant while varying precision; also retain allGPU468 as existing reference. Guard actualGPU3800MiB/freeRAM768MiB; no other apps closed, no silent context/cache precision reduction. Q8 needs RAM; qualify before quality. Same guarded composer source466 and6confirmation fixtures plus2memory controls (ESsavedname/ENprotectedrecord) per seed, no472/474 changes. All baseline/variant outputs and finish reasons retained; no source/runtime promotion without broader integrated quality/resources.',
    'repo': repo, 'revision': revision, 'filename': filename, 'url': url,
    'size': expected_size, 'sha256': expected_sha, 'destination': str(asset / filename),
    'manifest_sha256': initial, 'source_state': '466 validated1404owners/0skips/Fast3.66s, no later product edits',
})
for label, source in {
    'OFFICIAL_README.md': 'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/raw/main/README.md',
    'GENERATION_CONFIG.json': 'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/raw/main/generation_config.json',
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
