"""Registered product regression after the progress-only language repair626."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-conversation-regression592.py').read_text(encoding='utf-8')
source=source.replace('592','627').replace('source590','source626')
exec(compile(source,__file__,'exec'))
