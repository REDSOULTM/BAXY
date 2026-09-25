"""Everything BAXY or its authors have already seen or indexed, as normalised texts (F1 of the comprensión goal).

A candidate for DEV-A / DEV-B / FINAL is rejected when its normalised text is in this set:
- the uso-real campaign: tandas 1–12 and 20 (turn files and written conversations), every scratchpad corpus of the
  previous session (MASSIVE dev/reserve/en, layers, diagnostics) — any jsonl string under text/literal/utterance;
- the 742 survey (private registry) and the semantic corpus (layers A/B/C);
- every conversation script in artifacts/comprobaciones/C03 (owner script, held-out, cien, banks);
- the product's indices: turn evidence (MASSIVE train, PRESTO train, BAXY history), historical messages, the intent
  bank, the historical runtime intents;
- MASSIVE train es-ES/en-US whole (the evidence index is a subset of it).
Output: exclusion.txt (one normalised text per line) + exclusion.summary.json (count per source).
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import unicodedata

import pandas as pd

REPO = pathlib.Path(r"C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo")
PREV = pathlib.Path(r"C:/Users/usuario/AppData/Local/Temp/claude/C--Users-usuario-Desktop-ETC-Programacion-BAXY-Definitivo/"
                    r"6f29a6a5-6bd3-4363-bc79-bf1974e6d110/scratchpad")
LOCAL = pathlib.Path(os.environ["LOCALAPPDATA"]) / "BAXY"
MASSIVE = pathlib.Path(r"D:/BAXYRuntime/assets/huggingface/hub/datasets--AmazonScience--massive/snapshots/"
                       r"ed58ac423a2f4121720918bf5301577edce4ffd3")
HERE = pathlib.Path(__file__).resolve().parent
KEYS = {"text", "literal", "utterance", "user_query", "content", "message", "text_literal", "paraphrase"}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


def strings(value, key=None):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from strings(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v, key)
    elif isinstance(value, str) and key in KEYS and 0 < len(value) <= 600:
        yield value


def from_jsonl(path: pathlib.Path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                yield from strings(json.loads(line))
            except json.JSONDecodeError:
                continue


def main() -> None:
    seen: dict[str, set[str]] = {}

    def add(source: str, texts) -> None:
        bucket = seen.setdefault(source, set())
        for text in texts:
            folded = norm(text)
            if folded:
                bucket.add(folded)

    # the previous session: tandas, written conversations, every corpus of its scratchpad (≤ 60 MB each)
    for path in sorted(PREV.rglob("*.jsonl")):
        if "datasets" in path.parts or path.stat().st_size > 60_000_000:
            continue
        add("prev_scratchpad", from_jsonl(path))
    # the 742 and the semantic corpus
    add("survey_742", from_jsonl(LOCAL / "C03-survey-requirements336-private" / "requirements.jsonl"))
    for path in sorted((LOCAL / "semantic-corpus-v1").glob("*.jsonl")):
        add("semantic_corpus", from_jsonl(path))
    # every conversation script versioned under C03
    listed = subprocess.run(["git", "-C", str(REPO), "ls-files", "artifacts/comprobaciones/C03"],
                            capture_output=True, text=True, encoding="utf-8", check=True).stdout.split("\n")
    for rel in listed:
        if rel.endswith(".turns.jsonl"):
            add("c03_scripts", from_jsonl(REPO / rel))
    # product indices
    add("turn_evidence", from_jsonl(REPO / "tests/data/turn_evidence_runtime.v1.jsonl"))
    add("historical_messages", from_jsonl(REPO / "tests/data/historical_messages.jsonl"))
    add("intent_bank", from_jsonl(REPO / "src/baxy_mind/data/intent_bank.jsonl"))
    hashes = {json.loads(line)["text_sha256"] for line in open(REPO / "src/baxy_mind/data/historical_runtime_intents.jsonl",
                                                                 encoding="utf-8") if line.strip()}
    (HERE / "exclusion.sha256.txt").write_text("\n".join(sorted(hashes)) + "\n", encoding="utf-8")
    seen["historical_runtime_intents_sha256"] = hashes
    # MASSIVE train, whole
    for locale in ("es-ES", "en-US"):
        for part in sorted((MASSIVE / locale / "train").glob("*.parquet")):
            add("massive_train", pd.read_parquet(part, columns=["utt"])["utt"].astype(str))
    everything = set().union(*(v for k, v in seen.items() if not k.endswith("_sha256")))
    (HERE / "exclusion.txt").write_text("\n".join(sorted(everything)) + "\n", encoding="utf-8")
    summary = {source: len(texts) for source, texts in seen.items()} | {"total_unique": len(everything)}
    (HERE / "exclusion.summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    sys.exit(main())
