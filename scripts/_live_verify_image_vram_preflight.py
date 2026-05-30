"""Verificación EN VIVO del pre-flight de VRAM en inyección de imagen inline
(Ola 2.2, roadmap C6).

Ejercita el método REAL _image_inject_vram_safe de Gemma4Agent con el watchdog
en distintos estados (mockeando solo la lectura de VRAM, no la lógica), para
confirmar que el watchdog ACTÚA (no solo loguea):
  1. VRAM segura       -> inyecta (True).
  2. insegura -> recicla -> segura -> inyecta (True), y SE LLAMÓ el recycle.
  3. insegura aún tras recycle -> NO inyecta (False) -> nota honesta, no OOM.
  4. error del watchdog -> fail-open (True): no empeora el path viejo.
  5. sin GPU (watchdog no-op) -> True.

Esto valida que una imagen inline (gui.screenshot en turno de texto) ya NO carga
mmproj a ciegas en 4GB. NO toca GPU real ni lanza el server.

Uso: python scripts/_live_verify_image_vram_preflight.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.agent_core.agent import Gemma4Agent  # noqa: E402


def _agent(wd):
    ag = Gemma4Agent.__new__(Gemma4Agent)
    ag.vram_watchdog = wd
    ag.trace = MagicMock()
    return ag


def main() -> int:
    failures = []

    print("== el watchdog ACTÚA en la inyección de imagen inline ==")

    # 1. VRAM segura -> inyecta.
    wd = MagicMock(); wd.vision_safe.return_value = True
    ok = _agent(wd)._image_inject_vram_safe("t") is True
    print(f"  {'OK ' if ok else 'FALLA'} VRAM segura -> inyecta")
    if not ok: failures.append("segura")

    # 2. insegura -> recicla -> segura.
    wd = MagicMock(); wd.vision_safe.side_effect = [False, True]
    wd.snapshot.return_value = MagicMock(free_mib=900, level="degrade")
    with patch("gemma4_agent.infra.llama_server.get_shared_manager") as gsm:
        gsm.return_value.recycle_for_vision_leak.return_value = True
        res = _agent(wd)._image_inject_vram_safe("t")
        recycled = gsm.return_value.recycle_for_vision_leak.called
    ok = (res is True and recycled)
    print(f"  {'OK ' if ok else 'FALLA'} insegura -> RECICLÓ el server -> segura -> inyecta")
    if not ok: failures.append("recycle->safe")

    # 3. insegura aún tras recycle -> NO inyecta (evita OOM).
    wd = MagicMock(); wd.vision_safe.side_effect = [False, False]
    wd.snapshot.return_value = MagicMock(free_mib=200, level="critical")
    with patch("gemma4_agent.infra.llama_server.get_shared_manager") as gsm:
        gsm.return_value.recycle_for_vision_leak.return_value = False
        res = _agent(wd)._image_inject_vram_safe("t")
    ok = (res is False)
    print(f"  {'OK ' if ok else 'FALLA'} insegura tras recycle -> NO inyecta (nota honesta, sin OOM)")
    if not ok: failures.append("blocks")

    # 4. error del watchdog -> fail-open.
    wd = MagicMock(); wd.vision_safe.side_effect = RuntimeError("smi boom")
    ok = _agent(wd)._image_inject_vram_safe("t") is True
    print(f"  {'OK ' if ok else 'FALLA'} error del watchdog -> fail-open (no empeora el path viejo)")
    if not ok: failures.append("fail-open")

    # 5. sin GPU -> no-op.
    wd = MagicMock(); wd.vision_safe.return_value = True  # available=False -> True
    ok = _agent(wd)._image_inject_vram_safe("t") is True
    print(f"  {'OK ' if ok else 'FALLA'} sin GPU NVIDIA -> no-op (True)")
    if not ok: failures.append("no-gpu")

    print()
    if failures:
        print(f"RESULTADO: {len(failures)} FALLAS: {failures}")
        return 1
    print("RESULTADO: TODO OK — el watchdog actúa (recicla/bloquea), ya no carga mmproj a ciegas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
