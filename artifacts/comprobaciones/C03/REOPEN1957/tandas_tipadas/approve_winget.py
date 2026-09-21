"""Root review of one package.uninstall proposal (grupo G; D13): only the owner's test package may be removed.

Usage: approve_winget.py <reviews_dir> <case_id> <receipt.json> [timeout_s]

Approves ONLY if: schema conductor-review-proposal-v1, caseId matches, operation == package.uninstall and the
package argument (packageId or name) folds to 7zip.7zip / 7-zip / 7zip. Spotify, Discord or anything else of the
owner is never approved. Installs (package.install.prepare/commit) are ordinary turns (RiskPolicy: Installation →
Allow) and never reach a review. One approval at most.
"""
import datetime
import hashlib
import json
import sys
import time
import unicodedata
from pathlib import Path

TEST_PACKAGES = {"7zip.7zip", "7-zip", "7zip", "7 zip"}


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def fold(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(c for c in text if not unicodedata.combining(c)).casefold().strip()


def main():
    reviews, case_id, receipt_path = sys.argv[1:4]
    timeout = float(sys.argv[4]) if len(sys.argv) > 4 else 200.0
    receipt = {"schema": "winget-root-package-uninstall-review-receipt-v1", "case_id": case_id, "reviews_dir": reviews,
               "started_at": utc(), "proposal": None, "checks": {}, "decision": None, "approval_path": None}
    deadline = time.time() + timeout
    proposal_path = None
    while time.time() < deadline:
        root = Path(reviews)
        if root.is_dir():
            found = sorted(root.glob("*/proposal.json"))
            if found:
                proposal_path = found[0]
                break
        time.sleep(0.2)
    if proposal_path is None:
        receipt.update(decision="no_proposal_within_timeout", finished_at=utc())
        Path(receipt_path).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"decision": receipt["decision"]}))
        return 2
    time.sleep(0.3)
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    receipt["proposal"] = proposal
    receipt["proposal_sha256"] = hashlib.sha256(proposal_path.read_bytes()).hexdigest()
    checks = receipt["checks"]
    checks["schema"] = proposal.get("schema") == "conductor-review-proposal-v1"
    checks["case_id"] = proposal.get("caseId") == case_id
    checks["operation"] = proposal.get("operation") == "package.uninstall"
    arguments = proposal.get("arguments") or {}
    package = fold(arguments.get("packageId") or arguments.get("name") or arguments.get("package"))
    checks["package_is_test_package"] = package in TEST_PACKAGES
    approve = all(checks.values())
    receipt["decision"] = "approve" if approve else "not_approved"
    if approve:
        approval = {"schema": "conductor-review-approval-v1", "nonce": proposal["nonce"], "caseId": case_id,
                    "operation": proposal["operation"], "missionId": proposal["missionId"],
                    "invocationId": proposal["invocationId"], "arguments": arguments, "decision": "approve"}
        approval_path = proposal_path.parent / "approval.json"
        approval_path.write_text(json.dumps(approval, ensure_ascii=False), encoding="utf-8", newline="\n")
        receipt["approval_path"] = str(approval_path)
        receipt["approval_sha256"] = hashlib.sha256(approval_path.read_bytes()).hexdigest()
    receipt["finished_at"] = utc()
    Path(receipt_path).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": receipt["decision"], "checks": checks, "package": package}, ensure_ascii=False))
    return 0 if approve else 1


if __name__ == "__main__":
    raise SystemExit(main())
