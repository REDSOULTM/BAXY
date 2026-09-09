"""Check contextual diagnostic evidence before publication."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-audit-publication612-621.py').read_text(encoding='utf-8')
start = source.index('names='); end = source.index('verified=0', start)
source = source[:start]+"names=['context-candidates643','native-context644','native-context645']\n"+source[end:]
source = source.replace('d9ace8ac4adcf83af955276d1ed072b9a9ddff2fe85a26f2fa4511433dcc9425', '464603566c9dc66204cc75e45a79c8058063d0bb06fe6ff554bf56529e5ea73e')
exec(compile(source, __file__, 'exec'))
