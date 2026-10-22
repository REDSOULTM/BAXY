"""System One, Laya v2: the training file with the same requests said other ways.

usage: py -3.12 -X utf8 scripts/renew/system_one/assemble_laya.py DATADIR [--paraphrases FILE] [--noise 0.3]
Reads DATADIR/train.jsonl (build_kev_data.py, labels on each question) and DATADIR/train.ids.jsonl (the same lines'
cases) and writes DATADIR/laya_train_aug.jsonl for laya-train: every case as it is; its rewordings (teacher.py
--paraphrase: Chilean colloquial, spanglish, dictated) that keep its numbers and proper names; and, for a share of the
cases, a dictation-like copy (no capitals, accents or punctuation, one letter slipped in a long word). Each copy keeps
the case's labels and shuffles its options again. Only training cases are touched: calibration and dev stay as they are.
"""
import argparse
import collections
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent.parent / "src"))
from baxy_mind.system_one import state_text  # noqa: E402


def fold(text):
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def keeps_facts(original, variant):
    """A rewording that drops a number or a proper name of the original asks for something else."""
    words = fold(variant)
    numbers = re.findall(r"\d+", original)
    names = [w for i, w in enumerate(re.findall(r"\b[\wÁÉÍÓÚÑáéíóúñ]+\b", original))
             if i > 0 and w[:1].isupper() and len(w) >= 3]
    return all(n in words for n in numbers) and all(fold(n) in words for n in names)


def dictated(text, rng):
    """Like a speech recognizer's output: lower case, no accents or punctuation, one letter slipped in a long word."""
    text = re.sub(r"[¿?¡!.,;:«»\"()]", "", fold(text))
    words = text.split()
    long = [i for i, w in enumerate(words) if len(w) >= 5]
    if long:
        i = rng.choice(long)
        w = words[i]
        j = rng.randrange(1, len(w) - 1)
        words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:] if rng.random() < 0.5 else w[:j] + w[j + 1:]
    return " ".join(words)


def laya_record(record, state, rng):
    questions, expected = {}, {}
    for qid, body in record["questions"].items():
        keys = list(body["criteria"])
        rng.shuffle(keys)
        questions[qid] = {"type": body["type"], "instructions": body["instructions"],
                          "criteria": {k: body["criteria"][k] for k in keys}}
        expected[qid] = body["label"]
    return {"state": state, "questions": questions, "expected": expected}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("datadir")
    parser.add_argument("--paraphrases")
    parser.add_argument("--noise", type=float, default=0.3)
    args = parser.parse_args()
    rng = random.Random(20261022)
    data = Path(args.datadir)
    records = [json.loads(line) for line in open(data / "train.jsonl", encoding="utf-8")]
    cases = [json.loads(line) for line in open(data / "train.ids.jsonl", encoding="utf-8")]
    variants = {}
    if args.paraphrases:
        for line in open(args.paraphrases, encoding="utf-8"):
            item = json.loads(line)
            variants[item["id"]] = item["variants"]
    stats = collections.Counter()
    with open(data / "laya_train_aug.jsonl", "w", encoding="utf-8", newline="\n") as out:
        for record, case in zip(records, cases, strict=True):
            out.write(json.dumps(laya_record(record, record["state"], rng), ensure_ascii=False) + "\n")
            stats["original"] += 1
            # Rewordings only of short requests (a pasted text came back as three odd stories, 2026-10-21), without the
            # numbering the small rewriter sometimes put in front («1. chilo: …»), and not much longer than the request
            # (longer ones added things: «en el portátil»).
            short_request = len(case["text"]) <= 120
            for variant in variants.get(case["id"], []) if short_request else []:
                variant = re.sub(r"^\s*\d\s*[).:-]\s*([\wáéíóú ]{1,20}:\s*)?", "", variant).strip()
                if fold(variant) == fold(case["text"]) or len(variant) > 1.6 * len(case["text"]) + 15:
                    stats["paraphrase_dropped_same_or_long"] += 1
                elif not keeps_facts(case["text"], variant):
                    stats["paraphrase_dropped_facts"] += 1
                else:
                    out.write(json.dumps(laya_record(record, state_text(variant, case["history"]), rng),
                                         ensure_ascii=False) + "\n")
                    stats["paraphrase"] += 1
            if rng.random() < args.noise:
                noisy = dictated(case["text"], rng)
                if noisy and fold(noisy) != fold(case["text"]):
                    out.write(json.dumps(laya_record(record, state_text(noisy, case["history"]), rng),
                                         ensure_ascii=False) + "\n")
                    stats["dictated"] += 1
    print(json.dumps(dict(stats), ensure_ascii=False))


if __name__ == "__main__":
    main()
