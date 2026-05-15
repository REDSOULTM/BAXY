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
import urllib.error
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
            raw_args = step.get("args")
            tool_args: dict[str, Any] = raw_args if isinstance(raw_args, dict) else {}
            if not tool:
                continue
            results.append({"tool": tool, "args": tool_args, "result": execute(tool, tool_args)})
        return _ok(checkpoint=plan.get("checkpoint"), rollback_count=len(results), results=results)
    if action == "note":
        raw_meta = args.get("metadata")
        meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
        text = str(args.get("text") or "").strip()
        if not text:
            return _err("state.note requires non-empty text", status="needs_user")
        return state.note(text, metadata=meta)
    return _err(
        "unknown state action", action=action,
        valid_actions=[
            "resources", "cleanup_plan", "cleanup", "checkpoint", "checkpoints",
            "rollback_plan", "rollback", "note",
        ],
        status="needs_user",
    )


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
    return _err(
        "unknown input action", action=action,
        valid_actions=["language_list", "keyboard_layouts", "current_keyboard",
                       "set_language_list", "switch_keyboard"],
        status="needs_user",
    )


def env_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "get").casefold()
    scope = str(args.get("scope") or "process").casefold()
    name = str(args.get("name") or "").strip()
    target = _env_target(scope)
    if not target:
        return _err(
            "invalid env scope", scope=scope,
            valid_scopes=["process", "user", "machine"], status="needs_user",
        )

    if action == "list":
        if scope == "process":
            items = [{"name": key, "value": value} for key, value in sorted(os.environ.items())]
            limit = int(args.get("limit", 200))
            return _ok(
                scope=scope, variables=items[:limit], count=len(items),
                truncated=len(items) > limit, source="os.environ",
            )
        # CONSISTENCIA: _env_ps devuelve {scope, result, exit_code}. Para
        # uniformidad con el path de process, normalizamos a {variables, count}.
        ps_result = _env_ps("list", target, "", "")
        if not ps_result.get("ok"):
            return ps_result
        raw = ps_result.get("result")
        items_list: list[dict[str, Any]] = []
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("Name"):
                    items_list.append({"name": str(item["Name"]), "value": str(item.get("Value") or "")})
        return _ok(
            scope=scope, variables=items_list, count=len(items_list),
            truncated=False, source="powershell",
        )

    if not name:
        return _err("missing env var name", action=action, status="needs_user")

    # VALIDACION nombre: no permitir caracteres invalidos que SetEnvironmentVariable
    # rechaza silenciosamente o convierte en bug raro.
    if "=" in name or "\x00" in name:
        return _err(
            "invalid env var name (contains '=' or NUL)",
            name=name, status="needs_user",
        )

    if action == "get":
        if scope == "process":
            value = os.environ.get(name)
            return _ok(
                scope=scope, name=name, value=value, exists=value is not None,
                source="os.environ",
            )
        ps_result = _env_ps("get", target, name, "")
        if not ps_result.get("ok"):
            return ps_result
        raw = ps_result.get("result") or {}
        if isinstance(raw, dict):
            return _ok(
                scope=scope, name=name,
                value=raw.get("value"),
                exists=bool(raw.get("exists")),
                source="powershell",
            )
        return _ok(scope=scope, name=name, value=None, exists=False, source="powershell")

    if action in {"set", "delete"}:
        previous = env_tool({"action": "get", "scope": scope, "name": name}, state)
        value = "" if action == "delete" else str(args.get("value") or "")
        # IDEMPOTENCIA: si la operacion es no-op (set a mismo valor, delete de
        # algo que no existe), evitamos crear un checkpoint redundante.
        prev_value = previous.get("value")
        prev_exists = bool(previous.get("exists"))
        if action == "delete" and not prev_exists:
            return _ok(
                scope=scope, name=name, action=action,
                noop=True, note="env var did not exist; nothing to delete",
                value=None, exists=False,
            )
        if action == "set" and prev_exists and prev_value == value:
            return _ok(
                scope=scope, name=name, action=action,
                noop=True, note="env var already has requested value",
                value=value, exists=True,
            )

        rollback_args = {"action": "delete", "scope": scope, "name": name}
        if prev_value is not None and prev_exists:
            rollback_args = {"action": "set", "scope": scope, "name": name, "value": prev_value}
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
            # VERIFICACION post-mutation:
            current = os.environ.get(name)
            expected = None if action == "delete" else value
            verified = current == expected
            return _ok(
                scope=scope, name=name, action=action,
                checkpoint=checkpoint.get("checkpoint"),
                value=current, verified=verified,
                source="os.environ",
            )
        result = _env_ps("delete" if action == "delete" else "set", target, name, value)
        result["checkpoint"] = checkpoint.get("checkpoint")
        # VERIFICACION post-mutation para machine/user scope.
        if result.get("ok"):
            post = env_tool({"action": "get", "scope": scope, "name": name}, state)
            current = post.get("value")
            expected = None if action == "delete" else value
            result["verified"] = current == expected
            result["value"] = current
        return result
    return _err(
        "unknown env action", action=action,
        valid_actions=["get", "set", "delete", "list"], status="needs_user",
    )


