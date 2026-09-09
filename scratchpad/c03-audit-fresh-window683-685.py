"""Reuse the publication audit for the three sealed current-read artifacts."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-audit-focus680-682.py').read_text(encoding='utf-8')
start = source.index('specs = [')
end = source.index('pins = 0', start)
source = source[:start] + '''specs = [
    ('astra-survey-focus684', 'C03-survey-focus684-private'),
    ('astra-native-paraphrase685', 'C03-native-paraphrase685-private'),
    ('astra-fresh-window-source683', None),
]
''' + source[end:]
source = source.replace('astra-focus-subject-source680/RESULT.json', 'astra-fresh-window-source683/RESULT.json')
exec(compile(source, __file__, 'exec'))
