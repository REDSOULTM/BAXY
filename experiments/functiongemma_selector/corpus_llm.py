"""Minimal owned llama-server client used only for corpus generation/review."""

from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:2_000]
        raise RuntimeError(f"llama-server HTTP {error.code}: {detail}") from error
    if not isinstance(value, dict):
        raise ValueError("llama-server returned a non-object response")
    return value


class OwnedLlamaServer:
    def __init__(
        self,
        *,
        server: Path,
        model: Path,
        cwd: Path,
        gpu_layers: int = 99,
        context: int = 8192,
    ) -> None:
        self.server = server
        self.model = model
        self.cwd = cwd
        self.gpu_layers = gpu_layers
        self.context = context
        self.port = _free_port()
        self.process: subprocess.Popen[Any] | None = None

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1/chat/completions"

    def __enter__(self) -> "OwnedLlamaServer":
        command = [
            str(self.server),
            "-m",
            str(self.model),
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "-ngl",
            str(self.gpu_layers),
            "-c",
            str(self.context),
            "-fa",
            "on",
            "-ctk",
            "q8_0",
            "-ctv",
            "q8_0",
            "-np",
            "1",
            "--jinja",
            "--reasoning",
            "off",
            "--reasoning-budget",
            "0",
        ]
        self.process = subprocess.Popen(
            command,
            cwd=self.cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 180.0
        health = f"http://127.0.0.1:{self.port}/health"
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"llama-server exited during startup ({self.process.returncode})"
                )
            try:
                with urllib.request.urlopen(health, timeout=1.0) as response:
                    if response.status == 200:
                        return self
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        self.close()
        raise TimeoutError("llama-server did not become ready")

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        seed: int,
        timeout: float = 120.0,
    ) -> tuple[str, dict[str, Any]]:
        response = post_json(
            self.endpoint,
            {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "seed": seed,
                "response_format": {"type": "json_object"},
            },
            timeout,
        )
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("chat response has no choices")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ValueError("chat response has no JSON content")
        return content, response.get("usage") or {}

    def close(self) -> None:
        process = self.process
        self.process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=15.0)

    def __exit__(self, *_: object) -> None:
        self.close()


def parse_json_object(content: str) -> dict[str, Any]:
    rendered = content.strip()
    if rendered.startswith("```"):
        rendered = rendered.removeprefix("```json").removeprefix("```")
        rendered = rendered.removesuffix("```").strip()
    decoder = json.JSONDecoder()
    values: list[dict[str, Any]] = []
    offset = 0
    while rendered[offset:].strip():
        offset += len(rendered[offset:]) - len(rendered[offset:].lstrip())
        if not rendered[offset:].startswith("{"):
            # Some GGUF chat templates append an end-of-turn marker outside the
            # JSON response. The fully parsed object remains authoritative; any
            # prose before the first object is still rejected.
            if values:
                break
            raise ValueError("model output does not begin with a JSON object")
        value, end = decoder.raw_decode(rendered, offset)
        if not isinstance(value, dict):
            raise ValueError("model JSON must contain only objects")
        values.append(value)
        offset = end
    if not values:
        raise ValueError("model JSON is empty")
    merged = dict(values[0])
    for value in values[1:]:
        for key, item in value.items():
            if isinstance(item, list) and isinstance(merged.get(key), list):
                merged[key] = [*merged[key], *item]
            elif key not in merged or merged[key] == item:
                merged[key] = item
            else:
                raise ValueError(f"conflicting concatenated JSON field: {key}")
    return merged
