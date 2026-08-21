from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "run_turn_policy_gate.py"
SPEC = importlib.util.spec_from_file_location("run_turn_policy_gate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def row(index: int, mode: str, family: str, dataset: str, locale: str) -> dict:
    return {
        "schema": "baxy.turn-evidence-record.v1",
        "text": f"message {index} {mode} {family} {dataset} {locale}",
        "mode": mode,
        "families": [] if family == "none" else [family],
        "mission_id": f"mission-{index}",
        "source_id": f"fixture:{locale}:{index}",
        "split": "test",
        "provenance": {"dataset": dataset, "license": "fixture"},
    }


def write_selection_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, dict, list[dict]]:
    validation = row(9000, "conversation", "none", "fixture", "es-ES")
    validation["split"] = "validation"
    test_rows = [
        row(
            index,
            "conversation" if index % 2 else "action",
            "none" if index % 2 else "app",
            "fixture",
            "es-ES",
        )
        for index in range(6)
    ]
    all_rows = [validation, *test_rows]
    holdout = tmp_path / "holdout.jsonl"
    holdout.write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
            for item in all_rows
        ),
        encoding="utf-8",
    )
    runtime = tmp_path / "runtime.jsonl"
    runtime.write_text("", encoding="utf-8")
    final_ids = sorted(str(item["source_id"]) for item in test_rows[:3])
    payload = {
        "schema": gate.FINAL_SEAL_SCHEMA,
        "rule_declaration_sha256": (
            gate.PRODUCTION_RULE_DECLARATION_SHA256
        ),
        "holdout": {"test_rows": len(test_rows)},
        "final": {
            "rows": len(final_ids),
            "source_ids": final_ids,
            "source_ids_sha256": gate.list_sha256(final_ids),
        },
        "predecessor": {
            "final_source_ids_sha256": "9" * 64,
        },
        "policy_calibration": {
            "final_source_ids_sha256": "a" * 64,
        },
        "failed_attempt": {
            "report_sha256": "b" * 64,
            "journal_sha256": "c" * 64,
        },
        "evaluation": {"performed_by_generator": False},
        "contains_text_or_labels": False,
    }
    seal = tmp_path / "seal-v4.json"
    seal.write_text(json.dumps(payload), encoding="utf-8")
    return holdout, runtime, seal, payload, all_rows


def result(
    kind: str,
    *,
    operation: str | None = None,
    reply: str = "",
    question: str = "",
) -> dict:
    return {
        "kind": kind,
        "operation": operation,
        "reply": reply,
        "question": question,
        "latency_seconds": 0.1,
        "error": "",
    }


