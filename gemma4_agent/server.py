"""Runnable wrapper: `python -m gemma4_agent.server` -> `gemma4_agent.infra.server`.

Reorg 2026-05-28: el modulo real vive en `gemma4_agent.infra.server`.
Este archivo es un ejecutable minimo que reexpone `main()` para que las
Windows Scheduled Tasks y los atajos del usuario sigan funcionando con
el path historico.

Para `import` (no `python -m`), usar el path real:
    from gemma4_agent.infra.server import X

No re-aliasa sys.modules para no provocar RuntimeWarning en runpy.
"""
from __future__ import annotations


def main() -> int:
    from .infra.server import main as _main
    return _main()


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main() or 0)
