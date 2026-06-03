"""Creative Local domain tool (ComfyUI primarily) — extracted from
domain_tools.py.

Local generative ML backends. Talks to ComfyUI HTTP server (default
http://127.0.0.1:8188, override con GEMMA4_COMFYUI_HOST). Submit recibe el
"API format" JSON de ComfyUI; el agente lo construye o lo carga de archivo.

Funciones extraídas (9):
  creative_local_tool            (entry, 7 acciones)
  _comfy_alive                   (probe /system_stats con timeout 2s)
  _comfy_post_json / _comfy_get_json
  _comfy_submit                  (registra resource comfy_prompt)
  _comfy_result                  (lee /history/<prompt_id>)
  _comfy_wait                    (poll /history hasta timeout)
  _comfy_queue
  _comfy_interrupt
  _comfy_models                  (/object_info, lista node types)

Auto-contenido (urllib, json, datetime, time, AgentState)."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .._shared import _err, _ok
from ..memory_pkg.state import AgentState


__all__ = [
    "creative_local_tool",
    "_comfy_alive",
    "_comfy_post_json",
    "_comfy_get_json",
    "_comfy_submit",
    "_comfy_result",
    "_comfy_wait",
    "_comfy_queue",
    "_comfy_interrupt",
    "_comfy_models",
]


def creative_local_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for local generative ML backends (ComfyUI primarily).

    Actions: status, submit, result, wait, queue, interrupt, models. Talks to
    a local ComfyUI HTTP server (default http://127.0.0.1:8188). Returns
    needs_user with the launch command if not reachable.
    """
    action = str(args.get("action") or "status").casefold()
    host = str(args.get("host") or os.environ.get("GEMMA4_COMFYUI_HOST") or "http://127.0.0.1:8188").rstrip("/")
    if action == "status":
        alive = _comfy_alive(host)
        return _ok(
            comfyui=alive,
            host=host,
            launch_instruction="Start ComfyUI manually: `python main.py` from your ComfyUI install. Set GEMMA4_COMFYUI_HOST if it listens on a different port.",
        )
    if not _comfy_alive(host):
        return _err(
            f"ComfyUI is not reachable at {host}",
            status="needs_user", verified=False,
            completion_status="needs_comfyui_running",
            launch_instruction="Start ComfyUI from its install dir (`python main.py`) and re-call.",
        )
    if action == "submit":
        return _comfy_submit(host, args, state)
    if action == "result":
        return _comfy_result(host, args)
    if action == "wait":
        return _comfy_wait(host, args)
    if action == "queue":
        return _comfy_queue(host)
    if action == "interrupt":
        return _comfy_interrupt(host)
    if action == "models":
        return _comfy_models(host)
    return _err(
        "unknown creative_local action", action=action,
        valid_actions=[
            "status", "list_models", "txt2img", "img2img", "queue_status",
            "interrupt",
        ],
        status="needs_user",
    )


def _comfy_alive(host: str) -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(f"{host}/system_stats", headers={"User-Agent": "Gemma4Agent/1.0"})
        with urllib.request.urlopen(req, timeout=2.0):
            return True
    except Exception:
        return False


def _comfy_post_json(host: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    import urllib.request
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{host}{path}", data=data, headers={"Content-Type": "application/json", "User-Agent": "Gemma4Agent/1.0"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except Exception as exc:
        return {"_error": str(exc)}


def _comfy_get_json(host: str, path: str) -> dict[str, Any]:
    import urllib.request
    req = urllib.request.Request(f"{host}{path}", headers={"User-Agent": "Gemma4Agent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except Exception as exc:
        return {"_error": str(exc)}


def _comfy_submit(host: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    workflow = args.get("workflow")
    workflow_path = str(args.get("workflow_path") or args.get("path") or "").strip()
    if not workflow and workflow_path:
        p = Path(workflow_path).expanduser()
        if not p.is_file():
            return _err("workflow_path not found", path=str(p))
        try:
            workflow = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            return _err(f"workflow JSON invalid: {exc}", path=str(p))
    if not isinstance(workflow, dict):
        return _err("submit requires workflow (dict) or workflow_path (json file). ComfyUI 'API format' JSON expected.")
    client_id = str(args.get("client_id") or "gemma4-agent")
    payload = {"prompt": workflow, "client_id": client_id}
    response = _comfy_post_json(host, "/prompt", payload)
    if response.get("_error"):
        return _err(f"submit failed: {response['_error']}")
    prompt_id = response.get("prompt_id")
    if not prompt_id:
        return _err("ComfyUI did not return a prompt_id", response=response)
    state.register_resource(
        "comfy_prompt",
        f"comfy {prompt_id}",
        metadata={"prompt_id": prompt_id, "client_id": client_id, "host": host, "submitted_at": datetime.now().isoformat()},
    )
    return _ok(prompt_id=prompt_id, client_id=client_id, host=host, response=response, note="Use action=wait or action=result to retrieve outputs.")


def _comfy_result(host: str, args: dict[str, Any]) -> dict[str, Any]:
    prompt_id = str(args.get("prompt_id") or args.get("id") or "").strip()
    if not prompt_id:
        return _err("missing prompt_id")
    data = _comfy_get_json(host, f"/history/{prompt_id}")
    if data.get("_error"):
        return _err(f"result fetch failed: {data['_error']}")
    record = data.get(prompt_id)
    if not record:
        return _ok(prompt_id=prompt_id, status="pending", note="No history entry yet; the prompt may still be running.")
    outputs = record.get("outputs") or {}
    saved_images: list[dict[str, Any]] = []
    for node_id, node_output in outputs.items():
        for img in node_output.get("images") or []:
            saved_images.append({"node_id": node_id, "filename": img.get("filename"), "subfolder": img.get("subfolder"), "type": img.get("type")})
    return _ok(prompt_id=prompt_id, status=record.get("status", {}).get("status_str"), outputs=outputs, images=saved_images, verified=True)


def _comfy_wait(host: str, args: dict[str, Any]) -> dict[str, Any]:
    prompt_id = str(args.get("prompt_id") or args.get("id") or "").strip()
    if not prompt_id:
        return _err("missing prompt_id")
    timeout = float(args.get("timeout_sec", 300))
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = _comfy_get_json(host, f"/history/{prompt_id}")
        if not data.get("_error") and prompt_id in data:
            return _comfy_result(host, {"prompt_id": prompt_id})
        time.sleep(2.0)
    return _err("timeout waiting for prompt to finish", prompt_id=prompt_id, timeout_sec=timeout, status="needs_verification")


def _comfy_queue(host: str) -> dict[str, Any]:
    data = _comfy_get_json(host, "/queue")
    if data.get("_error"):
        return _err(f"queue fetch failed: {data['_error']}")
    return _ok(running=len(data.get("queue_running") or []), pending=len(data.get("queue_pending") or []), data=data)


def _comfy_interrupt(host: str) -> dict[str, Any]:
    response = _comfy_post_json(host, "/interrupt", {})
    if response.get("_error"):
        return _err(f"interrupt failed: {response['_error']}")
    return _ok(interrupted=True, response=response)


def _comfy_models(host: str) -> dict[str, Any]:
    data = _comfy_get_json(host, "/object_info")
    if data.get("_error"):
        return _err(f"object_info fetch failed: {data['_error']}")
    return _ok(node_types=len(data), sample=list(data.keys())[:30])
