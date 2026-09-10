"""Read completed 737 records without changing the live inference experiment."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import statistics

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path(os.environ["LOCALAPPDATA"]) / "BAXY/C03-facts-prompt737-private"
OUT = ROOT / "artifacts/comprobaciones/C03/FACTS_PROMPT737"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=0)
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--no-facts", action="store_true")
    args = parser.parse_args()
    cases = read(PRIVATE / "cases.json")
    rows = []
    with (PRIVATE / "results.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            if line.endswith("\n"):
                rows.append(json.loads(line))
    by_key = {(r["case_id"], r["arm"]): r for r in rows}
    assert len(by_key) == len(rows)
    report = {}
    for arm in ["native_high", "baxy_prompt_high"]:
        values = [r for r in rows if r["arm"] == arm]
        complete = [r for r in values if r.get("finish_reason") == "stop" and not r.get("error") and r["content"].strip()]
        report[arm] = {
            "completed_requests": len(values), "valid_final_transport": len(complete),
            "errors_or_incomplete": len(values)-len(complete),
            "completion_median_seconds": statistics.median([r["seconds"] for r in complete]) if complete else None,
            "complete_under4s_not_quality_adjudicated": sum(r["complete_within_product_reference_4s"] for r in values),
            "context_shift_possible": sum(r["context_shift_possible"] for r in values),
            "context_telemetry_missing": sum(not r.get("usage") for r in values),
        }
    print(json.dumps(report, ensure_ascii=False))
    for index in range(args.start, min(args.end, len(cases))):
        case = cases[index]
        print(json.dumps({"index": index, "case_id": case["case_id"], "question": case["text"], "facts": None if args.no_facts else case["facts"],
            "responses": [{"arm": arm, **{k: by_key.get((case["case_id"], arm), {}).get(k) for k in ["content", "error", "seconds", "finish_reason"]}}
                          for arm in ["native_high", "baxy_prompt_high"]]}, ensure_ascii=False))
    if args.export:
        assert (OUT / "RESULT.json").exists(), "Do not seal a live experiment"
        result = read(OUT / "RESULT.json")
        assert result["calls_completed"] == len(rows)
        lines = ["# Respuestas literales 737", "", "Diagnóstico privado con observaciones congeladas. No acredita producto, UI, voz ni cobertura.", ""]
        for case in cases:
            lines.extend([f"## {case['case_id']}", "", "Entrada:", "", case["text"], "", "Hechos suministrados:", "", "```json", json.dumps(case["facts"], ensure_ascii=False, indent=2), "```", ""])
            for arm in ["native_high", "baxy_prompt_high"]:
                row = by_key.get((case["case_id"], arm))
                lines.extend([f"### {arm}", ""])
                if row is None:
                    lines.extend(["No ejecutado.", ""])
                    continue
                lines.extend([row["content"] or "(Sin content)", "", "```json", json.dumps({k: row.get(k) for k in ["seconds", "first_content_seconds", "finish_reason", "error", "usage", "timings"]}, ensure_ascii=False, indent=2), "```", ""])
        (PRIVATE / "RESPUESTAS.md").write_text("\n".join(lines), encoding="utf-8")
        report["calls_completed"] = len(rows)
        report["results_sha256"] = hashlib.sha256((PRIVATE / "results.jsonl").read_bytes()).hexdigest()
        report["adjudication_pending"] = True
        (OUT / "TRANSPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
