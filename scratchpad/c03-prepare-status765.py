"""Prepare the same73-case registered regression with both current source seals."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-status-batch761.py').read_text(encoding='utf-8')
source = source.replace('STATUS_BATCH761', 'STATUS_BATCH765').replace('batch761', 'batch765').replace('profile761', 'profile765')
source = source.replace(
    "assert all(sha(ROOT / path) == digest for path, digest in pins760.items())",
    "pins764 = read(ROOT / 'artifacts/comprobaciones/C03/DENSE_INVENTORY764/SOURCE_PINS.json')\n"
    "assert all(sha(ROOT / path) == digest for path, digest in {**pins760, **pins764}.items())")
source = source.replace(
    'Registered73 product regression after semantic inventory760; same panel and criteria as752B, no model comparison.',
    'Registered73 product regression after dense inventory764; same panel and criteria as761/752B, no model comparison.')
source = source.replace(
    'Published760 owner tests, current integrity and Fast; Full7 is historical, not new product acceptance.',
    'Published764 owners136pass and Fast; Python760 intact. Full7 historical, not new product acceptance.')
source = source.replace("'source760_pins': pins760,", "'source760_pins': pins760, 'source764_pins': pins764,")
source = source.replace(
    "'source760_unchanged': all(sha(ROOT / path) == digest for path, digest in pins760.items()),",
    "'source760_unchanged': all(sha(ROOT / path) == digest for path, digest in pins760.items()),\n"
    "           'source764_unchanged': all(sha(ROOT / path) == digest for path, digest in pins764.items()),")
assert 'pins764' in source and 'STATUS_BATCH761' not in source
target = root / 'scratchpad/c03-status-batch765.py'
assert not target.exists()
target.write_bytes(source.encode('utf-8'))
print(target)
