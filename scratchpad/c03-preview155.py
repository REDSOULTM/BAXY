from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-preview-reserve105.py').read_text(encoding='utf-8')
source=source.replace('    first = row', '    if not int(sys.argv[1]) <= index < int(sys.argv[2]):\n        continue\n    first = row')
exec(compile(source,str(__file__),'exec'))
