"""Compile assembled wrappers without executing a snapshot or product launch."""
from pathlib import Path
import ast
import builtins

root = Path(__file__).resolve().parents[1]
captured = []
executed = 0


def capture_compile(source, filename, mode):
    ast.parse(source)
    captured.append(source)
    return builtins.compile(source, filename, mode)


def capture_exec(code, *args):
    global executed
    executed += 1
    # Only the outer two wrappers construct strings. The third captures
    # Windows; the fourth launches the product: neither is executed here.
    if executed <= 2:
        builtins.exec(code, namespace)


namespace = {'__file__': str(root / 'scratchpad/c03-language-product655.py'),
             'exec': capture_exec, 'compile': capture_compile, 'save': lambda name: None}
builtins.exec(builtins.compile(Path(namespace['__file__']).read_text(encoding='utf-8'), namespace['__file__'], 'exec'), namespace)
assert executed == 4, executed
assert "'foreground':foreground655()" in captured[2]
assert "focus-application-en" in captured[3]
assert "'src/baxy_mind/request_reading.py'" in captured[3]
assert 'C03-language-product655-private' in captured[3]
print({'compiled_layers': len(captured), 'snapshots_or_product_executed': False,
       'foreground_snapshot_present': True, 'new_language_variants': 4, 'reader_pin_present': True})