_VALID_REG_TYPES = {
    "REG_SZ", "REG_EXPAND_SZ", "REG_BINARY", "REG_DWORD", "REG_QWORD",
    "REG_MULTI_SZ", "REG_NONE",
}


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
        result = _run_cmd(cmd, timeout=15)  # antes 20, suficiente.
        # CONSISTENCIA: reg query devuelve exit 1 si la clave/valor no existe.
        # Esto NO es un error del agente; es informacion semantica. Convertir
        # a _ok(exists=False) para que el LLM distinga "registry call broken"
        # de "key not present".
        if not result.get("ok"):
            stderr_lower = str(result.get("stderr") or "").lower()
            if (
                "no se puede encontrar" in stderr_lower
                or "unable to find" in stderr_lower
                or "el sistema no puede encontrar" in stderr_lower
                or result.get("exit_code") == 1
            ):
                return _ok(
                    key=key, name=name or None, exists=False,
                    note="Registry key/value does not exist.",
                    source="reg.exe",
                )
            return result
        return _ok(**result, key=key, name=name or None, exists=True, source="reg.exe")

    if action in {"export", "backup"}:
        out = str(args.get("file") or args.get("dst") or "").strip()
        path = Path(out).expanduser() if out else _registry_backup_path(state, key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return _err("cannot create backup directory", path=str(path.parent), reason=str(exc))
        result = _run_cmd(["reg", "export", key, str(path), "/y"], timeout=20)
        # VERIFICACION: reg export puede devolver returncode 0 pero no
        # escribir el archivo (clave inaccesible, permisos). Chequear que
        # el .reg existe y tiene contenido.
        if result.get("ok"):
            if not path.is_file() or path.stat().st_size == 0:
                return _err(
                    "reg export reported success but backup file is missing/empty",
                    key=key, file=str(path), status="failed",
                )
        result.update(file=str(path.resolve()), registry_key=key)
        return result

    if action == "import":
        file_path = Path(str(args.get("file") or args.get("path") or "")).expanduser()
        if not file_path.is_file():
            return _err("registry import file not found", file=str(file_path), status="needs_user")
        if file_path.stat().st_size == 0:
            return _err("registry import file is empty", file=str(file_path), status="failed")
        return _run_cmd(["reg", "import", str(file_path)], timeout=20)

    if action == "add":
        if not name:
            return _err("missing registry value name")
        value_type = str(args.get("type") or "REG_SZ").upper()
        # VALIDACION: el LLM puede pasar tipos invalidos. reg.exe devuelve
        # error obscuro; lo atrapamos antes con un mensaje claro.
        if value_type not in _VALID_REG_TYPES:
            return _err(
                f"invalid registry value type: {value_type!r}",
                valid_types=sorted(_VALID_REG_TYPES), status="needs_user",
            )
        data = str(args.get("data") or args.get("value") or "")
        # VALIDACION cruzada type/data: REG_DWORD/REG_QWORD requieren numero.
        if value_type in {"REG_DWORD", "REG_QWORD"}:
            try:
                int(data, 0)  # base 0 -> acepta "0x..." y decimal
            except (ValueError, TypeError):
                return _err(
                    f"{value_type} requires integer data; got {data!r}",
                    type=value_type, data=data, status="needs_user",
                )
        backup = registry_tool({"action": "backup", "key": key}, state)
        if backup.get("ok"):
            rollback = [{"tool": "registry", "args": {"action": "import", "file": backup.get("file")}}]
        else:
            # T2-registry-backup-trust-015: solo permitimos fallback-to-delete
            # si confirmamos que la clave/valor NO existía antes del add.
            pre = _run_cmd(["reg", "query", key, "/v", name], timeout=10)
            if pre.get("ok"):
                # Existía un valor previo y el backup falló: rehusamos para no
                # destruirlo accidentalmente con un rollback-to-delete.
                return _err(
                    "registry backup failed but the value already exists; refusing to proceed (rollback would destroy the existing value)",
                    key=key, name=name, backup=backup, status="needs_user",
                )
            rollback = [{"tool": "registry", "args": {"action": "delete", "key": key, "name": name}}]
        checkpoint = state.checkpoint(f"registry {key}\\{name} before add", rollback=rollback, metadata={"backup": backup})
        result = _run_cmd(["reg", "add", key, "/v", name, "/t", value_type, "/d", data, "/f"], timeout=20)
        # VERIFICACION post-add: re-query para confirmar que el valor quedo.
        verified = False
        if result.get("ok"):
            post = _run_cmd(["reg", "query", key, "/v", name], timeout=10)
            verified = bool(post.get("ok"))
        result.update(
            backup=backup, checkpoint=checkpoint.get("checkpoint"),
            registry_key=key, value_name=name, type=value_type, verified=verified,
        )
        return result

    if action == "delete":
        backup = registry_tool({"action": "backup", "key": key}, state)
        rollback = [{"tool": "registry", "args": {"action": "import", "file": backup.get("file")}}] if backup.get("ok") else []
        checkpoint = state.checkpoint(f"registry {key} before delete", rollback=rollback, metadata={"backup": backup})
        cmd = ["reg", "delete", key]
        if name:
            cmd.extend(["/v", name])
        cmd.append("/f")
        result = _run_cmd(cmd, timeout=20)
        # VERIFICACION post-delete: re-query debe devolver exit 1.
        verified = False
        if result.get("ok"):
            post_cmd = ["reg", "query", key]
            if name:
                post_cmd.extend(["/v", name])
            post = _run_cmd(post_cmd, timeout=10)
            verified = not post.get("ok")  # absent means deleted
        result.update(
            backup=backup, checkpoint=checkpoint.get("checkpoint"),
            registry_key=key, value_name=name or None, verified=verified,
        )
        return result
    return _err("unknown registry action", action=action,
                valid_actions=["query", "export", "backup", "import", "add", "delete"])


def download_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "fetch").casefold()
    if action == "hash":
        path_raw = str(args.get("path") or "").strip()
        if not path_raw:
            return _err("hash requires path", status="needs_user")
        path = Path(path_raw).expanduser()
        return _file_hash(path, str(args.get("algorithm") or "SHA256"))
    if action == "signature":
        path_raw = str(args.get("path") or "").strip()
        if not path_raw:
            return _err("signature requires path", status="needs_user")
        path = Path(path_raw).expanduser()
        return _authenticode_signature(path)
    if action != "fetch":
        return _err(
            "unknown download action", action=action,
            valid_actions=["fetch", "hash", "signature"],
            status="needs_user",
        )

    url = str(args.get("url") or "").strip()
    if not url:
        return _err("missing url", status="needs_user")
    # VALIDACION: solo http/https. file:// y ftp:// son riesgos de seguridad.
    if not url.startswith(("http://", "https://")):
        return _err(
            "download.fetch only supports http/https",
            url=url, status="needs_user",
        )
    dst_raw = str(args.get("path") or args.get("dst") or "").strip()
    dst = Path(dst_raw).expanduser() if dst_raw else _download_default_path(state, url)
    if dst.exists() and not bool(args.get("overwrite", False)):
        return _err(
            "download target already exists",
            path=str(dst), status="needs_user", verified=False,
            hint="pass overwrite=true to replace",
        )
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _err(
            "cannot create download directory",
            path=str(dst.parent), reason=str(exc), status="needs_user",
        )

    env = os.environ.copy()
    env["GEMMA4_DOWNLOAD_URL"] = url
    env["GEMMA4_DOWNLOAD_PATH"] = str(dst)
    script = r"""
$ErrorActionPreference = "Stop"
Invoke-WebRequest -Uri $env:GEMMA4_DOWNLOAD_URL -OutFile $env:GEMMA4_DOWNLOAD_PATH -UseBasicParsing
[PSCustomObject]@{ path=$env:GEMMA4_DOWNLOAD_PATH; bytes=(Get-Item $env:GEMMA4_DOWNLOAD_PATH).Length } | ConvertTo-Json
"""
    timeout = max(5, min(int(args.get("timeout_sec", 300)), 1800))
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            env=env, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return _err(
            f"download timed out after {timeout}s",
            url=url, path=str(dst), status="timeout",
        )
    except OSError as exc:
        return _err(
            f"download spawn failed: {exc}",
            url=url, path=str(dst), status="failed",
        )
    if proc.returncode != 0:
        return _err("download failed", url=url, path=str(dst), stderr=_truncate(proc.stderr, 2000), exit_code=proc.returncode)
    # VERIFICACION: el archivo debe existir y tener bytes > 0 despues de la descarga.
    if not dst.is_file():
        return _err(
            "download reported success but target file is missing",
            url=url, path=str(dst), status="failed",
        )
    try:
        actual_bytes = dst.stat().st_size
    except OSError:
        actual_bytes = 0
    if actual_bytes == 0:
        return _err(
            "download produced empty file",
            url=url, path=str(dst), status="failed",
        )

    hash_result = _file_hash(dst, "SHA256")
    expected = str(args.get("sha256") or args.get("expected_sha256") or "").strip().casefold()
    actual = str(hash_result.get("hash") or "").casefold()
    hash_verified = bool(expected and actual and expected == actual)
    sig_result = _authenticode_signature(dst) if dst.suffix.casefold() in {".exe", ".msi", ".ps1", ".dll"} else {}
    # T2-download-signature-trust-016: Authenticode 'Valid' NO promueve a verified=True;
    # solo el hash explicit-expected lo hace. La firma queda como signal informativo
    # para que el agente la presente al usuario.
    signature_present = sig_result.get("status") == "Valid" if sig_result else False
    signer_subject = None
    if isinstance(sig_result, dict):
        signer_cert = sig_result.get("signer_certificate") or {}
        if isinstance(signer_cert, dict):
            signer_subject = signer_cert.get("Subject") or signer_cert.get("subject")
    verified = hash_verified
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
        signature_present=signature_present,
        signer_subject=signer_subject,
        verified=verified,
        status="done" if verified else "needs_verification",
        completion_status="download_verified" if verified else "download_unverified",
        resource=resource.get("resource"),
        note=(
            "Hash matched expected SHA256." if verified else
            "verified=False: provide expected_sha256 from a trusted source. "
            "Authenticode-Valid signatures alone are not promoted to verified=True."
        ),
    )


