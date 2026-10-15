"""The contextual decider: its payload and saved slot state, the warm-up, the decision prepared ahead, and the
contextual rewrite of a follow-up.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Iterable

from .semantic import decider as semantic_decider
from .llm_transport import ChatCompletionCancellation, SlotState, prepare_slot_state
from .request_intents import _message_response_language
from .context_rewrite import _REWRITE_DEPENDENCY_HINTS, _REWRITE_EXAMPLES, _REWRITE_EXAMPLES_SHOWN, _rewrite_input


# The contextual decider's budget for one decision (``decide_in_context``, ``prepare_decision``).
DECIDER_TIMEOUT_SECONDS = 8.0
# Reading its catalog prompt once at start-up (``warm_decider``): ≈6 400 tokens, 3.7–3.9 s on the GPU profile.
DECIDER_WARMUP_SECONDS = 30.0


def _decider_payload_key(payload: dict[str, Any]) -> str:
    """Every byte a contextual decision is generated from: a prepared reply serves only the same request."""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class DeciderMixin:
    """The contextual decision of a turn and the rewrite of a follow-up message."""

    def _decider_payload(
        self,
        text: str,
        history: list[dict[str, str]] | None,
        tools: Iterable[tuple[str, str]],
        signatures: dict[str, tuple[str, ...]] | None,
    ) -> tuple[dict[str, Any], list[str]]:
        """The contextual decider's request for one turn and the operation names it may answer."""

        tools = tuple(sorted(tools))
        key = (tools, tuple(sorted((signatures or {}).items())) if signatures is not None else None)
        cached = getattr(self, "_decider_prompt", None)
        if cached is None or cached[0] != key:
            cached = (key, semantic_decider.catalog_prompt(tools, signatures))
            self._decider_prompt = cached
        names = [name for name, _ in tools]
        payload = {
            "messages": semantic_decider.messages(cached[1], text, history),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_context_decision",
                    "strict": True,
                    "schema": semantic_decider.response_schema(names, with_arguments=signatures is not None),
                },
            },
            "temperature": 0.0,
            "max_tokens": 300,
            "seed": 0,
            "cache_prompt": True,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        adapter = getattr(self, "_decider_adapter", None)
        if adapter is not None:
            payload.update(adapter.request_fields())
        return payload, names

    def _decider_slot_state(self, payload: dict[str, Any]) -> SlotState | None:
        """The saved state of the decider's slot after the prefix every decision shares (policy and catalog).

        Estabilización A (r31-m1, «mandale a Ron92…»): the same request, byte for byte, came out ``message.send`` or
        ``message.draft`` depending on the context checkpoint the server resumed the hybrid model from, and the
        previous decision's length (often another conversation's) set that checkpoint. Every decision now starts from
        this one state. The server renders the prefix (``/apply-template``): what a dialogue that opens with the
        person and one that opens with BAXY share. Without it (no slot files, or no rendering) the decision resumes
        as the server's cache allows, as before.
        """

        directory = getattr(self, "_decider_state_dir", None)
        if directory is None:
            return None
        system = payload["messages"][0]
        options = {key: payload[key] for key in ("chat_template_kwargs",) if key in payload}
        adapter = {key: payload[key] for key in ("lora",) if key in payload}
        key = json.dumps([system, options, adapter], ensure_ascii=False, sort_keys=True)
        cached = getattr(self, "_decider_slot_prefix", None)
        if cached is None or cached[0] != key:
            openings = (
                [{"role": "user", "content": "x"}],
                [{"role": "assistant", "content": "x"}, {"role": "user", "content": "x"}],
            )
            try:
                self._ensure_started()
                rendered = []
                for opening in openings:
                    request = urllib.request.Request(
                        f"{self._endpoint}/apply-template",
                        data=json.dumps({"messages": [system, *opening], **options}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(request, timeout=DECIDER_WARMUP_SECONDS) as response:
                        rendered.append(json.loads(response.read().decode("utf-8"))["prompt"])
            except Exception:  # noqa: BLE001 - optional: the decision resumes as the server's cache allows
                return None
            # Revisión A H2: evaluated from nothing, never from a context checkpoint of what the slot held.
            prefix = {
                "prompt": os.path.commonprefix(rendered),
                "n_predict": 1,
                "temperature": 0.0,
                "cache_prompt": False,
                **adapter,
            }
            name = "decider-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16] + ".bin"
            for previous in Path(directory).glob("decider-*.bin"):
                if previous.name != name:
                    with contextlib.suppress(OSError):  # another catalog's state (a restore may still read it)
                        previous.unlink(missing_ok=True)
            cached = (key, SlotState(Path(directory) / name, prefix))
            self._decider_slot_prefix = cached
        return cached[1]

    def prepare_decision(
        self,
        text: str,
        history: list[dict[str, str]] | None,
        tools: Iterable[tuple[str, str]],
        *,
        timeout: float = DECIDER_TIMEOUT_SECONDS,
        signatures: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        """Start the contextual decision of this turn on its reserved slot while the readers still read it.

        M117 (window v4f-devF): the readers ran before the decider was asked, 0.18 s p50 of CPU in front of every
        decided turn. The request is the one ``decide_in_context`` would send, byte for byte; it hands the reply
        over only to a call with that same payload, and a turn the readers decide retires it unread
        (``end_request``). Only the multi-slot profile has a reserved slot to start it on.
        """

        self._retire_prepared_decision()
        if not getattr(self, "_parallel_turn_verification", False):
            return
        payload, _ = self._decider_payload(text, history, tools, signatures)
        budget = self._normalize_request_budget(timeout)
        cancellation = ChatCompletionCancellation()
        decision: Future = Future()

        def decide() -> None:
            if not decision.set_running_or_notify_cancel():
                return
            try:
                decision.set_result(
                    self._post(
                        payload,
                        timeout=budget,
                        reserved_slot=True,
                        cancellation=cancellation,
                        slot_state=self._decider_slot_state(payload),
                    )
                )
            except BaseException as error:  # noqa: BLE001 - handed to its consumer, which asks again
                decision.set_exception(error)

        self._prepared_decision = (_decider_payload_key(payload), cancellation, decision)
        threading.Thread(target=decide, name="baxy-prepared-decision", daemon=True).start()

    def warm_decider(
        self,
        tools: Iterable[tuple[str, str]],
        *,
        signatures: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        """Put the contextual decider's slot in its saved catalog state as soon as the catalog is configured.

        M117 (every window run: D-s001 6 139 tokens in 3.7 s, F-s002 6 478 in 3.9 s): the first decided turn after
        start-up prefilled the whole catalog prompt. It is the prefix every decision begins with, so it is evaluated
        and saved once beforehand (``_decider_slot_state``), with no request after it; the first turn then reads only
        its own message. A failure leaves the first turn building it.
        """

        if not getattr(self, "_parallel_turn_verification", False):
            return
        payload, _ = self._decider_payload("", [], tools, signatures)
        # 2026-10-08 (v2-u7, v2-t-file-3, v2-v3-20): every ``ConnectionError`` of this warmup was the app closing
        # while it still read (the run ended 2.3-5.0 s after catalog.ready; the read takes 4.3-4.7 s). ``close``
        # cancels it, so the cut is named for what it is (``ChatCompletionCancelled``), not a broken connection.
        self._retire_decider_warmup()
        cancellation = ChatCompletionCancellation()
        self._decider_warmup = cancellation

        def warm() -> None:
            try:
                state = self._decider_slot_state(payload)
                if state is not None:
                    self._prepare_slot(state, cancellation)
            except Exception:  # noqa: BLE001 - optional: the first turn builds the state itself
                return

        threading.Thread(target=warm, name="baxy-decider-warmup", daemon=True).start()

    def _prepare_slot(self, state: SlotState, cancellation: ChatCompletionCancellation) -> None:
        """Put the reserved slot in ``state`` (``llm_transport.prepare_slot_state``)."""

        prepare_slot_state(
            self._http_connection_pool,
            self._endpoint,
            state,
            timeout=DECIDER_WARMUP_SECONDS,
            cancellation=cancellation,
        )

    def _prepared_decision_response(self, payload: dict[str, Any], timeout: float) -> dict[str, Any] | None:
        """The prepared reply to exactly ``payload``, or None when the decider has to be asked now."""

        prepared = getattr(self, "_prepared_decision", None)
        self._prepared_decision = None
        if prepared is None:
            return None
        key, cancellation, decision = prepared
        if key != _decider_payload_key(payload):
            cancellation.cancel()
            decision.cancel()
            return None
        try:
            return decision.result(timeout=self._effective_request_timeout(timeout))
        except TimeoutError as error:
            cancellation.cancel()
            raise TimeoutError("se agotó el presupuesto del decisor") from error
        except Exception:  # noqa: BLE001 - cancelled or transport: asked again like a retry
            return None

    def decide_in_context(
        self,
        text: str,
        history: list[dict[str, str]] | None,
        tools: Iterable[tuple[str, str]],
        *,
        timeout: float = DECIDER_TIMEOUT_SECONDS,
        signatures: dict[str, tuple[str, ...]] | None = None,
    ) -> semantic_decider.ContextDecision:
        """Decide the turn with the whole conversation and the catalog (``semantic.decider``).

        The prompt is fixed for a catalog, so its state is saved once in the reserved slot and restored before each
        decision (``_decider_slot_state``); only the conversation and the last message are decoded each turn.
        """

        payload, names = self._decider_payload(text, history, tools, signatures)
        response = self._prepared_decision_response(payload, timeout)
        if response is None:
            response = self._post(
                payload,
                timeout=self._normalize_request_budget(timeout),
                reserved_slot=True,
                slot_state=self._decider_slot_state(payload),
            )
        # M49: what the server spent on this decision (prompt tokens it had to evaluate, tokens it wrote), for the
        # turn audit; a reserved slot that lost its cached catalog shows as a large prompt_n.
        timings = response.get("timings") if isinstance(response, dict) else None
        self._last_decider_timings = (
            {key: timings.get(key) for key in ("prompt_n", "prompt_ms", "predicted_n", "predicted_ms")}
            if isinstance(timings, dict) else None
        )
        try:
            content = response["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("el decisor no devolvió contenido") from error
        return semantic_decider.parse(content, names)

    def rewrite_in_context(
        self,
        text: str,
        context: list[tuple[str, str]],
        *,
        dependency: str = "",
        verified: list[tuple[str, str]] | tuple[tuple[str, str], ...] = (),
        shape: str = "",
        timeout: float = 2.5,
    ) -> str:
        """Rewrite a message that depends on the dialogue as a request that stands alone.

        The dialogue slot (``semantic.dialogue.dependency``) already decided that the
        message points back: an answer to BAXY's question, «sí», a new destination,
        a pronoun object, a lookup without its topic or a follow-up that says only
        what changes. ``verified`` is what this conversation verified (the dialogue
        state: place, day, what plays, the alarm set, the topic searched). The model
        only joins the message with what was said or verified;
        ``semantic.dialogue.rewrite_stays_in_context`` rejects any other word, so it
        can never add an object or an effect. ``shape`` (``semantic.dialogue.shape``) picks the worked
        conversations shown.
        """

        shown = [example for example in _REWRITE_EXAMPLES if shape in example[0]] or list(_REWRITE_EXAMPLES)
        # Tanda 8 replay: an English alarm example led «no, mejor a las 6:15» to «set an alarm for 6:15 a.m.
        # tomorrow», rejected for its language. When the shape has worked conversations in the message's
        # language, only those are shown.
        language = _message_response_language(text)
        shown = [example for example in shown if _message_response_language(example[3]) == language] or shown
        examples = []
        for _, example_verified, example_context, example_text, example_rewrite in shown[:_REWRITE_EXAMPLES_SHOWN]:
            examples += [
                {"role": "user", "content": _rewrite_input(example_text, example_context, example_verified)},
                {"role": "assistant", "content": json.dumps({"request": example_rewrite}, ensure_ascii=False)},
            ]
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Reescribes el último mensaje de una persona a BAXY, su asistente de PC, como un pedido "
                        "completo que se entienda sin leer la conversación. En lugar de lo que falta o se señala "
                        "(«eso», «allá», «esta», «it», un pronombre) pon lo que la conversación ya nombró: el "
                        "pedido anterior de la persona, lo que BAXY contestó (un número, un lugar, un nombre) o "
                        "lo verificado. Usa sólo palabras de la conversación, de lo verificado o del mensaje: "
                        "nada que nadie dijo. Si le falta algo, no lo devuelvas igual; un pedido completo y "
                        "nuevo, o charla, queda igual. Conserva el idioma y el trato de la persona. Devuelve "
                        "sólo el JSON."
                    ),
                },
                *examples,
                *(
                    [{"role": "system", "content": _REWRITE_DEPENDENCY_HINTS[dependency]}]
                    if dependency in _REWRITE_DEPENDENCY_HINTS
                    else []
                ),
                {
                    "role": "user",
                    "content": _rewrite_input(text, context, [line for _, line in verified]),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "baxy_contextual_rewrite",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "request": {"type": "string", "minLength": 1, "maxLength": 600}
                        },
                        "required": ["request"],
                        "additionalProperties": False,
                    },
                },
            },
            "temperature": 0.0,
            "max_tokens": 128,
            "seed": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        maximum_timeout = 15.0 if os.environ.get("BAXY_MIND_NGL", "").strip() == "0" else 2.5
        response = self._post(
            payload,
            timeout=min(maximum_timeout, self._normalize_request_budget(timeout)),
        )
        try:
            content = response["choices"][0]["message"].get("content") or ""
            raw = json.loads(content)
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise ValueError("reescritura contextual con JSON inválido") from error
        if not isinstance(raw, dict) or set(raw) != {"request"} or not isinstance(raw["request"], str):
            raise ValueError("reescritura contextual con forma inválida")
        return " ".join(raw["request"].split())
