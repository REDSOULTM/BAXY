"""Prepare native required-input controls, explicitly synthetic."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
s = (root/'scratchpad/c03-product342.py').read_text(encoding='utf-8').replace('342','343')
s = s.replace('source321/324/326/330/333/336/338/340','source321/324/326/330/333/336/338/340/343')
start = s.index('cases = [transcript')
end = s.index('commands = ',start)
s = s[:start] + "cases = ['What can you do? Remember my name.', 'cancelar']\n" + s[end:]
start = s.index("    'method':")
end = s.index("    'cases':",start)
s = s[:start] + '''    'method':'Native shared product with registered2507; two declared synthetic generalization controls for required input after a capability question. No human provenance or fresh acceptance claim, no overrides, no GUI/physical voice.',
    'profile_inheritance':'Dedicated fresh disabled profile. Source343 carries the required input through composition and scopes the knowledge-question rule. Default memory configuration unchanged.',
    'criteria':'Ask the missing name in English on the first request. Do not answer with capabilities, claim a save, or fall silent. Cancellation clears pending input without storing anything.',
''' + s[end:]
path = root/'scratchpad/c03-product343.py'
assert not path.exists()
path.write_text(s,encoding='utf-8')
hook = root/'scratchpad/c03-owner343-hook'
hook.mkdir(exist_ok=False)
(hook/'sitecustomize.py').write_text(
    (root/'scratchpad/c03-owner342-hook/sitecustomize.py').read_text(encoding='utf-8').replace('342','343'),
    encoding='utf-8')
print('Prepared synthetic required-input and cancellation controls343.')
