"""Check the three sealed artifacts against current source and staged bytes."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-audit-focus680-682.py').read_text(encoding='utf-8')
start = source.index('specs = [')
end = source.index('pins = 0',start)
source = source[:start]+'''specs = [
    ('astra-survey-focus687','C03-survey-focus687-private'),
    ('astra-compositor-window-identity688','C03-compositor-window-identity688-private'),
    ('astra-window-identity-source686',None),
]
'''+source[end:]
source = source.replace('astra-focus-subject-source680/RESULT.json','astra-window-identity-source686/RESULT.json')
exec(compile(source,__file__,'exec'))
