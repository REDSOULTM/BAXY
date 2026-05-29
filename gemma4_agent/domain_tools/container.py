"""Container domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Docker / docker-compose wrappers. exec acepta command list explícita (no
wrap arbitrary shells). lifecycle start/stop/restart con checkpoint+rollback.

Funciones extraídas (8):
  container_tool                 (entry, 13 acciones)
  _container_ps                  (--format {{json .}} con parse line-by-line)
  _container_images
  _container_inspect
  _container_logs                (--tail N)
  _container_lifecycle           (start/stop/restart + checkpoint inverso)
  _container_exec
  _container_compose             (up/down/ps con cwd opcional)

Auto-contenido (shutil, subprocess, json, AgentState)."""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from .._shared import _err, _ok
from ..memory_pkg.state import AgentState


__all__ = [
    "container_tool",
    "_container_ps",
    "_container_images",
    "_container_inspect",
    "_container_logs",
    "_container_lifecycle",
    "_container_exec",
    "_container_compose",
]


def container_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for Docker / docker-compose.

    Actions: status, ps, ps_all, images, inspect, logs, start, stop, restart,
    exec, compose_up, compose_down, compose_ps. Returns needs_dependency if
    docker is not on PATH. exec accepts an explicit command list and runs
    docker exec; we do not wrap arbitrary shells.
    """
    action = str(args.get("action") or "status").casefold()
    docker = shutil.which("docker") or shutil.which("docker.exe")
    if action == "status":
        return _ok(
            docker=bool(docker), docker_path=docker,
            install_hint="winget install Docker.DockerDesktop",
        )
    if not docker:
        return _err(
            "docker is not installed or not on PATH",
            status="needs_dependency", verified=False,
            install_hint="winget install Docker.DockerDesktop",
        )
    if action in {"ps", "ps_all"}:
        return _container_ps(docker, action == "ps_all")
    if action == "images":
        return _container_images(docker)
    if action == "inspect":
        return _container_inspect(docker, args)
    if action == "logs":
        return _container_logs(docker, args)
    if action in {"start", "stop", "restart"}:
        return _container_lifecycle(docker, action, args, state)
    if action == "exec":
        return _container_exec(docker, args)
    if action == "compose_up":
        return _container_compose(docker, "up", args)
    if action == "compose_down":
        return _container_compose(docker, "down", args)
    if action == "compose_ps":
        return _container_compose(docker, "ps", args)
    return _err(
        "unknown container action", action=action,
        valid_actions=[
            "status", "ps", "ps_all", "images", "inspect", "logs",
            "start", "stop", "restart", "pause", "unpause", "rm",
            "compose_up", "compose_down", "compose_ps",
        ],
        status="needs_user",
    )


def _container_ps(docker: str, all_containers: bool) -> dict[str, Any]:
    cmd = [docker, "ps", "--format", "{{json .}}"]
    if all_containers:
        cmd.insert(2, "-a")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("docker ps failed", stderr=proc.stderr, exit_code=proc.returncode)
    containers: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            containers.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return _ok(containers=containers, count=len(containers))


def _container_images(docker: str) -> dict[str, Any]:
    proc = subprocess.run([docker, "images", "--format", "{{json .}}"], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("docker images failed", stderr=proc.stderr)
    images: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            images.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return _ok(images=images, count=len(images))


def _container_inspect(docker: str, args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("name") or args.get("id") or args.get("container") or "").strip()
    if not target:
        return _err("missing container name/id")
    proc = subprocess.run([docker, "inspect", target], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("docker inspect failed", stderr=proc.stderr, target=target)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _err("inspect returned invalid JSON", raw=proc.stdout[:500])
    return _ok(target=target, inspect=data)


def _container_logs(docker: str, args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("name") or args.get("id") or args.get("container") or "").strip()
    if not target:
        return _err("missing container name/id")
    tail = int(args.get("tail", 100))
    proc = subprocess.run([docker, "logs", "--tail", str(tail), target], capture_output=True, text=True, timeout=30)
    return _ok(target=target, tail=tail, exit_code=proc.returncode, stdout=proc.stdout[-8000:], stderr=proc.stderr[-2000:])


def _container_lifecycle(docker: str, action: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    target = str(args.get("name") or args.get("id") or args.get("container") or "").strip()
    if not target:
        return _err("missing container name/id")
    reverse = {"start": "stop", "stop": "start", "restart": "restart"}.get(action)
    checkpoint = state.checkpoint(
        f"container {action} {target}",
        rollback=[{"tool": "container", "args": {"action": reverse, "name": target}}] if reverse else [],
        metadata={"target": target, "action": action},
    )
    proc = subprocess.run([docker, action, target], capture_output=True, text=True, timeout=60)
    return _ok(
        action=action, target=target,
        exit_code=proc.returncode, stdout=proc.stdout.strip()[:500], stderr=proc.stderr[-1000:],
        checkpoint=checkpoint.get("checkpoint"),
        verified=proc.returncode == 0,
    )


def _container_exec(docker: str, args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("name") or args.get("id") or args.get("container") or "").strip()
    cmd = args.get("command")
    if not target:
        return _err("missing container name/id")
    if isinstance(cmd, str):
        cmd_list = cmd.split()
    elif isinstance(cmd, list):
        cmd_list = [str(p) for p in cmd]
    else:
        return _err("command must be string or list")
    if not cmd_list:
        return _err("command is empty")
    proc = subprocess.run([docker, "exec", target, *cmd_list], capture_output=True, text=True, timeout=int(args.get("timeout_sec", 60)))
    return _ok(target=target, command=cmd_list, exit_code=proc.returncode, stdout=proc.stdout[-8000:], stderr=proc.stderr[-2000:], verified=proc.returncode == 0)


def _container_compose(docker: str, subcommand: str, args: dict[str, Any]) -> dict[str, Any]:
    cwd = str(args.get("cwd") or args.get("path") or "").strip() or None
    raw_extra = args.get("args")
    extra: list[Any] = raw_extra if isinstance(raw_extra, list) else []
    cmd = [docker, "compose", subcommand]
    if subcommand == "up":
        cmd.append("-d")
    if subcommand == "ps":
        cmd.extend(["--format", "json"])
    cmd.extend(str(a) for a in extra)
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=int(args.get("timeout_sec", 180)))
    return _ok(subcommand=subcommand, cwd=cwd, command=cmd, exit_code=proc.returncode, stdout=proc.stdout[-6000:], stderr=proc.stderr[-2000:], verified=proc.returncode == 0)
