"""Higher-level local operations for the Gemma 4 Windows agent."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from .state import AgentState


Executor = Callable[[str, dict[str, Any]], dict[str, Any]]
_PW: Any | None = None
_BROWSER_SESSIONS: dict[str, dict[str, Any]] = {}


def _ok(**kwargs: Any) -> dict[str, Any]:
    return {"ok": True, **kwargs}


def _err(message: str, **kwargs: Any) -> dict[str, Any]:
    return {"ok": False, "error": message, **kwargs}


def state_tool(args: dict[str, Any], state: AgentState, execute: Executor) -> dict[str, Any]:
    action = str(args.get("action") or "resources").casefold()
    resource_id = str(args.get("resource_id") or "").strip() or None
    checkpoint_id = str(args.get("checkpoint_id") or "").strip() or None

    if action == "resources":
        return state.list_resources(include_closed=bool(args.get("include_closed", False)))
    if action == "cleanup_plan":
        return state.cleanup_plan(resource_id)
    if action == "cleanup":
        plan = state.cleanup_plan(resource_id)
        if not plan.get("ok"):
            return plan
        results = []
        for item in plan.get("cleanup_items", []):
            tool = item.get("cleanup_tool")
            tool_args = item.get("cleanup_args") or {}
            if not tool:
                continue
            result = execute(str(tool), dict(tool_args))
            if result.get("ok") and result.get("status") not in {"failed", "needs_confirmation", "needs_user"}:
                state.mark_cleaned(str(item.get("id")), result)
            results.append({"resource_id": item.get("id"), "tool": tool, "args": tool_args, "result": result})
        return _ok(cleaned_count=len(results), results=results)
    if action == "checkpoint":
        rollback = args.get("rollback") if isinstance(args.get("rollback"), list) else []
        metadata = args.get("metadata") if isinstance(args.get("metadata"), dict) else {}
        return state.checkpoint(str(args.get("label") or "manual checkpoint"), rollback=rollback, metadata=metadata)
    if action == "checkpoints":
        return state.list_checkpoints()
    if action == "rollback_plan":
        return state.rollback_plan(checkpoint_id)
    if action == "rollback":
        plan = state.rollback_plan(checkpoint_id)
        if not plan.get("ok"):
            return plan
        results = []
        for step in plan.get("rollback", []):
            if not isinstance(step, dict):
                continue
            tool = str(step.get("tool") or "").strip()
            tool_args = step.get("args") if isinstance(step.get("args"), dict) else {}
            if not tool:
                continue
            results.append({"tool": tool, "args": tool_args, "result": execute(tool, tool_args)})
        return _ok(checkpoint=plan.get("checkpoint"), rollback_count=len(results), results=results)
    if action == "note":
        return state.note(str(args.get("text") or ""), metadata=args.get("metadata") if isinstance(args.get("metadata"), dict) else {})
    return _err("unknown state action", action=action)


def input_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "language_list").casefold()
    if action in {"language_list", "keyboard_layouts"}:
        return _windows_language_list()
    if action == "current_keyboard":
        return _current_keyboard()
    if action in {"set_language_list", "switch_keyboard"}:
        tags = args.get("language_tags")
        if not isinstance(tags, list) or not tags:
            tag = str(args.get("language_tag") or "").strip()
            tags = [tag] if tag else []
        tags = [str(tag).strip() for tag in tags if str(tag).strip()]
        if not tags:
            return _err("missing language_tags", status="needs_user", verified=False, completion_status="needs_user")
        before = _windows_language_list()
        rollback_tags = [item.get("language_tag") for item in before.get("languages", []) if item.get("language_tag")]
        checkpoint = state.checkpoint(
            "keyboard/language list before change",
            rollback=[{"tool": "input", "args": {"action": "set_language_list", "language_tags": rollback_tags, "force": True}}],
            metadata={"source": "Set-WinUserLanguageList"},
        )
        env = os.environ.copy()
        env["GEMMA4_LANGUAGE_TAGS"] = json.dumps(tags)
        env["GEMMA4_FORCE"] = "1" if bool(args.get("force", True)) else "0"
        script = r"""
