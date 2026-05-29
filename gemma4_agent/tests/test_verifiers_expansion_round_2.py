"""Tests for the 10 new round-2 verifiers (hotfix I 2026-05-17).

Same contract as the F batch: confirmed=False on tool failure,
confirmed=None on absent evidence, confirmed=True on present.
NEVER inspects natural-language text.
"""
from __future__ import annotations

import os
import tempfile
import unittest

from gemma4_agent.safety_pkg.verifiers import (
    verify_browser_real,
    verify_contacts,
    verify_database,
    verify_device_settings,
    verify_download,
    verify_local_calendar,
    verify_network,
    verify_notes_tasks,
    verify_package,
    verify_reminder,
)


class VerifyBrowserRealTest(unittest.TestCase):
    def test_click_with_ok_is_confirmed(self) -> None:
        out = verify_browser_real({"action": "click"}, {"ok": True})
        self.assertIs(out.confirmed, True)

    def test_extract_with_chars_is_confirmed(self) -> None:
        out = verify_browser_real(
            {"action": "extract"}, {"ok": True, "extracted_chars": 500},
        )
        self.assertIs(out.confirmed, True)

    def test_extract_no_text_is_unverifiable(self) -> None:
        out = verify_browser_real({"action": "extract"}, {"ok": True})
        self.assertIsNone(out.confirmed)

    def test_screenshot_with_path_is_confirmed(self) -> None:
        out = verify_browser_real(
            {"action": "screenshot"}, {"ok": True, "path": "C:\\shot.png"},
        )
        self.assertIs(out.confirmed, True)


class VerifyDeviceSettingsTest(unittest.TestCase):
    def test_wifi_connect_success(self) -> None:
        out = verify_device_settings(
            {"action": "wifi_connect"}, {"ok": True, "wifi_connected": True},
        )
        self.assertIs(out.confirmed, True)

    def test_wifi_connect_no_confirmation_is_unverifiable(self) -> None:
        out = verify_device_settings({"action": "wifi_connect"}, {"ok": True})
        self.assertIsNone(out.confirmed)

    def test_bluetooth_toggle_state_readback(self) -> None:
        out = verify_device_settings(
            {"action": "bluetooth_on"}, {"ok": True, "bluetooth_on": True},
        )
        self.assertIs(out.confirmed, True)


class VerifyNetworkTest(unittest.TestCase):
    def test_ping_success(self) -> None:
        out = verify_network(
            {"action": "ping"}, {"ok": True, "ping": {"success": True}},
        )
        self.assertIs(out.confirmed, True)

    def test_ping_unreachable_is_unverifiable(self) -> None:
        out = verify_network({"action": "ping"}, {"ok": True, "ping": {}})
        self.assertIsNone(out.confirmed)

    def test_dns_with_addresses_confirmed(self) -> None:
        out = verify_network(
            {"action": "dns"}, {"ok": True, "addresses": ["1.2.3.4"]},
        )
        self.assertIs(out.confirmed, True)

    def test_port_check_open_confirmed(self) -> None:
        out = verify_network(
            {"action": "port_check"}, {"ok": True, "port_open": True},
        )
        self.assertIs(out.confirmed, True)


class VerifyPackageTest(unittest.TestCase):
    def test_install_installed_flag(self) -> None:
        out = verify_package(
            {"action": "install"}, {"ok": True, "installed": True},
        )
        self.assertIs(out.confirmed, True)

    def test_install_already_present(self) -> None:
        out = verify_package(
            {"action": "install"},
            {"ok": True, "package_already_present": True},
        )
        self.assertIs(out.confirmed, True)

    def test_install_no_confirmation_is_unverifiable(self) -> None:
        out = verify_package({"action": "install"}, {"ok": True})
        self.assertIsNone(out.confirmed)


