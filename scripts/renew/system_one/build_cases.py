"""System One: the fine-tune goal's synthetic examples (written from the catalog, leak-checked; ft_v1/datos) as bench cases.

usage: py -3.12 -X utf8 scripts/renew/system_one/build_cases.py OUT.json
Each example becomes {id, family, history, text, expect} as in the banks (bench_decision.judge): the first target call
(its op and up to three arguments), an ask, or a text answer. Only the person's and the assistant's plain words go into
the history (a case starts before any tool result), so qwen_signals.py can run them as it runs a bank.
"""
import glob
import json
import sys
from pathlib import Path

SOURCE = Path(r"F:\BAXYeval\ft_v1\datos")
FILES = sorted(glob.glob(str(SOURCE / "G*.emb_limpio.jsonl"))) + [str(SOURCE / "G9.limpio.jsonl")]


def expect_of(target):
    if target["kind"] == "call":
        call = target["calls"][0]
        args = {k: v for k, v in (call.get("arguments") or {}).items()
                if isinstance(v, (str, int, float, bool))}
        return {"kind": "call", "op": call["op"], "args": dict(list(args.items())[:3])}
    return {"kind": target["kind"]}


def main():
    cases = []
    for path in FILES:
        for line in open(path, encoding="utf-8"):
            row = json.loads(line)
            history = [{"role": m["role"], "content": m["content"]} for m in row.get("history") or []
                       if m.get("role") in ("user", "assistant") and str(m.get("content") or "").strip()]
            cases.append({"id": row["id"], "family": "sint_" + row["family"], "source": row["source"],
                          "history": history, "text": row["text"], "expect": expect_of(row["target"])})
    Path(sys.argv[1]).write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    print(len(cases), "cases ->", sys.argv[1])


if __name__ == "__main__":
    main()
