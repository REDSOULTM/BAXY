"""Exact24 queries661 with Spanish policy candidate664."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-window-facts-product661.py').read_text(encoding='utf-8')
source=source.replace('window-facts-product661','literal-product665').replace('window-facts-profile661','literal-profile665').replace('Shared source660 product','Shared source664 product')
exec(compile(source,__file__,'exec'))
