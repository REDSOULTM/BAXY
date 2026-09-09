"""Prepare explicit synthetic generalization controls, preserving all runtime pins."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / 'scratchpad/c03-product364.py'
assert not target.exists()
source = (root / 'scratchpad/c03-product363.py').read_text(encoding='utf-8')
for old, new in [('product363', 'product364'), ('profile363', 'profile364'), ('owner363-hook', 'owner364-hook')]:
    source = source.replace(old, new)
source = source.replace('"""Six recovered owner turns through the complete shared product route."""',
    '"""Synthetic ES/EN name, confirmation and cancellation controls in a private profile."""')
start = source.index('transcript_path = ')
end = source.index("commands = [{'cmd'")
source = source[:start] + '''cases = [
    "My name is Jordan. Remember my name.",
    "What would I be confirming?",
    "cancel",
    "Who am I?",
    "What is my name?",
    "Me llamo Álvaro y quiero que guardes mi nombre.",
    "¿Qué vas a activar?",
    "cancelar",
    "quién soy ahora",
    "¿Cómo me llamo?",
]
''' + source[end:]
start = source.index("    'method':")
end = source.index("    'cases':", start)
source = source[:start] + '''    'method':'Ten explicitly synthetic development controls in one continuous private profile: namesJordan/Álvaro, ES/EN, ask what confirmation would authorize, cancel, then reference the session name without having enabled persistence. Same source362/modelQwen3.5/profile isolation as363; no runtime promotion, no classifier or response injection. These are not historical human messages or fresh acceptance. No graphical UI or physical voice evidence.',
    'profile_inheritance':'Dedicated LOCALAPPDATA/BAXY child, starts with persistence disabled. Only the typed product pipeline may change it. Requests expressly ask to remember a synthetic name but later cancel both enable challenges. No authorisation to affect owner memory; all journal/state are in the diagnostic profile. Model/sampling/template unchanged363.',
    'criteria':'Each request is answered in its language; confirmation explanation identifies enabling local memory and why needed, not an unspecified action. Cancel does not enable memory or save the name. Subsequent who-am-I and what-is-my-name can use the current conversation without falsely claiming persistence or substituting a Windows account. A newly declared name replaces the earlier conversational self-reference, without inventing a persistent update. Assess every terminal and journal; emitted text alone is not usefulness.',
''' + source[end:]
target.write_text(source, encoding='utf-8')
hook = root / 'scratchpad/c03-owner364-hook'
hook.mkdir(exist_ok=False)
(hook / 'sitecustomize.py').write_text(
    (root / 'scratchpad/c03-owner363-hook/sitecustomize.py').read_text(encoding='utf-8').replace('product363', 'product364'),
    encoding='utf-8',
)
print('364 prepared:10synthetic controls, runtime pins unchanged, source362.')
