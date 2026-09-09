"""Verify published possessive-use guard on current real CPU observations."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-cpu-actor-product582.py').read_text(encoding='utf-8')
source = source.replace('astra-cpu-actor-product582', 'astra-usage-product587').replace('C03-cpu-actor-product582-private', 'C03-usage-product587-private').replace('C03-cpu-actor-profile582', 'C03-usage-profile587').replace('c03-owner582-hook', 'c03-owner587-hook')
source = source.replace('source581', 'source584')
exec(compile(source, __file__, 'exec'))
