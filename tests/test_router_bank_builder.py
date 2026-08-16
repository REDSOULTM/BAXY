from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from baxy_mind.tools.build_bank import (  # noqa: E402
    DEFAULT_CASES,
    DEFAULT_OUTPUT,
    build_bank,
)
from baxy_mind.tools import atomic_output  # noqa: E402
from baxy_mind.tools.extract_router_cases import (  # noqa: E402
    build_cases,
    write_cases,
)
from baxy_mind.tools.frozen_files import (  # noqa: E402
    verify_frozen_file,
    verify_frozen_payload,
)
from baxy_mind.tools.router_bank_sources import ALL_POOLS  # noqa: E402


EXPECTED_SOURCES_SHA256 = (
    "a2fe3679dfe46a6de9c9f1721d255c2b78804d48fba0aadfb32934d29240c868"
)
EXPECTED_CASES_SHA256 = (
    "619848aaab1725309b8831799ec395b51ddb628f9cc9a22f3e9675b957fde55d"
)
EXPECTED_BANK_SHA256 = (
    "f39c414ff92f376ef409d460ab86b8cac6de4916b338f2575bbe40e58b78d312"
)
EXPECTED_POOL_SHA256 = (
    "09f33ba167a5d0a396b8a2c0eca508c7bd3c58223dff69bf7c664e5cf4a980c2"
)
EXPECTED_LLM_SAMPLED_SHA256 = (
    "9e050405ed9e4b09aeae0eab85c69a67149835c19e6dddca52058cb52c276780"
)
EXPECTED_LLM_PROBES_SHA256 = (
    "a2291776fcc135027bd9b134b58c6564c07f549dac008573c2e2ffeeb78024e7"
)
ENCODER_PROTOCOL = (
    ROOT
    / "experiments"
    / "mind_router_spike"
    / "tournament_encoder_protocol.json"
)
LLM_PROTOCOL = ROOT / "experiments" / "mind_llm_tournament" / "protocol.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_router_bank_inputs_are_canonical_and_byte_identical() -> None:
    sources = SRC / "baxy_mind" / "tools" / "router_bank_sources.py"

    assert sha256(sources) == EXPECTED_SOURCES_SHA256
    assert sha256(DEFAULT_CASES) == EXPECTED_CASES_SHA256
    assert len(ALL_POOLS) == 39
    assert sum(len(exemplars) for exemplars in ALL_POOLS.values()) == 302
    assert not (ROOT / "experiments" / "mind_router_spike" / "pools.py").exists()
    assert not (
        ROOT / "experiments" / "mind_router_spike" / "data" / "cases.jsonl"
    ).exists()


def test_historical_tournaments_bind_every_promoted_input_by_hash() -> None:
    encoder_files = {
        "router_cases": DEFAULT_CASES,
        "router_bank_sources": (
            SRC / "baxy_mind" / "tools" / "router_bank_sources.py"
        ),
        "development_probes": (
            ROOT / "experiments" / "mind_router_spike" / "dev_probes.py"
        ),
    }
    llm_files = {
        "router_cases": DEFAULT_CASES,
        "core_hello": (
            ROOT
            / "experiments"
            / "mind_router_spike"
            / "data"
            / "core_hello.json"
        ),
        "historical_messages": ROOT / "tests" / "data" / "historical_messages.jsonl",
        "sampled_cases": (
            ROOT
            / "experiments"
            / "mind_llm_tournament"
            / "data"
            / "sampled_cases.jsonl"
        ),
        "conversation_probes": (
            ROOT
            / "experiments"
            / "mind_llm_tournament"
            / "data"
            / "conversation_probes.jsonl"
        ),
    }

    for file_id, expected_path in encoder_files.items():
        assert verify_frozen_file(ROOT, ENCODER_PROTOCOL, file_id) == expected_path
    for file_id, expected_path in llm_files.items():
        assert verify_frozen_file(ROOT, LLM_PROTOCOL, file_id) == expected_path


