"""Exact24 window queries661 with the unadopted precise projection667."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-window-facts-product661.py').read_text(encoding='utf-8')
source = source.replace('window-facts-product661', 'projection-product669').replace('window-facts-profile661', 'projection-profile669').replace('Shared source660 product', 'Shared source667 product')
exec(compile(source, __file__, 'exec'))
