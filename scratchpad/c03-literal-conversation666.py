"""Repeat35 conversation cases611 with source664 and registered runtime."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-conversation-regression592.py').read_text(encoding='utf-8')
source=source.replace('592','666').replace('source590','source664')
exec(compile(source,__file__,'exec'))