def report_args(tmp_path: Path, **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "arm": "both",
        "seed": gate.DEFAULT_SEED,
        "sample_size": gate.FULL_HOLDOUT_SAMPLE,
        "preflight": False,
        "preflight_holdout_sample": gate.PREFLIGHT_HOLDOUT_SAMPLE,
        "max_holdout": None,
        "max_contextual": None,
        "max_calls": None,
        "llm_endpoint": None,
        "noninferiority_margin": gate.DEFAULT_NONINFERIORITY_MARGIN,
        "fresh": True,
        "holdout": tmp_path / "holdout.jsonl",
        "runtime_corpus": tmp_path / "runtime.jsonl",
        "gguf": tmp_path / "model.gguf",
        "llama_server": tmp_path / "llama-server.exe",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def expected_encoder_snapshot_identity() -> dict:
    return {
        "model": gate.ENCODER_MODEL_NAME,
        "revision": gate.ENCODER_MODEL_REVISION,
        "manifest_algorithm": gate.ENCODER_SNAPSHOT_MANIFEST_ALGORITHM,
        "manifest_sha256": gate.ENCODER_SNAPSHOT_MANIFEST_SHA256,
        "file_count": gate.ENCODER_SNAPSHOT_FILE_COUNT,
        "weights": {
            "path": "model.safetensors",
            "sha256": gate.ENCODER_WEIGHTS_SHA256,
        },
    }


def test_core_catalog_configuration_preserves_authenticated_entity_snapshots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    core = tmp_path / "baxy-core.exe"
    core.write_bytes(b"fixture")
    hello = {
        "type": "hello",
        "capabilities": [
            {
                "name": "app.open",
                "description": "Open one authenticated application.",
                "argumentsSchema": {"type": "object"},
                "risk": "low",
            }
        ],
        "applicationCatalog": {
            "version": 1,
            "verified": True,
            "complete": True,
            "names": ["Calculadora", "Bloc de notas"],
        },
        "gameCatalog": {
            "version": 1,
            "verified": True,
            "complete": True,
            "entries": [],
        },
    }

    class _Stream:
        def __init__(self, line: str = "") -> None:
            self._line = line

        def readline(self) -> str:
            return self._line

        def read(self) -> str:
            return ""

        def close(self) -> None:
            return None

    class _Process:
        def __init__(self) -> None:
            self.stdout = _Stream(json.dumps(hello))
            self.stderr = _Stream()
            self.stdin = _Stream()

        def wait(self, timeout: float) -> int:
            return 0

        def kill(self) -> None:
            return None

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(gate.subprocess, "Popen", lambda *args, **kwargs: _Process())

    configuration = gate.core_catalog_configuration(core)

    assert configuration["capabilities"][0]["name"] == "app.open"
    assert configuration["applicationCatalog"]["names"] == [
        "Calculadora",
        "Bloc de notas",
    ]
    assert configuration["gameCatalog"]["verified"] is True


def test_mind_source_hashes_bind_extracted_runtime_dependency_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert gate.MIND_RUNTIME_SOURCE_PATHS == (
        gate.SRC / "baxy_mind" / "__init__.py",
        gate.SRC / "baxy_mind" / "__main__.py",
        gate.SRC / "baxy_mind" / "catalog_operation_aliases.py",
        gate.SRC / "baxy_mind" / "corrector.py",
        gate.SRC / "baxy_mind" / "effect_intent.py",
        gate.SRC / "baxy_mind" / "family_classifier.py",
        gate.SRC / "baxy_mind" / "llm.py",
        gate.SRC / "baxy_mind" / "llm_transport.py",
        gate.SRC / "baxy_mind" / "phonetic_es.py",
        gate.SRC / "baxy_mind" / "planner.py",
        gate.SRC / "baxy_mind" / "process_lifecycle.py",
        gate.SRC / "baxy_mind" / "protocol.py",
        gate.SRC / "baxy_mind" / "router.py",
        gate.SRC / "baxy_mind" / "router_worker.py",
        gate.SRC / "baxy_mind" / "semantic_family_arbiter.py",
        gate.SRC / "baxy_mind" / "skill_registry.py",
        gate.SRC / "baxy_mind" / "time_budget.py",
        gate.SRC / "baxy_mind" / "turn_evidence.py",
        gate.SRC / "baxy_mind" / "turn_evidence_contracts.py",
        gate.SRC / "baxy_mind" / "data" / "family_classifier.v1.manifest.json",
        gate.SRC / "baxy_mind" / "data" / "family_classifier.v1.vocabulary.json.gz",
        gate.SRC / "baxy_mind" / "data" / "family_classifier.v1.weights.npz",
        gate.SRC / "baxy_mind" / "data" / "semantic_family_arbiter.v1.manifest.json",
        gate.SRC / "baxy_mind" / "data" / "semantic_family_arbiter.v1.weights.npz",
        gate.SRC / "baxy_mind" / "data" / "catalog_operation_aliases.v1.json",
    )

    stable_source = tmp_path / "llm.py"
    transport_source = tmp_path / "llm_transport.py"
    contracts_source = tmp_path / "turn_evidence_contracts.py"
    turn_probe = tmp_path / "run_turn_linear_probe_gate.py"
    stable_source.write_text("stable\n", encoding="utf-8")
    transport_source.write_text("transport-v1\n", encoding="utf-8")
    contracts_source.write_text("contracts-v1\n", encoding="utf-8")
    turn_probe.write_text("probe\n", encoding="utf-8")
    monkeypatch.setattr(
        gate,
        "MIND_RUNTIME_SOURCE_PATHS",
        (stable_source, transport_source, contracts_source),
    )

    before = gate.mind_source_hashes(turn_probe)
    before_fingerprint = hashlib.sha256(
        gate.canonical_json({"mind_sources": before})
    ).hexdigest()
    transport_source.write_text("transport-v2\n", encoding="utf-8")
    after_transport = gate.mind_source_hashes(turn_probe)
    after_transport_fingerprint = hashlib.sha256(
        gate.canonical_json({"mind_sources": after_transport})
    ).hexdigest()
    contracts_source.write_text("contracts-v2\n", encoding="utf-8")
    after_contracts = gate.mind_source_hashes(turn_probe)
    after_contracts_fingerprint = hashlib.sha256(
        gate.canonical_json({"mind_sources": after_contracts})
    ).hexdigest()

    assert set(before) == {
        "llm.py",
        "llm_transport.py",
        "turn_evidence_contracts.py",
        turn_probe.name,
    }
    assert before["llm.py"] == after_contracts["llm.py"]
    assert before[turn_probe.name] == after_contracts[turn_probe.name]
    assert (
        before["llm_transport.py"]
        != after_transport["llm_transport.py"]
    )
    assert (
        after_transport["turn_evidence_contracts.py"]
        != after_contracts["turn_evidence_contracts.py"]
    )
    assert before_fingerprint != after_transport_fingerprint
    assert after_transport_fingerprint != after_contracts_fingerprint


def build_test_report(
    tmp_path: Path,
    args: SimpleNamespace,
    specs: dict[str, dict],
    results: dict[str, dict[str, dict]],
    *,
    resumed: int = 0,
) -> dict:
    return gate.build_report(
        args=args,
        fingerprint="f" * 64,
        specs=specs,
        results=results,
        cleanliness={
            "selection_scope": "sealed_final_v4_only",
            "seal_schema": gate.FINAL_SEAL_SCHEMA,
            "blind_manifest_rebuilt": True,
        },
        corpus_hashes={
            "holdout": "a" * 64,
            "runtime": "b" * 64,
            "seal": "c" * 64,
            "predecessor_seal": "1" * 64,
            "policy_calibration_seal": "3" * 64,
            "ancestor_seal": "4" * 64,
            "failed_attempt_report": "5" * 64,
            "failed_attempt_journal": "6" * 64,
            "predecessor_failed_attempt_report": "7" * 64,
            "predecessor_failed_attempt_journal": "8" * 64,
            "policy": "d" * 64,
            "turn_probe": "e" * 64,
            "blind_seal_reset": "2" * 64,
            "predecessor_blind_seal_reset": "9" * 64,
            "policy_calibration_blind_seal_reset": "a" * 64,
            "gate_script": "f" * 64,
            "catalog": "0" * 64,
        },
        input_identities={
            "encoder_snapshot": expected_encoder_snapshot_identity(),
            **{
                name: {"path": name, "sha256": value * 64}
                for name, value in (
                    ("seal", "c"),
                    ("predecessor_seal", "1"),
                    ("policy_calibration_seal", "3"),
                    ("ancestor_seal", "4"),
                    ("failed_attempt_report", "5"),
                    ("failed_attempt_journal", "6"),
                    ("predecessor_failed_attempt_report", "7"),
                    ("predecessor_failed_attempt_journal", "8"),
                    ("policy", "d"),
                    ("turn_probe", "e"),
                    ("blind_seal_reset", "2"),
                    ("predecessor_blind_seal_reset", "9"),
                    ("policy_calibration_blind_seal_reset", "a"),
                    ("gate_script", "f"),
                )
            },
        },
        catalog_count=168,
        complete=True,
        journal_resumed_records=resumed,
    )


def test_allocate_stratified_quotas_is_exact_and_capacity_bounded() -> None:
    capacities = {
        ("action", "app"): 2,
        ("action", "web"): 20,
        ("conversation", "none"): 8,
    }
    quotas = gate.allocate_stratified_quotas(capacities, 17)

    assert sum(quotas.values()) == 17
    assert all(0 <= quotas[key] <= capacity for key, capacity in capacities.items())
    assert all(quotas[key] >= 1 for key in capacities)
    assert quotas[("action", "web")] > quotas[("action", "app")]


def test_hash_stratified_sample_is_reproducible_and_covers_every_stratum() -> None:
    rows = [
        *[row(i, "action", "app", "A", "es-ES") for i in range(20)],
        *[row(100 + i, "action", "web", "A", "en-US") for i in range(20)],
        *[
            row(200 + i, "conversation", "none", "B", "es-ES")
            for i in range(20)
        ],
    ]
    first = gate.stratified_hash_sample(rows, 15, "seed-one")
    second = gate.stratified_hash_sample(list(reversed(rows)), 15, "seed-one")
    other = gate.stratified_hash_sample(rows, 15, "seed-two")

    first_ids = [item["source_id"] for item in first]
    assert first_ids == [item["source_id"] for item in second]
    assert first_ids != [item["source_id"] for item in other]
    assert len(first_ids) == len(set(first_ids)) == 15
    assert {gate.stratum_key(item) for item in first} == {
        gate.stratum_key(item) for item in rows
    }


def test_normal_preflight_samples_only_its_validation_input(
    tmp_path: Path,
) -> None:
    validation_rows = [
        row(
            index,
            "conversation" if index % 2 else "action",
            "none" if index % 2 else "app",
            "fixture",
            "es-ES",
        )
        for index in range(32)
    ]
    for item in validation_rows:
        item["split"] = "validation"
    args = report_args(tmp_path, preflight=True)

    selected = gate.select_gate_specs(validation_rows, args)
    public = [case for case in selected if case["category"] == "public_holdout"]
    required = [case for case in selected if case["required"]]

    assert len(public) == gate.PREFLIGHT_HOLDOUT_SAMPLE
    assert all(case["case_id"].startswith("holdout:fixture:") for case in public)
    assert all(
        case["case_id"] in {
            "holdout:" + str(item["source_id"]) for item in validation_rows
        }
        for case in public
    )
    assert len(required) == sum(
        case["required"] for case in gate.contextual_cases()
    )


def test_preflight_max_holdout_zero_keeps_every_required_critical(
    tmp_path: Path,
) -> None:
    validation_rows = [
        row(index, "conversation", "none", "fixture", "es-ES")
        for index in range(16)
    ]
    for item in validation_rows:
        item["split"] = "validation"
    args = report_args(tmp_path, preflight=True, max_holdout=0)

    selected = gate.select_gate_specs(validation_rows, args)
    required_ids = {
        case["case_id"]
        for case in gate.contextual_cases()
        if case["required"]
    }

    assert {case["case_id"] for case in selected} == required_ids
    assert all(case["category"] != "public_holdout" for case in selected)


def test_load_clean_holdout_decodes_only_synthetic_final_v4_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holdout, runtime, seal, payload, all_rows = write_selection_fixture(
        tmp_path
    )
    monkeypatch.setattr(
        gate,
        "load_verified_final_seal",
        lambda *_args, **_kwargs: payload,
    )

    loaded, cleanliness = gate.load_clean_holdout(
        holdout,
        runtime,
        seal,
    )

    loaded_ids = [item["source_id"] for item in loaded]
    assert loaded_ids == payload["final"]["source_ids"]
    assert all(item["split"] == "test" for item in loaded)
    assert all_rows[0]["source_id"] not in loaded_ids
    assert cleanliness["selection_scope"] == "sealed_final_v4_only"
    assert cleanliness["holdout_file_rows"] == 7
    assert cleanliness["holdout_test_rows"] == 6
    assert cleanliness["holdout_validation_rows"] == 1
    assert cleanliness["sealed_final_rows"] == 3


def test_preflight_decodes_only_public_validation_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holdout, runtime, seal, payload, all_rows = write_selection_fixture(
        tmp_path
    )
    monkeypatch.setattr(
        gate,
        "load_verified_final_seal",
        lambda *_args, **_kwargs: payload,
    )

    loaded, cleanliness = gate.load_clean_holdout(
        holdout,
        runtime,
        seal,
        preflight=True,
    )

    assert [item["source_id"] for item in loaded] == [
        all_rows[0]["source_id"]
    ]
    assert all(item["split"] == "validation" for item in loaded)
    assert cleanliness["selection_scope"] == "public_validation_only"
    assert cleanliness["selected_split"] == "validation"
    assert cleanliness["sealed_final_source_ids_sha256"] == payload[
        "final"
    ]["source_ids_sha256"]


def test_validation_selection_does_not_decode_unselected_test_payload(
    tmp_path: Path,
) -> None:
    validation = json.dumps(
        row(9000, "conversation", "none", "fixture", "es-ES"),
        separators=(",", ":"),
    ).encode("utf-8")
    validation = validation.replace(b'"split":"test"', b'"split":"validation"')
    holdout = tmp_path / "opaque.jsonl"
    holdout.write_bytes(
        validation
        + b"\n"
        + b'{"split":"test","source_id":"sealed-test",'
        + b'"text":"\xff","mode":"\xfe","families":[]}\n'
    )

    loaded, scan = gate.load_selected_holdout_rows(
        holdout,
        split="validation",
    )

    assert len(loaded) == 1
    assert loaded[0]["split"] == "validation"
    assert scan == {"file_rows": 2, "test_rows": 1, "validation_rows": 1}


def test_canonical_v4_manifest_is_rebuilt_blindly() -> None:
    seal = gate.load_verified_final_seal(
        gate.DEFAULT_HOLDOUT,
        gate.DEFAULT_SEAL,
        gate.DEFAULT_PREDECESSOR_SEAL,
    )

    assert seal["schema"] == gate.FINAL_SEAL_SCHEMA
    assert (
        seal["rule_declaration_sha256"]
        == gate.PRODUCTION_RULE_DECLARATION_SHA256
    )
    assert seal["final"]["rows"] == 848
    assert seal["blind_reserve"]["rows"] == 184
    assert seal["audit"]["predecessor_chain_rebuilt"] is True
    assert seal["audit"]["failed_v3_selection_equals_predecessor_final"] is True
    assert seal["audit"]["failed_v3_selection_reserve_overlap_rows"] == 0
    assert seal["audit"]["final_predecessor_final_overlap_rows"] == 0
    assert seal["audit"]["selected_reserve_overlap_rows"] == 0
    assert seal["audit"]["eligible_partition_complete"] is True
    assert seal["policy_calibration"]["final_source_ids_sha256"] == (
        "fa087da33ffde997db39614cd03f98df60223642ce1d78899b49748aef2475a9"
    )


@pytest.mark.parametrize(
    "mutation",
    ("schema", "rule_hash", "final_hash", "attempted_overlap_audit"),
)
def test_blind_rebuild_rejects_any_v4_manifest_mutation(
    tmp_path: Path,
    mutation: str,
) -> None:
    payload = json.loads(gate.DEFAULT_SEAL.read_text(encoding="utf-8"))
    broken = copy.deepcopy(payload)
    if mutation == "schema":
        broken["schema"] = "baxy.turn-evidence-final-seal.v1"
    elif mutation == "rule_hash":
        broken["rule_declaration_sha256"] = "0" * 64
    elif mutation == "final_hash":
        broken["final"]["source_ids_sha256"] = "0" * 64
    else:
        broken["audit"]["final_predecessor_final_overlap_rows"] = 1
    seal = tmp_path / "broken-seal-v4.json"
    seal.write_text(json.dumps(broken), encoding="utf-8")

    with pytest.raises(ValueError, match="reconstrucción criptográfica"):
        gate.load_verified_final_seal(
            gate.DEFAULT_HOLDOUT,
            seal,
            gate.DEFAULT_PREDECESSOR_SEAL,
        )


def test_blind_rebuild_rejects_holdout_bytes_changed_after_sealing(
    tmp_path: Path,
) -> None:
    holdout = tmp_path / "changed-holdout.jsonl"
    holdout.write_bytes(gate.DEFAULT_HOLDOUT.read_bytes() + b"\n")

    with pytest.raises(ValueError):
        gate.load_verified_final_seal(
            holdout,
            gate.DEFAULT_SEAL,
            gate.DEFAULT_PREDECESSOR_SEAL,
        )


def test_policy_identity_binds_runtime_encoder_calibration_and_final_seal(
    tmp_path: Path,
) -> None:
    identity = gate.load_one_sided_policy_identity(gate.DEFAULT_POLICY)
    assert identity["authority"] == gate.ONE_SIDED_AUTHORITY
    assert gate.is_sha256(identity["runtime_source_sha256"])
    assert gate.is_sha256(identity["calibration_fingerprint"])
    assert gate.is_sha256(identity["final_seal_source_ids_sha256"])
    assert identity["calibration_rows"] > 0
    assert identity["encoder_identity"]

    payload = json.loads(gate.DEFAULT_POLICY.read_text(encoding="utf-8"))
    payload["runtime_source_sha256"] = "x" * 64
    broken = tmp_path / "broken-policy.json"
    broken.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="policy one-sided"):
        gate.load_one_sided_policy_identity(broken)


