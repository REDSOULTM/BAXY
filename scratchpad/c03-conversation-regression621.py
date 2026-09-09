"""Registered Qwen regression on candidate style source619, without hooks."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-conversation-regression592.py').read_text(encoding='utf-8')
source=source.replace('592','621').replace('source590','source619')
exec(compile(source,__file__,'exec'))
