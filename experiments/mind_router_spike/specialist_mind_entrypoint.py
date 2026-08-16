"""Development-only mind entrypoint with an ONNX operation pulse.

The pulse replaces only the raw atomic-operation nomination.  The production
catalogue, domain veto, grounding, clarification, and presentation pipeline
remain unchanged.  This module is never the installed product entrypoint and
must only be used by side-effect-free ``turn.decide`` probes.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import onnxruntime as ort
from transformers import AutoConfig, AutoTokenizer

import baxy_mind.family_classifier as family_module
import baxy_mind.llm as llm_module
from baxy_mind.__main__ import _explicit_response_language, main


MODEL_ENVIRONMENT_VARIABLE = "BAXY_EXPERIMENT_OPERATION_SPECIALIST_ONNX"
TOKENIZER_ENVIRONMENT_VARIABLE = "BAXY_EXPERIMENT_OPERATION_SPECIALIST_TOKENIZER"
NO_ACTION = "__none__"
MAX_CACHE_ROWS = 512


@dataclass(frozen=True, slots=True)
class OperationPrediction:
    operation: str
    margin: float


class OperationSpecialist:
    """CPU-only closed-set nominator with no execution interface."""

    def __init__(self) -> None:
        model_path = Path(os.environ[MODEL_ENVIRONMENT_VARIABLE]).resolve(strict=True)
        tokenizer_path = Path(
            os.environ[TOKENIZER_ENVIRONMENT_VARIABLE]
        ).resolve(strict=True)
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
            str(config.id2label[index])
            for index in range(config.num_labels)
        )
        self._cache: OrderedDict[str, OperationPrediction] = OrderedDict()
        self._lock = threading.Lock()

    def predict(self, text: str) -> OperationPrediction:
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
            winner = int(order[0])
            runner_up = int(order[1])
            prediction = OperationPrediction(
                operation=self._labels[winner],
                margin=float(scores[winner] - scores[runner_up]),
            )
            self._cache[normalized] = prediction
            self._cache.move_to_end(normalized)
            while len(self._cache) > MAX_CACHE_ROWS:
                self._cache.popitem(last=False)
            return prediction


_SPECIALIST = OperationSpecialist()
_REAL_LLM_RUNTIME = llm_module.LlmRuntime


class PulseFamilyClassifier:
    """Close the shortlist family around the specialist nomination."""

    def predict(
        self,
        text: str,
        available_families: Iterable[str],
    ) -> family_module.FamilyPrediction | None:
        prediction = _SPECIALIST.predict(text)
        if prediction.operation == NO_ACTION:
            return None
        family = prediction.operation.split(".", 1)[0]
        if family not in set(available_families):
            return None
        return family_module.FamilyPrediction(
            family=family,
            margin=prediction.margin,
        )


class PulseLlmRuntime(_REAL_LLM_RUNTIME):
    """Delegate every LLM method except the measured raw nomination."""

    def decide_turn(
        self,
        text: str,
        candidates: list[dict[str, Any]],
        *,
        history: list[dict[str, Any]] | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        del history, evidence
        prediction = _SPECIALIST.predict(text)
        candidate_names = {
            str(candidate.get("name", ""))
            for candidate in candidates
        }
        response_language = _explicit_response_language(text)
        if prediction.operation == NO_ACTION:
            return {
                "mode": "conversation",
                "operation": None,
                "question": "",
                "conversation_kind": "knowledge",
                "effect_count": "zero",
                "effect_operations": [],
                "effect_verification": "not_applicable",
                "response_language": response_language,
                "intent_operations": [],
            }
        if prediction.operation not in candidate_names:
            raise ValueError("specialist nomination escaped the authenticated shortlist")
        contract = next(
            candidate
            for candidate in candidates
            if candidate.get("name") == prediction.operation
        )
        with ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="baxy-specialist-pulse",
        ) as executor:
            shape_future = executor.submit(
                self._verify_semantic_effect_shape,
                text,
            )
            compatibility_future = executor.submit(
                self._operation_is_fully_compatible,
                text,
                prediction.operation,
                contract,
            )
            guard_state, effect_count = shape_future.result()
            compatible = bool(compatibility_future.result())
        if (
            guard_state != "complete"
            or effect_count != "one"
            or not compatible
        ):
            return {
                "mode": "conversation",
                "operation": None,
                "question": "",
                "conversation_kind": "unsupported",
                "effect_count": "zero",
                "effect_operations": [],
                "effect_verification": "not_applicable",
                "response_language": response_language,
                "intent_operations": [],
            }
        return {
            "mode": "action",
            "operation": prediction.operation,
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": [prediction.operation],
            "effect_verification": "recovered",
            "response_language": response_language,
            "intent_operations": [prediction.operation],
        }


family_module.FamilyClassifier = PulseFamilyClassifier
llm_module.LlmRuntime = PulseLlmRuntime


if __name__ == "__main__":
    raise SystemExit(main())
