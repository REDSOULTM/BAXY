"""Repeat the exact17 integrated focus/state cases with candidate686."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-compositor-focus-feedback675.py').read_text(encoding='utf-8')
source = source.replace('compositor-focus-feedback675', 'compositor-window-identity688').replace('compositor674', 'compositor686')
source = source.replace('Integrated source674 appends externally verified field contradiction to the existing retry; compare retry payloads to673.', 'Integrated source686 distinguishes requested window identity and Boolean focus, and binds postposed subjects. Same17 cases677; preserve contradictory and compound predicate coverage. No model, system instruction or reply template change.')
exec(compile(source, __file__, 'exec'))
