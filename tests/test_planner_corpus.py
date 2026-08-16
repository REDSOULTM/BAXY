from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MISSIONS = ROOT / "tests" / "data" / "historical_missions.jsonl"
CATALOG = ROOT / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs"
AUDIT = ROOT / "artifacts" / "planner_recovery" / "historical_compound_audit.json"
FULL_AUDIT = (
    ROOT / "artifacts" / "planner_recovery" / "historical_user_mission_audit.json"
)


class PlannerCorpusContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [
            json.loads(line)
            for line in MISSIONS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        source = CATALOG.read_text(encoding="utf-8")
        cls.catalog_names = set(re.findall(r'Descriptor\(\s*"([a-z0-9.]+)"', source))

    def test_historical_human_multipass_shape_is_frozen(self):
        human = [row for row in self.rows if row["class"] == "user_mission"]
        multi = [row for row in human if len(row.get("operations") or []) >= 2]

        self.assertEqual(len(human), 263)
        self.assertEqual(len(multi), 166)
        self.assertEqual(max(len(row["operations"]) for row in multi), 15)
        self.assertLessEqual(max(len(row["operations"]) for row in multi), 16)

    def test_every_non_private_historical_family_has_a_public_planning_primitive(self):
        multi = [
            row
            for row in self.rows
            if row["class"] == "user_mission"
            and len(row.get("operations") or []) >= 2
        ]
        catalog_families = {name.split(".", 1)[0] for name in self.catalog_names}
        missing = set()
        for row in multi:
            for operation in row["operations"]:
                family = operation.split(".", 1)[0]
                if family != "memory" and family not in catalog_families:
                    missing.add(operation)

        self.assertEqual(missing, set())

    def test_private_memory_compound_plans_remain_an_explicit_separate_boundary(self):
        private_compound = [
            row
            for row in self.rows
            if row["class"] == "user_mission"
            and len(row.get("operations") or []) >= 2
            and any(op.startswith("memory.") for op in row["operations"])
        ]
        mixed = [
            row
            for row in private_compound
            if any(not operation.startswith("memory.") for operation in row["operations"])
        ]

        # Estos casos no autorizan exponer memory.* al LLM. El parser/envelope
        # privado debe resolver esa rama antes del planner general.
        self.assertEqual(len(private_compound), 14)
        self.assertEqual(len(mixed), 12)

    def test_all_166_compounds_have_a_frozen_honest_classification(self):
        report = json.loads(AUDIT.read_text(encoding="utf-8"))
        missions = report["missions"]
        self.assertEqual(len(missions), 166)
        self.assertEqual(
            len({item["mission_id"] for item in missions}),
            166,
        )
        self.assertEqual(
            {item["classification"] for item in missions},
            {"natural_evaluable", "contaminated_trace", "private_boundary"},
        )
        self.assertTrue(report["summary"]["all_within_planner_limit"])
        self.assertEqual(report["summary"]["missions_missing_public_family"], 0)
        self.assertEqual(
            sum(report["summary"]["classification_counts"].values()),
            166,
        )

    def test_every_historical_user_mission_is_accounted_once(self):
        report = json.loads(FULL_AUDIT.read_text(encoding="utf-8"))
        missions = report["missions"]
        summary = report["summary"]

        self.assertEqual(len(missions), 263)
        self.assertEqual(len({item["mission_id"] for item in missions}), 263)
        self.assertTrue(summary["all_accounted_once"])
        self.assertEqual(summary["product_acceptance_rows"], 218)
        self.assertEqual(summary["trace_only_rows"], 45)
        self.assertEqual(sum(summary["classification_counts"].values()), 263)
        self.assertEqual(summary["missions_missing_public_family"], 0)
        self.assertEqual(summary["tools_executed"], 0)
        self.assertEqual(
            set(summary["classification_counts"]),
            {
                "contaminated_trace",
                "natural_evaluable",
                "private_boundary",
                "trace_only",
            },
        )

    def test_full_audit_never_replays_private_or_contaminated_text(self):
        report = json.loads(FULL_AUDIT.read_text(encoding="utf-8"))
        for item in report["missions"]:
            if item["classification"] == "natural_evaluable":
                objective = item["representative_objective"]
                self.assertIsInstance(objective, str)
                self.assertLessEqual(len(objective), 512)
                self.assertTrue(item["representative_detected_families"])
                self.assertNotIn("memory", item["representative_detected_families"])
            else:
                self.assertIsNone(item["representative_objective"])

    def test_full_audit_is_bound_to_the_exact_frozen_corpus(self):
        report = json.loads(FULL_AUDIT.read_text(encoding="utf-8"))
        self.assertEqual(
            report["source_sha256"],
            hashlib.sha256(MISSIONS.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
