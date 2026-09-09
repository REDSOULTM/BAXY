"""Same12 product controls608 after presentation-only source609."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-effect-controls608.py').read_text(encoding='utf-8')
source = source.replace('608', '610')
source = source.replace('Shared source606 baseline before the presentation change607.',
                        'Shared source609 candidate: incomplete guard no longer relabels primary knowledge as unsupported; compare baseline608.')
exec(compile(source, __file__, 'exec'))
