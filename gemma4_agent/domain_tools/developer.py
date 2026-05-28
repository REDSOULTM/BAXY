"""Developer workflows domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Detect project stack (Python/Node/Rust/Go/Java/Ruby/PHP) by markers + run
tests/lint/format with the right runner. Git status/diff/log read-only.
start_dev_server detacha el proceso (DETACHED_PROCESS) para sobrevivir al
cierre del agente. stop_dev_server verifica PID identity (CC-104) anti
pid-recycle.

Mutating git actions (commit/push) NO implementadas — el usuario debe usar
terminal(...) explícito.

Funciones extraídas (8):
  developer_tool                  (entry, 11 acciones)
  _developer_project_root
  _developer_project_detect       (markers + node_pm + python_pm)
  _developer_run                  (priority python>node>rust>go)
  _developer_command              (mapping stack+kind -> command)
  _developer_git
  _developer_start_dev_server     (DETACHED_PROCESS, log file)
  _developer_stop_dev_server      (CC-104 pid identity check)

Helpers desde domain_tools (lazy): _resources_by_kind, _pid_owned_by."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .._shared import _err, _ok
from ..state import AgentState


__all__ = [
    "developer_tool",
    "_developer_project_root",
    "_developer_project_detect",
    "_developer_run",
    "_developer_command",
    "_developer_git",
    "_developer_start_dev_server",
    "_developer_stop_dev_server",
]


def developer_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for developer workflows: detect, test, lint, format, git, dev_server.

    Actions:
      - status
      - project_detect(path?)
      - run_tests(path?, args?)
      - run_lint(path?)
      - run_format(path?)
      - git_status(path?)
      - git_diff(path?, staged?)
      - git_log(path?, limit?)
      - start_dev_server(path?, command?)
      - stop_dev_server(server_id?)
      - list_dev_servers
    Mutating git actions (git_commit/push) are intentionally NOT implemented:
    the agent must use terminal(...) explicitly so the user sees the command.
    """
    from .helpers import _resources_by_kind
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            git=bool(shutil.which("git")),
            python=bool(shutil.which("python") or shutil.which("py")),
            node=bool(shutil.which("node")),
            npm=bool(shutil.which("npm")),
            yarn=bool(shutil.which("yarn")),
            pnpm=bool(shutil.which("pnpm")),
            cargo=bool(shutil.which("cargo")),
            go=bool(shutil.which("go")),
            pytest=bool(shutil.which("pytest")),
            ruff=bool(shutil.which("ruff")),
            black=bool(shutil.which("black")),
            note="Use project_detect first; run_tests/lint/format then dispatch by detected stack.",
        )
    if action == "project_detect":
        return _developer_project_detect(args)
    if action == "run_tests":
        return _developer_run("tests", args)
    if action == "run_lint":
        return _developer_run("lint", args)
    if action == "run_format":
        return _developer_run("format", args)
    if action == "git_status":
        return _developer_git(["status", "--short", "--branch"], args)
    if action == "git_diff":
        cmd = ["diff"]
        if bool(args.get("staged", False)):
            cmd.append("--staged")
        return _developer_git(cmd, args)
    if action == "git_log":
        limit = int(args.get("limit", 10))
        return _developer_git(["log", "--oneline", f"-{limit}"], args)
    if action == "start_dev_server":
        return _developer_start_dev_server(args, state)
    if action == "stop_dev_server":
        return _developer_stop_dev_server(args, state)
    if action == "list_dev_servers":
        servers = _resources_by_kind(state, "dev_server", include_closed=bool(args.get("include_closed", False)))
        return _ok(servers=servers, count=len(servers))
    if action in {"git_commit", "git_push"}:
        return _err(
            f"developer.{action} is intentionally not implemented; use terminal(...) so the command is visible to the user",
            status="needs_user",
            note="Mutating git actions should be explicit, not hidden behind a tool wrapper.",
        )
    return _err(
        "unknown developer action", action=action,
        valid_actions=[
            "status", "project_detect", "run_tests", "run_build",
            "lint", "format", "git_status", "git_log", "git_diff",
            "git_branch", "git_commit",
        ],
        status="needs_user",
    )


def _developer_project_root(args: dict[str, Any]) -> Path:
    raw = str(args.get("path") or args.get("root") or "").strip()
    return Path(raw).expanduser() if raw else Path.cwd()


