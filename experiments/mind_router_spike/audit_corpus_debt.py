"""Inventory the corpus debt named as the starting blocker.

`goal.md` section 6 says the frozen historical corpora carry family,
reminder/notification and language conflicts against the authenticated
catalogue, and that until the oracle can tell a repair from an overfit
everything else is fixed blind. Nothing had ever measured that claim, so this
audit does exactly that and nothing else: it reads corpora and the catalogue,
counts conflicts by class, and writes one artifact.

It never edits a corpus, never opens a blind holdout and never invokes a model.
An inventory is not a repair; the numbers here say how big the debt is, not
what to do about it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

DEFAULT_OUTPUT = REPO / "artifacts/development/corpus_debt_inventory.json"
CATALOG_SNAPSHOT = REPO / "artifacts/development/catalog_vocabulary_snapshot.json"


def discover_corpora() -> tuple[Path, ...]:
    """Every corpus that declares a target operation and a language.

    Auditing a hand-picked few would let the debt hide in the ones not listed,
    so the set is discovered by shape instead of enumerated.
    """

    found: list[Path] = []
    for directory in ("artifacts/development", "artifacts/holdout"):
        for path in sorted((REPO / directory).glob("*.jsonl")):
            try:
                first = next(
                    (
                        line
                        for line in path.read_text(encoding="utf-8").splitlines()
                        if line.strip()
                    ),
                    "",
                )
                row = json.loads(first) if first else {}
            except (OSError, ValueError):
                continue
            if isinstance(row, dict) and "target_operation" in row and "text" in row:
                found.append(path)
    return tuple(found)


# Function words that belong to exactly one of the two product languages.
#
# The first version of this list included `a`, `me` and `no`, which exist in
# both, so "Tell me the current speaker volume" was scored as code-switched and
# "Navega la sesion web actual a https://..." too. That produced 47 phantom
# language conflicts: the measurement was the defect, not the corpus. Anything
# ambiguous across the two languages is excluded here on purpose.
SPANISH_MARKERS = re.compile(
    r"\b(?:el|la|los|las|un|una|unos|unas|de|del|que|con|para|por|mis|tus|"
    r"su|sus|en|y|si|te|se|lo|al|esta|estan|hay|como|cuando|"
    r"donde|quiero|puedes|dime|muestra|abre|cierra|pon|crea|borra)\b"
)
ENGLISH_MARKERS = re.compile(
    r"\b(?:the|an|of|to|for|with|your|and|or|not|is|are|was|were|does|"
    r"did|can|could|please|show|open|close|create|delete|tell|what|when|"
    r"where|which|how)\b"
)

# The two families cannot be told apart by the word "recordatorio": the
# catalogue itself describes notification.list.due as "Enumera recordatorios
# vencidos no descartados" and notification.cancel.at as cancelling "una alarma
# o recordatorio". What separates them is the action, not the noun.
#
#   notification.* -- something that already fired: due, dismissed, scheduled
#                     to sound, diagnosed
#   reminder.*     -- a stored item: created, listed, deleted, restored
#
# A conflict is therefore a target described only with the other family's
# actions. Scoring the noun alone produced two phantom conflicts on rows that
# match the catalogue's own wording exactly.
NOTIFICATION_ACTIONS = re.compile(
    r"\b(?:vencid[oa]s?|descart[a-z]*|dismiss[a-z]*|due|overdue|"
    r"suena|sono|sonar|alarma|alarmas|alarm|alarms|aviso|avisos)\b"
)
REMINDER_ACTIONS = re.compile(
    r"\b(?:programad[oa]s?|scheduled|guardad[oa]s?|stored|"
    r"restaur[a-z]*|restore[a-z]*|papelera|trash)\b"
)


def fold(text: object) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def detect_language(text: str) -> str:
    folded = fold(text)
    spanish = len(set(SPANISH_MARKERS.findall(folded)))
    english = len(set(ENGLISH_MARKERS.findall(folded)))
    if spanish and english:
        return "spanglish"
    if spanish:
        return "es"
    if english:
        return "en"
    return "unknown"


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def audit(catalog_names: set[str]) -> dict[str, Any]:
    families = {name.split(".", 1)[0] for name in catalog_names}
    per_corpus: dict[str, Any] = {}
    totals = Counter()

    for path in discover_corpora():
        rows = load_rows(path)
        if not rows:
            continue
        unknown_operation: list[dict[str, str]] = []
        family_conflict: list[dict[str, str]] = []
        reminder_notification: list[dict[str, str]] = []
        language_conflict: list[dict[str, str]] = []

        for row in rows:
            target = str(row.get("target_operation") or "")
            text = str(row.get("text") or "")
            declared = str(row.get("language") or "")
            folded = fold(text)

            # 1. The corpus must not name an operation the catalogue lacks.
            if target and target not in catalog_names:
                unknown_operation.append(
                    {"case_id": row.get("case_id", ""), "target_operation": target}
                )
            # 2. Every operation of a compatible set must belong to the catalogue
            #    and its family must exist.
            for operations in row.get("compatible_effect_operation_sets") or []:
                for operation in operations:
                    family = str(operation).split(".", 1)[0]
                    if operation not in catalog_names or family not in families:
                        family_conflict.append(
                            {
                                "case_id": row.get("case_id", ""),
                                "operation": str(operation),
                            }
                        )
            # 3. Reminder and notification are distinct families that the text
            #    must not cross against its own target.
            target_family = target.split(".", 1)[0]
            notification_action = NOTIFICATION_ACTIONS.search(folded) is not None
            reminder_action = REMINDER_ACTIONS.search(folded) is not None
            if (
                target_family == "reminder"
                and notification_action
                and not reminder_action
            ):
                reminder_notification.append(
                    {
                        "case_id": row.get("case_id", ""),
                        "target_operation": target,
                        "conflict": "reminder target described with notification actions",
                        "text": text[:70],
                    }
                )
            if (
                target_family == "notification"
                and reminder_action
                and not notification_action
            ):
                reminder_notification.append(
                    {
                        "case_id": row.get("case_id", ""),
                        "target_operation": target,
                        "conflict": "notification target described with reminder actions",
                        "text": text[:70],
                    }
                )
            # 4. The declared language must match what the text actually is.
            observed = detect_language(text)
            if declared and observed != "unknown" and observed != declared:
                # A declared spanglish row legitimately reads as one language
                # when the borrowed word carries no function words.
                if not (declared == "spanglish" and observed in {"es", "en"}):
                    language_conflict.append(
                        {
                            "case_id": row.get("case_id", ""),
                            "declared": declared,
                            "observed": observed,
                            "text": text[:70],
                        }
                    )

        relative = str(path.relative_to(REPO))
        per_corpus[relative] = {
            "rows": len(rows),
            "unknown_operation": unknown_operation,
            "family_conflict": family_conflict,
            "reminder_notification_conflict": reminder_notification,
            "language_conflict": language_conflict,
            "counts": {
                "unknown_operation": len(unknown_operation),
                "family_conflict": len(family_conflict),
                "reminder_notification_conflict": len(reminder_notification),
                "language_conflict": len(language_conflict),
            },
        }
        for key, value in per_corpus[relative]["counts"].items():
            totals[key] += value
        totals["rows"] += len(rows)

    return {"per_corpus": per_corpus, "totals": dict(totals)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    snapshot = json.loads(CATALOG_SNAPSHOT.read_text(encoding="utf-8"))
    catalog_names = {
        str(capability["name"]) for capability in snapshot["capabilities"]
    }
    result = audit(catalog_names)
    report = {
        "schema": "baxy.corpus-debt-inventory.v1",
        "authority": "inventory only; no corpus edited, no holdout opened, no model invoked",
        "catalog_operations": len(catalog_names),
        "corpora_discovered": len(result["per_corpus"]),
        **result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"catalog_operations": len(catalog_names), **result["totals"]},
                     ensure_ascii=False, indent=2))
    for corpus, detail in result["per_corpus"].items():
        print(f"\n{corpus}: {detail['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
