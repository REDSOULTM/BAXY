"""Materialize root-adjudicated final-answer quality; never adopt source or model."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import statistics
from collections import Counter

parser = argparse.ArgumentParser()
parser.add_argument("model", choices=["k2", "qwen"])
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
private = Path(os.environ["LOCALAPPDATA"]) / f"BAXY/C03-native-product736-{args.model}-private"
public = root / f"artifacts/comprobaciones/C03/NATIVE_PRODUCT736/{args.model}"
review = json.loads((private / "review.json").read_text(encoding="utf-8"))
assert len(review) == (50 if args.model == "k2" else 73)
passes = {"H0025", "H0442", "H0644", "gpu-identity-en", "memory-used-es", "H0144", "H0665",
          "battery-charge-en", "battery-level-es", "H0126", "H0449"}
markers = {"H0207", "H0384"}
evidenced = {"H0023": "shared_domain_veto", "H0103": "shared_domain_veto",
            "disk-used-es": "shared_domain_veto", "H0104": "prose_validator_false_rejection",
            "H0359": "native_selector_no_fresh_read_then_guard_timeout"}
qwen_failures = {}


def qwen_fail(ids, category, reason):
    for case_id in ids.split():
        assert case_id not in qwen_failures
        qwen_failures[case_id] = {"category": category, "reason": reason}


qwen_fail("H0023 H0103 H0209 H0663 windows-all-en", "inventory_not_delivered",
          "Explicit request for window inventory ends in a question without enumeration. English variant also changes scope and language.")
qwen_fail("disk-used-es H0532 H0675", "no_fresh_read",
          "Current PC quantity/ranking asserted without a fresh Core read; previous conversational values are insufficient.")
qwen_fail("H0194", "unverified_gpu_hierarchy",
          "Observed adapter identity/capacity is correct, but calling one GPU principal adds an unobserved relationship.")
qwen_fail("H0539 H0508", "memory_usable_labelled_available",
          "Labels about16.54GB usable total as available although fresh available RAM is about2.85GB.")
qwen_fail("H0037", "unverified_charging_completion",
          "Correctly says not charging, but adds that the battery is already charged; payload96%/not charging/AC does not establish completed charging.")
qwen_fail("H0065", "defective_spanish_after_repair",
          "CPU number is correct, but published repair says Esto computer; not natural Spanish for this Spanish request.")
qwen_fail("H0359 cpu-order-es H0450 H0499 H0602 clock-date-en audio-order-es", "supported_read_not_delivered",
          "Requested existing read did not reach Core; refusal, interpretation failure or no final does not fulfill it.")
qwen_fail("H0732", "interface_not_internet_verification",
          "network.status derives online only from interfaces that are up; no Internet reachability was verified.")
qwen_fail("network-wifi-en", "wifi_absence_extended_to_all_networks",
          "WLAN observation supports no Wi-Fi connection, not the published absence of every network connection.")
qwen_fail("network-internet-es", "supported_connectivity_read_not_delivered",
          "Refuses to verify Internet without performing a read.")
qwen_fail("H0364 processes-top2-es", "cpu_ranking_metric_and_membership",
          "Provider ranks cumulative CPU seconds, not current consumption; final also changes members/order of the observed list.")
assert len(qwen_failures) == 25
verdicts = []
for row in review:
    case_id, terminal = row["case_id"], row["terminal"]
    if args.model == "qwen":
        failure = qwen_failures.get(case_id)
        verdict = {"pass": failure is None, **(failure or {
            "reason": "Requested final fact matches this turn's fresh typed observation, scope and units."})}
        if failure is None:
            assert terminal["kind"] == "published_final" and row["core_calls"]
    elif case_id in passes:
        assert terminal["kind"] == "published_final" and row["core_calls"]
        verdict = {"pass": True, "reason": "Requested final fact matches this turn's fresh typed payload and units."}
    elif case_id in markers:
        assert terminal["kind"] == "published_final" and "</ifm|think>" in terminal["final"]
        verdict = {"pass": False, "reason": "Internal reasoning delimiter leaked into published final; already present in HTTP content."}
    else:
        assert terminal["kind"] == "composition_failed"
        verdict = {"pass": False, "reason": "No final response was published; not a claim that the native model chose incorrectly."}
    verdicts.append({"case_id": case_id, "turn_id": row["turn_id"], "group": row["group"],
        **verdict, "first_loss_attribution": evidenced.get(case_id,
            "server_content_delimiter_origin_unresolved" if case_id in markers else None) if args.model == "k2" else None,
        "route_note": "Also performed an unnecessary summary read; final-answer pass does not certify minimal operation scope."
            if case_id == "gpu-identity-en" else None,
        "trace_duration_ms": row["trace_duration_ms"]})
durations = [row["trace_duration_ms"]/1000 for row in review]
result = {"model": args.model, "registered_cases": 73, "completed_terminals": len(review),
    "correct_finals": sum(row["pass"] for row in verdicts), "failed_finals": sum(not row["pass"] for row in verdicts),
    "not_evaluated": 73-len(review), "capture_interrupted": args.model == "k2",
    "terminal_kinds": dict(Counter(row["terminal"]["kind"] for row in review)),
    "final_latency_seconds": {"median_all_completed_including_failures": statistics.median(durations), "max": max(durations)},
    "method": "Root reviewed all completed finals and fresh typed facts; bounded independent review assisted Qwen first23. No final means delivery failure, not native semantic failure. Scores concern requested final-answer quality, including unsupported additions and natural requested language; noted redundant reads prevent interpreting a pass as full product acceptance.",
    "judgment_notes": {
        "H0037": "Conservative failure for completed-charge addition. Accepting it as loose wording adds one pass.",
        "H0194": "Conservative failure for unobserved principal GPU. Scoring only requested core identity adds one pass.",
        "H0655": "Accepted because same final explicitly distinguishes free, used and installed from total usable; treating disponible en total as independently misleading subtracts one pass.",
    } if args.model == "qwen" else {},
    "review_sha256": hashlib.sha256((private / "review.json").read_bytes()).hexdigest(),
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "verdicts": verdicts, "adopted": False, "model_promoted": False, "survey_coverage_added": 0}
(public / "ADJUDICATION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "verdicts"}, ensure_ascii=False))
