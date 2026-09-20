from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_mtop_turn_evidence.py"
SOURCE_MAP = ROOT / "src" / "baxy_mind" / "data" / "mtop_turn_evidence_map.v1.json"
CATALOG = ROOT / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs"
TEST_SEAL = ROOT / "tests" / "data" / "mtop_test_seal.v1.json"

SPEC = importlib.util.spec_from_file_location("baxy_mtop_builder", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
mtop = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mtop
SPEC.loader.exec_module(mtop)


def _tsv(
    example_id: str,
    intent: str,
    utterance: str,
    *,
    language: str,
    slots: tuple[tuple[str, str], ...] = (),
    nested_intent: str | None = None,
) -> str:
    leaves = " ".join(f"[{slot} {value} ]" for slot, value in slots)
    if nested_intent is not None:
        leaves += f" [SL:TODO [{nested_intent} ] ]"
    tree = f"[{intent} {leaves} ]"
    flat = ",".join(
        f"0:{len(value.encode('utf-8'))}:{slot}" for slot, value in slots
    )
    columns = [
        example_id,
        intent,
        flat,
        utterance,
        "fixture",
        f"{language}_XX",
        tree,
        json.dumps({"tokens": [], "tokenSpans": []}, separators=(",", ":")),
    ]
    return "\t".join(columns) + "\n"


def _fixture_development(root: Path) -> None:
    for language in ("en", "es"):
        (root / language).mkdir(parents=True)
    (root / "en" / "train.txt").write_text(
        "".join(
            [
                _tsv(
                    "en-alarm-ok",
                    "IN:CREATE_ALARM",
                    "wake me tomorrow",
                    language="en",
                    slots=(("SL:DATE_TIME", "tomorrow"),),
                ),
                _tsv(
                    "en-alarm-period",
                    "IN:CREATE_ALARM",
                    "wake me every week",
                    language="en",
                    slots=(
                        ("SL:DATE_TIME", "tomorrow"),
                        ("SL:PERIOD", "weekly"),
                    ),
                ),
                _tsv(
                    "en-call",
                    "IN:CREATE_CALL",
                    "call somebody",
                    language="en",
                    slots=(("SL:CONTACT", "somebody"),),
                ),
                _tsv(
                    "en-help",
                    "IN:HELP_REMINDER",
                    "how do reminders work",
                    language="en",
                ),
            ]
        ),
        encoding="utf-8",
    )
    (root / "en" / "eval.txt").write_text(
        "".join(
            [
                _tsv(
                    "en-weather",
                    "IN:GET_WEATHER",
                    "weather tomorrow",
                    language="en",
                    slots=(("SL:DATE_TIME", "tomorrow"),),
                ),
                _tsv(
                    "en-alarm-missing-time",
                    "IN:CREATE_ALARM",
                    "wake me up",
                    language="en",
                ),
            ]
        ),
        encoding="utf-8",
    )
    (root / "es" / "train.txt").write_text(
        _tsv(
            "es-message",
            "IN:SEND_MESSAGE",
            "manda el contenido",
            language="es",
            slots=(
                ("SL:CONTENT_EXACT", "contenido"),
                ("SL:RECIPIENT", "destino"),
            ),
        ),
        encoding="utf-8",
    )
    (root / "es" / "eval.txt").write_text(
        _tsv(
            "es-reminder-nested",
            "IN:CREATE_REMINDER",
            "recuerdame una llamada",
            language="es",
            slots=(("SL:DATE_TIME", "mañana"),),
            nested_intent="IN:CREATE_CALL",
        ),
        encoding="utf-8",
    )
    # A development build must not even need this member to be valid text.
    (root / "en" / "test.txt").write_bytes(b"\xffTEST_SENTINEL_MUST_NOT_LEAK\n")
    (root / "es" / "test.txt").write_bytes(b"\xfeOTRO_TEST_SENTINEL\n")


def _write_fixture_map(
    path: Path,
    archive_hash: str,
    *,
    development_root: Path | None = None,
) -> None:
    mapping = deepcopy(json.loads(SOURCE_MAP.read_text(encoding="utf-8")))
    mapping["source"]["archive_sha256"] = archive_hash
    if development_root is not None:
        identities: dict[str, dict[str, int | str]] = {}
        for member in ("en/train.txt", "en/eval.txt", "es/train.txt", "es/eval.txt"):
            source = development_root / member
            identities[member] = {
                "sha256": mtop._sha256(source),
                "bytes": source.stat().st_size,
                "rows": sum(
                    bool(line.strip())
                    for line in source.read_bytes().splitlines()
                ),
            }
        mapping["source"]["development_members"] = identities
    path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_locked_preregistration(
    path: Path,
    *,
    archive: Path,
    source_map: Path,
    seal_path: Path,
    run_id: str,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": mtop.PREREGISTRATION_SCHEMA,
                "state": "locked",
                "run_id": run_id,
                "test_seal_sha256": mtop._sha256(seal_path),
                "source_map_sha256": mtop._sha256(source_map),
                "archive_sha256": mtop._sha256(archive),
                "protocol": {
                    "architecture_frozen": True,
                    "single_final_evaluation": True,
                    "test_content_unseen_when_locked": True,
                    "test_rows_used_for_training": False,
                    "gate_report_contains_text": False,
                    "metrics": ["mode_accuracy"],
                    "absolute_floors": {"mode_accuracy": 0.8},
                    "absolute_ceilings": {},
                    "maximum_recoveries": 0,
                    "frozen_artifacts": {
                        "builder": {
                            "repo_path": SCRIPT.relative_to(ROOT).as_posix(),
                            "sha256": mtop._sha256(SCRIPT),
                        },
                        "catalog": {
                            "repo_path": CATALOG.relative_to(ROOT).as_posix(),
                            "sha256": mtop._sha256(CATALOG),
                        },
                        "unit_test": {
                            "repo_path": (
                                Path(__file__).resolve()
                                .relative_to(ROOT)
                                .as_posix()
                            ),
                            "sha256": mtop._sha256(Path(__file__).resolve()),
                        },
                    },
                    "sample_protocol": {
                        "population": "all_synthetic_rows",
                        "grouping": "mission_id",
                        "seed": 1,
                    },
                    "report_repo_path": (
                        "artifacts/product/synthetic-mtop-gate.json"
                    ),
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_development_is_deterministic_and_does_not_read_test(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    _fixture_development(dataset)
    output = tmp_path / "development.jsonl"
    manifest = tmp_path / "manifest.json"
    source_map = tmp_path / "map.json"
    _write_fixture_map(source_map, "0" * 64, development_root=dataset)

    first = mtop.build_development(
        dataset,
        source_map,
        CATALOG,
        output,
        manifest,
        None,
    )
    first_output = output.read_bytes()
    first_manifest = manifest.read_bytes()
    second = mtop.build_development(
        dataset,
        source_map,
        CATALOG,
        output,
        manifest,
        None,
    )

    assert first == second
    assert first_output == output.read_bytes()
    assert first_manifest == manifest.read_bytes()
    assert first["constraints"]["test_content_read"] is False
    assert first["counts"]["dispositions"] == {
        "candidate": 3,
        "candidate_missing_information": 1,
        "conversation_no_effect": 1,
        "ood_no_effect": 3,
    }
    assert b"TEST_SENTINEL_MUST_NOT_LEAK" not in first_output
    rows = [json.loads(line) for line in first_output.splitlines()]
    assert all(row["projection"]["execution_authority"] is False for row in rows)
    assert any(
        row["projection"]["reason"] == "contract_structure_mismatch"
        for row in rows
    )
    assert any(
        row["projection"]["reason"] == "mapped_unsupported_intent"
        for row in rows
    )
    missing = next(
        row
        for row in rows
        if row["projection"]["disposition"] == "candidate_missing_information"
    )
    assert missing["projection"]["expected_turn"] == "clarify"
    assert (
        missing["projection"]["grounding_status"]
        == "missing_required_information"
    )
    assert missing["projection"]["missing_required_slots"] == ["SL:DATE_TIME"]
    assert missing["projection"]["execution_authority"] is False


def test_development_rejects_a_member_changed_after_provenance_freeze(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "dataset"
    _fixture_development(dataset)
    source_map = tmp_path / "map.json"
    _write_fixture_map(source_map, "0" * 64, development_root=dataset)
    with (dataset / "en" / "train.txt").open("a", encoding="utf-8") as handle:
        handle.write(
            _tsv(
                "mutated",
                "IN:GET_WEATHER",
                "a row added after the freeze",
                language="en",
            )
        )

    with pytest.raises(ValueError, match="no coincide con MTOP oficial"):
        mtop.build_development(
            dataset,
            source_map,
            CATALOG,
            tmp_path / "development.jsonl",
            tmp_path / "manifest.json",
            None,
        )


def test_map_cannot_expand_baxy_capabilities() -> None:
    mapping = mtop.load_source_map(SOURCE_MAP, CATALOG)
    public_operations = mtop._public_catalog_operations(CATALOG)
    mapped_operations = {
        operation
        for entry in mapping["intents"].values()
        for variant in entry["variants"]
        for operation in variant["operations"]
    }

    # 169 -> 190: the 21 public operations sealed in C03 (2026-09-12 … 2026-09-20; plan post-goal
    # 2026-09-20, Fase 1). The catalogue is still the authenticated one, only larger.
    # 190 -> 193: weather.current, web.news.headlines y package.uninstall (auditoría semántica REOPEN1993, grupos W, N y G).
    assert len(public_operations) == 193
    assert mapped_operations <= public_operations
    assert mapping["policy"]["execution_authority"] is False
    assert set(mapping["intents"]).isdisjoint(mapping["ood_intents"])
    assert all(
        variant["allow_nested_intents"] is False
        for entry in mapping["intents"].values()
        for variant in entry["variants"]
    )


def test_official_development_manifest_is_complete_and_portable() -> None:
    manifest = json.loads(
        (ROOT / "artifacts" / "product" / "mtop_development_manifest.json")
        .read_text(encoding="utf-8")
    )
    serialized = json.dumps(manifest, ensure_ascii=False)

    assert manifest["output"] == {
        "file_name": "mtop_development.v1.jsonl",
        "sha256": "ed1871262bdb78a53e219ac6ebd7b995879c60eba29ec5d9203217480a142802",
        "bytes": 24_680_426,
        "rows": 29_976,
    }
    assert manifest["counts"]["source_rows"] == 30_363
    assert manifest["counts"]["accepted_rows"] == 29_976
    assert manifest["counts"]["observed_intents"] == 113
    assert manifest["counts"]["dispositions"] == {
        "candidate": 12_758,
        "candidate_missing_information": 471,
        "conversation_no_effect": 8,
        "ood_no_effect": 16_739,
    }
    assert manifest["counts"]["decontamination"] == {
        "ambiguous_exact_text_groups_removed": 4,
        "ambiguous_exact_text_rows_removed": 13,
        "cross_split_exact_text_groups": 63,
        "cross_split_train_rows_removed": 81,
        "same_split_exact_duplicates_removed": 293,
    }
    assert manifest["constraints"]["mission_split_overlap"] == 0
    assert manifest["constraints"]["normalized_text_split_overlap"] == 0
    assert manifest["constraints"]["test_content_read"] is False
    assert "C:\\" not in serialized
    assert "D:\\" not in serialized


def test_test_seal_is_deterministic_and_byte_only(tmp_path: Path) -> None:
    archive = tmp_path / "mtop.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("mtop/en/test.txt", b"\xffSECRET_EN\tIN:HIDDEN\n")
        bundle.writestr("mtop/es/test.txt", b"\xfeSECRET_ES\tIN:OCULTO\n")
    source_map = tmp_path / "map.json"
    _write_fixture_map(source_map, mtop._sha256(archive))

    first = mtop.build_test_seal(archive, source_map, CATALOG)
    second = mtop.build_test_seal(archive, source_map, CATALOG)
    serialized = json.dumps(first, sort_keys=True)

    assert first == second
    assert first["rows"] == 2
    assert first["protocol"]["content_decoded"] is False
    assert first["protocol"]["columns_inspected"] is False
    assert "SECRET_EN" not in serialized
    assert "IN:HIDDEN" not in serialized
    assert ".decode(" not in inspect.getsource(mtop._opaque_test_member_identity)


def test_official_test_seal_contains_only_opaque_identity() -> None:
    seal = json.loads(TEST_SEAL.read_text(encoding="utf-8"))
    forbidden_keys = {"text", "utterance", "intent", "slots", "labels", "domain"}

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {
                child_key
                for child in value.values()
                for child_key in keys(child)
            }
        if isinstance(value, list):
            return {
                child_key
                for child in value
                for child_key in keys(child)
            }
        return set()

    assert seal["rows"] == 7_384
    assert seal["members"]["en"]["rows"] == 4_386
    assert seal["members"]["es"]["rows"] == 2_998
    assert seal["protocol"]["content_decoded"] is False
    assert seal["protocol"]["record_id_algorithm"] == (
        "sha256(domain || NUL || locale || NUL || ordinal || NUL || "
        "sha256(raw_line_without_eol))"
    )
    assert keys(seal).isdisjoint(forbidden_keys)


def test_materialization_rejects_unlocked_protocol_before_zip_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = tmp_path / "mtop.zip"
    archive.write_bytes(b"not-opened-as-zip")
    preregistration = tmp_path / "preregistration.json"
    preregistration.write_text(
        json.dumps(
            {
                "schema": mtop.PREREGISTRATION_SCHEMA,
                "state": "draft",
            }
        ),
        encoding="utf-8",
    )

    def forbidden_zip_access(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("el ZIP no debe abrirse antes de autorizar el test")

    monkeypatch.setattr(mtop.zipfile, "ZipFile", forbidden_zip_access)
    with pytest.raises(ValueError, match="prerregistro"):
        mtop.materialize_test(
            archive,
            SOURCE_MAP,
            CATALOG,
            TEST_SEAL,
            preregistration,
            tmp_path / "test.jsonl",
            tmp_path / "receipt.json",
        )
    assert not (tmp_path / "test.jsonl").exists()
    assert not (tmp_path / "receipt.json").exists()


def test_synthetic_test_materialization_requires_seal_and_is_one_shot(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "mtop.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(
            "mtop/en/test.txt",
            _tsv(
                "parallel-test-mission",
                "IN:GET_WEATHER",
                "weather now",
                language="en",
            ).encode("utf-8"),
        )
        bundle.writestr(
            "mtop/es/test.txt",
            _tsv(
                "parallel-test-mission",
                "IN:CREATE_CALL",
                "llama a alguien",
                language="es",
                slots=(("SL:CONTACT", "alguien"),),
            ).encode("utf-8"),
        )
    source_map = tmp_path / "map.json"
    _write_fixture_map(source_map, mtop._sha256(archive))
    seal_path = tmp_path / "seal.json"
    mtop._write_json_atomic(
        seal_path,
        mtop.build_test_seal(archive, source_map, CATALOG),
    )
    preregistration = tmp_path / "preregistration.json"
    _write_locked_preregistration(
        preregistration,
        archive=archive,
        source_map=source_map,
        seal_path=seal_path,
        run_id="synthetic-unit-test",
    )
    output = tmp_path / "test.jsonl"
    receipt_path = tmp_path / "receipt.json"
    usage_ledger = tmp_path / "one-shot-ledger.json"

    receipt = mtop.materialize_test(
        archive,
        source_map,
        CATALOG,
        seal_path,
        preregistration,
        output,
        receipt_path,
        usage_ledger,
    )
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

    assert receipt["output"]["rows"] == 2
    assert receipt["execution_authority"] is False
    assert {row["projection"]["disposition"] for row in rows} == {
        "candidate",
        "ood_no_effect",
    }
    assert len({row["mission_id"] for row in rows}) == 1
    assert all(row["projection"]["execution_authority"] is False for row in rows)
    with pytest.raises(FileExistsError, match="reservado o usado"):
        mtop.materialize_test(
            archive,
            source_map,
            CATALOG,
            seal_path,
            preregistration,
            tmp_path / "alternate-test.jsonl",
            tmp_path / "alternate-receipt.json",
            usage_ledger,
        )
    assert not (tmp_path / "alternate-test.jsonl").exists()
    assert not (tmp_path / "alternate-receipt.json").exists()


def test_integrated_gate_keeps_rows_in_memory_and_blocks_alternate_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = tmp_path / "mtop.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(
            "mtop/en/test.txt",
            _tsv(
                "shared-evaluation-mission",
                "IN:GET_WEATHER",
                "private synthetic weather wording",
                language="en",
            ).encode("utf-8"),
        )
        bundle.writestr(
            "mtop/es/test.txt",
            _tsv(
                "shared-evaluation-mission",
                "IN:CREATE_CALL",
                "frase sintetica privada",
                language="es",
                slots=(("SL:CONTACT", "alguien"),),
            ).encode("utf-8"),
        )
    source_map = tmp_path / "map.json"
    _write_fixture_map(source_map, mtop._sha256(archive))
    seal_path = tmp_path / "seal.json"
    mtop._write_json_atomic(
        seal_path,
        mtop.build_test_seal(archive, source_map, CATALOG),
    )
    preregistration = tmp_path / "preregistration.json"
    _write_locked_preregistration(
        preregistration,
        archive=archive,
        source_map=source_map,
        seal_path=seal_path,
        run_id="synthetic-integrated-gate",
    )
    report_path = tmp_path / "aggregate.json"
    ledger_directory = tmp_path / "ledger"
    observed: dict[str, object] = {}

    def evaluate(records: list[dict[str, object]]) -> dict[str, object]:
        observed["rows"] = len(records)
        observed["parallel_groups"] = len(
            {str(record["mission_id"]) for record in records}
        )
        return {
            "schema": "baxy.synthetic-mtop-gate.v1",
            "authority": "read_only_no_operation_dispatch",
            "contains_text": False,
            "execution_authority": False,
            "evaluated_rows": len(records),
            "recoveries": 0,
            "metrics": {"mode_accuracy": 1.0},
        }

    report = mtop.evaluate_test_once(
        archive,
        source_map,
        CATALOG,
        seal_path,
        preregistration,
        evaluate,
        synthetic_report_path=report_path,
        synthetic_ledger_directory=ledger_directory,
    )

    assert observed == {"rows": 2, "parallel_groups": 1}
    assert report["status"] == "passed"
    assert report["preregistered_checks"] == {
        "maximum_recoveries": True,
        "mode_accuracy_floor": True,
    }
    serialized = report_path.read_text(encoding="utf-8")
    assert "private synthetic weather wording" not in serialized
    assert "frase sintetica privada" not in serialized
    assert not list(tmp_path.rglob("*.jsonl"))
    assert json.loads(
        (ledger_directory / "claim.json").read_text(encoding="utf-8")
    )["state"] == "claimed"
    assert json.loads(
        (ledger_directory / "receipt.json").read_text(encoding="utf-8")
    )["schema"] == mtop.EVALUATION_RECEIPT_SCHEMA

    def forbidden_zip_access(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("el segundo intento no debe abrir test")

    monkeypatch.setattr(mtop.zipfile, "ZipFile", forbidden_zip_access)
    with pytest.raises(FileExistsError, match="reclamado o evaluado"):
        mtop.evaluate_test_once(
            archive,
            source_map,
            CATALOG,
            seal_path,
            preregistration,
            evaluate,
            synthetic_report_path=tmp_path / "alternate-aggregate.json",
            synthetic_ledger_directory=ledger_directory,
        )
    assert not (tmp_path / "alternate-aggregate.json").exists()


def test_integrated_gate_crash_burns_claim_without_persisting_rows(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "mtop.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(
            "mtop/en/test.txt",
            _tsv(
                "crash-mission",
                "IN:GET_WEATHER",
                "synthetic crash phrase",
                language="en",
            ).encode("utf-8"),
        )
        bundle.writestr("mtop/es/test.txt", b"")
    source_map = tmp_path / "map.json"
    _write_fixture_map(source_map, mtop._sha256(archive))
    seal_path = tmp_path / "seal.json"
    mtop._write_json_atomic(
        seal_path,
        mtop.build_test_seal(archive, source_map, CATALOG),
    )
    preregistration = tmp_path / "preregistration.json"
    _write_locked_preregistration(
        preregistration,
        archive=archive,
        source_map=source_map,
        seal_path=seal_path,
        run_id="synthetic-crash-gate",
    )
    ledger_directory = tmp_path / "ledger"

    def crash(_records: list[dict[str, object]]) -> object:
        raise RuntimeError("synthetic evaluator crash")

    with pytest.raises(RuntimeError, match="synthetic evaluator crash"):
        mtop.evaluate_test_once(
            archive,
            source_map,
            CATALOG,
            seal_path,
            preregistration,
            crash,
            synthetic_report_path=tmp_path / "aggregate.json",
            synthetic_ledger_directory=ledger_directory,
        )
    failure = json.loads(
        (ledger_directory / "failure.json").read_text(encoding="utf-8")
    )
    assert failure["state"] == "failed"
    assert failure["failure_type"] == "RuntimeError"
    assert "synthetic evaluator crash" not in json.dumps(failure)
    assert not (tmp_path / "aggregate.json").exists()
    assert not list(tmp_path.rglob("*.jsonl"))

    with pytest.raises(FileExistsError, match="reclamado o evaluado"):
        mtop.evaluate_test_once(
            archive,
            source_map,
            CATALOG,
            seal_path,
            preregistration,
            crash,
            synthetic_report_path=tmp_path / "second.json",
            synthetic_ledger_directory=ledger_directory,
        )
