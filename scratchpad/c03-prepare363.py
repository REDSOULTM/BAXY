"""Prepare the same integrated requests after the native dialogue repair362."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / 'scratchpad/c03-product363.py'
assert not target.exists()
source = (root / 'scratchpad/c03-product360.py').read_text(encoding='utf-8').replace('360', '363')
source = source.replace('source340/343b/344/354/356/359', 'source340/343b/344/354/356/359/362')
source = source.replace(
    'Compared with357, source359 retains the already bounded and sanitized history for native tool selection instead of truncating it a second time to six messages; sampling, model and all other source are unchanged;',
    'Compared with360, source362 passes the same bounded dialogue in native user/assistant roles with the current request literal; sampling, model and all other source are unchanged;',
)
target.write_text(source, encoding='utf-8')
hook = root / 'scratchpad/c03-owner363-hook'
hook.mkdir(exist_ok=False)
(hook / 'sitecustomize.py').write_text(
    (root / 'scratchpad/c03-owner360-hook/sitecustomize.py').read_text(encoding='utf-8').replace('360', '363'),
    encoding='utf-8',
)
print('363 prepared: same360 requests/model/profile isolation, source362 only difference.')
