from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-product393b.py').read_text(encoding='utf-8')
for old, new in [
    ('astra-stored-product393b', 'astra-stored-product402b'),
    ('C03-stored-product393b-private', 'C03-stored-product402b-private'),
    ('c03-owner393b-hook', 'c03-owner402b-hook'),
    ('C03-stored-profile393b', 'C03-stored-profile402b'),
]:
    assert old in source
    source = source.replace(old, new)
old = 'Source393 adds explicit stored-name reads to the existing sealed private route; source383 preserves native conversation drafts under guards.'
new = 'Source402 transports the short single projected read value via existing requiredFacts and enforces it in App acceptance; source395 retains retry history and397 fixes the accented-name language guard. Cases and profile setup are unchanged from393b. This is actual source, not401 injected facts.'
assert old in source
source = source.replace(old, new)
target = root / 'scratchpad/c03-product402b.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
hook = (root / 'scratchpad/c03-owner393b-hook/sitecustomize.py').read_text(encoding='utf-8')
hook = hook.replace('C03-stored-product393b-private', 'C03-stored-product402b-private')
folder = root / 'scratchpad/c03-owner402b-hook'
folder.mkdir(exist_ok=False)
(folder / 'sitecustomize.py').write_text(hook, encoding='utf-8')
