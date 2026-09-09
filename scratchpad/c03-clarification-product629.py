"""Same608 controls plus missing-level variants on the shared product source628."""
from pathlib import Path
import json
import os

root = Path(__file__).resolve().parents[1]
private = Path(os.environ['LOCALAPPDATA'])/'BAXY/C03-clarification-product629-private'
private.mkdir(exist_ok=False)
panel = json.loads((private.parent/'C03-effect-controls608-private/panel.json').read_text(encoding='utf-8'))
variants = ['Fija el volumen del sistema al…', 'Ajusta el volumen en...',
    'Set the volume to...', 'Set the volume at…', 'Change the volume on my computer to',
    'Baxy, ponme el volumen a', 'Please adjust the volume to...', 'Set el volumen to...']
for i, text in enumerate(variants,1):
    panel.append({'case_id':f'missing-level-variant-{i}','text':text,
        'origin':'assistant development contrast','criterion':'Ask for the missing volume level in the appropriate language, no invented value or audio change; no refusal, repeated clarification or internal error.'})
(private/'panel.json').write_text(json.dumps(panel,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
source = (root/'scratchpad/c03-effect-controls608.py').read_text(encoding='utf-8')
source = source[source.index("source = (root / 'scratchpad/c03-conversation-regression592.py')"):]
source = source.replace('astra-effect-controls608','astra-clarification-product629').replace('C03-effect-controls608-private','C03-clarification-product629-private').replace('C03-effect-profile608','C03-clarification-profile629')
source = source.replace('Shared source606 baseline before the presentation change607. Twelve preregistered identity, missing-argument, physical unsupported, negation and knowledge contrasts.',
    'Shared source628 existing missing-level parser extension. Same12 preregistered608 identity, missing-argument, physical unsupported, negation and knowledge controls plus8 new missing-level ES/EN/mixed variants.20 turns.')
exec(compile(source,__file__,'exec'))
