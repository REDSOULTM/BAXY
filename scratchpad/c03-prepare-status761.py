"""Reuse the registered73 observer with the newly validated source pins."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-status-batch752b.py').read_text(encoding='utf-8')
source = source.replace('STATUS_BATCH752B', 'STATUS_BATCH761').replace('752b', '761')
source = source.replace('WINDOW_INVENTORY751', 'SEMANTIC_INVENTORY760')
source = source.replace('pins751', 'pins760').replace('source751', 'source760')
source = source.replace('Registered product regression after published750/751; not a model comparison.',
                        'Registered73 product regression after semantic inventory760; same panel and criteria as752B, no model comparison.')
source = source.replace('Published751 owner tests and Fast, plus historical Full7; no new source edit.',
                        'Published760 owner tests, current integrity and Fast; Full7 is historical, not new product acceptance.')
source = source.replace("Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')",
                        "Path(path).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\\n').encode('utf-8'))")
target = root / 'scratchpad/c03-status-batch761.py'
assert not target.exists()
target.write_bytes(source.encode('utf-8'))
print(target)
