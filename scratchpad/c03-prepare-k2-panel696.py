"""Freeze common native inputs before observing any K2 benchmark outputs."""
from pathlib import Path
import copy
import hashlib
import json
import os

root = Path(__file__).resolve().parents[1]
home = Path(os.environ['LOCALAPPDATA']) / 'BAXY'
base = root / 'artifacts/comprobaciones/C03/K2_HORIZON_COMPARISON696'
private = home / 'C03-k2-comparison696-private'
private.mkdir(exist_ok=True)
assert not (private / 'panel.json').exists()

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def requests(path):
    with path.open(encoding='utf-8-sig') as stream:
        return [r for line in stream if (r := json.loads(line)).get('stage') == 'request']

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

source694 = home / 'C03-status-batch694-private'
source521 = home / 'C03-private-product521-private'
req694 = requests(source694 / 'http-posts.jsonl')
req521 = requests(source521 / 'http-posts.jsonl')
panel694 = {r['case_id']: r for r in read(source694 / 'panel.json')}
cases = []
selector_specs = {
    'disk-used-es': ['system.status'], 'H0532': ['system.status'],
    'H0359': ['system.status'], 'cpu-order-es': ['system.status'],
    'H0450': ['system.time'], 'H0499': ['system.time'], 'H0602': ['system.time'],
    'clock-date-en': ['system.time'], 'network-internet-es': ['network.status'],
    'H0675': ['system.process.list'], 'audio-order-es': ['audio.status'],
}

for case_id, operations in selector_specs.items():
    text = panel694[case_id]['text']
    source = next(r for r in req694 if r['payload'].get('tools') and r['payload']['messages'][-1].get('content') == text)
    available = {t['function']['name'] for t in source['payload']['tools']}
    expected = ['baxy_' + op.replace('.', '__') for op in operations]
    missing = sorted(set(expected) - available)
    cases.append({'id': 'select-' + case_id, 'kind': 'selector', 'payload': copy.deepcopy(source['payload']),
        'source': 'product694 HTTP ' + str(source['id']), 'expected_functions': [] if missing else expected,
        'requested_functions_missing_from_supplied_catalog': missing,
        'criterion': ('The supplied catalog omits the requested read. Do not invent a tool, a measurement or an executed connection. Abstention is the correct model boundary but does not satisfy the BAXY capability requirement.' if missing else 'Propose exactly the requested read operations, in order; no executed-effect claim. Empty arguments are intentional in this production selector stage; argument extraction is tested separately before promotion.')})

selector_reference = next(r for r in cases if r['id'] == 'select-cpu-order-es')['payload']
controls = [
    ('date-en', 'Show me the current local date.', ['system.time']),
    ('battery-es', '¿Cuánta batería queda en mi portátil?', ['system.status']),
    ('cpu-then-date-en', 'Read the current CPU usage, then tell me the date.', ['system.status', 'system.time']),
    ('negated-en', 'Do not check the CPU usage.', []),
    ('past-en', 'Yesterday I checked my RAM.', []),
    ('knowledge-en', 'What is RAM?', []),
    ('other-machine-es', '¿Cuánta RAM tiene el ordenador de Ana?', []),
    ('process-memory-es', '¿Qué app está usando más memoria ahora?', ['system.process.list']),
    ('disk-order-es', 'Del disco C, dime el espacio libre.', ['system.status']),
]
for case_id, text, operations in controls:
    payload = copy.deepcopy(selector_reference)
    payload['messages'] = [payload['messages'][0], {'role': 'user', 'content': text}]
    cases.append({'id': 'select-control-' + case_id, 'kind': 'selector', 'payload': payload,
        'source': 'explicit development variation; same production selector instructions/catalog, no history',
        'expected_functions': ['baxy_' + op.replace('.', '__') for op in operations],
        'criterion': 'Exact requested operations only, preserving order. No tool for negation, past event, stable knowledge or another machine. No execution claim.'})