def _developer_project_detect(args: dict[str, Any]) -> dict[str, Any]:
    root = _developer_project_root(args)
    if not root.exists():
        return _err("path not found", path=str(root))
    markers = {
        "package.json": "node",
        "pyproject.toml": "python",
        "setup.py": "python",
        "requirements.txt": "python",
        "Cargo.toml": "rust",
        "go.mod": "go",
        "pom.xml": "java",
        "build.gradle": "java",
        "Gemfile": "ruby",
        "composer.json": "php",
        "CMakeLists.txt": "cmake",
    }
    detected: list[dict[str, Any]] = []
    for marker, stack in markers.items():
        path = root / marker
        if path.is_file():
            detected.append({"marker": marker, "stack": stack, "path": str(path)})
    # Node sub-detection: detect package manager.
    node_pm = None
    if any(d["stack"] == "node" for d in detected):
        if (root / "pnpm-lock.yaml").is_file():
            node_pm = "pnpm"
        elif (root / "yarn.lock").is_file():
            node_pm = "yarn"
        elif (root / "package-lock.json").is_file():
            node_pm = "npm"
        else:
            node_pm = "npm"  # default
    # Python sub-detection: poetry vs pip.
    python_pm = None
    if any(d["stack"] == "python" for d in detected):
        if (root / "poetry.lock").is_file():
            python_pm = "poetry"
        elif (root / "uv.lock").is_file():
            python_pm = "uv"
        else:
            python_pm = "pip"
    is_git = (root / ".git").exists()
    return _ok(
        root=str(root),
        is_git=is_git,
        detected=detected,
        stacks=sorted({d["stack"] for d in detected}),
        node_package_manager=node_pm,
        python_package_manager=python_pm,
    )


def _developer_run(kind: str, args: dict[str, Any]) -> dict[str, Any]:
    detect = _developer_project_detect(args)
    if not detect.get("ok"):
        return detect
    stacks = detect.get("stacks") or []
    root = Path(detect["root"])
    raw_extra_args = args.get("args")
    extra_args: list[Any] = raw_extra_args if isinstance(raw_extra_args, list) else []
    timeout = int(args.get("timeout_sec", 300))
    # Pick a command for the (stack, kind) pair. We use the first matched stack
    # in priority order: python > node > rust > go.
    priority = ["python", "node", "rust", "go", "java", "ruby", "php"]
    chosen_stack = next((s for s in priority if s in stacks), None)
    if not chosen_stack:
        return _err("no recognized stack to run for", kind=kind, detected=stacks, status="needs_user")
    cmd = _developer_command(chosen_stack, kind, detect, extra_args)
    if not cmd:
        return _err(
            f"developer.{kind} not wired for stack '{chosen_stack}'",
            stack=chosen_stack, kind=kind,
            status="needs_implementation",
            note="Pass explicit command via args=[...] to terminal(...) instead.",
        )
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=timeout)
    return _ok(
        stack=chosen_stack, kind=kind,
        command=cmd, cwd=str(root),
        exit_code=proc.returncode,
        stdout=(proc.stdout or "")[-4000:],
        stderr=(proc.stderr or "")[-2000:],
        passed=proc.returncode == 0,
        verified=proc.returncode == 0,
        status="done" if proc.returncode == 0 else "needs_verification",
    )


def _developer_command(stack: str, kind: str, detect: dict[str, Any], extra: list[Any]) -> list[str] | None:
    if stack == "python":
        if kind == "tests":
            return ["pytest", *map(str, extra)]
        if kind == "lint":
            if shutil.which("ruff"):
                return ["ruff", "check", "."]
            if shutil.which("flake8"):
                return ["flake8"]
        if kind == "format":
            if shutil.which("ruff"):
                return ["ruff", "format", "."]
            if shutil.which("black"):
                return ["black", "."]
    if stack == "node":
        pm = detect.get("node_package_manager") or "npm"
        if kind == "tests":
            return [pm, "test", *map(str, extra)]
        if kind == "lint":
            return [pm, "run", "lint"]
        if kind == "format":
            return [pm, "run", "format"]
    if stack == "rust":
        if kind == "tests":
            return ["cargo", "test"]
        if kind == "lint":
            return ["cargo", "clippy"]
        if kind == "format":
            return ["cargo", "fmt"]
    if stack == "go":
        if kind == "tests":
            return ["go", "test", "./..."]
        if kind == "lint":
            return ["go", "vet", "./..."]
        if kind == "format":
            return ["gofmt", "-w", "."]
    return None