_EMAIL_RECIPIENT_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def email_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    action = str(args.get("action") or "status").casefold()
    token = os.environ.get("GEMMA4_GRAPH_TOKEN") or os.environ.get("MS_GRAPH_TOKEN")
    if action == "status":
        return _ok(provider="microsoft_graph", has_token=bool(token), auth_env_vars=["GEMMA4_GRAPH_TOKEN", "MS_GRAPH_TOKEN"])
    if action == "draft":
        to_list = _string_list(args.get("to"))
        subject = str(args.get("subject") or "").strip()
        body = str(args.get("body") or "").strip()
        if not to_list and not subject and not body:
            return _err(
                "draft requires at least one of: to, subject, body",
                status="needs_user",
            )
        return state.note(
            "email draft",
            metadata={"to": to_list, "subject": subject, "body": body},
        )
    if action != "send":
        return _err(
            "unknown email action", action=action,
            valid_actions=["status", "draft", "send"],
            status="needs_user",
        )
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
    # VALIDACION de formato email para cada destinatario. Microsoft Graph
    # rechaza con error oscuro si el formato es invalido; mejor abortar
    # temprano con hint claro.
    invalid_recipients = [addr for addr in to if not _EMAIL_RECIPIENT_RE.match(addr)]
    if invalid_recipients:
        return _err(
            f"invalid email recipient(s): {invalid_recipients}",
            status="needs_user", verified=False,
            hint="recipients must match user@host.tld",
        )
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
    timeout = max(5, min(int(args.get("timeout_sec", 30)), 120))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _ok(
                provider="microsoft_graph", status_code=resp.status,
                sent=True, to=to, recipient_count=len(to),
            )
    except urllib.error.HTTPError as exc:
        # Graph devuelve detalles en el body para HTTP errors. Leerlos
        # ayuda al LLM a entender el problema (token expired, scope falta).
        body_text = ""
        try:
            body_text = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        return _err(
            f"Microsoft Graph sendMail HTTP {exc.code}: {exc.reason}",
            provider="microsoft_graph", to=to, status_code=exc.code,
            response_body=body_text,
            status="needs_user" if exc.code in {401, 403} else "failed",
            hint=(
                "refresh GEMMA4_GRAPH_TOKEN; required scope is Mail.Send"
                if exc.code in {401, 403} else None
            ),
        )
    except Exception as exc:
        return _err(
            f"Microsoft Graph sendMail failed: {type(exc).__name__}: {exc}",
            provider="microsoft_graph", to=to, status="failed",
        )


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
            return _err("missing reminder id", status="needs_user")
        return state.mark_cleaned(rid, {"deleted": True})
    if action != "create":
        return _err(
            "unknown reminder action", action=action,
            valid_actions=["status", "list", "create", "delete"],
            status="needs_user",
        )
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
        return _err("missing reminder title/text", status="needs_user")
    # VALIDACION due si vino (ISO 8601 esperado).
    due_raw = args.get("due")
    due_normalized: str | None = None
    if due_raw is not None:
        s = str(due_raw).strip()
        if s:
            # Acepta YYYY-MM-DD y YYYY-MM-DDTHH:MM[:SS]; rechaza language natural.
            if re.match(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?$", s):
                due_normalized = s + ("T00:00:00" if "T" not in s else "")
            else:
                try:
                    from datetime import datetime as _dt
                    _dt.fromisoformat(s)
                    due_normalized = s
                except ValueError:
                    return _err(
                        f"reminder due {s!r} is not ISO 8601",
                        status="needs_user",
                        hint="pass YYYY-MM-DD or YYYY-MM-DDTHH:MM; resolve relative dates in the agent",
                    )
    resource = state.register_resource(
        "reminder",
        title,
        metadata={"due": due_normalized, "backend": "state", "text": args.get("text") or title},
    )
    return _ok(
        reminder=resource.get("resource"), backend="state",
        note="Stored locally as agent state; no OS notification was scheduled.",
        due=due_normalized,
    )


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

    if action == "attach_visible":
        return _attach_visible_browser(args, session_id, state)

    if action == "active_tab":
        session = _BROWSER_SESSIONS.get(session_id)
        if not session:
            return _err("no browser session; use attach_visible or connect_cdp first", status="needs_user")
        tabs = _tabs(session)
        active_idx = int(session.get("active", 0))
        active = tabs[active_idx] if 0 <= active_idx < len(tabs) else (tabs[0] if tabs else None)
        return _ok(session_id=session_id, active_tab=active, tabs=tabs, count=len(tabs))

    if action == "tab_open":
        if not url:
            return _err("tab_open requires url", status="needs_user")
        try:
            session = _BROWSER_SESSIONS.get(session_id) or _get_browser_session(session_id, state, headless=headless)
            page = _active_page(session, new_tab=True)
            page.goto(url, wait_until=str(args.get("wait_until") or "domcontentloaded"), timeout=timeout_ms)
        except Exception as exc:
            return _err(
                f"tab_open failed: {type(exc).__name__}: {exc}",
                url=url, session_id=session_id, status="failed",
            )
        return _ok(**_page_result(session_id, session, page), verified=True, content_verified=bool(page.title()))

    if action == "tab_close":
        session = _BROWSER_SESSIONS.get(session_id)
        if not session:
            return _err("no browser session", session_id=session_id, status="needs_user")
        page_id = args.get("page_id")
        if page_id is None:
            page_id = session.get("active", 0)
        pages = session.get("pages") or []
        try:
            idx = int(page_id)
        except (TypeError, ValueError):
            return _err("page_id must be integer", page_id=page_id)
        if not (0 <= idx < len(pages)):
            return _err("page_id out of range", page_id=idx, count=len(pages))
        page = pages[idx]
        try:
            page.close()
        except Exception as exc:
            return _err(f"failed to close tab: {exc}")
        session["pages"] = [p for p in session.get("pages", []) if not p.is_closed()]
        session["active"] = max(0, min(idx, len(session["pages"]) - 1)) if session["pages"] else 0
        return _ok(session_id=session_id, closed_page_id=idx, remaining_tabs=_tabs(session))

    if action == "tab_focus":
        session = _BROWSER_SESSIONS.get(session_id)
        if not session:
            return _err("no browser session", session_id=session_id, status="needs_user")
        page_id = args.get("page_id")
        pages = session.get("pages") or []
        try:
            idx = int(page_id) if page_id is not None else 0
        except (TypeError, ValueError):
            return _err("page_id must be integer", page_id=page_id)
        if not (0 <= idx < len(pages)):
            return _err("page_id out of range", page_id=idx, count=len(pages))
        session["active"] = idx
        try:
            pages[idx].bring_to_front()
        except Exception:
            pass  # CDP-attached browsers may not allow bring_to_front
        return _ok(session_id=session_id, active_page_id=idx, tabs=_tabs(session))

    if action in {"open", "goto"}:
        if not url:
            return _err("browser_real open/goto requires url", status="needs_user")
        try:
            session = _get_browser_session(session_id, state, headless=headless)
        except RuntimeError as exc:
            return _err(str(exc), session_id=session_id, status="needs_user")
        try:
            page = _active_page(session, new_tab=bool(args.get("new_tab", action == "open")))
            page.goto(url, wait_until=str(args.get("wait_until") or "domcontentloaded"), timeout=timeout_ms)
        except Exception as exc:
            return _err(
                f"navigation failed: {type(exc).__name__}: {exc}",
                url=url, session_id=session_id,
                status="failed" if "Timeout" not in type(exc).__name__ else "timeout",
            )
        result = _page_result(session_id, session, page)
        if bool(args.get("screenshot", False)):
            try:
                result.update(_page_screenshot(page, captures_dir, bool(args.get("full_page", False))))
            except Exception:
                pass
        return _ok(**result, verified=True, content_verified=bool(result.get("title")))

    session = _BROWSER_SESSIONS.get(session_id)
    if not session:
        return _err("browser session not found", session_id=session_id, status="needs_user", completion_status="needs_browser_session")
    page = _active_page(session, page_id=args.get("page_id"))

    if action == "click":
        if not selector:
            return _err("click requires selector", status="needs_user")
        try:
            page.click(selector, timeout=timeout_ms)
        except Exception as exc:
            return _err(
                f"click failed: {type(exc).__name__}: {exc}",
                selector=selector, session_id=session_id,
                status="failed" if "Timeout" not in type(exc).__name__ else "timeout",
                hint="check selector exists and is visible; try a more specific CSS or XPath",
            )
        return _ok(**_page_result(session_id, session, page), clicked=selector, verified=True, content_verified=True)
    if action == "fill":
        if not selector:
            return _err("fill requires selector", status="needs_user")
        try:
            page.fill(selector, value, timeout=timeout_ms)
        except Exception as exc:
            return _err(
                f"fill failed: {type(exc).__name__}: {exc}",
                selector=selector, session_id=session_id,
                status="failed" if "Timeout" not in type(exc).__name__ else "timeout",
            )
        return _ok(**_page_result(session_id, session, page), filled=selector, chars=len(value), verified=True, content_verified=True)
    if action == "press":
        key = str(args.get("key") or value or "Enter")
        try:
            page.press(selector or "body", key, timeout=timeout_ms)
        except Exception as exc:
            return _err(
                f"press failed: {type(exc).__name__}: {exc}",
                selector=selector or "body", key=key, session_id=session_id,
                status="failed" if "Timeout" not in type(exc).__name__ else "timeout",
            )
        return _ok(**_page_result(session_id, session, page), pressed=key, selector=selector or "body", verified=True, content_verified=True)
    if action == "text":
        try:
            text = page.inner_text(selector or "body", timeout=timeout_ms)[: int(args.get("max_chars", 8000))]
        except Exception as exc:
            return _err(
                f"text extraction failed: {type(exc).__name__}: {exc}",
                selector=selector or "body", session_id=session_id,
                status="failed" if "Timeout" not in type(exc).__name__ else "timeout",
            )
        return _ok(**_page_result(session_id, session, page), text=text, verified=True, content_verified=True)
    if action == "screenshot":
        try:
            shot = _page_screenshot(page, captures_dir, bool(args.get("full_page", False)))
        except Exception as exc:
            return _err(
                f"screenshot failed: {type(exc).__name__}: {exc}",
                session_id=session_id, status="failed",
            )
        return _ok(**_page_result(session_id, session, page), **shot, verified=True)
    if action == "evaluate":
        script = str(args.get("script") or "")
        if not script:
            return _err("evaluate requires script")
        # T3-browser_real-evaluate-arbitrary-js-038: si la sesión es CDP
        # (browser visible del usuario), exigir confirmación. En sesiones
        # headless propias del agente, pass-through.
        if session.get("cdp") and not bool(args.get("confirmed")):
            pending = state.create_confirmation(
                "browser_real",
                {**{k: v for k, v in args.items() if k not in {"routine_context", "confirmed_at_create"}}, "confirmed": True},
                reason=f"Running JS in attached visible browser (CDP) — cookies and session tokens are exposed. Script preview: {script[:200]}",
                risk="high",
            )
            return _err(
                "evaluate on CDP-attached browser requires confirmation",
                status="needs_confirmation",
                verified=False,
                completion_status="needs_user_confirmation",
                confirmation=pending.get("confirmation"),
                session_id=session_id,
            )
        value = page.evaluate(script)
        return _ok(**_page_result(session_id, session, page), value=value, verified=True, content_verified=True)
    if action == "click_text":
        target = str(args.get("text") or args.get("target") or value or "").strip()
        if not target:
            return _err("click_text requires text/target")
        # Playwright getByText returns the first matching visible element.
        try:
            locator = page.get_by_text(target, exact=bool(args.get("exact", False)))
            locator.first.click(timeout=timeout_ms)
        except Exception as exc:
            return _err(f"click_text failed: {exc}", target=target, session_id=session_id)
        return _ok(**_page_result(session_id, session, page), clicked_text=target, verified=True, content_verified=True)
    if action == "extract":
        mode = str(args.get("mode") or "main_text").casefold()
        max_chars = int(args.get("max_chars", 12000))
        return _browser_extract(session_id, session, page, mode, max_chars)
    if action == "wait_for_download":
        return _browser_wait_for_download(session_id, session, page, args, captures_dir)
    if action == "set_download_path":
        # Use CDP to set download path on the current context.
        target_dir = Path(str(args.get("path") or captures_dir / "downloads")).expanduser()
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            client = page.context.new_cdp_session(page)
            client.send("Browser.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": str(target_dir),
                "eventsEnabled": True,
            })
        except Exception as exc:
            return _err(f"set_download_path via CDP failed: {exc}", path=str(target_dir))
        return _ok(session_id=session_id, download_path=str(target_dir), verified=True)
    return _err(
        "unknown browser_real action", action=action,
        valid_actions=[
            "status", "close", "tabs", "connect_cdp", "attach_visible",
            "active_tab", "tab_open", "tab_close", "tab_focus", "open", "goto",
            "click", "fill", "press", "text", "screenshot", "evaluate",
        ],
        status="needs_user",
    )


