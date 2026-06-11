"""Standalone hands-free desktop controller entrypoint.

This module deliberately keeps the camera-control loop independent from the
main assistant runtime. It reuses the deterministic window-control runner, but
enables its strict standalone defaults.
"""
from __future__ import annotations

import sys

from .window_control import main as _window_control_main


def main(argv: list[str] | None = None) -> int:
    # El clasificador RF personalizado (entrenado con los videos del operador)
    # se activa SOLO en los entrypoints de runtime: el default del módulo es la
    # heurística universal (medida contra el fixture diverso). Override
    # explícito con GEMMA4_GESTURE_ML=0.
    import os
    os.environ.setdefault("GEMMA4_GESTURE_ML", "1")
    args = list(sys.argv[1:] if argv is None else argv)
    if "--standalone" not in args:
        args.insert(0, "--standalone")
    return _window_control_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
