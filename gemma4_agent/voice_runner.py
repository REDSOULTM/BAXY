"""Runnable wrapper: `python -m gemma4_agent.voice_runner` -> `gemma4_agent.infra.voice_runner`.

Reorg 2026-05-28: delega via runpy porque el modulo real ejecuta directo
en `if __name__ == '__main__'` sin funcion `main()`. Las Windows
Scheduled Tasks y atajos historicos siguen funcionando con este path.

Para `import` (no `python -m`), usar el path real:
    from gemma4_agent.infra.voice_runner import X
"""
from __future__ import annotations


if __name__ == "__main__":
    import runpy
    runpy.run_module("gemma4_agent.infra.voice_runner", run_name="__main__")
