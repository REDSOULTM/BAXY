"""Explicit complete-output judgments by the root agent; no product mutation."""
from pathlib import Path
import collections
import hashlib
import json
import os
import statistics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/comprobaciones/C03/FACTS_PROMPT737"
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-facts-prompt737-private"

# P: faithful final; F: incorrect/unsupported assertion or unusable language;
# I: supplied observation does not establish requested scope; E: delivery failure.
# The root reviewer inspected complete final content, not only the key numeric answer.
JUDGMENTS = {
    "H0104": ("F", "E", "Native infers off-screen placement from negative border coordinates; BAXY arm PEG500, semantic final not delivered."),
    "windows-focus-mixed": ("F", "P", "Native adds centered placement without screen geometry; BAXY final identifies observed focus and maximized state."),
    "windows-focus-reference-es": ("P", "P", "Both identify observed active window."),
    "H0025": ("F", "P", "Native says available disk space includes cache and temporary files; BAXY gives observed free value."),
    "H0207": ("I", "I", "Observation contains disk figures but no drive identity; cannot independently establish requested C: scope."),
    "H0384": ("F", "P", "Native turns empty read-failures into a claim of no disk faults; disk health was not measured."),
    "H0442": ("P", "P", "Observed free disk value, correct units."),
    "H0644": ("F", "P", "Native guarantees temporary/backups use will not affect long-term storage; no workload/storage evidence supports that assurance."),
    "disk-free-en": ("I", "I", "Same missing drive identity as H0207, despite correct disk figures."),
    "H0026": ("F", "F", "Native invents primary GPU/use assignment; BAXY reports per-adapter AMD capacity as total across several adapters."),
    "H0087": ("F", "P", "Native asserts primary GPU and actual shared RAM use from capacity limit; BAXY names observed adapters."),
    "H0114": ("F", "P", "Native invents virtual-duplicate explanation and labels engine usage CPU/GPU; BAXY VRAM percentage is observed."),
    "H0194": ("F", "P", "Native invents primary/physical-duplicate explanation and confuses dedicated/shared capacity; BAXY reports observed capacities."),
    "H0370": ("F", "P", "Native assigns primary role without observation; BAXY gives observed adapter and dedicated capacity."),
    "H0625": ("F", "F", "Native invents physical/virtual roles and leaks unrelated-language text; BAXY replaces observed6.2873GB capacity with12GB."),
    "gpu-identity-en": ("F", "F", "Native assigns primary role; BAXY labels AMD integrated although supplied observation does not distinguish integrated/discrete."),
    "gpu-usage-es": ("F", "F", "Native declares primary/active and other adapters irrelevant; BAXY invents incorrect total4.93GB and treats partial readings as all GPUs."),
    "H0111": ("P", "P", "Both distinguish installed, used and free RAM correctly."),
    "H0156": ("P", "P", "Observed free RAM, correct rounding."),
    "H0162": ("P", "P", "Observed installed RAM."),
    "H0342": ("P", "P", "Observed used RAM."),
    "H0539": ("P", "P", "Native distinguishes usable/installed/free; BAXY gives installed RAM."),
    "H0655": ("F", "P", "Native invents hypervisor/server and attributes system used RAM to one application; BAXY gives observed usable total and free RAM."),
    "H0508": ("F", "P", "Native invents cause for installed/usable difference and treats usable as per-program available; BAXY gives observed Windows family and installed RAM."),
    "memory-total-en": ("F", "P", "Native invents virtual-memory/disk-cache reason for installed/usable difference; BAXY gives installed physical RAM."),
    "memory-free-mixed": ("P", "P", "Observed free RAM in natural Spanish."),
    "memory-used-es": ("P", "P", "Observed used RAM."),
    "H0037": ("P", "F", "Native states not charging/AC online correctly, though awkwardly treats input as a label and speculates conditionally; BAXY contradicts AC online and leaks Hindi."),
    "H0144": ("F", "P", "Native adds global everything-working-correctly claim without health observation; BAXY gives observed battery percentage."),
    "H0379": ("P", "P", "Observed charge percentage, native also preserves charging and AC states."),
    "H0665": ("P", "P", "Observed battery percentage."),
    "battery-charge-en": ("F", "P", "Native suggests full-capacity cause at96% without supporting evidence; BAXY preserves not-charging and AC-online facts."),
    "battery-level-es": ("P", "P", "Observed battery percentage."),
    "H0065": ("F", "F", "Native contradicts16threads/8cores with one thread per core and adds incorrect advice; BAXY claims stable load and no faults from one sample without health measurement."),
    "H0350": ("F", "E", "Native generalizes read-failures to system faults and emits corrupted Spanish; BAXY exceeds offline120s observation with no final."),
    "cpu-usage-en": ("F", "F", "Native infers normal operation and running workload from CPU percentage alone; BAXY reports14.46 although14.4654088 rounds to14.47 at two decimals. Sensitivity: accept truncation adds one BAXY pass."),
    "H0126": ("P", "P", "Observed hour and minute."),
    "H0180": ("P", "P", "Observed date in natural text/ISO representation."),
    "H0223": ("P", "P", "Observed hour and minute, English or language-neutral numeric answer."),
    "H0449": ("P", "P", "Observed hour and minute; native has minor agreement error but unambiguous meaning."),
    "H0498": ("P", "P", "Observed hour and minute."),
    "H0586": ("P", "P", "Observed hour and minute."),
    "H0600": ("P", "E", "Native delivers observed time; BAXY arm sends84SSE events with reasoning only, then stop, no final content."),
    "H0700": ("P", "P", "Observed hour and minute; native minor agreement error does not change meaning."),
    "H0727": ("P", "P", "Observed hour and minute."),
    "clock-time-mixed": ("P", "P", "Observed time; natural Spanish is valid for mixed input."),
    "clock-date-reference-es": ("P", "P", "Observed date."),
    "H0127": ("F", "P", "Native invents Windows navigation and emits nonsensical Spanish in explanations; BAXY preserves no Wi-Fi connection."),
    "H0433": ("F", "F", "Native equates no Wi-Fi with no Internet and invents Ethernet detection steps; BAXY uses an imperative instead of reporting the observed state. Sensitivity: interpreting estes as a typo for estas adds one BAXY pass."),
    "H0732": ("I", "I", "Provider online means an interface is up, not verified Internet; frozen payload omits this distinction, so Internet cannot be established from it."),
    "network-wifi-en": ("P", "P", "Both preserve no Wi-Fi connection without asserting absence of all networks."),
    "H0364": ("I", "I", "Cumulative CPU seconds do not establish current usage. Additional errors: native invents Taskmgr supervisory relationship and Microsoft ownership; BAXY changes codex1849.21875 to1848.21875."),
    "H0650": ("F", "F", "Native changes observedProcessCount198 to5 while returning top5. BAXY approximates binary GiB quantities with GB labels; e.g.1084989440bytes rounds to1.1GB at one decimal, not1.0GB."),
    "processes-top3-en": ("P", "F", "Native preserves top3 and exact byte values. BAXY conversions1.01/0.83/0.73GB match neither decimal GB nor correctly rounded binary GiB."),
    "processes-top2-es": ("I", "I", "Cumulative CPU seconds rank historical processor time, not current CPU usage; two samples/rate are absent."),
    "H0383": ("P", "P", "Observed level100 and not-muted state; native lexical calque mutado is awkward but the audio meaning is unambiguous."),
    "audio-status-en": ("P", "P", "Observed volume and not-muted state."),
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = read(OUT / "RESULT.json")
    cases = read(PRIVATE / "cases.json")
    rows = [json.loads(line) for line in (PRIVATE / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert result["calls_completed"] == result["calls_planned"] == len(rows) == 114
    assert set(JUDGMENTS) == {case["case_id"] for case in cases}, "Every case needs explicit review"
    records = {(row["case_id"], row["arm"]): row for row in rows}
    assert len(records) == 114
    reviews = []
    for case in cases:
        first, second, reason = JUDGMENTS[case["case_id"]]
        review = {"case_id": case["case_id"], "native_high": first, "baxy_prompt_high": second, "reason": reason,
                  "input_insufficient": "I" in (first, second)}
        for arm, verdict in [("native_high", first), ("baxy_prompt_high", second)]:
            row = records[(case["case_id"], arm)]
            complete = row.get("finish_reason") == "stop" and not row.get("error") and bool(row["content"].strip())
            assert (verdict == "E") == (not complete), (case["case_id"], arm)
            review[arm+"_correct_within4s"] = verdict == "P" and row["complete_within_product_reference_4s"]
        reviews.append(review)
    summary = {}
    for arm in ["native_high", "baxy_prompt_high"]:
        values = [r for r in rows if r["arm"] == arm]
        complete = [r for r in values if r.get("finish_reason") == "stop" and not r.get("error") and r["content"].strip()]
        timing = [r["timings"]["predicted_per_second"] for r in complete if r.get("timings")]
        summary[arm] = {"verdict_counts": dict(collections.Counter(r[arm] for r in reviews)),
            "correct_within4s": sum(r[arm+"_correct_within4s"] for r in reviews),
            "complete_final_median_seconds": statistics.median(r["seconds"] for r in complete),
            "all_requests_median_seconds": statistics.median(r["seconds"] for r in values),
            "max_seconds": max(r["seconds"] for r in values),
            "first_content_median_seconds": statistics.median(r["first_content_seconds"] for r in complete),
            "decode_tokens_per_second_median": statistics.median(timing),
            "completion_tokens_median": statistics.median(r["usage"]["completion_tokens"] for r in complete),
            "context_shift_possible": sum(r["context_shift_possible"] for r in values),
            "context_telemetry_unknown": sum(not r.get("usage") for r in values)}
    summary["paired_quality"] = {
        "both_correct": sum(r["native_high"] == r["baxy_prompt_high"] == "P" for r in reviews),
        "baxy_only_correct": sum(r["native_high"] != "P" and r["baxy_prompt_high"] == "P" for r in reviews),
        "native_only_correct": sum(r["native_high"] == "P" and r["baxy_prompt_high"] != "P" for r in reviews),
        "neither_correct": sum(r["native_high"] != "P" and r["baxy_prompt_high"] != "P" for r in reviews)}
    artifact = {"method": "Root review of whole final content versus frozen question and observations. Length alone is not failure. Hedged possibilities distinguished from assertions. Missing drive/network/process evidence separated as I; delivery error E is not a semantic model failure.",
        "labels": {"P": "faithful answer", "F": "incorrect or unsupported assertion / unusable language", "I": "insufficient supplied facts for requested scope", "E": "delivery failure"},
        "cases_sha256": sha(PRIVATE / "cases.json"), "results_sha256": sha(PRIVATE / "results.jsonl"),
        "summary": summary, "reviews": reviews, "adopted": False, "model_promoted": False, "survey_coverage_added": 0}
    (OUT / "ADJUDICATION.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    transport = read(OUT / "TRANSPORT.json")
    transport.update(adjudication_pending=False, adjudication_file="ADJUDICATION.json",
                     adjudication_sha256=sha(OUT / "ADJUDICATION.json"))
    (OUT / "TRANSPORT.json").write_text(json.dumps(transport, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
