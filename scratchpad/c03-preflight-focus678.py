"""Compile all inherited product constructors without snapshots or launch."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-preflight-literal665.py').read_text(encoding='utf-8')
source=source.replace('c03-literal-product665.py','c03-focus-coverage-product678.py').replace('C03-literal-product665-private','C03-focus-coverage-product678-private')
exec(compile(source,__file__,'exec'))
