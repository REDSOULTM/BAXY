"""Correct the observer setup: preserve the original helper's PSScriptRoot."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = (root / "scratchpad/c03-packaging-phases718.py").read_text(encoding="utf-8")
source = source.replace('astra-packaging-phases718"', 'astra-packaging-phases718/attempt2"')
source = source.replace('BAXY/C03-packaging-phases718-private"', 'BAXY/C03-packaging-phases718-private/attempt2"')
source = source.replace('instrumented.write_text(helper, encoding="utf-8")', 'instrumented.write_text(segment, encoding="utf-8")')
source = source.replace('command.replace(old_import, f". \'{instrumented}\'\\n',
                        'command.replace(old_import, old_import + f"\\n. \'{instrumented}\'\\n')
assert 'old_import + f"\\n.' in source
exec(compile(source, __file__, "exec"))
