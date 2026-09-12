"""Compila el cambio .NET por el arranque vigente y deja un recibo de build propio.

No inventa un procedimiento: llama a `main.compile_if_needed`, que es lo que hace `py main.py`, y
después arranca el producto una vez por su conductor con un turno trivial. Ese arranque es el que
sustituye el Core junto a `Baxy.exe` por el publicado —lo hace `scripts/run_baxy_conductor.ps1`—, así
que sin él el Core efectivo y el publicado no coinciden y ningún runner sellado aceptaría el candidato.

El recibo dice exactamente qué se ejecutó y con qué código de salida. No es una prueba de calidad: una
compilación correcta no demuestra conducta.

Uso:
    python scratchpad/c03-build-receipt.py <batch>
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = pathlib.Path.home() / "AppData/Local/BAXY"


def sha(path) -> str:
    with pathlib.Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    batch = argv[1]
    private = BASE / f"C03-{batch}-private"
    private.mkdir(parents=True, exist_ok=True)
    build_log = private / "build.log"
    warmup_log = private / "warmup.log"
    shutdown_log = private / "shutdown.log"
    for path in (build_log, warmup_log, shutdown_log):
        if path.exists():
            raise SystemExit(f"{path} already exists; root reviews instead of overwriting")

    sys.path.insert(0, str(ROOT))
    import main as entry

    os.chdir(ROOT)
    captured = io.StringIO()
    build_exit = 0
    try:
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            entry.compile_if_needed(force=False)
    except Exception as error:  # a failed build is a result, not a crash of this script
        build_exit = 1
        captured.write(f"\nBUILD FAILED: {type(error).__name__}: {error}\n")
    build_log.write_text(captured.getvalue(), encoding="utf-8", newline="\n")
    print(captured.getvalue()[-800:])
    if build_exit:
        return 1

    # Arranque real del producto por su conductor, con un turno trivial: es lo que
    # sustituye el Core efectivo por el publicado.
    # El Core exige que su directorio privado sea hijo directo de %LOCALAPPDATA%/BAXY: con una ruta
    # anidada se niega a arrancar con «could not validate its private data directory», que es lo que
    # convirtió el primer intento de este calentamiento en un falso «runtime_not_ready».
    warmup = BASE / f"C03-{batch}-warmup"
    profile = BASE / f"C03-{batch}-warmup-profile"
    turns = warmup / "turns.jsonl"
    warmup.mkdir(parents=True, exist_ok=True)
    turns.write_text(
        json.dumps({"cmd": "session.new"}, ensure_ascii=False) + "\n"
        + json.dumps({"cmd": "turn", "text": "hola"}, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    command = [sys.executable, "-B", "-X", "utf8", "main.py", "--conductor",
               "--profile", str(profile), "--capture", str(warmup / "capture"),
               "--turns-file", str(turns), "--timeout-ms", "120000"]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=900)
    warmup_log.write_text((completed.stdout or "") + (completed.stderr or ""),
                          encoding="utf-8", newline="\n")
    print(f"warmup exit {completed.returncode}")

    shutdown = subprocess.run([entry.dotnet_executable(), "build-server", "shutdown"],
                              cwd=ROOT, capture_output=True, text=True)
    shutdown_log.write_text((shutdown.stdout or "") + (shutdown.stderr or ""),
                            encoding="utf-8", newline="\n")

    app = entry.APP_EXE.resolve()
    published = entry.CORE_EXE.resolve()
    effective = (app.parent / "baxy-core.exe").resolve()
    receipt = {
        "schema": f"c03-{batch}-root-build-receipt-v1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "dotnet": entry.dotnet_executable(),
        "build_exit": build_exit,
        "warmup_exit": completed.returncode,
        "shutdown_exit": shutdown.returncode,
        "warmup_command": command,
        "warmup_purpose": "one real product start through its conductor so the effective Core beside "
                          "Baxy.exe becomes the published one; not a coverage run and not adjudicated",
        "source_fingerprint": entry.source_fingerprint(),
        "recorded_fingerprint": entry.recorded_fingerprint(),
        "fingerprint_matches": entry.source_fingerprint() == entry.recorded_fingerprint(),
        "app_exe": str(app),
        "published_core_exe": str(published),
        "effective_core_exe": str(effective),
        "effective_equals_published": sha(published) == sha(effective),
        "build_state_path": str(entry.BUILD_STATE),
        "tests_run": False,
        "validation_policy": "owner_directed_no_tests",
        "note": "Una compilacion correcta no demuestra calidad ni UI.",
    }
    target = private / "BUILD_RECEIPT.json"
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")
    print(json.dumps({k: receipt[k] for k in
                      ("build_exit", "warmup_exit", "shutdown_exit", "fingerprint_matches",
                       "effective_equals_published")}, indent=1))
    print(f"receipt {target} sha256 {sha(target)}")
    return 0 if receipt["effective_equals_published"] and receipt["fingerprint_matches"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
