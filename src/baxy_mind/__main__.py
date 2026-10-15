"""Sidecar entry: speaks baxy.mind.v1 with the App over JSONL (see protocol.py)."""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from . import protocol
from .llm_server import LlmServer
from .mind import Mind

UNSUPPORTED = {"plan", "plan.ground", "computer.use.step", "narrate", "message.send",
               "voice.start", "voice.stop", "voice.status", "voice.speak", "voice.cancel"}


def main() -> int:
    gguf = os.environ.get("BAXY_MIND_LLM_GGUF", "")
    server_path = os.environ.get("BAXY_MIND_LLAMA_SERVER", "")
    if not gguf or not server_path:
        sys.stderr.write("baxy_mind_renew_failure: BAXY_MIND_LLM_GGUF and BAXY_MIND_LLAMA_SERVER are required\n")
        return 2
    server = LlmServer(gguf, server_path, os.environ.get("BAXY_MIND_NGL", "99"))
    server.start()
    trace = Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew" / "turns.jsonl"
    trace.parent.mkdir(parents=True, exist_ok=True)
    mind = Mind(server, trace)
    protocol.write_message({
        "type": "hello", "protocol": protocol.PROTOCOL, "mindVersion": "renew-0.1",
        "models": {"llm": server.name},
        "requests": ["catalog.configure", "turn.decide", "arguments", "message.compose", "shutdown"],
    })
    try:
        while True:
            try:
                message = protocol.read_message()
            except protocol.ProtocolViolation as violation:
                protocol.write_message(protocol.error_reply(None, violation.code, violation.detail))
                return 65
            if message is None:
                break
            if not message:
                continue
            request_id, kind = message.get("id"), str(message.get("type"))
            try:
                if kind == "catalog.configure":
                    count = mind.configure(message)
                    protocol.write_message({"type": "catalog.ready", "id": request_id, "count": count})
                    threading.Thread(target=mind.warm, daemon=True).start()
                elif kind == "turn.decide":
                    protocol.write_message(mind.decide(request_id, str(message.get("text") or ""),
                                                       list(message.get("history") or [])))
                elif kind == "arguments":
                    protocol.write_message(mind.arguments(request_id, str(message.get("operation") or ""),
                                                          str(message.get("text") or ""),
                                                          list(message.get("history") or [])))
                elif kind == "message.compose":
                    protocol.write_message(mind.compose(request_id, str(message.get("userText") or ""),
                                                        str(message.get("intent") or ""), message.get("facts")))
                elif kind == "shutdown":
                    protocol.write_message({"type": "shutdown.ack", "id": request_id})
                    break
                elif kind in UNSUPPORTED:
                    protocol.write_message(protocol.error_reply(request_id, "unsupported_request",
                                                                f"{kind}_unavailable_in_renew"))
                else:
                    protocol.write_message(protocol.error_reply(request_id, "unknown_request", kind))
            except Exception as error:  # noqa: BLE001 - one failed request never ends the sidecar
                surface = {"turn.decide": "turn", "arguments": "arguments"}.get(kind, "request")
                sys.stderr.write(f"baxy_mind_renew_failure:{kind}:{error!r}\n")
                sys.stderr.flush()
                protocol.write_message(protocol.error_reply(request_id, "request_failed",
                                                            f"{surface}_runtime_failure"))
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
