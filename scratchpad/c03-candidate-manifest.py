"""Escribe el manifiesto de candidato de raíz para una tanda cualquiera: pines reales de esta máquina.

Generalización del manifiesto de APPS1029, que era el mismo procedimiento con el nombre de la tanda
dentro. No copia ningún pin de otra máquina: fuentes, binarios y runtime se vuelven a hashear aquí.

La compilación no se repite mientras la huella de fuente de `main.py` coincida con la grabada y el
inventario de binarios sea byte a byte el de la preparación que los produjo; el recibo de aquella
preparación se referencia tal cual y se dice que se reutiliza. Si algo de eso cambia, el script falla
y pide compilar en vez de fingirlo.

Uso:
    python scratchpad/c03-candidate-manifest.py <batch>      # p. ej. repair1030
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
# Procedencia de build heredable: el candidato más reciente que compiló de verdad. Se comprueba que
# sus binarios sigan siendo byte a byte los de ahora; si no, esta tanda tiene que compilar.
BUILD_PROVENANCE = BASE / "C03-repair1032-private/CANDIDATE_AUTHORIZED.json"
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


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    batch = argv[1]
    panel = BASE / f"C03-{batch}-proposal"
    private = BASE / f"C03-{batch}-private"
    sys.path.insert(0, str(ROOT))
    import main as entry

    provenance = json.loads(BUILD_PROVENANCE.read_text(encoding="utf-8"))
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

    # Si la tanda trae recibo de build propio, esa es su procedencia y los binarios son suyos.
    # Si no, se reutiliza la preparación que los produjo y se exige que sigan siendo byte a byte
    # los mismos: sin eso habría que compilar, y no se finge una compilación que no ocurrió.
    own_receipt = private / "BUILD_RECEIPT.json"
    if own_receipt.is_file():
        receipt = json.loads(own_receipt.read_text(encoding="utf-8"))
        for key, expected in (("build_exit", 0), ("shutdown_exit", 0), ("warmup_exit", 0)):
            if receipt.get(key) != expected:
                raise SystemExit(f"own build receipt reports {key}={receipt.get(key)}")
        if not receipt.get("effective_equals_published") or not receipt.get("fingerprint_matches"):
            raise SystemExit("own build receipt does not attest effective==published and fingerprint")
        logs = {str((private / name).resolve()): sha(private / name)
                for name in ("build.log", "warmup.log", "shutdown.log")}
        preparation = {"build_exit": receipt["build_exit"], "shutdown_exit": receipt["shutdown_exit"],
                       "warmup_exit": receipt["warmup_exit"],
                       "receipt_path": str(own_receipt.resolve()),
                       "receipt_sha256": sha(own_receipt), "logs": logs}
        reuse = {"receipt_from": f"C03-{batch} own build on this machine", "no_build_for_this_batch": False,
                 "why": "The .NET change required a real compilation, so this batch carries its own "
                        "receipt: build, one product warmup that substitutes the effective Core, and "
                        "the compiler server shutdown.",
                 "verified_here": ["build_exit 0", "warmup_exit 0", "shutdown_exit 0",
                                   "source_fingerprint == recorded_fingerprint",
                                   "effective Core == published Core", "runtime pins re-hashed"]}
    else:
        if inventory != provenance["binary_pins"]:
            raise SystemExit("binary inventory differs from the recorded preparation; rebuild and "
                             "write a fresh receipt instead of reusing that one")
        preparation = provenance["preparation"]
        reuse = {
            "receipt_from": "the most recent root build on this machine, reused by identity",
            "no_build_for_this_batch": True,
            "why": "Only Python changed since that build; main.py's .NET source fingerprint equals the "
                   "recorded build state and the complete binary inventory re-hashed here is "
                   "byte-identical to that build's output. No compilation was performed for this batch "
                   "and none is claimed.",
            "verified_here": ["source_fingerprint == recorded_fingerprint",
                              "binary inventory identical to the recorded preparation",
                              "effective Core == published Core", "runtime pins re-hashed"],
        }

    config = json.loads(MANIFEST.read_text(encoding="utf-8"))
    runtime_paths = {MANIFEST.resolve(), pathlib.Path(config["gguf"]).resolve(),
                     pathlib.Path(config["llama_server"]).resolve(),
                     pathlib.Path(config["python"]).resolve(),
                     pathlib.Path(sys._base_executable).resolve()}
    sources = current_sources()
    state = pathlib.Path(os.environ["LOCALAPPDATA"]) / "BAXY/development/source-build-v1.json"
    manifest = {
        "schema": f"c03-{batch}-root-manifest-v1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "head": head,
        "panel_seal_sha256": sha(panel / "SEAL.json"),
        "runner_sha256": sha(panel / "runner.py"),
        "registry_current_sha256": sha(REGISTRY),
        "source_pins": sources,
        "source_pin_count": len(sources),
        "binary_pins": inventory,
        "binary_pin_count": len(inventory),
        "runtime_pins": {str(path): sha(path) for path in runtime_paths},
        "runtime_manifest_sha256": sha(MANIFEST),
        "model_sha256": sha(config["gguf"]),
        "backend_sha256": sha(config["llama_server"]),
        "app_exe": str(app),
        "published_core_exe": str(published),
        "effective_core_exe": str(effective),
        "build_state_path": str(state),
        "build_state_sha256": sha(state),
        "build_fingerprint": fingerprint,
        "preparation": preparation,
        "preparation_reuse": reuse,
        "tests_run": False,
        "validation_policy": "owner_directed_no_tests",
        "owner_instruction": OWNER_INSTRUCTION,
        "execution_authorized": True,
        "machine": {"host": os.environ.get("COMPUTERNAME"),
                    "note": "REDPC, maquina original. Pines medidos aqui."},
    }
    private.mkdir(parents=True, exist_ok=True)
    target = private / "CANDIDATE_AUTHORIZED.json"
    if target.exists():
        raise SystemExit(f"{target} already exists; root reviews instead of overwriting")
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")
    print(json.dumps({"manifest": str(target), "sha256": sha(target), "head": head,
                      "source_pins": len(sources), "binary_pins": len(inventory)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
