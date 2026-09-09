"""Prepare the unchanged seven-input development replay with source344."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root/'scratchpad/c03-product345.py'
assert not target.exists()
text = (root/'scratchpad/c03-product342.py').read_text(encoding='utf-8')
text = text.replace('342', '345')
text = text.replace('source321/324/326/330/333/336/338/340', 'source340/343b/344')
text = text.replace("'src/Baxy.App/PrivateOperationNarration.cs',", "'src/Baxy.App/PrivateOperationNarration.cs','src/Baxy.App/MemoryOperationResponseProjection.cs',")
text = text.replace('Compared with339, source340 adds guided enable confirmation and protected save continuation within MemoryTurnSession;', 'Compared with342, source344 transmits private results through observed/seen and names the pending private action; source343b aligns required-input publication;')
text = text.replace('then honor the explicit request', 'including an explanation that enabling local memory is being confirmed, then honor the explicit request')
target.write_text(text,encoding='utf-8')
hook = root/'scratchpad/c03-owner345-hook'
hook.mkdir(exist_ok=False)
(hook/'sitecustomize.py').write_text((root/'scratchpad/c03-owner342-hook/sitecustomize.py').read_text(encoding='utf-8').replace('342','345'),encoding='utf-8')
print('345 driver prepared with identical seven requests, isolated profile, current source pins, read-only observation.')
