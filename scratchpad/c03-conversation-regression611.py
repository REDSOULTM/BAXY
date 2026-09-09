"""Same35 product cases605 after presentation-only source609."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-conversation-regression592.py').read_text(encoding='utf-8')
source = source.replace('592', '611').replace('source590', 'source609')
exec(compile(source, __file__, 'exec'))
