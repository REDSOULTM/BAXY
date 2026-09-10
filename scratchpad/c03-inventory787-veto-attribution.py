"""Read-only composer replay: original HEAD versus sealed787, no model calls."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-inventory787-attribution-private'
CAPTURE = PRIVATE.parent / 'C03-inventory-composer788-private'


if '--worker' in sys.argv:
    mode = sys.argv[-1]
    sys.path[:0] = [str(PRIVATE / 'baseline') if mode == 'baseline' else str(ROOT / 'src'), str(ROOT)]
    from baxy_mind.llm import LlmRuntime, _compose_situation_payload, _payload_fact_defect, compose_visible_defect
    cases = json.loads((CAPTURE / 'cases.json').read_text(encoding='utf-8'))
    posts = [json.loads(l) for l in (CAPTURE / 'posts.jsonl').read_text(encoding='utf-8').splitlines()]
    first = {}
    for post in posts:
        first.setdefault(post['id'], post)

    class Replay(LlmRuntime):
        def __init__(self, response):
            self._gguf = 'Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
            self.response = response
            self.requests = []
        def _post(self, payload):
            self.requests.append(copy.deepcopy(payload))
            return copy.deepcopy(self.response)

    rows = []
    for case in cases:
        response = first[case['id']]['response']
        raw = response['choices'][0]['message']['content']
        client = Replay(response)
        facts = {'situation': case['situation']}
        answer = client.compose_user_message(case['request'], 'status', facts)
        projected = _compose_situation_payload(case['situation'], 'es', case['request'])
        rows.append({'case_id': case['id'], 'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                     'raw_delivered_in_one_post': answer == raw.strip() and len(client.requests) == 1,
                     'posts': len(client.requests), 'returned': answer,
                     'payload_defect': _payload_fact_defect(raw, projected, case['request']),
                     'visible_defect': compose_visible_defect(raw, 'status', case['request'], facts)})
    (PRIVATE / f'{mode}.json').write_bytes((json.dumps(rows, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    raise SystemExit(0)

assert not PRIVATE.exists()
package = PRIVATE / 'baseline/baxy_mind'
package.mkdir(parents=True)
snapshots = {}
for name in ['llm.py', 'window_prose_facts.py']:
    relative = 'src/baxy_mind/' + name
    raw = subprocess.check_output(['git', 'show', 'HEAD:' + relative], cwd=ROOT)
    (package / name).write_bytes(raw)
    snapshots[relative] = hashlib.sha256(raw).hexdigest()
original_init = subprocess.check_output(['git', 'show', 'HEAD:src/baxy_mind/__init__.py'], cwd=ROOT).decode('utf-8')
(package / '__init__.py').write_bytes((original_init + '\n__path__.append(' + repr(str(ROOT / 'src/baxy_mind')) + ')\n').encode('utf-8'))
for mode in ['baseline', 'candidate']:
    subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), '--worker', mode], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
baseline = json.loads((PRIVATE / 'baseline.json').read_text(encoding='utf-8'))
candidate = json.loads((PRIVATE / 'candidate.json').read_text(encoding='utf-8'))
rows = []
for before, after in zip(baseline, candidate, strict=True):
    assert before['case_id'] == after['case_id'] and before['raw_sha256'] == after['raw_sha256']
    rows.append({'case_id': before['case_id'], 'baseline_delivers_raw': before['raw_delivered_in_one_post'],
                 'candidate_delivers_raw': after['raw_delivered_in_one_post'],
                 'baseline_payload_defect': before['payload_defect'], 'candidate_payload_defect': after['payload_defect'],
                 'baseline_visible_defect': before['visible_defect'], 'candidate_visible_defect': after['visible_defect']})
report = {'method': 'Same50 raw first responses from788 replayed against HEAD1e997b9c runtime and sealed787. Stub supplies same raw regardless of output cap: isolates validation only, no inference/latency/product acceptance.',
          'baseline_source': snapshots, 'gained': [r['case_id'] for r in rows if not r['baseline_delivers_raw'] and r['candidate_delivers_raw']],
          'lost': [r['case_id'] for r in rows if r['baseline_delivers_raw'] and not r['candidate_delivers_raw']],
          'rows': rows, 'private_directory': str(PRIVATE)}
out = BASE / 'INVENTORY_COMPOSER788/VALIDATOR_ATTRIBUTION.json'
assert not out.exists()
out.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print(json.dumps({k: report[k] for k in ['gained', 'lost']}))
