"""Seal704 only after all73 finals and every compose stage are adjudicated."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-seal-status694.py').read_text(encoding='utf-8')
source = source.replace('694', '704')
source = source.replace("home/'C03-status-batch689-private/adjudication.json'", "home/'C03-status-batch702-private/adjudication.json'")
source = source.replace('before689', 'before702').replace('transitions689', 'transitions702')
exec(compile(source, __file__, 'exec'))
