"""Prepare the same product replay after removing the redundant selector cut359."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / 'scratchpad/c03-product360.py'
assert not target.exists()
source = (root / 'scratchpad/c03-product357.py').read_text(encoding='utf-8').replace('357', '360')
source = source.replace('source340/343b/344/354/356', 'source340/343b/344/354/356/359')
source = source.replace(
    'Compared with355, source356 permits an exactly requested greeting through the App and Python echo checks while retaining the information-request echo rejection; sampling and model are unchanged;',
    'Compared with357, source359 retains the already bounded and sanitized history for native tool selection instead of truncating it a second time to six messages; sampling, model and all other source are unchanged;',
)
target.write_text(source, encoding='utf-8')
hook = root / 'scratchpad/c03-owner360-hook'
hook.mkdir(exist_ok=False)
(hook / 'sitecustomize.py').write_text(
    (root / 'scratchpad/c03-owner357-hook/sitecustomize.py').read_text(encoding='utf-8').replace('357', '360'),
    encoding='utf-8',
)
print('360 prepared: same357 requests/model/profile isolation, source359 only difference.')