writer_specs = {
    0: ('welcome', 'Natural Spanish welcome as BAXY; no invented observation or action.'),
    1: ('error', 'English: name could not be saved because memory is disabled; no successful save.'),
    2: ('confirmation', 'English: ask about enabling memory for this invocation, no completed enable/save claim.'),
    3: ('completed', 'English: memory enabled; do not claim the pending save already happened.'),
    4: ('completed', 'English: verified memory update, brief natural prose without internal flags.'),
    6: ('clarification', 'Spanish: ask which application, without guessing or execution.'),
    7: ('read', 'English: private memory lists Jordan; report that observed value.'),
    8: ('conversation', 'Spanish: acknowledge the person is Álvaro, without inventing persistent storage.'),
    10: ('clarification', 'Spanish: ask which application. Repeated literal retained as source repetition, not independent evidence.'),
    11: ('read', 'Spanish: private memory lists Jordan; do not replace it with a conversational name.'),
    12: ('progress', 'Spanish: brief first-person progress, no facts/results yet and no request for manual work.'),
    16: ('conversation', 'Spanish: latest self-introduction in history is Álvaro; distinguish the private-memory value Jordan.'),
    17: ('completed', 'Spanish: private memory disabled, without claiming records were deleted or PC changed.'),
    18: ('read', 'Spanish: time21:24, or9:24PM; no new clock setting or presence claim.'),
    19: ('capability', 'Spanish: local memory exists but is disabled; one record is stored, not absent capability.'),
}
for source_id, (kind, criterion) in writer_specs.items():
    source = next(r for r in req521 if r['id'] == source_id)
    cases.append({'id': f'writer521-{source_id}', 'kind': kind, 'payload': copy.deepcopy(source['payload']),
        'source': f'product521 HTTP {source_id}; consumed development capture', 'criterion': criterion})

numeric_ids = ['H0111', 'H0342', 'H0539', 'H0508', 'H0114', 'gpu-usage-es',
               'H0650', 'processes-top3-en', 'H0104', 'H0127']
for case_id in numeric_ids:
    row = panel694[case_id]
    source = next(r for r in req694 if not r['payload'].get('tools')
        and r['payload']['messages'][0].get('content', '').startswith('Eres BAXY, un compañero.')
        and r['payload']['messages'][-1].get('content', '').startswith(row['text'] + '\n')
        and 'situation: ' in r['payload']['messages'][-1]['content'])
    cases.append({'id': 'writer694-' + case_id, 'kind': 'measured-facts', 'payload': copy.deepcopy(source['payload']),
        'source': f'product694 HTTP {source["id"]}; recorded observation, not current PC state',
        'criterion': row['criterion'] + ' In this native fixture only, judge against the supplied observation; no fresh hardware read is being claimed. Preserve numeric units, subjects and ranking; Wi-Fi absence is not absence of Internet.'})

system = next(r for r in req521 if r['id'] == 0)['payload']['messages'][0]
chats = [
    ('identity-es', '¿Quién eres?', 'Identify yourself as BAXY, not the user; Spanish, brief.'),
    ('name-es', 'Me llamo Vera. ¿Cómo me llamo?', 'The person is Vera, no claimed persistent storage.'),
    ('vocative-mixed', 'Hey Baxy, ¿cómo estás?', 'Respond naturally to the greeting; BAXY is the addressee, not the user name.'),
    ('knowledge-en', 'Why does ice float on water? Please explain briefly.', 'Brief English explanation: ice is less dense due to its open hydrogen-bonded crystal structure. No tools or PC facts.'),
    ('difference-es', 'Explica en una frase la diferencia entre RAM y VRAM.', 'Spanish: system memory versus GPU memory; no claim about quantities installed in this PC.'),
]
for case_id, text, criterion in chats:
    cases.append({'id': 'chat-' + case_id, 'kind': 'conversation',
        'payload': {'messages': [copy.deepcopy(system), {'role': 'user', 'content': text}], 'max_tokens': 512},
        'source': 'explicit development variation, not fresh human acceptance', 'criterion': criterion})

assert len(cases) == 50 and len({r['id'] for r in cases}) == 50
(private / 'panel.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
plan = {'status': 'frozen_before_K2_benchmark', 'cases': 50, 'selector': 20, 'prose_and_conversation': 30,
    'panel_sha256': sha(private / 'panel.json'), 'sources': {
        str(source694 / 'http-posts.jsonl'): sha(source694 / 'http-posts.jsonl'),
        str(source521 / 'http-posts.jsonl'): sha(source521 / 'http-posts.jsonl')},
    'case_index': [{k: v for k, v in row.items() if k != 'payload'} for row in cases],
    'method': 'Native semantic comparison before BAXY guards; exact shared messages/history/facts/catalog per case. Model-specific documented template/thinking/sampling and sufficient output budget. Prior bad answers in captured histories are identical inputs for both models, not expected outputs. Synthetic variants explicitly marked. Repeated writer521-6/10 retained, never called independent.',
    'criteria': 'Every output adjudicated against criterion and facts, not fluent prose or automatic pass alone. Report critical false execution/measurement/authority, wrong/missing tool, argument/parser failure, wrong language, and uncompleted reasoning. No coverage promotion or claim that native replay equals integrated BAXY.',
    'next': 'Backend smoke first; freeze effective model profiles after compatibility check, before50-case run. Compare registered and documented Qwen with K2 reference and interactive profiles, preserving all failed configurations.'}
(base / 'PANEL_PLAN.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'cases': 50, 'sha256': plan['panel_sha256'], 'kinds': sorted({r['kind'] for r in cases})}))
