"""Sprint 8/9 del optimization_roadmap.md — chequeo del estado de los
PRs/issues upstream de llama.cpp que bloquean optimizaciones de Gemma 4.

Uso:
    python audit/check_upstream_prs.py

Salida: tabla con el estado actual (open/closed/merged) + última actualización
+ diff vs el snapshot guardado en audit/upstream_pr_snapshot.json. Si algo
cambió (en especial, si #22288 mergeó o si #22735 produjo un PR), el script
imprime un bloque "ACTION NEEDED" con qué se puede aplicar al repo.

Sin token de GitHub usa el rate limit publico (60 req/h). Para chequeos mas
frecuentes, exportar GITHUB_TOKEN=... antes de invocar.

NO actua sobre el repo automaticamente: solo reporta. La decision de
cherry-pick / esperar / cambiar default queda en el dev.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = "ggml-org/llama.cpp"
API_BASE = "https://api.github.com"

# Issues/PRs trackeados. La etiqueta `concern` explica qué bloquea cada uno.
TRACKED: list[dict[str, Any]] = [
    {
        "num": 21468,
        "kind": "issue",
        "concern": "cache-reuse roto en Gemma 4 (shared-KV)",
        "on_resolve": "remover comentario en llama_server.py:--keep -1; reactivar --cache-reuse",
        "sprint": "8",
    },
    {
        "num": 22288,
        "kind": "pull",
        "concern": "fix candidato para #21468 (cache-reuse Gemma 4)",
        "on_resolve": "validar build minima requerida; bumpear LLAMA_CPP_BUILD_MIN",
        "sprint": "8",
    },
    {
        "num": 22735,
        "kind": "discussion",
        "concern": "Gemma 4 MTP drafters no soportados en upstream",
        "on_resolve": "implementar --model-draft con assistant GGUF para performance profile",
        "sprint": "9",
    },
    {
        "num": 21690,
        "kind": "issue",
        "concern": "mmproj + checkpoints OOM RAM en Gemma 4",
        "on_resolve": "remover counter de imagenes en multimodal.py (item 1.7)",
        "sprint": "extra",
    },
    {
        "num": 21868,
        "kind": "issue",
        "concern": "input_audio HTTP 500 en /v1/chat/completions (closed not planned)",
        "on_resolve": "evaluar audio nativo Gemma 4 vs Whisper en STT primario",
        "sprint": "extra",
    },
    {
        "num": 21384,
        "kind": "issue",
        "concern": "tool_call args serializados como JSON string con braces",
        "on_resolve": "remover doble-string handling en llm_client.normalize_tool_call_arguments",
        "sprint": "extra",
    },
]

SNAPSHOT_PATH = Path(__file__).parent / "upstream_pr_snapshot.json"


def _headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "gemma4-agent-upstream-watch/1.0",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def fetch_one(num: int) -> dict[str, Any]:
    """GitHub API: el endpoint /issues/<num> tambien sirve para PRs (un PR es
    un tipo especial de issue). Devolvemos un dict normalizado con state,
    merged, title, updated_at, html_url o un campo 'error'."""
    url = f"{API_BASE}/repos/{REPO}/issues/{num}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}", "num": num}
    except urllib.error.URLError as exc:
        return {"error": f"URLError: {exc.reason}", "num": num}
    except (OSError, json.JSONDecodeError, TimeoutError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "num": num}

    out = {
        "num": num,
        "state": data.get("state"),  # open / closed
        "title": data.get("title"),
        "updated_at": data.get("updated_at"),
        "html_url": data.get("html_url"),
        "is_pull": "pull_request" in data,
        "comments": data.get("comments"),
    }
    # Para PRs queremos saber si esta merged (issues API no lo expone; query extra).
    if out["is_pull"]:
        pr_url = f"{API_BASE}/repos/{REPO}/pulls/{num}"
        req2 = urllib.request.Request(pr_url, headers=_headers())
        try:
            with urllib.request.urlopen(req2, timeout=10) as resp:
                pr_data = json.loads(resp.read().decode("utf-8"))
            out["merged"] = bool(pr_data.get("merged"))
            out["merged_at"] = pr_data.get("merged_at")
        except Exception:
            out["merged"] = None
    return out


def load_snapshot() -> dict[str, Any]:
    if SNAPSHOT_PATH.is_file():
        try:
            return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_snapshot(data: dict[str, Any]) -> None:
    SNAPSHOT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def diff_state(prev: dict[str, Any], curr: dict[str, Any]) -> list[str]:
    """Devuelve lista de mensajes de cambio relevantes (state, merged, updated)."""
    msgs: list[str] = []
    if not prev:
        return msgs
    for k in ("state", "merged"):
        old = prev.get(k)
        new = curr.get(k)
        if old != new:
            msgs.append(f"{k}: {old!r} -> {new!r}")
    return msgs


def main() -> int:
    prev_snapshot = load_snapshot().get("items") or {}
    curr_snapshot: dict[str, Any] = {}
    actions: list[str] = []

    print(f"# Upstream PR/Issue Watch — {datetime.now().isoformat(timespec='seconds')}")
    print(f"Repo: {REPO}")
    print(f"Snapshot: {SNAPSHOT_PATH}")
    print()
    header = f"{'#':>6} | {'state':<10} | {'merged':<7} | {'updated':<20} | sprint | concern"
    print(header)
    print("-" * len(header))

    for entry in TRACKED:
        num = entry["num"]
        info = fetch_one(num)
        if "error" in info:
            print(f"{num:>6} | ERROR: {info['error']}")
            continue
        state = info.get("state") or "?"
        merged = info.get("merged")
        merged_str = "yes" if merged is True else ("no" if merged is False else "-")
        updated = (info.get("updated_at") or "")[:19]
        print(f"{num:>6} | {state:<10} | {merged_str:<7} | {updated:<20} | {entry['sprint']:<6} | {entry['concern']}")
        curr_snapshot[str(num)] = {
            "state": state,
            "merged": merged,
            "updated_at": updated,
            "title": info.get("title"),
            "html_url": info.get("html_url"),
        }
        # Diff vs snapshot anterior
        prev = prev_snapshot.get(str(num))
        if prev:
            changes = diff_state(prev, curr_snapshot[str(num)])
            for c in changes:
                actions.append(f"#{num} CHANGED {c} — {entry['on_resolve']}")

    # Detectar transiciones criticas: cerrar issue / merge PR
    print()
    if actions:
        print("# ACTION NEEDED")
        for a in actions:
            print(f"  - {a}")
    else:
        print("# No upstream state changes since last snapshot.")

    save_snapshot({"saved_at": datetime.now().isoformat(timespec="seconds"), "items": curr_snapshot})
    return 0


if __name__ == "__main__":
    sys.exit(main())
