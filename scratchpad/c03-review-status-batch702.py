"""Correlate702 with the same private evidence reader used for694."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-review-status-batch694.py').read_text(encoding='utf-8')
source=source.replace('694','702')
exec(compile(source,__file__,'exec'))
