"""Unchanged614 diagnostic profile, with620 trace destination."""
from pathlib import Path
root=Path(__file__).resolve().parents[2]
source=(root/'scratchpad/c03-gemma-chat614-hook/sitecustomize.py').read_text(encoding='utf-8')
exec(compile(source.replace('614','620'),__file__,'exec'))
