"""The model's checks of a request: whether an operation is the effect asked, whether a lookup is public, and the
language a reply is owed in.
"""

from __future__ import annotations

from collections import OrderedDict
import json
import threading
from typing import Any

from .llm_transport import ChatCompletionCancellation
from .llm_grammar import _RESPONSE_LANGUAGE_GRAMMAR
from .llm_prompts import (
    _RESPONSE_LANGUAGE_EXAMPLES, COMPOUND_CLAUSE_COMPATIBILITY_PROMPT, OPERATION_COMPATIBILITY_PROMPT,
    OPERATION_IDENTITY_PROMPT, RESPONSE_LANGUAGE_PROMPT, SEMANTIC_EFFECT_GUARD_PROMPT,
)
from .effect_guard import _guard_request_text, derive_semantic_effect_state, SEMANTIC_REQUEST_TYPES


class RequestChecksMixin:
    """Operation compatibility, the semantic effect guard and the response language, asked of the model."""

    def _operation_is_fully_compatible(
        self,
        text: str,
        operation: str,
        contract: dict[str, Any],
        *,
        _system_prompt: str = OPERATION_COMPATIBILITY_PROMPT,
    ) -> bool:
        """Independently verify a proposed operation against all constraints."""

        cache_key = json.dumps(
            [
                _system_prompt,
                text,
                operation,
                contract["description"],
                contract["arguments_schema"],
            ],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        reused = self._validated_classifier_reuse_get(
            "_operation_compatibility_reuse_cache",
            cache_key,
        )
        if isinstance(reused, bool):
            return reused
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": _system_prompt,
                },
                {
                    "role": "user",
                    "content": (
                        f"Pedido:\n{text}\n\n"
                        f"Operación:\n{operation} | "
                        f"{contract['description']}\n"
                        "Contrato:\n"
                        + json.dumps(
                            contract["arguments_schema"],
                            ensure_ascii=False,
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                    ),
                },
            ],
            "temperature": 0.0,
            "seed": 0,
            "max_tokens": 24,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_operation_compatibility",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "compatible": {"type": "boolean"},
                        },
                        "required": ["compatible"],
                        "additionalProperties": False,
                    },
                },
            },
        }
        try:
            raw = self._post_schema_object(
                payload,
                "la verificación de compatibilidad de la operación",
            )
        except ValueError:
            return False
        if set(raw) != {"compatible"} or not isinstance(raw.get("compatible"), bool):
            return False
        compatible = raw["compatible"]
        self._validated_classifier_reuse_put(
            "_operation_compatibility_reuse_cache",
            cache_key,
            compatible,
        )
        return compatible

    def _compound_clause_is_fully_compatible(
        self,
        text: str,
        operation: str,
        contract: dict[str, Any],
    ) -> bool:
        """Verify one structurally isolated positive compound clause."""

        return self._operation_is_fully_compatible(
            text,
            operation,
            contract,
            _system_prompt=COMPOUND_CLAUSE_COMPATIBILITY_PROMPT,
        )

    def operation_is_the_requested_effect(
        self,
        text: str,
        operation: str,
        contract: dict[str, Any],
    ) -> bool:
        """Ask only whether this operation *is* the effect the person named.

        The shipped verifier asks a harder question -- can this single operation
        satisfy the whole request, arguments included -- because it guards
        execution. Measured on the R2 proposals it keeps 10 of 48 correct ones
        (``current_catalog_leaf_compatibility_r2.json``); it refuses
        ``bluetooth.radio.set`` for "apágame el bluetooth". That is the right
        strictness for acting and the wrong one for deciding whether BAXY may
        say he cannot do something.

        This asks the identity question instead, with the prompt written and
        measured alongside it on 2026-08-02
        (``current_catalog_leaf_compatibility_semantic_r2.json``): 46 of 48
        correct proposals kept, and only 21 of 84 wrong ones refused. That
        acceptance rate disqualified it as an execution gate: nothing acts on it
        alone. What it names is acted on only after
        ``operation_satisfies_the_request`` or a reader grounds it; otherwise it
        is only asked about (``confirm_operation_before_acting``).
        """

        return self._operation_is_fully_compatible(
            text,
            operation,
            contract,
            _system_prompt=OPERATION_IDENTITY_PROMPT,
        )

    def operation_satisfies_the_request(
        self,
        text: str,
        operation: str,
        contract: dict[str, Any],
    ) -> bool:
        """Ask the strict question: this one operation satisfies the whole request.

        It is the verifier that guards execution (``OPERATION_COMPATIBILITY_PROMPT``):
        on the R2 proposals it keeps only 10 of 48 correct ones, which is the price of
        acting on it. The turn asks it when a lexical stage withheld a proposal or a
        catalogue probe named one, instead of offering either back as a yes/no
        question (tanda 4 2026-09-24, D3).
        """

        return self._operation_is_fully_compatible(text, operation, contract)

    def _remember_semantic_request_type(self, text: str, request_type: str) -> None:
        remembered = self.__dict__.setdefault("_semantic_request_types", OrderedDict())
        remembered[text] = request_type
        remembered.move_to_end(text)
        while len(remembered) > 256:
            remembered.popitem(last=False)

    def public_lookup_requested(self, text: str) -> bool:
        """Whether the guard read ``text`` as public information to look up.

        Reuses the guard's own reading of the same text when the turn already ran
        it; otherwise runs the guard once. Never selects an operation.
        """

        text = _guard_request_text(text)
        remembered = self.__dict__.get("_semantic_request_types") or {}
        if text not in remembered:
            cache = getattr(self, "_semantic_effect_cache", None)
            if cache is not None:
                cache.pop(text, None)
            reuse = getattr(self, "_semantic_effect_reuse_cache", None)
            if reuse is not None:
                with self._validated_classifier_reuse_lock:
                    reuse.pop(text, None)
            try:
                self._verify_semantic_effect_shape(text)
            except ValueError:
                return False
            remembered = self.__dict__.get("_semantic_request_types") or {}
        return remembered.get(text) == "public_lookup"

    def _verify_semantic_effect_shape(
        self,
        text: str,
    ) -> tuple[str, str | None]:
        """Candidate-free, one-sided guard for effect completeness.

        The count can only detect disagreement and force independent
        re-analysis. It never selects an operation or rewrites primary effects.
        """

        text = _guard_request_text(text)
        cache = getattr(self, "_semantic_effect_cache", None)
        if cache is not None and text in cache:
            return cache[text]
        reused = self._validated_classifier_reuse_get(
            "_semantic_effect_reuse_cache",
            text,
        )
        if isinstance(reused, tuple) and len(reused) == 2:
            state, effect_count = reused
            if state in {"no_effect", "complete", "not_complete"} and (
                effect_count is None or effect_count in {"zero", "one", "multiple"}
            ):
                result = (str(state), effect_count)
                if cache is not None:
                    cache[text] = result
                return result
        payload = {
            "messages": [
                {"role": "system", "content": SEMANTIC_EFFECT_GUARD_PROMPT},
                {"role": "user", "content": f"Mensaje actual:\n{text}"},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_semantic_effect_guard",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "request_type": {
                                "type": "string",
                                "enum": list(SEMANTIC_REQUEST_TYPES),
                            },
                            "effect_count": {
                                "type": "string",
                                "enum": ["zero", "one", "multiple"],
                            },
                        },
                        "required": [
                            "request_type",
                            "effect_count",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "temperature": 0.0,
            "max_tokens": 64,
            "seed": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        raw = self._post_schema_object(payload, "el veto semántico de efectos")
        state = derive_semantic_effect_state(raw)
        if state != "invalid" and isinstance(raw, dict):
            self._remember_semantic_request_type(text, str(raw.get("request_type")))
        effect_count = None
        if state != "invalid" and isinstance(raw, dict):
            effect_count = "zero" if state == "no_effect" else raw.get("effect_count")
        assert effect_count is None or isinstance(effect_count, str)
        result = (state, effect_count)
        if cache is not None:
            cache[text] = result
        if state != "invalid":
            self._validated_classifier_reuse_put(
                "_semantic_effect_reuse_cache",
                text,
                result,
            )
        return result

    def detect_response_language(
        self,
        text: str,
        *,
        cancellation: ChatCompletionCancellation | None = None,
        cache_result: bool = True,
    ) -> str:
        """Classify language independently from routing, catalog and history."""

        cache = getattr(self, "_response_language_cache", None)
        if cache is not None and text in cache:
            return cache[text]
        reused = self._validated_classifier_reuse_get(
            "_response_language_reuse_cache",
            text,
        )
        if reused in {"es", "en", "mixed"}:
            result = str(reused)
            if cache is not None:
                cache[text] = result
            return result
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        messages = [{"role": "system", "content": RESPONSE_LANGUAGE_PROMPT}]
        for example, language in _RESPONSE_LANGUAGE_EXAMPLES:
            messages.extend(
                [
                    {
                        "role": "user",
                        "content": f"Mensaje actual:\n{example}",
                    },
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {"language": language},
                            separators=(",", ":"),
                        ),
                    },
                ]
            )
        messages.append(
            {
                "role": "user",
                "content": f"Mensaje actual:\n{text}",
            }
        )
        payload = {
            "messages": messages,
            "grammar": _RESPONSE_LANGUAGE_GRAMMAR,
            "temperature": 0.0,
            "max_tokens": 12,
            "seed": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        cancellation_state = getattr(
            self,
            "_completion_cancellation_state",
            None,
        )
        if cancellation_state is None:
            cancellation_state = threading.local()
            self._completion_cancellation_state = cancellation_state
        prior_cancellation = getattr(cancellation_state, "current", None)
        cancellation_state.current = cancellation
        try:
            raw = self._post_schema_object(payload, "la detección de idioma")
        finally:
            if prior_cancellation is None:
                try:
                    del cancellation_state.current
                except AttributeError:
                    pass
            else:
                cancellation_state.current = prior_cancellation
        language = raw.get("language")
        if language not in {"es", "en", "mixed"}:
            raise ValueError("idioma detectado inválido")
        result = str(language)
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        if cache is not None and (cache_result or cancellation is not None):
            # A completed speculative L is still authoritative for this exact
            # request text and can serve a subsequent logical retry.
            cache[text] = result
        if cache_result or cancellation is not None:
            self._validated_classifier_reuse_put(
                "_response_language_reuse_cache",
                text,
                result,
            )
        return result