$ErrorActionPreference = "Stop"
$tags = $env:GEMMA4_LANGUAGE_TAGS | ConvertFrom-Json
$list = New-Object 'System.Collections.Generic.List[Microsoft.InternationalSettings.Commands.WinUserLanguage]'
foreach ($tag in $tags) {
  $entry = New-WinUserLanguageList -Language $tag
  $list.Add($entry[0]) | Out-Null
}
Set-WinUserLanguageList -LanguageList $list -Force:([bool]([int]$env:GEMMA4_FORCE))
$items = @()
foreach ($lang in (Get-WinUserLanguageList)) {
  $items += [PSCustomObject]@{
    LanguageTag=$lang.LanguageTag
    EnglishName=$lang.EnglishName
    LocalizedName=$lang.LocalizedName
    InputMethodTips=@($lang.InputMethodTips)
  }
}
$items | ConvertTo-Json -Depth 4
"""
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=40)
        if proc.returncode != 0:
            return _err("failed to set language list", stderr=_truncate(proc.stderr, 2000), checkpoint=checkpoint.get("checkpoint"))
        return _ok(action=action, language_tags=tags, checkpoint=checkpoint.get("checkpoint"), result=_json_or_text(proc.stdout))
    return _err("unknown input action", action=action)


def env_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "get").casefold()
    scope = str(args.get("scope") or "process").casefold()
    name = str(args.get("name") or "").strip()
    target = _env_target(scope)
    if not target:
        return _err("invalid env scope", scope=scope)

    if action == "list":
        if scope == "process":
            items = [{"name": key, "value": value} for key, value in sorted(os.environ.items())]
            return _ok(scope=scope, variables=items[: int(args.get("limit", 200))], count=len(items))
        return _env_ps("list", target, "", "")
    if not name:
        return _err("missing env var name")
    if action == "get":
        if scope == "process":
            return _ok(scope=scope, name=name, value=os.environ.get(name), exists=name in os.environ)
        return _env_ps("get", target, name, "")
    if action in {"set", "delete"}:
        previous = env_tool({"action": "get", "scope": scope, "name": name}, state)
        value = "" if action == "delete" else str(args.get("value") or "")
        rollback_value = previous.get("value")
        rollback_args = {"action": "delete", "scope": scope, "name": name}
        if rollback_value is not None:
            rollback_args = {"action": "set", "scope": scope, "name": name, "value": rollback_value}
        checkpoint = state.checkpoint(
            f"env {scope}:{name} before {action}",
            rollback=[{"tool": "env", "args": rollback_args}],
            metadata={"previous": previous},
        )
        if scope == "process":
            if action == "delete":
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
            return _ok(scope=scope, name=name, action=action, checkpoint=checkpoint.get("checkpoint"), value=os.environ.get(name))
        result = _env_ps("delete" if action == "delete" else "set", target, name, value)
        result["checkpoint"] = checkpoint.get("checkpoint")
        return result
    return _err("unknown env action", action=action)


def registry_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "query").casefold()
    key = str(args.get("key") or args.get("path") or "").strip()
    name = str(args.get("name") or args.get("value_name") or "").strip()
    if action in {"query", "export", "backup", "add", "delete"} and not key:
        return _err("missing registry key/path")

    if action == "query":
        cmd = ["reg", "query", key]
        if name:
            cmd.extend(["/v", name])
        return _run_cmd(cmd, timeout=20)
    if action in {"export", "backup"}:
        out = str(args.get("file") or args.get("dst") or "").strip()
        path = Path(out).expanduser() if out else _registry_backup_path(state, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        result = _run_cmd(["reg", "export", key, str(path), "/y"], timeout=30)
        result.update(file=str(path.resolve()), registry_key=key)
        return result
    if action == "import":
        file_path = Path(str(args.get("file") or args.get("path") or "")).expanduser()
        if not file_path.is_file():
            return _err("registry import file not found", file=str(file_path))
        return _run_cmd(["reg", "import", str(file_path)], timeout=30)
    if action == "add":
        if not name:
            return _err("missing registry value name")
        backup = registry_tool({"action": "backup", "key": key}, state)
        value_type = str(args.get("type") or "REG_SZ")
        data = str(args.get("data") or args.get("value") or "")
        rollback = [{"tool": "registry", "args": {"action": "import", "file": backup.get("file")}}] if backup.get("ok") else [
            {"tool": "registry", "args": {"action": "delete", "key": key, "name": name}}
        ]
        checkpoint = state.checkpoint(f"registry {key}\\{name} before add", rollback=rollback, metadata={"backup": backup})
        result = _run_cmd(["reg", "add", key, "/v", name, "/t", value_type, "/d", data, "/f"], timeout=30)
        result.update(backup=backup, checkpoint=checkpoint.get("checkpoint"), registry_key=key, value_name=name)
        return result
    if action == "delete":
        backup = registry_tool({"action": "backup", "key": key}, state)
        rollback = [{"tool": "registry", "args": {"action": "import", "file": backup.get("file")}}] if backup.get("ok") else []
        checkpoint = state.checkpoint(f"registry {key} before delete", rollback=rollback, metadata={"backup": backup})
        cmd = ["reg", "delete", key]
        if name:
            cmd.extend(["/v", name])
        cmd.append("/f")
        result = _run_cmd(cmd, timeout=30)
        result.update(backup=backup, checkpoint=checkpoint.get("checkpoint"), registry_key=key, value_name=name or None)
        return result
    return _err("unknown registry action", action=action)


def download_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "fetch").casefold()
    if action == "hash":
        path = Path(str(args.get("path") or "")).expanduser()
        return _file_hash(path, str(args.get("algorithm") or "SHA256"))
    if action == "signature":
        path = Path(str(args.get("path") or "")).expanduser()
        return _authenticode_signature(path)
    if action != "fetch":
        return _err("unknown download action", action=action)

    url = str(args.get("url") or "").strip()
    if not url:
        return _err("missing url")
    dst_raw = str(args.get("path") or args.get("dst") or "").strip()
    dst = Path(dst_raw).expanduser() if dst_raw else _download_default_path(state, url)
    if dst.exists() and not bool(args.get("overwrite", False)):
        return _err("download target already exists", path=str(dst), status="needs_user", verified=False)
    dst.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["GEMMA4_DOWNLOAD_URL"] = url
    env["GEMMA4_DOWNLOAD_PATH"] = str(dst)
    script = r"""
