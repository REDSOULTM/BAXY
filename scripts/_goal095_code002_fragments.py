"""Write a condensed fragments file from the batch 002 inspect JSON."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INSPECT = (
    REPO
    / "artifacts"
    / "goal095"
    / "extract"
    / "code_tests-002-carter-carter_legacy_Carter_v2.inspect.json"
)
FRAG = INSPECT.with_name(
    "code_tests-002-carter-carter_legacy_Carter_v2.fragments.txt"
)


def clip(value: object, limit: int = 500) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def main() -> int:
    data = json.loads(INSPECT.read_text(encoding="utf-8"))
    head_yes = head_no = head_err = 0
    out: list[str] = []
    for row in data["files"]:
        if row.get("head_matches_queue") is True:
            head_yes += 1
        elif row.get("head_sha256"):
            head_no += 1
            out.append(f"HEAD_DRIFT {row['path']}")
        else:
            head_err += 1
            err = (row.get("head_error") or "")[:120]
            out.append(f"HEAD_MISS {row['path']} {err}")
    out.insert(0, f"head_match={head_yes} head_drift={head_no} head_miss={head_err}")
    for row in data["files"]:
        path = row["path"]
        name = path.rsplit("/", 1)[-1]
        if "json" in row:
            payload = row["json"]
            if "error" in payload:
                out.append(f"JSONERR {name}: {payload['error']}")
                continue
            out.append(f"=== {name} ===")
            out.append(f"  scalars={clip(payload.get('scalars'), 900)}")
            highlights = payload.get("highlights") or {}
            if highlights:
                out.append(f"  highlights_keys={list(highlights)}")
                for key, value in highlights.items():
                    out.append(f"  {key}: {clip(value, 600)}")
            for key, value in payload.items():
                if key.startswith("list_") or key.startswith("obj_"):
                    out.append(f"  {key}: {clip(value, 500)}")
        if "outline" in row:
            outline = row["outline"]
            out.append(f"=== PY {name} lines={outline['lines']} ===")
            out.append("HEAD:")
            out.extend(f"  {line}" for line in outline["head"])
            out.append("IMPORTS:")
            out.extend(f"  {line}" for line in outline["imports"])
            out.append("DEFS:")
            out.extend(f"  {line}" for line in outline["defs"])
        if "snapshot" in row:
            snap = row["snapshot"]
            out.append(f"=== SNAP {name} lines={snap['lines']} ===")
            out.extend(f"  {line}" for line in snap["head"])
        if "wal" in row:
            wal = row["wal"]
            out.append(
                f"WAL {name} size={wal['size']} magic={wal['ascii_prefix']!r} "
                f"parent_sqlite={row.get('parent_sqlite')}"
            )
        if "parent_on_disk" in row:
            out.append(
                f"SIDECAR {name} parent_on_disk={row['parent_on_disk']} "
                f"parent={row.get('parent_path')}"
            )
    FRAG.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {FRAG} lines={len(out)} bytes={FRAG.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
