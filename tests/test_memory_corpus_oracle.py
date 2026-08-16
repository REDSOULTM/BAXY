from __future__ import annotations

import hashlib
import json
import re
import unittest
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data"
ORACLE_PATH = DATA / "memory_corpus_oracle.json"
CORPUS_PATH = DATA / "historical_messages.jsonl"


def normalize_literal(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.casefold()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def ids_digest(ids: list[str] | set[str]) -> str:
    payload = "".join(f"{message_id}\n" for message_id in sorted(ids))
    return sha256_bytes(payload.encode("utf-8"))


def records_digest(ids: list[str] | set[str], corpus: dict[str, dict]) -> str:
    payload = "".join(
        f"{message_id}\t{normalize_literal(corpus[message_id]['text_literal'])}\n"
        for message_id in sorted(ids)
    )
    return sha256_bytes(payload.encode("utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


class MemoryCorpusOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.oracle = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
        rows = read_jsonl(CORPUS_PATH)
        cls.corpus = {row["message_id"]: row for row in rows}
        if len(cls.corpus) != len(rows):
            raise AssertionError("historical_messages.jsonl contains duplicate IDs")

    def test_oracle_is_bound_to_the_frozen_corpus_and_normalization(self) -> None:
        self.assertEqual(self.oracle["schema_version"], 1)
        self.assertEqual(self.oracle["oracle_id"], "baxy.memory.explicit-local.v1")
        self.assertEqual(
            self.oracle["corpus"],
            {
                "path": "tests/data/historical_messages.jsonl",
                "sha256": (
                    "9d8b2d095dcd0bafb9d2a7bb616876b34b6b0321d53597211c37a26473ac436e"
                ),
            },
        )
        self.assertEqual(
            sha256_bytes(CORPUS_PATH.read_bytes()), self.oracle["corpus"]["sha256"]
        )
        self.assertEqual(
            self.oracle["normalization"]["order"],
            [
                "unicode_nfc",
                "collapse_whitespace",
                "trim",
                "unicode_casefold",
            ],
        )
        self.assertEqual(normalize_literal("  CAFE\u0301\t\nAZUL  "), "café azul")

    def test_declared_groups_have_exact_counts_and_digests(self) -> None:
        for name in ("save", "recall", "forget", "correct", "hard_negative"):
            with self.subTest(group=name):
                group = self.oracle["groups"][name]
                ids = group["ids"]
                self.assertEqual(len(ids), group["count"])
                self.assertEqual(len(ids), len(set(ids)))
                self.assertTrue(set(ids).issubset(self.corpus))
                self.assertEqual(ids_digest(ids), group["ids_sha256"])
                self.assertEqual(
                    records_digest(ids, self.corpus), group["records_sha256"]
                )

                rows = [self.corpus[message_id] for message_id in ids]
                normalized_literals = {
                    normalize_literal(row["text_literal"]) for row in rows
                }
                self.assertEqual(
                    len(normalized_literals), group["normalized_literal_count"]
                )
                self.assertEqual(
                    len({row["canonical_mission_id"] for row in rows}),
                    group["mission_count"],
                )
                self.assertEqual(
                    len({row["source"] for row in rows}), group["source_count"]
                )
                for literal in normalized_literals:
                    self.assertTrue(unicodedata.is_normalized("NFC", literal))
                    self.assertEqual(literal, literal.casefold())
                    self.assertEqual(literal, literal.strip())
                    self.assertIsNone(re.search(r"\s{2,}", literal))

    def test_positive_union_has_stable_identity_and_no_cross_route_overlap(self) -> None:
        groups = self.oracle["groups"]
        union = groups["positive_union"]
        members = [set(groups[name]["ids"]) for name in union["members"]]

        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                self.assertFalse(left & right)

        positive = set().union(*members)
        self.assertEqual(len(positive), union["count"])
        self.assertEqual(ids_digest(positive), union["ids_sha256"])
        self.assertEqual(records_digest(positive, self.corpus), union["records_sha256"])
        self.assertEqual(
            len(
                {
                    normalize_literal(self.corpus[message_id]["text_literal"])
                    for message_id in positive
                }
            ),
            union["normalized_literal_count"],
        )

        hard_negative = set(groups["hard_negative"]["ids"])
        self.assertFalse(positive & hard_negative)

        correction = set(groups["correct"]["ids"])
        self.assertEqual(
            correction & hard_negative, {"msg_f98a7dee0392ad997fd5"}
        )

    def test_canonical_cases_cover_every_positive_and_correction_once(self) -> None:
        cases = self.oracle["canonical_cases"]
        groups = self.oracle["groups"]
        required_arguments = {
            "memory.save": {"selector", "value", "kind", "retention"},
            "memory.recall": {"scope", "selector"},
            "memory.forget": {"scope", "selector", "confirmation"},
            "memory.correct": {"selector", "value", "retention"},
        }

        for group_name in ("save", "recall", "forget", "correct"):
            operation = groups[group_name]["operation"]
            covered = [
                message_id
                for case in cases
                if case["operation"] == operation
                for message_id in case["ids"]
            ]
            with self.subTest(group=group_name):
                self.assertEqual(len(covered), len(set(covered)))
                self.assertEqual(set(covered), set(groups[group_name]["ids"]))

        for case in cases:
            operation = case["operation"]
            self.assertIn(operation, required_arguments)
            self.assertTrue(case["ids"])
            self.assertTrue(
                required_arguments[operation].issubset(case["arguments"]),
                case,
            )

        serialized = ORACLE_PATH.read_text(encoding="utf-8").casefold()
        self.assertNotIn("sk-12345", serialized)
        self.assertNotIn('"value": "1234"', serialized)

    def test_hard_negative_taxonomy_is_complete_and_machine_readable(self) -> None:
        expected = set(self.oracle["groups"]["hard_negative"]["ids"])
        cases = self.oracle["hard_negative_cases"]
        categories = [case["category"] for case in cases]
        covered = [message_id for case in cases for message_id in case["ids"]]

        self.assertEqual(len(categories), len(set(categories)))
        self.assertEqual(len(covered), len(set(covered)))
        self.assertEqual(set(covered), expected)
        for case in cases:
            self.assertTrue(case["ids"])
            self.assertIsInstance(case["expected"].get("outcome"), str)

    def test_ttl_consent_and_inspection_contracts_reference_curated_rows(self) -> None:
        contracts = self.oracle["behavioral_contracts"]
        self.assertEqual(set(contracts), {"ttl", "consent", "inspection"})

        groups = self.oracle["groups"]
        curated = set().union(
            groups["save"]["ids"],
            groups["recall"]["ids"],
            groups["forget"]["ids"],
            groups["correct"]["ids"],
            groups["hard_negative"]["ids"],
        )
        for section_name, section in contracts.items():
            self.assertTrue(section, section_name)
            names = [case["name"] for case in section]
            self.assertEqual(len(names), len(set(names)), section_name)
            for case in section:
                self.assertTrue(set(case["ids"]).issubset(curated), case["name"])
                self.assertTrue(case["expected"], case["name"])

        export = next(
            case
            for case in contracts["inspection"]
            if case["name"] == "export_has_no_frozen_literal_in_this_oracle"
        )
        self.assertEqual(export["ids"], [])
        self.assertEqual(export["expected"]["status"], "product_requirement_only")


if __name__ == "__main__":
    unittest.main()
