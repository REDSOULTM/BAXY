"""The GPU llama-server computes on, from the machine's PCI vendor ids (encargo 8, 2026-11-02): CUDA with an NVIDIA GPU,
Vulkan with an AMD or Intel one, the CPU with neither. The installation registers the llama-server folder of that backend
(scripts/register_mind_runtime.ps1 runs ``python -m baxy_mind.gpu``); the mind reads the backend from the folder it was
given (llm_server.declared_backend), for that backend's settings.

A vendor id, not a model's name: 10DE is NVIDIA, 1002 AMD, 8086 Intel (PCI-SIG). NVIDIA wins beside an integrated AMD or
Intel GPU (a laptop's): llama.cpp's CUDA build never uses the other, and its Vulkan build leaves an integrated GPU out
whenever there is a discrete one (src/llama.cpp, b11609)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BACKENDS = {"10de": "cuda", "1002": "vulkan", "8086": "vulkan"}


def _vendor(device_id: str) -> str | None:
    """The PCI vendor id of a device id as Windows writes it («PCI\\VEN_10DE&DEV_…», any case); None for others."""
    found = re.match(r"pci\\ven_([0-9a-f]{4})", device_id.strip().lower())
    return found.group(1) if found else None


def backend(device_ids: list[str]) -> str:
    """«cuda», «vulkan» or «cpu» for the machine's display devices (their PNP device ids)."""
    found = {BACKENDS.get(_vendor(device) or "") for device in device_ids}
    return "cuda" if "cuda" in found else "vulkan" if "vulkan" in found else "cpu"


def choose(device_ids: list[str], servers: list[str], builds: Path | None = None) -> dict:
    """The machine's backend, the first of ``servers`` (llama-server.exe paths) whose folder is a declared build with that
    backend (None when none is), and what each one is: its backend, or why it is not declared."""
    from . import llm_server

    declaration = llm_server.BUILDS if builds is None else builds
    wanted = backend(device_ids)
    told: dict[str, str] = {}
    chosen = None
    for server in servers:
        try:
            told[server] = llm_server.declared_backend(server, llm_server.declared_build(server, declaration),
                                                       declaration)
        except (RuntimeError, OSError, ValueError) as error:
            told[server] = str(error)
            continue
        if chosen is None and told[server] == wanted:
            chosen = server
    return {"backend": wanted, "server": chosen, "servers": told}


def main(argv: list[str] | None = None) -> int:
    """``python -m baxy_mind.gpu --pci <device id> … <llama-server.exe> …``: the choice as one JSON line; exit 1 when no
    server is of the machine's backend."""
    parser = argparse.ArgumentParser(prog="python -m baxy_mind.gpu")
    parser.add_argument("--pci", action="append", default=[], help="a display device's PNP device id")
    parser.add_argument("servers", nargs="*")
    arguments = parser.parse_args(argv)
    chosen = choose(arguments.pci, arguments.servers)
    sys.stdout.write(json.dumps(chosen, ensure_ascii=False) + "\n")
    return 0 if chosen["server"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
