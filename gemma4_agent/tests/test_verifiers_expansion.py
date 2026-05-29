"""Tests for the 5 new verifiers (hotfix F 2026-05-17).

Contract: each verifier returns confirmed=False on tool-reported
failure, confirmed=None when evidence absent, confirmed=True on
structural evidence. NO verifier inspects natural-language text.
"""
from __future__ import annotations

import os
import tempfile
import unittest

from gemma4_agent.safety_pkg.verifiers import (
    verify_email,
    verify_media,
    verify_notification,
    verify_office,
    verify_routine,
)


class VerifyMediaTest(unittest.TestCase):
    def test_play_with_auto_play_played_and_verified_is_ok(self) -> None:
        out = verify_media(
            {"action": "play"},
            {"ok": True, "auto_play_info": {"played": True, "verified": True}},
        )
        self.assertIs(out.confirmed, True)

    def test_play_with_url_but_no_playback_is_unverifiable(self) -> None:
        out = verify_media(
            {"action": "play"},
            {"ok": True, "url": "https://netflix.com/watch/123"},
        )
        self.assertIsNone(out.confirmed)

    def test_play_with_query_match_only_is_ok(self) -> None:
        out = verify_media(
            {"action": "play"},
            {"ok": True, "auto_play_info": {"played": True, "query_match": True}},
        )
        self.assertIs(out.confirmed, True)

    def test_pause_is_ok_when_dispatched(self) -> None:
        out = verify_media({"action": "pause"}, {"ok": True})
        self.assertIs(out.confirmed, True)

    def test_failed_result_is_failed(self) -> None:
        out = verify_media({"action": "play"}, {"ok": False, "error": "no spotify"})
        self.assertIs(out.confirmed, False)


class VerifyOfficeTest(unittest.TestCase):
    def test_create_with_real_path_is_ok(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
            f.write(b"dummy")
            p = f.name
        try:
            out = verify_office(
                {"action": "create_presentation"},
                {"ok": True, "path": p},
            )
            self.assertIs(out.confirmed, True)
        finally:
            os.unlink(p)

    def test_create_with_missing_path_is_failed(self) -> None:
        out = verify_office(
            {"action": "create_presentation"},
            {"ok": True, "path": r"C:\nonexistent\file_F3_test.pptx"},
        )
        self.assertIs(out.confirmed, False)

    def test_create_with_no_path_is_unverifiable(self) -> None:
        out = verify_office(
            {"action": "create_presentation"},
            {"ok": True},
        )
        self.assertIsNone(out.confirmed)

    def test_empty_file_is_failed(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
            p = f.name
        try:
            out = verify_office(
                {"action": "create_presentation"},
                {"ok": True, "path": p},
            )
            self.assertIs(out.confirmed, False)
        finally:
            os.unlink(p)


class VerifyEmailTest(unittest.TestCase):
    def test_send_with_message_id_is_ok(self) -> None:
        out = verify_email(
            {"action": "send"},
            {"ok": True, "message_id": "abc123"},
        )
        self.assertIs(out.confirmed, True)

    def test_send_with_sent_true_is_ok(self) -> None:
        out = verify_email(
            {"action": "send"},
            {"ok": True, "sent": True},
        )
        self.assertIs(out.confirmed, True)

    def test_send_without_id_is_unverifiable(self) -> None:
        out = verify_email({"action": "send"}, {"ok": True})
        self.assertIsNone(out.confirmed)

    def test_failed_send_is_failed(self) -> None:
        out = verify_email(
            {"action": "send"},
            {"ok": False, "error": "smtp 550"},
        )
        self.assertIs(out.confirmed, False)


class VerifyNotificationTest(unittest.TestCase):
    def test_toast_with_task_name_is_ok(self) -> None:
        out = verify_notification(
            {"action": "toast_schedule"},
            {"ok": True, "task_name": "Gemma4Agent\\toast_1"},
        )
        self.assertIs(out.confirmed, True)

    def test_toast_with_id_is_ok(self) -> None:
        out = verify_notification(
            {"action": "toast_now"},
            {"ok": True, "id": "notif_abc"},
        )
        self.assertIs(out.confirmed, True)

    def test_toast_without_id_is_unverifiable(self) -> None:
        out = verify_notification(
            {"action": "toast_schedule"},
            {"ok": True},
        )
        self.assertIsNone(out.confirmed)


class VerifyRoutineTest(unittest.TestCase):
    def test_create_with_id_is_ok(self) -> None:
        out = verify_routine(
            {"action": "create"},
            {"ok": True, "id": "routine_abc"},
        )
        self.assertIs(out.confirmed, True)

    def test_create_with_resource_id_is_ok(self) -> None:
        out = verify_routine(
            {"action": "create"},
            {"ok": True, "resource_id": "res_xyz"},
        )
        self.assertIs(out.confirmed, True)

    def test_create_without_id_is_unverifiable(self) -> None:
        out = verify_routine(
            {"action": "create"},
            {"ok": True},
        )
        self.assertIsNone(out.confirmed)


if __name__ == "__main__":
    unittest.main()