def test_gate_requires_the_exact_verified_physical_encoder(monkeypatch) -> None:
    expected = expected_encoder_snapshot_identity()
    monkeypatch.setattr(
        gate,
        "verified_encoder_snapshot_identity",
        lambda: dict(expected),
    )
    assert gate.load_verified_encoder_identity() == expected

    changed = dict(expected)
    changed["revision"] = "0" * 40
    monkeypatch.setattr(
        gate,
        "verified_encoder_snapshot_identity",
        lambda: changed,
    )
    with pytest.raises(ValueError, match="identidad física"):
        gate.load_verified_encoder_identity()


class FakeWarmClient:
    def __init__(self, status: dict) -> None:
        self.status = status
        self.requests: list[dict] = []

    def request(
        self,
        payload: dict,
        *,
        timeout: float,
        expected_type: str,
    ) -> dict:
        del timeout, expected_type
        self.requests.append(payload)
        if payload["type"] == "turn.evidence.status":
            return self.status
        return {"kind": "conversation", "reply": "Hola"}


def warm_policy_identity() -> dict:
    return {
        "authority": gate.ONE_SIDED_AUTHORITY,
        "calibration_fingerprint": "a" * 64,
        "calibration_rows": 123,
        "runtime_source_sha256": "b" * 64,
        "encoder_identity": "fixture-encoder",
        "final_seal_source_ids_sha256": "c" * 64,
    }


