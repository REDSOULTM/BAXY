"""Exercise integrated verified feedback on original fixtures and renamed subjects."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-compositor-window-states672.py').read_text(encoding='utf-8')
source = source.replace('compositor-window-states672', 'compositor-focus-feedback675')
source = source.replace('compositor671', 'compositor674')
source = source.replace('assert len(panel) == 14', '''for case_id in ['topmost-es-true','topmost-es-false','topmost-en-false']:
    original = next(row for row in panel if row['case_id'] == case_id)
    renamed = copy.deepcopy(original)
    name = 'Brújula 7' if original['language'] == 'es' else 'Nimbus 41'
    renamed['case_id'] += '-renamed'
    renamed['text'] = renamed['text'].replace('Atlas', name)
    renamed['facts']['situation'] = renamed['facts']['situation'].replace('Atlas', name)
    panel.append(renamed)
assert len(panel) == 17''')
source = source.replace("'cases':14", "'cases':17")
source = source.replace('Same14 fixture requests668.', 'Same14 fixture requests668 plus three renamed subjects673. Integrated source674 appends externally verified field contradiction to the existing retry; compare retry payloads to673.')
source = source.replace('Collected14 compositor outcomes', 'Collected17 compositor outcomes')
exec(compile(source, __file__, 'exec'))
