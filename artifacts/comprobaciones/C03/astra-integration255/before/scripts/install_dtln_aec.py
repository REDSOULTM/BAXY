"""Explicit installation of the pinned DTLN512 models and their MIT license."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind.assets import resolve_asset  # noqa: E402
from baxy_mind.dtln_aec import LICENSE_SHA256, MODEL_HASHES, SOURCE_URL  # noqa: E402


def install(destination: Path, source_directory: Path | None = None) -> dict:
    destination = destination.resolve()
    expected = {**MODEL_HASHES, "LICENSE": LICENSE_SHA256}

    def verify(directory: Path) -> None:
        for name, digest in expected.items():
            with (directory / name).open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != digest:
                raise ValueError(f"dtln_asset_hash_mismatch:{name}")

    if destination.exists():
        verify(destination)
        return {"directory": str(destination), "reused": True, "sha256": expected}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".dtln-install-", dir=destination.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        for name in expected:
            target = staging / name
            if source_directory is not None:
                shutil.copyfile(source_directory / name, target)
            else:
                relative = f"pretrained_models/{name}" if name in MODEL_HASHES else name
                with urlopen(f"{SOURCE_URL}/{relative}", timeout=120) as response, target.open("xb") as stream:
                    shutil.copyfileobj(response, stream)
        verify(staging)
        # Windows rename refuses an existing destination, including a race.
        staging.rename(destination)
    return {"directory": str(destination), "reused": False, "sha256": expected}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-directory", type=Path, help="Reuse an existing bundle without downloading.")
    args = parser.parse_args()
    destination = args.destination
    if destination is None:
        resolution = resolve_asset("echo_canceller")
        if not resolution.candidates:
            parser.error("echo_canceller_destination_missing")
        destination = resolution.path or resolution.candidates[0]
    print(json.dumps(install(destination, args.source_directory), ensure_ascii=False))


if __name__ == "__main__":
    main()
