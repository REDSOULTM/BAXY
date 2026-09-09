"""Verify native comparison and bounded writer adoption, including staged bytes."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root/'scratchpad/c03-audit-publication612-621.py').read_text(encoding='utf-8')
start = source.index('names=')
end = source.index('verified=0', start)
source = source[:start]+"names=['native-window-scope650','window-scope-source652','window-scope-product653']\n"+source[end:]
source = source.replace('d9ace8ac4adcf83af955276d1ed072b9a9ddff2fe85a26f2fa4511433dcc9425', 'e6993ddb155b9586dd178e5814604eb4ec25f7baf853d68a9c855d3d6e41de45')
exec(compile(source, __file__, 'exec'))