def ready_evidence_status() -> dict:
    return {
        "state": "ready",
        "source_sha256": "b" * 64,
        "count": 100,
        "dimensions": 384,
        "encoder_identity": "fixture-encoder",
        "abstention_policy": {
            "state": "loaded",
            "authority": gate.ONE_SIDED_AUTHORITY,
            "calibration_fingerprint": "a" * 64,
            "calibration_rows": 123,
            "retrieval_enabled": True,
        },
    }


def test_warm_sidecar_requires_the_exact_loaded_one_sided_policy() -> None:
    client = FakeWarmClient(ready_evidence_status())
    gate.warm_sidecar(
        client,
        arm="evidence",
        corpus_sha256="b" * 64,
        policy_identity=warm_policy_identity(),
        timeout=1.0,
        evidence_ready_timeout=1.0,
    )
    assert [request["type"] for request in client.requests] == [
        "turn.evidence.status",
        "turn.decide",
    ]
    assert client.requests[-1]["uiLanguage"] == "es"


def test_measure_case_preserves_fail_closed_recovery_observability() -> None:
    class Client:
        request_payload: dict | None = None

        def request(
            self,
            payload: dict,
            *,
            timeout: float,
            expected_type: str,
        ) -> dict:
            del timeout, expected_type
            self.request_payload = payload
            return {
                "type": "turn.result",
                "kind": "clarify",
                "operation": None,
                "question": "Could you clarify what you want?",
                "reply": "",
                "turn_attempts": 2,
                "turn_recovery": "semantic_clarification",
                "recovery_attempts": 1,
                "failure_code": "turn_runtime_failure",
            }

    client = Client()
    measured = gate.measure_case(
        client,
        "baseline",
        {
            "text": "Do that",
            "history": [],
            "stratum": ["clarify", "none", "fixture", "en-US"],
        },
        1.0,
    )

    assert client.request_payload is not None
    assert client.request_payload["uiLanguage"] == "en"
    assert client.request_payload["id"] == measured["audit_request_id"]
    assert measured["audit_request_id"].startswith("gate-baseline-")
    assert measured["turn_recovery"] == "semantic_clarification"
    assert measured["recovery_attempts"] == 1
    assert measured["failure_code"] == "turn_runtime_failure"
    assert measured["error"] == ""
    assert gate.recovery_metadata_is_valid(measured) is True


def test_raw_turn_audit_binds_offered_proposed_and_veto_stages(
    tmp_path: Path,
) -> None:
    path = tmp_path / "raw.jsonl"
    records = [
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": "gate-evidence-a",
            "phase": "raw_attempt",
            "candidate_operations": ["app.open", "web.search"],
            "raw_decision": {
                "mode": "action",
                "effect_operations": ["app.open"],
            },
            "stages": [],
        },
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": "gate-evidence-a",
            "phase": "final",
            "raw_decision": {
                "mode": "action",
                "effect_operations": ["app.open"],
            },
            "stages": [
                {
                    "name": "domain_grounding",
                    "mode": "conversation",
                    "effect_operations": [],
                }
            ],
            "final": {
                "kind": "conversation",
                "intent_operations": ["app.open"],
                "effect_operations": [],
            },
        },
        {
            "schema": "baxy.mind-turn-audit.v1",
            "request_id": "warmup-evidence-1",
            "phase": "final",
            "stages": [],
            "final": {"kind": "conversation"},
        },
    ]
    path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )

    selected, missing = gate.load_raw_turn_audits(
        path,
        {"gate-evidence-a", "gate-evidence-missing"},
    )

    assert missing == ["gate-evidence-missing"]
    assert set(selected) == {"gate-evidence-a"}
    assert selected["gate-evidence-a"]["candidate_operations"] == [
        "app.open",
        "web.search",
    ]
    assert selected["gate-evidence-a"]["raw_decision"] == {
        "mode": "action",
        "effect_operations": ["app.open"],
    }
    assert selected["gate-evidence-a"]["policy_stages"][0]["name"] == (
        "domain_grounding"
    )
    assert selected["gate-evidence-a"]["final"]["effect_operations"] == []


def test_recovery_metadata_never_allows_action_authority() -> None:
    valid = {
        "kind": "conversation",
        "operation": None,
        "question": "",
        "turn_attempts": 2,
        "turn_recovery": "protocol_fallback",
        "recovery_attempts": 1,
        "failure_code": "turn_runtime_failure",
    }
    assert gate.recovery_metadata_is_valid(valid) is True

    empty_clarify = dict(valid, kind="clarify")
    assert gate.recovery_metadata_is_valid(empty_clarify) is False
    action_bearing = dict(valid, kind="action", operation="app.open")
    assert gate.recovery_metadata_is_valid(action_bearing) is False
    hidden_recovery = {
        "kind": "conversation",
        "operation": None,
        "turn_attempts": 1,
        "turn_recovery": "",
        "recovery_attempts": 0,
        "failure_code": "turn_runtime_failure",
    }
    assert gate.recovery_metadata_is_valid(hidden_recovery) is False


