"""Crea 11 shims fisicos en gemma4_agent/ para los modulos runnable
(con `if __name__ == '__main__'`).

Estos NO son shims cosmeticos: son ejecutables que el usuario invoca con
`python -m gemma4_agent.<name>` y que Windows Scheduled Tasks ya tienen
registrados.

El shim DELEGA al subpkg real bajo `__main__`. No re-aliasa sys.modules
para evitar el RuntimeWarning de runpy.
"""
from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "gemma4_agent"

RUNNABLES = {
    "launcher": "infra",
    "server": "infra",
    "voice_runner": "infra",
    "watcher_runner": "infra",
    "task_runner": "infra",
    "routine_runner": "infra",
    "microagents": "memory_pkg",
    "mcp_server": "tools_pkg",
    "skills_registry": "tools_pkg",
    "chat": "support",
    "eval_smoke": "support",
    "import_triggercmd": "support",
}

TEMPLATE = '''"""Runnable wrapper: `python -m gemma4_agent.{stem}` -> `gemma4_agent.{subpkg}.{stem}`.

Reorg 2026-05-28: el modulo real vive en `gemma4_agent.{subpkg}.{stem}`.
Este archivo es un ejecutable minimo que reexpone `main()` para que las
Windows Scheduled Tasks y los atajos del usuario sigan funcionando con
el path historico.

Para `import` (no `python -m`), usar el path real:
    from gemma4_agent.{subpkg}.{stem} import X

No re-aliasa sys.modules para no provocar RuntimeWarning en runpy.
"""
from __future__ import annotations


def main() -> int:
    from .{subpkg}.{stem} import main as _main
    return _main()


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main() or 0)
'''


def has_main_func(subpkg: str, stem: str) -> bool:
    """True si el modulo real tiene `def main()`. Si no, el wrapper usa
    runpy via -m directamente sobre el modulo real."""
    target = PKG / subpkg / f"{stem}.py"
    if not target.exists():
        return False
    src = target.read_text(encoding="utf-8", errors="replace")
    return "def main(" in src


# Template fallback: el modulo real NO tiene `def main()` (corre directo
# en __main__). Re-exportamos via runpy.
TEMPLATE_NO_MAIN = '''"""Runnable wrapper: `python -m gemma4_agent.{stem}` -> `gemma4_agent.{subpkg}.{stem}`.

Reorg 2026-05-28: delega via runpy porque el modulo real ejecuta directo
en `if __name__ == '__main__'` sin funcion `main()`. Las Windows
Scheduled Tasks y atajos historicos siguen funcionando con este path.

Para `import` (no `python -m`), usar el path real:
    from gemma4_agent.{subpkg}.{stem} import X
"""
from __future__ import annotations


if __name__ == "__main__":
    import runpy
    runpy.run_module("gemma4_agent.{subpkg}.{stem}", run_name="__main__")
'''


def main() -> int:
    created = 0
    for stem, subpkg in RUNNABLES.items():
        shim = PKG / f"{stem}.py"
        if shim.exists():
            print(f"SKIP: {shim.name} already exists")
            continue
        if has_main_func(subpkg, stem):
            shim.write_text(
                TEMPLATE.format(stem=stem, subpkg=subpkg),
                encoding="utf-8",
            )
        else:
            shim.write_text(
                TEMPLATE_NO_MAIN.format(stem=stem, subpkg=subpkg),
                encoding="utf-8",
            )
        print(f"Created {shim.name} -> {subpkg}.{stem}")
        created += 1
    print(f"Created {created} runnable shims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
