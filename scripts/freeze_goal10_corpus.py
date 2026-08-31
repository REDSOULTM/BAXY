"""Freeze Goal 10 observed-user corpora N10/M10/C10 and the 10.7–10.16 queue.

Selection, subset floors, C10 membership and partition assignment are pure
functions over already-frozen authority rows. I/O stays at the edge. Derived
JSONL with user text is not versioned; counts, hashes, schema, the partition
index and tests are.

09.5.4 residual_evidence is never opened. Language labels are not the
partition: owner goals follow operations, compounds and zero-op semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Iterator

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tests" / "data"
SOURCE_MESSAGES = DATA / "historical_messages.jsonl"
SOURCE_MAPPING = DATA / "historical_message_mapping.jsonl"

N10_NAME = "goal10_n10.v1.jsonl"
M10_NAME = "goal10_m10.v1.jsonl"
C10_NAME = "goal10_c10.v1.jsonl"
INDEX_NAME = "goal10_partition_index.v1.jsonl"
MANIFEST_NAME = "goal10_corpus_freeze.v1.json"

SCHEMA = "baxy.goal10.corpus_freeze.v1"
CUTOFF_UTC = "2026-07-14T10:51:49.1612548Z"
CUTOFF_STATE_SHA256 = (
    "85929373646040f54771a7e3543a5ac3d022dbce688c55d17615ae35b7eb3fbd"
)
EVIDENCE_BUILDER_COMMIT = "a6cd673"
EXCLUDED_SOURCE_PREFIX = "codex/"
OBSERVED_ORIGIN = "observed_user"
PRODUCT_ACCEPTANCE_SCOPE = "product_1_0"
TRACE_ONLY_SCOPE = "trace_only_not_acceptance_commitment"

FLOOR_N10_ROWS = 1947
FLOOR_N10_UNIQUE_TEXTS = 626
FLOOR_M10_ROWS = 808
FLOOR_M10_UNIQUE_TEXTS = 281
FLOOR_C10_CHAINS = 74
FLOOR_SOURCE_PREFIXES = ("probando_gemma4/", "gemma4_local/")

OWNER_GOALS = tuple(f"10.{n}" for n in range(7, 17))

OWNER_BY_OPERATION: dict[str, str] = {
    "system.status": "10.8",
    "web.search": "10.9",
    "app.open": "10.10",
    "app.close": "10.10",
    "window.manage": "10.10",
    "vision.describe": "10.10",
    "capture.screenshot": "10.10",
    "ocr.read": "10.10",
    "audio.volume": "10.11",
    "audio.mute": "10.11",
    "audio.status": "10.11",
    "media.play": "10.12",
    "media.control": "10.12",
    "streaming.navigate": "10.12",
    "game.install": "10.12",
    "game.launch": "10.12",
    "game.manage": "10.12",
    "game.purchase": "10.12",
    "system.settings": "10.13",
    "system.power": "10.13",
    "wifi.manage": "10.13",
    "bluetooth.manage": "10.13",
    "peripheral.manage": "10.13",
    "backup.manage": "10.13",
    "package.install": "10.13",
    "note.manage": "10.14",
    "calendar.manage": "10.14",
    "reminder.create": "10.14",
    "memory.recall": "10.14",
    "memory.save": "10.14",
    "memory.forget": "10.14",
    "task.manage": "10.14",
    "notification.manage": "10.14",
    "routine.manage": "10.14",
    "filesystem.search": "10.14",
    "filesystem.read": "10.14",
    "filesystem.write": "10.14",
    "filesystem.transfer": "10.14",
    "filesystem.trash": "10.14",
    "browser.navigate": "10.15",
    "message.send": "10.15",
    "clipboard.manage": "10.15",
    "office.document": "10.15",
}

OPERATION_ENVIRONMENT: dict[str, tuple[str, ...]] = {
    "app.open": ("target_application",),
    "app.close": ("target_application",),
    "window.manage": ("target_window",),
    "vision.describe": ("visible_window_or_image",),
    "capture.screenshot": ("visible_desktop",),
    "ocr.read": ("visible_window_or_image",),
    "audio.volume": ("audio_output",),
    "audio.mute": ("audio_output",),
    "audio.status": ("audio_output",),
    "media.play": ("media_app", "playable_content"),
    "media.control": ("active_media_session",),
    "streaming.navigate": (
        "streaming_service",
        "streaming_account",
        "requested_title",
    ),
    "game.install": ("game_client", "game_library"),
    "game.launch": ("game_client", "installed_game"),
    "game.manage": ("game_client",),
    "game.purchase": ("game_client", "store_account"),
    "system.status": (),
    "system.settings": (),
    "system.power": ("host_session",),
    "wifi.manage": ("wifi_adapter",),
    "bluetooth.manage": ("bluetooth_adapter", "pairable_device"),
    "peripheral.manage": ("target_peripheral",),
    "backup.manage": ("backup_target",),
    "package.install": ("package_source",),
    "web.search": ("network",),
    "browser.navigate": ("browser",),
    "message.send": ("messaging_app", "test_recipient_account"),
    "clipboard.manage": (),
    "office.document": ("office_application",),
    "note.manage": ("note_store",),
    "calendar.manage": ("calendar_store",),
    "reminder.create": ("reminder_store",),
    "memory.recall": (),
    "memory.save": (),
    "memory.forget": (),
    "task.manage": ("task_store",),
    "notification.manage": ("notification_scheduler",),
    "routine.manage": ("routine_store",),
    "filesystem.search": ("filesystem_scope",),
    "filesystem.read": ("target_file",),
    "filesystem.write": ("writable_path",),
    "filesystem.transfer": ("source_and_destination_paths",),
    "filesystem.trash": ("target_file",),
}

ACCOUNT_OPERATIONS = frozenset(
    {
        "media.play",
        "streaming.navigate",
        "game.install",
        "game.launch",
        "game.manage",
        "game.purchase",
        "message.send",
        "calendar.manage",
    }
)

LOCAL_FACT_RE = re.compile(
    r"(?i)\b(qu[eé]\s+hora|what\s+time|qu[eé]\s+d[ií]a|what\s+day|"
    r"qu[eé]\s+fecha|fecha\s+es|hora\s+es|d[ií]a\s+es|"
    r"procesos?\b|cpu\b|ram\b|gpu\b|bater[ií]a|battery|"
    r"temperatura|ventanas?\s+abiert|qu[eé]\s+hay\s+abierto|"
    r"estado\s+del\s+pc|disk\s+space|espacio\s+en\s+disco)\b"
)
WEB_CURRENT_RE = re.compile(
    r"(?i)\b(busca(?:r)?\b|googlea|noticias?|news\b|actualidad|"
    r"en\s+internet|en\s+la\s+web|who\s+won|qui[eé]n\s+gan[oó]|"
    r"clima\b|weather|qu[eé]\s+pas[oó]\s+con|latest)\b"
)

GOAL095_FROZEN_SOURCES = (
    {
        "logical": "Programacion/BAXY",
        "role": "generation_5",
        "authority_family": "baxy",
    },
    {
        "logical": "Programacion/Carter OS AI",
        "role": "generation_1_2",
        "authority_family": "carter_os_ai",
    },
    {
        "logical": "Programacion/FunctionGemma",
        "role": "generation_4",
        "authority_family": "functiongemma",
    },
    {
        "logical": "Programacion/Probando Gemma 4",
        "role": "generation_3",
        "authority_family": "probando_gemma4",
    },
    {
        "logical": "gemma4_local",
        "role": "local_gemma_session_store",
        "authority_family": "gemma4_local",
    },
)

PUBLIC_INDEX_FIELDS = (
    "message_id",
    "owner_goal",
    "in_n10",
    "in_m10",
    "in_c10",
    "family_key",
    "class",
    "operations",
    "required_environment",
    "security_fixture",
    "language_scope",
    "source_family",
    "risk_class",
    "repetition_family",
)

PRIVATE_PAYLOAD_KEYS = frozenset(
    {
        "text_literal",
        "paraphrase",
        "natural_response",
        "expected_state",
        "fallback",
        "success_evidence",
    }
)

REPETITION_SELECTION_RULE = (
    "Among non-C10 N10 rows, rank family_key by observed occurrence count "
    "(duplicates kept), then name. Pick five keys whose owner partitions are "
    "distinct so the 10.3–10.6 dose covers general use, not a single area."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def source_family(source: str) -> str:
    return str(source or "").split("/", 1)[0]


def operations_of(row: dict[str, Any]) -> list[str]:
    return [str(op) for op in (row.get("operations") or [])]


def is_compound(row: dict[str, Any]) -> bool:
    return bool(row.get("possible_chain")) or len(operations_of(row)) > 1


def is_floor_row(row: dict[str, Any]) -> bool:
    source = str(row.get("source") or "")
    return row.get("origin") == OBSERVED_ORIGIN and source.startswith(
        FLOOR_SOURCE_PREFIXES
    )


def select_n10(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if row.get("origin") != OBSERVED_ORIGIN:
            continue
        source = str(row.get("source") or "")
        if source.startswith(EXCLUDED_SOURCE_PREFIX):
            continue
        message_id = str(row.get("message_id") or "")
        if not message_id:
            raise RuntimeError("observed_user row is missing message_id")
        if message_id in seen:
            raise RuntimeError(f"duplicate message_id in N10 selection: {message_id}")
        seen.add(message_id)
        selected.append(row)
    return selected


def select_m10(n10: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in n10 if row.get("class") == "user_mission"]


def select_c10(n10: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in n10 if is_compound(row)]


def is_web_current_text(text: str) -> bool:
    return bool(WEB_CURRENT_RE.search(text or ""))


def is_local_fact_text(text: str) -> bool:
    return bool(LOCAL_FACT_RE.search(text or ""))


def assign_owner_goal(row: dict[str, Any]) -> str:
    ops = operations_of(row)
    if is_compound(row):
        return "10.16"
    message_class = str(row.get("class") or "")
    if message_class == "no_action_constraint":
        return "10.7"
    if message_class == "feedback_failure":
        return "10.7"
    if ops:
        owner = OWNER_BY_OPERATION.get(ops[0])
        if owner is None:
            raise RuntimeError(
                f"unmapped operation {ops[0]!r} on {row.get('message_id')}"
            )
        return owner
    text = str(row.get("text_literal") or "")
    if is_web_current_text(text):
        return "10.9"
    if is_local_fact_text(text):
        return "10.8"
    return "10.7"


def family_key(row: dict[str, Any]) -> str:
    if is_compound(row):
        return "compound:" + "+".join(operations_of(row))
    ops = operations_of(row)
    if ops:
        return ops[0]
    owner = assign_owner_goal(row)
    if owner == "10.8":
        return "local_facts"
    if owner == "10.9":
        return "web_current"
    return "conversation"


def family_owner_goal(key: str) -> str:
    if key.startswith("compound:"):
        return "10.16"
    if key == "conversation":
        return "10.7"
    if key == "local_facts":
        return "10.8"
    if key == "web_current":
        return "10.9"
    owner = OWNER_BY_OPERATION.get(key)
    if owner is None:
        raise RuntimeError(f"unmapped family key {key!r}")
    return owner


def required_environment(row: dict[str, Any]) -> list[str]:
    reqs: set[str] = set()
    ops = operations_of(row)
    flags = {str(flag) for flag in (row.get("data_or_preferences") or [])}
    for op in ops:
        reqs.update(OPERATION_ENVIRONMENT.get(op, ()))
    if flags.intersection({"account"}) and any(op in ACCOUNT_OPERATIONS for op in ops):
        reqs.add("signed_in_account")
    if "file_content" in flags and any(op.startswith("filesystem.") for op in ops):
        reqs.add("target_file")
    if "screen_content" in flags and any(
        op in {"vision.describe", "ocr.read", "capture.screenshot"} for op in ops
    ):
        reqs.add("visible_window_or_image")
    return sorted(reqs)


def security_fixture(row: dict[str, Any]) -> str | None:
    ops = set(operations_of(row))
    risk = str((row.get("risk") or {}).get("class") or "")
    if "game.purchase" in ops or risk == "monetary":
        return "monetary_checkout_fixture"
    if "message.send" in ops or risk == "external_communication":
        return "test_recipient_or_draft_fixture"
    if "system.power" in ops or risk == "session_disruption":
        return "host_power_transition_fixture"
    if risk == "forbidden_destructive":
        return "blocked_destructive_no_physical"
    if "filesystem.trash" in ops and risk == "irreversible":
        return "irreversible_delete_fixture"
    if "backup.manage" in ops:
        return "disposable_backup_target_fixture"
    if risk == "work_loss":
        return "unsaved_work_confirmation_no_personal_data"
    return None


def choose_repetition_families(
    n10: Iterable[dict[str, Any]], *, k: int = 5
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    unique_texts: dict[str, set[str]] = defaultdict(set)
    for row in n10:
        if is_compound(row):
            continue
        key = family_key(row)
        counts[key] += 1
        unique_texts[key].add(str(row.get("text_sha256") or ""))
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    picked: list[dict[str, Any]] = []
    used_partitions: set[str] = set()
    leftover: list[tuple[str, int]] = []
    for key, count in ranked:
        owner = family_owner_goal(key)
        if owner in used_partitions:
            leftover.append((key, count))
            continue
        used_partitions.add(owner)
        picked.append(_family_record(key, count, unique_texts[key], owner, len(picked)))
        if len(picked) == k:
            return picked
    for key, count in leftover:
        if len(picked) == k:
            break
        picked.append(
            _family_record(
                key, count, unique_texts[key], family_owner_goal(key), len(picked)
            )
        )
    if len(picked) != k:
        raise RuntimeError(f"could not freeze {k} repetition families, got {len(picked)}")
    return picked


def _family_record(
    key: str, count: int, texts: set[str], owner: str, index: int
) -> dict[str, Any]:
    return {
        "name": key,
        "family_key": key,
        "rank": index + 1,
        "observed_occurrences": count,
        "unique_texts": len(texts),
        "owner_goal": owner,
        "frozen_for": ["10.3", "10.4", "10.5", "10.6"],
    }


def annotate_row(
    row: dict[str, Any],
    *,
    repetition_keys: set[str],
) -> dict[str, Any]:
    owner = assign_owner_goal(row)
    key = family_key(row)
    annotated = dict(row)
    annotated["owner_goal"] = owner
    annotated["family_key"] = key
    annotated["in_n10"] = True
    annotated["in_m10"] = row.get("class") == "user_mission"
    annotated["in_c10"] = is_compound(row)
    annotated["required_environment"] = required_environment(row)
    annotated["security_fixture"] = security_fixture(row)
    annotated["language_scope"] = str(
        row.get("acceptance_scope") or PRODUCT_ACCEPTANCE_SCOPE
    )
    annotated["source_family"] = source_family(str(row.get("source") or ""))
    annotated["risk_class"] = str((row.get("risk") or {}).get("class") or "")
    annotated["repetition_family"] = (
        key if (key in repetition_keys and not is_compound(row)) else None
    )
    return annotated


def public_index_row(annotated: dict[str, Any]) -> dict[str, Any]:
    return {field: annotated[field] for field in PUBLIC_INDEX_FIELDS}


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("rb") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as error:
                raise RuntimeError(f"Invalid JSON at {path}:{line_number}") from error
            if not isinstance(row, dict):
                raise RuntimeError(f"JSON object required at {path}:{line_number}")
            yield row


def read_mapping_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    for row in iter_jsonl(path):
        message_id = str(row.get("message_id") or "")
        if not message_id or message_id in ids:
            raise RuntimeError(f"missing or duplicate mapping id: {message_id}")
        ids.add(message_id)
    return ids


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(canonical_json(row))
            handle.write("\n")
    temporary.replace(path)


def _logical_output_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def ids_digest(rows: Iterable[dict[str, Any]]) -> str:
    joined = "\n".join(str(row["message_id"]) for row in rows)
    return sha256_text(joined)


def level_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "unique_message_ids": len({row["message_id"] for row in rows}),
        "unique_text_sha256": len({str(row.get("text_sha256") or "") for row in rows}),
        "class_counts": dict(sorted(Counter(row.get("class") for row in rows).items())),
        "source_family_counts": dict(
            sorted(Counter(row.get("source_family") for row in rows).items())
        ),
        "language_label_counts": dict(
            sorted(Counter(row.get("language") for row in rows).items())
        ),
        "risk_class_counts": dict(
            sorted(Counter(row.get("risk_class") for row in rows).items())
        ),
        "required_environment_counts": dict(
            sorted(
                Counter(
                    req
                    for row in rows
                    for req in (row.get("required_environment") or [])
                ).items()
            )
        ),
        "security_fixture_counts": dict(
            sorted(
                Counter(
                    row.get("security_fixture")
                    for row in rows
                    if row.get("security_fixture")
                ).items()
            )
        ),
        "family_counts": dict(
            sorted(Counter(row.get("family_key") for row in rows).items())
        ),
        "message_ids_sha256": ids_digest(rows),
    }


def partition_publication(n10: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {goal: [] for goal in OWNER_GOALS}
    for row in n10:
        grouped[row["owner_goal"]].append(row)
    publication: dict[str, Any] = {}
    for goal in OWNER_GOALS:
        members = grouped[goal]
        publication[goal] = {
            "owner_goal": goal,
            **level_counts(members),
            "mission_count": sum(1 for row in members if row.get("in_m10")),
            "compound_count": sum(1 for row in members if row.get("in_c10")),
        }
    return publication


def assert_disjoint_cover(n10: list[dict[str, Any]]) -> None:
    by_goal: dict[str, set[str]] = defaultdict(set)
    missing: list[str] = []
    unknown: list[str] = []
    for row in n10:
        message_id = str(row["message_id"])
        owner = row.get("owner_goal")
        if owner not in OWNER_GOALS:
            unknown.append(message_id)
            continue
        by_goal[str(owner)].add(message_id)
    ids = [str(row["message_id"]) for row in n10]
    union = set()
    for goal, members in by_goal.items():
        overlap = union.intersection(members)
        if overlap:
            raise RuntimeError(
                f"partition overlap on {goal}: {len(overlap)} message_ids"
            )
        union.update(members)
    if unknown:
        raise RuntimeError(f"{len(unknown)} rows assigned outside 10.7–10.16")
    missing = sorted(set(ids) - union)
    if missing:
        raise RuntimeError(f"{len(missing)} N10 rows missing a 10.7–10.16 owner")
    if len(union) != len(ids):
        raise RuntimeError("partition union does not equal N10")


def floor_snapshot(n10: list[dict[str, Any]], all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    n10_ids = {str(row["message_id"]) for row in n10}
    n10_texts = {str(row.get("text_sha256") or "") for row in n10}
    m10 = [row for row in n10 if row.get("in_m10")]
    m10_ids = {str(row["message_id"]) for row in m10}
    m10_texts = {str(row.get("text_sha256") or "") for row in m10}
    c10 = [row for row in n10 if row.get("in_c10")]
    c10_ids = {str(row["message_id"]) for row in c10}

    floor = [row for row in all_rows if is_floor_row(row)]
    floor_ids = {str(row["message_id"]) for row in floor}
    floor_texts = {str(row.get("text_sha256") or "") for row in floor}
    floor_m10 = [row for row in floor if row.get("class") == "user_mission"]
    floor_m10_ids = {str(row["message_id"]) for row in floor_m10}
    floor_m10_texts = {str(row.get("text_sha256") or "") for row in floor_m10}
    floor_c10_ids = {
        str(row["message_id"]) for row in floor if bool(row.get("possible_chain"))
    }
    extra_c10 = c10_ids - m10_ids
    if extra_c10:
        raise RuntimeError("C10 rows were added on top of M10 instead of as a subset")
    if not floor_ids <= n10_ids or not floor_texts <= n10_texts:
        raise RuntimeError("N10 does not preserve the observed-user floor as a subset")
    if not floor_m10_ids <= m10_ids or not floor_m10_texts <= m10_texts:
        raise RuntimeError("M10 does not preserve the mission floor as a subset")
    if not floor_c10_ids <= c10_ids:
        raise RuntimeError("C10 does not preserve historical chains as a subset")
    return {
        "floor_n10_rows": len(floor),
        "floor_n10_unique_texts": len(floor_texts),
        "floor_m10_rows": len(floor_m10),
        "floor_m10_unique_texts": len(floor_m10_texts),
        "floor_c10_chains": len(floor_c10_ids),
        "delta_n10_rows": len(n10_ids) - len(floor_ids),
        "delta_n10_unique_texts": len(n10_texts - floor_texts),
        "delta_m10_rows": len(m10_ids) - len(floor_m10_ids),
        "delta_c10_chains": len(c10_ids) - len(floor_c10_ids),
    }


def assert_known_floors(floors: dict[str, Any]) -> None:
    if floors["floor_n10_rows"] != FLOOR_N10_ROWS:
        raise RuntimeError("authority no longer holds the 1.947 observed-user floor")
    if floors["floor_n10_unique_texts"] != FLOOR_N10_UNIQUE_TEXTS:
        raise RuntimeError("authority no longer holds the 626 unique-text floor")
    if floors["floor_m10_rows"] != FLOOR_M10_ROWS:
        raise RuntimeError("authority no longer holds the 808 observed-mission floor")
    if floors["floor_m10_unique_texts"] != FLOOR_M10_UNIQUE_TEXTS:
        raise RuntimeError("authority no longer holds the 281 unique-mission floor")
    if floors["floor_c10_chains"] != FLOOR_C10_CHAINS:
        raise RuntimeError("authority no longer holds the 74 historical chains")


def assert_no_private_payload(payload: Any, *, path: str) -> None:
    if isinstance(payload, dict):
        leaked = PRIVATE_PAYLOAD_KEYS.intersection(payload)
        if leaked:
            raise RuntimeError(f"private payload keys {sorted(leaked)} in {path}")
        for key, value in payload.items():
            assert_no_private_payload(value, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            assert_no_private_payload(value, path=f"{path}[{index}]")


def build(
    *,
    source_messages: Path = SOURCE_MESSAGES,
    source_mapping: Path = SOURCE_MAPPING,
    output_dir: Path = DATA,
    manifest_path: Path | None = None,
    index_path: Path | None = None,
    require_known_floors: bool = True,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    manifest_path = Path(manifest_path) if manifest_path else output_dir / MANIFEST_NAME
    index_path = Path(index_path) if index_path else output_dir / INDEX_NAME

    all_rows = list(iter_jsonl(source_messages))
    mapping_ids = read_mapping_ids(source_mapping)
    selected = select_n10(all_rows)
    missing_map = [
        str(row["message_id"])
        for row in selected
        if row["message_id"] not in mapping_ids
    ]
    if missing_map:
        raise RuntimeError(f"{len(missing_map)} N10 rows have no acceptance mapping")

    families = choose_repetition_families(selected)
    repetition_keys = {item["family_key"] for item in families}
    n10 = [annotate_row(row, repetition_keys=repetition_keys) for row in selected]
    assert_disjoint_cover(n10)
    floors = floor_snapshot(n10, all_rows)
    if require_known_floors:
        assert_known_floors(floors)
    m10 = [row for row in n10 if row["in_m10"]]
    c10 = [row for row in n10 if row["in_c10"]]

    n10_path = output_dir / N10_NAME
    m10_path = output_dir / M10_NAME
    c10_path = output_dir / C10_NAME
    write_jsonl(n10_path, n10)
    write_jsonl(m10_path, m10)
    write_jsonl(c10_path, c10)
    write_jsonl(index_path, (public_index_row(row) for row in n10))

    partitions = partition_publication(n10)
    manifest = {
        "schema": SCHEMA,
        "schema_version": 1,
        "goal": "10.1",
        "evidence_builder_commit": EVIDENCE_BUILDER_COMMIT,
        "authority": {
            "messages_path": "tests/data/historical_messages.jsonl",
            "messages_file_sha256": sha256_file(source_messages),
            "mapping_path": "tests/data/historical_message_mapping.jsonl",
            "mapping_file_sha256": sha256_file(source_mapping),
            "cutoff_utc": CUTOFF_UTC,
            "cutoff_state_sha256": CUTOFF_STATE_SHA256,
        },
        "selection": {
            "origin": OBSERVED_ORIGIN,
            "excluded_source_prefix": EXCLUDED_SOURCE_PREFIX,
            "language_partition": "semantics_not_heuristic_label",
            "duplicates": "preserved_as_real_occurrences",
            "residual_evidence": "not_reparsed",
            "level_2_class": "user_mission",
            "c10": "possible_chain_or_multiple_operations",
        },
        "floors": {
            "n10_occurrences": FLOOR_N10_ROWS,
            "n10_unique_texts": FLOOR_N10_UNIQUE_TEXTS,
            "m10_occurrences": FLOOR_M10_ROWS,
            "m10_unique_texts": FLOOR_M10_UNIQUE_TEXTS,
            "c10_historical_chains": FLOOR_C10_CHAINS,
            **floors,
        },
        "n10": {
            "path": _logical_output_path(n10_path),
            "file_sha256": sha256_file(n10_path),
            "bytes": n10_path.stat().st_size,
            **level_counts(n10),
        },
        "m10": {
            "path": _logical_output_path(m10_path),
            "file_sha256": sha256_file(m10_path),
            "bytes": m10_path.stat().st_size,
            **level_counts(m10),
        },
        "c10": {
            "path": _logical_output_path(c10_path),
            "file_sha256": sha256_file(c10_path),
            "bytes": c10_path.stat().st_size,
            "subset_of_m10": True,
            "excluded_from_direct_families": True,
            "owner_goal": "10.16",
            **level_counts(c10),
        },
        "partition_index": {
            "path": _logical_output_path(index_path),
            "file_sha256": sha256_file(index_path),
            "bytes": index_path.stat().st_size,
            "user_text_payload": False,
        },
        "goal095": {
            "sources": [dict(item) for item in GOAL095_FROZEN_SOURCES],
            "residual_evidence": "not_reparsed",
            "user_turn_delta_rows": floors["delta_n10_rows"],
            "user_turn_delta_unique_texts": floors["delta_n10_unique_texts"],
            "user_turn_delta_missions": floors["delta_m10_rows"],
            "user_turn_delta_chains": floors["delta_c10_chains"],
        },
        "partitions": partitions,
        "repetition_families": {
            "frozen_for": ["10.3", "10.4", "10.5", "10.6"],
            "count": len(families),
            "selection_rule": REPETITION_SELECTION_RULE,
            "families": families,
        },
        "privacy": {
            "classification": "private_local_project_data",
            "generated_jsonl_versioned": False,
            "publish_as_dataset": False,
            "versioned_index_has_user_text": False,
        },
    }
    assert_no_private_payload(manifest, path="manifest")
    write_json(manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-messages", type=Path, default=SOURCE_MESSAGES)
    parser.add_argument("--source-mapping", type=Path, default=SOURCE_MAPPING)
    parser.add_argument("--output-dir", type=Path, default=DATA)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--index", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build(
        source_messages=args.source_messages.resolve(),
        source_mapping=args.source_mapping.resolve(),
        output_dir=args.output_dir.resolve(),
        manifest_path=args.manifest.resolve() if args.manifest else None,
        index_path=args.index.resolve() if args.index else None,
    )
    print(
        canonical_json(
            {
                "n10": manifest["n10"]["row_count"],
                "m10": manifest["m10"]["row_count"],
                "c10": manifest["c10"]["row_count"],
                "n10_sha256": manifest["n10"]["file_sha256"],
                "m10_sha256": manifest["m10"]["file_sha256"],
                "families": [item["family_key"] for item in manifest["repetition_families"]["families"]],
                "delta_n10_rows": manifest["goal095"]["user_turn_delta_rows"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
