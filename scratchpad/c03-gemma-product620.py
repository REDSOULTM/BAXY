"""Repeat614 with candidate source619; preserve the exact model/chat profile."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-gemma-product614.py').read_text(encoding='utf-8')
source=source.replace('614','620').replace('source606','source619')
exec(compile(source,__file__,'exec'))
