"""R278: audit which published seals a CRLF checkout breaks, and which it does not.

Git for Windows ships ``core.autocrlf=true`` in its system config. Several BAXY
checks hash raw on-disk bytes, so a clone can hold files whose SHA-256 matches
no published constant while their LF form matches one exactly.

This program classifies every tracked text file into three buckets:

``restorable``
    Its LF SHA-256 is a published constant and its on-disk SHA-256 is not. The
    checkout broke a seal that was always correct.
``sealed_as_crlf``
    Its on-disk SHA-256 *is* a published constant. Normalising it would break a
    seal rather than repair one, so it must be pinned with ``-text``.
``unreferenced``
    Neither form appears in the tree; the file carries no published identity.

It starts no model, enables no provider and executes no effect, and it never
writes to the files it classifies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "baxy.line-ending-seal-damage.r278.v1"
SEARCH_DIRS = ("src", "tests", "experiments", "scripts", "artifacts", "documentacion")
CONSTANT_SUFFIXES = {".py", ".cs", ".json", ".jsonl", ".md"}
HEX = re.compile(r"[0-9a-fA-F]{64}")
RESULT_PATH = "artifacts/audit/line_ending_seal_damage_r278.json"


def _tracked(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files"], capture_output=True, check=True
    ).stdout.decode("utf-8", "replace")
    return sorted(line for line in out.splitlines() if line.strip())


def published_constants(root: Path) -> set[str]:
    """Every 64-hex constant recorded anywhere in the tree."""

    found: set[str] = set()
    for directory in SEARCH_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in CONSTANT_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            found.update(match.lower() for match in HEX.findall(text))
    return found


def classify(root: Path) -> dict[str, Any]:
    constants = published_constants(root)
    restorable: list[str] = []
    sealed_as_crlf: list[str] = []
    unreferenced = 0

    for relative in _tracked(root):
        path = root / relative
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\r\n" not in data or b"\x00" in data[:8192]:
            continue
        on_disk = hashlib.sha256(data).hexdigest()
        as_lf = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        if on_disk in constants:
            sealed_as_crlf.append(relative)
        elif as_lf in constants:
            restorable.append(relative)
        else:
            unreferenced += 1

    return {
        "schema": SCHEMA,
        "authority": "read_only_seal_classification_never_writes_the_files_it_reads",
        "publishedConstants": len(constants),
        "restorableCount": len(restorable),
        "sealedAsCrlfCount": len(sealed_as_crlf),
        "unreferencedCrlfCount": unreferenced,
        "restorable": restorable,
        "sealedAsCrlf": sealed_as_crlf,
        "rule": (
            "Restore a file only when its LF hash is a published constant and its "
            "on-disk hash is not. Never normalise a file whose on-disk hash is "
            "already the sealed value: that would break a seal instead of repairing "
            "one."
        ),
        "constraints": {
            "model_started": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "overall_goal_met": False,
        "section_7_met": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="R278 line ending seal audit")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()

    root = Path(arguments.repository_root).resolve()
    result = classify(root)
    rendered = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if arguments.write:
        destination = root / RESULT_PATH
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(rendered.encode("utf-8"))
        print(f"wrote {RESULT_PATH}")
    else:
        print(
            f"restorable={result['restorableCount']} "
            f"sealed_as_crlf={result['sealedAsCrlfCount']} "
            f"unreferenced={result['unreferencedCrlfCount']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
