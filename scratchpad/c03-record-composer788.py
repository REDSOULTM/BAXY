"""Record completed788; distinguish raw quality, validation and final delivery."""
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
OUT = BASE / 'INVENTORY_COMPOSER788'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-inventory-composer788-private'
OLD = PRIVATE.parent / 'C03-inventory-budget786-private'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    assert not path.exists(), path
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    path.write_bytes(text.encode('utf-8'))


plan, run = read(OUT / 'PREREG.json'), read(OUT / 'RESULT.json')
cases = read(PRIVATE / 'cases.json')
posts = [json.loads(l) for l in (PRIVATE / 'posts.jsonl').read_text(encoding='utf-8').splitlines()]
replies = [json.loads(l) for l in (PRIVATE / 'replies.jsonl').read_text(encoding='utf-8').splitlines()]
expected = read(PRIVATE / 'expected-first.json')
previous = read(OLD / 'results.json')
judgments = read(BASE / 'INVENTORY_BUDGET786/ADJUDICATION.json')['rows']
assert len(cases) == len(replies) == 50 and len(posts) == 59
assert run['fatal'] is None and not run['violations']
assert all(run[k] for k in ['source_pins_unchanged', 'sources_unchanged', 'manifest_unchanged', 'driver_unchanged'])
assert sha(PRIVATE / 'cases.json') == plan['case_sha256']
assert sha(PRIVATE / 'expected-first.json') == plan['first_payloads_sha256']
assert sha(ROOT / 'scratchpad/c03-inventory-composer788.py') == plan['driver_sha256']
assert all(sha(ROOT / p) == h for p, h in plan['source_pins'].items())
by_case = defaultdict(list)
for post in posts:
    by_case[post['id']].append(post)
old_raw = {(r['case_id'], r['arm']): r['response']['choices'][0]['message']['content'] for r in previous}
old_judged = {(r['case_id'], r['arm']): r for r in judgments}
new_judgments = {
    'H0023': (False, ['timeout'], 'No final answer within9s; first raw retained unsupported chronology.'),
    'H0103': (False, ['timeout'], 'No final answer within9s; successful raws omit identities/multiplicity.'),
    'inventory785-1-3': (False, ['empty_final', 'false_veto'], 'Three truthful empty-inventory responses vetoed as copied_instruction; final empty.'),
    'inventory785-1-4': (False, ['empty_final', 'false_veto'], 'Three truthful empty-inventory responses vetoed as copied_instruction; final empty.'),
    'inventory785-2-2': (False, ['timeout', 'false_veto'], 'Two truthful2-of7 responses vetoed as reversed_result; final timeout4s.'),
    'inventory785-2-3': (True, [], 'Root reviewed complete final: both identities, observed7/listed2, explicit partial scope; no invented facts.'),
    'inventory785-4-1': (False, ['timeout', 'false_veto'], 'Truthful12-entry inventory with observed20 vetoed as extra_claim; final timeout9s.'),
    'inventory785-4-2': (False, ['missing_multiplicity'], 'Only5 unique titles for12entries; vague repetitions omit exact multiplicity.'),
    'inventory785-6-2': (False, ['missing_multiplicity'], 'Only5 unique titles for20entries; observed25/page20 alone does not identify each entry.'),
}
rows, effective = [], []
exact_count = 0
for case, reply in zip(cases, replies, strict=True):
    case_id = case['id']
    assert case_id == reply['id']
    captured = by_case[case_id]
    assert captured[0]['attempt'] == 1 and captured[0]['payload'] == expected[case_id]
    matches = [a for a in ['B_output_512', 'A_original_256'] if reply['answer'] == old_raw[(case_id, a)]]
    if matches:
        assert case_id not in new_judgments
        old = old_judged[(case_id, matches[0])]
        passed, defects, reason = old['passed'], old['defects'], old['reason']
        exact_count += 1
    else:
        passed, defects, reason = new_judgments[case_id]
    rows.append({'case_id': case_id, 'passed': passed, 'defects': defects, 'reason': reason,
                 'same_final_as786': matches, 'seconds': reply['seconds'], 'error': reply['error'],
                 'successful_http_responses': len(captured),
                 'answer_sha256': hashlib.sha256(reply['answer'].encode('utf-8')).hexdigest() if reply['answer'] is not None else None})
    for post in captured:
        slot = max((s for s in post['slots_after'] if 'id_task' in s), key=lambda s: s['id_task'])
        wanted = {'temperature': 0., 'top_k': 40, 'top_p': .95, 'min_p': .05, 'seed': 4294967295,
                  'presence_penalty': 0., 'repeat_penalty': 1., 'max_tokens': post['payload']['max_tokens'],
                  'n_predict': post['payload']['max_tokens']}
        assert all(math.isclose(slot['params'][k], v, rel_tol=1e-6, abs_tol=1e-7) for k, v in wanted.items())
        assert slot['n_ctx'] == 4096 and slot['n_prompt_tokens_cache'] == 0
        effective.append({'case_id': case_id, 'attempt': post['attempt'], 'id_task': slot['id_task'],
                          'params': {k: slot['params'][k] for k in wanted}, 'n_ctx': 4096, 'cache_tokens': 0})
