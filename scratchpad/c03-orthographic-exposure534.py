"""Conservative reserve audit: punctuation/accent variants are not fresh cases."""
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
LOCAL = Path(os.environ["LOCALAPPDATA"]) / "BAXY"
ART = ROOT / "artifacts/comprobaciones/C03/astra-orthographic-exposure534"
OUT = LOCAL / "C03-orthographic-exposure534-private"
ART.mkdir(exist_ok=False)
OUT.mkdir(exist_ok=False)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rows(folder):
    return [json.loads(line) for line in (LOCAL / folder / "review.jsonl").read_text(encoding="utf-8-sig").splitlines()]


def key(value):
    folded = "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))
    return " ".join(re.findall(r"[^\W_]+", folded))


reserve = rows("C03-reserve-language475-private")
training = {r["id"]: r for r in rows("C03-training-audit518-private")}
prior = {r["id"]: r for r in rows("C03-private-exposure533-private")}
index = defaultdict(set)
for row in reserve:
    if key(row["text_literal"]):
        index[key(row["text_literal"])].add(row["id"])
hits = defaultdict(set)
sources = []
errors = []


def visit(value, ref, depth=0):
    if depth > 30:
        errors.append({"ref": ref, "error": "depth limit"})
        return
    if isinstance(value, str):
        for text in [value, *value.splitlines()]:
            for identifier in index.get(key(text), ()):
                hits[identifier].add(ref)
        if value.lstrip().startswith(("{", "[")):
            try:
                parsed = json.loads(value)
            except (ValueError, RecursionError):
                return
            if isinstance(parsed, (dict, list)):
                visit(parsed, ref, depth + 1)
    elif isinstance(value, dict):
        for item in value.values():
            visit(item, ref, depth + 1)
    elif isinstance(value, list):
        for item in value:
            visit(item, ref, depth + 1)


inventory = {}
for folder, method in (("C03-exposure532-private", "code_or_panel"), ("C03-private-exposure533-private", "actual_private_log"), ("C03-training-audit518-private", "inherited_training")):
    for entry in json.loads((LOCAL / folder / "sources.json").read_text(encoding="utf-8-sig")):
        inventory[entry["path"]] = {"path": entry["path"], "method": method, "prior_sha256": entry.get("sha256", entry.get("sha256_after"))}
dump(ART / "PREREG.json", {"utc": datetime.now(timezone.utc).isoformat(), "why": "Freshness checks532/533/518 ignored punctuation and accent equivalence: a question without ¿? or an accented command cannot be credited as a new independent case merely by spelling. This only excludes conservatively, never certifies a nonmatch.", "method": "NFKD, casefold, remove combining marks, compare complete sequences of alphanumeric words. Preserve word order/numbers; no stemming, translations or semantic relabelling. Sources are exact inventories532/533/518, no new traversal or model inference.", "source_count": len(inventory), "reserve": 204, "privacy": "Only counts/hashes public; exact matches and originals stay private."})
for entry in inventory.values():
    path = Path(entry["path"])
    before = sha(path)
    entry["sha256_before"] = before
    if before != entry["prior_sha256"]:
        errors.append({"path": str(path), "error": "changed since previous inventory"})
    try:
        if path.suffix == ".py":
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    visit(node.value, f"{path}:{node.lineno}")
        elif path.suffix == ".cs":
            text = path.read_text(encoding="utf-8-sig")
            for match in re.finditer(r'(?<![$@])"(?:[^"\\\r\n]|\\.)*"', text):
                try:
                    value = json.loads(match.group())
                except ValueError:
                    continue
                visit(value, f"{path}:{text.count(chr(10), 0, match.start()) + 1}")
        elif path.suffix == ".jsonl":
            with path.open(encoding="utf-8-sig") as stream:
                for number, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if entry["method"] == "inherited_training":
                        data = {field: data.get(field) for field in ("user_text", "prev_text", "final_reply", "q")}
                    visit(data, f"{path}:{number}")
        elif path.suffix == ".json" and path.stat().st_size <= 1_000_000:
            visit(json.loads(path.read_text(encoding="utf-8-sig")), str(path))
        else:
            errors.append({"path": str(path), "error": "unparsed type or large JSON"})
    except (SyntaxError, ValueError, RecursionError) as exc:
        errors.append({"path": str(path), "error": str(exc)})
    entry["sha256_after"] = sha(path)
    entry["stable"] = before == entry["sha256_after"]
    sources.append(entry)
review = []
for row in reserve:
    preexisting = training[row["id"]]["overlap"] or prior[row["id"]]["freshness_review"] == "known_exposure"
    review.append({"id": row["id"], "ordinal": row["ordinal"], "language": row["language_semantic"], "complete_original": training[row["id"]]["complete_original"], "context_needed": row["original_context_needed"], "preexisting_exposure": preexisting, "orthographic_matches": sorted(hits[row["id"]]), "remaining_candidate": not preexisting and not hits[row["id"]], "certified_fresh": False, "frozen": False, "replayed": False})
(OUT / "review.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in review), encoding="utf-8")
dump(OUT / "sources.json", sources)
dump(OUT / "errors.json", errors)
remaining = [r for r in review if r["remaining_candidate"]]
summary = {"source_count": len(sources), "stable_sources": sum(r["stable"] for r in sources), "unresolved_source_issues": len(errors), "reserve_count": 204, "additional_exposed": sum(not r["preexisting_exposure"] and bool(r["orthographic_matches"]) for r in review), "remaining": len(remaining), "remaining_complete_original": sum(r["complete_original"] for r in remaining), "remaining_languages": dict(Counter(r["language"] for r in remaining)), "remaining_complete_languages": dict(Counter(r["language"] for r in remaining if r["complete_original"])), "remaining_complete_context_flags": sum(bool(r["context_needed"]) for r in remaining if r["complete_original"]), "private": str(OUT), "review_sha256": sha(OUT / "review.jsonl"), "sources_sha256": sha(OUT / "sources.json"), "certified_fresh": 0, "frozen": False, "replayed": 0, "limits": "Conservative orthographic exclusion only; context, semantic overlap and previously declared extraction limitations still require adjudication. No BAXY inference or effects."}
dump(ART / "RESULT.json", summary)
print(json.dumps(summary, ensure_ascii=False))
