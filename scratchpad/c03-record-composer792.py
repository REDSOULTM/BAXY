"""Record the completed paired ablation and the owner's model-selection decision."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/comprobaciones/C03'
OUT = BASE / 'INVENTORY_COMPOSER792'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-inventory-composer792-private'
OLD = PRIVATE.parent / 'C03-inventory-composer790-private'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def lines(p):
    with p.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def write(p, value):
    assert not p.exists(), p
    content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    p.write_bytes(content.encode('utf-8'))


run, parity = read(OUT / 'RESULT.json'), read(OUT / 'PARITY.json')
assert run['fatal'] is None and not run['violations'] and run['executions_completed'] == 100
cases, replies, posts = read(PRIVATE / 'cases.json'), lines(PRIVATE / 'replies.jsonl'), lines(PRIVATE / 'posts.jsonl')
old = {r['id']: r for r in lines(OLD / 'replies.jsonl')}
judged = {r['case_id']: r for r in read(BASE / 'INVENTORY_COMPOSER790/ADJUDICATION.json')['rows']}
rows = []
for reply in replies:
    key = reply['id']
    same = (reply['answer'], reply['error']) == (old[key]['answer'], old[key]['error'])
    if same:
        passed, reason, defects = judged[key]['passed'], judged[key]['reason'], judged[key]['defects']
    elif not reply['answer']:
        passed, reason, defects = False, 'No final answer within the unchanged product deadline; empty or timeout does not fulfill the available read.', ['timeout' if reply['error'] else 'empty_final']
    else:
        assert key == 'inventory785-2-3' and reply['arm'] == 'A'
        passed, defects = True, []
        reason = 'Root reviewed complete answer: both observed names,2 on this page,7 observed and more beyond this page. First response differs before intervention, so not caused by B.'
    rows.append({'case_id': key, 'arm': reply['arm'], 'passed': passed, 'reason': reason, 'defects': defects,
                 'same_final_as790': same, 'seconds': reply['seconds'], 'attempts': reply['attempts'], 'error': reply['error']})
summary = {}
for arm in ['A', 'B']:
    selected = [r for r in rows if r['arm'] == arm]
    raw = [r for r in replies if r['arm'] == arm]
    summary[arm] = {'pass': sum(r['passed'] for r in selected), 'fail': sum(not r['passed'] for r in selected),
                    'timeouts': sum(bool(r['error']) for r in raw), 'empty_finals': sum(r['answer'] == '' for r in raw),
                    'seconds_p50': statistics.median(r['seconds'] for r in raw), 'seconds_sum': sum(r['seconds'] for r in raw)}
    assert summary[arm]['pass'] == 32
assert {(r['case_id'], r['passed']) for r in rows if r['arm'] == 'A'} == {(r['case_id'], r['passed']) for r in rows if r['arm'] == 'B'}
write(OUT / 'ADJUDICATION.json', {'utc': datetime.now(timezone.utc).isoformat(), 'summary': summary, 'rows': rows,
    'method': 'Root whole-answer review under frozen785/790 criteria.90 exact finals inherit judgment;10 changed finals and all9 novel raw outputs read. Validator is not the oracle.',
    'novel_raws_read': 9, 'changed_finals_read': 10, 'paired_quality_gains': 0, 'paired_quality_losses': 0,
    'decision': 'Do not remove rejected_draft from runtime on this evidence. No delivered quality gain; repeated missing multiplicities remain.',
    'attribution_limits': '48/50 first raw pairs match despite100 exact first payloads. H0103 and2-3 differ before intervention; do not attribute their difference to B. Both arms time out at4-1 after an old false veto, unlike790; source or performance causality not established.',
    'partial_finding': 'H0023 B attempt2 removes unsupported opening chronology; final still fails. Checker reports8 explorer identities missing when draft uses Explorador. This is not successful recovery and does not justify a hardcoded alias.',
    'candidate791_adopted': False, 'runtime_prompt_changed': False, 'coverage_added': 0})
by_case = defaultdict(list)
for post in posts:
    by_case[(post['id'], post['arm'])].append(post)
reply_map = {(r['id'], r['arm']): r for r in replies}
private_md, public_md = ['# Comparación792: entradas, respuestas y adjudicación\n'], ['# Respuestas sintéticas cambiadas792\n']
changed = {r['id'] for r in parity['changed_from790']}
for case in cases:
    section = [f"## {case['id']}\n", 'Petición: ' + case['request'], 'Criterio: ' + case['criterion'],
               '```json\n' + json.dumps(case['situation'], ensure_ascii=False, indent=2) + '\n```']
    for arm in ['A', 'B']:
        reply = reply_map[(case['id'], arm)]
        section += [f"### Brazo {arm} — {reply['seconds']:.3f}s — {reply['attempts']} intentos\n",
                    f"Error: {reply['error']}", '```text\n' + (reply['answer'] or '') + '\n```']
        for post in by_case[(case['id'], arm)]:
            section += [f"Intento{post['attempt']}:", '```text\n' + post['response']['choices'][0]['message']['content'] + '\n```']
    private_md.extend(section)
    if case['id'] in changed and case['id'].startswith('inventory785-'):
        public_md.extend(section)
write(PRIVATE / 'RESPUESTAS.md', '\n\n'.join(private_md))
write(OUT / 'RESPUESTAS_CAMBIADAS.md', '\n\n'.join(public_md))
write(OUT / 'PRIVATE_PINS.json', {'directory': str(PRIVATE), 'files': {p: sha(PRIVATE / p) for p in
    ['cases.json', 'expected-first.json', 'attempts.jsonl', 'posts.jsonl', 'replies.jsonl', 'compose-audit.jsonl', 'REVIEW.md', 'RESPUESTAS.md']}})
write(OUT / 'TERMINAL.json', {'session': 59555, 'exit_code': 0, 'terminal_collected': True, 'inference_active': False})
note = '792 terminada y revisada: A32/50 y B32/50;0 ganancias finales al retirar rejected_draft.133 intentos,124 éxitos HTTP,9 errores;100 primeros payloads idénticos,48 primeros brutos emparejados.285,859s;3499,56MiB VRAM/765,25MiB RSS compositor.59555 terminal0 recogida. Dueño ordena cerrar selección: Qwen3-4B-Instruct2507Q4_K_M registrado; continuar sólo bloqueantes, sin más comparativas de modelo.791 validado y preservado sin adoptar;28/714/0.'
p = BASE / 'RELEVO_ACTIVO.json'; r = read(p)
r.update(checkpoint=note, activeValidation=None, workStatus='model_selected_qwen_continue_c03_blockers',
         selectedModel='Qwen3-4B-Instruct-2507 Q4_K_M registered',
         ownerPriority='Owner ordered model selection after792 and immediate progress on C03 blockers; no further model campaign.',
         continuation='Publish791/792. Repair demonstrated shared false vetoes (empty inventory, page quantity/exhaustiveness) and then run whole categories. RO agents locate causes and next survey family; root implements. Do not add another prompt or hardcoded process alias.')
p.write_bytes((json.dumps(r, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
p = BASE / 'CHECKPOINT.md'; p.write_bytes((note + '\n\n').encode('utf-8') + p.read_bytes())
print(json.dumps(summary))
