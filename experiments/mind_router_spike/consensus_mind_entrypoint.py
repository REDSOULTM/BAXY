"""Development-only mind entrypoint with verified consensus recovery.

Two CPU ONNX classifiers and one frozen lexical ranker can nominate only an
authenticated top-three specialist operation. The normal product path remains
the fallback. This module is never the installed entrypoint and is restricted
to side-effect-free ``turn.decide`` probes.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import threading
import unicodedata
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import onnxruntime as ort
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import AutoConfig, AutoTokenizer

import baxy_mind.family_classifier as family_module
import baxy_mind.llm as llm_module
import baxy_mind.__main__ as mind_main_module
from baxy_mind.__main__ import _explicit_response_language, main
from experiments.mind_router_spike.benchmark_native_no_match_tool import _select


SPECIALIST_MODEL_ENV = "BAXY_EXPERIMENT_OPERATION_SPECIALIST_ONNX"
SPECIALIST_TOKENIZER_ENV = "BAXY_EXPERIMENT_OPERATION_SPECIALIST_TOKENIZER"
FULL_MODEL_ENV = "BAXY_EXPERIMENT_FULL_CATALOG_ONNX"
FULL_TOKENIZER_ENV = "BAXY_EXPERIMENT_FULL_CATALOG_TOKENIZER"
LEXICAL_ASSETS_ENV = "BAXY_EXPERIMENT_OPERATION_LEXICAL_ASSETS"
VERIFY_ENV = "BAXY_EXPERIMENT_CONSENSUS_VERIFY"
DISABLE_FULL_ENV = "BAXY_EXPERIMENT_DISABLE_FULL_CONSENSUS"
NO_ACTION = "__none__"
MAX_CACHE_ROWS = 512
ALARM_CANCEL_ACTION = re.compile(
    r"\b(cancel|deactivate|turn off|cancela|desactiva|anula)\b"
)
ALARM_OBJECT = re.compile(r"\b(alarm|alarma)\b")
ALARM_ACTIVE = re.compile(
    r"\b(ringing|sounding|going off|went off|heard|hear you|awake|silence|"
    r"quiet|sonando|suena|sono|oi|despiert|silencia|calla)\b"
)
EXPLICIT_TIME = re.compile(
    r"\b([0-2]?\d[:.]\d\d|a las|at \d|am|pm|manana|tomorrow|monday|lunes)\b"
)


@dataclass(frozen=True, slots=True)
class Ranking:
    operations: tuple[str, ...]
    margin: float


class OnnxRanker:
    """CPU-only closed-set ranker with no execution interface."""

    def __init__(self, model_env: str, tokenizer_env: str) -> None:
        model_path = Path(os.environ[model_env]).resolve(strict=True)
        tokenizer_path = Path(os.environ[tokenizer_env]).resolve(strict=True)
        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self._session = ort.InferenceSession(
            str(model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self._input_names = {item.name for item in self._session.get_inputs()}
        self._tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_path,
            local_files_only=True,
        )
        config = AutoConfig.from_pretrained(tokenizer_path, local_files_only=True)
        self._labels = tuple(
            str(config.id2label[index]) for index in range(config.num_labels)
        )
        self._cache: OrderedDict[str, Ranking] = OrderedDict()
        self._lock = threading.Lock()

    def predict(self, text: str) -> Ranking:
        normalized = " ".join(text.split())
        with self._lock:
            cached = self._cache.get(normalized)
            if cached is not None:
                self._cache.move_to_end(normalized)
                return cached
            encoded = self._tokenizer(
                normalized,
                truncation=True,
                max_length=96,
                return_tensors="np",
            )
            feeds = {
                key: np.asarray(value, dtype=np.int64)
                for key, value in encoded.items()
                if key in self._input_names
            }
            scores = np.asarray(
                self._session.run(["logits"], feeds)[0],
                dtype=np.float32,
            ).reshape(-1)
            order = np.argsort(-scores)
            ranking = Ranking(
                operations=tuple(self._labels[int(index)] for index in order[:5]),
                margin=float(scores[int(order[0])] - scores[int(order[1])]),
            )
            self._cache[normalized] = ranking
            self._cache.move_to_end(normalized)
            while len(self._cache) > MAX_CACHE_ROWS:
                self._cache.popitem(last=False)
            return ranking


class LexicalRanker:
    """Frozen word/character ranker loaded from non-executable assets."""

    def __init__(self) -> None:
        assets = Path(os.environ[LEXICAL_ASSETS_ENV]).resolve(strict=True)
        with gzip.open(
            assets / "operation_shortlist.v1.vocabulary.json.gz",
            "rt",
            encoding="utf-8",
        ) as handle:
            vocabulary = json.load(handle)
        self._words = TfidfVectorizer(
            analyzer="word",
            ngram_range=tuple(vocabulary["word_ngram_range"]),
            vocabulary=vocabulary["word_vocabulary"],
            sublinear_tf=True,
            strip_accents="unicode",
        )
        self._characters = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=tuple(vocabulary["character_ngram_range"]),
            vocabulary=vocabulary["character_vocabulary"],
            sublinear_tf=True,
            strip_accents="unicode",
        )
        self._words.fit(["baxy operation ranker bootstrap"])
        self._characters.fit(["baxy operation ranker bootstrap"])
        with np.load(
            assets / "operation_shortlist.v1.weights.npz",
            allow_pickle=False,
        ) as arrays:
            self._words.idf_ = np.asarray(arrays["word_idf"], dtype=np.float64)
            self._characters.idf_ = np.asarray(
                arrays["character_idf"],
                dtype=np.float64,
            )
            self._coefficients = np.asarray(
                arrays["coefficients"],
                dtype=np.float64,
            )
            self._intercept = np.asarray(arrays["intercept"], dtype=np.float64)
        self._labels = tuple(str(value) for value in vocabulary["classes"])

    def predict(self, text: str) -> Ranking:
        features = hstack(
            (self._words.transform([text]), self._characters.transform([text])),
            format="csr",
        )
        scores = np.asarray(
            features @ self._coefficients.T + self._intercept
        ).reshape(-1)
        order = np.argsort(-scores)
        return Ranking(
            operations=tuple(self._labels[int(index)] for index in order[:5]),
            margin=float(scores[int(order[0])] - scores[int(order[1])]),
        )


def _normal_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def _notification_cancel_contract(text: str) -> bool:
    normalized = _normal_text(text)
    return bool(
        ALARM_CANCEL_ACTION.search(normalized)
        and ALARM_OBJECT.search(normalized)
        and not ALARM_ACTIVE.search(normalized)
        and not EXPLICIT_TIME.search(normalized)
    )


def _family(operation: str) -> str:
    return operation.split(".", 1)[0]


_SPECIALIST = OnnxRanker(SPECIALIST_MODEL_ENV, SPECIALIST_TOKENIZER_ENV)
_FULL = (
    None
    if os.environ.get(DISABLE_FULL_ENV, "").strip() == "1"
    else OnnxRanker(FULL_MODEL_ENV, FULL_TOKENIZER_ENV)
)
_LEXICAL = LexicalRanker()
_REAL_LLM_RUNTIME = llm_module.LlmRuntime
_REAL_RESOLVE_CLARIFICATION = mind_main_module.resolve_explicit_clarification_intent
_REAL_RESOLVE_EFFECTS = mind_main_module.resolve_explicit_effects
_REAL_STABLE_NO_EFFECT = mind_main_module._explicit_stable_no_effect_turn_decision


@lru_cache(maxsize=MAX_CACHE_ROWS)
def _static_consensus(text: str) -> tuple[str, str] | None:
    specialist = _SPECIALIST.predict(text)
    baseline = specialist.operations[0]
    if baseline == NO_ACTION:
        return None
    top3 = tuple(
        value for value in specialist.operations[:3] if value != NO_ACTION
    )
    if (
        _family(baseline) == "notification"
        and "notification.cancel.latest" in top3
        and _notification_cancel_contract(text)
    ):
        return "notification.cancel.latest", "notification-contract"
    full = _FULL.predict(text)
    lexical = _LEXICAL.predict(text)
    if (
        full.operations[0] == lexical.operations[0]
        and full.operations[0] in top3
        and _family(full.operations[0]) == _family(baseline)
    ):
        return full.operations[0], "full+lexical"
    return None


def _consensus_resolve_clarification(
    text: str,
    available_operations: Iterable[str],
) -> Any:
    if _static_consensus(text) is not None:
        return None
    return _REAL_RESOLVE_CLARIFICATION(text, available_operations)


def _consensus_resolve_effects(
    text: str,
    available_operations: Iterable[str],
    application_names: Iterable[str] = (),
    game_catalog: Iterable[tuple[str, str, str]] = (),
) -> Any:
    if _static_consensus(text) is not None:
        return None
    return _REAL_RESOLVE_EFFECTS(
        text,
        available_operations,
        application_names,
        game_catalog,
    )


def _consensus_stable_no_effect(
    objective: str,
    history: object = None,
) -> dict[str, object] | None:
    decision = _REAL_STABLE_NO_EFFECT(objective, history)
    if decision is not None and _static_consensus(objective) is not None:
        return None
    return decision


class ConsensusFamilyClassifier:
    """Close family retrieval only around a non-abstaining specialist."""

    def predict(
        self,
        text: str,
        available_families: Iterable[str],
    ) -> family_module.FamilyPrediction | None:
        prediction = _SPECIALIST.predict(text)
        operation = prediction.operations[0]
        if operation == NO_ACTION:
            return None
        family = _family(operation)
        if family not in set(available_families):
            return None
        return family_module.FamilyPrediction(
            family=family,
            margin=prediction.margin,
        )


class ConsensusLlmRuntime(_REAL_LLM_RUNTIME):
    """Recover only verified consensus; delegate every other turn."""

    def decide_turn(
        self,
        text: str,
        candidates: list[dict[str, Any]],
        *,
        history: list[dict[str, Any]] | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        specialist = _SPECIALIST.predict(text)
        full = _FULL.predict(text)
        lexical = _LEXICAL.predict(text)
        baseline = specialist.operations[0]
        specialist_top3 = tuple(
            value for value in specialist.operations[:3] if value != NO_ACTION
        )
        selected: str | None = None
        gate = ""
        static = _static_consensus(text)
        if static is not None:
            selected, gate = static
        elif baseline != NO_ACTION:
            if (
                lexical.operations[0] in specialist_top3
                and _family(lexical.operations[0]) == _family(baseline)
            ):
                candidate_by_name = {
                    str(candidate.get("name", "")): candidate
                    for candidate in candidates
                }
                if all(name in candidate_by_name for name in specialist_top3):
                    native, no_match = _select(
                        self,
                        text,
                        [candidate_by_name[name] for name in specialist_top3],
                        no_match_mode="sentinel",
                        tool_choice="required",
                    )
                    if not no_match and native == (lexical.operations[0],):
                        selected = lexical.operations[0]
                        gate = "native+lexical"
            if (
                selected is None
                and baseline == full.operations[0] == lexical.operations[0]
            ):
                selected = baseline
                gate = "triple"

        candidate_by_name = {
            str(candidate.get("name", "")): candidate for candidate in candidates
        }
        if selected is None or selected not in candidate_by_name:
            return super().decide_turn(
                text,
                candidates,
                history=history,
                evidence=evidence,
            )
        verified = os.environ.get(VERIFY_ENV, "1") != "0"
        if verified:
            with ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="baxy-consensus-pulse",
            ) as executor:
                shape_future = executor.submit(
                    self._verify_semantic_effect_shape,
                    text,
                )
                compatibility_future = executor.submit(
                    self._operation_is_fully_compatible,
                    text,
                    selected,
                    candidate_by_name[selected],
                )
                guard_state, effect_count = shape_future.result()
                compatible = bool(compatibility_future.result())
            if (
                guard_state != "complete"
                or effect_count != "one"
                or not compatible
            ):
                return super().decide_turn(
                    text,
                    candidates,
                    history=history,
                    evidence=evidence,
                )
        response_language = _explicit_response_language(text)
        return {
            "mode": "action",
            "operation": selected,
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": [selected],
            "effect_verification": "recovered",
            "response_language": response_language,
            "intent_operations": [selected],
            "diagnostic_consensus_gate": gate,
        }


family_module.FamilyClassifier = ConsensusFamilyClassifier
llm_module.LlmRuntime = ConsensusLlmRuntime
mind_main_module.resolve_explicit_clarification_intent = (
    _consensus_resolve_clarification
)
mind_main_module.resolve_explicit_effects = _consensus_resolve_effects
mind_main_module._explicit_stable_no_effect_turn_decision = (
    _consensus_stable_no_effect
)


if __name__ == "__main__":
    raise SystemExit(main())
