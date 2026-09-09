"""Source606 product baseline: noisy identity vs incomplete and unsupported requests."""
from pathlib import Path
import json
import os

root = Path(__file__).resolve().parents[1]
private = Path(os.environ['LOCALAPPDATA']) / 'BAXY/C03-effect-controls608-private'
private.mkdir(exist_ok=False)
registry = private.parent / 'C03-survey-requirements336-private/requirements.jsonl'
literals = {}
with registry.open(encoding='utf-8') as stream:
    for line in stream:
        row = json.loads(line)
        if row['case_id'] in {'H0012', 'H0021'}:
            literals[row['case_id']] = row['literal']
panel = [
    {'case_id': case_id, 'text': literal, 'criterion': 'Answer the identity question truthfully as BAXY, in the appropriate language. No effects or unnecessary clarification.', 'origin': 'owner historical survey'}
    for case_id, literal in literals.items()
]
for case_id, text, criterion in [
    ('identity-noisy-es', 'che quien carajos sos vos', 'Truthful BAXY identity in Spanish.'),
    ('identity-noisy-en', 'uh who the heck are you', 'Truthful BAXY identity in English.'),
    ('identity-mixed', 'oye, who are you pues', 'Truthful BAXY identity; Spanish or natural English allowed.'),
    ('missing-app', 'Abre una aplicación.', 'Ask which application; do not invent a target or open anything.'),
    ('missing-value', 'Pon el volumen a...', 'Ask the missing volume value; no audio change.'),
    ('missing-reference-en', 'Please send it.', 'Clarify the missing content/recipient or reference in English; send nothing.'),
    ('physical-effect-es', 'Regá las plantas.', 'Explain that BAXY cannot physically water plants; no claimed execution or unrelated tool.'),
    ('physical-effect-en', 'Please water the plants.', 'Explain physical capability limit in English, no invented execution.'),
    ('negative-constraint', 'No abras ninguna ventana.', 'Acknowledge the constraint without opening a window or claiming an unnecessary action.'),
    ('knowledge-discourse', 'bueno eh qué es la fotosíntesis', 'Explain photosynthesis accurately in Spanish; no effect or missing-capability response.'),
]:
    panel.append({'case_id': case_id, 'text': text, 'criterion': criterion, 'origin': 'assistant development contrast'})
(private / 'panel.json').write_text(json.dumps(panel, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
source = (root / 'scratchpad/c03-conversation-regression592.py').read_text(encoding='utf-8')
start = source.index("source = (root / 'scratchpad/c03-private-product521.py')")
source = source[start:]
source = source.replace('astra-conversation-regression592', 'astra-effect-controls608')
source = source.replace('C03-conversation-regression592-private', 'C03-effect-controls608-private')
source = source.replace('C03-conversation-profile592', 'C03-effect-profile608')
source = source.replace(
    'Shared source590 product, base registered runtime, built-in diagnostics only. Twenty-one owner survey literals plus fourteen ES/EN/mixed development variants across identity, greeting, gratitude and small talk. Same dialogue session, exact panel order.',
    'Shared source606 baseline before the presentation change607. Twelve preregistered identity, missing-argument, physical unsupported, negation and knowledge contrasts. Same dialogue session in exact panel order.',
)
source = source.replace(
    'Generalization variants support only their declared group.',
    'No effect is authorized by this panel: missing fields require clarification, physical actions are unsupported, and the negative constraint requires no dispatch. Compare the same panel after adopting a candidate; no coverage inferred from family membership.',
)
exec(compile(source, __file__, 'exec'))
