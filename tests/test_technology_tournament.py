from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "artifacts" / "technology_tournament" / "protocol.json"
CASES_PATH = ROOT / "experiments" / "technology_tournament" / "cases.json"
RESULTS_PATH = ROOT / "artifacts" / "technology_tournament" / "raw" / "round_a_results.json"
PACKAGING_PATH = ROOT / "artifacts" / "technology_tournament" / "raw" / "packaging_results.json"
SCORECARD_PATH = ROOT / "artifacts" / "technology_tournament" / "round_a_scorecard.json"
ROUND_B_SCORECARD_PATH = (
    ROOT / "artifacts" / "technology_tournament" / "round_b_scorecard.json"
)
ROUND_B_SUPPLY_PATH = (
    ROOT
    / "artifacts"
    / "technology_tournament"
    / "raw"
    / "round_b_supply_chain.json"
)
ROUND_B_REPRODUCIBILITY_PATH = (
    ROOT
    / "artifacts"
    / "technology_tournament"
    / "raw"
    / "round_b_reproducibility.json"
)
ROUND_B_FUNCTIONAL_HARNESS_PATH = (
    ROOT / "experiments" / "technology_tournament" / "round_b" / "harness.ps1"
)
ROUND_B_LIFECYCLE_HARNESS_PATH = (
    ROOT
    / "experiments"
    / "technology_tournament"
    / "round_b"
    / "lifecycle_harness.ps1"
)
ROUND_B_PACKAGE_HARNESS_PATH = (
    ROOT
    / "experiments"
    / "technology_tournament"
    / "round_b"
    / "package_lifecycle.ps1"
)
ROUND_B_BUILD_RECIPE_PATH = (
    ROOT
    / "experiments"
    / "technology_tournament"
    / "round_b"
    / "build_round_b.ps1"
)
ROUND_B_OFFICIAL_WPF_SC_PATH = (
    ROOT
    / "artifacts"
    / "technology_tournament"
    / "build"
    / "round_b"
    / "wpf_sc_shell"
)
ROUND_B_NETWORK_OBSERVER = "Get-NetTCPConnection+Get-NetUDPEndpoint"
REJECTED_PATH = (
    ROOT
    / "artifacts"
    / "technology_tournament"
    / "raw"
    / "round_a_rejected_pre_workspace_gate.json"
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_inventory(path: Path) -> dict:
    files = []
    for item in sorted(
        (candidate for candidate in path.rglob("*") if candidate.is_file()),
        key=lambda candidate: (
            candidate.relative_to(path).as_posix().casefold(),
            candidate.relative_to(path).as_posix(),
        ),
    ):
        files.append(
            {
                "relative_path": item.relative_to(path).as_posix(),
                "bytes": item.stat().st_size,
                "sha256": sha256_file(item),
            }
        )
    rows = "".join(
        f"{item['relative_path']}\0{item['bytes']}\0{item['sha256']}\n"
        for item in files
    )
    return {
        "tree_sha256": hashlib.sha256(rows.encode("utf-8")).hexdigest(),
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "files": files,
    }


class FrozenTournamentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
        cls.cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        cls.results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        cls.packaging = json.loads(PACKAGING_PATH.read_text(encoding="utf-8"))
        cls.scorecard = json.loads(SCORECARD_PATH.read_text(encoding="utf-8"))

    def test_protocol_was_frozen_before_measurement_and_weights_sum_to_100(self) -> None:
        self.assertEqual(self.protocol["status"], "frozen-before-measurement")
        self.assertEqual(sum(self.protocol["weights"].values()), 100)
        self.assertEqual(self.protocol["protocol_id"], self.cases["protocol_id"])
        self.assertEqual(self.protocol["protocol_id"], self.results["protocol_id"])

    def test_cases_are_unique_and_cover_the_fixed_suite(self) -> None:
        case_ids = [case["id"] for case in self.cases["cases"]]
        self.assertEqual(len(case_ids), 16)
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertIn("T07_IDEMPOTENT_REPLAY", case_ids)
        self.assertIn("T11_BLOCK_NUL", case_ids)
        self.assertIn("T15_TRUNCATED_JOURNAL_RECOVERY", case_ids)
        self.assertIn("T16_MALFORMED_REQUEST", case_ids)

    def test_results_bind_the_exact_protocol_cases_and_harness(self) -> None:
        protocol_digest = hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()
        cases_digest = hashlib.sha256(CASES_PATH.read_bytes()).hexdigest()
        harness_digest = hashlib.sha256(
            (ROOT / "experiments" / "technology_tournament" / "harness.py").read_bytes()
        ).hexdigest()
        self.assertEqual(self.results["protocol_sha256"], protocol_digest)
        self.assertEqual(self.results["cases_sha256"], cases_digest)
        self.assertEqual(self.results["harness_sha256"], harness_digest)

    def test_three_contenders_pass_all_functional_repetitions_and_workspace_gate(self) -> None:
        self.assertEqual(
            set(self.results["contenders"]),
            {"python_core", "dotnet_windows_core", "rust_core"},
        )
        expected_ids = {case["id"] for case in self.cases["cases"]}
        for contender_id, contender in self.results["contenders"].items():
            with self.subTest(contender=contender_id):
                self.assertEqual(contender["build"]["exit_code"], 0)
                self.assertEqual(len(contender["functional"]), 3)
                for repetition in contender["functional"]:
                    self.assertTrue(repetition["unauthorized_workspace_probe"]["passed"])
                    self.assertEqual(
                        {sample["case_id"] for sample in repetition["samples"]},
                        expected_ids,
                    )
                    self.assertTrue(all(sample["passed"] for sample in repetition["samples"]))
                self.assertEqual(contender["cold_start"]["valid_samples"], 21)
                self.assertEqual(contender["warm"]["valid_samples"], 100)
                self.assertEqual(contender["warm"]["network_snapshot"], {"tcp": [], "udp": []})

    def test_rejected_pre_gate_run_is_preserved_as_distinct_evidence(self) -> None:
        self.assertTrue(REJECTED_PATH.is_file())
        self.assertNotEqual(
            hashlib.sha256(REJECTED_PATH.read_bytes()).hexdigest(),
            hashlib.sha256(RESULTS_PATH.read_bytes()).hexdigest(),
        )

    def test_packaged_variants_pass_the_same_contract_and_are_self_describing(self) -> None:
        self.assertEqual(
            set(self.packaging["variants"]),
            {
                "python_embedded_runtime",
                "python_pyinstaller_onedir",
                "python_pyinstaller_onefile",
                "dotnet_fdd_single",
                "dotnet_sc_single",
                "dotnet_native_aot",
                "rust_native",
            },
        )
        self.assertEqual(
            self.packaging["core_harness_sha256"],
            hashlib.sha256(
                (ROOT / "experiments" / "technology_tournament" / "harness.py").read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(
            self.packaging["package_harness_sha256"],
            hashlib.sha256(
                (ROOT / "experiments" / "technology_tournament" / "package_harness.py").read_bytes()
            ).hexdigest(),
        )
        for variant_id, variant in self.packaging["variants"].items():
            with self.subTest(variant=variant_id):
                self.assertNotIn("fatal", variant)
                self.assertEqual(variant["build"]["exit_code"], 0)
                self.assertTrue(variant["functional"]["unauthorized_workspace_probe"]["passed"])
                self.assertTrue(all(sample["passed"] for sample in variant["functional"]["samples"]))
                self.assertEqual(variant["cold_start"]["valid_samples"], 21)
                self.assertEqual(variant["warm"]["valid_samples"], 100)
                self.assertEqual(variant["warm"]["network_snapshot"], {"tcp": [], "udp": []})

    def test_scorecard_is_derived_and_promotion_obeys_the_frozen_rule(self) -> None:
        self.assertTrue(self.scorecard["weights_unchanged"])
        self.assertEqual(
            self.scorecard["source_results_sha256"],
            hashlib.sha256(PACKAGING_PATH.read_bytes()).hexdigest(),
        )
        performance_frontier = self.scorecard["pareto"]["self_contained_performance"]
        self.assertIn("rust_native", performance_frontier)
        self.assertEqual(
            self.scorecard["round_a_promotion"]["integrated_finalists"],
            ["dotnet_windows_core", "rust_core"],
        )
        self.assertFalse(self.scorecard["round_a_promotion"]["winner_declared"])
        self.assertTrue(all(not score["disqualified"] for score in self.scorecard["scores"].values()))
        scores = self.scorecard["scores"]
        best = max(score["provisional_normalized_100"] for score in scores.values())
        self.assertLessEqual(best - scores["dotnet_native_aot"]["provisional_normalized_100"], 7)
        self.assertLessEqual(best - scores["rust_native"]["provisional_normalized_100"], 7)


class RoundBFinalScorecardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.protocol = load_json(PROTOCOL_PATH)
        cls.scorecard = load_json(ROUND_B_SCORECARD_PATH)
        cls.supply = load_json(ROUND_B_SUPPLY_PATH)
        cls.reproducibility = load_json(ROUND_B_REPRODUCIBILITY_PATH)
        cls.finalist_raw = {}
        for system_id, evidence in cls.scorecard["source_evidence"][
            "finalists"
        ].items():
            cls.finalist_raw[system_id] = {
                "functional": [
                    load_json(ROOT / record["path"])
                    for record in evidence["functional_runs"]
                ],
                "lifecycle": load_json(ROOT / evidence["lifecycle"]["path"]),
                "package": load_json(
                    ROOT / evidence["package_lifecycle"]["path"]
                ),
            }

    def assert_current_provenance(
        self,
        data: dict,
        expected: dict[str, Path],
        *,
        records_include_bytes: bool,
    ) -> None:
        self.assertEqual(set(data["provenance"]), set(expected))
        expected_record_keys = {"path", "sha256"}
        if records_include_bytes:
            expected_record_keys.add("bytes")
        for name, path in expected.items():
            with self.subTest(provenance=name):
                record = data["provenance"][name]
                self.assertEqual(set(record), expected_record_keys)
                self.assertEqual(
                    record["path"], path.relative_to(ROOT).as_posix()
                )
                self.assertEqual(record["sha256"], sha256_file(path))
                if records_include_bytes:
                    self.assertEqual(record["bytes"], path.stat().st_size)

    def assert_empty_observed_network_snapshot(self, snapshot: dict) -> None:
        self.assertEqual(snapshot["observer"], ROUND_B_NETWORK_OBSERVER)
        self.assertIs(snapshot["observer_ok"], True)
        self.assertEqual(snapshot["tcp"], [])
        self.assertEqual(snapshot["udp"], [])

    def test_only_numbered_final_runs_feed_round_b_scores(self) -> None:
        expected_systems = {"dotnet-wpf", "dotnet-wpf-rust"}
        self.assertEqual(set(self.scorecard["scores"]), expected_systems)
        generator = self.scorecard["source_evidence"]["generator"]
        self.assertEqual(
            hashlib.sha256((ROOT / generator["path"]).read_bytes()).hexdigest(),
            generator["sha256"],
        )
        self.assertEqual(
            set(self.scorecard["source_evidence"]["finalists"]), expected_systems
        )
        for system_id, evidence in self.scorecard["source_evidence"][
            "finalists"
        ].items():
            with self.subTest(system=system_id):
                functional = evidence["functional_runs"]
                self.assertEqual(len(functional), 3)
                self.assertEqual(
                    [Path(item["path"]).stem[-5:] for item in functional],
                    ["run01", "run02", "run03"],
                )
                for item in functional:
                    path = ROOT / item["path"]
                    self.assertEqual(
                        hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"]
                    )
        used_paths = {
            item["path"]
            for evidence in self.scorecard["source_evidence"]["finalists"].values()
            for item in evidence["functional_runs"]
        }
        self.assertTrue(
            used_paths.isdisjoint(
                self.scorecard["source_evidence"]["excluded_stale_inputs"]
            )
        )

    def test_all_finalist_raw_inputs_bind_current_harnesses_and_contracts(self) -> None:
        expected_provenance = {
            "functional": {
                "harness": ROUND_B_FUNCTIONAL_HARNESS_PATH,
                "protocol": PROTOCOL_PATH,
                "cases": CASES_PATH,
            },
            "lifecycle": {
                "harness": ROUND_B_LIFECYCLE_HARNESS_PATH,
                "protocol": PROTOCOL_PATH,
                "cases": CASES_PATH,
            },
            "package": {
                "harness": ROUND_B_PACKAGE_HARNESS_PATH,
                "cases": CASES_PATH,
                "protocol": PROTOCOL_PATH,
                "build_recipe": ROUND_B_BUILD_RECIPE_PATH,
            },
        }
        for system_id, raw in self.finalist_raw.items():
            evidence = self.scorecard["source_evidence"]["finalists"][system_id]
            with self.subTest(system=system_id, evidence="lifecycle-source"):
                lifecycle_path = ROOT / evidence["lifecycle"]["path"]
                self.assertEqual(
                    evidence["lifecycle"]["sha256"], sha256_file(lifecycle_path)
                )
            with self.subTest(system=system_id, evidence="package-source"):
                package_path = ROOT / evidence["package_lifecycle"]["path"]
                self.assertEqual(
                    evidence["package_lifecycle"]["sha256"],
                    sha256_file(package_path),
                )
            for run_number, functional in enumerate(raw["functional"], start=1):
                with self.subTest(
                    system=system_id,
                    evidence="functional-provenance",
                    run=run_number,
                ):
                    self.assert_current_provenance(
                        functional,
                        expected_provenance["functional"],
                        records_include_bytes=False,
                    )
            with self.subTest(system=system_id, evidence="lifecycle-provenance"):
                self.assert_current_provenance(
                    raw["lifecycle"],
                    expected_provenance["lifecycle"],
                    records_include_bytes=False,
                )
            with self.subTest(system=system_id, evidence="package-provenance"):
                self.assert_current_provenance(
                    raw["package"],
                    expected_provenance["package"],
                    records_include_bytes=True,
                )

    def test_finalist_network_observers_are_fail_closed_and_empty(self) -> None:
        for system_id, raw in self.finalist_raw.items():
            for run_number, functional in enumerate(raw["functional"], start=1):
                with self.subTest(system=system_id, run=run_number, scope="ui"):
                    aggregate = functional["resources"]["network_snapshot"]
                    self.assert_empty_observed_network_snapshot(aggregate)
                    self.assertEqual(len(aggregate["samples"]), 18)
                    for snapshot in aggregate["samples"]:
                        self.assert_empty_observed_network_snapshot(snapshot)
                    malformed = next(
                        sample
                        for sample in functional["functional"]["cases"]
                        if sample["case_id"] == "T16_MALFORMED_REQUEST"
                    )
                    self.assert_empty_observed_network_snapshot(
                        malformed["transport_evidence"]["network_snapshot"]
                    )

            package = raw["package"]
            launches = {
                "install": package["install"]["launch"],
                "update": package["update"]["launch"],
                "rollback": package["rollback"]["launch"],
                "reinstall": package["reinstall"]["launch"],
            }
            self.assertEqual(len(launches), 4)
            for launch_name, launch in launches.items():
                with self.subTest(
                    system=system_id, launch=launch_name, scope="package"
                ):
                    self.assertIs(launch["network_observer_ok"], True)
                    self.assertEqual(len(launch["network_snapshots"]), 2)
                    for snapshot in launch["network_snapshots"]:
                        self.assert_empty_observed_network_snapshot(snapshot)

    def test_malformed_transport_is_real_redacted_and_recovers_in_process(self) -> None:
        for system_id, raw in self.finalist_raw.items():
            for run_number, functional in enumerate(raw["functional"], start=1):
                malformed = next(
                    sample
                    for sample in functional["functional"]["cases"]
                    if sample["case_id"] == "T16_MALFORMED_REQUEST"
                )
                transport = malformed["transport_evidence"]
                with self.subTest(system=system_id, run=run_number):
                    self.assertEqual(malformed["route"], "raw_core_transport_probe")
                    self.assertIs(malformed["passed"], True)
                    self.assertEqual(malformed["failures"], [])
                    self.assertIs(transport["passed"], True)
                    self.assertEqual(transport["failures"], [])
                    self.assertEqual(
                        transport["stderr_record"],
                        "BAXY_PROTOCOL_ERROR malformed_json",
                    )
                    self.assertIs(transport["stderr_redacted"], True)
                    self.assertEqual(
                        transport["malformed_stdout_protocol_records"], 0
                    )
                    self.assertEqual(
                        transport["filesystem_snapshot_scope"],
                        "complete_workspace_before_recovery",
                    )
                    self.assertEqual(
                        set(transport["workspace_before_malformed"]),
                        {"root_exists", "entries"},
                    )
                    self.assertEqual(
                        transport["workspace_before_malformed"],
                        transport["workspace_after_malformed_before_recovery"],
                    )
                    self.assertIs(transport["filesystem_unchanged"], True)
                    # The valid recovery is sent to the still-running probe server.
                    self.assertIs(transport["process_survived"], True)
                    self.assertIs(transport["recovery_response_valid"], True)
                    self.assertEqual(transport["recovery_response_state"], "done")
                    self.assertEqual(transport["exit_code"], 0)
                    self.assertIs(transport["timed_out"], False)

    def test_keyboard_evidence_covers_complete_seven_control_cycles(self) -> None:
        expected_controls = {
            ("InvocationInput", "ID de invocación de prueba"),
            ("MessageInput", "Mensaje para BAXY"),
            ("SendButton", "Enviar mensaje"),
            ("ContrastButton", "Alternar contraste alto"),
            ("", "Crear una nota"),
            ("", "Leer una nota"),
            ("", "Mover a papelera"),
        }
        for system_id, raw in self.finalist_raw.items():
            for run_number, functional in enumerate(raw["functional"], start=1):
                accessibility = functional["accessibility"]
                controls = accessibility["focusable_controls"]
                keys = [control["key"] for control in controls]
                start = accessibility["focus_start_key"]
                forward = accessibility["forward_focus_order"]
                reverse = accessibility["reverse_focus_order"]
                with self.subTest(system=system_id, run=run_number):
                    self.assertEqual(len(controls), 7)
                    self.assertEqual(len(set(keys)), 7)
                    self.assertEqual(
                        {
                            (control["automation_id"], control["name"])
                            for control in controls
                        },
                        expected_controls,
                    )
                    self.assertIn(start, keys)
                    self.assertEqual(len(forward), 8)
                    self.assertEqual(len(reverse), 8)
                    self.assertEqual(forward[0], start)
                    self.assertEqual(forward[-1], start)
                    self.assertEqual(reverse[0], start)
                    self.assertEqual(reverse[-1], start)
                    self.assertEqual(set(forward[:-1]), set(keys))
                    self.assertEqual(len(set(forward[:-1])), 7)
                    self.assertEqual(
                        reverse, [start, *reversed(forward[1:-1]), start]
                    )
                    self.assertIs(
                        accessibility["forward_focus_cycle_complete"], True
                    )
                    self.assertIs(
                        accessibility["reverse_focus_cycle_complete"], True
                    )

    def test_package_alias_ads_and_unique_launch_count_are_explicit(self) -> None:
        for system_id, raw in self.finalist_raw.items():
            package = raw["package"]
            runtime = package["runtime_resolution_probe"]
            integrity = package["package_integrity"]
            tampered = package["tampered_update"]
            with self.subTest(system=system_id):
                self.assertIs(runtime["shared_with_install_launch"], True)
                self.assertEqual(runtime["first_launch"], package["install"]["launch"])
                self.assertIs(integrity["alternate_data_stream_observed"], True)
                self.assertTrue(integrity["alternate_data_stream_name"])
                self.assertIs(
                    integrity["alternate_data_stream_payload_rejected"], True
                )
                self.assertIs(tampered["alternate_data_stream_rejected"], True)
                self.assertEqual(
                    tampered["current_after_alternate_data_stream_tamper"], "1.0.1"
                )
                self.assertIs(tampered["current_unchanged"], True)
                self.assertIs(package["gates"]["tampered_payload_rejected"], True)

                offline_cell = self.scorecard["scores"][system_id]["cells"][
                    "security.offline_and_no_listeners"
                ]
                self.assertEqual(
                    offline_cell["evidence"]["package_unique_launches_checked"], 4
                )

    def test_complete_official_wpf_tree_matches_both_reproducible_trees(self) -> None:
        reproduced = self.reproducibility["comparisons"]["wpf_self_contained"]
        # Auditable from the tree on any machine: the two recorded runs agree.
        self.assertEqual(reproduced["run_01"]["file_count"], 6)
        self.assertEqual(reproduced["run_01"], reproduced["run_02"])
        self.assertIs(reproduced["primary_artifact"]["equal"], True)
        if not ROUND_B_OFFICIAL_WPF_SC_PATH.is_dir():
            # The official build output is 69 MB and versioned in no repository
            # of this project: **/build/ excludes it on purpose. Without it only
            # the published inventories above can be checked.
            self.skipTest(
                "environment: the official Round B WPF build tree is not on "
                "this machine"
            )
        official = tree_inventory(ROUND_B_OFFICIAL_WPF_SC_PATH)
        self.assertEqual(official, reproduced["run_01"])
        self.assertEqual(official, reproduced["run_02"])

    def test_same_host_reproducibility_is_scored_conservatively_one_of_two(self) -> None:
        self.assertTrue(self.reproducibility["passed"])
        for system_id, score in self.scorecard["scores"].items():
            with self.subTest(system=system_id):
                cell = score["cells"]["installation.reproducible_clean_build"]
                self.assertEqual(cell["points"], 1)
                self.assertEqual(cell["maximum"], 2)
                self.assertIs(cell["evidence"]["same_host_all_passed"], True)
                self.assertIs(
                    cell["evidence"]["complete_official_wpf_tree_bound"], True
                )
                limitations = " ".join(cell["limitations"]).lower()
                self.assertIn("cross-host", limitations)
                self.assertIn("clean-vm", limitations)

    def test_round_b_has_complete_conservative_100_point_cells(self) -> None:
        expected_categories = self.scorecard["weights"]
        for system_id, score in self.scorecard["scores"].items():
            with self.subTest(system=system_id):
                self.assertFalse(score["disqualified"])
                self.assertTrue(all(score["hard_gates"].values()))
                self.assertEqual(score["maximum_points"], 100)
                self.assertEqual(
                    sum(cell["maximum"] for cell in score["cells"].values()), 100
                )
                self.assertNotIn("NE", {cell["status"] for cell in score["cells"].values()})
                self.assertTrue(
                    all(cell["criterion"] for cell in score["cells"].values())
                )
                self.assertEqual(set(score["category_points"]), set(expected_categories))
                for category, maximum in expected_categories.items():
                    self.assertLessEqual(score["category_points"][category], maximum)
                self.assertEqual(
                    score["cells"][
                        "ux.accessible_names_live_regions_and_screen_reader"
                    ]["points"],
                    1,
                )
                self.assertEqual(
                    score["cells"]["security.verified_effect_idempotency_and_tamper_evidence"][
                        "points"
                    ],
                    0,
                )

    def test_reproducibility_and_supply_chain_bind_official_hashes(self) -> None:
        self.assertTrue(self.reproducibility["passed"])
        self.assertTrue(self.reproducibility["gates"]["all_passed"])
        recipe = self.reproducibility["recipe"]
        self.assertEqual(
            hashlib.sha256((ROOT / recipe["path"]).read_bytes()).hexdigest(),
            recipe["sha256"],
        )
        for pin in (
            self.reproducibility["toolchains"]["dotnet"],
            self.reproducibility["toolchains"]["rust"],
        ):
            self.assertEqual(
                hashlib.sha256((ROOT / pin["pin_file"]).read_bytes()).hexdigest(),
                pin["pin_sha256"],
            )
        reports = {item["system_id"]: item for item in self.supply["systems"]}
        comparisons = self.reproducibility["comparisons"]
        self.assertEqual(
            comparisons["wpf_self_contained"]["primary_artifact"][
                "run_01_sha256"
            ],
            reports["dotnet-wpf"]["shell_sha256"],
        )
        self.assertEqual(
            comparisons["dotnet_native_aot"]["primary_artifact"]["run_01_sha256"],
            reports["dotnet-wpf"]["core_sha256"],
        )
        self.assertEqual(
            comparisons["rust_static"]["primary_artifact"]["run_01_sha256"],
            reports["dotnet-wpf-rust"]["core_sha256"],
        )
        for system_id, report in reports.items():
            with self.subTest(system=system_id):
                sbom_path = ROOT / report["sbom_path"]
                self.assertEqual(
                    hashlib.sha256(sbom_path.read_bytes()).hexdigest(),
                    report["sbom_sha256"],
                )

    def test_pareto_winner_and_webview_rejections_are_preserved(self) -> None:
        self.assertEqual(
            list(self.scorecard["pareto"]["orientations"]),
            self.protocol["pareto_dimensions"],
        )
        inherited = self.scorecard["pareto"]["inherited_core_dimensions"]
        self.assertEqual(
            inherited["dimensions"],
            ["build_seconds", "implementation_source_lines"],
        )
        round_a_sources = self.scorecard["source_evidence"][
            "round_a_pareto_inherited_core_metrics"
        ]
        for record in round_a_sources.values():
            self.assertEqual(sha256_file(ROOT / record["path"]), record["sha256"])
        self.assertEqual(
            set(self.scorecard["pareto"]["frontier"]),
            {"dotnet-wpf", "dotnet-wpf-rust"},
        )
        self.assertTrue(self.scorecard["decision"]["winner_declared"])
        self.assertEqual(self.scorecard["decision"]["winner_id"], "dotnet-wpf")
        rejected = {
            item["system_id"]: item
            for item in self.scorecard["rejected_candidates"]
        }
        self.assertEqual(set(rejected), {"dotnet-webview", "tauri-rust"})
        for system_id, item in rejected.items():
            with self.subTest(system=system_id):
                self.assertTrue(item["disqualified"])
                self.assertIn("no_network", item["gate_failures"])
                self.assertGreater(
                    item["network"]["tcp_records"]
                    + item["network"]["udp_records"],
                    0,
                )


if __name__ == "__main__":
    unittest.main()
