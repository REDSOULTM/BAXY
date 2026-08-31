from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.freeze_goal10_corpus import (
    C10_NAME,
    FLOOR_C10_CHAINS,
    FLOOR_M10_ROWS,
    FLOOR_M10_UNIQUE_TEXTS,
    FLOOR_N10_ROWS,
    FLOOR_N10_UNIQUE_TEXTS,
    INDEX_NAME,
    M10_NAME,
    MANIFEST_NAME,
    N10_NAME,
    OWNER_GOALS,
    PRIVATE_PAYLOAD_KEYS,
    SOURCE_MAPPING,
    SOURCE_MESSAGES,
    assign_owner_goal,
    build,
    choose_repetition_families,
    family_key,
    is_compound,
    public_index_row,
    required_environment,
    select_c10,
    select_m10,
    select_n10,
    security_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
PUBLISHED_MANIFEST = ROOT / "tests" / "data" / MANIFEST_NAME
PUBLISHED_INDEX = ROOT / "tests" / "data" / INDEX_NAME


def _row(
    *,
    message_id: str,
    text: str,
    operations: list[str] | None = None,
    message_class: str = "user_mission",
    origin: str = "observed_user",
    source: str = "probando_gemma4/session.jsonl",
    possible_chain: bool | None = None,
    language: str = "es",
    acceptance_scope: str = "product_1_0",
    risk_class: str = "low_reversible",
    data_or_preferences: list[str] | None = None,
) -> dict:
    ops = list(operations or [])
    chain = bool(possible_chain) if possible_chain is not None else len(ops) > 1
    payload = text.encode("utf-8")
    return {
        "acceptance_scope": acceptance_scope,
        "class": message_class,
        "data_or_preferences": list(data_or_preferences or []),
        "language": language,
        "message_id": message_id,
        "operations": ops,
        "origin": origin,
        "possible_chain": chain,
        "risk": {"class": risk_class, "confirmation": "not_required"},
        "source": source,
        "text_literal": text,
        "text_sha256": hashlib.sha256(payload).hexdigest(),
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _mapping_for(rows: list[dict]) -> list[dict]:
    return [{"message_id": row["message_id"]} for row in rows]


def _synthetic_corpus() -> list[dict]:
    return [
        _row(message_id="msg_hi", text="hola", operations=[], message_class="conversation_question"),
        _row(message_id="msg_hi2", text="hola", operations=[], message_class="conversation_question"),
        _row(message_id="msg_time", text="qué hora es", operations=[], message_class="conversation_question"),
        _row(message_id="msg_news", text="busca noticias de hoy en internet", operations=[], message_class="conversation_question"),
        _row(message_id="msg_no", text="no subas el volumen", operations=[], message_class="no_action_constraint", risk_class="no_effect"),
        _row(message_id="msg_play", text="pon música", operations=["media.play"]),
        _row(message_id="msg_play2", text="pon música", operations=["media.play"]),
        _row(message_id="msg_vol", text="sube el volumen", operations=["audio.volume"]),
        _row(message_id="msg_status", text="cómo está la ram", operations=["system.status"]),
        _row(message_id="msg_bright", text="baja el brillo", operations=["system.settings"]),
        _row(
            message_id="msg_stream",
            text="pon la serie en netflix",
            operations=["streaming.navigate"],
            data_or_preferences=["account"],
        ),
        _row(
            message_id="msg_send",
            text="manda un mensaje por whatsapp",
            operations=["message.send"],
            risk_class="external_communication",
            data_or_preferences=["account"],
        ),
        _row(
            message_id="msg_chain",
            text="abre steam y pon música",
            operations=["app.open", "media.play"],
            possible_chain=True,
        ),
        _row(
            message_id="msg_codex",
            text="fix the test",
            operations=[],
            message_class="engineering_instruction",
            origin="observed_user",
            source="codex/threads/abc.jsonl",
        ),
        _row(
            message_id="msg_doc",
            text="Baxy, pon música",
            operations=["media.play"],
            origin="document_example",
            source="baxy/prompt.md",
        ),
    ]


def test_selection_keeps_observed_user_and_drops_codex() -> None:
    rows = _synthetic_corpus()
    n10 = select_n10(rows)
    ids = [row["message_id"] for row in n10]
    assert "msg_codex" not in ids
    assert "msg_doc" not in ids
    assert "msg_hi" in ids
    assert "msg_chain" in ids
    m10 = select_m10(n10)
    c10 = select_c10(n10)
    assert {row["message_id"] for row in c10} == {"msg_chain"}
    assert {row["message_id"] for row in c10} <= {row["message_id"] for row in m10}
    assert {row["message_id"] for row in m10} <= {row["message_id"] for row in n10}


def test_owner_assignment_is_semantic_not_language_label() -> None:
    other_play = _row(
        message_id="msg_other_play",
        text="pon spotify",
        operations=["media.play"],
        language="other",
    )
    assert assign_owner_goal(other_play) == "10.12"
    assert assign_owner_goal(_row(message_id="a", text="hola", operations=[], message_class="conversation_question")) == "10.7"
    assert assign_owner_goal(_row(message_id="b", text="qué hora es", operations=[], message_class="conversation_question")) == "10.8"
    assert assign_owner_goal(
        _row(
            message_id="c",
            text="busca noticias en internet",
            operations=[],
            message_class="conversation_question",
        )
    ) == "10.9"
    assert assign_owner_goal(
        _row(
            message_id="d",
            text="abre chrome y pon youtube",
            operations=["app.open", "streaming.navigate"],
        )
    ) == "10.16"
    assert assign_owner_goal(
        _row(
            message_id="e",
            text="no cierres spotify",
            operations=[],
            message_class="no_action_constraint",
        )
    ) == "10.7"


def test_environment_and_security_fixture_stamps() -> None:
    stream = _row(
        message_id="s",
        text="pon la serie",
        operations=["streaming.navigate"],
        data_or_preferences=["account"],
    )
    env = required_environment(stream)
    assert "streaming_service" in env
    assert "requested_title" in env
    assert "signed_in_account" in env
    send = _row(
        message_id="m",
        text="manda un mensaje",
        operations=["message.send"],
        risk_class="external_communication",
    )
    assert security_fixture(send) == "test_recipient_or_draft_fixture"
    talk = _row(message_id="t", text="hola", operations=[], message_class="conversation_question")
    assert required_environment(talk) == []
    assert security_fixture(talk) is None


def test_repetition_families_follow_frequency_and_partition_coverage() -> None:
    rows = []
    for i in range(20):
        rows.append(
            _row(
                message_id=f"c{i}",
                text="hola",
                operations=[],
                message_class="conversation_question",
            )
        )
    for i in range(8):
        rows.append(_row(message_id=f"p{i}", text="pon música", operations=["media.play"]))
    for i in range(6):
        rows.append(_row(message_id=f"v{i}", text="volumen", operations=["audio.volume"]))
    for i in range(5):
        rows.append(_row(message_id=f"u{i}", text="mute", operations=["audio.mute"]))
    for i in range(4):
        rows.append(_row(message_id=f"s{i}", text="ram", operations=["system.status"]))
    for i in range(3):
        rows.append(_row(message_id=f"b{i}", text="brillo", operations=["system.settings"]))
    rows.append(
        _row(
            message_id="chain",
            text="abre steam y pon música",
            operations=["app.open", "media.play"],
        )
    )
    families = choose_repetition_families(rows)
    names = [item["family_key"] for item in families]
    assert names[0] == "conversation"
    assert "media.play" in names
    assert "audio.volume" in names
    assert "audio.mute" not in names
    assert "compound:app.open+media.play" not in names
    assert len({item["owner_goal"] for item in families}) == 5


def test_public_index_has_no_user_text_payload() -> None:
    row = _row(message_id="msg_play", text="pon música privada", operations=["media.play"])
    row["owner_goal"] = assign_owner_goal(row)
    row["family_key"] = family_key(row)
    row["in_n10"] = True
    row["in_m10"] = True
    row["in_c10"] = False
    row["required_environment"] = required_environment(row)
    row["security_fixture"] = security_fixture(row)
    row["language_scope"] = "product_1_0"
    row["source_family"] = "probando_gemma4"
    row["risk_class"] = "low_reversible"
    row["repetition_family"] = "media.play"
    published = public_index_row(row)
    assert PRIVATE_PAYLOAD_KEYS.isdisjoint(published)
    dumped = json.dumps(published)
    assert "pon música privada" not in dumped


def test_two_isolated_rebuilds_are_byte_identical(tmp_path: Path) -> None:
    rows = [row for row in _synthetic_corpus() if row["origin"] == "observed_user"]
    source = tmp_path / "messages.jsonl"
    mapping = tmp_path / "mapping.jsonl"
    _write_jsonl(source, rows)
    _write_jsonl(mapping, _mapping_for(rows))
    first_dir = tmp_path / "a"
    second_dir = tmp_path / "b"
    first = build(
        source_messages=source,
        source_mapping=mapping,
        output_dir=first_dir,
        require_known_floors=False,
    )
    second = build(
        source_messages=source,
        source_mapping=mapping,
        output_dir=second_dir,
        require_known_floors=False,
    )
    assert (first_dir / N10_NAME).read_bytes() == (second_dir / N10_NAME).read_bytes()
    assert (first_dir / M10_NAME).read_bytes() == (second_dir / M10_NAME).read_bytes()
    assert (first_dir / C10_NAME).read_bytes() == (second_dir / C10_NAME).read_bytes()
    assert first["n10"]["file_sha256"] == second["n10"]["file_sha256"]
    assert first["m10"]["file_sha256"] == second["m10"]["file_sha256"]
    index_rows = [
        json.loads(line)
        for line in (first_dir / INDEX_NAME).read_text(encoding="utf-8").splitlines()
        if line
    ]
    ids = [row["message_id"] for row in index_rows]
    assert len(ids) == len(set(ids))
    assert {row["owner_goal"] for row in index_rows} <= set(OWNER_GOALS)
    assert all(row["owner_goal"] in OWNER_GOALS for row in index_rows)
    assert any(row["in_c10"] for row in index_rows)
    assert all(not (row["in_c10"] and row["owner_goal"] != "10.16") for row in index_rows)
    env_row = next(row for row in index_rows if row["message_id"] == "msg_stream")
    assert env_row["required_environment"]
    assert "codex" not in {row["source_family"] for row in index_rows}
    dumped = json.dumps(first)
    for key in PRIVATE_PAYLOAD_KEYS:
        assert f'"{key}"' not in dumped


def test_private_generated_jsonl_is_gitignored_and_notice_exists() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    notice = (ROOT / "tests" / "data" / "GOAL10_CORPUS_NOTICE.md").read_text(
        encoding="utf-8"
    )
    assert f"/tests/data/{N10_NAME}" in ignored
    assert f"/tests/data/{M10_NAME}" in ignored
    assert f"/tests/data/{C10_NAME}" in ignored
    assert N10_NAME in notice
    assert M10_NAME in notice
    assert "not versioned" in notice.lower() or "no se versionan" in notice.lower()


def test_freeze_module_does_not_reparse_residual_evidence() -> None:
    source = (ROOT / "scripts" / "freeze_goal10_corpus.py").read_text(encoding="utf-8")
    assert "residual_evidence" in source
    assert "not_reparsed" in source
    assert "goal095_evidence_parse" not in source
    assert "artifacts/goal095/extract" not in source


def test_live_authorities_two_rebuilds_preserve_floors_and_match_publication(
    tmp_path: Path,
) -> None:
    first_dir = tmp_path / "a"
    second_dir = tmp_path / "b"
    first = build(output_dir=first_dir)
    second = build(output_dir=second_dir)
    assert (first_dir / N10_NAME).read_bytes() == (second_dir / N10_NAME).read_bytes()
    assert (first_dir / M10_NAME).read_bytes() == (second_dir / M10_NAME).read_bytes()
    assert first["n10"]["file_sha256"] == second["n10"]["file_sha256"]
    assert first["m10"]["file_sha256"] == second["m10"]["file_sha256"]
    assert first["floors"]["floor_n10_rows"] == FLOOR_N10_ROWS
    assert first["floors"]["floor_n10_unique_texts"] == FLOOR_N10_UNIQUE_TEXTS
    assert first["floors"]["floor_m10_rows"] == FLOOR_M10_ROWS
    assert first["floors"]["floor_m10_unique_texts"] == FLOOR_M10_UNIQUE_TEXTS
    assert first["floors"]["floor_c10_chains"] == FLOOR_C10_CHAINS
    assert first["n10"]["row_count"] >= FLOOR_N10_ROWS
    assert first["m10"]["row_count"] >= FLOOR_M10_ROWS
    assert first["c10"]["row_count"] >= FLOOR_C10_CHAINS
    assert first["c10"]["row_count"] <= first["m10"]["row_count"]
    published = json.loads(PUBLISHED_MANIFEST.read_text(encoding="utf-8"))
    assert first["n10"]["file_sha256"] == published["n10"]["file_sha256"]
    assert first["m10"]["file_sha256"] == published["m10"]["file_sha256"]
    assert first["c10"]["file_sha256"] == published["c10"]["file_sha256"]
    assert published["repetition_families"]["count"] == 5
    occupancy = {
        goal: published["partitions"][goal]["row_count"] for goal in OWNER_GOALS
    }
    assert sum(occupancy.values()) == published["n10"]["row_count"]
    assert all(count >= 0 for count in occupancy.values())
    index_rows = [
        json.loads(line)
        for line in PUBLISHED_INDEX.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert len(index_rows) == published["n10"]["row_count"]
    owners = [row["owner_goal"] for row in index_rows]
    assert len(owners) == len({row["message_id"] for row in index_rows})
    assert set(owners) <= set(OWNER_GOALS)
    assert all(PRIVATE_PAYLOAD_KEYS.isdisjoint(row) for row in index_rows)
    raw_index = PUBLISHED_INDEX.read_text(encoding="utf-8")
    assert "text_literal" not in raw_index
    assert "c:\\users\\" not in raw_index.casefold()


def test_live_selection_excludes_codex_and_keeps_mapping() -> None:
    rows = []
    with SOURCE_MESSAGES.open("rb") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            rows.append(json.loads(raw))
    n10 = select_n10(rows)
    assert all(not str(row.get("source") or "").startswith("codex/") for row in n10)
    assert all(row.get("origin") == "observed_user" for row in n10)
    assert len(n10) >= FLOOR_N10_ROWS
    mapping_ids = set()
    with SOURCE_MAPPING.open("rb") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            mapping_ids.add(json.loads(raw)["message_id"])
    assert {row["message_id"] for row in n10} <= mapping_ids
    compounds = select_c10(n10)
    missions = select_m10(n10)
    assert {row["message_id"] for row in compounds} <= {row["message_id"] for row in missions}
    assert is_compound(compounds[0])
