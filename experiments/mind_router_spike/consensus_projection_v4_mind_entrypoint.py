"""Development-only consensus with independent compatibility veto.

Product deterministic recognizers retain first refusal.  For model-owned
turns, the frozen consensus nominates one authenticated operation.  An
independent calibrated binary verifier may only veto that nomination, while
the v12 conditioned classifier decides action, clarification, or conversation.
Both classifiers run concurrently and no model receives execution authority.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from transformers import AutoConfig, AutoTokenizer

import baxy_mind.__main__ as mind_main_module
import baxy_mind.family_classifier as family_module
import baxy_mind.llm as llm_module
from baxy_mind.__main__ import _explicit_response_language, main
from experiments.mind_router_spike import consensus_projection_v3_mind_entrypoint as v3


base = v3.base
v1 = v3.v1
v2 = v3.v2
MODEL_ENV = "BAXY_EXPERIMENT_COMPATIBILITY_ONNX"
TOKENIZER_ENV = "BAXY_EXPERIMENT_COMPATIBILITY_TOKENIZER"
THRESHOLD_ENV = "BAXY_EXPERIMENT_COMPATIBILITY_THRESHOLD"
DEFAULT_THRESHOLD = 0.906282544
MAX_CACHE_ROWS = 512


class CompatibilityVerifier:
    """Calibrated CPU-only veto with no operation-selection interface."""

    def __init__(self) -> None:
        model_path = Path(os.environ[MODEL_ENV]).resolve(strict=True)
        tokenizer_path = Path(os.environ[TOKENIZER_ENV]).resolve(strict=True)
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
        self._inputs = {item.name for item in self._session.get_inputs()}
        self._tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_path,
            local_files_only=True,
        )
        config = AutoConfig.from_pretrained(tokenizer_path, local_files_only=True)
        labels = tuple(
            str(config.id2label[index]) for index in range(config.num_labels)
        )
        if set(labels) != {"compatible", "incompatible"}:
            raise RuntimeError("compatibility labels are invalid")
        self._compatible_id = labels.index("compatible")
        self._threshold = float(os.environ.get(THRESHOLD_ENV, DEFAULT_THRESHOLD))
        if not 0.5 <= self._threshold < 1.0:
            raise RuntimeError("compatibility threshold is outside the safe range")
        self._cache: OrderedDict[tuple[str, str], bool] = OrderedDict()
        self._lock = threading.Lock()

    def accepts(self, text: str, operation: str) -> bool:
        key = (" ".join(text.split()), operation)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached
            encoded = self._tokenizer(
                key[0],
                text_pair=f"authenticated operation nomination: {operation}",
                truncation=True,
                max_length=112,
                return_tensors="np",
            )
            feeds = {
                name: np.asarray(value, dtype=np.int64)
                for name, value in encoded.items()
                if name in self._inputs
            }
            logits = np.asarray(
                self._session.run(["logits"], feeds)[0],
                dtype=np.float64,
            ).reshape(-1)
            shifted = logits - float(np.max(logits))
            probability = float(
                np.exp(shifted)[self._compatible_id] / np.exp(shifted).sum()
            )
            accepted = probability >= self._threshold
            self._cache[key] = accepted
            self._cache.move_to_end(key)
            while len(self._cache) > MAX_CACHE_ROWS:
                self._cache.popitem(last=False)
            return accepted


_COMPATIBILITY = CompatibilityVerifier()
_PAIR_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="baxy-consensus-projection-v4",
)
_select_consensus = v1._closed_consensus


class ConsensusProjectionV4FamilyClassifier(v3.ConsensusProjectionV3FamilyClassifier):
    """Keep the v3 specialist-owned primary family boundary."""


class ConsensusProjectionV4LlmRuntime(base._REAL_LLM_RUNTIME):
    """Require both compatibility and disposition after consensus nomination."""

    def decide_turn(
        self,
        text: str,
        candidates: list[dict[str, Any]],
        *,
        history: list[dict[str, Any]] | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        selected, _gate = _select_consensus(self, text, candidates)
        operation = selected or base.NO_ACTION
        disposition_future = _PAIR_EXECUTOR.submit(
            v3._DISPOSITION.predict,
            text,
            operation,
        )
        compatibility_future = (
            _PAIR_EXECUTOR.submit(_COMPATIBILITY.accepts, text, selected)
            if selected is not None
            else None
        )
        disposition = disposition_future.result()
        compatible = (
            compatibility_future.result()
            if compatibility_future is not None
            else False
        )
        response_language = _explicit_response_language(text)
        if disposition == "conversation" or selected is None:
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
        if not compatible:
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
        by_name = {
            str(candidate.get("name", "")): candidate for candidate in candidates
        }
        candidate = by_name.get(selected)
        if candidate is None:
            return base._REAL_LLM_RUNTIME.decide_turn(
                self,
                text,
                candidates,
                history=history,
                evidence=evidence,
            )
        if disposition == "clarify":
            return {
                "mode": "clarify",
                "operation": None,
                "question": v1._clarification_question(
                    self,
                    text,
                    selected,
                    candidate,
                ),
                "conversation_kind": "",
                "effect_count": "zero",
                "effect_operations": [],
                "effect_verification": "not_applicable",
                "response_language": response_language,
                "intent_operations": [selected],
            }
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
        }


mind_main_module.resolve_explicit_clarification_intent = v2._projected_clarification
mind_main_module.resolve_explicit_effects = base._REAL_RESOLVE_EFFECTS
mind_main_module._explicit_stable_no_effect_turn_decision = (
    v2._projected_stable_no_effect
)
family_module.FamilyClassifier = ConsensusProjectionV4FamilyClassifier
llm_module.LlmRuntime = ConsensusProjectionV4LlmRuntime


if __name__ == "__main__":
    raise SystemExit(main())
