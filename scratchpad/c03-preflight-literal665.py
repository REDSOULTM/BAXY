"""Compile every665 constructor without Windows snapshots or product launch."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'scratchpad/c03-preflight-window-facts661.py').read_text(encoding='utf-8')
source=source.replace('executed <= 3','executed <= 4').replace('executed == 5','executed == 6')
source=source.replace('captured[3]','captured[4]').replace('captured[4]\n','captured[5]\n')
# Replace the exact assertions explicitly, without index replacement cascades.
source=source.replace('assert "\'foreground\':foreground655()" in captured[5]', 'assert "\'foreground\':foreground655()" in captured[4]')
source=source.replace('c03-window-facts-product661.py','c03-literal-product665.py').replace('C03-window-facts-product661-private','C03-literal-product665-private')
exec(compile(source,__file__,'exec'))
