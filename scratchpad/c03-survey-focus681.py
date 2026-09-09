"""Repeat the exact seven-case product panel after the relative-clause repair."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-survey-focus679.py').read_text(encoding='utf-8')
source = source.replace('survey-focus679', 'survey-focus681').replace('survey-focus-profile679', 'survey-focus-profile681')
source = source.replace('Shared source676 product', 'Shared source680 product')
exec(compile(source, __file__, 'exec'))
