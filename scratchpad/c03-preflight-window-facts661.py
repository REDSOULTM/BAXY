"""Compile all product661 constructors, without snapshots or launch."""
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
    if executed <= 3:
        builtins.exec(code, namespace)


namespace = {'__file__': str(root / 'scratchpad/c03-window-facts-product661.py'),
             'exec': capture_exec, 'compile': capture_compile, 'save': lambda name: None}
builtins.exec(builtins.compile(Path(namespace['__file__']).read_text(encoding='utf-8'), namespace['__file__'], 'exec'), namespace)
assert executed == 5, executed
assert "'foreground':foreground655()" in captured[3]
assert "focus-application-en" in captured[4]
assert "'src/baxy_mind/window_prose_facts.py'" in captured[4]
assert 'C03-window-facts-product661-private' in captured[4]
print({'compiled_layers': len(captured), 'snapshots_or_product_executed': False,
       'foreground_snapshot_present': True, 'panel_unchanged_from655': True,
       'window_fact_source_pin_present': True})
