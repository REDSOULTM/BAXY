"""Root review of one message.send proposal that follows a message.recipient.resolve{channel: any}
(REOPEN1993 grupo E, D24; D13/D22: the only approvable destinations are the owner's test chats).

Usage: approve_message_send_any.py <reviews_dir> <case_id> <expected_recipient_display> <receipt.json> [timeout_s]

Waits for <reviews_dir>/<nonce>/proposal.json written by the App's reviewed turn, then approves ONLY if:
  - schema conductor-review-proposal-v1, caseId matches, operation == message.send;
  - arguments == {"recipientId", "text"}, non-empty text (the person's words; the root never supplies or edits it);
  - the proposal's read evidence (webSearchObservations = the completed prefix) holds exactly one verified
    message.recipient.resolve whose recipientId equals the argument, whose displayName folds to the expected one
    and whose channel is whatsapp (Música) or discord (Ron92) — the owner's test chats, never a third party.
Anything else is recorded and left unapproved (the App then rejects on timeout). One approval at most.
"""
import datetime
import hashlib
import json
import sys
import time
import unicodedata
from pathlib import Path

TEST_CHATS = {"musica": "whatsapp", "ron92": "discord"}


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def fold(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(c for c in text if not unicodedata.combining(c)).casefold().strip()


def main():
    reviews, case_id, expected_recipient, receipt_path = sys.argv[1:5]
    timeout = float(sys.argv[5]) if len(sys.argv) > 5 else 200.0
    receipt = {"schema": "msgany-root-message-send-review-receipt-v1", "case_id": case_id, "reviews_dir": reviews,
               "expected_recipient": expected_recipient, "started_at": utc(), "proposal": None, "checks": {},
               "decision": None, "approval_path": None}
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
    checks["operation"] = proposal.get("operation") == "message.send"
    arguments = proposal.get("arguments") or {}
    text = arguments.get("text")
    checks["argument_names"] = set(arguments) == {"recipientId", "text"}
    checks["text_present"] = isinstance(text, str) and bool(text.strip()) and len(text.encode("utf-8")) <= 16384
    evidence = proposal.get("webSearchObservations") or []
    resolves = [
        item for item in evidence
        if isinstance(item, dict) and item.get("operation") == "message.recipient.resolve"
        and item.get("verified") is True and item.get("status") == "completed" and isinstance(item.get("result"), dict)
    ]
    checks["one_resolve"] = len(resolves) == 1
    result = resolves[0]["result"] if resolves else {}
    checks["recipient_id_matches"] = bool(result.get("recipientId")) and result.get("recipientId") == arguments.get("recipientId")
    display = fold(result.get("displayName"))
    checks["recipient_expected"] = display == fold(expected_recipient)
    checks["destination_is_test_chat"] = display in TEST_CHATS and result.get("channel") == TEST_CHATS[display]
    approve = all(checks.values())
    receipt["decision"] = "approve" if approve else "not_approved"
    if approve:
        approval = {
            "schema": "conductor-review-approval-v1",
            "nonce": proposal["nonce"],
            "caseId": case_id,
            "operation": proposal["operation"],
            "missionId": proposal["missionId"],
            "invocationId": proposal["invocationId"],
            "arguments": arguments,
            "decision": "approve",
        }
        approval_path = proposal_path.parent / "approval.json"
        approval_path.write_text(json.dumps(approval, ensure_ascii=False), encoding="utf-8", newline="\n")
        receipt["approval_path"] = str(approval_path)
        receipt["approval_sha256"] = hashlib.sha256(approval_path.read_bytes()).hexdigest()
    receipt["finished_at"] = utc()
    Path(receipt_path).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": receipt["decision"], "checks": checks, "channel": result.get("channel"),
                      "display": result.get("displayName"), "text_bytes": len((text or "").encode("utf-8"))}, ensure_ascii=False))
    return 0 if approve else 1


if __name__ == "__main__":
    raise SystemExit(main())
