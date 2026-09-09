from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-files-empty60.py').read_text(encoding='utf-8')
source = source.replace("out = base / 'astra-files-empty60'", "out = base / 'astra-files-sandbox61'")
source = source.replace('no matches in the searched scope', 'no matches in the filesystem sandbox')
source = source.replace('Scope59 alone gave 0/2 useful replies.',
                        'Scope59 alone gave 0/2 useful replies. Empty60 removed the false system-data explanation '
                        'but left the searched scope unnamed; this variation identifies the actual known scope in the cause fact.')
target = root / 'scratchpad/c03-files-sandbox61.py'
assert not target.exists()
target.write_text(source, encoding='utf-8')
