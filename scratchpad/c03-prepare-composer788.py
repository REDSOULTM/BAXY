"""Prepare the existing real-composer harness with the frozen785 panel."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
s = (ROOT / 'scratchpad/c03-clock-values784.py').read_text(encoding='utf-8')
s = s.replace('Fifty declared synthetic clock/calendar scenarios', 'Fifty frozen development inventory/memory/clock scenarios')
s = s.replace('CLOCK_VALUES784', 'INVENTORY_COMPOSER788').replace('C03-clock-values784-private', 'C03-inventory-composer788-private')
s = s.replace('NAMED_CLOCK783', 'INVENTORY_BUDGET787').replace('C03-status-batch779-private', 'C03-status-batch772-private')
s = s.replace('C03-clock-values780-private/cases.json', 'C03-prose-sampling785-private/cases.json')
s = s.replace("'groups': {'time': 25, 'date': 25}", "'groups': {'inventory': 26, 'memory': 23, 'clock': 1}")
s = s.replace('Identical50 cases, IDs, observed values, questions and criteria from780; only validator source783 changed. Original situation came from779.',
              'Identical50 cases, IDs, observed values, questions and criteria from785. Candidate787 changes dense inventory cap and quantity interpretation only; original model/sampler/prompt remain fixed.')
s = s.replace('previous779_server_command', 'previous772_server_command').replace('same779_command_except_port', 'same772_command_except_port')
s = s.replace('processes779', 'processes772').replace('actual779 environment', 'actual772 environment')
s = s.replace("'budget': {'per_request_seconds': 4", "'budget': {'per_request_seconds': '4 ordinary / 9 dense inventory, existing C#764 policy'")
s = s.replace('import time\n', 'import time\nimport urllib.request\n')
s = s.replace('from baxy_mind.llm import LlmRuntime\n', 'from baxy_mind.llm import LlmRuntime\n')
marker = "write(OUT / 'PREREG.json', prereg)"
insert = '''# Capture candidate first requests without loading or invoking a model.
class Captured(BaseException):
    pass


class Capture(LlmRuntime):
    def __init__(self):
        self._gguf = config['gguf']
        self.payload = None
    def _post(self, payload):
        self.payload = copy.deepcopy(payload)
        raise Captured()


old_planned = read(PRIVATE.parent / 'C03-prose-sampling785-private/planned.json')
old_payloads = {r['case_id']:r['payload'] for r in old_planned if r['arm'] == 'A_registered_greedy'}
expected_first = {}
for case in cases:
    capture = Capture()
    try:
        capture.compose_user_message(case['request'], 'status', {'situation': case['situation']})
    except Captured:
        pass
    candidate = capture.payload
    old = old_payloads[case['id']]
    assert candidate and candidate['max_tokens'] in {256,512}
    assert {k:v for k,v in candidate.items() if k != 'max_tokens'} == {k:v for k,v in old.items() if k != 'max_tokens'}
    expected_first[case['id']] = candidate
write(PRIVATE / 'expected-first.json', expected_first)
prereg['first_payloads_sha256'] = sha(PRIVATE / 'expected-first.json')
prereg['first_payload_message_parity785'] = 50
prereg['server_cwd'] = str(Path(config['python']).parent)
write(OUT / 'PREREG.json', prereg)'''
assert s.count(marker) == 1
s = s.replace(marker, insert)
start = s.index('class Client(LlmRuntime):')
end = s.index('\ndef normalized_command', start)
s = s[:start] + '''class Client(LlmRuntime):
    case_id = None
    attempts = {}

    def _post(self, payload, *args, **kwargs):
        attempt = self.attempts.get(self.case_id, 0) + 1
        self.attempts[self.case_id] = attempt
        if attempt == 1:
            assert payload == expected_first[self.case_id], self.case_id
        before = time.monotonic()
        response = super()._post(payload, *args, **kwargs)
        record = {'id': self.case_id, 'attempt': attempt, 'payload': payload,
                  'response': response, 'post_seconds': time.monotonic() - before}
        try:
            with urllib.request.urlopen(self._endpoint + '/slots', timeout=2) as stream:
                record['slots_after'] = json.load(stream)
        except Exception as exc:
            record['slots_unavailable'] = str(exc)
        with (PRIVATE / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\\n')
        return response

''' + s[end:]
s = s.replace('client = Client()\n', "os.chdir(Path(config['python']).parent)\nclient = Client()\n")
s = s.replace('        client.begin_request(4)\n', '''        situation = case['situation']
        windows = (situation.get('observed') or {}).get('windows')
        dense = (situation.get('operation') == 'window.resolve'
                 and situation.get('verified') is True and situation.get('succeeded') is True
                 and isinstance(windows, list)
                 and (len(windows) >= 8 or len(json.dumps(windows, ensure_ascii=False, separators=(',',':'))) >= 512))
        request_budget = 9 if dense else 4
        client.begin_request(request_budget)
''')
s = s.replace("row = {'id': case['id'], 'answer': answer", "row = {'id': case['id'], 'request_budget_seconds': request_budget, 'answer': answer")
target = ROOT / 'scratchpad/c03-inventory-composer788.py'
assert not target.exists()
compile(s, str(target), 'exec')
target.write_bytes(s.encode('utf-8'))
print(target)
