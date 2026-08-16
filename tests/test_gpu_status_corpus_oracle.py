from __future__ import annotations

import hashlib
import json
import re
import unittest
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data"
ORACLE_PATH = DATA / "gpu_status_corpus_oracle.json"
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


class GpuStatusCorpusOracleTests(unittest.TestCase):
    FROZEN_GROUP_CONTRACTS = {
        "identity_historical": (
            "system.status",
            "gpu_identity",
            "9695f791cf890a0eddba9e94039abb39098945df437fdb12a79184c4e3892b70",
            "d30495b914722a4e150b31c576e7a53800d4fe5a286908b79a2f6d4bbc33658a",
        ),
        "identity_semantic_repair": (
            "system.status",
            "gpu_identity",
            "996a2d682c3baaeaa056e96db9a11d9a2c4ee4b89d8fafa12d8f11729ee557ad",
            "3fc67c6031eb13bf80c873f1960e08ced0cf5e73a0a7b893a38e5787c651b71d",
        ),
        "usage_semantic_repair": (
            "system.status",
            "gpu_usage",
            "f8ed8c44451adaa7a17464f81844e8eb7d2dbd348f97b14f3e6355c604ca6807",
            "68b57c1f747fb6bb863dac2fe75555a0985a9de8faf9eac9d4e201af628c4837",
        ),
        "usage_historical": (
            "system.status",
            "gpu_usage",
            "4141bea579e0c3180861a9cf130ebfbd78c1fc53465b8bef5b5009c04635b542",
            "a617d664f56b0fb2045b47936a32f868df496caad0e48476ce0ec6961318debf",
        ),
        "usage_bounded_alias": (
            "system.status",
            "gpu_usage",
            "ddfe566be528a212326c7e382615dc2cfd3cd166a9ec2e55ab7d31f89f934c19",
            "5c7cf387af1ad2badd97e46dc222dccf82798a7128ca3e1acb9e8a9c33a6e4e4",
        ),
        "composition": (
            None,
            None,
            "d3c640324b210ec2ad0475648dd4e7a6b22c01bd5585c5c9767701661a667643",
            "c7dff98d56bdbb61a1f2fa00235d7155958a24dcc5e0145cc03852dd1a40f97b",
        ),
        "hard_negative": (
            None,
            None,
            "481280cb9d3e3978ac34cbbb5a849226a17c54247480c369fea6068af98275c6",
            "4cff5e3572cba6aa6aaba8e1369880644115d0fab54b47cf8e8afdf7096a0c39",
        ),
        "trace_only": (
            "system.status",
            None,
            "e7d123c0eb96637e9aab0d4bd488f9b4117f50a7565b5ab33804b9ec748276f3",
            "dbba8acb099e5311b611866edbac704cfbdacce20bd53b34af2d8176790a895d",
        ),
    }
    FROZEN_VIRTUAL_DIGESTS = {
        "positive_union": (
            "61d2265b499313c85e30d84e207ec462a0e166d4f88352549c1456f8d80335e4",
            "36ec73ee52e75f856a10dc4fdca8aa6868015b6f3af1eb1d202303ddd4ef171e",
        ),
        "selected_universe": (
            "d67a8156f8cd5db417c1318a28ab900150b162e05104e197d60a921e454f2065",
            "4f7b212bdca9f4920ebf71a180470b2c4d61a82e823f415d18740f11dd611285",
        ),
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.oracle = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
        rows = read_jsonl(CORPUS_PATH)
        cls.corpus = {row["message_id"]: row for row in rows}
        if len(cls.corpus) != len(rows):
            raise AssertionError("historical_messages.jsonl contains duplicate IDs")

    def test_oracle_is_bound_to_frozen_corpus_and_normalization(self) -> None:
        self.assertEqual(self.oracle["schema_version"], 1)
        self.assertEqual(
            self.oracle["oracle_id"], "baxy.system-status.gpu-local.v1"
        )
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
        self.assertEqual(normalize_literal("  GPU\t\nCAFE\u0301  "), "gpu café")

    def test_declared_groups_have_exact_counts_metadata_and_digests(self) -> None:
        explicit_groups = (
            "identity_historical",
            "identity_semantic_repair",
            "usage_semantic_repair",
            "usage_historical",
            "usage_bounded_alias",
            "composition",
            "hard_negative",
            "trace_only",
        )
        for name in explicit_groups:
            with self.subTest(group=name):
                group = self.oracle["groups"][name]
                expected_operation, expected_scope, expected_ids, expected_records = (
                    self.FROZEN_GROUP_CONTRACTS[name]
                )
                self.assertEqual(group["operation"], expected_operation)
                self.assertEqual(group.get("scope"), expected_scope)
                self.assertEqual(group["ids_sha256"], expected_ids)
                self.assertEqual(group["records_sha256"], expected_records)
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

    def test_positive_union_and_selected_universe_are_exact_and_disjoint(self) -> None:
        groups = self.oracle["groups"]
        positive_group = groups["positive_union"]
        positive_members = [set(groups[name]["ids"]) for name in positive_group["members"]]
        for index, left in enumerate(positive_members):
            for right in positive_members[index + 1 :]:
                self.assertFalse(left & right)

        positive = set().union(*positive_members)
        self.assertEqual(
            (positive_group["ids_sha256"], positive_group["records_sha256"]),
            self.FROZEN_VIRTUAL_DIGESTS["positive_union"],
        )
        self._assert_virtual_group(positive_group, positive)

        composition = set(groups["composition"]["ids"])
        hard_negative = set(groups["hard_negative"]["ids"])
        self.assertFalse(positive & composition)
        self.assertFalse(positive & hard_negative)
        self.assertFalse(composition & hard_negative)

        selected = positive | composition | hard_negative
        selected_group = groups["selected_universe"]
        self.assertEqual(
            selected_group["members"],
            ["positive_union", "composition", "hard_negative"],
        )
        self.assertEqual(
            (selected_group["ids_sha256"], selected_group["records_sha256"]),
            self.FROZEN_VIRTUAL_DIGESTS["selected_universe"],
        )
        self._assert_virtual_group(selected_group, selected)

    def test_positive_provenance_and_semantic_repairs_are_explicit(self) -> None:
        groups = self.oracle["groups"]
        for name in ("identity_historical", "usage_historical"):
            for message_id in groups[name]["ids"]:
                row = self.corpus[message_id]
                self.assertEqual(row["acceptance_scope"], "product_1_0")
                self.assertEqual(row["class"], "user_mission")
                self.assertEqual(row["operations"], ["system.status"])

        for repair_name in (
            "identity_semantic_repair",
            "usage_semantic_repair",
        ):
            repairs = groups[repair_name]
            self.assertEqual(
                repairs["label_state"], "semantic_positive_historically_unmapped"
            )
            for message_id in repairs["ids"]:
                row = self.corpus[message_id]
                self.assertEqual(row["acceptance_scope"], "product_1_0")
                self.assertEqual(row["class"], "conversation_question")
                self.assertEqual(row["operations"], [])

        aliases = groups["usage_bounded_alias"]
        self.assertEqual(aliases["label_state"], "bounded_summary_resolution")
        for message_id in aliases["ids"]:
            row = self.corpus[message_id]
            self.assertEqual(row["acceptance_scope"], "product_1_0")
            self.assertIn(row["class"], {"conversation_question", "user_mission"})
            self.assertIn(row["operations"], [[], ["system.status"]])

    def test_canonical_cases_cover_every_positive_once_with_exact_scope(self) -> None:
        groups = self.oracle["groups"]
        cases = self.oracle["canonical_cases"]
        covered = [message_id for case in cases for message_id in case["ids"]]
        positive = set().union(
            *(set(groups[name]["ids"]) for name in groups["positive_union"]["members"])
        )
        self.assertEqual(len(covered), len(set(covered)))
        self.assertEqual(set(covered), positive)

        expected_scope = {
            message_id: self.FROZEN_GROUP_CONTRACTS[name][1]
            for name in (
                "identity_historical",
                "identity_semantic_repair",
                "usage_semantic_repair",
                "usage_historical",
                "usage_bounded_alias",
            )
            for message_id in groups[name]["ids"]
        }
        for case in cases:
            self.assertIn(case["scope"], {"gpu_identity", "gpu_usage"})
            self.assertTrue(case["ids"])
            for message_id in case["ids"]:
                self.assertEqual(case["scope"], expected_scope[message_id])

    def test_boundary_taxonomies_are_complete_and_machine_readable(self) -> None:
        groups = self.oracle["groups"]
        for cases_name, group_name in (
            ("composition_cases", "composition"),
            ("hard_negative_cases", "hard_negative"),
        ):
            with self.subTest(cases=cases_name):
                cases = self.oracle[cases_name]
                categories = [case["category"] for case in cases]
                covered = [message_id for case in cases for message_id in case["ids"]]
                self.assertEqual(len(categories), len(set(categories)))
                self.assertEqual(len(covered), len(set(covered)))
                self.assertEqual(set(covered), set(groups[group_name]["ids"]))
                self.assertTrue(all(case["ids"] for case in cases))

    def test_provider_neutral_alias_and_scope_isolation_are_frozen(self) -> None:
        contracts = self.oracle["behavioral_contracts"]
        alias = contracts["provider_neutral_nvidia_smi_alias"]
        usage_ids = set(self.oracle["groups"]["usage_semantic_repair"]["ids"])
        usage_ids |= set(self.oracle["groups"]["usage_historical"]["ids"])
        usage_ids |= set(self.oracle["groups"]["usage_bounded_alias"]["ids"])
        self.assertEqual(len(alias["ids"]), 7)
        self.assertTrue(set(alias["ids"]).issubset(usage_ids))
        self.assertEqual(alias["expected"]["operation"], "system.status")
        self.assertEqual(alias["expected"]["scope"], "gpu_usage")
        self.assertTrue(alias["expected"]["must_not_claim_nvidia_smi_execution"])
        self.assertTrue(alias["expected"]["must_not_spawn_a_subprocess"])
        self.assertEqual(alias["contract_origin"], "architecture_decision_preserving_the_requested_outcome")
        self.assertEqual(len(alias["historical_terminal_hint_ids"]), 4)
        self.assertTrue(
            set(alias["historical_terminal_hint_ids"]).issubset(alias["ids"])
        )

        self.assertEqual(
            set(contracts["excluded_metrics"]),
            {"temperature", "power_fan_clocks", "process_attribution", "continuous_monitoring"},
        )
        isolation = contracts["summary_isolation"]["expected"]
        self.assertFalse(isolation["generic_summary_includes_gpu"])
        self.assertFalse(isolation["gpu_identity_collects_usage"])
        self.assertTrue(isolation["gpu_usage_is_point_in_time"])
        self.assertEqual(
            set(contracts["boundary_semantics"]), {"msg_f9b7fc6890f8b020d3b1"}
        )

    def test_selection_is_explicitly_curated_not_exhaustive(self) -> None:
        selection = self.oracle["selection"]
        self.assertEqual(selection["acceptance_scope"], "product_1_0")
        self.assertEqual(selection["lexical_regex"], r"(?i)\b(?:gpu|vram|nvidia-smi)\b")
        self.assertEqual(
            selection["lexical_candidate_classes"],
            ["user_mission", "conversation_question", "feedback_failure"],
        )
        pattern = re.compile(selection["lexical_regex"])
        candidates = {
            message_id
            for message_id, row in self.corpus.items()
            if row["acceptance_scope"] == selection["acceptance_scope"]
            and row["class"] in selection["lexical_candidate_classes"]
            and pattern.search(row["text_literal"])
        }
        self.assertEqual(selection["lexical_candidate_count"], 148)
        self.assertEqual(selection["lexical_candidate_normalized_literal_count"], 125)
        self.assertEqual(selection["selected_lexical_candidate_count"], 74)
        self.assertEqual(selection["selected_temperature_collision_count"], 3)
        self.assertEqual(selection["selected_total_count"], 77)
        self.assertFalse(selection["is_exhaustive_lexical_inventory"])
        self.assertEqual(len(candidates), selection["lexical_candidate_count"])
        self.assertEqual(ids_digest(candidates), selection["lexical_candidate_ids_sha256"])
        self.assertEqual(
            records_digest(candidates, self.corpus),
            selection["lexical_candidate_records_sha256"],
        )
        self.assertEqual(
            len(
                {
                    normalize_literal(self.corpus[message_id]["text_literal"])
                    for message_id in candidates
                }
            ),
            selection["lexical_candidate_normalized_literal_count"],
        )
        groups = self.oracle["groups"]
        selected = set().union(
            *(set(groups[name]["ids"]) for name in groups["positive_union"]["members"]),
            set(groups["composition"]["ids"]),
            set(groups["hard_negative"]["ids"]),
        )
        collisions = set(selection["selected_temperature_collision_ids"])
        self.assertEqual(len(selected & candidates), 74)
        self.assertEqual(selected - candidates, collisions)
        self.assertEqual(len(collisions), selection["selected_temperature_collision_count"])
        self.assertEqual(
            selection["lexical_candidate_ids_sha256"],
            "fde1d597ceec751d130005ca2a4d42e131ff1f46e39dcfaeff7ea25e45e91ea8",
        )
        self.assertEqual(
            selection["lexical_candidate_records_sha256"],
            "9aba2fe4d873ce6582f8f9803c0b8f26b255776c9bf2d92d8c835e378c285179",
        )

    def test_trace_rows_remain_outside_product_acceptance(self) -> None:
        trace = self.oracle["groups"]["trace_only"]
        self.assertIsNone(trace["scope"])
        for message_id in trace["ids"]:
            row = self.corpus[message_id]
            self.assertEqual(
                row["acceptance_scope"], "trace_only_not_acceptance_commitment"
            )
            self.assertEqual(row["class"], "user_mission")
            self.assertEqual(row["operations"], ["system.status"])

    def _assert_virtual_group(self, group: dict, ids: set[str]) -> None:
        self.assertEqual(len(ids), group["count"])
        self.assertEqual(ids_digest(ids), group["ids_sha256"])
        self.assertEqual(records_digest(ids, self.corpus), group["records_sha256"])
        rows = [self.corpus[message_id] for message_id in ids]
        self.assertEqual(
            len({normalize_literal(row["text_literal"]) for row in rows}),
            group["normalized_literal_count"],
        )
        self.assertEqual(
            len({row["canonical_mission_id"] for row in rows}),
            group["mission_count"],
        )
        self.assertEqual(len({row["source"] for row in rows}), group["source_count"])


if __name__ == "__main__":
    unittest.main()