def _attach_visible_browser(args: dict[str, Any], session_id: str, state: AgentState) -> dict[str, Any]:
    """Connect to a visible browser started with --remote-debugging-port.

    If the browser is not listening on the requested port, return needs_user with
    explicit launch instructions. We do not auto-restart the user's browser
    because that would close their tabs.
    """
    browser_choice = str(args.get("browser") or "chrome").casefold()
    port = int(args.get("port", 9222))
    endpoint = str(args.get("endpoint") or f"http://127.0.0.1:{port}").strip()
    # Probe the endpoint first.
    if not _cdp_endpoint_alive(endpoint):
        launch_cmd = _cdp_launch_instruction(browser_choice, port)
        return _err(
            f"no browser is listening on {endpoint}",
            status="needs_user", verified=False,
            completion_status="needs_browser_debug_port",
            browser=browser_choice, endpoint=endpoint, port=port,
            launch_instructions=launch_cmd,
            note="Start the browser yourself with the listed flags and re-call attach_visible. Auto-restart is not done because it would close your tabs.",
        )
    session = _connect_cdp_session(session_id, endpoint)
    return _ok(
        session_id=session_id, endpoint=endpoint, attached=True,
        browser=browser_choice, tabs=_tabs(session), cdp=True,
        evidence={"session_id": session_id, "browser_profile": "user_profile_via_cdp"},
        note="Attached to the user's visible browser via CDP. Tabs you open here are visible to the user. Use tab_close to clean up.",
    )