def test_frozen_file_verification_fails_closed_on_drift(tmp_path: Path) -> None:
    source = tmp_path / "input.bin"
    source.write_bytes(b"original")
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "frozen_files": {
                    "fixture": {
                        "canonical_location": "input.bin",
                        "sha256": hashlib.sha256(b"original").hexdigest(),
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    assert verify_frozen_file(tmp_path, protocol, "fixture") == source
    assert verify_frozen_payload(
        tmp_path,
        protocol,
        "fixture",
        b"original",
    ) == source

    source.write_bytes(b"drifted")
    with pytest.raises(RuntimeError, match=r"^frozen_file_drift:fixture$"):
        verify_frozen_file(tmp_path, protocol, "fixture")
    with pytest.raises(RuntimeError, match=r"^frozen_file_drift:fixture$"):
        verify_frozen_payload(tmp_path, protocol, "fixture", b"drifted")


def test_llm_eval_builder_reproduces_frozen_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = (
        ROOT / "experiments" / "mind_llm_tournament" / "build_eval_sets.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_baxy_llm_eval_builder_test",
        script,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured: dict[str, bytes] = {}

    def capture(path: Path, payload: bytes) -> None:
        captured[path.name] = payload

    monkeypatch.setattr(module, "replace_bytes_atomically", capture)
    module.main()

    assert hashlib.sha256(captured["sampled_cases.jsonl"]).hexdigest() == (
        EXPECTED_LLM_SAMPLED_SHA256
    )
    assert hashlib.sha256(captured["conversation_probes.jsonl"]).hexdigest() == (
        EXPECTED_LLM_PROBES_SHA256
    )


def test_hashed_router_sources_are_checked_out_with_lf_bytes() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    hashed_text_paths = (
        "src/baxy_mind/tools/router_bank_sources.py",
        "src/baxy_mind/tools/data/router_cases.jsonl",
        "src/baxy_mind/data/intent_bank.jsonl",
        "experiments/mind_router_spike/dev_probes.py",
        "experiments/mind_router_spike/data/core_hello.json",
        "experiments/mind_llm_tournament/data/*.jsonl",
    )

    for path in hashed_text_paths:
        assert f"/{path} text eol=lf" in attributes


def test_router_case_extractor_reproduces_the_canonical_input(tmp_path: Path) -> None:
    output = tmp_path / "router_cases.jsonl"
    cases = build_cases()

    write_cases(cases, output)

    assert len(cases) == 675
    assert sha256(output) == EXPECTED_CASES_SHA256
    assert output.read_bytes() == DEFAULT_CASES.read_bytes()


def test_router_bank_builder_preserves_the_frozen_bank_and_pool(
    tmp_path: Path,
) -> None:
    output = tmp_path / "intent_bank.jsonl"

    result = build_bank(output_path=output)

    assert (result.rows, result.labels, result.ambiguous) == (638, 40, 0)
    assert result.sha256 == EXPECTED_BANK_SHA256
    assert sha256(output) == EXPECTED_BANK_SHA256
    assert output.read_bytes() == DEFAULT_OUTPUT.read_bytes()

    rows = [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 638
    assert len({row["label"] for row in rows}) == 40

    pool = DEFAULT_OUTPUT.with_name("intent_bank.embeddings.npy")
    metadata = json.loads(
        DEFAULT_OUTPUT.with_name("intent_bank.embeddings.json").read_text(
            encoding="utf-8"
        )
    )
    assert sha256(pool) == EXPECTED_POOL_SHA256
    assert metadata["bank_sha256"] == EXPECTED_BANK_SHA256
    assert metadata["pool_sha256"] == EXPECTED_POOL_SHA256
    assert metadata["rows"] == 638


def test_encoder_experiment_composes_the_canonical_bank_exactly() -> None:
    script = ROOT / "experiments" / "mind_router_spike" / "run_spike.py"
    spec = importlib.util.spec_from_file_location(
        "_baxy_router_spike_equivalence",
        script,
    )
    assert spec is not None and spec.loader is not None
    spike = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(spike)

    labels_by_text: dict[str, set[str]] = {}
    text_by_key: dict[str, str] = {}
    pairs = [
        *(
            (label, text)
            for label, exemplars in spike.ALL_POOLS.items()
            for text in exemplars
        ),
        *spike.corpus_exemplars(spike.load_cases()),
    ]
    for label, text in pairs:
        key = spike.identity_key(text)
        labels_by_text.setdefault(key, set()).add(label)
        text_by_key[key] = text
    experiment_rows = [
        {"label": next(iter(labels)), "text": text_by_key[key]}
        for key, labels in sorted(labels_by_text.items())
        if len(labels) == 1
    ]
    canonical_rows = [
        json.loads(line)
        for line in DEFAULT_OUTPUT.read_text(encoding="utf-8").splitlines()
    ]

    assert experiment_rows == canonical_rows


def test_router_bank_builder_cli_accepts_explicit_paths(tmp_path: Path) -> None:
    output = tmp_path / "intent_bank.jsonl"
    script = SRC / "baxy_mind" / "tools" / "build_bank.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--cases",
            str(DEFAULT_CASES),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "638 anclas, 40 clases, 0 ambiguos" in completed.stdout
    assert sha256(output) == EXPECTED_BANK_SHA256


def test_atomic_tool_output_allows_concurrent_replacements(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "shared.bin"
    payloads = (b"first", b"second")
    barrier = Barrier(len(payloads))
    synchronized_sources: set[Path] = set()
    synchronization_lock = Lock()
    real_replace = atomic_output.os.replace

    def synchronized_replace(source: Path, destination: Path) -> None:
        with synchronization_lock:
            first_attempt = source not in synchronized_sources
            synchronized_sources.add(source)
        if first_attempt:
            barrier.wait(timeout=5)
        real_replace(source, destination)

    monkeypatch.setattr(atomic_output.os, "replace", synchronized_replace)
    with ThreadPoolExecutor(max_workers=len(payloads)) as executor:
        futures = [
            executor.submit(
                atomic_output.replace_bytes_atomically,
                output,
                payload,
            )
            for payload in payloads
        ]
        for future in futures:
            future.result(timeout=5)

    assert output.read_bytes() in payloads
    assert not list(tmp_path.glob(".*.tmp"))


def test_atomic_replace_retries_permission_errors_with_a_fixed_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.tmp"
    destination = tmp_path / "destination.bin"
    source.write_bytes(b"complete")
    attempts = 0
    sleeps: list[float] = []
    real_replace = atomic_output.os.replace

    def transient_replace(current: Path, target: Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("sharing violation")
        real_replace(current, target)

    monkeypatch.setattr(atomic_output.os, "replace", transient_replace)
    monkeypatch.setattr(atomic_output.time, "sleep", sleeps.append)
    atomic_output._replace_with_bounded_retry(source, destination)

    assert attempts == 3
    assert sleeps == [
        atomic_output.REPLACE_RETRY_INITIAL_SECONDS,
        atomic_output.REPLACE_RETRY_INITIAL_SECONDS * 2,
    ]
    assert destination.read_bytes() == b"complete"

    sleeps.clear()
    monotonic_values = iter((0.0, 0.4, 1.0))
    monkeypatch.setattr(
        atomic_output.time,
        "monotonic",
        lambda: next(monotonic_values),
    )

    def persistent_denial(_source: Path, _destination: Path) -> None:
        raise PermissionError("persistent denial")

    monkeypatch.setattr(atomic_output.os, "replace", persistent_denial)
    with pytest.raises(PermissionError, match="persistent denial"):
        atomic_output._replace_with_bounded_retry(source, destination)
    assert sleeps == [atomic_output.REPLACE_RETRY_INITIAL_SECONDS]
