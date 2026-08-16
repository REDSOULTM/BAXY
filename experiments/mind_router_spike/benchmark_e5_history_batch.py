"""Gate two isolated E5 latency candidates without modifying the runtime.

Candidate A removes the current user turn from the semantic-evidence history
when the shell already appended that same normalized text.  Candidate B
pre-encodes the normalized objective and evidence query as one request-local
batch before the two production projections consume them.

The experiment deliberately keeps the candidates separate.  It:

* scans the complete canonical runtime and historical-message workloads for
  text-size effects;
* selects a deterministic, length-stratified E5 sample from both workloads;
* loads the attested 25,156-row vector cache without rebuilding it;
* compares singleton and paired-batch float32 embeddings bit for bit;
* compares exact neighbor order, scores, candidate families, one-sided
  evidence, probe output, and an advisory decision projection;
* reports paired latency, process-crossing counts, encoded bytes, and
  approximate token counts by objective-length and history bucket.

No raw workload text is written to the report.  This is a CPU-only research
harness under ``experiments/``; it does not edit product source, assets,
runtime manifests, models, or an installed BAXY.  By default it refuses to run
while a llama-server process is active so that an unrelated GPU campaign is
not perturbed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
import unicodedata
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


REPOSITORY = Path(__file__).resolve().parents[2]
SOURCE = REPOSITORY / "src"
sys.path.insert(0, str(SOURCE))

from baxy_mind.router import ProcessIntentRouter, SemanticEncoder  # noqa: E402
from baxy_mind.turn_evidence import (  # noqa: E402
    DEFAULT_CANDIDATE_NEIGHBORS,
    MAX_RETRIEVED_EVIDENCE,
    TurnEvidenceIndex,
    _normalized_text,
    load_abstention_policy,
)
from baxy_mind.turn_probe import OneSidedTurnEvidencePolicy  # noqa: E402


SCHEMA = "baxy.e5-history-batch-gate.v1"
SEED = "baxy-e5-history-batch-v1"
DEFAULT_RUNTIME_CORPUS = (
    REPOSITORY / "tests" / "data" / "turn_evidence_runtime.v1.jsonl"
)
DEFAULT_HISTORICAL_MESSAGES = (
    REPOSITORY / "tests" / "data" / "historical_messages.jsonl"
)
DEFAULT_POLICY = (
    SOURCE / "baxy_mind" / "data" / "turn_evidence_abstention_policy.v1.json"
)
DEFAULT_OUTPUT = (
    REPOSITORY / "artifacts" / "fixes" / "e5_history_batch_gate_20260729.json"
)
HISTORY_PROFILES = (
    "no_history",
    "shell_echo",
    "context_then_echo",
    "context_without_echo",
)
LENGTH_BUCKETS = (
    "000_032_bytes",
    "033_096_bytes",
    "097_256_bytes",
    "257_plus_bytes",
)
MAX_MISMATCH_EXAMPLES = 32


@dataclass(frozen=True, slots=True)
class WorkloadRow:
    case_id: str
    source: str
    source_id: str
    text: str
    expected_mode: str
    expected_families: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FlowCase:
    case_id: str
    source: str
    objective: str
    expected_mode: str
    expected_families: tuple[str, ...]
    history_profile: str
    history: tuple[dict[str, str], ...]
    length_bucket: str


@dataclass(slots=True)
class FlowResult:
    query: str
    total_ms: float
    preencode_ms: float
    candidate_ms: float
    evidence_ms: float
    crossings: int
    encoded_rows: int
    encoded_utf8_bytes: int
    encoded_approx_tokens: int
    crossing_ms: tuple[float, ...]
    objective_embedding: np.ndarray
    evidence_embedding: np.ndarray
    candidate_rank_ids: tuple[str, ...]
    candidate_rank_scores: tuple[str, ...]
    candidate_families: tuple[str, ...]
    evidence_rank_ids: tuple[str, ...]
    evidence_rank_scores: tuple[str, ...]
    probe_projection: tuple[bool, tuple[tuple[str, str], ...]]
    evidence: tuple[str, ...]
    decision_projection: str
    family_covered: bool
    unsafe_action_conversation_signal: bool


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_hash(*parts: object) -> str:
    material = "\0".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            yield value


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def _case_identity(source: str, source_id: str, text: str) -> str:
    return _stable_hash(source, source_id, _normalized(text))[:24]


def _load_runtime_rows(path: Path) -> list[WorkloadRow]:
    rows: list[WorkloadRow] = []
    for position, value in enumerate(_jsonl(path)):
        text = value.get("text")
        mode = value.get("mode")
        raw_families = value.get("families")
        if (
            not isinstance(text, str)
            or not _normalized(text)
            or mode not in {"conversation", "clarify", "action", "plan"}
            or not isinstance(raw_families, list)
        ):
            continue
        families = tuple(
            sorted(
                {
                    family
                    for family in raw_families
                    if isinstance(family, str) and family
                }
            )
        )
        source_id = str(value.get("source_id") or f"row:{position}")
        rows.append(
            WorkloadRow(
                case_id=_case_identity("runtime", source_id, text),
                source="runtime_25156",
                source_id=source_id,
                text=text,
                expected_mode=str(mode),
                expected_families=families,
            )
        )
    return rows


def _historical_mode(value: dict[str, Any]) -> str:
    row_class = value.get("class")
    if row_class in {
        "conversation_question",
        "feedback_failure",
        "no_action_constraint",
    }:
        return "conversation"
    operations = value.get("operations")
    if not isinstance(operations, list) or not operations:
        return "conversation"
    return (
        "plan" if bool(value.get("possible_chain")) or len(operations) > 1 else "action"
    )


def _historical_families(value: dict[str, Any]) -> tuple[str, ...]:
    operations = value.get("operations")
    if not isinstance(operations, list):
        return ()
    return tuple(
        sorted(
            {
                operation.split(".", 1)[0]
                for operation in operations
                if isinstance(operation, str) and "." in operation
            }
        )
    )


def _load_historical_rows(path: Path) -> list[WorkloadRow]:
    rows: list[WorkloadRow] = []
    for position, value in enumerate(_jsonl(path)):
        text = value.get("text_literal")
        if not isinstance(text, str):
            text = value.get("paraphrase")
        if (
            not isinstance(text, str)
            or not _normalized(text)
            or bool(value.get("redacted"))
        ):
            continue
        source_id = str(value.get("message_id") or f"row:{position}")
        rows.append(
            WorkloadRow(
                case_id=_case_identity("historical", source_id, text),
                source="historical_messages",
                source_id=source_id,
                text=text,
                expected_mode=_historical_mode(value),
                expected_families=_historical_families(value),
            )
        )
    return rows


def _length_bucket(text: str) -> str:
    size = len(text.encode("utf-8"))
    if size <= 32:
        return LENGTH_BUCKETS[0]
    if size <= 96:
        return LENGTH_BUCKETS[1]
    if size <= 256:
        return LENGTH_BUCKETS[2]
    return LENGTH_BUCKETS[3]


def _approx_tokens(text: str) -> int:
    """Cheap, explicitly approximate multilingual token count."""

    size = len(text.encode("utf-8"))
    return 0 if size == 0 else max(1, math.ceil(size / 4))


def _deterministic_sample(
    rows: Sequence[WorkloadRow],
    sample_size: int,
    seed: str,
) -> list[WorkloadRow]:
    if sample_size < 1 or sample_size >= len(rows):
        return sorted(
            rows,
            key=lambda row: _stable_hash(seed, row.source, row.case_id),
        )
    queues: dict[tuple[str, str], list[WorkloadRow]] = defaultdict(list)
    for row in rows:
        queues[(row.source, _length_bucket(row.text))].append(row)
    for key, queue in queues.items():
        queue.sort(
            key=lambda row: _stable_hash(seed, key, row.case_id),
            reverse=True,
        )
    selected: list[WorkloadRow] = []
    ordered_keys = sorted(queues)
    while len(selected) < sample_size:
        progressed = False
        for key in ordered_keys:
            if queues[key] and len(selected) < sample_size:
                selected.append(queues[key].pop())
                progressed = True
        if not progressed:
            break
    return selected


def _normalized_echo(text: str) -> str:
    words = text.split()
    if not words:
        return text
    return "  \t".join(words)


def _flow_cases(rows: Sequence[WorkloadRow]) -> list[FlowCase]:
    cases: list[FlowCase] = []
    for position, row in enumerate(rows):
        prior = rows[position - 1] if position else rows[-1]
        if _normalized(prior.text) == _normalized(row.text):
            prior = rows[(position + 1) % len(rows)]
        histories = {
            "no_history": (),
            "shell_echo": ({"role": "user", "content": _normalized_echo(row.text)},),
            "context_then_echo": (
                {"role": "user", "content": prior.text},
                {"role": "assistant", "content": "Entendido."},
                {"role": "user", "content": _normalized_echo(row.text)},
            ),
            "context_without_echo": (
                {"role": "user", "content": prior.text},
                {"role": "assistant", "content": "Entendido."},
            ),
        }
        for profile in HISTORY_PROFILES:
            cases.append(
                FlowCase(
                    case_id=_stable_hash(row.case_id, profile)[:24],
                    source=row.source,
                    objective=row.text,
                    expected_mode=row.expected_mode,
                    expected_families=row.expected_families,
                    history_profile=profile,
                    history=histories[profile],
                    length_bucket=_length_bucket(row.text),
                )
            )
    return cases


def _baseline_evidence_query(
    text: str,
    history: Sequence[dict[str, str]],
) -> str:
    """Literal copy of the current production query composition."""

    context: list[str] = []
    for turn in history[-4:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            compact = " ".join(content.split())
            if compact:
                context.append(f"{role}: {compact[:1_024]}")
    current = " ".join(text.split())[:2_048]
    return "\n".join([*context, f"user: {current}"])[-4_096:]


def _deduplicated_evidence_query(
    text: str,
    history: Sequence[dict[str, str]],
) -> str:
    """Candidate A, local to this harness.

    Only the final eligible history message can be removed, and only when it
    is a user message whose complete normalized content equals the complete
    normalized current turn.  A prior intentional repetition remains context.
    """

    current_complete = " ".join(text.split())
    eligible: list[tuple[str, str]] = []
    for turn in history[-4:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            compact = " ".join(content.split())
            if compact:
                eligible.append((role, compact))
    if eligible and eligible[-1][0] == "user" and eligible[-1][1] == current_complete:
        eligible.pop()
    context = [f"{role}: {content[:1_024]}" for role, content in eligible]
    current = current_complete[:2_048]
    return "\n".join([*context, f"user: {current}"])[-4_096:]


def _active_llama_server_pids() -> tuple[int, ...]:
    try:
        import psutil

        pids = []
        try:
            for process in psutil.process_iter(("pid", "name")):
                name = str(process.info.get("name") or "").casefold()
                if name in {"llama-server", "llama-server.exe"}:
                    pids.append(int(process.info["pid"]))
        except psutil.Error:
            pass
        return tuple(sorted(pids))
    except (ImportError, OSError):
        pass
    if os.name != "nt":
        return ()
    try:
        result = subprocess.run(
            [
                "tasklist",
                "/FI",
                "IMAGENAME eq llama-server.exe",
                "/FO",
                "CSV",
                "/NH",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ()
    pids = []
    for line in result.stdout.splitlines():
        fields = [field.strip().strip('"') for field in line.split('","')]
        if len(fields) >= 2 and fields[0].casefold() == "llama-server.exe":
            try:
                pids.append(int(fields[1].replace(",", "")))
            except ValueError:
                continue
    return tuple(sorted(pids))


def _discover_metadata(runtime_corpus: Path) -> Path:
    local_data = os.environ.get("LOCALAPPDATA", "").strip()
    if not local_data:
        raise RuntimeError("LOCALAPPDATA unavailable; pass --metadata")
    cache = Path(local_data) / "BAXYRuntime" / "turn-evidence"
    source_sha256 = _sha256_file(runtime_corpus)
    candidates: list[Path] = []
    for path in cache.glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(value, dict)
            and value.get("source_sha256") == source_sha256
            and value.get("contains_text") is False
        ):
            candidates.append(path)
    if not candidates:
        raise RuntimeError("no attested vector cache matches the runtime corpus")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def _load_index(
    metadata_path: Path,
    runtime_corpus: Path,
) -> tuple[TurnEvidenceIndex, dict[str, Any]]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("turn-evidence metadata is not an object")
    source_sha256 = _sha256_file(runtime_corpus)
    if metadata.get("source_sha256") != source_sha256:
        raise ValueError("metadata does not bind the selected runtime corpus")
    encoder_identity = str(metadata.get("encoder_identity") or "")
    index = TurnEvidenceIndex._load_cache(
        metadata_path.parent,
        metadata_path.stem,
        source_sha256=source_sha256,
        encoder_identity=encoder_identity,
    )
    if index is None:
        raise ValueError("the attested turn-evidence cache failed validation")
    return index, metadata


class RequestLocalEncoder:
    """Mirror request-local exact-row caching and count physical calls."""

    def __init__(self, encode: Callable[[Sequence[str]], Any]) -> None:
        self._encode = encode
        self.rows: dict[str, np.ndarray] = {}
        self.crossing_ms: list[float] = []
        self.encoded_rows = 0
        self.encoded_utf8_bytes = 0
        self.encoded_approx_tokens = 0

    @property
    def crossings(self) -> int:
        return len(self.crossing_ms)

    def __call__(self, texts: Sequence[str]) -> np.ndarray:
        batch = tuple(texts)
        if not batch:
            raise ValueError("empty encoder batch")
        missing = tuple(dict.fromkeys(text for text in batch if text not in self.rows))
        if missing:
            started_at = time.perf_counter_ns()
            matrix = np.asarray(self._encode(missing), dtype=np.float32)
            elapsed_ms = (time.perf_counter_ns() - started_at) / 1_000_000
            if (
                matrix.ndim != 2
                or matrix.shape[0] != len(missing)
                or not np.isfinite(matrix).all()
            ):
                raise ValueError("encoder returned an invalid matrix")
            self.crossing_ms.append(elapsed_ms)
            self.encoded_rows += len(missing)
            self.encoded_utf8_bytes += sum(
                len(text.encode("utf-8")) for text in missing
            )
            self.encoded_approx_tokens += sum(_approx_tokens(text) for text in missing)
            for text, row in zip(missing, matrix, strict=True):
                frozen = row.copy()
                frozen.flags.writeable = False
                self.rows[text] = frozen
            if len(missing) == len(batch):
                return matrix
        return np.stack([self.rows[text] for text in batch], axis=0)


def _float_hex(value: float) -> str:
    return float(value).hex()


def _rank_projection(
    index: TurnEvidenceIndex,
    objective_embedding: np.ndarray,
    evidence_embedding: np.ndarray,
    candidate_families: tuple[str, ...],
    policy: OneSidedTurnEvidencePolicy,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    candidate_limit = max(DEFAULT_CANDIDATE_NEIGHBORS * 8, 64)
    candidate_ranking = index._rank_candidate_training_query(
        objective_embedding,
        limit=candidate_limit,
    )
    operations = tuple(f"{family}.benchmark" for family in candidate_families)
    evidence_limit = max(
        MAX_RETRIEVED_EVIDENCE * 32,
        policy.neighbors * 16,
        128,
    )
    evidence_ranking = index._rank_query(
        evidence_embedding,
        operations,
        limit=evidence_limit,
    )
    return (
        tuple(match.record.source_id for match in candidate_ranking),
        tuple(_float_hex(match.score) for match in candidate_ranking),
        tuple(match.record.source_id for match in evidence_ranking),
        tuple(_float_hex(match.score) for match in evidence_ranking),
    )


def _execute_flow(
    *,
    case: FlowCase,
    index: TurnEvidenceIndex,
    policy: OneSidedTurnEvidencePolicy,
    encode: Callable[[Sequence[str]], Any],
    query_builder: Callable[[str, Sequence[dict[str, str]]], str],
    preencode: bool,
) -> FlowResult:
    query = query_builder(case.objective, case.history)
    normalized_objective = _normalized_text(case.objective)
    normalized_query = _normalized_text(query)
    if normalized_objective is None or normalized_query is None:
        raise ValueError(f"case {case.case_id} is not encodable")
    request_encoder = RequestLocalEncoder(encode)
    started_total = time.perf_counter_ns()
    preencode_ms = 0.0
    if preencode:
        started_at = time.perf_counter_ns()
        request_encoder((normalized_objective, normalized_query))
        preencode_ms = (time.perf_counter_ns() - started_at) / 1_000_000
    started_at = time.perf_counter_ns()
    candidate_families = index.candidate_families(
        case.objective,
        request_encoder,
    )
    candidate_ms = (time.perf_counter_ns() - started_at) / 1_000_000
    operations = tuple(f"{family}.benchmark" for family in candidate_families)
    started_at = time.perf_counter_ns()
    evidence_value = index.retrieve(
        query,
        request_encoder,
        operations,
        policy=policy,
    )
    evidence_ms = (time.perf_counter_ns() - started_at) / 1_000_000
    total_ms = (time.perf_counter_ns() - started_total) / 1_000_000

    objective_embedding = request_encoder.rows[normalized_objective]
    evidence_embedding = request_encoder.rows[normalized_query]
    (
        candidate_rank_ids,
        candidate_rank_scores,
        evidence_rank_ids,
        evidence_rank_scores,
    ) = _rank_projection(
        index,
        objective_embedding,
        evidence_embedding,
        candidate_families,
        policy,
    )
    emits_conversation, distribution = policy.probe.emits_conversation(
        evidence_embedding
    )
    probe_projection = (
        emits_conversation,
        tuple(
            (label, _float_hex(probability))
            for label, probability in sorted(distribution.items())
        ),
    )
    evidence = tuple(_canonical_json(item) for item in evidence_value)
    decision_projection = _canonical_json(
        {
            "candidate_families": candidate_families,
            "evidence": evidence_value,
            "probe_emits_conversation": emits_conversation,
        }
    )
    family_covered = not case.expected_families or not set(
        case.expected_families
    ).isdisjoint(candidate_families)
    unsafe_action_conversation_signal = (
        case.expected_mode in {"action", "plan"} and emits_conversation
    )
    return FlowResult(
        query=query,
        total_ms=total_ms,
        preencode_ms=preencode_ms,
        candidate_ms=candidate_ms,
        evidence_ms=evidence_ms,
        crossings=request_encoder.crossings,
        encoded_rows=request_encoder.encoded_rows,
        encoded_utf8_bytes=request_encoder.encoded_utf8_bytes,
        encoded_approx_tokens=request_encoder.encoded_approx_tokens,
        crossing_ms=tuple(request_encoder.crossing_ms),
        objective_embedding=objective_embedding,
        evidence_embedding=evidence_embedding,
        candidate_rank_ids=candidate_rank_ids,
        candidate_rank_scores=candidate_rank_scores,
        candidate_families=candidate_families,
        evidence_rank_ids=evidence_rank_ids,
        evidence_rank_scores=evidence_rank_scores,
        probe_projection=probe_projection,
        evidence=evidence,
        decision_projection=decision_projection,
        family_covered=family_covered,
        unsafe_action_conversation_signal=(unsafe_action_conversation_signal),
    )


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def _latency_summary(results: Sequence[FlowResult]) -> dict[str, Any]:
    total = [result.total_ms for result in results]
    candidate = [result.candidate_ms for result in results]
    evidence = [result.evidence_ms for result in results]
    preencode = [result.preencode_ms for result in results]
    crossings = [value for result in results for value in result.crossing_ms]
    return {
        "cases": len(results),
        "total_ms": {
            "sum": round(sum(total), 6),
            "p50": round(_percentile(total, 50), 6),
            "p95": round(_percentile(total, 95), 6),
            "minimum": round(min(total, default=0.0), 6),
            "maximum": round(max(total, default=0.0), 6),
        },
        "candidate_families_ms": {
            "p50": round(_percentile(candidate, 50), 6),
            "p95": round(_percentile(candidate, 95), 6),
        },
        "evidence_ms": {
            "p50": round(_percentile(evidence, 50), 6),
            "p95": round(_percentile(evidence, 95), 6),
        },
        "preencode_ms": {
            "p50": round(_percentile(preencode, 50), 6),
            "p95": round(_percentile(preencode, 95), 6),
        },
        "physical_encoder_calls": sum(result.crossings for result in results),
        "physical_encoder_call_ms": {
            "p50": round(_percentile(crossings, 50), 6),
            "p95": round(_percentile(crossings, 95), 6),
        },
        "encoded_rows": sum(result.encoded_rows for result in results),
        "encoded_utf8_bytes": sum(result.encoded_utf8_bytes for result in results),
        "encoded_approx_tokens": sum(
            result.encoded_approx_tokens for result in results
        ),
    }


def _embedding_delta(
    baseline: np.ndarray,
    candidate: np.ndarray,
) -> tuple[bool, float, float]:
    exact = bool(np.array_equal(baseline, candidate))
    maximum_absolute = float(np.max(np.abs(baseline - candidate)))
    denominator = float(np.linalg.norm(baseline) * np.linalg.norm(candidate))
    cosine = float(np.dot(baseline, candidate) / denominator) if denominator else 0.0
    return exact, maximum_absolute, cosine


def _comparison(
    case: FlowCase,
    baseline: FlowResult,
    candidate: FlowResult,
) -> dict[str, Any]:
    objective_exact, objective_max_abs, objective_cosine = _embedding_delta(
        baseline.objective_embedding,
        candidate.objective_embedding,
    )
    evidence_exact, evidence_max_abs, evidence_cosine = _embedding_delta(
        baseline.evidence_embedding,
        candidate.evidence_embedding,
    )
    return {
        "case_id": case.case_id,
        "source": case.source,
        "length_bucket": case.length_bucket,
        "history_profile": case.history_profile,
        "query_changed": baseline.query != candidate.query,
        "query_utf8_bytes_saved": len(baseline.query.encode("utf-8"))
        - len(candidate.query.encode("utf-8")),
        "query_approx_tokens_saved": (
            _approx_tokens(baseline.query) - _approx_tokens(candidate.query)
        ),
        "objective_embedding_exact": objective_exact,
        "objective_embedding_max_abs": objective_max_abs,
        "objective_embedding_cosine": objective_cosine,
        "evidence_embedding_exact": evidence_exact,
        "evidence_embedding_max_abs": evidence_max_abs,
        "evidence_embedding_cosine": evidence_cosine,
        "candidate_rank_order_exact": (
            baseline.candidate_rank_ids == candidate.candidate_rank_ids
        ),
        "candidate_rank_scores_exact": (
            baseline.candidate_rank_scores == candidate.candidate_rank_scores
        ),
        "candidate_families_exact": (
            baseline.candidate_families == candidate.candidate_families
        ),
        "evidence_rank_order_exact": (
            baseline.evidence_rank_ids == candidate.evidence_rank_ids
        ),
        "evidence_rank_scores_exact": (
            baseline.evidence_rank_scores == candidate.evidence_rank_scores
        ),
        "probe_projection_exact": (
            baseline.probe_projection == candidate.probe_projection
        ),
        "evidence_exact": baseline.evidence == candidate.evidence,
        "decision_projection_exact": (
            baseline.decision_projection == candidate.decision_projection
        ),
        "family_coverage_loss": (
            baseline.family_covered and not candidate.family_covered
        ),
        "new_unsafe_action_conversation_signal": (
            not baseline.unsafe_action_conversation_signal
            and candidate.unsafe_action_conversation_signal
        ),
        "baseline_crossings": baseline.crossings,
        "candidate_crossings": candidate.crossings,
        "crossings_saved": baseline.crossings - candidate.crossings,
        "paired_total_ms_saved": baseline.total_ms - candidate.total_ms,
    }


QUALITY_FIELDS = (
    "objective_embedding_exact",
    "evidence_embedding_exact",
    "candidate_rank_order_exact",
    "candidate_rank_scores_exact",
    "candidate_families_exact",
    "evidence_rank_order_exact",
    "evidence_rank_scores_exact",
    "probe_projection_exact",
    "evidence_exact",
    "decision_projection_exact",
)


def _comparison_summary(
    comparisons: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    exact_counts = {
        field: sum(bool(item[field]) for item in comparisons)
        for field in QUALITY_FIELDS
    }
    paired_savings = [float(item["paired_total_ms_saved"]) for item in comparisons]
    maximum_objective_delta = max(
        (float(item["objective_embedding_max_abs"]) for item in comparisons),
        default=0.0,
    )
    maximum_evidence_delta = max(
        (float(item["evidence_embedding_max_abs"]) for item in comparisons),
        default=0.0,
    )
    mismatches = []
    for item in comparisons:
        failed = [field for field in QUALITY_FIELDS if not bool(item[field])]
        if not failed:
            continue
        mismatches.append(
            {
                "case_id": item["case_id"],
                "source": item["source"],
                "length_bucket": item["length_bucket"],
                "history_profile": item["history_profile"],
                "query_changed": item["query_changed"],
                "failed_exact_fields": failed,
                "objective_embedding_max_abs": item["objective_embedding_max_abs"],
                "evidence_embedding_max_abs": item["evidence_embedding_max_abs"],
            }
        )
        if len(mismatches) >= MAX_MISMATCH_EXAMPLES:
            break
    return {
        "paired_cases": len(comparisons),
        "exact_counts": exact_counts,
        "exact_rates": {
            field: (round(count / len(comparisons), 9) if comparisons else 0.0)
            for field, count in exact_counts.items()
        },
        "maximum_objective_embedding_abs_delta": (maximum_objective_delta),
        "maximum_evidence_embedding_abs_delta": maximum_evidence_delta,
        "family_coverage_losses": sum(
            bool(item["family_coverage_loss"]) for item in comparisons
        ),
        "new_unsafe_action_conversation_signals": sum(
            bool(item["new_unsafe_action_conversation_signal"]) for item in comparisons
        ),
        "query_changes": sum(bool(item["query_changed"]) for item in comparisons),
        "query_utf8_bytes_saved": sum(
            int(item["query_utf8_bytes_saved"]) for item in comparisons
        ),
        "query_approx_tokens_saved": sum(
            int(item["query_approx_tokens_saved"]) for item in comparisons
        ),
        "physical_crossings_saved": sum(
            int(item["crossings_saved"]) for item in comparisons
        ),
        "paired_total_ms_saved": {
            "sum": round(sum(paired_savings), 6),
            "p50": round(_percentile(paired_savings, 50), 6),
            "p95": round(_percentile(paired_savings, 95), 6),
        },
        "mismatch_examples": mismatches,
    }


def _bucket_report(
    cases: Sequence[FlowCase],
    baseline_results: Sequence[FlowResult],
    candidate_results: Sequence[FlowResult],
    comparisons: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    buckets: dict[str, Any] = {}
    for dimension, accessor in (
        ("length", lambda case: case.length_bucket),
        ("history", lambda case: case.history_profile),
        (
            "length_x_history",
            lambda case: f"{case.length_bucket}|{case.history_profile}",
        ),
    ):
        values: dict[str, Any] = {}
        names = sorted({accessor(case) for case in cases})
        for name in names:
            indices = [
                index for index, case in enumerate(cases) if accessor(case) == name
            ]
            values[name] = {
                "baseline": _latency_summary(
                    [baseline_results[index] for index in indices]
                ),
                "candidate": _latency_summary(
                    [candidate_results[index] for index in indices]
                ),
                "comparison": _comparison_summary(
                    [comparisons[index] for index in indices]
                ),
            }
        buckets[dimension] = values
    return buckets


def _run_experiment(
    *,
    name: str,
    cases: Sequence[FlowCase],
    repeats: int,
    seed: str,
    index: TurnEvidenceIndex,
    policy: OneSidedTurnEvidencePolicy,
    encode: Callable[[Sequence[str]], Any],
) -> dict[str, Any]:
    if name == "A_history_dedup":
        baseline_query = _baseline_evidence_query
        candidate_query = _deduplicated_evidence_query
        candidate_preencode = False
    elif name == "B_request_local_batch":
        baseline_query = _baseline_evidence_query
        candidate_query = _baseline_evidence_query
        candidate_preencode = True
    else:
        raise ValueError(f"unknown experiment: {name}")

    expanded_cases: list[FlowCase] = []
    baseline_results: list[FlowResult] = []
    candidate_results: list[FlowResult] = []
    comparisons: list[dict[str, Any]] = []
    for repeat in range(repeats):
        ordered_cases = sorted(
            cases,
            key=lambda case: _stable_hash(
                seed,
                name,
                repeat,
                case.case_id,
            ),
        )
        for case in ordered_cases:
            candidate_first = (
                int(
                    _stable_hash(
                        seed,
                        name,
                        repeat,
                        case.case_id,
                        "arm-order",
                    )[:8],
                    16,
                )
                % 2
                == 0
            )
            results: dict[str, FlowResult] = {}
            arms = (
                ("candidate", "baseline")
                if candidate_first
                else ("baseline", "candidate")
            )
            for arm in arms:
                results[arm] = _execute_flow(
                    case=case,
                    index=index,
                    policy=policy,
                    encode=encode,
                    query_builder=(
                        candidate_query if arm == "candidate" else baseline_query
                    ),
                    preencode=(candidate_preencode if arm == "candidate" else False),
                )
            baseline = results["baseline"]
            candidate = results["candidate"]
            expanded_cases.append(case)
            baseline_results.append(baseline)
            candidate_results.append(candidate)
            comparisons.append(_comparison(case, baseline, candidate))

    summary = _comparison_summary(comparisons)
    downstream_fields = (
        "candidate_rank_order_exact",
        "candidate_families_exact",
        "evidence_rank_order_exact",
        "probe_projection_exact",
        "evidence_exact",
        "decision_projection_exact",
    )
    downstream_exact = all(
        summary["exact_counts"][field] == len(comparisons)
        for field in downstream_fields
    )
    no_oracle_regression = (
        summary["family_coverage_losses"] == 0
        and summary["new_unsafe_action_conversation_signals"] == 0
    )
    latency_win = (
        summary["paired_total_ms_saved"]["p50"] > 0.0
        and summary["paired_total_ms_saved"]["p95"] > 0.0
    )
    expected_crossing_savings = (
        summary["physical_crossings_saved"] > 0
        if name == "B_request_local_batch"
        else True
    )
    return {
        "candidate": name,
        "isolation": (
            "history_dedup_only"
            if name == "A_history_dedup"
            else "request_local_batch_only"
        ),
        "sampled_base_rows": len(cases) // len(HISTORY_PROFILES),
        "flow_cases_per_repeat": len(cases),
        "repeats": repeats,
        "baseline": _latency_summary(baseline_results),
        "candidate_measurement": _latency_summary(candidate_results),
        "comparison": summary,
        "buckets": _bucket_report(
            expanded_cases,
            baseline_results,
            candidate_results,
            comparisons,
        ),
        "gate": {
            "downstream_projections_exact": downstream_exact,
            "no_available_oracle_regression": no_oracle_regression,
            "paired_latency_p50_and_p95_win": latency_win,
            "expected_crossing_savings": expected_crossing_savings,
            "promotion_ready": (
                downstream_exact
                and no_oracle_regression
                and latency_win
                and expected_crossing_savings
            ),
            "actual_llm_decisions_evaluated": False,
            "interpretation": (
                "promotion_ready is necessary, not sufficient; run the "
                "canonical turn-policy gate before any production change"
            ),
        },
    }


def _lexical_scan(cases: Sequence[FlowCase]) -> dict[str, Any]:
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for case in cases:
        baseline = _baseline_evidence_query(case.objective, case.history)
        candidate = _deduplicated_evidence_query(
            case.objective,
            case.history,
        )
        keys = (
            "all",
            f"length:{case.length_bucket}",
            f"history:{case.history_profile}",
            (f"length_x_history:{case.length_bucket}|{case.history_profile}"),
        )
        for key in keys:
            bucket = totals[key]
            bucket["cases"] += 1
            bucket["query_changes"] += int(baseline != candidate)
            bucket["baseline_utf8_bytes"] += len(baseline.encode("utf-8"))
            bucket["candidate_utf8_bytes"] += len(candidate.encode("utf-8"))
            bucket["baseline_approx_tokens"] += _approx_tokens(baseline)
            bucket["candidate_approx_tokens"] += _approx_tokens(candidate)
    return {
        key: {
            **dict(value),
            "utf8_bytes_saved": (
                value["baseline_utf8_bytes"] - value["candidate_utf8_bytes"]
            ),
            "approx_tokens_saved": (
                value["baseline_approx_tokens"] - value["candidate_approx_tokens"]
            ),
        }
        for key, value in sorted(totals.items())
    }


def _source_identity(path: Path, accepted_rows: int) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        source_lines = sum(1 for _ in handle)
    return {
        "path": str(path.resolve()),
        "sha256": _sha256_file(path),
        "source_lines": source_lines,
        "accepted_workload_rows": accepted_rows,
        "utf8_bytes": path.stat().st_size,
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gate isolated E5 history-dedup and pair-batch candidates."
    )
    parser.add_argument(
        "--runtime-corpus",
        type=Path,
        default=DEFAULT_RUNTIME_CORPUS,
    )
    parser.add_argument(
        "--historical-messages",
        type=Path,
        default=DEFAULT_HISTORICAL_MESSAGES,
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--sample-size",
        type=int,
        default=96,
        help="base texts before applying all four history profiles; 0 means all",
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--seed", default=SEED)
    parser.add_argument(
        "--torch-threads",
        type=int,
        default=0,
        help="direct mode only; 0 preserves the registered runtime default",
    )
    parser.add_argument(
        "--encoder-mode",
        choices=("process", "direct"),
        default="process",
        help="process measures the production JSONL/IPC crossing",
    )
    parser.add_argument(
        "--allow-llama-server",
        action="store_true",
        help="explicitly permit a concurrent llama-server process",
    )
    args = parser.parse_args()
    if args.sample_size < 0:
        parser.error("--sample-size cannot be negative")
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if args.torch_threads < 0:
        parser.error("--torch-threads cannot be negative")
    return args


def main() -> int:
    args = _arguments()
    active_llama_pids = _active_llama_server_pids()
    if active_llama_pids and not args.allow_llama_server:
        raise SystemExit(
            "refusing to perturb an active llama-server campaign; "
            f"active process count={len(active_llama_pids)}"
        )

    runtime_corpus = args.runtime_corpus.resolve(strict=True)
    historical_messages = args.historical_messages.resolve(strict=True)
    policy_path = args.policy.resolve(strict=True)
    metadata_path = (
        args.metadata.resolve(strict=True)
        if args.metadata is not None
        else _discover_metadata(runtime_corpus)
    )
    runtime_rows = _load_runtime_rows(runtime_corpus)
    historical_rows = _load_historical_rows(historical_messages)
    workload_rows = [*runtime_rows, *historical_rows]
    if not workload_rows:
        raise RuntimeError("the canonical workloads are empty")
    e5_workload_rows = [
        row for row in workload_rows if _normalized_text(row.text) is not None
    ]
    if not e5_workload_rows:
        raise RuntimeError("the canonical workloads have no E5-eligible text")

    index, metadata = _load_index(metadata_path, runtime_corpus)
    policy = load_abstention_policy(policy_path)
    if policy is None or not policy.is_compatible(
        source_sha256=index.report.source_sha256,
        encoder_identity=index.encoder_identity,
        dimensions=index.dimensions,
    ):
        raise RuntimeError("the selected one-sided policy is incompatible")

    selected = _deterministic_sample(
        e5_workload_rows,
        args.sample_size,
        args.seed,
    )
    sampled_cases = _flow_cases(selected)
    lexical_cases = _flow_cases(workload_rows)

    random.seed(args.seed)
    np.random.seed(int(_stable_hash(args.seed, "numpy")[:8], 16))
    model_started_at = time.perf_counter_ns()
    process_encoder: ProcessIntentRouter | None = None
    if args.encoder_mode == "process":
        process_encoder = ProcessIntentRouter()

        def encode(texts: Sequence[str]) -> Any:
            if process_encoder is None:
                raise RuntimeError("process encoder is unavailable")
            return process_encoder.encode(tuple(texts), timeout=180.0)

    else:
        direct_encoder = SemanticEncoder(device="cpu")
        if args.torch_threads:
            import torch

            torch.set_num_threads(args.torch_threads)
        encode = direct_encoder.encode

    try:
        # Warm both singleton and pair shapes outside measured cases. In
        # process mode the first call also waits for the registered worker.
        encode(("warmup",))
        encode(("warmup short", "warmup with a longer second sequence"))
        model_load_ms = (time.perf_counter_ns() - model_started_at) / 1_000_000

        campaign_started_at = time.perf_counter_ns()
        experiment_a = _run_experiment(
            name="A_history_dedup",
            cases=sampled_cases,
            repeats=args.repeats,
            seed=args.seed,
            index=index,
            policy=policy,
            encode=encode,
        )
        experiment_b = _run_experiment(
            name="B_request_local_batch",
            cases=sampled_cases,
            repeats=args.repeats,
            seed=args.seed,
            index=index,
            policy=policy,
            encode=encode,
        )
        campaign_ms = (time.perf_counter_ns() - campaign_started_at) / 1_000_000
    finally:
        if process_encoder is not None:
            process_encoder.close(timeout=5.0)

    records = metadata.get("records")
    report = {
        "schema": SCHEMA,
        "status": (
            "passed"
            if experiment_a["gate"]["promotion_ready"]
            and experiment_b["gate"]["promotion_ready"]
            else "candidate_rejected_or_requires_full_gate"
        ),
        "scope": {
            "runtime_modified": False,
            "assets_modified": False,
            "installation_modified": False,
            "llm_started": False,
            "actual_llm_decisions_evaluated": False,
            "cpu_only": True,
            "raw_workload_text_written": False,
            "encoder_mode": args.encoder_mode,
            "process_transport_measured": args.encoder_mode == "process",
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpus": os.cpu_count(),
            "torch_threads_override": args.torch_threads,
            "encoder_mode": args.encoder_mode,
            "active_llama_server_count_at_start": len(active_llama_pids),
            "concurrent_llama_server_explicitly_allowed": bool(args.allow_llama_server),
            "model_load_ms": round(model_load_ms, 6),
            "campaign_ms": round(campaign_ms, 6),
        },
        "inputs": {
            "runtime_corpus": _source_identity(
                runtime_corpus,
                len(runtime_rows),
            ),
            "historical_messages": _source_identity(
                historical_messages,
                len(historical_rows),
            ),
            "policy": {
                "path": str(policy_path),
                "sha256": _sha256_file(policy_path),
                "validation_fingerprint": policy.validation_fingerprint,
            },
            "vector_cache": {
                "metadata_path": str(metadata_path),
                "metadata_sha256": _sha256_file(metadata_path),
                "vectors_path": str(metadata_path.with_suffix(".npy")),
                "vectors_sha256": _sha256_file(metadata_path.with_suffix(".npy")),
                "records": (len(records) if isinstance(records, list) else None),
                "dimensions": index.dimensions,
                "encoder_identity": index.encoder_identity,
                "source_sha256": index.report.source_sha256,
            },
        },
        "selection": {
            "seed": args.seed,
            "all_workload_rows": len(workload_rows),
            "e5_eligible_workload_rows": len(e5_workload_rows),
            "sampled_base_rows": len(selected),
            "sampled_flow_cases": len(sampled_cases),
            "history_profiles": list(HISTORY_PROFILES),
            "length_buckets": list(LENGTH_BUCKETS),
            "repeats": args.repeats,
            "sampled_case_ids_sha256": hashlib.sha256(
                "\n".join(sorted(case.case_id for case in sampled_cases)).encode(
                    "ascii"
                )
            ).hexdigest(),
        },
        "full_workload_history_dedup_lexical_scan": _lexical_scan(lexical_cases),
        "experiments": {
            "A_history_dedup": experiment_a,
            "B_request_local_batch": experiment_b,
        },
        "promotion_rule": (
            "No candidate may enter production from this experiment alone. "
            "It must first pass every exact projection here and then the "
            "canonical turn-policy/corpus gates with no safety or quality loss."
        ),
    }
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, output_path)
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "status": report["status"],
                "output": str(output_path),
                "workload_rows": len(workload_rows),
                "sampled_flow_cases": len(sampled_cases),
                "A_promotion_ready": experiment_a["gate"]["promotion_ready"],
                "B_promotion_ready": experiment_b["gate"]["promotion_ready"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
