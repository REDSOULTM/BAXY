"""Inspect a docs batch without dumping bodies to chat.

Read-only on the frozen sibling snapshot. Writes extract under
artifacts/goal095/extract/. Text only: headings, lead, measurements.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.goal095_docs_ledger import batch_from_batches, load_json, queue_paths
from scripts.goal095_inspect_code_batch import (
    git_blob_sha256,
    sha256_file,
    source_root_for,
)

OUT = REPO / "artifacts" / "goal095" / "extract"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
MEASURE_RE = re.compile(
    r"("
    r"\d+\s*/\s*\d+"
    r"|\d+(?:[.,]\d+)?\s*%"
    r"|recall\s*[:=]?\s*\d"
    r"|fp\s*/\s*hr"
    r"|\b(?:VRAM|vram)\b"
    r"|\b\d+(?:\.\d+)?\s*(?:GB|GiB|MB|ms|s)\b"
    r"|\b(?:pass(?:ed)?|fail(?:ed)?|FAIL|PASS|GREEN|RED)\b"
    r"|\bQ[0-9]_"
    r"|\bgguf\b"
    r"|\bepoch"
    r"|\btool-acc"
    r")",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"20\d\d-\d{2}-\d{2}")
MODEL_RE = re.compile(
    r"\b(gemma[-\s]?4|qwen3|functiongemma|whisper|llama\.cpp|e4b|"
    r"piper|voxcpm|livekit|e5-small|nemotron)\b",
    re.IGNORECASE,
)
HW_RE = re.compile(
    r"\b(RTX\s*\d{3,4}\s*(?:Ti)?(?:\s*\d+\s*GB)?|4060|VRAM|16\s*GB|6\s*GB)\b",
    re.IGNORECASE,
)
MECH_RE = re.compile(
    r"\b(porque|because|root cause|mecanismo|caused by|due to|"
    r"padding|spinning|busy-wait|verifier|hardcode|fake success)\b",
    re.IGNORECASE,
)


def _decode(raw: bytes) -> str | None:
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16-le")
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16-be")
    if b"\x00" in raw[:4096]:
        return None
    for encoding in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_text(raw: bytes) -> dict[str, Any]:
    text = _decode(raw)
    if text is None:
        return {
            "binary": True,
            "lines": 0,
            "headings": [],
            "lead": "",
            "measures": [],
            "dates": [],
            "models": [],
            "hardware": [],
            "mechanisms": [],
        }
    lines = text.splitlines()
    headings: list[dict[str, Any]] = []
    measures: list[dict[str, Any]] = []
    mechanisms: list[dict[str, Any]] = []
    dates: list[str] = []
    models: list[str] = []
    hardware: list[str] = []
    lead_parts: list[str] = []
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        match = HEADING_RE.match(stripped)
        if match and len(headings) < 24:
            headings.append(
                {"line": index, "level": len(match.group(1)), "text": match.group(2)[:180]}
            )
            continue
        if (
            not lead_parts
            and not stripped.startswith(">")
            and not stripped.startswith("```")
            and not stripped.startswith("---")
            and not stripped.startswith("|")
        ):
            lead_parts.append(stripped[:400])
            if sum(len(part) for part in lead_parts) >= 420:
                lead_parts = lead_parts[:3]
        if MEASURE_RE.search(stripped) and len(measures) < 12 and len(stripped) < 280:
            measures.append({"line": index, "text": stripped[:240]})
        if MECH_RE.search(stripped) and len(mechanisms) < 6 and len(stripped) < 280:
            mechanisms.append({"line": index, "text": stripped[:240]})
        for found in DATE_RE.findall(stripped):
            if found not in dates and len(dates) < 8:
                dates.append(found)
        for found in MODEL_RE.findall(stripped):
            key = found.lower()
            if key not in models and len(models) < 8:
                models.append(key)
        for found in HW_RE.findall(stripped):
            key = found.strip()
            if key not in hardware and len(hardware) < 6:
                hardware.append(key)
    ranges = ["1-" + str(max(1, len(lines)))]
    if headings:
        ranges.append(f"h:{headings[0]['line']}")
    if measures:
        ranges.append(f"m:{measures[0]['line']}")
    return {
        "binary": False,
        "lines": len(lines),
        "headings": headings,
        "lead": " ".join(lead_parts)[:500],
        "measures": measures,
        "dates": dates,
        "models": models,
        "hardware": hardware,
        "mechanisms": mechanisms,
        "ranges": ranges,
    }


def inspect_batch(repo: Path, batch_id: str) -> dict[str, Any]:
    batches_path, _ledger, _summary = queue_paths(repo)
    batches = load_json(batches_path)
    batch = batch_from_batches(batches, batch_id)
    source = source_root_for(batch.get("source_id") or "carter")
    if not source.is_dir():
        raise SystemExit(f"FALLO_DE_AMBIENTE missing source root {source}")
    rows: list[dict[str, Any]] = []
    hash_ok = hash_miss = hash_drift = 0
    for item in batch["files"]:
        rel = item["path"]
        disk = source / rel
        rec: dict[str, Any] = {
            "path": rel,
            "queued_sha256": item["sha256"],
            "size_queued": item["size"],
            "exists": disk.is_file(),
        }
        raw: bytes | None = None
        if disk.is_file():
            rec["disk_sha256"] = sha256_file(disk)
            rec["disk_size"] = disk.stat().st_size
            rec["hash_match"] = rec["disk_sha256"] == item["sha256"]
            if rec["hash_match"]:
                hash_ok += 1
                raw = disk.read_bytes()
            else:
                hash_drift += 1
        else:
            rec["hash_match"] = False
        head_sha, head_err = git_blob_sha256(source, rel)
        rec["head_sha256"] = head_sha
        if head_err:
            rec["head_err"] = head_err[:120]
        if raw is None and head_sha == item["sha256"]:
            shown = subprocess.run(
                ["git", "show", f"HEAD:{rel.replace(chr(92), '/')}"],
                cwd=source,
                capture_output=True,
                check=False,
            )
            if shown.returncode == 0:
                raw = shown.stdout
                rec["from_git_blob"] = True
                if rec.get("exists"):
                    hash_ok += 1
                    hash_drift = max(0, hash_drift - 1)
                else:
                    hash_ok += 1
        if raw is None:
            if not rec.get("exists"):
                hash_miss += 1
            rec["extract"] = {"binary": True, "missing": True}
        else:
            rec["extract"] = extract_text(raw)
        rows.append(rec)
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "batch_id": batch_id,
        "kind": "docs",
        "source_id": batch.get("source_id"),
        "subsystem": batch.get("subsystem"),
        "file_count": len(rows),
        "hash_ok": hash_ok,
        "hash_drift": hash_drift,
        "hash_missing": hash_miss,
        "files": rows,
    }
    out = OUT / f"{batch_id}.inspect.json"
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    index_lines = [
        f"batch_id={batch_id}",
        "kind=docs",
        f"file_count={len(rows)}",
        f"hash_ok={hash_ok} drift={hash_drift} miss={hash_miss}",
        f"subsystem={batch.get('subsystem')}",
        "---FILES---",
    ]
    for rec in rows:
        flag = "OK" if rec.get("hash_match") or rec.get("from_git_blob") else "DRIFT"
        extract = rec.get("extract") or {}
        heading = ""
        if extract.get("headings"):
            heading = extract["headings"][0]["text"][:80]
        index_lines.append(f"{flag} {rec['path']}\t{heading}")
    index_path = OUT / f"{batch_id}.index.txt"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8", newline="\n")
    return {
        "wrote": str(out),
        "index": str(index_path),
        "hash_ok": hash_ok,
        "hash_drift": hash_drift,
        "hash_missing": hash_miss,
        "file_count": len(rows),
        "subsystem": batch.get("subsystem"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--batch-id", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = inspect_batch(args.repo.resolve(), args.batch_id)
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
