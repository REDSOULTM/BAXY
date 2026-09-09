from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-progress-instruction88.py').read_text(encoding='utf-8')
source = source.replace("'astra-progress-instruction88'", "'astra-progress-role90'")
source = source.replace("for variant in ('activity_instruction',):", "for variant in ('dedicated_role', 'structured_request'):")
source = source.replace("if variant == 'activity_instruction':", "if variant in ('dedicated_role', 'structured_request'):")
needle = '            client.begin_request(40)'
addition = '''            if variant == 'dedicated_role':
                payload['messages'][0]['content'] = (
                    "You are BAXY, a companion. Write one brief natural first-person progress update "
                    "in the requested language. Describe only the current activity in situation. "
                    "The person's request is context for that activity, not proof that its action has started. "
                    "Return only the update.")
            else:
                lines = payload['messages'][-1]['content'].splitlines()
                assert lines[0].startswith('Texto original de la persona: ')
                lines[0] = 'requested_goal: ' + json.dumps({'text': case['text']}, ensure_ascii=False)
                payload['messages'][-1]['content'] = '\\n'.join(lines)
            client.begin_request(40)'''
source = source.replace(needle, addition)
start = source.index("prereg = {'method':")
end = source.index("    'sourceSha256':", start)
source = source[:start] + '''prereg = {'method': 'Native two orthogonal contrasts against recorded88. Same six cases and factual state. '
    'dedicated_role replaces the whole general narration system message with one progress role; '
    'structured_request keeps88 instructions and only frames the original imperative as requested_goal JSON. '
    'No source changes, appended correction stack, retries, functions/UI/audio/reserve or promotion. '
    'Judge actual interpretation phase, not just absence of claimed final success.',
''' + source[end:]
target = root / 'scratchpad/c03-progress-role90.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')

source = (root / 'scratchpad/c03-context89.py').read_text(encoding='utf-8')
source = source.replace("'astra-context89'", "'astra-context91'")
source = source.replace("for variant in ('without_context', 'previous_exchange_data'):", "for variant in ('previous_response_data',):")
source = source.replace("if variant == 'previous_exchange_data':", "if variant == 'previous_response_data':")
source = source.replace("situation['previousExchange'] = {'request': previous_request, 'response': previous_answer}",
    "situation['previousResponse'] = previous_answer")
start = source.index("prereg = {'method':")
end = source.index("    'cases':", start)
source = source[:start] + '''prereg = {'method': 'Same five89 cases and packets, replacing previousExchange data with previousResponse only. '
    'The App already supplies its previous published response as context, but its priorRequests list does '
    'not guarantee a matching preceding request if a turn ended without a published reply. Do not invent '
    'an association between those fields. Compare with recorded89; no repeated baseline, source/model/sampler '
    'change, functions/UI/audio/reserve or promotion. Prior limits control lacks real catalog context and '
    'is only a no-replay check, not capability acceptance.',
''' + source[end:]
target = root / 'scratchpad/c03-context91.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
