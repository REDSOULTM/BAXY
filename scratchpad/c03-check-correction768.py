"""Check factual acceptance parity over the existing767 captured window drafts."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from baxy_mind.window_prose_facts import window_fact_defect, window_fact_feedback

baseline_commit = 'b2983c075b98f401fc9f49ba7bcd1980a2e2bf04'
baseline_bytes = subprocess.check_output(['git', 'show', baseline_commit + ':src/baxy_mind/window_prose_facts.py'])
baseline = {'__name__': 'baxy_mind.window_prose_baseline768', '__package__': 'baxy_mind'}
exec(compile(baseline_bytes, '<window-baseline766>', 'exec'), baseline)
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-status-batch767-private'
review_path = private / 'review.json'
review = json.loads(review_path.read_text(encoding='utf-8-sig'))
unique = set()
outcomes = Counter()
feedback_count = 0
for row in review:
    for draft in row['compose']:
        payload = draft.get('payload')
        text = draft.get('draft')
        if not isinstance(payload, dict) or not isinstance(text, str) or not str(payload.get('operation', '')).startswith('window.'):
            continue
        key = json.dumps([row['text'], text, payload], ensure_ascii=False, sort_keys=True)
        if key in unique:
            continue
        unique.add(key)
        before = baseline['window_fact_defect'](text, payload, row['text'])
        after = window_fact_defect(text, payload, row['text'])
        assert before == after, (row['case_id'], before, after)
        outcomes[after or 'accepted_by_window_facts'] += 1
        feedback = window_fact_feedback(text, payload, row['text'])
        if feedback is not None and 'unsupported_claim' in feedback:
            assert before == 'extra_claim'
            assert feedback['rejected_draft'] == text
            feedback_count += 1
assert unique and feedback_count
result = {'baseline_commit': baseline_commit,
    'baseline_window_source_sha256': hashlib.sha256(baseline_bytes).hexdigest(),
    'review_sha256': hashlib.sha256(review_path.read_bytes()).hexdigest(),
    'unique_captured_window_drafts': len(unique), 'decisions_unchanged': True,
    'outcomes': dict(outcomes), 'unsupported_chronology_feedback_added': feedback_count,
    'scope': 'Offline deterministic window fact checker only; not new model inference, full response acceptance or coverage.'}
target = ROOT / 'artifacts/comprobaciones/C03/INVENTORY_CORRECTION768/CAPTURED_PARITY.json'
assert not target.exists()
target.write_bytes((json.dumps(result, indent=2) + '\n').encode('utf-8'))
print(json.dumps(result))