$ErrorActionPreference = "Stop"
Invoke-WebRequest -Uri $env:GEMMA4_DOWNLOAD_URL -OutFile $env:GEMMA4_DOWNLOAD_PATH -UseBasicParsing
[PSCustomObject]@{ path=$env:GEMMA4_DOWNLOAD_PATH; bytes=(Get-Item $env:GEMMA4_DOWNLOAD_PATH).Length } | ConvertTo-Json
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=int(args.get("timeout_sec", 300)))
    if proc.returncode != 0:
        return _err("download failed", url=url, path=str(dst), stderr=_truncate(proc.stderr, 2000), exit_code=proc.returncode)

    hash_result = _file_hash(dst, "SHA256")
    expected = str(args.get("sha256") or args.get("expected_sha256") or "").strip().casefold()
    actual = str(hash_result.get("hash") or "").casefold()
    hash_verified = bool(expected and actual and expected == actual)
    sig_result = _authenticode_signature(dst) if dst.suffix.casefold() in {".exe", ".msi", ".ps1", ".dll"} else {}
    signature_verified = sig_result.get("status") == "Valid"
    verified = hash_verified or signature_verified
    resource = state.register_resource(
        "download",
        str(dst.name),
        cleanup_tool="filesystem",
        cleanup_args={"action": "delete", "path": str(dst)},
        metadata={"url": url, "sha256": actual},
    )
    return _ok(
        url=url,
        path=str(dst.resolve()),
        bytes=dst.stat().st_size,
        sha256=actual,
        expected_sha256=expected or None,
        hash_verified=hash_verified,
        signature=sig_result or None,
        signature_verified=signature_verified,
        verified=verified,
        status="done" if verified else "needs_verification",
        completion_status="download_verified" if verified else "download_unverified",
        resource=resource.get("resource"),
    )


