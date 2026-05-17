"""Operational state for resources, checkpoints and cleanup."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON to `path` atomically.

    Writes to a sibling `.tmp` file then os.replace()s it onto the target,
    which is atomic on POSIX and on NTFS (Windows). Prevents truncated JSONs
    when the process crashes mid-write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(data, ensure_ascii=False, indent=2)
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


@dataclass
class AgentState:
    path: Path
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"resources": {}, "checkpoints": {}, "notes": [], "confirmations": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"resources": {}, "checkpoints": {}, "notes": [], "confirmations": {}}
        if not isinstance(data, dict):
            return {"resources": {}, "checkpoints": {}, "notes": [], "confirmations": {}}
        data.setdefault("resources", {})
        data.setdefault("checkpoints", {})
        data.setdefault("notes", [])
        data.setdefault("confirmations", {})
        return data

    def _save(self, data: dict[str, Any]) -> None:
        atomic_write_json(self.path, data)

    def register_resource(
        self,
        kind: str,
        label: str,
        cleanup_tool: str | None = None,
        cleanup_args: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            rid = f"res_{uuid.uuid4().hex[:10]}"
            data["resources"][rid] = {
                "id": rid,
                "kind": kind,
                "label": label,
                "status": "open",
                "created_at": _now(),
                "cleanup_tool": cleanup_tool,
                "cleanup_args": cleanup_args or {},
                "metadata": metadata or {},
            }
            self._save(data)
            return {"ok": True, "resource": data["resources"][rid]}

    def list_resources(self, include_closed: bool = False) -> dict[str, Any]:
        with self._lock:
            resources = list(self._load().get("resources", {}).values())
        if not include_closed:
            resources = [res for res in resources if res.get("status") == "open"]
        return {"ok": True, "resources": resources, "count": len(resources)}

    def cleanup_plan(self, resource_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            resources = self._load().get("resources", {})
            if resource_id:
                selected = [resources[resource_id]] if resource_id in resources else []
            else:
                selected = [res for res in resources.values() if res.get("status") == "open"]
        selected = [res for res in selected if res.get("cleanup_tool")]
        return {"ok": True, "cleanup_items": selected, "count": len(selected)}

    def update_resource(
        self,
        resource_id: str,
        *,
        metadata_patch: dict[str, Any] | None = None,
        cleanup_args_patch: dict[str, Any] | None = None,
        status: str | None = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        """Atomic patch of a resource (metadata, cleanup_args, status).

        Useful when more than `metadata` needs to be touched in the same
        transaction (e.g. job_manager sets cleanup_args after creation).
        """
        with self._lock:
            data = self._load()
            resource = data.get("resources", {}).get(resource_id)
            if not resource:
                return {"ok": False, "error": "resource not found", "resource_id": resource_id}
            if metadata_patch:
                metadata = resource.setdefault("metadata", {})
                metadata.update(metadata_patch)
            if cleanup_args_patch:
                cleanup_args = resource.setdefault("cleanup_args", {})
                cleanup_args.update(cleanup_args_patch)
            if status:
                resource["status"] = status
            if label is not None:
                resource["label"] = str(label)
            self._save(data)
            return {"ok": True, "resource": resource}

    def update_resource_metadata(
        self,
        resource_id: str,
        patch: dict[str, Any],
        *,
        append_lists: tuple[str, ...] = (),
        max_append: int | None = None,
    ) -> dict[str, Any]:
        """Atomic read-modify-save of a resource's metadata.

        `patch` keys override (or set) entries inside resource["metadata"].
        Keys listed in `append_lists` are treated as list-append targets
        (the patched value must itself be a list); `max_append` trims the
        oldest entries when given.

        CC-102 / T3-routine-state-private-api-029: este es el reemplazo
        público del idiom `state._load(); ...; state._save(data)` que
        antes saltaba el RLock entre read y write.
        """
        with self._lock:
            data = self._load()
            resource = data.get("resources", {}).get(resource_id)
            if not resource:
                return {"ok": False, "error": "resource not found", "resource_id": resource_id}
            metadata = resource.setdefault("metadata", {})
            for key, value in patch.items():
                if key in append_lists and isinstance(value, list):
                    current = metadata.get(key)
                    if not isinstance(current, list):
                        current = []
                    current = current + list(value)
                    if max_append is not None and max_append >= 0:
                        current = current[-max_append:]
                    metadata[key] = current
                else:
                    metadata[key] = value
            self._save(data)
            return {"ok": True, "resource": resource}

    def mark_cleaned(self, resource_id: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            resource = data.get("resources", {}).get(resource_id)
            if not resource:
                return {"ok": False, "error": "resource not found", "resource_id": resource_id}
            resource["status"] = "closed"
            resource["closed_at"] = _now()
            resource["cleanup_result"] = result or {}
            self._save(data)
            return {"ok": True, "resource": resource}

    def purge_stale_closed(self, max_age_days: int = 7) -> dict[str, Any]:
        """Drop closed resources older than ``max_age_days``.

        Resources with ``status == "closed"`` and a ``closed_at`` timestamp
        older than the cutoff are removed. Closed resources WITHOUT a
        ``closed_at`` (legacy entries written before this field existed)
        are also dropped — we assume they are old enough to discard.
        Closed resources with a malformed ``closed_at`` are dropped for
        the same reason.

        Open resources are never touched, regardless of age.

        Sprint 7.2: introduced to prevent state.json from accumulating
        zombie ``closed`` entries forever. Called once on Gemma4Agent
        startup, in a try/except so a malformed state.json never breaks
        boot.
        """
        import datetime as _dt
        cutoff = _dt.datetime.now().astimezone() - _dt.timedelta(days=max_age_days)
        with self._lock:
            data = self._load()
            resources = data.get("resources", {})
            before = len(resources)
            kept: dict[str, Any] = {}
            for rid, r in resources.items():
                status = str(r.get("status") or "")
                if status != "closed":
                    kept[rid] = r
                    continue
                closed_at = r.get("closed_at")
                if not closed_at:
                    # Legacy closed without timestamp: assume old, drop.
                    continue
                try:
                    parsed = _dt.datetime.fromisoformat(str(closed_at))
                    # Normalize naive timestamps to local tz so the
                    # comparison with `cutoff` (which is tz-aware) works.
                    if parsed.tzinfo is None:
                        parsed = parsed.astimezone()
                    if parsed > cutoff:
                        kept[rid] = r
                except (ValueError, TypeError):
                    # Malformed timestamp: drop.
                    continue
            data["resources"] = kept
            self._save(data)
            return {
                "ok": True,
                "before": before,
                "after": len(kept),
                "purged": before - len(kept),
                "max_age_days": max_age_days,
            }

    def checkpoint(self, label: str, rollback: list[dict[str, Any]] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            cid = f"chk_{uuid.uuid4().hex[:10]}"
            data["checkpoints"][cid] = {
                "id": cid,
                "label": label,
                "created_at": _now(),
                "rollback": rollback or [],
                "metadata": metadata or {},
            }
            self._save(data)
            return {"ok": True, "checkpoint": data["checkpoints"][cid]}

    def list_checkpoints(self) -> dict[str, Any]:
        with self._lock:
            checkpoints = list(self._load().get("checkpoints", {}).values())
        return {"ok": True, "checkpoints": checkpoints, "count": len(checkpoints)}

    def rollback_plan(self, checkpoint_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            checkpoints = self._load().get("checkpoints", {})
            if checkpoint_id:
                checkpoint = checkpoints.get(checkpoint_id)
            else:
                checkpoint = next(reversed(checkpoints.values()), None) if checkpoints else None
        if not checkpoint:
            return {"ok": False, "error": "checkpoint not found"}
        return {"ok": True, "checkpoint": checkpoint, "rollback": checkpoint.get("rollback", [])}

    def note(self, text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            item = {"text": text, "created_at": _now(), "metadata": metadata or {}}
            data["notes"].append(item)
            self._save(data)
            return {"ok": True, "note": item}

    def create_confirmation(self, tool: str, args: dict[str, Any], reason: str, risk: str) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            cid = f"cfm_{uuid.uuid4().hex[:10]}"
            data["confirmations"][cid] = {
                "id": cid,
                "tool": tool,
                "args": args,
                "reason": reason,
                "risk": risk,
                "status": "pending",
                "created_at": _now(),
            }
            self._save(data)
            return {"ok": True, "confirmation": data["confirmations"][cid]}

    def list_confirmations(self, include_resolved: bool = False) -> dict[str, Any]:
        with self._lock:
            items = list(self._load().get("confirmations", {}).values())
        if not include_resolved:
            items = [item for item in items if item.get("status") == "pending"]
        return {"ok": True, "confirmations": items, "count": len(items)}

    def get_confirmation(self, confirmation_id: str) -> dict[str, Any]:
        with self._lock:
            item = self._load().get("confirmations", {}).get(confirmation_id)
        if not item:
            return {"ok": False, "error": "confirmation not found", "confirmation_id": confirmation_id}
        return {"ok": True, "confirmation": item}

    def resolve_confirmation(self, confirmation_id: str, status: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            item = data.get("confirmations", {}).get(confirmation_id)
            if not item:
                return {"ok": False, "error": "confirmation not found", "confirmation_id": confirmation_id}
            item["status"] = status
            item["resolved_at"] = _now()
            item["result"] = result or {}
            self._save(data)
            return {"ok": True, "confirmation": item}

    # ------------------------------------------------------------------
    # Pending intent (hotfix F 2026-05-17)
    # ------------------------------------------------------------------
    # Cross-turn rescue slot. Triggered when a tool result returns
    # status='needs_user'; consumed by router_v2 as a tool hint on the
    # NEXT turn. Language-agnostic: the slot stores tool name + args,
    # never user-reply text. See feat(state) commit in hotfix F.

    def set_pending_intent(
        self,
        tool: str,
        args: dict[str, Any],
        asks_for: str,
        current_turn: int,
        ttl_turns: int = 3,
    ) -> None:
        with self._lock:
            data = self._load()
            data["_pending_intent"] = {
                "tool": tool,
                "args": dict(args or {}),
                "asks_for": asks_for,
                "created_turn": int(current_turn),
                "ttl_turns": int(ttl_turns),
            }
            self._save(data)

    def get_pending_intent(self, current_turn: int) -> dict[str, Any] | None:
        with self._lock:
            data = self._load()
            pi = data.get("_pending_intent")
            if not pi:
                return None
            if int(current_turn) - int(pi.get("created_turn", 0)) > int(pi.get("ttl_turns", 3)):
                # TTL elapsed: self-clear on next read.
                data.pop("_pending_intent", None)
                self._save(data)
                return None
            return dict(pi)

    def clear_pending_intent(self) -> None:
        with self._lock:
            data = self._load()
            if "_pending_intent" in data:
                data.pop("_pending_intent", None)
                self._save(data)
