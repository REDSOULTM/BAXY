"""Verify paired payload fidelity and expose changed answers for root review."""
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'INVENTORY_COMPOSER792'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-inventory-composer792-private'
OLD = PRIVATE.parent / 'C03-inventory-composer790-private'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def rows(path):
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


plan, run = read(OUT / 'PREREG.json'), read(OUT / 'RESULT.json')
assert run['fatal'] is None and not run['violations'] and run['executions_completed'] == 100
assert all(run[k] for k in ['source_pins_unchanged', 'sources_unchanged', 'manifest_unchanged', 'driver_unchanged'])
assert all(sha(ROOT / p) == h for p, h in plan['source_pins'].items())
cases = read(PRIVATE / 'cases.json')
replies, posts, attempts = [rows(PRIVATE / name) for name in ['replies.jsonl', 'posts.jsonl', 'attempts.jsonl']]
old_replies = {r['id']: r for r in rows(OLD / 'replies.jsonl')}
old_raw = defaultdict(set)
for row in rows(OLD / 'posts.jsonl'):
    old_raw[row['id']].add(row['response']['choices'][0]['message']['content'])
expected = read(PRIVATE / 'expected-first.json')
assert expected == read(OLD / 'expected-first.json')
assert sha(PRIVATE / 'cases.json') == sha(OLD / 'cases.json') == plan['case_sha256']
expected_order = [(case['id'], arm) for index, case in enumerate(cases) for arm in (('A', 'B') if index % 2 == 0 else ('B', 'A'))]
assert [(r['id'], r['arm']) for r in replies] == expected_order
events = defaultdict(list)
for event in attempts:
    events[(event['id'], event['arm'], event['attempt'])].append(event)
for key, history in events.items():
    assert [r['state'] for r in history] in (['started', 'succeeded'], ['started', 'failed']), key
    event = history[0]
    original, payload = event['original_payload'], event['payload']
    if key[2] == 1:
        assert original == payload == expected[key[0]] and not event['removed']
    if key[1] == 'A':
        assert original == payload and not event['removed']
    else:
        reconstructed = json.loads(json.dumps(payload))
        for item in event['removed']:
            index = item['message_index']
            old_content = original['messages'][index]['content']
            new_content = payload['messages'][index]['content']
            marker = '\nVerified factual correction: '
            before, rest = old_content.rsplit(marker, 1)
            old_correction, old_end = json.JSONDecoder().raw_decode(rest)
            new_before, new_rest = new_content.rsplit(marker, 1)
            new_correction, new_end = json.JSONDecoder().raw_decode(new_rest)
            assert before == new_before and rest[old_end:] == new_rest[new_end:]
            assert old_correction.pop('rejected_draft') == item['rejected_draft']
            assert old_correction == new_correction
            reconstructed['messages'][index]['content'] = old_content
        assert reconstructed == original
by_case = defaultdict(list)
for post in posts:
    key = (post['id'], post['arm'])
    by_case[key].append(post)
    history = events[(*key, post['attempt'])]
    assert history[-1]['state'] == 'succeeded' and history[0]['payload'] == post['payload']
    slot = max((s for s in post['slots_after'] if 'id_task' in s), key=lambda s: s['id_task'])
    wanted = {'temperature': 0., 'top_k': 40, 'top_p': .95, 'min_p': .05, 'seed': 4294967295,
              'presence_penalty': 0., 'repeat_penalty': 1., 'max_tokens': post['payload']['max_tokens'],
              'n_predict': post['payload']['max_tokens']}
    assert all(math.isclose(slot['params'][k], v, rel_tol=1e-6, abs_tol=1e-7) for k, v in wanted.items())
    assert slot['n_ctx'] == 4096 and slot['n_prompt_tokens_cache'] == 0
first = lambda key: by_case[key][0]['response']['choices'][0]['message']['content']
first_parity = [c['id'] for c in cases if first((c['id'], 'A')) == first((c['id'], 'B'))]
reply_map = {(r['id'], r['arm']): r for r in replies}
changes = [r for r in replies if (r['answer'], r['error']) != (old_replies[r['id']]['answer'], old_replies[r['id']]['error'])]
novel = [p for p in posts if p['response']['choices'][0]['message']['content'] not in old_raw[p['id']]]
summary = {'executions': len(replies), 'posts': len(posts), 'attempt_states': dict(Counter(e['state'] for e in attempts)),
           'first_payload_parity': 100, 'first_raw_pair_parity': len(first_parity),
           'first_raw_different_cases': [c['id'] for c in cases if c['id'] not in first_parity],
           'effective_params_verified': len(posts),
           'paired_final_different_cases': [c['id'] for c in cases if (reply_map[(c['id'],'A')]['answer'], reply_map[(c['id'],'A')]['error']) != (reply_map[(c['id'],'B')]['answer'], reply_map[(c['id'],'B')]['error'])],
           'changed_from790': [{'id': r['id'], 'arm': r['arm']} for r in changes],
           'novel_raw_outputs': len(novel),
           'B_attempts_with_intervention': sum(bool(e.get('removed')) for e in attempts if e['state'] == 'started')}
path = OUT / 'PARITY.json'; assert not path.exists()
path.write_bytes((json.dumps(summary, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
sections = ['# Respuestas nuevas por revisar — 792\n']
for case in cases:
    key = case['id']
    if not any(r['id'] == key for r in changes) and not any(p['id'] == key for p in novel):
        continue
    sections += [f'## {key}\n', 'Petición: ' + case['request'], 'Criterio: ' + case['criterion'],
                 '```json\n' + json.dumps(case['situation'], ensure_ascii=False, indent=2) + '\n```']
    for arm in ['A', 'B']:
        r = reply_map[(key, arm)]
        sections += [f"### Final {arm}: {r['seconds']:.3f}s / {r['attempts']} intentos / error {r['error']}\n",
                     '```text\n' + (r['answer'] or '') + '\n```']
        for post in by_case[(key, arm)]:
            if post not in novel:
                continue
            sections += [f"Intento {post['attempt']}:\n", '```text\n' + post['response']['choices'][0]['message']['content'] + '\n```']
path = PRIVATE / 'REVIEW.md'; assert not path.exists()
path.write_bytes(('\n\n'.join(sections) + '\n').encode('utf-8'))
print(json.dumps(summary, ensure_ascii=False))
print(str(path))