class VerifyDownloadTest(unittest.TestCase):
    def test_fetch_with_real_file(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 1024)
            p = f.name
        try:
            out = verify_download(
                {"action": "fetch"}, {"ok": True, "dst_path": p},
            )
            self.assertIs(out.confirmed, True)
        finally:
            os.unlink(p)

    def test_fetch_missing_file_is_failed(self) -> None:
        out = verify_download(
            {"action": "fetch"},
            {"ok": True, "dst_path": r"C:\nonexistent\nope.zip"},
        )
        self.assertIs(out.confirmed, False)

    def test_fetch_size_mismatch_is_failed(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 100)
            p = f.name
        try:
            out = verify_download(
                {"action": "fetch"},
                {"ok": True, "dst_path": p, "expected_size": 200},
            )
            self.assertIs(out.confirmed, False)
        finally:
            os.unlink(p)


class VerifyLocalCalendarTest(unittest.TestCase):
    def test_event_create_with_id(self) -> None:
        out = verify_local_calendar(
            {"action": "event_create"},
            {"ok": True, "event": {"id": "evt_123"}},
        )
        self.assertIs(out.confirmed, True)

    def test_event_create_no_id_is_unverifiable(self) -> None:
        out = verify_local_calendar(
            {"action": "event_create"}, {"ok": True},
        )
        self.assertIsNone(out.confirmed)


class VerifyNotesTasksTest(unittest.TestCase):
    def test_note_create_with_id(self) -> None:
        out = verify_notes_tasks(
            {"action": "note_create"},
            {"ok": True, "note": {"id": "n_1"}},
        )
        self.assertIs(out.confirmed, True)

    def test_task_create_with_id(self) -> None:
        out = verify_notes_tasks(
            {"action": "task_create"},
            {"ok": True, "task": {"id": "t_1"}},
        )
        self.assertIs(out.confirmed, True)

    def test_note_create_no_id_is_unverifiable(self) -> None:
        out = verify_notes_tasks(
            {"action": "note_create"}, {"ok": True},
        )
        self.assertIsNone(out.confirmed)


class VerifyReminderTest(unittest.TestCase):
    def test_create_with_task_name(self) -> None:
        out = verify_reminder(
            {"action": "create"},
            {"ok": True, "task_name": "Gemma\\rem_1"},
        )
        self.assertIs(out.confirmed, True)

    def test_create_with_id(self) -> None:
        out = verify_reminder(
            {"action": "create"}, {"ok": True, "id": "rem_abc"},
        )
        self.assertIs(out.confirmed, True)

    def test_create_no_id_is_unverifiable(self) -> None:
        out = verify_reminder({"action": "create"}, {"ok": True})
        self.assertIsNone(out.confirmed)


class VerifyContactsTest(unittest.TestCase):
    def test_create_with_id(self) -> None:
        out = verify_contacts(
            {"action": "create"},
            {"ok": True, "contact": {"id": "c_1"}},
        )
        self.assertIs(out.confirmed, True)

    def test_resolve_with_match(self) -> None:
        out = verify_contacts(
            {"action": "resolve_recipient"},
            {"ok": True, "match": {"id": "c_2"}},
        )
        self.assertIs(out.confirmed, True)

    def test_resolve_no_match_is_unverifiable(self) -> None:
        out = verify_contacts(
            {"action": "resolve_recipient"}, {"ok": True},
        )
        self.assertIsNone(out.confirmed)


class VerifyDatabaseTest(unittest.TestCase):
    def test_execute_with_rows_affected(self) -> None:
        out = verify_database(
            {"action": "execute"}, {"ok": True, "rows_affected": 3},
        )
        self.assertIs(out.confirmed, True)

    def test_query_with_rows_returned(self) -> None:
        out = verify_database(
            {"action": "query"}, {"ok": True, "rows_returned": 42},
        )
        self.assertIs(out.confirmed, True)

    def test_query_with_rows_list_counts(self) -> None:
        out = verify_database(
            {"action": "query"},
            {"ok": True, "rows": [{"a": 1}, {"a": 2}]},
        )
        self.assertIs(out.confirmed, True)

    def test_execute_no_rows_is_unverifiable(self) -> None:
        out = verify_database({"action": "execute"}, {"ok": True})
        self.assertIsNone(out.confirmed)


if __name__ == "__main__":
    unittest.main()