def _cdp_endpoint_alive(endpoint: str) -> bool:
    try:
        with urllib.request.urlopen(f"{endpoint.rstrip('/')}/json/version", timeout=2.0):
            return True
    except Exception:
        return False


def _cdp_launch_instruction(browser: str, port: int) -> dict[str, Any]:
    profile_hint = "Use a separate user-data-dir to avoid singleton conflicts with your current session."
    base = {
        "chrome": [
            r'& "C:\Program Files\Google\Chrome\Application\chrome.exe" `',
            f'    --remote-debugging-port={port} `',
            r'    --user-data-dir="$env:LOCALAPPDATA\Gemma4Agent\chrome-cdp"',
        ],
        "edge": [
            r'& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `',
            f'    --remote-debugging-port={port} `',
            r'    --user-data-dir="$env:LOCALAPPDATA\Gemma4Agent\edge-cdp"',
        ],
        "opera": [
            r'& "$env:LOCALAPPDATA\Programs\Opera\opera.exe" `',
            f'    --remote-debugging-port={port} `',
            r'    --user-data-dir="$env:LOCALAPPDATA\Gemma4Agent\opera-cdp"',
        ],
        "brave": [
            r'& "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" `',
            f'    --remote-debugging-port={port} `',
            r'    --user-data-dir="$env:LOCALAPPDATA\Gemma4Agent\brave-cdp"',
        ],
    }
    cmd = base.get(browser) or base["chrome"]
    return {"browser": browser, "port": port, "powershell": "\n".join(cmd), "note": profile_hint}


