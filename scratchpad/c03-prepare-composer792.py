"""Prepare paired integration ablation, never a native model comparison."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / 'scratchpad/c03-inventory-composer792.py'
assert not target.exists()
text = (ROOT / 'scratchpad/c03-inventory-composer790.py').read_text(encoding='utf-8')
text = text.replace('790', '792').replace('INVENTORY_IDENTITY789', 'INVENTORY_IDENTITY791')


def change(old, new):
    global text
    assert text.count(old) == 1, old
    text = text.replace(old, new)


change('Fifty frozen development inventory/memory/clock scenarios through the real local composer.',
       'The same fifty frozen tasks per arm: original versus factual correction without rejected_draft.')
change("'candidate': 'INVENTORY_IDENTITY791 including preserved787; validated but not adopted yet', 'cases': len(cases),",
       "'candidate': 'INVENTORY_IDENTITY791 including787+789; validated, unadopted', 'cases': len(cases), 'executions': 100,\n"
       "    'arms': {'A': 'Original composer payload', 'B': 'Remove only rejected_draft from Verified factual correction JSON at HTTP boundary'},\n"
       "    'order': 'AB on even zero-based case index, BA on odd; same persistent backend, request context reset per execution',")
change("'template_source': 'Identical50 cases/IDs/observed values/questions/criteria from788. Candidate789 adds identity-count factual feedback; first messages, output caps, model/sampler/backend remain fixed.'",
       "'template_source': 'Same50 cases, questions, observations and whole-answer criteria as785/788/790. Each arm gets all50; first messages/caps/model/sampler/backend/deadlines identical. Only B retry rejected_draft is removed.'")
change("'wall_seconds': 600", "'wall_seconds': 1200")
change('time.monotonic() - started > 600', 'time.monotonic() - started > 1200')
start = text.index('class Client(LlmRuntime):')
end = text.index('\n\ndef normalized_command', start)
replacement = '''def remove_rejected_draft(payload):
    result = copy.deepcopy(payload)
    removed = []
    marker = "\\nVerified factual correction: "
    for index, message in enumerate(result.get('messages', [])):
        content = message.get('content')
        if message.get('role') != 'user' or not isinstance(content, str) or marker not in content:
            continue
        before, rest = content.rsplit(marker, 1)
        correction, stop_at = json.JSONDecoder().raw_decode(rest)
        if not isinstance(correction, dict) or 'rejected_draft' not in correction:
            continue
        original = copy.deepcopy(correction)
        draft = correction.pop('rejected_draft')
        message['content'] = before + marker + json.dumps(correction, ensure_ascii=False) + rest[stop_at:]
        recovered, _ = json.JSONDecoder().raw_decode(message['content'].rsplit(marker, 1)[1])
        recovered['rejected_draft'] = draft
        assert recovered == original
        removed.append({'message_index': index, 'rejected_draft': draft})
    # Reconstruct the original object to prove there are no other differences.
    reconstructed = copy.deepcopy(result)
    for item in removed:
        index = item['message_index']
        reconstructed['messages'][index]['content'] = payload['messages'][index]['content']
    assert reconstructed == payload
    return result, removed


# Exact inherited payloads prove the intervention before any model inference.
prior_posts = PRIVATE.parent / 'C03-inventory-composer790-private/posts.jsonl'
probe_count = 0
with prior_posts.open(encoding='utf-8') as stream:
    for line in stream:
        prior = json.loads(line)
        actual, removed = remove_rejected_draft(prior['payload'])
        if prior['attempt'] == 1:
            assert actual == prior['payload'] and not removed
        probe_count += bool(removed)
assert probe_count > 0
prereg['intervention_replayed_on790_payloads'] = probe_count
write(OUT / 'PREREG.json', prereg)


class Client(LlmRuntime):
    case_id = None
    arm = None
    attempts = {}

    def _post(self, payload, *args, **kwargs):
        key = (self.case_id, self.arm)
        attempt = self.attempts.get(key, 0) + 1
        self.attempts[key] = attempt
        original_payload = copy.deepcopy(payload)
        removed = []
        if self.arm == 'B':
            payload, removed = remove_rejected_draft(payload)
        if attempt == 1:
            assert payload == original_payload == expected_first[self.case_id]
            assert not removed
        before = time.monotonic()

        def attempt_event(state, **fields):
            with (PRIVATE / 'attempts.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'id': self.case_id, 'arm': self.arm, 'attempt': attempt,
                                         'state': state, 'utc': utc(), **fields}, ensure_ascii=False) + '\\n')
        attempt_event('started', payload=payload, original_payload=original_payload, removed=removed)
        try:
            response = super()._post(payload, *args, **kwargs)
        except Exception as exc:
            attempt_event('failed', error=f'{type(exc).__name__}: {exc}', seconds=time.monotonic() - before)
            raise
        attempt_event('succeeded', seconds=time.monotonic() - before)
        record = {'id': self.case_id, 'arm': self.arm, 'attempt': attempt, 'payload': payload,
                  'original_payload': original_payload, 'removed': removed,
                  'response': response, 'post_seconds': time.monotonic() - before}
        try:
            with urllib.request.urlopen(self._endpoint + '/slots', timeout=2) as stream:
                record['slots_after'] = json.load(stream)
        except Exception as exc:
            record['slots_unavailable'] = str(exc)
        with (PRIVATE / 'posts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\\n')
        return response
'''
text = text[:start] + replacement + text[end:]
change("    for case in cases:\n        assert not violations, violations",
       "    executions = [(case, arm) for index, case in enumerate(cases) for arm in (('A', 'B') if index % 2 == 0 else ('B', 'A'))]\n"
       "    for case, arm in executions:\n        assert not violations, violations\n        client.arm = arm")
change("row = {'id': case['id'], 'request_budget_seconds': request_budget, 'answer': answer, 'error': error, 'attempts': client.attempts[case['id']], 'seconds': time.monotonic() - case_started}",
       "row = {'id': case['id'], 'arm': arm, 'request_budget_seconds': request_budget, 'answer': answer, 'error': error, 'attempts': client.attempts.get((case['id'], arm), 0), 'seconds': time.monotonic() - case_started}")
change("{'completed': len(replies), 'registered': len(cases)}", "{'completed': len(replies), 'registered': 100}")
change("'cases_completed': len(replies), 'cases_registered': len(cases)", "'executions_completed': len(replies), 'executions_registered': 100, 'distinct_cases': len(cases)")
change('len(replies) == 50 else 1', 'len(replies) == 100 else 1')
compile(text, str(target), 'exec')
target.write_bytes(text.encode('utf-8'))
print(target)
