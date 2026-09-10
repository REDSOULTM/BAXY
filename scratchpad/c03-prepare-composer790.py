"""Prepare same50 frozen composer scenarios; log attempts before HTTP dispatch."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'scratchpad/c03-inventory-composer788.py'
target = ROOT / 'scratchpad/c03-inventory-composer790.py'
assert not target.exists()
text = source.read_text(encoding='utf-8').replace('788', '790').replace('INVENTORY_BUDGET787', 'INVENTORY_IDENTITY789')


def change(old, new):
    global text
    assert text.count(old) == 1, old
    text = text.replace(old, new)


change("assert validation['failed'] == 0 and validation['fast_exit_code'] == 0 and validation['terminal_collected']",
       "assert validation['python_exit_code'] == validation['fast_exit_code'] == 0 and validation['terminal_collected']")
change("'candidate': 'INVENTORY_IDENTITY789, validated but not adopted yet'",
       "'candidate': 'INVENTORY_IDENTITY789 including preserved787; validated but not adopted yet'")
change("'template_source': 'Identical50 cases, IDs, observed values, questions and criteria from785. Candidate787 changes dense inventory cap and quantity interpretation only; original model/sampler/prompt remain fixed.'",
       "'template_source': 'Identical50 cases/IDs/observed values/questions/criteria from788. Candidate789 adds identity-count factual feedback; first messages, output caps, model/sampler/backend remain fixed.'")
change("'method': 'Real local BAXY composer with first draft and all retries retained; not bare/native model ranking. '",
       "'method': 'Real local BAXY composer: all attempts logged before dispatch, successful responses and failed outcomes retained; not native model ranking. '")
start = text.index("old_planned = read(PRIVATE.parent / 'C03-prose-sampling785-private/planned.json')")
end = text.index('expected_first = {}', start)
text = text[:start] + "old_payloads = read(PRIVATE.parent / 'C03-inventory-composer788-private/expected-first.json')\n" + text[end:]
change("assert {k:v for k,v in candidate.items() if k != 'max_tokens'} == {k:v for k,v in old.items() if k != 'max_tokens'}",
       "assert candidate == old, case['id']")
change("prereg['first_payload_message_parity785'] = 50",
       "prereg['first_payload_exact_parity788'] = 50\nassert sha(PRIVATE / 'cases.json') == sha(PRIVATE.parent / 'C03-inventory-composer788-private/cases.json')")
change("        response = super()._post(payload, *args, **kwargs)",
       """        def attempt_event(state, **fields):
            with (PRIVATE / 'attempts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'id': self.case_id, 'attempt': attempt, 'state': state,
                                         'utc': utc(), **fields}, ensure_ascii=False) + '\\n')
        attempt_event('started', payload=payload)
        try:
            response = super()._post(payload, *args, **kwargs)
        except Exception as exc:
            attempt_event('failed', error=f'{type(exc).__name__}: {exc}', seconds=time.monotonic() - before)
            raise
        attempt_event('succeeded', seconds=time.monotonic() - before)""")
change("row = {'id': case['id'], 'request_budget_seconds': request_budget, 'answer': answer, 'error': error, 'seconds': time.monotonic() - case_started}",
       "row = {'id': case['id'], 'request_budget_seconds': request_budget, 'answer': answer, 'error': error, 'attempts': client.attempts[case['id']], 'seconds': time.monotonic() - case_started}")
target.write_bytes(text.encode('utf-8'))
print(target)
