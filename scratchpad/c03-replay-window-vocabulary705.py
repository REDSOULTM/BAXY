"""Replay preserved native drafts through current validation; never infer or claim fresh acceptance."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root/'src'), str(root/'tests')]
from test_c03_window_state_facts import Recorder

out = root/'artifacts/comprobaciones/C03/astra-window-vocabulary-source705'
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-window-vocabulary705-private'
private.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
write = lambda p, v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
terms = ['planner', 'router', 'tool', 'catálogo', 'catalogo', 'schema', 'operación', 'operacion',
         'capacidad interna', 'language model', 'modelo de lenguaje', 'qwen', 'resolver el efecto',
         "el efecto '", 'opaque identity', 'observed profile', 'grounding', 'checkpoint',
         'reconciliación', 'reconciliacion', 'motor local', 'core', 'datos verificables',
         'pasos verificables', 'identificador interno']
rows = []
inputs = {}
for campaign, case_id in [(694, 'H0104'), (704, 'windows-focus-mixed')]:
    path = Path(os.environ['LOCALAPPDATA'])/f'BAXY/C03-status-batch{campaign}-private/review.json'
    inputs[str(campaign)] = sha(path)
    row, = [r for r in json.loads(path.read_text(encoding='utf-8-sig')) if r['case_id'] == case_id]
    for index, compose in enumerate(row['compose']):
        draft = compose['draft']
        facts = {'situation': compose['situation'], 'forbiddenResponseTerms': terms,
                 'mustNotAskFollowUp': True}
        client = Recorder([draft] * 3)
        result = client.compose_user_message(row['text'], 'status', facts)
        rows.append({'campaign': campaign, 'case_id': case_id, 'compose_index': index,
                     'source_stage': compose['stage'], 'previous_reason': compose['reason'],
                     'request': row['text'], 'facts': facts, 'draft': draft,
                     'draft_sha256': hashlib.sha256(draft.encode()).hexdigest(),
                     'replayed_text': result, 'accepted_identical': result == draft,
                     'fixture_calls': len(client.requests)})
write(private/'REPLAY.json', rows)
counts = {str(c): {'draft_occurrences': sum(r['campaign'] == c for r in rows),
                  'accepted_identical': sum(r['campaign'] == c and r['accepted_identical'] for r in rows),
                  'unique_drafts': len({r['draft_sha256'] for r in rows if r['campaign'] == c})}
          for c in [694, 704]}
receipt = {'utc': datetime.now(timezone.utc).isoformat(), 'source_reviews': inputs,
           'private_replay_sha256': sha(private/'REPLAY.json'), 'counts': counts,
           'method': 'Preserved native drafts, current composer in a deterministic Recorder. Each rejected draft is repeated up to the existing three attempts to reveal validation outcome; these are not new model calls, new user tests, or a reconstruction of every original HTTP parameter. Source situation/request and full C# forbidden-term list retained. No public prose altered.',
           'new_coverage': 0, 'goal_complete': False}
write(out/'REPLAY.json', receipt)
print(counts)
