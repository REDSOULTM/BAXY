"""Repeat364 generalization controls after private name binding365 only."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / 'scratchpad/c03-product366.py'
assert not target.exists()
source = (root / 'scratchpad/c03-product364.py').read_text(encoding='utf-8')
for old, new in [('product364', 'product366'), ('profile364', 'profile366'), ('owner364-hook', 'owner366-hook')]:
    source = source.replace(old, new)
source = source.replace('Same source362/modelQwen3.5/profile isolation as363;',
    'Same modelQwen3.5 and ten controls364; source365 joins explicit name declaration and name-save authority, including compound names, without changing model/prompt or public response guards;')
source = source.replace('Model/sampling/template unchanged363.', 'Model/sampling/template unchanged364.')
target.write_text(source, encoding='utf-8')
hook = root / 'scratchpad/c03-owner366-hook'
hook.mkdir(exist_ok=False)
(hook / 'sitecustomize.py').write_text(
    (root / 'scratchpad/c03-owner364-hook/sitecustomize.py').read_text(encoding='utf-8').replace('product364', 'product366'),
    encoding='utf-8',
)
print('366 prepared: same10 controls364, source365 only; runtime hashes unchanged.')
