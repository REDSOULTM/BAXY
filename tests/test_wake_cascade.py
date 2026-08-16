from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from baxy_mind.wake_cascade import (
    CALIBRATION_REPORT_FILENAME,
    HyperspotterCascadeDetector,
    WakeCascadeConfigurationError,
    has_strict_exact_alias,
    has_strict_leading_alias,
    load_wake_cascade_candidate_config,
    load_wake_cascade_config,
    match_bounded_lexical_wake,
    match_suffix_independent_endpoint_wake,
    same_window_consensus,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(tmp_path: Path) -> Path:
    graphs = []
    for index in range(2):
        path = tmp_path / f"upstream-{index}.onnx"
        path.write_bytes(f"upstream-{index}".encode())
        graphs.append(path)
    verifier = tmp_path / "verifier.onnx"
    verifier.write_bytes(b"verifier")
    filters = tmp_path / "mel.npy"
    np.save(filters, np.ones((80, 201), dtype=np.float32))
    assets = {
        "upstreamGraphSha256": [_sha(path) for path in graphs],
        "melFiltersSha256": _sha(filters),
        "logmelVerifierSha256": _sha(verifier),
    }
    report = {
        "schema": "baxy-wake-cascade-gate-v1",
        "role": "validation",
        "candidateFrozen": True,
        "corpusFrozen": True,
        "physicalRoomValidated": True,
        "promotable": True,
        "assets": assets,
        "metrics": {
            "positiveFiles": 48,
            "positiveAcceptedFiles": 48,
            "negativeFiles": 1000,
            "negativeFalseActivations": 0,
            "farConfidence": 0.95,
            "farUpperConfidencePerHour": 0.09,
        },
    }
    report_path = tmp_path / CALIBRATION_REPORT_FILENAME
    report_path.write_text(json.dumps(report), encoding="utf-8")
    manifest = {
        "schema": "baxy-wake-cascade-v1",
        "backend": "onnxruntime-hyperspotter-logmel-cascade",
        "phrase": "Baxy",
        "sampleRate": 16000,
        "windowSamples": 48000,
        "hopSamples": 4000,
        "historyWindows": 20,
        "debounceSeconds": 2.0,
        "primaryLogitGte": 0.5,
        "secondaryLogitGte": 0.3,
        "acousticAliases": ["baxy", "baxi", "basi", "bakse"],
        "lexicalAliases": ["baxy", "baxi", "boxy"],
        "upstreamModels": [
            {"graph": path.name, "graphSha256": _sha(path)} for path in graphs
        ],
        "melFilters": filters.name,
        "melFiltersSha256": _sha(filters),
        "logmelVerifier": {
            "graph": verifier.name,
            "graphSha256": _sha(verifier),
            "scoreGte": 3.0,
        },
        "calibration": {
            "approved": True,
            "report": CALIBRATION_REPORT_FILENAME,
            "reportSha256": _sha(report_path),
        },
    }
    path = tmp_path / "baxy-wake-cascade-v1.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


class _UpstreamSession:
    def __init__(self, candidate: bool) -> None:
        self.candidate = candidate

    def run(self, outputs, inputs):
        values = [0.6, 0.4, -1.0, -2.0] if self.candidate else [0.4, 0.2, -1.0, -2.0]
        return [np.asarray([values], dtype=np.float32)]


class _VerifierSession:
    def __init__(self, score: float) -> None:
        self.score = score

    def run(self, outputs, inputs):
        count = len(inputs["logmel"])
        return [np.full((count, 1), self.score, dtype=np.float32)]


def test_calibrated_manifest_binds_all_assets(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    config = load_wake_cascade_config(manifest)
    assert config.verifier_threshold == 3.0
    assert config.history_windows == 20

    report = tmp_path / CALIBRATION_REPORT_FILENAME
    report.write_text(report.read_text() + " ", encoding="utf-8")
    with pytest.raises(
        WakeCascadeConfigurationError,
        match="wake_cascade_calibration_report_hash_mismatch",
    ):
        load_wake_cascade_config(manifest)


@pytest.mark.parametrize("text", ["Baxy", "BOXy!", " baxi. "])
def test_strict_alias_accepts_only_the_entire_name(text: str) -> None:
    assert has_strict_exact_alias(text, frozenset(("baxy", "baxi", "boxy")))


@pytest.mark.parametrize("text", ["Vaxi", "Foxy", "Baxy abre Chrome", "Back soon"])
def test_strict_alias_rejects_confusables_and_commands(text: str) -> None:
    assert not has_strict_exact_alias(text, frozenset(("baxy", "baxi", "boxy")))


def test_leading_alias_allows_a_command_without_accepting_a_confusable() -> None:
    aliases = frozenset(("baxy", "baxi", "boxy"))
    assert has_strict_leading_alias("Baxy, abre Chrome", aliases)
    assert not has_strict_leading_alias("Vaxi, abre Chrome", aliases)


@pytest.mark.parametrize(
    ("transcript", "command"),
    [
        ("Baxy abre la calculadora", "abre la calculadora"),
        ("Vaxi open the calculator", "open the calculator"),
        ("Vasi what time is it", "what time is it"),
        ("Vasi what the maze it", "what the maze it"),
        ("Vaxi", ""),
        ("Basi", ""),
        ("Backsy open Spotify", "open Spotify"),
        ("Bakse dime la hora", "dime la hora"),
        ("Waxi open the calculator", "open the calculator"),
        ("Waxi", ""),
        ("Vas y pon pausa", "pon pausa"),
        ("Va si dímela ahora", "dímela ahora"),
        ("Basic how much battery is left", "how much battery is left"),
        ("Basic order and lamar manyana", "order and lamar manyana"),
        ("Basic word and Lama Miniana", "word and Lama Miniana"),
        ("Basic 1 0 3 0", "1 0 3 0"),
        ("They see how much battery is left", "how much battery is left"),
        ("Vaxi take a screenshot", "take a screenshot"),
        ("Vas y muestrame los procesos activos", "muestrame los procesos activos"),
        ("Basic lower the screen brightness", "lower the screen brightness"),
    ],
)
def test_bounded_lexical_matcher_preserves_measured_command_context(
    transcript: str, command: str
) -> None:
    match = match_bounded_lexical_wake(
        (transcript,), frozenset(("baxy", "baxi", "boxy"))
    )
    assert match is not None
    assert match.command == command


@pytest.mark.parametrize(
    "transcript",
    [
        "Maxi viene en camino",
        "Back see whether the light is on",
        "La caja esta vacia",
        "basi ends as that",
        "basic",
        "Waxi comes tomorrow",
        "these front doors can be baxy",
        "this is a basic example",
        "Basic arithmetic is useful",
        "Vasi comes tomorrow",
        "Basic lower layers remain unchanged",
    ],
)
def test_bounded_lexical_matcher_rejects_opened_confusables(transcript: str) -> None:
    assert (
        match_bounded_lexical_wake((transcript,), frozenset(("baxy", "baxi", "boxy")))
        is None
    )


def test_bounded_lexical_matcher_requires_acoustic_score_for_bare_they_see() -> None:
    aliases = frozenset(("baxy", "baxi", "boxy"))
    assert match_bounded_lexical_wake(("They see",), aliases) is None
    assert (
        match_bounded_lexical_wake(
            ("They see",),
            aliases,
            verifier_score=3.99,
            phonetic_confusion_score_gte=4.0,
        )
        is None
    )
    match = match_bounded_lexical_wake(
        ("They see",),
        aliases,
        verifier_score=4.0,
        phonetic_confusion_score_gte=4.0,
    )
    assert match is not None
    assert match.method == "score_gated_bare_they_see_confusion"


@pytest.mark.parametrize(
    "transcript",
    [
        "Basic turn on airplane mode",
        "Basic lower the screen brightness",
        "Basi turn on airplane mode",
        "Vas y muestrame los procesos activos",
        "They see how much battery is left",
    ],
)
def test_suffix_independent_endpoint_rejects_ambiguous_pronunciations(
    transcript: str,
) -> None:
    aliases = frozenset(("baxy", "baxi", "bakse", "backsy", "boxy"))
    assert match_suffix_independent_endpoint_wake((transcript,), aliases) is None


@pytest.mark.parametrize(
    "transcript",
    [
        "Baxy frobnicate the seventh pane",
        "Baxi inventa un comando nuevo",
        "Bakse muestrame los procesos activos",
        "Backsy translate the selected paragraph",
        "Vaxi take a screenshot",
        "Waxi lower the screen brightness",
    ],
)
def test_suffix_independent_endpoint_accepts_canonical_and_bounded_forms(
    transcript: str,
) -> None:
    aliases = frozenset(("baxy", "baxi", "bakse", "backsy", "boxy"))
    assert match_suffix_independent_endpoint_wake((transcript,), aliases) is not None


def test_same_window_consensus_requires_two_aliases() -> None:
    assert same_window_consensus(
        np.asarray([0.6, 0.3, -1.0, -2.0]),
        primary_threshold=0.5,
        secondary_threshold=0.3,
    )
    assert not same_window_consensus(
        np.asarray([0.6, 0.2, -1.0, -2.0]),
        primary_threshold=0.5,
        secondary_threshold=0.3,
    )


def test_detector_marks_strong_and_lexical_candidates(tmp_path: Path) -> None:
    config = load_wake_cascade_config(_manifest(tmp_path))
    upstream = (_UpstreamSession(True), _UpstreamSession(False))
    strong = HyperspotterCascadeDetector(
        config,
        upstream_sessions=upstream,
        verifier_session=_VerifierSession(4.0),
    ).accept(np.zeros(48_000, dtype=np.float32), now=10.0)
    assert strong is not None
    assert strong.method == "logmel_verifier"
    assert not strong.lexical_rescue_required

    weak = HyperspotterCascadeDetector(
        config,
        upstream_sessions=upstream,
        verifier_session=_VerifierSession(-4.0),
    ).accept(np.zeros(48_000, dtype=np.float32), now=10.0)
    assert weak is not None
    assert weak.method == "strict_lexical_rescue"
    assert weak.lexical_rescue_required


def test_detector_can_fail_closed_without_lexical_rescue(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["lexicalRescueEnabled"] = False
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    config = load_wake_cascade_config(manifest)

    weak = HyperspotterCascadeDetector(
        config,
        upstream_sessions=(_UpstreamSession(True), _UpstreamSession(False)),
        verifier_session=_VerifierSession(-4.0),
    ).accept(np.zeros(48_000, dtype=np.float32), now=10.0)
    assert weak is None
    assert not config.lexical_rescue_enabled


def test_detector_keeps_verifier_lazy_without_upstream_candidate(
    tmp_path: Path,
) -> None:
    config = load_wake_cascade_config(_manifest(tmp_path))

    class _ForbiddenVerifier:
        def run(self, outputs, inputs):
            raise AssertionError("verifier must stay lazy")

    detector = HyperspotterCascadeDetector(
        config,
        upstream_sessions=(_UpstreamSession(False), _UpstreamSession(False)),
        verifier_session=_ForbiddenVerifier(),
    )
    assert detector.accept(np.zeros(48_000, dtype=np.float32), now=10.0) is None


def test_direct_lexical_verifier_can_propose_without_an_upstream_hit(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    direct = tmp_path / "verifier-direct.onnx"
    direct.write_bytes(b"direct")
    payload["schema"] = "baxy-wake-cascade-v2"
    payload.pop("logmelVerifier")
    payload["logmelVerifiers"] = [
        {
            "graph": "verifier.onnx",
            "graphSha256": _sha(tmp_path / "verifier.onnx"),
            "scoreGte": 3.0,
        },
        {"graph": direct.name, "graphSha256": _sha(direct), "scoreGte": 3.0},
    ]
    payload["routes"] = [
        {"name": "legacy", "upstreamModelIndexes": [0, 1], "verifierIndex": 0}
    ]
    payload["directLexicalProposal"] = {
        "verifierIndex": 1,
        "scoreGte": 3.0,
        "retrySpeedFactors": [0.85, 1.14],
        "minimumConsecutiveHops": 4,
    }
    payload["lexicalRescueEnabled"] = False
    payload["calibration"] = {"approved": False}
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    from baxy_mind.wake_cascade import load_wake_cascade_candidate_config

    config = load_wake_cascade_candidate_config(manifest)
    hit = HyperspotterCascadeDetector(
        config,
        upstream_sessions=(_UpstreamSession(False), _UpstreamSession(False)),
        verifier_sessions=(_VerifierSession(-9.0), _VerifierSession(3.1)),
    ).accept(np.zeros(48_000, dtype=np.float32), now=10.0)
    assert hit is not None
    assert hit.method == "direct_lexical_proposal"
    assert hit.lexical_rescue_required
    assert config.direct_lexical_retry_speed_factors == (0.85, 1.14)


def test_endpoint_lexical_score_uses_its_manifest_bound_verifier(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    direct = tmp_path / "verifier-direct.onnx"
    direct.write_bytes(b"direct")
    payload["schema"] = "baxy-wake-cascade-v2"
    payload.pop("logmelVerifier")
    payload["logmelVerifiers"] = [
        {
            "graph": "verifier.onnx",
            "graphSha256": _sha(tmp_path / "verifier.onnx"),
            "scoreGte": 3.0,
        },
        {"graph": direct.name, "graphSha256": _sha(direct), "scoreGte": 2.5},
    ]
    payload["routes"] = [
        {"name": "legacy", "upstreamModelIndexes": [0, 1], "verifierIndex": 0}
    ]
    payload["directLexicalProposal"] = {
        "verifierIndex": 1,
        "scoreGte": 2.5,
        "retrySpeedFactors": [0.85, 1.14],
    }
    payload["endpointLexicalProposal"] = {
        "verifierIndex": 1,
        "scoreGte": -1.0,
        "aliases": ["baxy", "baxi", "bakse", "backsy", "boxy"],
        "retrySpeedFactors": [0.85, 1.14],
    }
    payload["calibration"] = {"approved": False}
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    config = load_wake_cascade_candidate_config(manifest)
    detector = HyperspotterCascadeDetector(
        config,
        upstream_sessions=(_UpstreamSession(False), _UpstreamSession(False)),
        verifier_sessions=(_VerifierSession(-9.0), _VerifierSession(-0.5)),
    )

    assert detector.score_endpoint_lexical(np.zeros(16_000, dtype=np.float32)) == -0.5
    assert config.endpoint_lexical_score_threshold == -1.0


def test_endpoint_lexical_manifest_rejects_an_ambiguous_alias(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["schema"] = "baxy-wake-cascade-v2"
    payload.pop("logmelVerifier")
    payload["logmelVerifiers"] = [
        {
            "graph": "verifier.onnx",
            "graphSha256": _sha(tmp_path / "verifier.onnx"),
            "scoreGte": 3.0,
        }
    ]
    payload["routes"] = [
        {"name": "legacy", "upstreamModelIndexes": [0, 1], "verifierIndex": 0}
    ]
    payload["directLexicalProposal"] = {
        "verifierIndex": 0,
        "scoreGte": 2.5,
        "retrySpeedFactors": [],
    }
    payload["endpointLexicalProposal"] = {
        "verifierIndex": 0,
        "scoreGte": -1.0,
        "aliases": ["baxy", "baxi", "basi", "backsy", "boxy"],
        "retrySpeedFactors": [],
    }
    payload["calibration"] = {"approved": False}
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        WakeCascadeConfigurationError, match="wake_cascade_manifest_invalid"
    ):
        load_wake_cascade_candidate_config(manifest)


def test_direct_lexical_proposal_waits_for_the_strong_route_priority_window(
    tmp_path: Path,
) -> None:
    manifest = _manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    direct = tmp_path / "verifier-direct.onnx"
    direct.write_bytes(b"direct")
    payload["schema"] = "baxy-wake-cascade-v2"
    payload.pop("logmelVerifier")
    payload["logmelVerifiers"] = [
        {
            "graph": "verifier.onnx",
            "graphSha256": _sha(tmp_path / "verifier.onnx"),
            "scoreGte": 3.0,
        },
        {"graph": direct.name, "graphSha256": _sha(direct), "scoreGte": 3.0},
    ]
    payload["routes"] = [
        {"name": "legacy", "upstreamModelIndexes": [0, 1], "verifierIndex": 0}
    ]
    payload["directLexicalProposal"] = {
        "verifierIndex": 1,
        "scoreGte": 3.0,
        "retrySpeedFactors": [],
        "minimumConsecutiveHops": 4,
    }
    payload["lexicalRescueEnabled"] = False
    payload["calibration"] = {"approved": False}
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    from baxy_mind.wake_cascade import load_wake_cascade_candidate_config

    detector = HyperspotterCascadeDetector(
        load_wake_cascade_candidate_config(manifest),
        upstream_sessions=(_UpstreamSession(True), _UpstreamSession(False)),
        verifier_sessions=(_VerifierSession(-9.0), _VerifierSession(3.1)),
    )
    assert detector.accept(np.zeros(48_000, dtype=np.float32), now=10.0) is None
    hit = detector.accept(np.zeros(12_000, dtype=np.float32), now=11.0)
    assert hit is not None
    assert hit.method == "direct_lexical_proposal"


def test_detector_keeps_routed_verifiers_independent(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    second = tmp_path / "verifier-expanded.onnx"
    second.write_bytes(b"expanded")
    payload["schema"] = "baxy-wake-cascade-v2"
    payload.pop("logmelVerifier")
    payload["logmelVerifiers"] = [
        {
            "graph": "verifier.onnx",
            "graphSha256": _sha(tmp_path / "verifier.onnx"),
            "scoreGte": 3.0,
        },
        {"graph": second.name, "graphSha256": _sha(second), "scoreGte": 4.0},
    ]
    payload["routes"] = [
        {"name": "legacy", "upstreamModelIndexes": [0], "verifierIndex": 0},
        {"name": "expanded", "upstreamModelIndexes": [1], "verifierIndex": 1},
    ]
    payload["calibration"] = {"approved": False}
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    from baxy_mind.wake_cascade import load_wake_cascade_candidate_config

    config = load_wake_cascade_candidate_config(manifest)
    hit = HyperspotterCascadeDetector(
        config,
        upstream_sessions=(_UpstreamSession(False), _UpstreamSession(True)),
        verifier_sessions=(_VerifierSession(9.0), _VerifierSession(4.5)),
    ).accept(np.zeros(48_000, dtype=np.float32), now=10.0)
    assert hit is not None
    assert hit.verifier_score == 4.5


def test_detector_can_rescue_one_measured_acoustic_alias(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["singleAliasRescue"] = {"alias": "basi", "logitGte": 0.3}
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    config = load_wake_cascade_config(manifest)

    class _BasiOnlySession:
        def run(self, outputs, inputs):
            return [np.asarray([[0.0, 0.0, 0.31, -1.0]], dtype=np.float32)]

    hit = HyperspotterCascadeDetector(
        config,
        upstream_sessions=(_BasiOnlySession(), _UpstreamSession(False)),
        verifier_session=_VerifierSession(4.0),
    ).accept(np.zeros(48_000, dtype=np.float32), now=10.0)
    assert hit is not None
    assert hit.method == "logmel_verifier"


def test_detector_scores_at_exact_hops_across_512_sample_frames(
    tmp_path: Path,
) -> None:
    config = load_wake_cascade_config(_manifest(tmp_path))

    class _CountingUpstream(_UpstreamSession):
        def __init__(self) -> None:
            super().__init__(False)
            self.calls = 0

        def run(self, outputs, inputs):
            self.calls += 1
            return super().run(outputs, inputs)

    first = _CountingUpstream()
    second = _CountingUpstream()
    detector = HyperspotterCascadeDetector(
        config,
        upstream_sessions=(first, second),
        verifier_session=_VerifierSession(4.0),
    )
    samples = np.zeros(56_000, dtype=np.float32)
    for start in range(0, len(samples), 512):
        detector.accept(samples[start : start + 512], now=10.0)

    assert first.calls == 3
    assert second.calls == 3
