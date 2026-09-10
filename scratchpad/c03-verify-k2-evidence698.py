"""Verify provenance, paired review accounting and report links before publication."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import py_compile
import re
import subprocess

root = Path(__file__).resolve().parents[1]
base = root/'artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696'
out = root/'artifacts/comprobaciones/C03/K2_HORIZON_LATENCY697'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

summary = read(out/'SUMMARY698.json')
assert len(summary['records']) == 19 and summary['evaluable_completed_outputs'] == 860
checks = []
for tag, record in summary['records'].items():
    folder = base/('run-'+tag)
    private = Path(os.environ['LOCALAPPDATA'])/f'BAXY/C03-k2-run696-{tag}-private'
    adj, metrics, prereg = read(folder/'ADJUDICATION.json'), read(folder/'MEASUREMENTS.json'), read(folder/'PREREG.json')
    assert metrics['results_sha256'] == sha(private/'results.jsonl')
    assert adj['private_review_sha256'] == sha(private/'review.json')
    assert prereg['driver_sha256'] == sha(private/'driver.py')
    review = read(private/'review.json')
    assert [r['verdict'] for r in review] == adj['rows']
    assert sum(r['pass'] for r in adj['rows']) == adj['pass']
    assert len(review) == adj['pass']+adj['fail'] == metrics['responses']
    failed = {r['id'] for r in adj['rows'] if not r['pass']}
    assert set(metrics['errors']) <= failed
    assert metrics['resources']['manifest_unchanged'] and not metrics['resources']['violations']
    assert metrics['resources']['gpu_peak_mib'] < 4096
    if 'parser698' in tag:
        parity = [json.loads(line) for line in (folder/'TEMPLATE_PARITY.jsonl').read_text().splitlines()]
        assert len(parity) == 50 and all(r['suffix_matches'] for r in parity)
    if not tag.startswith('qwen'):
        parity = read(folder/'TOKENIZER_PARITY.json')
        assert parity['equal'] == parity['cases'] == 285 and parity['mismatches'] == 0
    checks.append({'tag':tag,'responses':len(review),'verified':True})
receipt = read(out/'BACKEND_BUILD698.json')
fork = Path('D:/BAXYRuntime/build/llama-k2-horizon-35999d1')
for name, expected in receipt['source_files'].items():
    assert sha(fork/name) == expected
for name, expected in receipt['backend_files'].items():
    assert sha(fork/'build-cuda13-sm86/bin'/name) == expected['sha256']
assert sha(out/receipt['patch']) == receipt['patch_sha256']
assert sha(Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime/mind-runtime-v1.json') == summary['decision']['production_manifest_sha256']
report = (out/'REPORTE_FINAL.md').read_text(encoding='utf-8')
local_links = re.findall(r'\]\(<([A-Z]:/[^>]+)>\)',report)
assert local_links and all(Path(p).is_file() for p in local_links)
assert '%20' not in report and 'C 03' not in report and '{decision' not in report
scripts = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','--','scratchpad'],text=True).splitlines()
owned = [Path(p) for p in scripts if Path(p).suffix == '.py' and (
    re.match(r'c03-(?:k2-|adjudicate-k2-|review-k2-|report-k2-|seal-k2-|checkpoint-k2-|close-k2-|verify-k2-|prepare-k2-)',Path(p).name)
    or Path(p).name == 'c03_k2_tokenizer_parity696.py')]
for script in owned:
    py_compile.compile(str(script),doraise=True)
result = {'utc':datetime.now(timezone.utc).isoformat(),'panels':checks,'results_verified':860,
    'backend_files_verified':len(receipt['backend_files']),'source_files_verified':len(receipt['source_files']),
    'local_report_links_verified':len(local_links),'diagnostic_python_files_compiled':len(owned),
    'manifest_unchanged':True,'report_sha256':sha(out/'REPORTE_FINAL.md'),
    'scope':'Evidence/provenance validation, not BAXY Full or C03 acceptance.'}
(out/'EVIDENCE_VALIDATION698.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='panels'}))
