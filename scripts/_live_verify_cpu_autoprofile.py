"""Verificación EN VIVO del auto-perfil CPU sin GPU (Ola 2.1, roadmap).

Ejercita el flujo REAL de selección de perfil (profiles.recommend_profile +
get_active_profile) simulando una máquina SIN NVIDIA vía el override
GEMMA4_LLAMA_GPU_VENDOR=cpu (no hace falta desconectar la GPU del dev).

Verifica:
  1. Sin GPU NVIDIA -> recommend_profile devuelve 'cpu' (no vram4 que no arrancaría).
  2. Con GPU NVIDIA (override cuda) -> vram4 (no rompemos a usuarios NVIDIA).
  3. El guard del default forzado: GEMMA4_DEFAULT_PROFILE=vram4 + sin GPU -> cae a cpu
     igual (el binario CUDA no arrancaría; el código garantiza su precondición).
  4. Gate OFF (GEMMA4_NO_GPU_AUTOCPU=0) -> vuelve al comportamiento viejo (vram4).

NO toca hardware ni lanza el server: sólo el código puro de selección de perfil.

Uso: python scripts/_live_verify_cpu_autoprofile.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.infra import profiles  # noqa: E402


def _clear_env():
    for k in ("GEMMA4_LLAMA_GPU_VENDOR", "GEMMA4_NO_GPU_AUTOCPU",
              "GEMMA4_DEFAULT_PROFILE"):
        os.environ.pop(k, None)


def main() -> int:
    failures = []

    print("== 1. recommend_profile según hardware ==")
    _clear_env()
    os.environ["GEMMA4_LLAMA_GPU_VENDOR"] = "cpu"   # simular sin-NVIDIA
    r = profiles.recommend_profile(None)
    ok = (r == "cpu")
    print(f"  {'OK ' if ok else 'FALLA'} sin NVIDIA -> {r!r} (esperado 'cpu')")
    if not ok:
        failures.append(f"sin GPU dio {r}")

    os.environ["GEMMA4_LLAMA_GPU_VENDOR"] = "cuda"  # simular NVIDIA presente
    r = profiles.recommend_profile(None)
    ok = (r == "vram4")
    print(f"  {'OK ' if ok else 'FALLA'} con NVIDIA -> {r!r} (esperado 'vram4')")
    if not ok:
        failures.append(f"con GPU dio {r}")

    print()
    print("== 2. guard del default forzado (vram4 sin GPU -> cpu) ==")
    # active_profile.txt en un tmp aislado, asegurar que NO existe -> primer arranque.
    with tempfile.TemporaryDirectory() as td:
        _saved_path = profiles.ACTIVE_PROFILE_PATH
        try:
            profiles.ACTIVE_PROFILE_PATH = Path(td) / "active_profile.txt"
            _clear_env()
            os.environ["GEMMA4_DEFAULT_PROFILE"] = "vram4"
            os.environ["GEMMA4_LLAMA_GPU_VENDOR"] = "cpu"  # sin NVIDIA
            prof = profiles.get_active_profile()
            ok = (prof.name == "cpu")
            print(f"  {'OK ' if ok else 'FALLA'} default=vram4 + sin GPU -> perfil {prof.name!r} (esperado 'cpu')")
            if not ok:
                failures.append(f"default forzado sin GPU dio {prof.name}")

            # Mismo default PERO con NVIDIA -> respeta vram4.
            if profiles.ACTIVE_PROFILE_PATH.exists():
                profiles.ACTIVE_PROFILE_PATH.unlink()
            os.environ["GEMMA4_LLAMA_GPU_VENDOR"] = "cuda"
            prof2 = profiles.get_active_profile()
            ok2 = (prof2.name == "vram4")
            print(f"  {'OK ' if ok2 else 'FALLA'} default=vram4 + con GPU -> perfil {prof2.name!r} (esperado 'vram4')")
            if not ok2:
                failures.append(f"default forzado con GPU dio {prof2.name}")
        finally:
            profiles.ACTIVE_PROFILE_PATH = _saved_path

    print()
    print("== 3. gate OFF preserva comportamiento viejo ==")
    _clear_env()
    os.environ["GEMMA4_NO_GPU_AUTOCPU"] = "0"
    os.environ["GEMMA4_LLAMA_GPU_VENDOR"] = "cpu"  # sin GPU pero gate apagado
    r = profiles.recommend_profile(None)
    ok = (r == "vram4")
    print(f"  {'OK ' if ok else 'FALLA'} gate OFF + sin GPU -> {r!r} (esperado 'vram4', diagnóstico)")
    if not ok:
        failures.append(f"gate off dio {r}")

    _clear_env()
    print()
    if failures:
        print(f"RESULTADO: {len(failures)} FALLAS:")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULTADO: TODO OK — el agente cae a 'cpu' sin NVIDIA y mantiene vram4 con NVIDIA.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
