"""Same35 survey/variant turns as592, production language repair602, no hooks."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-conversation-regression592.py').read_text(encoding='utf-8')
source = source.replace('592', '603').replace('source590', 'source602')
exec(compile(source, __file__, 'exec'))