assert exact_count == 41 and sum(r['passed'] for r in rows) == 32
fixed = {f'inventory785-{layout}-{variant}' for layout in [5, 6] for variant in [1, 3, 4]}
fixed_rows = [r for r in rows if r['case_id'] in fixed]
assert all(r['passed'] and r['successful_http_responses'] == 1 and r['seconds'] < 9 for r in fixed_rows)
assert sum(bool(r['error']) for r in rows) == 4
assert sum(r['answer'] == '' for r in replies) == 2
attribution = read(OUT / 'VALIDATOR_ATTRIBUTION.json')
assert 'inventory785-5-2' in attribution['gained'] and not attribution['lost']
summary = {'pass': 32, 'fail': 18, 'timeouts': 4, 'empty_finals': 2,
           'successful_http_responses': 59, 'failed_http_attempts_recorded': False,
           'final_exact786': 41, 'new_final_outcomes_reviewed': 9,
           'fixed_six_complete_in_one_post': sorted(fixed),
           'six_seconds_min': min(r['seconds'] for r in fixed_rows),
           'six_seconds_max': max(r['seconds'] for r in fixed_rows),
           'all_final_seconds_p50': statistics.median(r['seconds'] for r in rows),
           'defects': dict(Counter(d for r in rows for d in r['defects']))}
write(OUT / 'ADJUDICATION.json', {'utc': datetime.now(timezone.utc).isoformat(), 'quality_adjudicated': True,
    'method': 'Root whole-answer criteria unchanged785/786;41 byte-identical finals inherit judgment,9 new final outcomes and all9 successful retry outputs manually read. Runtime validator is not the oracle.',
    'summary': summary, 'rows': rows, 'survey_credit': 0, 'source_adopted': False,
    'adoption_hold': '5-2 is newly delivered yet incomplete: old false scope veto had masked missing multiplicity validation. Preserve787 before further repair; green unit suites alone do not resolve this.'})
write(OUT / 'PARITY.json', {'cases_same785': 50, 'first_payloads_checked': 50,
    'first_messages_same785': 50, 'only_first_request_difference': 'max_tokens256/512 for dense inventory',
    'effective_successful_response_slots': 59, 'failed_attempt_payload_limit': 'Client logs only after a successful HTTP response; failed/aborted attempts not captured.59 is not the total attempt count.',
    'effective': effective})
md = ['# Respuestas del compositor788\n', 'Entradas privadas y sintéticas; todos los resultados finales y cada HTTP exitoso capturado. Los intentos HTTP fallidos no están conservados por el conductor.\n']
public = ['# Finales sintéticos del compositor788\n', 'Criterios íntegros de785; los históricos se conservan sólo en el artefacto privado.\n']
for case, reply, row in zip(cases, replies, rows, strict=True):
    section = [f"## {case['id']} — {'CUMPLE' if row['passed'] else 'FALLA'}\n", f"Petición: {case['request']}\n", f"Criterio: {case['criterion']}\n", row['reason'] + '\n',
               '```json\n' + json.dumps(case['situation'], ensure_ascii=False, indent=2) + '\n```\n',
               f"Final: {reply['seconds']:.3f}s; error: {reply['error']!r}.\n",
               '```text\n' + (reply['answer'] if reply['answer'] is not None else '[sin respuesta final]') + '\n```\n']
    for post in by_case[case['id']]:
        choice = post['response']['choices'][0]
        section += [f"### HTTP exitoso, intento {post['attempt']} — {post['post_seconds']:.3f}s — {choice['finish_reason']}\n",
                    '```text\n' + choice['message']['content'] + '\n```\n']
    md += section
    if case['id'].startswith(('inventory785-', 'memory785-')):
        public += section
write(PRIVATE / 'RESPUESTAS.md', '\n'.join(md))
write(OUT / 'RESPUESTAS_SINTETICAS.md', '\n'.join(public))
write(OUT / 'PRIVATE_PINS.json', {'directory': str(PRIVATE), 'files': {name: sha(PRIVATE / name) for name in ['cases.json', 'expected-first.json', 'posts.jsonl', 'replies.jsonl', 'compose-audit.jsonl', 'RESPUESTAS.md']}})
note = '788 adjudicado:32/50correctos,18fallos;6inventarios antes cortados completos en1post/7,42–7,67s.59HTTPexitosos(no todos los intentos),4timeouts/2vacíos.4vetos a brutos correctos preexistían.5-2ahoraentrega lista incompleta:787validado pero adopciónretenida hasta multiplicidad.3499,56MiBVRAM/763,57MiBRSScompositor.26847terminal0recogida;sinprocesosactivos.28/714/0.'
r = read(BASE / 'RELEVO_ACTIVO.json')
r.update(checkpoint=note, activeValidation=None, workStatus='inventory_composer788_adjudicated_candidate787_held',
         continuation='Record/preserve787 source snapshot and788 evidence. Repair existing identity/multiplicity gap as a new candidate, retaining frozen787 pins. No inference before recording; no native-model ranking or survey credit.',
         previousGoalTurnClassification='progress', previousGoalTurnClassificationReason='786 completed100 paired requests,787 source candidate118 controls with owners2901pass/1STTskip+121subtests and Fast0;788 completed50 real composer cases and baseline validation attribution.')
(BASE / 'RELEVO_ACTIVO.json').write_bytes((json.dumps(r, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
cp = BASE / 'CHECKPOINT.md'
cp.write_bytes((note + '\n\n').encode('utf-8') + cp.read_bytes())
print(json.dumps(summary))
