"""Repeat the exact seven queries after identity/Boolean factual verification repair."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-survey-focus679.py').read_text(encoding='utf-8')
source = source.replace('survey-focus679', 'survey-focus687').replace('survey-focus-profile679', 'survey-focus-profile687')
source = source.replace('Shared source676 product', 'Shared source686 product')
exec(compile(source, __file__, 'exec'))
