"""Adjudicate786 by exact inheritance of785 plus six complete root-reviewed answers."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'INVENTORY_BUDGET786'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-inventory-budget786-private'
OLD = PRIVATE.parent / 'C03-prose-sampling785-private'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    assert not path.exists(), path
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    path.write_bytes(text.encode('utf-8'))


plan = read(OUT / 'PREREG.json')
run = read(OUT / 'RESULT.json')
cases = read(PRIVATE / 'cases.json')
planned = read(PRIVATE / 'planned.json')
results = read(PRIVATE / 'results.json')
assert len(results) == len(planned) == 100 and len(cases) == 50
assert not run['violations'] and run['sources_unchanged'] and run['driver_unchanged']
assert sha(PRIVATE / 'cases.json') == plan['cases_sha256'] == plan['reference_cases_sha256']
assert sha(PRIVATE / 'planned.json') == plan['planned_sha256']
assert sha(ROOT / 'scratchpad/c03-inventory-budget786.py') == plan['driver_sha256']
assert all(sha(ROOT / p) == h for p, h in plan['source_pins'].items())
old_rows = {r['case_id']: r for r in read(BASE / 'PROSE_SAMPLING785/ADJUDICATION.json')['rows'] if r['arm'] == 'A_registered_greedy'}
old_raw = {r['case_id']: r for r in read(OLD / 'results.json') if r['arm'] == 'A_registered_greedy'}
old_plans = {r['case_id']: r['payload'] for r in read(OLD / 'planned.json') if r['arm'] == 'A_registered_greedy'}
lookup = {(r['case_id'], r['arm']): r for r in results}
payloads = {(r['case_id'], r['arm']): r['payload'] for r in planned}
arms = ['A_original_256', 'B_output_512']
# Full new answers read by root against all20 entries and exact page/total meaning.
fixed = {f'inventory785-{layout}-{variant}' for layout in [5, 6] for variant in [1, 3, 4]}
rows, effective, changed = [], [], []
for c in cases:
    for arm in arms:
        result = lookup[(c['id'], arm)]
        payload = payloads[(c['id'], arm)]
        expected_payload = dict(old_plans[c['id']])
        expected_payload['max_tokens'] = 256 if arm == arms[0] else 512
        assert payload == expected_payload
        choice = result['response']['choices'][0]
        text = choice['message']['content']
        original = old_raw[c['id']]['response']['choices'][0]['message']['content']
        is_fixed = arm == arms[1] and c['id'] in fixed
        if is_fixed:
            assert text != original and text.startswith(original)
            assert choice['finish_reason'] == 'stop'
            changed.append(c['id'])
        else:
            assert text == original, (c['id'], arm)
        passed = True if is_fixed else old_rows[c['id']]['passed']
        rows.append({'case_id': c['id'], 'arm': arm, 'passed': passed,
            'reason': 'Root read complete answer: all20 identities/multiplicities and true partial scope; no chronology invented. Exact old cut prefix preserved, followed by completion.' if is_fixed else old_rows[c['id']]['reason'],
            'defects': [] if is_fixed else old_rows[c['id']]['defects'],
            'same_answer_as785_A': not is_fixed, 'finish_reason': choice['finish_reason'],
            'seconds': result['seconds'], 'completion_tokens': result['response']['usage']['completion_tokens'],
            'answer_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()})
        slot = max((s for s in result['slots_after'] if 'id_task' in s), key=lambda s: s['id_task'])
        wanted = {'temperature': 0., 'top_k': 40, 'top_p': .95, 'min_p': .05, 'seed': 4294967295,
                  'presence_penalty': 0., 'repeat_penalty': 1., 'max_tokens': expected_payload['max_tokens'], 'n_predict': expected_payload['max_tokens']}
        assert all(math.isclose(slot['params'][k], v, rel_tol=1e-6, abs_tol=1e-7) for k, v in wanted.items())
        assert slot['n_ctx'] == 4096 and slot['n_prompt_tokens_cache'] == 0
        effective.append({'case_id': c['id'], 'arm': arm, 'id_task': slot['id_task'],
                          'params': {k: slot['params'][k] for k in wanted}, 'n_ctx': 4096, 'cache_tokens': 0})
assert set(changed) == fixed
summary = {}
for arm in arms:
    selected = [r for r in rows if r['arm'] == arm]
    summary[arm] = {'pass': sum(r['passed'] for r in selected), 'fail': sum(not r['passed'] for r in selected),
                    'finish_reasons': dict(Counter(r['finish_reason'] for r in selected)),
                    'final_seconds_p50': statistics.median(r['seconds'] for r in selected),
                    'final_seconds_max': max(r['seconds'] for r in selected),
                    'completion_tokens_max': max(r['completion_tokens'] for r in selected)}
assert [summary[a]['pass'] for a in arms] == [30, 36]
write(OUT / 'ADJUDICATION.json', {'utc': datetime.now(timezone.utc).isoformat(), 'quality_adjudicated': True,
    'method': '94 answers byte-identical to root-adjudicated785A with identical cases/criteria; six new complete answers manually reviewed by root. No validator as oracle.',
    'summary': summary, 'paired': {'gains': sorted(fixed), 'regressions': [], 'both_pass': 30, 'both_fail': 14},
    'source_adopted': False, 'survey_credit': 0, 'rows': rows})
write(OUT / 'PARITY.json', {'source': 'PROSE_SAMPLING785', 'case_parity': 50, 'exact_A_payload_parity': 50,
    'A_raw_response_parity': 50, 'B_raw_response_parity': 44, 'B_extends_exact_cut_prefix': sorted(fixed),
    'only_changed_request_field': 'max_tokens', 'effective_parameters_verified': 100, 'effective': effective})
md = ['# Respuestas786\n', 'A256 frente a B512; sólo cambia el límite de salida. Todos los criterios son los de785.\n']
public = ['# Seis respuestas completadas con512\n', 'El resto coincide literalmente con785A. Los datos siguientes son sintéticos.\n']
for c in cases:
    section = [f"## {c['id']}\n", f"Petición: {c['request']}\n", f"Criterio: {c['criterion']}\n", '```json\n' + json.dumps(c['situation'], ensure_ascii=False, indent=2) + '\n```\n']
    for arm in arms:
        r = next(r for r in rows if r['case_id'] == c['id'] and r['arm'] == arm)
        section += [f"### {arm}: {'CUMPLE' if r['passed'] else 'FALLA'}\n", r['reason'] + '\n',
                    f"Final {r['finish_reason']}; {r['completion_tokens']} tokens; {r['seconds']:.3f} s.\n",
                    '```text\n' + lookup[(c['id'], arm)]['response']['choices'][0]['message']['content'] + '\n```\n']
    md += section
    if c['id'] in fixed:
        public += section
write(PRIVATE / 'RESPUESTAS.md', '\n'.join(md))
write(OUT / 'RESPUESTAS_CAMBIADAS.md', '\n'.join(public))
write(OUT / 'PRIVATE_PINS.json', {'directory': str(PRIVATE), 'files': {name: sha(PRIVATE / name) for name in ['cases.json', 'planned.json', 'results.json', 'server-props.json', 'server.log', 'RESPUESTAS.md']}})
r = read(BASE / 'RELEVO_ACTIVO.json')
note = '786 terminada0/78684 recogida:100 respuestas, A30/50 B36/50; seis cortes completados correctamente a512, cero regresiones.50A y44B idénticas785; seisB prolongan prefijo exacto del corte.125,797s;3499,56MiB VRAM/724,80MiB RSS servidor;100slots efectivos y10fuentes intactas. Sin proceso activo ni fuente adoptada.28/714/0. Siguiente reutilizar512 sólo para inventario denso, sin instrucción nueva, validar compositor.'
r.update(checkpoint=note, activeValidation=None, workStatus='inventory_budget786_adjudicated', continuation='Implement existing dense512 budget for verified inventory only; keep messages/sampler/validators unchanged. Validate owners and full composer with frozen50, then publish source. No survey credit from raw diagnostics.')
(BASE / 'RELEVO_ACTIVO.json').write_bytes((json.dumps(r, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
cp = BASE / 'CHECKPOINT.md'
cp.write_bytes((note + '\n\n').encode('utf-8') + cp.read_bytes())
print(json.dumps(summary))
