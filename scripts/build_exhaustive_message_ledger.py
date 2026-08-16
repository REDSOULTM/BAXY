"""Build an occurrence-complete Carter/BAXY historical message ledger.

Unlike the product corpus builder, this inventory does not sample one
representative objective per canonical mission.  It walks every reachable Git
blob for message-bearing logs (including deleted historical revisions), the
current worktrees, non-Git historical roots, local Gemma sessions, and relevant
Codex development sessions.  Every recovered occurrence keeps its provenance;
exact duplicates remain in the occurrence ledger and share one executable case.

The script only reads sources.  It never replays a message or executes a tool.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_historical_corpus import (  # noqa: E402
    classify,
    normalize,
    redact,
    requirement_tags,
    resolve_operation_polarity,
    risk_policy,
    text_content,
)


REPO = Path(__file__).resolve().parents[1]
PROGRAMACION = REPO.parent
HOME = Path.home()

GIT_ROOTS = {
    "baxy": REPO,
    "probando_gemma4": PROGRAMACION / "Probando Gemma 4",
    "carter_os_ai": PROGRAMACION / "Carter OS AI",
}
NON_GIT_ROOTS = {
    "functiongemma": PROGRAMACION / "FunctionGemma",
    "carter_os": PROGRAMACION / "Carter OS",
    "gemma4_local": HOME / ".gemma4" / "sessions",
}

MESSAGE_SUFFIXES = {
    ".json",
    ".jsonl",
    ".ndjson",
    ".log",
    ".txt",
    ".csv",
    ".tsv",
    ".yaml",
    ".yml",
}
PATH_CUE = re.compile(
    r"(?:trace|session|history|histor|chat|conversation|audit|runs?|cases?|"
    r"corpus|eval|request|prompt|real[_-]?logs?|marathon|results?|probe)",
    re.IGNORECASE,
)
DERIVED_CUE = re.compile(
    r"(?:historical_messages|historical_message_mapping|historical_missions|"
    r"source_manifest|extraction_report|corpus_oracle|planner_gate|"
    r"message_occurrences|exhaustive_message)",
    re.IGNORECASE,
)
EXCLUDED_PARTS = {
    ".git",
    ".runtime",
    ".venv",
    "venv",
    "node_modules",
    "site-packages",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    # Carter kept third-party reference checkouts here.  They are useful
    # implementation research, but their benchmark prompts are not messages
    # ever sent to Carter/BAXY and would contaminate the product ledger.
    "extras",
}
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_MESSAGE_CHARS = 100_000

USER_KEYS = (
    "utterance",
    "user_text",
    "query",
    "q",
    "cmd",
    "command",
    "prompt",
    "input",
)
TEXT_LOG_PREFIX = re.compile(
    r"^\s*(?:user|usuario|usuaria|vos|you|human|prompt|query|cmd|command|"
    r"utterance)\s*(?::|>)\s*(.+?)\s*$",
    re.IGNORECASE,
)
INJECTED_ONLY_PREFIXES = (
    "<recommended_plugins>",
    "<environment_context>",
    "<permissions instructions>",
    "<app-context>",
    "<collaboration_mode>",
    "<skills_instructions>",
    "<apps_instructions>",
    "<plugins_instructions>",
    "<turn_aborted>",
)
CODEX_REQUEST_MARKER = "## My request for Codex:"
SYSTEM_PROMPT_CUE = re.compile(
    r"(?:<\|system|^\s*system\s*:|you are (?:an?|the) |"
    r"available tools|tool schemas?|developer instructions?)",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class SourceDocument:
    family: str
    source_kind: str
    revision: str
    relative_path: str
    data: bytes


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_candidate_path(value: str) -> bool:
    path = Path(value.replace("\\", "/"))
    lowered_parts = {part.casefold() for part in path.parts}
    return (
        path.suffix.casefold() in MESSAGE_SUFFIXES
        and not (lowered_parts & EXCLUDED_PARTS)
        and not any(part.startswith(".venv") for part in lowered_parts)
        and PATH_CUE.search(value) is not None
        and DERIVED_CUE.search(value) is None
    )


def run_git(root: Path, *args: str, text: bool = True) -> str | bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
    )
    return completed.stdout


def git_documents(family: str, root: Path) -> Iterator[SourceDocument]:
    if not (root / ".git").exists():
        return
    objects = str(run_git(root, "rev-list", "--objects", "--all"))
    candidates: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for line in objects.splitlines():
        if " " not in line:
            continue
        object_id, relative = line.split(" ", 1)
        if not is_candidate_path(relative) or (object_id, relative) in seen:
            continue
        seen.add((object_id, relative))
        candidates.append((object_id, relative))

    # Ask Git for object sizes first.  Some old repositories contain model or
    # training-result blobs whose filenames look like logs but are hundreds of
    # megabytes.  Reading those blobs just to reject them made the inventory
    # appear hung and could consume gigabytes of memory.
    check = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "cat-file",
            "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        ],
        input="".join(f"{object_id}\n" for object_id, _ in candidates),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    eligible: list[tuple[str, str]] = []
    for candidate, line in zip(candidates, check.stdout.splitlines(), strict=True):
        parts = line.split()
        if len(parts) != 3:
            continue
        _, kind, raw_size = parts
        try:
            size = int(raw_size)
        except ValueError:
            continue
        if kind == "blob" and size <= MAX_SOURCE_BYTES:
            eligible.append(candidate)
    print(
        f"git inventory: {family} {len(eligible)}/{len(candidates)} "
        "candidate blobs within size limit",
        file=sys.stderr,
        flush=True,
    )

    if not eligible:
        return

    # On Git for Windows, keeping stdin/stdout open concurrently for a long
    # `cat-file --batch` stream can deadlock.  `subprocess.run` drains both
    # pipes safely; small chunks also cap memory even for the 64 MiB boundary.
    for offset in range(0, len(eligible), 8):
        chunk = eligible[offset : offset + 8]
        result = subprocess.run(
            ["git", "-C", str(root), "cat-file", "--batch"],
            input="".join(f"{object_id}\n" for object_id, _ in chunk).encode("ascii"),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stream = io.BytesIO(result.stdout)
        for object_id, relative in chunk:
            header = stream.readline().decode("ascii", errors="replace").strip()
            parts = header.split()
            if len(parts) != 3:
                continue
            _, kind, raw_size = parts
            try:
                size = int(raw_size)
            except ValueError:
                continue
            data = stream.read(size)
            _ = stream.read(1)
            if kind == "blob" and len(data) == size:
                yield SourceDocument(family, "git_blob", object_id, relative, data)


def walk_files(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    for current, directories, files in os.walk(root):
        directories[:] = [
            item
            for item in directories
            if item.casefold() not in EXCLUDED_PARTS
            and not item.casefold().startswith(".venv")
        ]
        for name in files:
            path = Path(current) / name
            try:
                relative = path.relative_to(root).as_posix()
                size = path.stat().st_size
            except (OSError, ValueError):
                continue
            if is_candidate_path(relative) and size <= MAX_SOURCE_BYTES:
                yield path


def live_documents(family: str, root: Path) -> Iterator[SourceDocument]:
    paths: Iterable[Path]
    if family == "gemma4_local" and root.exists():
        paths = (
            path
            for path in root.glob("*.json")
            if path.is_file() and path.stat().st_size <= MAX_SOURCE_BYTES
        )
    else:
        paths = walk_files(root)
    for path in paths:
        try:
            data = path.read_bytes()
            relative = path.relative_to(root).as_posix()
        except OSError:
            continue
        yield SourceDocument(
            family,
            "live_file",
            sha256_bytes(data),
            relative,
            data,
        )


def clean_codex_user_text(value: str) -> str:
    text = value.strip()
    if not text or any(text.startswith(prefix) for prefix in INJECTED_ONLY_PREFIXES):
        return ""
    if CODEX_REQUEST_MARKER in text:
        text = text.rsplit(CODEX_REQUEST_MARKER, 1)[1].strip()
    return text


def codex_documents() -> Iterator[SourceDocument]:
    sessions = HOME / ".codex" / "sessions"
    if not sessions.exists():
        return
    relevant_roots = tuple(str(path.resolve()).casefold() for path in GIT_ROOTS.values())
    for path in sessions.rglob("*.jsonl"):
        try:
            prefix: list[bytes] = []
            with path.open("rb") as handle:
                for _ in range(5):
                    line = handle.readline()
                    if not line:
                        break
                    prefix.append(line)
        except OSError:
            continue
        cwd = ""
        for raw_line in prefix:
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            payload = event.get("payload") or {}
            cwd = str(payload.get("cwd") or cwd)
        if not cwd or not str(Path(cwd).resolve()).casefold().startswith(relevant_roots):
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        yield SourceDocument(
            "codex_development",
            "codex_session",
            sha256_bytes(data),
            path.name,
            data,
        )


def scalar_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return text_content(value)


def json_messages(value: Any, pointer: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        if value.get("role") == "user":
            content = scalar_text(value.get("content"))
            if content:
                yield pointer + "/content", content
            return

        if value.get("kind") == "request_start":
            content = value.get("content") or {}
            if isinstance(content, dict):
                candidate = content.get("text") or content.get("preview")
                if isinstance(candidate, str) and candidate.strip():
                    yield pointer + "/content", candidate

        yielded_keys: set[str] = set()
        for key in USER_KEYS:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                yield f"{pointer}/{key}", candidate
                yielded_keys.add(key)

        for key, child in value.items():
            if key in yielded_keys or key in {"tools", "tool_schemas", "schemas"}:
                continue
            if isinstance(child, (dict, list)):
                yield from json_messages(child, f"{pointer}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from json_messages(child, f"{pointer}/{index}")


def jsonl_messages(text: str) -> Iterator[tuple[str, str]]:
    for line_number, line in enumerate(text.splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        yield from json_messages(row, f"line:{line_number}")


def delimited_messages(text: str, delimiter: str) -> Iterator[tuple[str, str]]:
    try:
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        for row_number, row in enumerate(reader, 2):
            for key in USER_KEYS:
                value = row.get(key)
                if isinstance(value, str) and value.strip():
                    yield f"row:{row_number}/{key}", value
                    break
    except csv.Error:
        return


def text_log_messages(text: str) -> Iterator[tuple[str, str]]:
    for line_number, line in enumerate(text.splitlines(), 1):
        match = TEXT_LOG_PREFIX.match(line)
        if match:
            yield f"line:{line_number}", match.group(1)


def document_messages(document: SourceDocument) -> Iterator[tuple[str, str]]:
    text = document.data.decode("utf-8", errors="replace")
    suffix = Path(document.relative_path).suffix.casefold()
    if document.source_kind == "codex_session":
        for locator, value in jsonl_messages(text):
            cleaned = clean_codex_user_text(value)
            if cleaned:
                yield locator, cleaned
        return
    if suffix in {".jsonl", ".ndjson"}:
        yield from jsonl_messages(text)
        return
    if suffix == ".json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return
        yield from json_messages(value)
        return
    if suffix in {".csv", ".tsv"}:
        yield from delimited_messages(text, "\t" if suffix == ".tsv" else ",")
        return
    yield from text_log_messages(text)


def plausible_user_text(locator: str, value: str) -> bool:
    text = value.strip()
    if not text or any(text.startswith(prefix) for prefix in INJECTED_ONLY_PREFIXES):
        return False
    if locator.casefold().endswith("/prompt") and (
        len(text) > 8_000 or SYSTEM_PROMPT_CUE.search(text) is not None
    ):
        return False
    return True


def source_version(document: SourceDocument) -> str:
    match = re.search(
        r"(?:carter[_ -]?v|baxy[_ -]?v)(\d+)",
        document.relative_path,
        re.IGNORECASE,
    )
    if match:
        return f"v{match.group(1)}"
    if document.family == "probando_gemma4":
        return "probando_gemma4"
    if document.family == "gemma4_local":
        return "gemma4_local"
    if document.family == "baxy":
        return "baxy_current_or_legacy"
    return document.family


def provenance_class(document: SourceDocument) -> str:
    path = document.relative_path.casefold()
    if document.source_kind == "codex_session":
        return "development_observed"
    if document.family == "gemma4_local" or "traces" in path or "session" in path:
        return "runtime_observed"
    return "runtime_historical_case"


def existing_contracts() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    path = REPO / "tests" / "data" / "historical_messages.jsonl"
    exact: dict[str, dict[str, Any]] = {}
    normalized: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not path.exists():
        return exact, normalized
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        literal = str(row.get("text_literal") or "")
        exact[sha256_bytes(literal.encode("utf-8"))] = row
        normalized[normalize(literal)].append(row)
    return exact, normalized


def all_documents() -> Iterator[SourceDocument]:
    seen: set[tuple[str, str, str]] = set()
    for family, root in GIT_ROOTS.items():
        for document in itertools.chain(
            git_documents(family, root),
            live_documents(family, root),
        ):
            key = (family, document.relative_path, sha256_bytes(document.data))
            if key not in seen:
                seen.add(key)
                yield document
    for family, root in NON_GIT_ROOTS.items():
        for document in live_documents(family, root):
            key = (family, document.relative_path, sha256_bytes(document.data))
            if key not in seen:
                seen.add(key)
                yield document
    for document in codex_documents():
        key = (
            document.family,
            document.relative_path,
            sha256_bytes(document.data),
        )
        if key not in seen:
            seen.add(key)
            yield document


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def build() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    exact_contracts, normalized_contracts = existing_contracts()
    occurrences: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    documents_count = 0
    occurrence_keys: set[str] = set()
    analysis_cache: dict[str, dict[str, Any] | None] = {}

    for document in all_documents():
        documents_count += 1
        if documents_count % 100 == 0:
            print(
                f"source inventory: {documents_count} documents / "
                f"{len(occurrences)} occurrences / "
                f"{document.family}:{document.relative_path}",
                file=sys.stderr,
                flush=True,
            )
        document_sha = sha256_bytes(document.data)
        for locator, raw_text in document_messages(document):
            if not plausible_user_text(locator, raw_text):
                continue
            raw = raw_text.strip().replace("\x00", "")[:MAX_MESSAGE_CHARS]
            if not raw:
                continue
            raw_sha = sha256_bytes(raw.encode("utf-8", errors="replace"))
            analysis = analysis_cache.get(raw_sha)
            if raw_sha not in analysis_cache:
                literal, was_redacted = redact(raw)
                if not literal:
                    analysis_cache[raw_sha] = None
                    continue
                literal_sha = sha256_bytes(literal.encode("utf-8"))
                normalized_text = normalize(literal)
                matched = exact_contracts.get(literal_sha)
                match_kind = "exact"
                if (
                    matched is None
                    and len(normalized_contracts.get(normalized_text, ())) == 1
                ):
                    matched = normalized_contracts[normalized_text][0]
                    match_kind = "normalized_unique"
                polarity = resolve_operation_polarity(literal)
                operations = list(polarity.actionable_operations)
                message_class = classify(
                    literal,
                    "observed_user",
                    operations,
                    effect_denied=polarity.kind in {"no_action", "constraint"},
                )
                analysis = {
                    "text_literal": literal,
                    "text_sha256": literal_sha,
                    "normalized_sha256": sha256_bytes(
                        normalized_text.encode("utf-8")
                    ),
                    "redacted": was_redacted,
                    "class": message_class,
                    "operations": operations,
                    "denied_operations": list(polarity.denied_operations),
                    "risk": risk_policy(
                        literal, operations, message_class=message_class
                    ),
                    "requirement_tags": requirement_tags(literal),
                    "existing_message_id": (
                        matched.get("message_id") if matched else None
                    ),
                    "existing_contract_match": (
                        match_kind if matched else "unmatched"
                    ),
                }
                analysis_cache[raw_sha] = analysis
            if analysis is None:
                continue
            stable = "|".join(
                (
                    document.family,
                    document.source_kind,
                    document.revision,
                    document.relative_path,
                    locator,
                    raw_sha,
                )
            )
            occurrence_id = "occ_" + sha256_bytes(stable.encode("utf-8"))[:24]
            if occurrence_id in occurrence_keys:
                continue
            occurrence_keys.add(occurrence_id)
            row = {
                "occurrence_id": occurrence_id,
                "source_family": document.family,
                "source_kind": document.source_kind,
                "source_revision": document.revision,
                "source_document_sha256": document_sha,
                "source_path": document.relative_path,
                "source_locator": locator,
                "source_version": source_version(document),
                "provenance_class": provenance_class(document),
                **analysis,
            }
            occurrences.append(row)
            source_counts[document.family] += 1

    occurrences.sort(
        key=lambda row: (
            row["source_family"],
            row["source_version"],
            row["source_path"],
            row["source_revision"],
            row["source_locator"],
            row["occurrence_id"],
        )
    )
    executable: dict[str, dict[str, Any]] = {}
    for row in occurrences:
        key = row["text_sha256"]
        case = executable.setdefault(
            key,
            {
                "case_id": "case_" + key[:24],
                "text_literal": row["text_literal"],
                "text_sha256": key,
                "class": row["class"],
                "operations": row["operations"],
                "denied_operations": row["denied_operations"],
                "risk": row["risk"],
                "provenance_classes": set(),
                "source_versions": set(),
                "occurrence_ids": [],
            },
        )
        case["provenance_classes"].add(row["provenance_class"])
        case["source_versions"].add(row["source_version"])
        case["occurrence_ids"].append(row["occurrence_id"])

    cases = []
    for case in executable.values():
        case["provenance_classes"] = sorted(case["provenance_classes"])
        case["source_versions"] = sorted(case["source_versions"])
        case["occurrence_count"] = len(case["occurrence_ids"])
        cases.append(case)
    cases.sort(key=lambda row: row["case_id"])

    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "all_recoverable_carter_baxy_message_occurrences_across_git_history_and_live_logs",
        "git_roots": {
            family: {
                "path": str(root),
                "commits": int(str(run_git(root, "rev-list", "--all", "--count")).strip()),
            }
            for family, root in GIT_ROOTS.items()
        },
        "documents_scanned": documents_count,
        "occurrences": len(occurrences),
        "unique_raw_messages_analyzed": len(analysis_cache),
        "unique_exact_messages": len(cases),
        "unique_normalized_messages": len({row["normalized_sha256"] for row in occurrences}),
        "by_source_family": dict(sorted(source_counts.items())),
        "by_provenance_class": dict(
            sorted(Counter(row["provenance_class"] for row in occurrences).items())
        ),
        "by_message_class": dict(
            sorted(Counter(row["class"] for row in occurrences).items())
        ),
        "by_version": dict(
            sorted(Counter(row["source_version"] for row in occurrences).items())
        ),
        "matched_existing_contract": sum(
            row["existing_contract_match"] != "unmatched" for row in occurrences
        ),
        "unmatched_existing_contract": sum(
            row["existing_contract_match"] == "unmatched" for row in occurrences
        ),
        "occurrence_ids_sha256": sha256_bytes(
            "\n".join(row["occurrence_id"] for row in occurrences).encode("utf-8")
        ),
        "case_ids_sha256": sha256_bytes(
            "\n".join(row["case_id"] for row in cases).encode("utf-8")
        ),
    }
    return occurrences, cases, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO / "artifacts" / "historical_exhaustive",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output_dir.resolve()
    occurrences, cases, report = build()
    write_jsonl(output / "all_message_occurrences.jsonl", occurrences)
    write_jsonl(output / "all_executable_cases.jsonl", cases)
    (output / "source_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
