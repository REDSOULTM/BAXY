"""Assemble DEV-A, DEV-B and FINAL (turn rows for scripts/comprension_eval.py) from stage1 + gold + written.

- singles and public conversations: stage1 files + the labelers' gold (opaque ids, label/idmap.json);
- written conversations (clean-room writers): pooled, shuffled, dealt to the sets by speaker so every set gets the
  same mix, until each set reaches its turn target;
- history of a conversation turn = the earlier user and assistant turns; ``pending`` = the previous user message when
  the previous assistant turn asked for a value (written: ``assistant_asks``; public: it ends with «?»).
Prints counts and SHA-256 only (never the text): DEV-B is looked at by its figure, FINAL not at all until the close.
usage: assemble.py  (applies <ROOT>/audit/adjudicated_*.jsonl when present: label_id -> final gold)
"""
import hashlib
import json
import os
import pathlib
import random
import sys
from collections import Counter

ROOT = pathlib.Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "comprension-2026-09-25"
HERE = pathlib.Path(__file__).resolve().parent
CATALOG = {c["name"] for c in json.load(open(HERE / "catalog_config.json", encoding="utf-8"))["capabilities"]}
WRITTEN_TURNS = {"A": 75, "B": 75, "F": 60}
NAMES = {"A": "DEV-A", "B": "DEV-B", "F": "FINAL"}


def speaker_of(conv) -> str:
    import unicodedata
    raw = unicodedata.normalize("NFKD", str(conv.get("speaker") or "").casefold())
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    for key, name in (("spanglish", "spanglish"), ("chile", "chileno"), ("rioplat", "rioplatense"),
                      ("argent", "rioplatense"), ("urugu", "rioplatense"), ("mexic", "mexicano"),
                      ("colomb", "colombiano"), ("espan", "espana"), ("spain", "espana"), ("ingl", "ingles"),
                      ("english", "ingles"), ("us", "ingles")):
        if key in raw:
            return name
    return raw or "?"


def valid_label(label: str) -> bool:
    if label in {"web", "talk", "limit", "ask"}:
        return True
    if label.startswith("plan:"):
        return all(op in CATALOG for op in label[5:].split("+"))
    if label.startswith("op:"):
        name = label[3:]
        return any(op.startswith(name[:-1]) for op in CATALOG) if name.endswith("*") else name in CATALOG
    return False


def clean_gold(gold, problems, where):
    labels = [str(g).strip() for g in (gold or []) if str(g).strip()]
    bad = [g for g in labels if not valid_label(g)]
    if bad:
        problems.append(f"{where}: etiquetas inválidas {bad}")
    return [g for g in labels if valid_label(g)]


def clean_args(args, gold):
    if not isinstance(args, dict):
        return {}
    out = {}
    for label, groups in args.items():
        if label not in gold or not isinstance(groups, list):
            continue
        fixed = [[str(a) for a in group] if isinstance(group, list) else [str(group)] for group in groups]
        fixed = [g for g in fixed if g]
        if fixed:
            out[label] = fixed
    return out


def conversation_rows(set_name, conv_id, source, turns, problems):
    rows, history = [], []
    for index, turn in enumerate(turns):
        where = f"{conv_id}:t{index + 1}"
        gold = clean_gold(turn.get("gold"), problems, where)
        if not gold:
            problems.append(f"{where}: sin oro")
        previous = turns[index - 1] if index else None
        asks = bool(previous and (previous.get("assistant_asks")
                                  if "assistant_asks" in previous
                                  else str(previous.get("assistant") or "").rstrip().endswith("?")))
        rows.append({
            "id": f"{set_name}-{conv_id}-t{index + 1}", "set": set_name, "kind": "conv", "conv": conv_id,
            "turn": index + 1, "source": source, "text": turn["user"], "history": list(history),
            "pending": previous["user"] if asks else None, "dep": bool(turn.get("dep")) if index else False,
            "gold": gold, "args": clean_args(turn.get("args"), gold),
        })
        history.append({"role": "user", "content": turn["user"]})
        if turn.get("assistant"):
            history.append({"role": "assistant", "content": str(turn["assistant"])})
    return rows


