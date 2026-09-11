"""Correlate every product706 stage; do not adjudicate by prior labels."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-review-status-batch694.py').read_text(encoding='utf-8')
exec(compile(source.replace('694', '706'), __file__, 'exec'))