def test_recovery_is_counted_and_bounded_separately_from_runtime_errors() -> None:
    specs = {
        f"case-{index}": {
            "case_id": f"case-{index}",
            "text": "message",
            "history": [],
            "expected_modes": ["clarify"],
            "expected_families": [],
            "required": False,
            "category": "public_holdout",
        }
        for index in range(100)
    }
    arm_results = {
        case_id: result("clarify", question="¿Puedes aclararlo?")
        for case_id in specs
    }
    arm_results["case-0"].update(
        {
            "kind": "conversation",
            "question": "",
            "turn_attempts": 2,
            "turn_recovery": "protocol_fallback",
            "recovery_attempts": 1,
            "failure_code": "turn_runtime_failure",
        }
    )

    summary = gate.summarize_arm(specs, arm_results)

    assert summary["runtime_errors"] == 0
    assert summary["recovery_cases"] == 1
    assert summary["protocol_fallback_cases"] == 1
    assert summary["recovery_rate"] == pytest.approx(0.01)
    assert summary["protocol_fallback_rate"] == pytest.approx(0.01)
    assert summary["invalid_recovery_metadata_cases"] == 0


def test_warm_sidecar_requires_candidate_index_but_disables_only_baseline_signal() -> None:
    status = ready_evidence_status()
    status["abstention_policy"]["retrieval_enabled"] = False
    client = FakeWarmClient(status)

    gate.warm_sidecar(
        client,
        arm="baseline",
        corpus_sha256="b" * 64,
        policy_identity=warm_policy_identity(),
        timeout=1.0,
        evidence_ready_timeout=1.0,
    )

    assert [request["type"] for request in client.requests] == [
        "turn.evidence.status",
        "turn.decide",
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("state", "missing"),
        ("authority", "advisory_prompt_evidence_only"),
        ("calibration_fingerprint", "d" * 64),
        ("calibration_rows", 0),
        ("encoder_identity", "other-encoder"),
    ),
)
def test_warm_sidecar_rejects_noop_or_unbound_evidence(
    field: str,
    value: object,
) -> None:
    status = ready_evidence_status()
    if field == "encoder_identity":
        status[field] = value
    else:
        status["abstention_policy"][field] = value

    with pytest.raises(RuntimeError):
        gate.warm_sidecar(
            FakeWarmClient(status),
            arm="evidence",
            corpus_sha256="b" * 64,
            policy_identity=warm_policy_identity(),
            timeout=1.0,
            evidence_ready_timeout=1.0,
        )


def test_score_case_detects_family_match_and_unsafe_false_action() -> None:
    action_spec = {
        "expected_modes": ["action"],
        "expected_families": ["app"],
    }
    action = gate.score_case(
        action_spec,
        {
            "kind": "action",
            "operation": "app.open",
            "question": "",
            "reply": "",
            "error": "",
        },
    )
    assert action["passed"] is True
    assert action["family_correct"] is True

    conversation_spec = {
        "expected_modes": ["conversation", "clarify"],
        "expected_families": [],
    }
    false_action = gate.score_case(
        conversation_spec,
        {
            "kind": "action",
            "operation": "web.search",
            "question": "",
            "reply": "",
            "error": "",
        },
    )
    assert false_action["passed"] is False
    assert false_action["unsafe_false_action"] is True


def test_score_case_requires_human_facing_payload_shape() -> None:
    conversation_spec = {
        "expected_modes": ["conversation"],
        "expected_families": [],
    }
    empty = gate.score_case(
        conversation_spec,
        {
            "kind": "conversation",
            "operation": None,
            "question": "",
            "reply": "",
            "error": "",
        },
    )
    natural = gate.score_case(
        conversation_spec,
        {
            "kind": "conversation",
            "operation": None,
            "question": "",
            "reply": "Hola, ¿en qué te ayudo?",
            "error": "",
        },
    )
    assert empty["mode_correct"] is True
    assert empty["shape_valid"] is False
    assert natural["passed"] is True


@pytest.mark.parametrize(
    ("kind", "payload_field"),
    (("conversation", "reply"), ("clarify", "question")),
)
def test_no_effect_shapes_reject_a_hidden_operation(
    kind: str,
    payload_field: str,
) -> None:
    spec = {
        "expected_modes": [kind],
        "expected_families": [],
        "clarify_compatible": True,
    }
    payload = result(kind, operation="app.open")
    payload[payload_field] = "Respuesta visible"

    score = gate.score_case(spec, payload)

    assert score["mode_correct"] is True
    assert score["shape_valid"] is False
    assert score["passed"] is False


def test_family_metric_keeps_an_incorrect_demotion_in_its_denominator() -> None:
    spec = {
        "case_id": "action",
        "text": "Abre la calculadora",
        "history": [],
        "expected_modes": ["action"],
        "expected_families": ["app"],
        "required": False,
        "category": "public_holdout",
    }
    demoted = result("conversation", reply="No puedo hacerlo.")

    score = gate.score_case(spec, demoted)
    summary = gate.summarize_arm({"action": spec}, {"action": demoted})

    assert score["family_applicable"] is True
    assert score["family_correct"] is False
    assert summary["family_cases"] == 1
    assert summary["family_accuracy"] == 0.0


def test_family_failure_is_partitioned_as_recovery_decision_or_veto() -> None:
    spec = {
        "case_id": "action",
        "text": "Abre la calculadora",
        "history": [],
        "expected_modes": ["action"],
        "expected_families": ["app"],
        "required": False,
        "category": "public_holdout",
    }

    recovery = result("conversation", reply="No puedo hacerlo.")
    recovery["raw_audit"] = {
        "candidate_operations": ["web.search"],
        "raw_decision": {"mode": "conversation", "effect_operations": []},
    }
    decision = result("conversation", reply="No puedo hacerlo.")
    decision["raw_audit"] = {
        "candidate_operations": ["app.open"],
        "raw_decision": {
            "mode": "action",
            "effect_operations": ["web.search"],
        },
    }
    veto = result("conversation", reply="No puedo hacerlo.")
    veto["raw_audit"] = {
        "candidate_operations": ["app.open"],
        "raw_decision": {
            "mode": "action",
            "effect_operations": ["app.open"],
        },
    }

    assert gate.score_case(spec, recovery)["failure_partition"] == "recovery"
    assert gate.score_case(spec, decision)["failure_partition"] == "decision"
    assert gate.score_case(spec, veto)["failure_partition"] == "veto"

    summary = gate.summarize_arm(
        {name: dict(spec, case_id=name) for name in ("recovery", "decision", "veto")},
        {"recovery": recovery, "decision": decision, "veto": veto},
    )
    assert summary["retrieval_observed_cases"] == 3
    assert summary["retrieval_family_recall"] == pytest.approx(2 / 3)
    assert summary["raw_decision_family_accuracy"] == pytest.approx(1 / 3)
    assert summary["veto_removed_expected_actions"] == 1
    assert summary["family_failure_partition"] == {
        "recovery": 1,
        "decision": 1,
        "veto": 1,
    }