def _browser_extract(session_id: str, session: dict[str, Any], page: Any, mode: str, max_chars: int) -> dict[str, Any]:
    if mode == "main_text":
        # Conservative: grab <main>, <article>, or body inner_text.
        try:
            content = page.evaluate(
                """() => {
                  const sel = ['main', 'article', '[role=\"main\"]', '#content', 'body'];
                  for (const s of sel) {
                    const el = document.querySelector(s);
                    if (el && el.innerText && el.innerText.length > 200) return el.innerText;
                  }
                  return document.body ? document.body.innerText : '';
                }"""
            )
        except Exception as exc:
            return _err(f"extract main_text failed: {exc}")
        text = str(content or "")[:max_chars]
        return _ok(**_page_result(session_id, session, page), mode=mode, text=text, chars=len(text), verified=True, content_verified=bool(text))
    if mode == "tables":
        try:
            tables = page.evaluate(
                """() => {
                  return [...document.querySelectorAll('table')].slice(0, 20).map(t => {
                    return [...t.rows].slice(0, 200).map(r => [...r.cells].map(c => c.innerText.trim()));
                  });
                }"""
            )
        except Exception as exc:
            return _err(f"extract tables failed: {exc}")
        return _ok(**_page_result(session_id, session, page), mode=mode, tables=tables, table_count=len(tables or []), verified=True, content_verified=bool(tables))
    if mode == "links":
        try:
            links = page.evaluate(
                """() => [...document.querySelectorAll('a[href]')].slice(0, 500).map(a => ({
                  text: (a.innerText || a.textContent || '').trim().slice(0, 200),
                  href: a.href
                }))"""
            )
        except Exception as exc:
            return _err(f"extract links failed: {exc}")
        return _ok(**_page_result(session_id, session, page), mode=mode, links=links, count=len(links or []), verified=True, content_verified=bool(links))
    if mode == "html":
        try:
            html = page.content()
        except Exception as exc:
            return _err(f"extract html failed: {exc}")
        return _ok(**_page_result(session_id, session, page), mode=mode, html=html[:max_chars], chars=len(html), verified=True, content_verified=True)
    return _err(f"unknown extract mode: {mode}", supported=["main_text", "tables", "links", "html"])


