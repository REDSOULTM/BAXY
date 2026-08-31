"""One-shot profile of evidence_assets queue. Writes a compact report."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "artifacts" / "goal095" / "extract" / "_evidence_profile.txt"


def main() -> int:
    batches = json.loads(
        (REPO / "artifacts/goal095/queue/batches.json").read_text(encoding="utf-8")
    )
    ea = [b for b in batches if b.get("kind") == "evidence_assets"]
    lines: list[str] = []
    lines.append(f"batches={len(ea)}")
    lines.append("BATCHES")
    for batch in ea:
        lines.append(
            f"{batch['batch_id']}\t{batch['file_count']}\t"
            f"{batch['estimated_tokens']}\t{batch.get('source_id')}\t"
            f"{batch.get('subsystem')}"
        )
    ext_src: dict[str, Counter[str]] = defaultdict(Counter)
    prefix: Counter[str] = Counter()
    huge: list[tuple[int, str, str, str]] = []
    wav_pref: Counter[str] = Counter()
    rust_pref: Counter[str] = Counter()
    none_pref: Counter[str] = Counter()
    for batch in ea:
        sid = str(batch.get("source_id"))
        for row in batch["files"]:
            path = row["path"].replace("\\", "/")
            suffix = Path(path).suffix.lower() or "(none)"
            ext_src[sid][suffix] += 1
            parts = path.split("/")
            pref = "/".join(parts[:3]) if len(parts) >= 3 else path
            prefix[pref] += 1
            size = int(row.get("size") or 0)
            if size >= 50_000_000:
                huge.append((size, batch["batch_id"], sid, path))
            if suffix == ".wav":
                wav_pref[pref] += 1
            if suffix in {".rlib", ".rmeta", ".d", ".rlib"}:
                rust_pref[pref] += 1
            if suffix == "(none)":
                none_pref[pref] += 1
    lines.append("PREFIX top50")
    for key, count in prefix.most_common(50):
        lines.append(f"{count}\t{key}")
    lines.append("WAV prefixes")
    for key, count in wav_pref.most_common(20):
        lines.append(f"{count}\t{key}")
    lines.append("RUST prefixes")
    for key, count in rust_pref.most_common(20):
        lines.append(f"{count}\t{key}")
    lines.append("NONE-SUFFIX prefixes")
    for key, count in none_pref.most_common(20):
        lines.append(f"{count}\t{key}")
    lines.append(f"HUGE>=50MB {len(huge)}")
    for size, batch_id, sid, path in sorted(huge, reverse=True)[:40]:
        lines.append(f"{round(size / 1e6, 1)}\t{batch_id}\t{sid}\t{path[:160]}")
    lines.append("EXT per source")
    for sid, counter in ext_src.items():
        lines.append(f"{sid}\t{counter.most_common(15)}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(str(OUT), len(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