def email_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "status").casefold()
    token = os.environ.get("GEMMA4_GRAPH_TOKEN") or os.environ.get("MS_GRAPH_TOKEN")
    if action == "status":
        return _ok(provider="microsoft_graph", has_token=bool(token), auth_env_vars=["GEMMA4_GRAPH_TOKEN", "MS_GRAPH_TOKEN"])
    if action == "draft":
        return state.note("email draft", metadata={"to": args.get("to"), "subject": args.get("subject"), "body": args.get("body")})
    if action != "send":
        return _err("unknown email action", action=action)
    if not token:
        return _err(
            "missing Microsoft Graph token",
            status="needs_user",
            verified=False,
            completion_status="needs_user_auth",
            provider="microsoft_graph",
            required_env="GEMMA4_GRAPH_TOKEN",
        )
    to = _string_list(args.get("to"))
    if not to:
        return _err("missing email recipient", status="needs_user", verified=False)
    payload = {
        "message": {
            "subject": str(args.get("subject") or ""),
            "body": {"contentType": "Text", "content": str(args.get("body") or "")},
            "toRecipients": [{"emailAddress": {"address": addr}} for addr in to],
        },
        "saveToSentItems": bool(args.get("save_to_sent", True)),
    }
    req = urllib.request.Request(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=int(args.get("timeout_sec", 30))) as resp:
            return _ok(provider="microsoft_graph", status_code=resp.status, sent=True, to=to)
    except Exception as exc:
        return _err(f"Microsoft Graph sendMail failed: {exc}", provider="microsoft_graph", to=to)


def reminder_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "list").casefold()
    backend = str(args.get("backend") or "state").casefold()
    if action == "status":
        return _ok(local_state=True, graph_token=bool(os.environ.get("GEMMA4_GRAPH_TOKEN") or os.environ.get("MS_GRAPH_TOKEN")))
    if action == "list":
        resources = state.list_resources(include_closed=bool(args.get("include_closed", False))).get("resources", [])
        reminders = [res for res in resources if res.get("kind") == "reminder"]
        return _ok(reminders=reminders, count=len(reminders))
    if action == "delete":
        rid = str(args.get("id") or args.get("resource_id") or "").strip()
        if not rid:
            return _err("missing reminder id")
        return state.mark_cleaned(rid, {"deleted": True})
    if action != "create":
        return _err("unknown reminder action", action=action)
    if backend == "graph":
        return _err(
            "Microsoft Graph To Do/Calendar auth is not configured in this local prototype",
            status="needs_user",
            verified=False,
            completion_status="needs_user_auth",
            required_env="GEMMA4_GRAPH_TOKEN",
        )
    title = str(args.get("title") or args.get("text") or "").strip()
    if not title:
        return _err("missing reminder title/text")
    resource = state.register_resource(
        "reminder",
        title,
        metadata={"due": args.get("due"), "backend": "state", "text": args.get("text") or title},
    )
    return _ok(reminder=resource.get("resource"), backend="state", note="Stored locally as agent state; no OS notification was scheduled.")


