"""Repeat product355 with the greeting publication repair356 only."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / 'scratchpad/c03-product357.py'
assert not target.exists()
source = (root / 'scratchpad/c03-product355.py').read_text(encoding='utf-8')
source = source.replace('355', '357')
source = source.replace('source340/343b/344/354', 'source340/343b/344/354/356')
source = source.replace(
    'Compared with351, only source354 forwards typed operation identity to the composer; sampling is unchanged;',
    'Compared with355, source356 permits an exactly requested greeting through the App and Python echo checks while retaining the information-request echo rejection; sampling and model are unchanged;',
)
target.write_text(source, encoding='utf-8')
hook = root / 'scratchpad/c03-owner357-hook'
hook.mkdir(exist_ok=False)
(hook / 'sitecustomize.py').write_text(
    (root / 'scratchpad/c03-owner355-hook/sitecustomize.py').read_text(encoding='utf-8').replace('355', '357'),
    encoding='utf-8',
)
print('357 prepared: identical355 requests/model/profile isolation, source356 only difference.')
