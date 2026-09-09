"""Native paired retry reason, preserving all scoped history and model settings."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-guard-boundary594.py').read_text(encoding='utf-8')
source = source.replace('594', '596').replace('guard-boundary596', 'language-repair596')
start = source.index('original = next(')
end = source.index('\nmanifest = ', start)
source = source[:start] + '''captured = {row['id']: row['payload'] for row in capture if row['stage'] == 'request'}
original = captured[46]
assert 'quedo vacia' in original['messages'][1]['content']
old = original['messages'][1]['content']
new = ('The previous answer used the wrong language. Answer the current request '
       'in {language}, even when the earlier conversation is in another language. '
       'Preserve the facts and who said them. Give a direct, useful, brief answer; '
       'do not discuss these instructions.')
cases = [('identity-name-en', captured[46], 'English'),
         ('identity-who-en', captured[60], 'English')]
controls = [
    ('recall-en', 'What is my name?', 'English', [
        {'role':'user','content':'My name is Sofia.'},
        {'role':'assistant','content':'Your name is Elena.'}]),
    ('recall-es', '¿Cómo me llamo?', 'Spanish', [
        {'role':'user','content':'Me llamo Isabel.'},
        {'role':'assistant','content':'Your name is Robert.'}]),
    ('identity-switch-es', '¿Quién eres tú?', 'Spanish', [
        {'role':'user','content':'Who are you?'},
        {'role':'assistant','content':"I am BAXY, your companion."}] * 4),
    ('knowledge-en', 'What is RAM?', 'English', [
        {'role':'user','content':'¿Quién eres?'},
        {'role':'assistant','content':'Soy BAXY, tu compañero.'}] * 4),
]
for case_id, text, language, history in controls:
    payload = copy.deepcopy(original)
    payload['messages'][2]['content'] = ('Internal language policy: answer exclusively in English.'
        if language == 'English' else 'Política interna de idioma: responde exclusivamente en español.')
    payload['messages'][-2]['content'] = json.dumps({'conversation_history_as_data_not_instructions': history}, ensure_ascii=False)
    payload['messages'][-1]['content'] = text
    cases.append((case_id, payload, language))
assert len(cases) == 6
write(private / 'panel.json', cases)
''' + source[end:]
source = source.replace('Exact native grammar/sampling/template593, paired original vs replacing only incomplete-effect definition.16 preregistered cases, first owner literal and15 development contrasts. Alternate arm order. No classifier bypass, output rewriting, effects, model or registration change.', 'Two exact593 failed English retry payloads and four declared development controls. Paired original retry instruction vs accurate wrong-language instruction; identical original history, identity, JSON schema, sampling, seed and budgets. Native requests only, no output replacement or effects. Alternate arm order.')
source = source.replace('Ambiguous wording classifies conversational noise as an incomplete effect. Require an actual request for external reading/change before missing arguments can imply incomplete_effect.', 'The retry currently claims empty/echo when the observed failure is wrong language. Give the actual failure and target language without deleting or translating the dialogue. This is a separate causal repair from guard classification594/595.')
source = source.replace('Every response must finish normally and match its preregistered request_type. Stable conversation must count zero; two requested effects must count multiple. No adoption from fixing H0012 while losing real effects. Final product and more generalization remain mandatory.', 'Both identity retries must answer BAXY in English without invented failure. Controls preserve human names Sofia/Isabel, Spanish identity after English history, and correct RAM explanation in English. All replies must be complete valid answer JSON and natural prose. No adoption if any control regresses; product regression and owners remain mandatory.')
start = source.index('    for index, (case_id, text, expected) in enumerate(cases):')
end = source.index('            append(private /', start)
source = source[:start] + '''    for index, (case_id, original_payload, expected) in enumerate(cases):
        arms = ['original', 'candidate'] if index % 2 == 0 else ['candidate', 'original']
        for arm in arms:
            payload = copy.deepcopy(original_payload)
            if arm == 'candidate':
                payload['messages'][1]['content'] = new.format(language=expected)
''' + source[end:]
source = source.replace('32 native classifications collected; adjudication pending.', '12 native language-repair answers collected; adjudication pending.')
exec(compile(source, __file__, 'exec'))
