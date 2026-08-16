"""Build R16 ASR fusion from the live authenticated Core catalogue."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from baxy_mind.asr_fusion import (  # noqa: E402
    select_transcript,
    select_transcript_with_pause_safe_redecode,
)
from scripts.measure_mind_budget import (  # noqa: E402
    current_core_catalog_snapshot,
    discover_core,
)


EXPECTED_ROWS = 337
CORPUS_SCHEMA = "baxy.r16-sapi-semantic-asr-fusion-development.v2"
REPORT_SCHEMA = "baxy.r16-sapi-semantic-asr-fusion-build-development.v2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("baxy_asr_fusion_jsonl_invalid")
    return rows


def authenticated_catalog(
    core: Path,
) -> tuple[frozenset[str], tuple[str, ...], tuple[tuple[str, str, str], ...], dict[str, object]]:
    capabilities, applications, games = current_core_catalog_snapshot(core)
    if (
        not isinstance(applications, dict)
        or applications.get("verified") is not True
        or applications.get("complete") is not True
        or not isinstance(applications.get("names"), list)
        or not all(isinstance(name, str) for name in applications["names"])
        or not isinstance(games, dict)
        or games.get("verified") is not True
        or games.get("complete") is not True
        or not isinstance(games.get("entries"), list)
    ):
        raise ValueError("baxy_asr_fusion_authenticated_entities_invalid")
    operations = frozenset(
        capability.get("name")
        for capability in capabilities
        if isinstance(capability, dict) and isinstance(capability.get("name"), str)
    )
    if len(operations) != len(capabilities):
        raise ValueError("baxy_asr_fusion_catalog_invalid")
    game_entries: list[tuple[str, str, str]] = []
    for entry in games["entries"]:
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(key), str) for key in ("provider", "appId", "name")
        ):
            raise ValueError("baxy_asr_fusion_game_catalog_invalid")
        game_entries.append((entry["provider"], entry["appId"], entry["name"]))
    applications_names = tuple(applications["names"])
    identities: dict[str, object] = {
        "coreSha256": sha256(core),
        "operationCatalogSha256": canonical_sha256(capabilities),
        "applicationCatalogSha256": canonical_sha256(applications),
        "gameCatalogSha256": canonical_sha256(games),
        "operations": len(operations),
        "applications": len(applications_names),
        "games": len(game_entries),
    }
    return operations, applications_names, tuple(game_entries), identities


def build(
    *,
    parakeet_path: Path,
    whisper_path: Path,
    output_path: Path,
    report_path: Path,
    available_operations: frozenset[str],
    application_names: tuple[str, ...],
    game_catalog: tuple[tuple[str, str, str], ...],
    catalog_identities: dict[str, object],
    corpus_schema: str = CORPUS_SCHEMA,
    report_schema: str = REPORT_SCHEMA,
    scope: str = "opened_r16_authenticated_catalog_semantic_asr_fusion_build",
    supersedes: dict[str, str] | None = None,
    redecode_parakeet_path: Path | None = None,
    redecode_whisper_path: Path | None = None,
) -> dict[str, object]:
    for candidate in (output_path, report_path):
        if candidate.exists():
            raise ValueError(f"baxy_asr_fusion_output_exists:{candidate}")
    parakeet_path = parakeet_path.resolve(strict=True)
    whisper_path = whisper_path.resolve(strict=True)
    output_path = output_path.resolve()
    report_path = report_path.resolve()
    parakeet_rows = read_jsonl(parakeet_path)
    whisper_rows = read_jsonl(whisper_path)
    if (redecode_parakeet_path is None) != (redecode_whisper_path is None):
        raise ValueError("baxy_asr_fusion_redecode_pair_invalid")
    redecode_parakeet_rows = (
        read_jsonl(redecode_parakeet_path.resolve(strict=True))
        if redecode_parakeet_path is not None
        else None
    )
    redecode_whisper_rows = (
        read_jsonl(redecode_whisper_path.resolve(strict=True))
        if redecode_whisper_path is not None
        else None
    )
    if (
        len(parakeet_rows) != EXPECTED_ROWS
        or len(whisper_rows) != EXPECTED_ROWS
        or any(row.get("execution_authority") is not False for row in parakeet_rows)
        or any(row.get("execution_authority") is not False for row in whisper_rows)
        or (
            redecode_parakeet_rows is not None
            and (
                len(redecode_parakeet_rows) != EXPECTED_ROWS
                or any(
                    row.get("execution_authority") is not False
                    for row in redecode_parakeet_rows
                )
            )
        )
        or (
            redecode_whisper_rows is not None
            and (
                len(redecode_whisper_rows) != EXPECTED_ROWS
                or any(
                    row.get("execution_authority") is not False
                    for row in redecode_whisper_rows
                )
            )
        )
        or not available_operations
    ):
        raise ValueError("baxy_asr_fusion_population_invalid")
    derived: list[dict[str, object]] = []
    decisions: list[dict[str, str]] = []
    counts: Counter[tuple[str, str]] = Counter()
    for index, (parakeet, whisper) in enumerate(
        zip(parakeet_rows, whisper_rows, strict=True)
    ):
        case_id = str(parakeet.get("case_id"))
        if (
            case_id != str(whisper.get("case_id"))
            or parakeet.get("voice_reference_text_sha256")
            != whisper.get("voice_reference_text_sha256")
        ):
            raise ValueError(f"baxy_asr_fusion_binding_invalid:{case_id}")
        if redecode_parakeet_rows is not None and redecode_whisper_rows is not None:
            redecode_parakeet = redecode_parakeet_rows[index]
            redecode_whisper = redecode_whisper_rows[index]
            if (
                case_id != str(redecode_parakeet.get("case_id"))
                or case_id != str(redecode_whisper.get("case_id"))
                or parakeet.get("voice_reference_text_sha256")
                != redecode_parakeet.get("voice_reference_text_sha256")
                or parakeet.get("voice_reference_text_sha256")
                != redecode_whisper.get("voice_reference_text_sha256")
            ):
                raise ValueError(f"baxy_asr_fusion_redecode_binding_invalid:{case_id}")
            selection = select_transcript_with_pause_safe_redecode(
                str(parakeet.get("text") or ""),
                str(whisper.get("text") or ""),
                str(redecode_parakeet.get("text") or ""),
                str(redecode_whisper.get("text") or ""),
                available_operations,
                application_names,
                game_catalog,
            )
        else:
            selection = select_transcript(
                str(parakeet.get("text") or ""),
                str(whisper.get("text") or ""),
                available_operations,
                application_names,
                game_catalog,
            )
        if selection.requires_clarification:
            raise ValueError(f"baxy_asr_fusion_conflict:{case_id}:{selection.reason}")
        row = dict(parakeet)
        row.update(
            {
                "schema": corpus_schema,
                "text": selection.text,
                "transcript_authority": selection.source,
                "transcript_selection_reason": selection.reason,
            }
        )
        derived.append(row)
        decisions.append(
            {"caseId": case_id, "source": selection.source, "reason": selection.reason}
        )
        counts[(selection.source, selection.reason)] += 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in derived
        ),
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, output_path)
    report: dict[str, object] = {
        "schema": report_schema,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "sources": {
            "parakeetCorpusSha256": sha256(parakeet_path),
            "whisperCorpusSha256": sha256(whisper_path),
            "authenticatedCatalog": catalog_identities,
            **(
                {
                    "redecodeParakeetCorpusSha256": sha256(
                        redecode_parakeet_path.resolve(strict=True)
                    ),
                    "redecodeWhisperCorpusSha256": sha256(
                        redecode_whisper_path.resolve(strict=True)
                    ),
                }
                if redecode_parakeet_path is not None
                and redecode_whisper_path is not None
                else {}
            ),
        },
        "rows": len(derived),
        "selectionCounts": [
            {"source": source, "reason": reason, "cases": cases}
            for (source, reason), cases in sorted(counts.items())
        ],
        "decisions": decisions,
        "outputSha256": sha256(output_path),
        "usesExpectedLabelsForSelection": False,
        "catalogSource": "live_core_hello",
        "supersedes": supersedes
        or {
            "artifact": "r16_sapi_semantic_asr_fusion_build_v1.v1.json",
            "reason": "v1_derived_operation_inventory_from_evaluation_labels",
        },
        "effectsExecuted": 0,
        "developmentOnly": True,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parakeet", type=Path, required=True)
    parser.add_argument("--whisper", type=Path, required=True)
    parser.add_argument("--redecode-parakeet", type=Path)
    parser.add_argument("--redecode-whisper", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--dotnet-root", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    if arguments.dotnet_root is not None:
        dotnet_root = str(arguments.dotnet_root.resolve(strict=True))
        os.environ["DOTNET_ROOT"] = dotnet_root
        os.environ["DOTNET_ROOT_X64"] = dotnet_root
        os.environ["DOTNET_ROOT(x64)"] = dotnet_root
    core = discover_core(arguments.core)
    operations, applications, games, identities = authenticated_catalog(core)
    report = build(
        parakeet_path=arguments.parakeet,
        whisper_path=arguments.whisper,
        output_path=arguments.output,
        report_path=arguments.report,
        available_operations=operations,
        application_names=applications,
        game_catalog=games,
        catalog_identities=identities,
        redecode_parakeet_path=arguments.redecode_parakeet,
        redecode_whisper_path=arguments.redecode_whisper,
    )
    print(json.dumps({"rows": report["rows"], "outputSha256": report["outputSha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
