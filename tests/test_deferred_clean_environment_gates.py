from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_OPEN = ROOT / "scripts" / "test_app_open.ps1"
GATE14 = ROOT / "scripts" / "test_gate14_clean_environment.ps1"
CHECKLIST = (
    ROOT
    / "contexto"
    / "06_pruebas_y_mediciones"
    / "GATES_APLAZADOS_EQUIPO_LIMPIO.md"
)


class DeferredCleanEnvironmentGateTests(unittest.TestCase):
    def test_app_open_refuses_preexisting_processes_and_data_leaf(self) -> None:
        source = APP_OPEN.read_text(encoding="utf-8")
        for required in (
            "preexisting_notepad",
            "preexisting_baxy_process",
            "The app.open gate data leaf must be absent",
            "data_root_removed",
            "AllowCloseVerifiedNotepadInQuiescentSession",
        ):
            self.assertIn(required, source)

    def test_app_open_publishes_one_step_evidence(self) -> None:
        source = APP_OPEN.read_text(encoding="utf-8")
        self.assertIn("Publish-GateEvidence", source)
        self.assertIn("app_open_gate.json", source)
        self.assertIn("Move-Item -LiteralPath $nextPath", source)

    def test_app_open_reader_accepts_the_full_public_protocol_bound(self) -> None:
        source = APP_OPEN.read_text(encoding="utf-8")
        self.assertIn("$maximumJsonLineBytes = 1024 * 1024", source)
        self.assertIn(
            "A protocol line exceeded the configured byte limit.",
            source,
        )
        self.assertNotIn("$maximumJsonLineBytes = 64 * 1024", source)
        self.assertIn("[Console]::InputEncoding = $Utf8NoBom", source)
        self.assertIn(
            "[Console]::InputEncoding = $previousConsoleInputEncoding",
            source,
        )
        self.assertIn("PathChainHasNoReparsePoint", source)
        self.assertIn("GetFileAttributesW", source)

    def test_gate14_requires_disposable_profile_and_exact_purge_token(self) -> None:
        source = GATE14.read_text(encoding="utf-8")
        self.assertIn("ConfirmDisposableProfile", source)
        self.assertIn("profile_preflight = 'pristine'", source)
        self.assertIn(
            "'--uninstall', '--purge-data', '--confirm-purge-data', '--quiet'",
            source,
        )

    def test_gate14_freezes_required_lifecycle_order(self) -> None:
        source = GATE14.read_text(encoding="utf-8")
        ordered_steps = (
            "install_1.0.0",
            "first_installed_launch",
            "update_1.0.1",
            "rollback_1.0.0",
            "uninstall_keep_data",
            "reinstall_1.0.1",
            "uninstall_purge_data",
        )
        positions = [source.index(step) for step in ordered_steps]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("current.previous has the wrong version", source)
        self.assertIn("keep-data changed the gate canary", source)

    def test_gate14_uses_the_attested_input_versions_instead_of_historical_literals(
        self,
    ) -> None:
        source = GATE14.read_text(encoding="utf-8")

        self.assertNotIn("-ExpectedVersion '1.0.0'", source)
        self.assertNotIn("-ExpectedVersion '1.0.1'", source)
        self.assertIn("$predecessorVersion", source)
        self.assertIn("$candidateVersion", source)

    def test_checklist_keeps_both_gates_pending_by_environment(self) -> None:
        text = CHECKLIST.read_text(encoding="utf-8")
        self.assertIn("pendiente-por-entorno", text)
        self.assertIn("test_app_open.ps1", text)
        self.assertIn("test_gate14_clean_environment.ps1", text)
        self.assertIn("no se ejecutan en el perfil actual", text)


if __name__ == "__main__":
    unittest.main()
