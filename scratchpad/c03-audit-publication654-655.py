"""Verify the validated language source and both sealed campaigns."""
from pathlib import Path
import hashlib
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-audit-publication612-621.py').read_text(encoding='utf-8')
start, end = source.index('names='), source.index('verified=0')
source = source[:start] + "names=['language-source654','language-product655']\n" + source[end:]
source = source.replace('d9ace8ac4adcf83af955276d1ed072b9a9ddff2fe85a26f2fa4511433dcc9425', 'e6993ddb155b9586dd178e5814604eb4ec25f7baf853d68a9c855d3d6e41de45')
exec(compile(source, __file__, 'exec'))
reader = root / 'src/baxy_mind/request_reading.py'
expected = '5598275ce957f36430063a0f4fb1811b87ec9bc077fb09900c5c69684c139025'
assert hashlib.sha256(reader.read_bytes()).hexdigest() == expected
if '--staged' in sys.argv:
    staged = subprocess.check_output(['git', 'show', ':src/baxy_mind/request_reading.py'], cwd=root)
    assert staged.replace(b'\r\n', b'\n') == reader.read_bytes().replace(b'\r\n', b'\n')
print({'reader_validated': True, 'staged_source_equal_except_line_endings': '--staged' in sys.argv})
