"""Scan complete evidence_assets ledgers for terminals, metrics, ranking."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.goal095_evidence_ledger import TERMINALS, load_json, queue_paths

RANKING = ("best model", "modelo mejor", "mejor modelo")
METRIC_FIELDS = ("corpus", "denominator", "version", "hardware", "limitations")


def main() -> int:
    _batches, ledger_path, _ = queue_paths(REPO)
    queue = load_json(ledger_path)
    terminals: Counter[str] = Counter()
    parse_missing_extract = 0
    binary_missing = 0
    dup_missing = 0
    excl_missing = 0
    ranking_bad = 0
    metric_missing = 0
    works_true = 0
    failed_preserved = 0
    negative_cards = 0
    contamination_cards = 0
    complete = 0
    for item in queue["batches"]:
        if item.get("kind") != "evidence_assets" or item.get("status") != "complete":
            continue
        complete += 1
        path = REPO / "artifacts" / "goal095" / "ledger" / f"{item['batch_id']}.json"
        led = load_json(path)
        for row in led.get("files") or []:
            term = row.get("terminal")
            terminals[term or "?"] += 1
            if term == "parseado_completo" and not row.get("extract_ref"):
                parse_missing_extract += 1
            if term == "binario_inventariado" and (
                not row.get("binary_format") or not row.get("extract_ref")
            ):
                binary_missing += 1
            if term == "duplicado_por_hash" and not row.get("duplicate_of"):
                dup_missing += 1
            if term == "excluido_razonado" and not row.get("exclusion_rule"):
                excl_missing += 1
            if term not in TERMINALS:
                pass
        for card in led.get("cards") or []:
            blob = json.dumps(card, ensure_ascii=False).casefold()
            if any(n in blob for n in RANKING) and not card.get("equivalent_comparison"):
                ranking_bad += 1
            if any(not card.get(field) for field in METRIC_FIELDS):
                metric_missing += 1
            if card.get("works") is True:
                works_true += 1
            if card.get("outcome") in {"fracaso", "negativo"}:
                failed_preserved += 1
            if card.get("card_kind") == "negative":
                negative_cards += 1
            if card.get("card_kind") == "contamination":
                contamination_cards += 1
    payload = {
        "complete_ledgers": complete,
        "terminals": dict(terminals),
        "bad_terminals": [k for k in terminals if k not in TERMINALS],
        "parseado_completo_missing_extract": parse_missing_extract,
        "binario_missing_fields": binary_missing,
        "duplicado_missing_of": dup_missing,
        "excluido_missing_rule": excl_missing,
        "ranking_without_comparison": ranking_bad,
        "metric_cards_missing_fields": metric_missing,
        "works_true": works_true,
        "failed_or_negative_cards": failed_preserved,
        "negative_cards": negative_cards,
        "contamination_cards": contamination_cards,
    }
    print(json.dumps(payload, indent=2), flush=True)
    bad = (
        parse_missing_extract
        or binary_missing
        or dup_missing
        or excl_missing
        or ranking_bad
        or metric_missing
        or works_true
        or payload["bad_terminals"]
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
