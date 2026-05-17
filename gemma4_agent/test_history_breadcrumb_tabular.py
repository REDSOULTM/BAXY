"""Tabular breadcrumb extension (hotfix D 2026-05-17).

Bug repro: user asked "cuánto espacio en C", tool returned disks
list with all drives, LLM only verbalized C in its reply. Next
turn ("y en F?") had no F data in history because the disks list
was dropped. LLM hallucinated 350 GB.

The pure helper `stitch_breadcrumbs` exposes the logic; we exercise
it directly, no AgentRunner instantiation needed.
"""
from __future__ import annotations

import json
import unittest

from gemma4_agent.agent_compaction import stitch_breadcrumbs


class TabularBreadcrumbTest(unittest.TestCase):
    def test_disks_list_stitched_into_reply(self) -> None:
        disks = [
            {"DeviceID": "C:", "FreeSpace": 77768957952},
            {"DeviceID": "F:", "FreeSpace": 96764792832},
        ]
        hist = [
            {"role": "user", "content": "cuánto espacio en C"},
            {"role": "assistant", "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "system", "arguments": '{"action":"disk"}'}}]},
            {"role": "tool", "tool_call_id": "c1",
             "content": json.dumps({"ok": True, "disks": disks})},
            {"role": "assistant", "content": "Te quedan ~74 GB libres en C."},
        ]
        out = stitch_breadcrumbs(hist)
        final_text = ""
        for m in out:
            if m.get("role") == "assistant" and not m.get("tool_calls"):
                final_text += str(m.get("content") or "")
        # Both drives' data must be reachable in the breadcrumb.
        self.assertIn("F:", final_text, f"F not in breadcrumb: {final_text!r}")
        self.assertIn("96764792832", final_text)

    def test_disks_breadcrumb_present_only_once(self) -> None:
        # When the reply already mentions one of the rows verbatim,
        # the breadcrumb should still attach the full table so the
        # other rows are recoverable. The reply must not duplicate
        # itself though.
        disks = [
            {"DeviceID": "C:", "FreeSpace": 100},
            {"DeviceID": "D:", "FreeSpace": 200},
        ]
        hist = [
            {"role": "user", "content": "cuánto espacio"},
            {"role": "assistant", "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "system", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1",
             "content": json.dumps({"ok": True, "disks": disks})},
            {"role": "assistant", "content": "100 bytes en C."},
        ]
        out = stitch_breadcrumbs(hist)
        final_text = ""
        for m in out:
            if m.get("role") == "assistant" and not m.get("tool_calls"):
                final_text += str(m.get("content") or "")
        # D should be reachable via the breadcrumb even though C is in
        # the reply.
        self.assertIn("DeviceID=D:", final_text)
        # Only one breadcrumb block.
        self.assertEqual(final_text.count("[breadcrumb:"), 1)

    def test_processes_list_stitched(self) -> None:
        # Generalization: another tabular key.
        procs = [
            {"name": "chrome.exe", "pid": 1234, "mem_mb": 512},
            {"name": "code.exe", "pid": 5678, "mem_mb": 1024},
        ]
        hist = [
            {"role": "user", "content": "qué procesos pesan más"},
            {"role": "assistant", "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "system", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1",
             "content": json.dumps({"ok": True, "processes": procs})},
            {"role": "assistant", "content": "Los más pesados son chrome y vscode."},
        ]
        out = stitch_breadcrumbs(hist)
        final_text = ""
        for m in out:
            if m.get("role") == "assistant" and not m.get("tool_calls"):
                final_text += str(m.get("content") or "")
        self.assertIn("pid=1234", final_text)
        self.assertIn("pid=5678", final_text)

    def test_games_list_stitched(self) -> None:
        # Hotfix E 2026-05-17: steam.list_library returns 'games'.
        games = [
            {"appid": 730, "name": "CS2"},
            {"appid": 570, "name": "Dota 2"},
        ]
        hist = [
            {"role": "user", "content": "qué juegos tengo"},
            {"role": "assistant", "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "steam", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1",
             "content": json.dumps({"ok": True, "games": games})},
            {"role": "assistant", "content": "Tenés CS2 y Dota 2."},
        ]
        out = stitch_breadcrumbs(hist)
        final_text = ""
        for m in out:
            if m.get("role") == "assistant" and not m.get("tool_calls"):
                final_text += str(m.get("content") or "")
        self.assertIn("appid=730", final_text)
        self.assertIn("appid=570", final_text)

    def test_events_list_stitched(self) -> None:
        # Hotfix E 2026-05-17: local_calendar.list returns 'events'.
        events = [
            {"id": "e1", "title": "reunión equipo", "start": "2026-05-18 10:00"},
            {"id": "e2", "title": "dentista", "start": "2026-05-19 15:00"},
        ]
        hist = [
            {"role": "user", "content": "qué tengo agendado"},
            {"role": "assistant", "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "local_calendar", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1",
             "content": json.dumps({"ok": True, "events": events})},
            {"role": "assistant", "content": "Tenés 2 eventos esta semana."},
        ]
        out = stitch_breadcrumbs(hist)
        final_text = ""
        for m in out:
            if m.get("role") == "assistant" and not m.get("tool_calls"):
                final_text += str(m.get("content") or "")
        self.assertIn("title=reunión equipo", final_text)
        self.assertIn("title=dentista", final_text)

    def test_empty_or_non_list_tabular_is_skipped(self) -> None:
        # `disks: []` and `disks: "C:"` must not produce a breadcrumb.
        for bad in ([], "C:", 42, None):
            hist = [
                {"role": "user", "content": "x"},
                {"role": "assistant", "tool_calls": [
                    {"id": "c1", "type": "function",
                     "function": {"name": "system", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "c1",
                 "content": json.dumps({"ok": True, "disks": bad})},
                {"role": "assistant", "content": "ok."},
            ]
            out = stitch_breadcrumbs(hist)
            final_text = ""
            for m in out:
                if m.get("role") == "assistant" and not m.get("tool_calls"):
                    final_text += str(m.get("content") or "")
            self.assertNotIn("[breadcrumb:", final_text,
                             f"bad value {bad!r} should not stitch")


if __name__ == "__main__":
    unittest.main()
