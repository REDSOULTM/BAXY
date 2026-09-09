from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-selector-history65.py').read_text(encoding='utf-8')
target = root / 'scratchpad/c03-selector-history66.py'
assert not target.exists()
source = source.replace('astra-selector-history65', 'astra-selector-history66')
source = source.replace("('captured', 'no_context', 'scoped_history')", "('captured', 'native_roles', 'user_history_only')")
start = source.index("            if variant == 'no_context':")
end = source.index('            client.begin_request(40)', start)
source = source[:start] + '''            if variant == 'native_roles':
                payload['messages'] = [payload['messages'][0],
                    *context['previous_dialogue_for_references_only'],
                    {'role': 'user', 'content': context['current_request_to_interpret']}]
            elif variant == 'user_history_only':
                context['previous_dialogue_for_references_only'] = [
                    row for row in context['previous_dialogue_for_references_only'] if row['role'] == 'user']
                payload['messages'][-1]['content'] = json.dumps(context, ensure_ascii=False)
''' + source[end:]
source = source.replace("'registrationSha256':", "'comparison66': 'Compare unchanged captured JSON context with original dialogue as native role messages and current request as the last user message; separately omit only previous assistant messages inside the original JSON as a diagnostic. Native roles retain all references; user-only is not proposed as product behavior. No other sampling, tools or system policy change.',\n          'registrationSha256':", 1)
target.write_text(source, encoding='utf-8')
print('prepared66')
