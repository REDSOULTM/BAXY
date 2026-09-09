"""Same35 cases592/603; complete language repair and sentence guard604, no hooks."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-conversation-regression592.py').read_text(encoding='utf-8')
source = source.replace('592', '605').replace('source590', 'source604')
exec(compile(source, __file__, 'exec'))