def browser_real_tool(args: dict[str, Any], state: AgentState, captures_dir: Path) -> dict[str, Any]:
    action = str(args.get("action") or "status").casefold()
    available = importlib.util.find_spec("playwright") is not None
    if action == "status":
        return _ok(
            engine="playwright",
            available=available,
            persistent_session=True,
            sessions=[_session_summary(sid, session) for sid, session in _BROWSER_SESSIONS.items()],
        )
    if action == "close":
        session_id = str(args.get("session_id") or "default")
        return _close_browser_session(session_id, state)
    if not available:
        return _err(
            "Playwright is not installed for this Python environment",
            status="needs_user",
            verified=False,
            completion_status="needs_dependency",
            install_hint="python -m pip install playwright && python -m playwright install chromium",
        )

    session_id = str(args.get("session_id") or "default")
    url = str(args.get("url") or args.get("query") or "").strip()
    selector = str(args.get("selector") or "").strip()
    value = str(args.get("value") or args.get("text") or "").strip()
    headless = bool(args.get("headless", True))
    timeout_ms = int(float(args.get("timeout_sec", 30)) * 1000)
    captures_dir.mkdir(parents=True, exist_ok=True)

    if action == "tabs":
        session = _BROWSER_SESSIONS.get(session_id)
        if not session:
            return _ok(session_id=session_id, tabs=[], count=0)
        return _ok(session_id=session_id, tabs=_tabs(session), count=len(session.get("pages") or []))

    if action == "connect_cdp":
        endpoint = str(args.get("endpoint") or args.get("url") or "http://127.0.0.1:9222").strip()
        session = _connect_cdp_session(session_id, endpoint)
        return _ok(session_id=session_id, endpoint=endpoint, tabs=_tabs(session), note="Connected over CDP. Browser must have been started with a remote debugging port.")

    if action in {"open", "goto"}:
        if not url:
            return _err("browser_real open/goto requires url")
        session = _get_browser_session(session_id, state, headless=headless)
        page = _active_page(session, new_tab=bool(args.get("new_tab", action == "open")))
        page.goto(url, wait_until=str(args.get("wait_until") or "domcontentloaded"), timeout=timeout_ms)
        result = _page_result(session_id, session, page)
        if bool(args.get("screenshot", False)):
            result.update(_page_screenshot(page, captures_dir, bool(args.get("full_page", False))))
        return _ok(**result, verified=True, content_verified=bool(result.get("title")))

    session = _BROWSER_SESSIONS.get(session_id)
    if not session:
        return _err("browser session not found", session_id=session_id, status="needs_user", completion_status="needs_browser_session")
    page = _active_page(session, page_id=args.get("page_id"))

    if action == "click":
        if not selector:
            return _err("click requires selector")
        page.click(selector, timeout=timeout_ms)
        return _ok(**_page_result(session_id, session, page), clicked=selector, verified=True, content_verified=True)
    if action == "fill":
        if not selector:
            return _err("fill requires selector")
        page.fill(selector, value, timeout=timeout_ms)
        return _ok(**_page_result(session_id, session, page), filled=selector, chars=len(value), verified=True, content_verified=True)
    if action == "press":
        key = str(args.get("key") or value or "Enter")
        page.press(selector or "body", key, timeout=timeout_ms)
        return _ok(**_page_result(session_id, session, page), pressed=key, selector=selector or "body", verified=True, content_verified=True)
    if action == "text":
        text = page.inner_text(selector or "body", timeout=timeout_ms)[: int(args.get("max_chars", 8000))]
        return _ok(**_page_result(session_id, session, page), text=text, verified=True, content_verified=True)
    if action == "screenshot":
        return _ok(**_page_result(session_id, session, page), **_page_screenshot(page, captures_dir, bool(args.get("full_page", False))), verified=True)
    if action == "evaluate":
        script = str(args.get("script") or "")
        if not script:
            return _err("evaluate requires script")
        value = page.evaluate(script)
        return _ok(**_page_result(session_id, session, page), value=value, verified=True, content_verified=True)
    return _err("unknown browser_real action", action=action)