def _browser_wait_for_download(session_id: str, session: dict[str, Any], page: Any, args: dict[str, Any], captures_dir: Path) -> dict[str, Any]:
    """Wait for a download to finish.

    NOTE: For Playwright-launched browsers, page.expect_download() is reliable.
    For CDP-attached visible browsers Playwright's Download API may not fire
    consistently; in that case we fall back to setDownloadBehavior + raw CDP
    events. We try the Playwright path first.
    """
    timeout_ms = int(float(args.get("timeout_sec", 60)) * 1000)
    save_dir = Path(str(args.get("save_dir") or captures_dir / "downloads")).expanduser()
    save_dir.mkdir(parents=True, exist_ok=True)
    if session.get("cdp"):
        return _err(
            "wait_for_download over CDP requires raw event listening; not implemented yet for attached visible browsers",
            status="needs_implementation", verified=False,
            note="Use set_download_path then trigger the download manually; we can verify the file landed in save_dir.",
        )
    try:
        with page.expect_download(timeout=timeout_ms) as info:
            # Caller must trigger the download outside this call; this path is only
            # meaningful when chained with a click that initiates the download.
            pass
        download = info.value
        target = save_dir / download.suggested_filename
        download.save_as(str(target))
        return _ok(
            session_id=session_id,
            path=str(target.resolve()),
            suggested_filename=download.suggested_filename,
            url=download.url,
            size=target.stat().st_size if target.exists() else None,
            verified=target.exists(),
        )
    except Exception as exc:
        return _err(f"wait_for_download failed: {exc}", status="needs_verification")


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
    # T3-browser_real-headless-fixed-after-open-040: si la sesión existe con
    # otro headless, fallar rápido.
    session = _BROWSER_SESSIONS.get(session_id)
    if session:
        if session.get("headless") != headless:
            raise RuntimeError(
                f"session {session_id!r} already open with headless={session.get('headless')}; "
                f"close it first or pass session_id explicitly"
            )
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
    ctx = session.get("context")
    if ctx is None:
        return tabs
    pages = [page for page in ctx.pages if not page.is_closed()]
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
    # timeout 20 -> 8s + try/except.
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return _err("language list timeout", reason="powershell_timeout")
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
    # timeout 15 -> 6s. Add-Type ya cachea el assembly tras primer uso;
    # GetKeyboardLayout es instant. 6s da headroom 10x.
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=6)
    except (OSError, subprocess.TimeoutExpired):
        return _err("keyboard read timeout", reason="powershell_timeout")
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
    # timeout 20 -> 10s + try/except. SetEnvironmentVariable es instant;
    # GetEnvironmentVariables del scope Machine sobre HKLM puede tardar
    # 2-5s con muchas vars; 10s es generoso.
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return _err("environment operation timeout", scope=target, reason="powershell_timeout")
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
    # Preferir hashlib in-process (~10-50ms para 10MB) sobre PowerShell
    # Get-FileHash (~600ms cold-start). Solo caemos a PS si hashlib falla
    # con el nombre del algoritmo (raro).
    try:
        h = hashlib.new(algo.lower())
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return _ok(path=str(path.resolve()), algorithm=algo, hash=h.hexdigest(), source="hashlib")
    except (ValueError, OSError) as exc:
        # hashlib no soporta este algoritmo o falla I/O. Intentar PowerShell.
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"Get-FileHash -Algorithm {algo} -LiteralPath $env:GEMMA4_HASH_PATH | ConvertTo-Json"],
                env={**os.environ, "GEMMA4_HASH_PATH": str(path)},
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            return _err(f"file hash failed: {exc}", path=str(path), source="hashlib_and_ps_timeout")
        if proc.returncode == 0 and proc.stdout.strip():
            data = _json_or_text(proc.stdout)
            if isinstance(data, dict):
                return _ok(path=str(path.resolve()), algorithm=algo, hash=str(data.get("Hash") or "").lower(), source="powershell")
        return _err(f"file hash failed: {exc}", path=str(path))


def _authenticode_signature(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _err("file not found", path=str(path))
    env = {**os.environ, "GEMMA4_SIG_PATH": str(path)}
    script = "Get-AuthenticodeSignature -LiteralPath $env:GEMMA4_SIG_PATH | Select-Object Status,StatusMessage,SignerCertificate,Path | ConvertTo-Json -Depth 4"
    # timeout 30 -> 12s + try/except. signature check normalmente <2s; los
    # que requieren CRL revocation pueden tardar 3-8s. 12s es suficiente.
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", script], env=env, capture_output=True, text=True, timeout=12)
    except (OSError, subprocess.TimeoutExpired):
        return _err("signature check timeout", path=str(path), reason="powershell_timeout")
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
