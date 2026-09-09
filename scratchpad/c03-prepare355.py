"""Prepare product355 with source354 and the identical351 model override/inputs."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
target=root/'scratchpad/c03-product355.py'
assert not target.exists()
text=(root/'scratchpad/c03-product351.py').read_text(encoding='utf-8').replace('351','355')
text=text.replace('source340/343b/344','source340/343b/344/354')
text=text.replace('Source and sampling unchanged from345;', 'Compared with351, only source354 forwards typed operation identity to the composer; sampling is unchanged;')
target.write_text(text,encoding='utf-8')
hook=root/'scratchpad/c03-owner355-hook'
hook.mkdir(exist_ok=False)
(hook/'sitecustomize.py').write_text((root/'scratchpad/c03-owner351-hook/sitecustomize.py').read_text(encoding='utf-8').replace('351','355'),encoding='utf-8')
print('355 prepared: same351 inputs/model/profile isolation, source354 only difference.')
