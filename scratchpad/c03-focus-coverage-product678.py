"""Exact24 queries669 with candidate676, using shared product code."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-window-facts-product661.py').read_text(encoding='utf-8')
source=source.replace('window-facts-product661','focus-coverage-product678').replace('window-facts-profile661','focus-coverage-profile678').replace('Shared source660 product','Shared source676 product')
exec(compile(source,__file__,'exec'))
