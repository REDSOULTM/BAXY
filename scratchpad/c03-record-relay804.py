"""Preserve relay preparation and the owner's updated objective; no product credit."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
state_path = root / "artifacts/comprobaciones/C03/RELEVO_ACTIVO.json"
state = json.loads(state_path.read_text(encoding="utf-8-sig"))
objective = Path("C:/Users/usuario/.codex/attachments/310753b7-9a38-4a57-951e-007fdcf7693a/goal-objective.md")
state["objectiveFile"] = str(objective)
state["objectiveSha256"] = hashlib.sha256(objective.read_bytes()).hexdigest()
state["checkpoint"] = root.joinpath("artifacts/comprobaciones/C03/CHECKPOINT.md").read_text(encoding="utf-8-sig").split("\n\n", 1)[0]
state["workStatus"] = "process803_waiting_ram_identity804_isolated_root_review"
state["goalStatusNote"] = "C03 active. Updated owner objective explicitly prioritizes minimal complexity; RAM question pending, independent work continues."
state["publishedEvidenceCommit"] = "a1633b09"
state["diagnosticTaskManager"] = {"status": "closed_by_owner", "confirmed_absent": True,
    "evidence": "C:/Users/usuario/AppData/Local/BAXY/C03-task-manager-observation804-private/OBSERVATION.json",
    "product_credit": False, "atUtc": datetime.now(timezone.utc).isoformat()}
state_path.write_bytes((json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(json.dumps({"objective_sha256": state["objectiveSha256"], "survey": state["surveyVerificationCounts"]}))
