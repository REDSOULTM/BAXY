"""Replay every captured writer draft against the old and current focus piece."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from baxy_mind import llm, window_prose_facts

BASE = ROOT / "artifacts/comprobaciones/C03"
OUT = BASE / "WINDOW_FOCUS738"
LOCAL = Path(os.environ["LOCALAPPDATA"]) / "BAXY"
PRIVATE = LOCAL / "C03-window-focus738-private"
OLD_COMMIT = "d47a92c532f205a71a39eec83c606b9a8ac939d3"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    old_source = subprocess.check_output(["git", "show", OLD_COMMIT+":src/baxy_mind/window_prose_facts.py"], cwd=ROOT)
    old = types.ModuleType("baxy_mind._window_before738")
    old.__package__ = "baxy_mind"
    exec(compile(old_source, "window_before738.py", "exec"), old.__dict__)
    rows, sources = [], {}
    for model in ["k2", "qwen"]:
        path = LOCAL / f"C03-native-product736-{model}-private/review.json"
        sources[str(path)] = sha(path.read_bytes())
        for case in read(path):
            for index, draft in enumerate(case["compose"]):
                if isinstance(draft.get("draft"), str) and isinstance(draft.get("payload"), dict):
                    rows.append({"source": "736_"+model, "case_id": case["case_id"], "draft_index": index,
                                 "stage": draft.get("stage"), "question": case["text"],
                                 "draft": draft["draft"], "payload": draft["payload"]})
    facts = {c["case_id"]: c for c in read(LOCAL / "C03-facts-prompt737-private/cases.json")}
    judgments = {c["case_id"]: c for c in read(BASE / "FACTS_PROMPT737/ADJUDICATION.json")["reviews"]}
    path = LOCAL / "C03-facts-prompt737-private/results.jsonl"
    sources[str(path)] = sha(path.read_bytes())
    for line in path.read_text(encoding="utf-8").splitlines():
        result = json.loads(line)
        if result["content"] and result.get("finish_reason") == "stop" and not result.get("error"):
            case = facts[result["case_id"]]
            rows.append({"source": "737_"+result["arm"], "case_id": case["case_id"],
                         "stage": "final", "question": case["text"], "draft": result["content"],
                         "payload": case["facts"], "whole_answer_judgment": judgments[result["case_id"]][result["arm"]]})
    original_validator = llm.window_fact_defect
    try:
        for row in rows:
            args = row["draft"], row["payload"], row["question"]
            row["focus_before"] = old.window_focus_feedback(*args)
            row["focus_after"] = window_prose_facts.window_focus_feedback(*args)
            llm.window_fact_defect = old.window_fact_defect
            row["all_facts_before"] = llm._payload_fact_defect(*args)
            llm.window_fact_defect = original_validator
            row["all_facts_after"] = llm._payload_fact_defect(*args)
    finally:
        llm.window_fact_defect = original_validator
    OUT.mkdir(exist_ok=True)
    PRIVATE.mkdir(exist_ok=True)
    (PRIVATE / "replay.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    changed = [r for r in rows if r["focus_before"] != r["focus_after"] or r["all_facts_before"] != r["all_facts_after"]]
    faithful_rejected = [r for r in rows if r.get("whole_answer_judgment") == "P" and r["focus_after"]]
    def identity(row):
        return json.dumps([row["source"], row["case_id"], row["question"], row["draft"], row["payload"]],
                          ensure_ascii=False, sort_keys=True)
    unique_windows = {identity(r): r for r in rows if str(r["payload"].get("operation", "")).startswith("window.")}
    lines = ["# Replay privado de ventanas 738", "", "Preguntas, hechos y respuestas literales capturados antes de esta corrección. No son lecturas actuales del PC.", ""]
    for row in unique_windows.values():
        lines.extend([f"## {row['source']} / {row['case_id']}", "", "Entrada:", "", row["question"],
                      "", "Respuesta:", "", row["draft"], "", "Hechos y validación:", "", "```json",
                      json.dumps({k: row[k] for k in ["payload", "focus_before", "focus_after", "all_facts_before", "all_facts_after"]}, ensure_ascii=False, indent=2), "```", ""])
    (PRIVATE / "RESPUESTAS.md").write_text("\n".join(lines), encoding="utf-8")
    result = {"baseline_commit": OLD_COMMIT, "baseline_source_sha256": sha(old_source),
        "candidate_source_sha256": sha((ROOT / "src/baxy_mind/window_prose_facts.py").read_bytes()),
        "drafts": len(rows), "window_drafts": sum(str(r["payload"].get("operation", "")).startswith("window.") for r in rows),
        "unique_drafts": len({identity(r) for r in rows}), "unique_window_drafts": len(unique_windows),
        "unique_changed_drafts": len({identity(r) for r in changed}),
        "changes": [{k: r.get(k) for k in ["source", "case_id", "draft_index", "stage", "all_facts_before", "all_facts_after"]} for r in changed],
        "faithful737_focus_rejections": [{"source": r["source"], "case_id": r["case_id"]} for r in faithful_rejected],
        "source_pins": sources, "replay_sha256": sha((PRIVATE / "replay.json").read_bytes()),
        "scope": "Offline replay of captured facts/drafts, not fresh product/UI/voice or survey acceptance.",
        "adopted": False, "survey_coverage_added": 0}
    (OUT / "REPLAY.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    for row in faithful_rejected:
        print(json.dumps({k: row[k] for k in ["source", "case_id", "draft", "focus_after"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
