"""Repeat exactly642 after contextual query and argument transport646."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-count-product642.py').read_text(encoding='utf-8')
source = source.replace('count-product642', 'context-product647').replace('count-profile642', 'context-profile647').replace('Shared source641 product', 'Shared source646 product')
exec(compile(source, __file__, 'exec'))
