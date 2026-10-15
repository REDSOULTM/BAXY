"""Opt-in diagnostics of the model calls: invalid schema replies, raw conversation drafts, call timings and the
stages of a composition. Nothing is written unless the environment asks for it.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any


def _capture_invalid_schema_response(
    label: str,
    attempt: int,
    content: object,
    finish_reason: object,
) -> None:
    configured = os.environ.get("BAXY_MIND_LLM_INVALID_JSON_DIR", "").strip()
    if not configured:
        return
    try:
        directory = Path(configured).expanduser()
        directory.mkdir(parents=True, exist_ok=True)
        raw = content if isinstance(content, str) else ""
        sanitized = "".join(
            character
            for character in raw[:4096]
            if ord(character) >= 32 or character in {"\n", "\r", "\t"}
        )
        payload = {
            "schema": "baxy.invalid-schema-response.v1",
            "label": label,
            "attempt": attempt,
            "finish_reason": str(finish_reason or ""),
            "content_state": (
                "empty"
                if not raw
                else "truncated_capture"
                if len(raw) > 4096
                else "present"
            ),
            "content_chars": len(raw),
            "content_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "sanitized_content": sanitized,
        }
        identity = f"{time.time_ns()}-{os.getpid()}-{threading.get_ident()}"
        destination = directory / f"invalid-turn-{identity}.json"
        temporary = directory / f".invalid-turn-{identity}.tmp"
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
    except (OSError, ValueError, TypeError):
        # Diagnostics can never change the protocol outcome.
        return


_RAW_REPLY_AUDIT_LOCK = threading.Lock()


def _capture_raw_conversation_reply(
    *,
    attempt: int,
    request: str,
    raw_reply: object,
    conversation_kind: str | None,
    presentation_shape: str | None,
    followup_subject: str | None = None,
    history_users: int = 0,
) -> None:
    """Append an opt-in raw draft before any visible-reply veto evaluates it."""

    configured = os.environ.get("BAXY_MIND_RAW_REPLY_AUDIT_PATH", "").strip()
    if not configured:
        return
    try:
        path = Path(configured).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = raw_reply if isinstance(raw_reply, str) else ""
        record = {
            "schema": "baxy.raw-conversation-reply.v1",
            "stage": "pre_veto",
            "attempt": attempt,
            "request_sha256": hashlib.sha256(request.encode("utf-8")).hexdigest(),
            "conversation_kind": str(conversation_kind or ""),
            "presentation_shape": str(presentation_shape or ""),
            "followup_subject": str(followup_subject or ""),
            "history_users": int(history_users),
            "raw_reply": raw[:4096],
            "raw_reply_chars": len(raw),
            "raw_reply_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        }
        payload = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        with _RAW_REPLY_AUDIT_LOCK:
            with path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
    except (OSError, ValueError, TypeError):
        # Opt-in diagnostics never change the turn outcome.
        return


def _capture_model_call_timing(
    payload: dict[str, Any],
    *,
    request_identity: str,
    elapsed_ms: float,
    response: object,
    error: BaseException | None,
) -> None:
    """Append an opt-in, content-free timing row for one model call.

    The shell trace times a whole ``turn.decide``; tandas 04f/05 could not tell
    which of its calls spent the seconds. The row names the call by the head of
    its code-owned system prompt, never by the person's words.
    """

    configured = os.environ.get("BAXY_MIND_MODEL_CALL_AUDIT_PATH", "").strip()
    if not configured:
        return
    try:
        messages = payload.get("messages") or [{}]
        first = messages[0] if isinstance(messages[0], dict) else {}
        head = str(first.get("content") or "")[:40] if first.get("role") == "system" else ""
        choice = {}
        timings: dict[str, Any] = {}
        if isinstance(response, dict):
            choices = response.get("choices") or [{}]
            choice = choices[0] if isinstance(choices[0], dict) else {}
            timings = response.get("timings") if isinstance(response.get("timings"), dict) else {}
        record = {
            "schema": "baxy.model-call-timing.v1",
            "request": request_identity,
            "thread": threading.current_thread().name,
            "prompt_head": head,
            "tools": len(payload.get("tools") or ()),
            "max_tokens": payload.get("max_tokens"),
            "elapsed_ms": round(elapsed_ms, 1),
            "finish_reason": choice.get("finish_reason"),
            "error": type(error).__name__ if error is not None else "",
            **{
                key: timings.get(key)
                for key in ("cache_n", "prompt_n", "prompt_ms", "predicted_n", "predicted_ms")
            },
        }
        from .cu_step_prompt import STEP_PROMPT as computer_use_step_prompt

        if first.get("role") == "system" and str(first.get("content") or "") == computer_use_step_prompt:
            # A computer-use step is diagnosed from what the model saw and said (r5a/decision.md: without the
            # prompt and the raw act the analysis of a refused step was inference). Only these rows carry content;
            # every other call stays content-free.
            message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
            record["messages"] = [
                {"role": str(item.get("role") or ""), "content": str(item.get("content") or "")}
                for item in messages if isinstance(item, dict)
            ]
            record["raw_reply"] = str(message.get("content") or "")
        path = Path(configured).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        with _RAW_REPLY_AUDIT_LOCK:
            with path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(line)
    except (OSError, ValueError, TypeError, IndexError, AttributeError, ImportError):
        # Opt-in diagnostics never change the turn outcome.
        return


def _capture_message_compose_diagnostic(
    reason: str,
    scaffold: str,
    *,
    required_fact_count: int,
    required_fact_characters: int,
    required_actions: list[str],
    required_words: list[str],
) -> None:
    """Write an opt-in, content-free diagnostic for a rejected visible draft."""

    configured = os.environ.get("BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH", "").strip()
    if not configured:
        return
    try:
        path = Path(configured).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "schema": "baxy.message-compose-diagnostic.v1",
            "reason": str(reason)[:256],
            "scaffold_bytes": len(scaffold.encode("utf-8")),
            "scaffold_sha256": hashlib.sha256(scaffold.encode("utf-8")).hexdigest(),
            "required_fact_count": int(required_fact_count),
            "required_fact_characters": int(required_fact_characters),
            "required_actions": [str(value)[:64] for value in required_actions],
            "required_words": [str(value)[:64] for value in required_words],
        }
        payload = (
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        if len(payload) > 8_192:
            return
        with path.open("ab") as handle:
            handle.write(payload)
            handle.flush()
    except (OSError, TypeError, ValueError):
        # Diagnostics can never change the protocol outcome.
        return


def _compose_audit_records_content() -> bool:
    """El contenido sólo se guarda cuando se pide de forma explícita."""

    return os.environ.get("BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT", "").strip() in {
        "1",
        "true",
        "yes",
    }


def _finish_reason_of(response: object) -> str:
    if not isinstance(response, dict):
        return ""
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    return str(first.get("finish_reason") or "") if isinstance(first, dict) else ""


def _capture_compose_stage(
    *,
    trace: str,
    stage: str,
    intent: str,
    language: str,
    greeting: str,
    payload: dict,
    raw: str,
    clipped: str,
    reason: str,
    finish_reason: str,
    published: bool,
    situation: str = "",
    followup_subject: str | None = None,
) -> None:
    """Traza reconstruible de una etapa de composición, opt-in.

    El audit anterior sólo guardaba causa, bytes y hash: no permitía ligar un
    rechazo con su turno ni leer el borrador que se descartó. Aquí van el turno,
    la etapa, el idioma leído, el payload real y el motivo exacto. El texto del
    borrador exige además BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT: con entradas
    sintéticas se lee entero, y en uso normal no se registra nada privado.
    """

    configured = os.environ.get("BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH", "").strip()
    if not configured:
        return
    try:
        path = Path(configured).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        record: dict[str, object] = {
            "schema": "baxy.message-compose-diagnostic.v2",
            "trace": str(trace)[:128],
            "stage": str(stage)[:32],
            "intent": str(intent)[:32],
            "language": str(language)[:8],
            "greeting": str(greeting)[:16],
            "payload_keys": sorted(str(key)[:32] for key in payload),
            "reason": str(reason)[:256],
            "finish_reason": str(finish_reason)[:32],
            "followup_subject": str(followup_subject or ""),
            "published": bool(published),
            "draft_bytes": len(raw.encode("utf-8")),
            "draft_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        }
        if _compose_audit_records_content():
            record["payload"] = payload
            record["situation"] = str(situation)[:2048]
            record["draft"] = raw[:2048]
            if clipped != raw:
                record["clipped"] = clipped[:2048]
        payload_line = (
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        if len(payload_line) > 16_384:
            return
        with path.open("ab") as handle:
            handle.write(payload_line)
            handle.flush()
    except (OSError, TypeError, ValueError):
        # La traza nunca puede cambiar el resultado del protocolo.
        return
