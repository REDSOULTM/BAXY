"""Development-only consensus plus operation-conditioned disposition.

The product's closed deterministic effects keep first refusal.  Model-owned
turns use the verified three-head operation consensus, followed by a separate
ONNX classifier conditioned on that authenticated operation name.  This arm
measures integration ceiling only: the disposition model was trained with the
oracle operation and therefore is not yet a wrong-operation compatibility
verifier.  It is restricted to side-effect-free ``turn.decide`` probes.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import onnxruntime as ort
from transformers import AutoConfig, AutoTokenizer

import baxy_mind.__main__ as mind_main_module
import baxy_mind.family_classifier as family_module
import baxy_mind.llm as llm_module
from baxy_mind.__main__ import _explicit_response_language, main
from experiments.mind_router_spike import consensus_projection_v2_mind_entrypoint as v2


base = v2.base
v1 = v2.v1
MODEL_ENV = "BAXY_EXPERIMENT_CONDITIONED_DISPOSITION_ONNX"
TOKENIZER_ENV = "BAXY_EXPERIMENT_CONDITIONED_DISPOSITION_TOKENIZER"
MAX_CACHE_ROWS = 512


class ConditionedDispositionRanker:
    """CPU-only disposition ranker with no execution interface."""

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
        self._labels = tuple(
            str(config.id2label[index]) for index in range(config.num_labels)
        )
        if set(self._labels) != {"action", "clarify", "conversation"}:
            raise RuntimeError("conditioned disposition labels are invalid")
        self._cache: OrderedDict[tuple[str, str], str] = OrderedDict()
        self._lock = threading.Lock()

    def predict(self, text: str, operation: str) -> str:
        key = (" ".join(text.split()), operation)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached
            encoded = self._tokenizer(
                key[0],
                text_pair=(
                    f"authenticated operation nomination: {operation}"
                ),
                truncation=True,
                max_length=112,
                return_tensors="np",
            )
            feeds = {
                name: np.asarray(value, dtype=np.int64)
                for name, value in encoded.items()
                if name in self._inputs
            }
            scores = np.asarray(
                self._session.run(["logits"], feeds)[0],
                dtype=np.float32,
            ).reshape(-1)
            disposition = self._labels[int(np.argmax(scores))]
            self._cache[key] = disposition
            self._cache.move_to_end(key)
            while len(self._cache) > MAX_CACHE_ROWS:
                self._cache.popitem(last=False)
            return disposition


_DISPOSITION = ConditionedDispositionRanker()


class ConsensusProjectionV3FamilyClassifier:
    """Close the primary family around the specialist nomination."""

    def predict(
        self,
        text: str,
        available_families: Iterable[str],
    ) -> family_module.FamilyPrediction | None:
        prediction = base._SPECIALIST.predict(text)
        operation = prediction.operations[0]
        if operation == base.NO_ACTION:
            return None
        family = base._family(operation)
        if family not in set(available_families):
            return None
        return family_module.FamilyPrediction(
            family=family,
            margin=prediction.margin,
        )


class ConsensusProjectionV3LlmRuntime(base._REAL_LLM_RUNTIME):
    """Project consensus identity through the conditioned disposition."""

    def decide_turn(
        self,
        text: str,
        candidates: list[dict[str, Any]],
        *,
        history: list[dict[str, Any]] | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        selected, _gate = v1._closed_consensus(self, text, candidates)
        operation = selected or base.NO_ACTION
        disposition = _DISPOSITION.predict(text, operation)
        response_language = _explicit_response_language(text)
        if disposition == "conversation":
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
        by_name = {
            str(candidate.get("name", "")): candidate
            for candidate in candidates
        }
        candidate = by_name.get(selected) if selected is not None else None
        if candidate is None:
            return super().decide_turn(
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


mind_main_module.resolve_explicit_clarification_intent = (
    v2._projected_clarification
)
mind_main_module.resolve_explicit_effects = base._REAL_RESOLVE_EFFECTS
mind_main_module._explicit_stable_no_effect_turn_decision = (
    v2._projected_stable_no_effect
)
family_module.FamilyClassifier = ConsensusProjectionV3FamilyClassifier
llm_module.LlmRuntime = ConsensusProjectionV3LlmRuntime


if __name__ == "__main__":
    raise SystemExit(main())