def _developer_git(git_args: list[str], args: dict[str, Any]) -> dict[str, Any]:
    git = shutil.which("git")
    if not git:
        return _err("git is not installed", status="needs_dependency", install_hint="winget install Git.Git")
    root = _developer_project_root(args)
    proc = subprocess.run([git, *git_args], cwd=str(root), capture_output=True, text=True, timeout=30)
    return _ok(
        cwd=str(root),
        command=["git", *git_args],
        exit_code=proc.returncode,
        stdout=(proc.stdout or "")[-6000:],
        stderr=(proc.stderr or "")[-2000:],
        verified=proc.returncode == 0,
        status="done" if proc.returncode == 0 else "needs_verification",
    )


def _developer_start_dev_server(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    root = _developer_project_root(args)
    if not root.exists():
        return _err("path not found", path=str(root))
    explicit = args.get("command")
    if isinstance(explicit, list) and explicit:
        cmd = [str(part) for part in explicit]
    elif isinstance(explicit, str) and explicit.strip():
        cmd = explicit.split()
    else:
        detect = _developer_project_detect({"path": str(root)})
        if not detect.get("ok"):
            return detect
        stacks = detect.get("stacks") or []
        if "node" in stacks:
            pm = detect.get("node_package_manager") or "npm"
            cmd = [pm, "run", "dev"]
        elif "python" in stacks:
            # No universal dev command for python; the user must pass command=.
            return _err(
                "no default dev command for python; pass command='uvicorn app:app --reload' or similar",
                stack="python",
                status="needs_user",
            )
        else:
            return _err("no default dev command for detected stack", stacks=stacks, status="needs_user")
    log_dir = state.path.parent / "dev_servers"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"dev_{int(time.time())}.log"
    log_file = log_path.open("w", encoding="utf-8")
    # T3-developer-start-no-creationflags-detach-037: detach del agent process
    # group para que el dev server sobreviva al cierre del agente.
    creationflags = 0
    if os.name == "nt":
        creationflags = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.CREATE_NEW_PROCESS_GROUP
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    proc = subprocess.Popen(cmd, cwd=str(root), stdout=log_file, stderr=subprocess.STDOUT, creationflags=creationflags)
    resource = state.register_resource(
        "dev_server",
        f"{cmd[0]} {' '.join(cmd[1:])}",
        cleanup_tool="developer",
        cleanup_args={"action": "stop_dev_server"},
        metadata={"cmd": cmd, "cwd": str(root), "pid": proc.pid, "log": str(log_path), "started_at": datetime.now().isoformat()},
    )
    # The cleanup_args needs the server_id, but we only have it after registration.
    # CC-102: patch atómico vía API pública.
    rid = resource.get("resource", {}).get("id")
    if rid:
        state.update_resource(rid, cleanup_args_patch={"action": "stop_dev_server", "server_id": rid})
    return _ok(
        server_id=rid, pid=proc.pid, cmd=cmd, cwd=str(root),
        log=str(log_path),
        note="Process detached; use list_dev_servers to inspect and stop_dev_server to terminate.",
    )


def _developer_stop_dev_server(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    from .helpers import _pid_owned_by, _resources_by_kind
    server_id = str(args.get("server_id") or args.get("id") or "").strip()
    pid = args.get("pid")
    target = None
    if server_id:
        target = state._load().get("resources", {}).get(server_id)
    elif pid is not None:
        for res in state._load().get("resources", {}).values():
            if res.get("kind") == "dev_server" and (res.get("metadata") or {}).get("pid") == int(pid):
                target = res
                break
    else:
        # Stop the most recent open dev_server.
        opens = _resources_by_kind(state, "dev_server", include_closed=False)
        target = opens[-1] if opens else None
    if not target:
        return _err("no dev_server found", status="needs_user")
    pid = (target.get("metadata") or {}).get("pid")
    if not pid:
        return _err("dev_server has no pid", target=target)
    # CC-104 / T3-developer-stop-no-pid-alive-check-036: verificar identidad
    # antes de matar (Windows recicla PIDs).
    cmd = (target.get("metadata") or {}).get("cmd") or []
    expected = str(cmd[0]) if cmd else None
    matches, current_name = _pid_owned_by(int(pid), expected)
    if not matches:
        return _err(
            "pid_recycled: refused to kill PID held by a different process",
            pid=pid,
            expected_exe=expected,
            current_name=current_name,
            status="needs_user",
        )
    killed = False
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"], capture_output=True, text=True, timeout=10)
        else:
            os.kill(int(pid), 15)
        killed = True
    except (subprocess.SubprocessError, ProcessLookupError, PermissionError, OSError) as exc:
        return _err(f"failed to kill pid {pid}: {exc}", pid=pid)
    state.mark_cleaned(str(target["id"]), {"killed": killed, "pid": pid})
    return _ok(server_id=str(target["id"]), pid=pid, killed=killed, verified=killed)
