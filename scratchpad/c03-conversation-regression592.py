"""Broader survey regression: literal identity, greetings, thanks and small talk."""
from pathlib import Path
import json
import os

root = Path(__file__).resolve().parents[1]
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-conversation-regression592-private'
private.mkdir(exist_ok=False)
registry = private.parent / 'C03-survey-requirements336-private/requirements.jsonl'
rows = {r['case_id']: r for r in map(json.loads, registry.read_text(encoding='utf-8').splitlines())}
groups = {
    'identity': ['H0012', 'H0120', 'H0145', 'H0502', 'H0517', 'H0657', 'H0717'],
    'greeting': ['H0122', 'H0131', 'H0448', 'H0515', 'H0595', 'H0648', 'H0670', 'H0687'],
    'thanks': ['H0115', 'H0200', 'H0218', 'H0298'],
    'small-talk': ['H0032', 'H0241'],
}
variants = {
    'identity': ['What is your name?', 'Tell me who you are.', 'Hola, who are you?',
                 '¿Cómo te llamas y qué haces aquí?'],
    'greeting': ['Good morning!', 'Hey there, how are you?', 'Hola Atlas, ¿cómo estás?',
                 'Buenas noches, BAXY.'],
    'thanks': ['Thank you for your help.', 'Muchas gracias, that helped.',
               'Te agradezco la ayuda.'],
    'small-talk': ['Estoy bien, ¿y tú?', 'Doing well, how about you?', 'Todo tranquilo por aquí.'],
}
criteria = {
    'identity': 'Identify BAXY and its real local assistant role naturally in the requested language. No invented human identity or capability. No required fixed opening.',
    'greeting': 'Respond naturally to the greeting and any how-are-you question; preserve BAXY identity when addressed by another name. Do not execute effects or demand an unnecessary task clarification.',
    'thanks': 'Acknowledge gratitude briefly and naturally, without inventing a performed task or requesting details that the message does not need.',
    'small-talk': 'Respond to the conversational acknowledgement and reciprocal question without inventing user facts, claiming an effect or treating it as a command.',
}
panel = []
for group, ids in groups.items():
    for case_id in ids:
        row = rows[case_id]
        assert row['expected_capability'] is True
        panel.append({'case_id': case_id, 'group': group, 'origin': 'owner historical survey',
                      'text': row['literal'], 'criterion': criteria[group]})
    for index, utterance in enumerate(variants[group]):
        panel.append({'case_id': f'{group}-variant-{index + 1}', 'group': group,
                      'origin': 'assistant development variant', 'text': utterance,
                      'criterion': criteria[group], 'supports': ids})
(private / 'panel.json').write_text(json.dumps(panel, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
source = (root / 'scratchpad/c03-private-product521.py').read_text(encoding='utf-8')
for old, new in [
    ('astra-private-product521', 'astra-conversation-regression592'),
    ('C03-private-product521-private', 'C03-conversation-regression592-private'),
    ('C03-private-profile521', 'C03-conversation-profile592'),
]:
    source = source.replace(old, new)
start = source.index('cases = ')
end = source.index('\n\ncommands =', start)
source = source[:start] + "cases = [row['text'] for row in json.loads((private/'panel.json').read_text(encoding='utf-8'))]" + source[end:]
start = source.index('prereg = {')
end = source.index("(out/'PREREG.json').write_text", start)
source = source[:start] + '''prereg = {
    'utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Shared source590 product, base registered runtime, built-in diagnostics only. Twenty-one owner survey literals plus fourteen ES/EN/mixed development variants across identity, greeting, gratitude and small talk. Same dialogue session, exact panel order. No parameter, payload, classification, draft or output replacement. No adapter override. This is development regression, not blind acceptance.',
    'criteria': 'Read every final and progress against the individual panel criterion; correct language, natural response and no invented facts or effects. Every literal receives an individual verdict; common family does not grant coverage by itself. Generalization variants support only their declared group. No UI or voice credit from this hidden conductor.',
    'manifest_sha256': sha(manifest), 'panel_sha256': sha(private/'panel.json'),
    'sources': {name: sha(root/name) for name in ['src/baxy_mind/cpu_prose_adapter.py', 'src/baxy_mind/llm.py', 'src/baxy_mind/__main__.py', 'src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.dll']},
    'private': str(private), 'case_count': len(cases),
    'resource_limits': {'gpu_stop_mib': 3800, 'minimum_free_ram_mib': 768, 'wall_time_seconds': 240},
}
''' + source[end:]
old = "str(root/'scratchpad/c03-owner521-hook')+os.pathsep+str(root/'src')"
assert source.count(old) == 1
source = source.replace(old, "str(root/'src')")
exec(compile(source, __file__, 'exec'))
