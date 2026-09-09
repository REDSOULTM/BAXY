"""Prepare two distinct development replays after source340 validation."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-product339.py').read_text(encoding='utf-8')
hook_source = (root/'scratchpad/c03-owner339-hook/sitecustomize.py').read_text(encoding='utf-8')
for number in ('341', '342'):
    text = source.replace('339', number).replace('source321/324/326/330/333/336/338', 'source321/324/326/330/333/336/338/340')
    text = text.replace('Compared with337, only source338 scopes conversational capability facts to conversation situations;',
        'Compared with339, source340 adds guided enable confirmation and protected save continuation within MemoryTurnSession;')
    if number == '342':
        text = text.replace("indices = [99, 101, 103, 105, 107, 109]", "indices = [99, 103, 105, 107, 109]")
        text = text.replace("cases = [transcript[index]['body'] for index in indices]",
            "cases = [transcript[index]['body'] for index in indices]\ncases.insert(2, 'confirmar')\ncases.append('c\u00f3mo me llamo')")
        text = text.replace('Six exact human requests from owner264 transcript282 indices99,101,103,105,107,109 in their original order, one continuous session.',
            'Five exact development requests from owner264 indices99,103,105,107,109, with a synthetic explicit confirmar after the name and a synthetic final recall control. One continuous session. Added inputs are agent-created test controls, not historical human messages or fresh acceptance.')
        text = text.replace('the new profile remains memory-disabled by default and no activation is injected;',
            'the new profile starts disabled; an explicit confirmar is supplied as a test response to the expected enable challenge. No settings are changed outside the product;')
        text = text.replace("'criteria':'Honor the explicit request to remember a name,", "'criteria':'Enable only on the exact confirmation, verify private persistence and the requested greeting, then honor the explicit request to remember a name,")
    path = root/f'scratchpad/c03-product{number}.py'
    assert not path.exists()
    path.write_text(text,encoding='utf-8')
    hook = root/f'scratchpad/c03-owner{number}-hook'
    hook.mkdir(exist_ok=False)
    (hook/'sitecustomize.py').write_text(hook_source.replace('339',number),encoding='utf-8')
print('Prepared341 unchanged six human literals;342 separate flow with declared synthetic confirmation/recall controls.')