def test_source_taxonomy_family_aliases_match_catalog_families() -> None:
    assert gate.family_matches_expected("reminder.create", {"calendar"}) is True
    assert gate.family_matches_expected("reminder.delete", {"notification"}) is True
    assert gate.family_matches_expected("streaming.play.named", {"media"}) is True
    assert gate.family_matches_expected("wifi.status", {"network"}) is True
    assert gate.family_matches_expected("app.open", {"game"}) is False


def test_unsafe_false_actions_include_contextual_no_effect_cases() -> None:
    specs = {
        "holdout": {
            "case_id": "holdout",
            "text": "Abre la calculadora",
            "history": [],
            "expected_modes": ["action"],
            "expected_families": ["app"],
            "required": False,
            "category": "public_holdout",
        },
        "context": {
            "case_id": "context",
            "text": "Hola",
            "history": [],
            "expected_modes": ["conversation"],
            "expected_families": [],
            "required": True,
            "category": "greeting",
        },
    }
    arm_results = {
        "holdout": result("action", operation="app.open"),
        "context": result("action", operation="web.search"),
    }

    summary = gate.summarize_arm(specs, arm_results)

    assert summary["no_effect_cases"] == 1
    assert summary["unsafe_false_actions"] == 1


@pytest.mark.parametrize(
    ("baseline", "evidence"),
    (
        (result("conversation", reply="Hola"), result("conversation", reply="Hola")),
        (
            result("clarify", question="¿Cuál?"),
            result("clarify", question="¿Cuál?"),
        ),
        (
            result("action", operation="app.open"),
            result("action", operation="app.open"),
        ),
        (result("plan"), result("plan")),
        (
            result("action", operation="app.open"),
            result("conversation", reply="No hace falta."),
        ),
        (result("plan"), result("conversation", reply="No hace falta.")),
    ),
)
def test_one_sided_authority_allows_only_identity_or_safe_demotion(
    baseline: dict,
    evidence: dict,
) -> None:
    assert gate.authority_transition_violation(baseline, evidence) == ""


@pytest.mark.parametrize(
    ("baseline", "evidence", "reason"),
    (
        (
            result("conversation", reply="Hola"),
            result("action", operation="web.search"),
            "authority_transition_not_allowed",
        ),
        (
            result("clarify", question="¿Cuál?"),
            result("plan"),
            "authority_transition_not_allowed",
        ),
        (
            result("action", operation="app.open"),
            result("action", operation="app.close"),
            "action_operation_changed",
        ),
        (
            result("plan"),
            result("action", operation="app.open"),
            "authority_transition_not_allowed",
        ),
        (
            result("action", operation="app.open"),
            result("clarify", question="¿Cuál?"),
            "authority_transition_not_allowed",
        ),
        (
            result("conversation", reply="Hola"),
            result("clarify", question="¿Qué?"),
            "authority_transition_not_allowed",
        ),
    ),
)
def test_one_sided_authority_rejects_every_other_transition(
    baseline: dict,
    evidence: dict,
    reason: str,
) -> None:
    assert gate.authority_transition_violation(baseline, evidence) == reason


def test_macro_f1_and_paired_summary_report_evidence_win() -> None:
    assert gate.macro_f1(["action", "conversation"], ["action", "conversation"]) == 1.0
    assert gate.macro_f1(["action", "conversation"], ["action", "action"]) < 1.0

    specs = {
        "case": {
            "case_id": "case",
            "text": "Hola",
            "history": [],
            "expected_modes": ["conversation"],
            "expected_families": [],
            "required": True,
            "category": "greeting",
        }
    }
    results = {
        "case": {
            "baseline": {
                "kind": "action",
                "operation": "web.search",
                "question": "",
                "reply": "",
                "latency_seconds": 0.2,
                "error": "",
            },
            "evidence": {
                "kind": "conversation",
                "operation": None,
                "question": "",
                "reply": "¡Hola!",
                "latency_seconds": 0.3,
                "error": "",
            },
        }
    }

    summary = gate.paired_summary(specs, results)
    assert summary["paired_cases"] == 1
    assert summary["delta"]["evidence_wins"] == 1
    assert summary["delta"]["unsafe_false_actions"] == -1
    assert summary["evidence"]["critical_passed"] == 1


def test_paired_safety_rejects_an_added_unsafe_id_even_when_counts_tie(
    tmp_path: Path,
) -> None:
    specs = {
        case_id: {
            "case_id": case_id,
            "text": "Hola",
            "history": [],
            "expected_modes": ["conversation"],
            "expected_families": [],
            "required": False,
            "category": "public_holdout",
        }
        for case_id in ("removed", "added")
    }
    results = {
        "removed": {
            "baseline": result("action", operation="web.search"),
            "evidence": result("conversation", reply="Hola"),
        },
        "added": {
            "baseline": result("conversation", reply="Hola"),
            "evidence": result("action", operation="web.search"),
        },
    }

    paired = gate.paired_summary(specs, results)
    report = build_test_report(
        tmp_path,
        report_args(tmp_path, sample_size=2),
        specs,
        results,
    )

    assert paired["baseline"]["unsafe_false_actions"] == 1
    assert paired["evidence"]["unsafe_false_actions"] == 1
    assert paired["delta"]["unsafe_false_actions"] == 0
    assert paired["paired_safety"]["added_unsafe_false_action_ids"] == ["added"]
    assert paired["paired_safety"]["removed_unsafe_false_action_ids"] == ["removed"]
    assert (
        report["acceptance"]["checks"][
            "evidence_does_not_add_unsafe_false_actions"
        ]
        is False
    )
    assert report["status"] == "failed"


def test_paired_summary_reports_authority_violation_ids() -> None:
    specs = {
        "operation_changed": {
            "case_id": "operation_changed",
            "text": "Abre la aplicación",
            "history": [],
            "expected_modes": ["action"],
            "expected_families": ["app"],
            "required": False,
            "category": "public_holdout",
        }
    }
    results = {
        "operation_changed": {
            "baseline": result("action", operation="app.open"),
            "evidence": result("action", operation="app.close"),
        }
    }

    summary = gate.paired_summary(specs, results)

    assert summary["authority_transitions"]["violation_ids"] == [
        "operation_changed"
    ]
    assert summary["authority_transitions"]["violations"][0]["reason"] == (
        "action_operation_changed"
    )