def ocr_image(image_path: Path, *, lang: str = "spa+eng", min_conf: int = 35) -> dict[str, Any]:
    if not image_path.is_file():
        return _err("image not found", image_path=str(image_path))
    tesseract = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if not tesseract:
        return _err(
            "Tesseract OCR is not installed or not on PATH",
            status="needs_user",
            verified=False,
            completion_status="needs_dependency",
            install_hint="winget install UB-Mannheim.TesseractOCR",
        )
    cmd = [tesseract, str(image_path), "stdout", "-l", lang, "--psm", "6", "tsv"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return _err("tesseract failed", image_path=str(image_path), stderr=_truncate(proc.stderr, 2000), exit_code=proc.returncode)
    words = _parse_tesseract_tsv(proc.stdout, min_conf=min_conf)
    text = " ".join(word["text"] for word in words)
    lines = _ocr_lines(words)
    return _ok(
        image_path=str(image_path.resolve()),
        lang=lang,
        words=words[:500],
        lines=lines[:200],
        text=_truncate(text, 12000),
        word_count=len(words),
        line_count=len(lines),
        content_verified=True,
    )


def ocr_find_text(image_path: Path, target: str, *, lang: str = "spa+eng", min_conf: int = 25) -> dict[str, Any]:
    ocr = ocr_image(image_path, lang=lang, min_conf=min_conf)
    if not ocr.get("ok"):
        return ocr
    target_fold = _fold_local(target)
    matches = []
    for line in ocr.get("lines", []):
        line_text = str(line.get("text") or "")
        if target_fold and target_fold in _fold_local(line_text):
            matches.append(line)
    if not matches:
        for word in ocr.get("words", []):
            if target_fold and target_fold in _fold_local(str(word.get("text") or "")):
                matches.append(word)
    return _ok(
        image_path=str(image_path.resolve()),
        target=target,
        found=bool(matches),
        matches=matches[:20],
        ocr_text=ocr.get("text", ""),
        content_verified=bool(matches),
        visual_verified=bool(matches),
    )


def _playwright() -> Any:
    global _PW
    if _PW is None:
        from playwright.sync_api import sync_playwright

        _PW = sync_playwright().start()
    return _PW


def _get_browser_session(session_id: str, state: AgentState, *, headless: bool) -> dict[str, Any]:
    session = _BROWSER_SESSIONS.get(session_id)
    if session:
        return session
    pw = _playwright()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context()
    session = {"browser": browser, "context": context, "pages": [], "active": 0, "headless": headless, "cdp": False}
    resource = state.register_resource(
        "browser_real",
        f"Playwright session {session_id}",
        cleanup_tool="browser_real",
        cleanup_args={"action": "close", "session_id": session_id},
        metadata={"headless": headless},
    )
    session["resource"] = resource.get("resource")
    _BROWSER_SESSIONS[session_id] = session
    return session


def _connect_cdp_session(session_id: str, endpoint: str) -> dict[str, Any]:
    existing = _BROWSER_SESSIONS.get(session_id)
    if existing:
        _close_browser_session(session_id)
    pw = _playwright()
    browser = pw.chromium.connect_over_cdp(endpoint)
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    pages = list(context.pages)
    session = {"browser": browser, "context": context, "pages": pages, "active": 0, "headless": False, "cdp": True, "endpoint": endpoint}
    _BROWSER_SESSIONS[session_id] = session
    return session


def _close_browser_session(session_id: str, state: AgentState | None = None) -> dict[str, Any]:
    session = _BROWSER_SESSIONS.pop(session_id, None)
    if not session:
        return _ok(engine="playwright", session_id=session_id, closed=False, note="browser session was not open")
    errors: list[str] = []
    for obj_name in ("context", "browser"):
        obj = session.get(obj_name)
        if not obj:
            continue
        try:
            obj.close()
        except Exception as exc:
            errors.append(f"{obj_name}: {exc}")
    result = _ok(engine="playwright", session_id=session_id, closed=True, errors=errors)
    resource = session.get("resource") or {}
    if state and resource.get("id"):
        state.mark_cleaned(str(resource["id"]), result)
    return result


def _active_page(session: dict[str, Any], page_id: Any | None = None, *, new_tab: bool = False) -> Any:
    pages = session.setdefault("pages", [])
    if page_id is not None:
        index = int(page_id)
        if 0 <= index < len(pages):
            session["active"] = index
            return pages[index]
    if new_tab or not pages:
        page = session["context"].new_page()
        pages.append(page)
        session["active"] = len(pages) - 1
        return page
    index = max(0, min(int(session.get("active", 0)), len(pages) - 1))
    session["active"] = index
    return pages[index]


def _tabs(session: dict[str, Any]) -> list[dict[str, Any]]:
    tabs = []
    pages = [page for page in session.get("context").pages if not page.is_closed()]
    session["pages"] = pages
    for index, page in enumerate(pages):
        try:
            tabs.append({"page_id": index, "url": page.url, "title": page.title(), "active": index == int(session.get("active", 0))})
        except Exception:
            tabs.append({"page_id": index, "url": "", "title": "", "active": index == int(session.get("active", 0))})
    return tabs


def _page_result(session_id: str, session: dict[str, Any], page: Any) -> dict[str, Any]:
    pages = session.setdefault("pages", [])
    if page not in pages:
        pages.append(page)
    session["active"] = pages.index(page)
    return {"session_id": session_id, "page_id": session["active"], "url": page.url, "title": page.title(), "engine": "playwright", "tabs": _tabs(session)}


def _page_screenshot(page: Any, captures_dir: Path, full_page: bool) -> dict[str, Any]:
    name = f"browser_real_{int(time.time())}.png"
    shot = captures_dir / name
    page.screenshot(path=str(shot), full_page=full_page)
    return {"image_path": str(shot.resolve())}


def _session_summary(session_id: str, session: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "headless": bool(session.get("headless")),
        "cdp": bool(session.get("cdp")),
        "tabs": _tabs(session),
        "resource": session.get("resource"),
    }


def _parse_tesseract_tsv(text: str, *, min_conf: int) -> list[dict[str, Any]]:
    rows = []
    reader = csv_dict_reader(text)
    for row in reader:
        raw = str(row.get("text") or "").strip()
        if not raw:
            continue
        try:
            conf = float(row.get("conf") or -1)
        except ValueError:
            conf = -1
        if conf < min_conf:
            continue
        try:
            left = int(float(row.get("left") or 0))
            top = int(float(row.get("top") or 0))
            width = int(float(row.get("width") or 0))
            height = int(float(row.get("height") or 0))
        except ValueError:
            continue
        rows.append({
            "text": raw,
            "conf": conf,
            "left": left,
            "top": top,
            "width": width,
            "height": height,
            "center_x": left + width // 2,
            "center_y": top + height // 2,
            "block": row.get("block_num"),
            "line": row.get("line_num"),
        })
    return rows


def _ocr_lines(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for word in words:
        grouped.setdefault((str(word.get("block")), str(word.get("line"))), []).append(word)
    lines = []
    for (_block, _line), items in grouped.items():
        items.sort(key=lambda item: int(item.get("left", 0)))
        left = min(int(item["left"]) for item in items)
        top = min(int(item["top"]) for item in items)
        right = max(int(item["left"]) + int(item["width"]) for item in items)
        bottom = max(int(item["top"]) + int(item["height"]) for item in items)
        text = " ".join(str(item["text"]) for item in items)
        lines.append({
            "text": text,
            "left": left,
            "top": top,
            "width": right - left,
            "height": bottom - top,
            "center_x": left + (right - left) // 2,
            "center_y": top + (bottom - top) // 2,
            "avg_conf": sum(float(item.get("conf", 0)) for item in items) / max(1, len(items)),
        })
    lines.sort(key=lambda item: (int(item["top"]), int(item["left"])))
    return lines


def csv_dict_reader(text: str) -> Any:
    import csv

    return csv.DictReader(io.StringIO(text), delimiter="\t")


def _fold_local(text: str) -> str:
    import unicodedata

    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def _windows_language_list() -> dict[str, Any]:
    script = r"""
$items = @()
foreach ($lang in (Get-WinUserLanguageList)) {
  $items += [PSCustomObject]@{
    LanguageTag=$lang.LanguageTag
    EnglishName=$lang.EnglishName
    LocalizedName=$lang.LocalizedName
    InputMethodTips=@($lang.InputMethodTips)
  }
}
$items | ConvertTo-Json -Depth 4
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("failed to read language list", stderr=_truncate(proc.stderr, 2000), exit_code=proc.returncode)
    data = _json_or_text(proc.stdout)
    if isinstance(data, dict):
        data = [data]
    languages = []
    for item in data if isinstance(data, list) else []:
        languages.append({
            "language_tag": item.get("LanguageTag"),
            "english_name": item.get("EnglishName"),
            "localized_name": item.get("LocalizedName"),
            "input_method_tips": item.get("InputMethodTips") or [],
        })
    return _ok(languages=languages, count=len(languages), exit_code=proc.returncode)


def _current_keyboard() -> dict[str, Any]:
    script = r"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class KeyboardNative {
  [DllImport("user32.dll")] public static extern IntPtr GetKeyboardLayout(uint idThread);
}
"@
$hkl = [KeyboardNative]::GetKeyboardLayout(0).ToInt64()
[PSCustomObject]@{ hkl=("0x{0:X}" -f $hkl); language_id=("0x{0:X4}" -f ($hkl -band 0xffff)) } | ConvertTo-Json
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=15)
    if proc.returncode != 0:
        return _err("failed to read current keyboard", stderr=_truncate(proc.stderr, 2000), exit_code=proc.returncode)
    return _ok(current=_json_or_text(proc.stdout), language_list=_windows_language_list().get("languages", []))


def _env_target(scope: str) -> str | None:
    return {"process": "Process", "user": "User", "machine": "Machine"}.get(scope)


def _env_ps(action: str, target: str, name: str, value: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["GEMMA4_ENV_ACTION"] = action
    env["GEMMA4_ENV_TARGET"] = target
    env["GEMMA4_ENV_NAME"] = name
    env["GEMMA4_ENV_VALUE"] = value
    script = r"""
$action=$env:GEMMA4_ENV_ACTION
$target=$env:GEMMA4_ENV_TARGET
$name=$env:GEMMA4_ENV_NAME
$value=$env:GEMMA4_ENV_VALUE
if ($action -eq "get") {
  $v=[Environment]::GetEnvironmentVariable($name,$target)
  [PSCustomObject]@{ name=$name; scope=$target; value=$v; exists=($null -ne $v) } | ConvertTo-Json
  exit 0
}
if ($action -eq "list") {
  [Environment]::GetEnvironmentVariables($target).GetEnumerator() |
    Sort-Object Name |
    Select-Object Name,Value |
    ConvertTo-Json -Depth 3
  exit 0
}
if ($action -eq "delete") { [Environment]::SetEnvironmentVariable($name,$null,$target) }
if ($action -eq "set") { [Environment]::SetEnvironmentVariable($name,$value,$target) }
$v=[Environment]::GetEnvironmentVariable($name,$target)
[PSCustomObject]@{ name=$name; scope=$target; value=$v; exists=($null -ne $v) } | ConvertTo-Json
"""
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        return _err("environment operation failed", stderr=_truncate(proc.stderr, 2000), exit_code=proc.returncode, scope=target)
    data = _json_or_text(proc.stdout)
    if action == "list" and isinstance(data, dict):
        data = [data]
    return _ok(scope=target.casefold(), result=data, exit_code=proc.returncode)


def _run_cmd(cmd: list[str], timeout: int) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return {
        "ok": proc.returncode == 0,
        "command": cmd,
        "exit_code": proc.returncode,
        "stdout": _truncate(proc.stdout.strip(), 3000),
        "stderr": _truncate(proc.stderr.strip(), 2000),
    }


def _registry_backup_path(state: AgentState, key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", key).strip("_")[:80] or "registry"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return state.path.parent / "registry_backups" / f"{stamp}_{safe}.reg"


def _download_default_path(state: AgentState, url: str) -> Path:
    parsed = urlparse(url)
    name = unquote(Path(parsed.path).name) or "download.bin"
    return state.path.parent / "downloads" / name


def _file_hash(path: Path, algorithm: str) -> dict[str, Any]:
    if not path.is_file():
        return _err("file not found", path=str(path))
    algo = algorithm.upper()
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Get-FileHash -Algorithm {algo} -LiteralPath $env:GEMMA4_HASH_PATH | ConvertTo-Json"],
        env={**os.environ, "GEMMA4_HASH_PATH": str(path)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        data = _json_or_text(proc.stdout)
        if isinstance(data, dict):
            return _ok(path=str(path.resolve()), algorithm=algo, hash=str(data.get("Hash") or "").lower())
    h = hashlib.new(algo.lower())
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return _ok(path=str(path.resolve()), algorithm=algo, hash=h.hexdigest(), fallback="python_hashlib")


def _authenticode_signature(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _err("file not found", path=str(path))
    env = {**os.environ, "GEMMA4_SIG_PATH": str(path)}
    script = "Get-AuthenticodeSignature -LiteralPath $env:GEMMA4_SIG_PATH | Select-Object Status,StatusMessage,SignerCertificate,Path | ConvertTo-Json -Depth 4"
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return _err("signature check failed", stderr=_truncate(proc.stderr, 2000), exit_code=proc.returncode)
    data = _json_or_text(proc.stdout)
    if not isinstance(data, dict):
        return _err("signature check returned invalid data", stdout=_truncate(str(data), 1000))
    return _ok(path=str(path.resolve()), status=data.get("Status"), status_message=data.get("StatusMessage"), signer_certificate=data.get("SignerCertificate"))


def _json_or_text(text: str) -> Any:
    raw = text.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[;,]", value) if part.strip()]
    return []


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + f"...<truncated {len(text) - limit} chars>"