def main() -> None:
    problems: list[str] = []
    idmap = json.loads((ROOT / "label" / "idmap.json").read_text(encoding="utf-8"))
    gold = {}
    for k in (1, 2, 3):
        for line in open(ROOT / "label" / f"gold{k}.jsonl", encoding="utf-8"):
            if line.strip():
                row = json.loads(line)
                gold[row["id"]] = row
    adjudicated = {}
    for path in sorted((ROOT / "audit").glob("adjudicated_*.jsonl")):
        for line in open(path, encoding="utf-8"):
            if line.strip():
                row = json.loads(line)
                adjudicated[row["label_id"]] = row["gold"]
    missing = sorted(set(idmap) - set(gold))
    if missing:
        problems.append(f"sin oro del etiquetador: {len(missing)} ítems")
    by_place = {(v["set"], v["kind"], v["index"]): k for k, v in idmap.items()}
    sets: dict[str, list[dict]] = {s: [] for s in NAMES}
    for s in NAMES:
        for i, line in enumerate(open(ROOT / "stage1" / f"singles_{s}.jsonl", encoding="utf-8")):
            row = json.loads(line)
            opaque = by_place[(s, "single", i)]
            labeled = gold.get(opaque, {})
            g = clean_gold(labeled.get("gold"), problems, opaque)
            sets[s].append({"id": f"{s}-s{i + 1:03d}", "set": s, "kind": "single", "conv": None, "turn": 1,
                            "source": row["source"], "text": row["text"], "history": [], "pending": None,
                            "dep": False, "gold": g, "args": clean_args(labeled.get("args"), g), "label_id": opaque})
        for i, line in enumerate(open(ROOT / "stage1" / f"pubconv_{s}.jsonl", encoding="utf-8")):
            conv = json.loads(line)
            opaque = by_place[(s, "pubconv", i)]
            labeled = (gold.get(opaque) or {}).get("turns") or []
            if len(labeled) != len(conv["turns"]):
                problems.append(f"{opaque}: {len(labeled)} turnos etiquetados de {len(conv['turns'])}")
                continue
            turns = [{**t, **lab} for t, lab in zip(conv["turns"], labeled)]
            rows = conversation_rows(s, f"p{i + 1:02d}", conv["source"], turns, problems)
            for row, t in zip(rows, range(len(rows))):
                row["label_id"] = f"{opaque}:t{t + 1}"
            sets[s].extend(rows)
    written = []
    for path in sorted((ROOT / "written").glob("writer*.jsonl")):
        for line in open(path, encoding="utf-8"):
            if line.strip():
                written.append(json.loads(line))
    rng = random.Random(250925)
    rng.shuffle(written)
    written.sort(key=speaker_of)
    by_speaker: dict[str, list] = {}
    for conv in written:
        by_speaker.setdefault(speaker_of(conv), []).append(conv)
    counts = {s: 0 for s in NAMES}
    order = []
    for convs in by_speaker.values():
        rng.shuffle(convs)
        order.extend(convs)
    numbering = {s: 0 for s in NAMES}
    for conv in order:
        deficits = {s: (WRITTEN_TURNS[s] - counts[s]) / WRITTEN_TURNS[s] for s in NAMES}
        target = max(deficits, key=deficits.get)
        if deficits[target] <= 0:
            break
        numbering[target] += 1
        turns = conv["turns"]
        rows = conversation_rows(target, f"w{numbering[target]:02d}", f"written:{speaker_of(conv)}", turns, problems)
        for row, t in zip(rows, range(len(rows))):
            row["label_id"] = f"{conv['conv']}:t{t + 1}"
        sets[target].extend(rows)
        counts[target] += len(turns)
    applied = 0
    for s in NAMES:
        for row in sets[s]:
            final = adjudicated.get(row["label_id"])
            if final:
                cleaned = clean_gold(final, problems, f"adjudicado {row['label_id']}")
                if cleaned:
                    applied += cleaned != row["gold"]
                    row["gold"] = cleaned
                    row["args"] = {k: v for k, v in row["args"].items() if k in cleaned}
    out = ROOT / "sets"
    out.mkdir(exist_ok=True)
    report = {}
    for s, name in NAMES.items():
        path = out / f"{name}.jsonl"
        with open(path, "w", encoding="utf-8", newline="\n") as sink:
            for row in sets[s]:
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
        rows = sets[s]
        report[name] = {
            "turns": len(rows), "singles": sum(r["kind"] == "single" for r in rows),
            "conversation_turns": sum(r["kind"] == "conv" for r in rows),
            "followups_dep": sum(r["kind"] == "conv" and r["dep"] for r in rows),
            "conversations": len({r["conv"] for r in rows if r["conv"]}),
            "with_args": sum(bool(r["args"]) for r in rows),
            "sources": dict(Counter(r["source"].split(":")[0] for r in rows)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    print(f"written conversations pooled: {len(written)}; used turns per set: {counts}; adjudicated golds applied: {applied}")
    print(f"problems: {len(problems)}")
    for p in problems[:40]:
        print("  ", p)


if __name__ == "__main__":
    main()
