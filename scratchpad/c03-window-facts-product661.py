"""Repeat the exact655 product panel with the validated fact contract candidate."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-language-product655.py').read_text(encoding='utf-8')
source = source.replace('language-product655','window-facts-product661').replace('language-profile655','window-facts-profile661').replace('Shared source654 product','Shared source660 product')
old = "'src/baxy_mind/request_reading.py', 'src/baxy_mind/cpu_prose_adapter.py',"
new = "'src/baxy_mind/window_prose_facts.py', 'src/baxy_mind/request_reading.py', 'src/baxy_mind/cpu_prose_adapter.py',"
assert source.count(old) == 1
source = source.replace(old,new)
exec(compile(source,__file__,'exec'))
