"""Compile inherited product constructor without executing effects."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-preflight-literal665.py').read_text(encoding='utf-8')
source = source.replace('c03-literal-product665.py', 'c03-projection-product669.py').replace('C03-literal-product665-private', 'C03-projection-product669-private')
exec(compile(source, __file__, 'exec'))
