"""Repeat714 with the product-supported private root layout; preserve714 evidence."""
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-core-catalog-smoke714.py').read_text(encoding='utf-8')
source=source.replace('714','715')
source=source.replace("private.mkdir()", "private.mkdir()\nassert not private.with_name('C03-core-catalog-smoke715-data').exists()")
source=source.replace("str(private/'data')", "str(private.with_name('C03-core-catalog-smoke715-data'))")
exec(compile(source,__file__,'exec'))
