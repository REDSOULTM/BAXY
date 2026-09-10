"""Adjudicate single-model integration; adopt the measured shared-veto repair."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'INVENTORY_COMPOSER794'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-inventory-composer794-private'
OLD = PRIVATE.parent / 'C03-inventory-composer792-private'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def lines(path):
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def write(path, value):
    assert not path.exists(), path
    content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    path.write_bytes(content.encode('utf-8'))


run, plan = read(OUT / 'RESULT.json'), read(OUT / 'PREREG.json')
assert run['fatal'] is None and not run['violations'] and run['cases_completed'] == 50
assert all(run[k] for k in ['source_pins_unchanged', 'sources_unchanged', 'manifest_unchanged', 'driver_unchanged'])
assert all(sha(ROOT / p) == h for p, h in plan['source_pins'].items())
cases, replies, posts, attempts = read(PRIVATE / 'cases.json'), lines(PRIVATE / 'replies.jsonl'), lines(PRIVATE / 'posts.jsonl'), lines(PRIVATE / 'attempts.jsonl')
old = {r['id']: r for r in lines(OLD / 'replies.jsonl') if r['arm'] == 'A'}
old_judged = {r['case_id']: r for r in read(BASE / 'INVENTORY_COMPOSER792/ADJUDICATION.json')['rows'] if r['arm'] == 'A'}
old_raw = defaultdict(set)
for r in lines(OLD / 'posts.jsonl'):
    old_raw[r['id']].add(r['response']['choices'][0]['message']['content'])
assert sha(PRIVATE / 'cases.json') == sha(OLD / 'cases.json')
expected = read(PRIVATE / 'expected-first.json')
assert expected == read(OLD / 'expected-first.json')
events, by_case = defaultdict(list), defaultdict(list)
for event in attempts:
    events[(event['id'], event['attempt'])].append(event)
for key, history in events.items():
    assert [e['state'] for e in history] in (['started', 'succeeded'], ['started', 'failed'])
    if key[1] == 1:
        assert history[0]['payload'] == expected[key[0]]
for post in posts:
    by_case[post['id']].append(post)
    history = events[(post['id'], post['attempt'])]
    assert history[0]['payload'] == post['payload'] and history[-1]['state'] == 'succeeded'
    slot = max((s for s in post['slots_after'] if 'id_task' in s), key=lambda s: s['id_task'])
    wanted = {'temperature': 0., 'top_k': 40, 'top_p': .95, 'min_p': .05, 'seed': 4294967295,
              'presence_penalty': 0., 'repeat_penalty': 1., 'max_tokens': post['payload']['max_tokens'],
              'n_predict': post['payload']['max_tokens']}
    assert all(math.isclose(slot['params'][k], v, rel_tol=1e-6, abs_tol=1e-7) for k, v in wanted.items())
    assert slot['n_ctx'] == 4096 and slot['n_prompt_tokens_cache'] == 0
    assert post['response']['choices'][0]['message']['content'] in old_raw[post['id']]
recovered = {'inventory785-1-3', 'inventory785-1-4', 'inventory785-2-2', 'inventory785-4-1'}
rows, changed = [], []
for case, reply in zip(cases, replies, strict=True):
    key = case['id']; assert key == reply['id']
    prior = old_judged[key]
    same = (reply['answer'], reply['error']) == (old[key]['answer'], old[key]['error'])
    if not same:
        changed.append(key)
    passed, reason, defects = prior['passed'], prior['reason'], prior['defects']
    if key in recovered:
        assert not passed and reply['attempts'] == 1 and reply['error'] is None
        assert reply['answer'] == by_case[key][0]['response']['choices'][0]['message']['content']
        passed, defects = True, []
        reason = 'Root reviewed the complete captured first draft against typed identities/counts/scope. It now reaches the user unchanged in one request. REPLAY793 proves the same captured draft was rejected before the repair.'
    elif not same:
        assert key == 'inventory785-2-3' and passed
        reason = 'Complete faithful first answer already seen in792B; both identities and2/7 page scope preserved. Quality unchanged; first-generation variation not attributed to793.'
    rows.append({'case_id': key, 'passed': passed, 'reason': reason, 'defects': defects,
                 'same_final_as792A': same, 'seconds': reply['seconds'], 'attempts': reply['attempts'], 'error': reply['error']})
assert len(changed) == 5 and sum(r['passed'] for r in rows) == 36
six = {f'inventory785-{a}-{b}' for a in [5, 6] for b in [1, 3, 4]}
assert all(r['passed'] and r['attempts'] == 1 for r in rows if r['case_id'] in six)
summary = {'pass': 36, 'fail': 14, 'quality_gains_over792A': 4, 'quality_losses_over792A': 0,
           'recovered_in_one_request': sorted(recovered), 'first_payload_parity': 50,
           'attempt_events': dict(Counter(e['state'] for e in attempts)), 'effective_params_verified': len(posts),
           'new_raw_outputs': 0, 'changed_finals_read': 5, 'exact_final_outcomes': 45,
           'timeouts': sum(bool(r['error']) for r in replies), 'empty_finals': sum(r['answer'] == '' for r in replies)}
write(OUT / 'ADJUDICATION.json', {'utc': datetime.now(timezone.utc).isoformat(), 'summary': summary, 'rows': rows,
    'method': 'Frozen785/792 whole-answer criteria;45 exact finals inherit judgment, five changed finals read by root. All successful raw responses already present792. Four recovered drafts independently replayed through the changed composer.',
    'candidate793_adopted': True, 'model_selection_closed': True, 'coverage_added': 0,
    'limits': 'Directed integration panel, not native-model ranking, live provider/UI/voice acceptance or full survey coverage.14 failures remain.'})
private_md, public_md = ['# Integración794 — entradas y respuestas\n'], ['# Cuatro respuestas recuperadas794\n']
for case, reply, row in zip(cases, replies, rows, strict=True):
    section = [f"## {case['id']} — {'CUMPLE' if row['passed'] else 'FALLA'}\n", 'Petición: ' + case['request'], 'Criterio: ' + case['criterion'], row['reason'],
               '```json\n' + json.dumps(case['situation'], ensure_ascii=False, indent=2) + '\n```',
               f"Final: {reply['seconds']:.3f}s; {reply['attempts']} intentos; error {reply['error']}", '```text\n' + (reply['answer'] or '') + '\n```']
    for post in by_case[case['id']]:
        section += [f"Intento{post['attempt']}:", '```text\n' + post['response']['choices'][0]['message']['content'] + '\n```']
    private_md.extend(section)
    if case['id'] in recovered:
        public_md.extend(section)
write(PRIVATE / 'RESPUESTAS.md', '\n\n'.join(private_md))
write(OUT / 'RESPUESTAS_RECUPERADAS.md', '\n\n'.join(public_md))
write(OUT / 'PRIVATE_PINS.json', {'directory': str(PRIVATE), 'files': {p: sha(PRIVATE / p) for p in
    ['cases.json', 'expected-first.json', 'attempts.jsonl', 'posts.jsonl', 'replies.jsonl', 'compose-audit.jsonl', 'RESPUESTAS.md']}})
write(OUT / 'TERMINAL.json', {'session': 56452, 'exit_code': 0, 'terminal_collected': True, 'inference_active': False})
note = '794 completada:36/50 correctos,4 recuperaciones y0 pérdidas frente792A; cuatro primeros borradores entregados exactos en1petición.3134pass/1skipSTT+121subtests,Fast0. Se adopta793 con787/789/791 heredados; fuente lista para publicar.136,516s;3499,56MiBVRAM/764,42MiBRSS compositor.56452terminal0 recogida, sin inferencia. Qwen elegido; siguiente categoría process.list795, sólo bloqueantes. Encuesta28/714/0.'
p = BASE / 'RELEVO_ACTIVO.json'; r = read(p)
r.update(checkpoint=note, activeValidation=None, workStatus='inventory_veto793_adopted_publish_next_process795',
         continuation='Publish validated793 sources and794 evidence immediately. Then run actual product process.list category795 (six historical requirements plus variants>=50), following NEXT_PROCESS_CATEGORY795.json. No more model selection, no prompt experiments without a demonstrated blocker.')
p.write_bytes((json.dumps(r, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
p = BASE / 'CHECKPOINT.md'; p.write_bytes((note + '\n\n').encode('utf-8') + p.read_bytes())
print(json.dumps(summary))
