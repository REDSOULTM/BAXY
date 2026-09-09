from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / 'scratchpad/c03-prepare144.py').read_text(encoding='utf-8')
source = source.replace('144', '148').replace('source143', 'source147')
exec(compile(source, str(__file__), 'exec'))
