"""Repeat the exact640 panel after count request preservation641."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-window-reference-product640.py').read_text(encoding='utf-8')
source=source.replace('window-reference-product640','count-product642').replace('window-reference-profile640','count-profile642').replace('Shared source638 product','Shared source641 product')
exec(compile(source,__file__,'exec'))
