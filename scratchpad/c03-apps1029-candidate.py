"""Escribe el manifiesto de candidato de raíz para APPS1029: pines reales de esta máquina.

No se copia ningún pin de la otra máquina ni del candidato anterior: fuentes, binarios y runtime se
vuelven a hashear aquí. La compilación no se repite porque no hace falta y se dice por qué: la huella
de fuente de `main.py` coincide con la grabada en el estado de build, y el inventario de binarios
resulta byte a byte idéntico al de la preparación de SYSTEM1028 en esta misma máquina, que es la que
produjo estos binarios. Ese recibo se referencia tal cual, sin fingir una compilación nueva.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = pathlib.Path.home() / "AppData/Local/BAXY"
PANEL = BASE / "C03-apps1029-proposal"
PRIVATE = BASE / "C03-apps1029-private"
PREVIOUS = BASE / "C03-system1028-private/CANDIDATE_AUTHORIZED.json"
MANIFEST = pathlib.Path.home() / "AppData/Local/BAXYRuntime/mind-runtime-v1.json"
REGISTRY = BASE / "C03-survey-requirements336-private/requirements.jsonl"

OWNER_INSTRUCTION = (
    "El dueno pidio expresamente acelerar C03 sin pruebas automatizadas, ni Fast ni Full, sin perder "
    "conducta veraz del producto. Las suites quedan omitidas, no verdes ni aprobadas. Se exige "
    "ejecucion real sellada en el producto para cualquier cobertura."
)


def sha(path) -> str:
    with pathlib.Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, encoding="utf-8").strip()


def current_sources() -> dict[str, str]:
    names = git("ls-files", "--cached", "--others", "--exclude-standard", "--",
                "src", "scripts", "main.py").splitlines()
    return {name: sha(ROOT / name) for name in sorted(set(names)) if (ROOT / name).is_file()}


def main() -> int:
    sys.path.insert(0, str(ROOT))
    import main as entry

    previous = json.loads(PREVIOUS.read_text(encoding="utf-8"))
    head = git("rev-parse", "HEAD")
    app = entry.APP_EXE.resolve()
    published = entry.CORE_EXE.resolve()
    effective = (app.parent / "baxy-core.exe").resolve()
    for path in (app, published, effective):
        if not path.is_file():
            raise SystemExit(f"missing product binary: {path}")
    if sha(published) != sha(effective):
        raise SystemExit("effective Core differs from published Core; start the product once")
    fingerprint = entry.source_fingerprint()
    if fingerprint != entry.recorded_fingerprint():
        raise SystemExit("source fingerprint differs from the recorded build; a build is required")

    inventory = {str(path.resolve()): sha(path)
                 for folder in {app.parent, published.parent}
                 for path in sorted(folder.iterdir())
                 if path.is_file() and path.suffix.lower() in {".exe", ".dll", ".json"}}
    if inventory != previous["binary_pins"]:
        raise SystemExit("binary inventory differs from the SYSTEM1028 preparation; rebuild and "
                         "write a fresh receipt instead of reusing that one")

    config = json.loads(MANIFEST.read_text(encoding="utf-8"))
    runtime_paths = {MANIFEST.resolve(), pathlib.Path(config["gguf"]).resolve(),
                     pathlib.Path(config["llama_server"]).resolve(),
                     pathlib.Path(config["python"]).resolve(),
                     pathlib.Path(sys._base_executable).resolve()}
    runtime_pins = {str(path): sha(path) for path in runtime_paths}

    sources = current_sources()
    state = pathlib.Path(os.environ["LOCALAPPDATA"]) / "BAXY/development/source-build-v1.json"
    manifest = {
        "schema": "c03-apps1029-root-manifest-v1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "head": head,
        "panel_seal_sha256": sha(PANEL / "SEAL.json"),
        "runner_sha256": sha(PANEL / "runner.py"),
        "registry_current_sha256": sha(REGISTRY),
        "source_pins": sources,
        "source_pin_count": len(sources),
        "binary_pins": inventory,
        "binary_pin_count": len(inventory),
        "runtime_pins": runtime_pins,
        "runtime_manifest_sha256": sha(MANIFEST),
        "model_sha256": sha(config["gguf"]),
        "backend_sha256": sha(config["llama_server"]),
        "app_exe": str(app),
        "published_core_exe": str(published),
        "effective_core_exe": str(effective),
        "build_state_path": str(state),
        "build_state_sha256": sha(state),
        "build_fingerprint": fingerprint,
        "preparation": previous["preparation"],
        "preparation_reuse": {
            "receipt_from": "SYSTEM1028 root preparation on this same machine",
            "no_build_for_this_batch": True,
            "why": "main.py source fingerprint equals the recorded build state, and the complete "
                   "binary inventory re-hashed here is byte-identical to that preparation's, so these "
                   "binaries are that build's output. No compilation was performed for APPS1029 and "
                   "none is claimed.",
            "verified_here": ["source_fingerprint == recorded_fingerprint",
                              "binary inventory identical to SYSTEM1028 pins",
                              "effective Core == published Core",
                              "runtime pins re-hashed"],
        },
        "tests_run": False,
        "validation_policy": "owner_directed_no_tests",
        "owner_instruction": OWNER_INSTRUCTION,
        "execution_authorized": True,
        "machine": {"host": os.environ.get("COMPUTERNAME"),
                    "note": "REDPC, maquina original. Pines medidos aqui; ninguno copiado de la replica."},
        "declared_environment_note": "Steam, Chrome, Discord, Settings y un Notepad ya estaban en "
                                     "ejecucion antes del sello, fuera del arbol medido; Calculator, "
                                     "Paint y Windows Terminal no. Medido en el PLAN, verificado por "
                                     "el runner en preflight.",
    }
    PRIVATE.mkdir(parents=True, exist_ok=True)
    target = PRIVATE / "CANDIDATE_AUTHORIZED.json"
    if target.exists():
        raise SystemExit(f"{target} already exists; root reviews instead of overwriting")
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")
    print(json.dumps({"manifest": str(target), "sha256": sha(target), "head": head,
                      "source_pins": len(sources), "binary_pins": len(inventory),
                      "runtime_pins": len(runtime_pins)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
