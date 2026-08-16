"""Fuse opened cascade and endpoint reports without re-reading blind audio."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "baxy.cascade-endpoint-fusion-development.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fuse_group(cascade: dict[str, Any], endpoint: dict[str, Any]) -> dict[str, object]:
    cascade_records = cascade.get("records")
    endpoint_records = endpoint.get("records")
    if (
        not isinstance(cascade_records, list)
        or not isinstance(endpoint_records, list)
        or len(cascade_records) != len(endpoint_records)
        or not cascade_records
    ):
        raise ValueError("wake_fusion_record_count_mismatch")
    records: list[dict[str, object]] = []
    for index, (acoustic, lexical) in enumerate(
        zip(cascade_records, endpoint_records, strict=True)
    ):
        if (
            acoustic.get("record") != index
            or lexical.get("record") != index
            or acoustic.get("audioSha256") != lexical.get("audioSha256")
        ):
            raise ValueError("wake_fusion_record_identity_mismatch")
        cascade_hit = bool(acoustic.get("accepted"))
        endpoint_hit = bool(lexical.get("hit"))
        records.append(
            {
                "record": index,
                "audioSha256": acoustic["audioSha256"],
                "cascade": cascade_hit,
                "endpoint": endpoint_hit,
                "cascadeOrEndpoint": cascade_hit or endpoint_hit,
                "cascadeAndEndpoint": cascade_hit and endpoint_hit,
            }
        )
    policies = {}
    for name in ("cascade", "endpoint", "cascadeOrEndpoint", "cascadeAndEndpoint"):
        hits = sum(bool(record[name]) for record in records)
        policies[name] = {
            "hits": hits,
            "files": len(records),
            "rate": hits / len(records),
        }
    return {"files": len(records), "policies": policies, "records": records}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cascade-report", type=Path, required=True)
    parser.add_argument("--endpoint-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists.")
    cascade_path = args.cascade_report.resolve(strict=True)
    endpoint_path = args.endpoint_report.resolve(strict=True)
    cascade = json.loads(cascade_path.read_text(encoding="utf-8"))
    endpoint = json.loads(endpoint_path.read_text(encoding="utf-8"))
    if (
        cascade.get("corpusManifestSha256") != endpoint.get("corpusManifestSha256")
        or not cascade.get("developmentOnly")
        or not endpoint.get("developmentOnly")
        or cascade.get("blindHumanPartitionAccessed")
        or endpoint.get("blindHumanPartitionAccessed")
    ):
        raise SystemExit("Reports are not compatible opened development evidence.")
    positive = fuse_group(cascade["positive"], endpoint["positive"])
    negative = fuse_group(cascade["negative"], endpoint["negative"])
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_wasapi_raw_parallel_cascade_endpoint_fusion",
        "sourceReports": {
            "cascadeSha256": _sha256(cascade_path),
            "endpointSha256": _sha256(endpoint_path),
        },
        "corpusManifestSha256": cascade["corpusManifestSha256"],
        "positive": positive,
        "negative": negative,
        "developmentOnly": True,
        "promotable": False,
        "blindHumanPartitionAccessed": False,
        "effectsExecuted": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "positive": positive["policies"]["cascadeOrEndpoint"],
                "negative": negative["policies"]["cascadeOrEndpoint"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