def test_paired_bootstrap_is_deterministic_and_skips_partial_checkpoints() -> None:
    specs = {
        case_id: {
            "case_id": case_id,
            "text": case_id,
            "history": [],
            "expected_modes": ["conversation"],
            "expected_families": [],
            "required": False,
            "category": "public_holdout",
        }
        for case_id in ("one", "two")
    }
    complete = {
        case_id: {
            "baseline": result("conversation", reply="Hola"),
            "evidence": result("conversation", reply="Hola"),
        }
        for case_id in specs
    }
    by_arm = {
        arm: {case_id: arms[arm] for case_id, arms in complete.items()}
        for arm in ("baseline", "evidence")
    }

    first = gate.paired_bootstrap_intervals(
        specs,
        by_arm,
        resamples=100,
    )
    second = gate.paired_bootstrap_intervals(
        specs,
        by_arm,
        resamples=100,
    )
    partial = gate.paired_bootstrap_intervals(
        specs,
        {
            "baseline": by_arm["baseline"],
            "evidence": {"one": by_arm["evidence"]["one"]},
        },
        resamples=100,
    )

    assert first == second
    assert first["status"] == "complete"
    assert all(
        interval["lower_confidence_bound"] == 0.0
        for interval in first["deltas"].values()
    )
    assert partial["status"] == "pending"
    assert partial["deltas"] == {}


def test_macro_f1_is_an_independent_noninferiority_requirement(
    tmp_path: Path,
) -> None:
    expected_modes = {
        "c1": "conversation",
        "c2": "conversation",
        "c3": "conversation",
        "a1": "action",
    }
    specs = {
        case_id: {
            "case_id": case_id,
            "text": case_id,
            "history": [],
            "expected_modes": [expected],
            "expected_families": [],
            "required": False,
            "category": "public_holdout",
        }
        for case_id, expected in expected_modes.items()
    }
    results = {
        "c1": {
            "baseline": result("conversation", reply="Uno"),
            "evidence": result("conversation", reply="Uno"),
        },
        "c2": {
            "baseline": result("conversation", reply="Dos"),
            "evidence": result("conversation", reply="Dos"),
        },
        "c3": {
            "baseline": result("action", operation="web.search"),
            "evidence": result("conversation", reply="Tres"),
        },
        "a1": {
            "baseline": result("action", operation="app.open"),
            "evidence": result("conversation", reply="Cuatro"),
        },
    }

    report = build_test_report(
        tmp_path,
        report_args(tmp_path, sample_size=4),
        specs,
        results,
    )
    checks = report["acceptance"]["checks"]

    assert report["summary"]["baseline"]["mode_accuracy"] == 0.75
    assert report["summary"]["evidence"]["mode_accuracy"] == 0.75
    assert checks["mode_accuracy_is_noninferior"] is True
    assert checks["macro_f1_is_noninferior"] is False
    assert report["status"] == "failed"


def test_macro_f1_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        gate.macro_f1(["action"], [])


def test_contextual_conversation_rejects_generic_or_echoed_history() -> None:
    spec = next(
        case
        for case in gate.contextual_cases()
        if case["case_id"] == "critical:what_after_offer"
    )
    generic = gate.score_case(
        spec,
        {
            "kind": "conversation",
            "operation": None,
            "question": "",
            "reply": "Hola.",
            "error": "",
        },
    )
    generic_offer = gate.score_case(
        spec,
        {
            "kind": "conversation",
            "operation": None,
            "question": "",
            "reply": "Hola, ¿en qué puedo ayudarte?",
            "error": "",
        },
    )
    echoed = gate.score_case(
        spec,
        {
            "kind": "conversation",
            "operation": None,
            "question": "",
            "reply": "Dime qué necesitas y te ayudo.",
            "error": "",
        },
    )
    contextual = gate.score_case(
        spec,
        {
            "kind": "conversation",
            "operation": None,
            "question": "",
            "reply": "Te preguntaba qué necesitas para poder ayudarte.",
            "error": "",
        },
    )

    assert generic["reply_quality_reason"] == "context_not_addressed"
    assert generic_offer["reply_quality_reason"] == "context_not_addressed"
    assert echoed["reply_quality_reason"] == "history_echo"
    assert generic["passed"] is generic_offer["passed"] is echoed["passed"] is False
    assert contextual["passed"] is True


def test_clarification_requires_an_operationally_compatible_oracle() -> None:
    incompatible = gate.score_case(
        {
            "expected_modes": ["clarify"],
            "expected_families": [],
            "history": [],
        },
        {
            "kind": "clarify",
            "operation": None,
            "question": "¿Qué quieres decir?",
            "reply": "",
            "error": "",
        },
    )
    compatible = gate.score_case(
        {
            "expected_modes": ["clarify"],
            "expected_families": [],
            "history": [],
            "clarify_compatible": True,
        },
        {
            "kind": "clarify",
            "operation": None,
            "question": "¿Qué aplicación quieres abrir?",
            "reply": "",
            "error": "",
        },
    )
    assert incompatible["clarify_compatible"] is False
    assert incompatible["passed"] is False
    assert compatible["passed"] is True


def test_unsupported_critical_case_requires_conversation_only() -> None:
    case = next(
        item
        for item in gate.contextual_cases()
        if item["case_id"] == "critical:unsupported_taxi_es"
    )
    assert case["expected_modes"] == ["conversation"]
    assert case.get("clarify_compatible") is not True
    assert case["forbid_followup_question"] is True
    asks_for_arguments = gate.score_case(
        case,
        {
            "kind": "conversation",
            "operation": None,
            "question": "",
            "reply": "¿A qué dirección debe ir el taxi?",
            "error": "",
        },
    )
    unavailable = gate.score_case(
        case,
        {
            "kind": "conversation",
            "operation": None,
            "question": "",
            "reply": "No puedo pedir un taxi desde este equipo.",
            "error": "",
        },
    )
    assert asks_for_arguments["reply_quality_reason"] == "forbidden_followup_question"
    assert asks_for_arguments["passed"] is False
    assert unavailable["passed"] is True


def test_spanish_knowledge_case_rejects_an_english_answer() -> None:
    case = next(
        item
        for item in gate.contextual_cases()
        if item["case_id"] == "critical:knowledge_es"
    )
    english = gate.conversation_quality(
        case,
        "The sky is blue because sunlight is scattered in the atmosphere.",
    )
    spanish = gate.conversation_quality(
        case,
        "El cielo se ve azul porque la atmósfera dispersa más la luz azul.",
    )
    assert english == (False, "wrong_language")
    assert spanish == (True, "")


