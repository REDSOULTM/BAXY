"""Operational state for resources, checkpoints and cleanup."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


@dataclass
class AgentState:
    path: Path

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
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def register_resource(
        self,
        kind: str,
        label: str,
        cleanup_tool: str | None = None,
        cleanup_args: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
        resources = list(self._load().get("resources", {}).values())
        if not include_closed:
            resources = [res for res in resources if res.get("status") == "open"]
        return {"ok": True, "resources": resources, "count": len(resources)}

    def cleanup_plan(self, resource_id: str | None = None) -> dict[str, Any]:
        resources = self._load().get("resources", {})
        if resource_id:
            selected = [resources[resource_id]] if resource_id in resources else []
        else:
            selected = [res for res in resources.values() if res.get("status") == "open"]
        selected = [res for res in selected if res.get("cleanup_tool")]
        return {"ok": True, "cleanup_items": selected, "count": len(selected)}

    def mark_cleaned(self, resource_id: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
        data = self._load()
        resource = data.get("resources", {}).get(resource_id)
        if not resource:
            return {"ok": False, "error": "resource not found", "resource_id": resource_id}
        resource["status"] = "closed"
        resource["closed_at"] = _now()
        resource["cleanup_result"] = result or {}
        self._save(data)
        return {"ok": True, "resource": resource}

    def checkpoint(self, label: str, rollback: list[dict[str, Any]] | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
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
        checkpoints = list(self._load().get("checkpoints", {}).values())
        return {"ok": True, "checkpoints": checkpoints, "count": len(checkpoints)}

    def rollback_plan(self, checkpoint_id: str | None = None) -> dict[str, Any]:
        checkpoints = self._load().get("checkpoints", {})
        if checkpoint_id:
            checkpoint = checkpoints.get(checkpoint_id)
        else:
            checkpoint = next(reversed(checkpoints.values()), None) if checkpoints else None
        if not checkpoint:
            return {"ok": False, "error": "checkpoint not found"}
        return {"ok": True, "checkpoint": checkpoint, "rollback": checkpoint.get("rollback", [])}

    def note(self, text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        data = self._load()
        item = {"text": text, "created_at": _now(), "metadata": metadata or {}}
        data["notes"].append(item)
        self._save(data)
        return {"ok": True, "note": item}

    def create_confirmation(self, tool: str, args: dict[str, Any], reason: str, risk: str) -> dict[str, Any]:
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
        items = list(self._load().get("confirmations", {}).values())
        if not include_resolved:
            items = [item for item in items if item.get("status") == "pending"]
        return {"ok": True, "confirmations": items, "count": len(items)}

    def get_confirmation(self, confirmation_id: str) -> dict[str, Any]:
        item = self._load().get("confirmations", {}).get(confirmation_id)
        if not item:
            return {"ok": False, "error": "confirmation not found", "confirmation_id": confirmation_id}
        return {"ok": True, "confirmation": item}

    def resolve_confirmation(self, confirmation_id: str, status: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
        data = self._load()
        item = data.get("confirmations", {}).get(confirmation_id)
        if not item:
            return {"ok": False, "error": "confirmation not found", "confirmation_id": confirmation_id}
        item["status"] = status
        item["resolved_at"] = _now()
        item["result"] = result or {}
        self._save(data)
        return {"ok": True, "confirmation": item}
