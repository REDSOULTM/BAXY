"""Adjudicate790 against788 without treating rejection as successful recovery."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'INVENTORY_COMPOSER790'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-inventory-composer790-private'
OLD = PRIVATE.parent / 'C03-inventory-composer788-private'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
lines = lambda p: [json.loads(line) for line in p.read_text(encoding='utf-8').splitlines()]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    assert not path.exists(), path
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    path.write_bytes(text.encode('utf-8'))


plan, run = read(OUT / 'PREREG.json'), read(OUT / 'RESULT.json')
cases, replies, posts, attempts = read(PRIVATE / 'cases.json'), lines(PRIVATE / 'replies.jsonl'), lines(PRIVATE / 'posts.jsonl'), lines(PRIVATE / 'attempts.jsonl')
old_replies = {r['id']: r for r in lines(OLD / 'replies.jsonl')}
old_first = {}
old_raw = defaultdict(set)
for r in lines(OLD / 'posts.jsonl'):
    old_first.setdefault(r['id'], r)
    old_raw[r['id']].add(r['response']['choices'][0]['message']['content'])
old_judged = {r['case_id']: r for r in read(BASE / 'INVENTORY_COMPOSER788/ADJUDICATION.json')['rows']}
assert len(cases) == len(replies) == 50 and len(posts) == 67 and len(attempts) == 134
assert run['fatal'] is None and not run['violations']
assert all(run[k] for k in ['source_pins_unchanged', 'sources_unchanged', 'manifest_unchanged', 'driver_unchanged'])
assert sha(PRIVATE / 'cases.json') == plan['case_sha256'] == sha(OLD / 'cases.json')
assert all(sha(ROOT / p) == h for p, h in plan['source_pins'].items())
assert sha(ROOT / 'scratchpad/c03-inventory-composer790.py') == plan['driver_sha256']
expected = read(PRIVATE / 'expected-first.json')
assert expected == read(OLD / 'expected-first.json')
events = defaultdict(list)
for event in attempts:
    events[(event['id'], event['attempt'])].append(event)
by_case = defaultdict(list)
effective = []
for post in posts:
    by_case[post['id']].append(post)
    event = events[(post['id'], post['attempt'])]
    assert [e['state'] for e in event] == ['started', 'succeeded']
    assert event[0]['payload'] == post['payload']
    slot = max((s for s in post['slots_after'] if 'id_task' in s), key=lambda s: s['id_task'])
    wanted = {'temperature': 0., 'top_k': 40, 'top_p': .95, 'min_p': .05, 'seed': 4294967295,
              'presence_penalty': 0., 'repeat_penalty': 1., 'max_tokens': post['payload']['max_tokens'],
              'n_predict': post['payload']['max_tokens']}
    assert all(math.isclose(slot['params'][k], v, rel_tol=1e-6, abs_tol=1e-7) for k, v in wanted.items())
    assert slot['n_ctx'] == 4096 and slot['n_prompt_tokens_cache'] == 0
    effective.append({'case_id': post['id'], 'attempt': post['attempt'], 'id_task': slot['id_task'],
                      'params': {k: slot['params'][k] for k in wanted}, 'n_ctx': 4096, 'cache_tokens': 0})
rows = []
changed = []
for case, reply in zip(cases, replies, strict=True):
    key = case['id']
    assert key == reply['id']
    first = by_case[key][0]
    assert first['attempt'] == 1 and first['payload'] == expected[key]
    assert len(by_case[key]) == reply['attempts']
    old, judged = old_replies[key], old_judged[key]
    same = reply['answer'] == old['answer'] and reply['error'] == old['error']
    passed = judged['passed']
    reason, defects = judged['reason'], judged['defects']
    if not same:
        changed.append(key)
        if key == 'inventory785-4-1':
            passed, defects = True, []
            reason = 'Root reviewed all12 identities/multiplicities and true20-observed/page12 scope. Correct second response arrived within9s. First raw remains falsely vetoed; speed difference, not attribution to identity repair.'
        elif key == 'inventory785-2-3':
            assert passed
            reason = 'Root reviewed new first raw: both identities,7observed/page2 and partial scope. Same outcome quality; first payload identical but raw differs, cause not established.'
        else:
            assert not passed and reply['answer'] == '' and reply['error'] is None
            defects = ['empty_final', 'unrepaired_inventory']
            reason = 'All three attempts returned, but no publishable final. Original chronology/identity omission or false count veto remains; rejection does not satisfy the request.'
    rows.append({'case_id': key, 'passed': passed, 'reason': reason, 'defects': defects,
                 'same_final_as788': same, 'seconds': reply['seconds'], 'attempts': reply['attempts'],
                 'error': reply['error'], 'first_raw_exact788': first['response']['choices'][0]['message']['content'] == old_first[key]['response']['choices'][0]['message']['content']})
assert len(changed) == 8 and sum(r['passed'] for r in rows) == 33
assert sum(r['first_raw_exact788'] for r in rows) == 49
assert sum(r['answer'] == '' for r in replies) == 8 and not any(r['error'] for r in replies)
novel = [p for p in posts if p['response']['choices'][0]['message']['content'] not in old_raw[p['id']]]
assert len(novel) == 13
six = {f'inventory785-{a}-{b}' for a in [5, 6] for b in [1, 3, 4]}
assert all(r['passed'] and r['attempts'] == 1 for r in rows if r['case_id'] in six)
summary = {'pass': 33, 'fail': 17, 'empty_finals': 8, 'timeouts': 0,
           'attempts_started': 67, 'attempts_succeeded': 67, 'attempts_failed': 0, 'attempts_without_terminal': 0,
           'first_payloads_exact788': 50, 'first_raws_exact788': 49, 'final_outcomes_exact788': 42,
           'new_raw_outputs_read': 13, 'new_final_outcomes_read': 8,
           'six_complete_one_post_seconds_min': min(r['seconds'] for r in rows if r['case_id'] in six),
           'six_complete_one_post_seconds_max': max(r['seconds'] for r in rows if r['case_id'] in six),
           'final_seconds_p50': statistics.median(r['seconds'] for r in rows),
           'multiplicity_failures_recovered': 0,
           'incomplete_finals_now_blocked': ['inventory785-4-2', 'inventory785-5-2', 'inventory785-6-2']}
write(OUT / 'ADJUDICATION.json', {'utc': datetime.now(timezone.utc).isoformat(), 'quality_adjudicated': True,
    'method': 'Root whole-answer criteria unchanged785/788.42 exact final outcomes inherit judgment;8 changed finals and13 novel raw outputs read manually. Runtime validator is not the oracle.',
    'summary': summary, 'rows': rows, 'survey_credit': 0, 'candidate789_adopted': False,
    'attribution_limit': '4-1 already had a correct first raw rejected by the old numeric/exhaustiveness validator; faster serving permitted a second correct response. Do not attribute33vs32 or faster timings to789 without a causal replay.'})
write(OUT / 'PARITY.json', {'first_full_payloads_exact788': 50, 'first_raws_exact788': 49,
    'raw_difference_case': 'inventory785-2-3', 'raw_difference_cause': 'Not established; greedy and equal HTTP payloads do not demonstrate byte-identical execution.',
    'attempts_all_accounted_for': True, 'effective_verified': 67, 'effective': effective})
private_md = ['# Compositor790: todas las entradas y respuestas\n', 'Cada intento se registra antes de HTTP y tiene resultado terminal. Criterios íntegros de788.\n']
public_md = ['# Cambios sintéticos del compositor790\n', 'Los históricos permanecen en el directorio privado. La respuesta vacía no cumple.\n']
for case, reply, row in zip(cases, replies, rows, strict=True):
    section = [f"## {case['id']} — {'CUMPLE' if row['passed'] else 'FALLA'}\n", f"Petición: {case['request']}\n", f"Criterio: {case['criterion']}\n", row['reason'] + '\n',
               '```json\n' + json.dumps(case['situation'], ensure_ascii=False, indent=2) + '\n```\n',
               f"Final: {reply['seconds']:.3f}s; {reply['attempts']} intentos.\n", '```text\n' + reply['answer'] + '\n```\n']
    for post in by_case[case['id']]:
        section += [f"### Intento {post['attempt']} — {post['post_seconds']:.3f}s\n", '```text\n' + post['response']['choices'][0]['message']['content'] + '\n```\n']
    private_md += section
    if case['id'] in changed and case['id'].startswith('inventory785-'):
        public_md += section
write(PRIVATE / 'RESPUESTAS.md', '\n'.join(private_md))
write(OUT / 'RESPUESTAS_CAMBIADAS.md', '\n'.join(public_md))
write(OUT / 'PRIVATE_PINS.json', {'directory': str(PRIVATE), 'files': {name: sha(PRIVATE / name) for name in ['cases.json', 'expected-first.json', 'attempts.jsonl', 'posts.jsonl', 'replies.jsonl', 'compose-audit.jsonl', 'RESPUESTAS.md']}})
note = '790 terminado0/44316recogida:33/50correctos,17fallos;8vacíos,0timeouts;67intentos completos/success67.50primerpayloadsiguales788,49primerbrutoigual. Treslistas incompletas ahora vetadas pero0recuperadas;33vs32 ligado a velocidad/retry4-1,noatribuir a789.3499,56MiBVRAM/761,77MiBRSS;93,844s.789validado pero sinadoptar;feedback cuenta0enúltimotítulo seguido de otra frase, corregir antes.28/714/0.'
r = read(BASE / 'RELEVO_ACTIVO.json')
r.update(checkpoint=note, activeValidation=None, workStatus='inventory_composer790_adjudicated_candidate789_held',
         continuation='Preserve789 and790 before edits. Fix measured final-title counting and process-annotation ambiguity under a new candidate; then isolate why factual repair repeats incomplete drafts. No further unchanged batch, no adoption or survey credit from empty finals.')
(BASE / 'RELEVO_ACTIVO.json').write_bytes((json.dumps(r, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
cp = BASE / 'CHECKPOINT.md'
cp.write_bytes((note + '\n\n').encode('utf-8') + cp.read_bytes())
print(json.dumps(summary))
