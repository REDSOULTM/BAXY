from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-product402b.py').read_text(encoding='utf-8')
for old, new in [('astra-stored-product402b', 'astra-stored-product404b'),
                 ('C03-stored-product402b-private', 'C03-stored-product404b-private'),
                 ('c03-owner402b-hook', 'c03-owner404b-hook'),
                 ('C03-stored-profile402b', 'C03-stored-profile404b')]:
    assert old in source
    source = source.replace(old, new)
source = source.replace('This is actual source, not401 injected facts.',
    'Source404 now lets generic name recall use the current role-bounded human self-naming context; explicit stored reads and a session without that context retain private dispatch. No name extraction/cache or model wording is added. Compare same six-turn402b profile. This is actual source, not injected facts or decisions.')
target = root / 'scratchpad/c03-product404b.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
hook = (root / 'scratchpad/c03-owner402b-hook/sitecustomize.py').read_text(encoding='utf-8')
hook = hook.replace('C03-stored-product402b-private', 'C03-stored-product404b-private')
folder = root / 'scratchpad/c03-owner404b-hook'
folder.mkdir(exist_ok=False)
(folder / 'sitecustomize.py').write_text(hook, encoding='utf-8')
