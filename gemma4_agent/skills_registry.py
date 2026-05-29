"""Runnable wrapper: `python -m gemma4_agent.skills_registry` -> `gemma4_agent.tools_pkg.skills_registry`.

Reorg 2026-05-28: el modulo real vive en `gemma4_agent.tools_pkg.skills_registry`.
Este archivo es un ejecutable minimo que reexpone `main()` para que las
Windows Scheduled Tasks y los atajos del usuario sigan funcionando con
el path historico.

Para `import` (no `python -m`), usar el path real:
    from gemma4_agent.tools_pkg.skills_registry import X

No re-aliasa sys.modules para no provocar RuntimeWarning en runpy.
"""
from __future__ import annotations


def main() -> int:
    from .tools_pkg.skills_registry import main as _main
    return _main()


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main() or 0)