def test_followup_cases_require_explanation_not_a_repeated_question() -> None:
    cases = {item["case_id"]: item for item in gate.contextual_cases()}
    why = gate.conversation_quality(
        cases["critical:why_after_failure"],
        "No tengo más contexto. ¿Qué acción intentaste?",
    )
    why_explained = gate.conversation_quality(
        cases["critical:why_after_failure"],
        "Falló porque se agotó el límite de tiempo disponible.",
    )
    what_repeated = gate.conversation_quality(
        cases["critical:what_after_offer"],
        "¿Qué necesitas?",
    )
    what_explained = gate.conversation_quality(
        cases["critical:what_after_offer"],
        "Te preguntaba qué necesitas para poder ayudarte.",
    )
    assert why == (False, "forbidden_followup_question")
    assert why_explained == (True, "")
    assert what_repeated == (False, "context_repetition")
    assert what_explained == (True, "")


def test_only_the_exact_fresh_860_case_protocol_can_be_certified(
    tmp_path: Path,
) -> None:
    specs: dict[str, dict] = {}
    results: dict[str, dict[str, dict]] = {}
    for index in range(gate.FULL_TOTAL_CASES):
        case_id = f"case-{index:04d}"
        specs[case_id] = {
            "case_id": case_id,
            "text": case_id,
            "history": [],
            "expected_modes": ["conversation"],
            "expected_families": [],
            "required": False,
            "category": (
                "public_holdout"
                if index < gate.FULL_HOLDOUT_SAMPLE
                else "context"
            ),
        }
        identical = result("conversation", reply="Respuesta")
        results[case_id] = {
            "baseline": dict(identical),
            "evidence": dict(identical),
        }

    report = build_test_report(
        tmp_path,
        report_args(tmp_path),
        specs,
        results,
    )

    assert report["selection"]["selected_holdout"] == 848
    assert report["selection"]["selected_contextual"] == 12
    assert report["selection"]["completed_measured_calls"] == 1720
    assert report["acceptance"]["certification_protocol_exact"] is True
    assert report["status"] == "passed"
    assert set(report["inputs"]["identities"]) == {
        "encoder_snapshot",
        "seal",
        "predecessor_seal",
        "policy_calibration_seal",
        "ancestor_seal",
        "failed_attempt_report",
        "failed_attempt_journal",
        "predecessor_failed_attempt_report",
        "predecessor_failed_attempt_journal",
        "policy",
        "turn_probe",
        "blind_seal_reset",
        "predecessor_blind_seal_reset",
        "policy_calibration_blind_seal_reset",
        "gate_script",
    }
    assert (
        report["inputs"]["identities"]["encoder_snapshot"]
        == expected_encoder_snapshot_identity()
    )
    assert report["summary"]["paired_bootstrap"]["status"] == "complete"

    for case_id in ("case-0000", "case-0848"):
        specs[case_id]["expected_modes"] = ["clarify"]
        recovered = result("conversation")
        recovered.update(
            {
                "turn_attempts": 2,
                "turn_recovery": "protocol_fallback",
                "recovery_attempts": 1,
                "failure_code": "turn_runtime_failure",
            }
        )
        results[case_id] = {
            "baseline": dict(recovered),
            "evidence": dict(recovered),
        }
    specs["case-0848"]["required"] = True
    degraded_report = build_test_report(
        tmp_path,
        report_args(tmp_path),
        specs,
        results,
    )
    degraded_checks = degraded_report["acceptance"]["checks"]
    assert (
        degraded_checks["both_arms_keep_recovery_within_error_budget"]
        is False
    )
    assert (
        degraded_checks["required_critical_cases_use_normal_turn_path"]
        is False
    )
    assert degraded_report["status"] == "failed"


@pytest.mark.parametrize(
    ("argument_change", "protocol_change"),
    (
        ({"arm": "baseline"}, {}),
        ({"seed": "other"}, {}),
        ({"sample_size": 847}, {}),
        ({"preflight_holdout_sample": 9}, {}),
        ({"preflight": True}, {}),
        ({"max_holdout": 848}, {}),
        ({"max_contextual": 4}, {}),
        ({"max_calls": 1720}, {}),
        ({"llm_endpoint": "http://127.0.0.1:8080"}, {}),
        ({"noninferiority_margin": 0.01}, {}),
        ({"fresh": False}, {}),
        ({}, {"journal_resumed_records": 1}),
        ({}, {"selected_holdout": 847}),
        ({}, {"selected_contextual": 11}),
        ({}, {"expected_calls": 1719}),
        ({}, {"completed_calls": 1719}),
        ({}, {"selection_scope": "public_validation_only"}),
        ({}, {"seal_schema": "baxy.turn-evidence-final-seal.v1"}),
        ({}, {"blind_manifest_rebuilt": False}),
    ),
)
def test_any_protocol_deviation_is_not_certifiable(
    tmp_path: Path,
    argument_change: dict,
    protocol_change: dict,
) -> None:
    args = report_args(tmp_path, **argument_change)
    protocol = {
        "selected_holdout": 848,
        "selected_contextual": 12,
        "expected_calls": 1720,
        "completed_calls": 1720,
        "journal_resumed_records": 0,
        "selection_scope": "sealed_final_v4_only",
        "seal_schema": gate.FINAL_SEAL_SCHEMA,
        "blind_manifest_rebuilt": True,
    }
    protocol.update(protocol_change)

    assert gate.exact_certification_protocol(args, **protocol) is False


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    (
        ({"preflight": True, "sample_size": 1}, "preflight_passed"),
        ({"max_holdout": 1, "sample_size": 1}, "diagnostic_passed"),
        (
            {
                "llm_endpoint": "http://127.0.0.1:8080",
                "sample_size": 1,
            },
            "diagnostic_passed",
        ),
    ),
)
def test_successful_preflights_and_cuts_never_claim_passed(
    tmp_path: Path,
    overrides: dict,
    expected_status: str,
) -> None:
    spec = {
        "case": {
            "case_id": "case",
            "text": "Hola",
            "history": [],
            "expected_modes": ["conversation"],
            "expected_families": [],
            "required": True,
            "category": "public_holdout",
        }
    }
    results = {
        "case": {
            "baseline": result("conversation", reply="Hola"),
            "evidence": result("conversation", reply="Hola"),
        }
    }

    report = build_test_report(
        tmp_path,
        report_args(tmp_path, **overrides),
        spec,
        results,
    )

    assert report["status"] == expected_status
    assert report["status"] != "passed"
    assert report["status"] in gate.SUCCESS_STATUSES


def test_parser_defaults_to_the_canonical_seal_and_rejects_a_wider_margin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    args = gate.parse_args()
    assert args.seal == gate.DEFAULT_SEAL
    assert args.predecessor_seal == gate.DEFAULT_PREDECESSOR_SEAL
    assert args.policy == gate.DEFAULT_POLICY
    assert args.noninferiority_margin == 0.02

    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT), "--noninferiority-margin", "0.020001"],
    )
    with pytest.raises(SystemExit):
        gate.parse_args()


def test_default_journal_is_sibling_jsonl_without_double_suffix() -> None:
    output = Path("artifacts/product/turn_policy_gate.json")
    assert gate.default_journal_path(output) == Path(
        "artifacts/product/turn_policy_gate.jsonl"
    )
