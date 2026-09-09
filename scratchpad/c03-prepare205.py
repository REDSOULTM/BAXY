"""Freeze proposed native decoder repair before local inference."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import urllib.request

root = Path(__file__).resolve().parents[1]
out = root/'artifacts/comprobaciones/C03/astra-sherpa205'
out.mkdir(exist_ok=False)
source = Path('D:/BAXYRuntime/experiments/voice/sherpa205/source')
def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'BAXY-local-decoder-investigation'})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()
def save(name, value):
    (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
pr = json.loads(fetch('https://api.github.com/repos/k2-fsa/sherpa-onnx/pulls/3657'))
save('UPSTREAM.json', {key: pr[key] for key in ['html_url','state','merged','created_at','updated_at','head','base']})
patch = fetch('https://github.com/k2-fsa/sherpa-onnx/pull/3657.diff')
(out/'upstream3657.patch').write_bytes(patch)
owner = source/'sherpa-onnx/csrc/offline-transducer-modified-beam-search-nemo-decoder.cc'
save('PREREG.json', {
    'createdAtUtc': datetime.now(timezone.utc).isoformat(),
    'sourceTag': 'v1.13.4', 'sourceCommit': '142807252687d81b40d6315f23470a1512a00de3',
    'patchHead': pr['head']['sha'], 'patchSha256': hashlib.sha256(patch).hexdigest(),
    'originalDecoderSha256': hashlib.sha256(owner.read_bytes()).hexdigest(),
    'method': 'Build unchanged native Python library from exact version first. Compare frozen42 product segments, four originals and silence with installed202/203. Apply upstream3657 patch, rebuild same target/dependencies and repeat same47 controls. Preserve all outputs. Use beam8 CPU6 unchanged. No product/runtime promotion on merely better aggregate; inspect lost words and contextual/wake behavior.',
    'context': '203 greedy recovers three human blanks;204 duplicate native contexts cost729MiB extra RSS and6.204s construction. Prefer one model if native beam defect can be repaired. Prior failed204 import ended before output/model load; retry complete.',
    'limitation': 'Upstream PR is unmerged/unvalidated. Existing1.13.4 already advances blank at least one frame; actual patch changes duration scoring and TDT symbol limit, not a newly added blank guard. Build uses source-pinned ONNX Runtime1.27.0; compare local baseline before attributing results to patch. No devices or app effects.',
})
print(json.dumps({'head': pr['head']['sha'], 'merged': pr['merged'], 'patchBytes': len(patch)}))
