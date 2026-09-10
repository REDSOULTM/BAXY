"""Attribute790 using the same captured response sequence on787 and789."""
from collections import defaultdict
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-inventory-identity790-replay-private'
CAPTURE = PRIVATE.parent / 'C03-inventory-composer790-private'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


if '--worker' in sys.argv:
    mode = sys.argv[-1]
    sys.path[:0] = [str(PRIVATE / 'baseline') if mode == 'baseline' else str(ROOT / 'src'), str(ROOT)]
    from baxy_mind.llm import LlmRuntime
    cases = read(CAPTURE / 'cases.json')
    responses = defaultdict(list)
    for line in (CAPTURE / 'posts.jsonl').read_text(encoding='utf-8').splitlines():
        post = json.loads(line)
        responses[post['id']].append(post)

    class Replay(LlmRuntime):
        def __init__(self, posts):
            self._gguf = 'Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
            self.responses = [p['response'] for p in posts]
            self.requests = []

        def _post(self, payload):
            self.requests.append(copy.deepcopy(payload))
            return copy.deepcopy(self.responses[min(len(self.requests) - 1, len(self.responses) - 1)])

    rows = []
    for case in cases:
        client = Replay(responses[case['id']])
        answer = client.compose_user_message(case['request'], 'status', {'situation': json.dumps(case['situation'], ensure_ascii=False), 'requiredResponseWords': []})
        rows.append({'case_id': case['id'], 'answer': answer, 'requests': client.requests})
    (PRIVATE / (mode + '.json')).write_bytes((json.dumps(rows, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    raise SystemExit(0)

assert not PRIVATE.exists()
snapshot = Path(read(BASE / 'INVENTORY_BUDGET787/SOURCE_SNAPSHOT.json')['private_directory'])
pins = read(BASE / 'INVENTORY_BUDGET787/SOURCE_PINS.json')
package = PRIVATE / 'baseline/baxy_mind'
package.mkdir(parents=True)
for name in ['llm.py', 'window_prose_facts.py']:
    relative = 'src/baxy_mind/' + name
    assert sha(snapshot / relative) == pins[relative]
    (package / name).write_bytes((snapshot / relative).read_bytes())
original_init = (ROOT / 'src/baxy_mind/__init__.py').read_text(encoding='utf-8')
(package / '__init__.py').write_bytes((original_init + '\n__path__.append(' + repr(str(ROOT / 'src/baxy_mind')) + ')\n').encode('utf-8'))
for mode in ['baseline', 'candidate']:
    subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), '--worker', mode], cwd=ROOT,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
before, after = read(PRIVATE / 'baseline.json'), read(PRIVATE / 'candidate.json')
rows = []
for a, b in zip(before, after, strict=True):
    assert a['case_id'] == b['case_id'] and a['requests'][0] == b['requests'][0]
    rows.append({'case_id': a['case_id'], 'same_final': a['answer'] == b['answer'],
                 'same_requests': a['requests'] == b['requests'],
                 'baseline_posts': len(a['requests']), 'candidate_posts': len(b['requests']),
                 'baseline_empty': not a['answer'], 'candidate_empty': not b['answer']})
out = BASE / 'INVENTORY_COMPOSER790/CAUSAL_REPLAY.json'
assert not out.exists()
record = {'method': 'Same captured790 HTTP response sequence replayed on preserved787 and789; no inference or deadlines. If more replies are requested than captured, repeat the final captured reply. Isolates transformations, not real latency.',
          'first_payloads_equal': 50, 'rows': rows, 'private_directory': str(PRIVATE),
          'private_files': {name: sha(PRIVATE / name) for name in ['baseline.json', 'candidate.json']}}
out.write_bytes((json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print(json.dumps([r for r in rows if not r['same_final'] or r['case_id'] in ['inventory785-4-1', 'inventory785-2-3']]))
